"""End-to-end agent loop test: the real SDK streaming client against a mocked HTTP transport."""

import asyncio
import json

import httpx2
import pytest
from anthropic import AsyncAnthropic, DefaultAsyncHttpxClient

from app.agent import Agent
from app.agent.loop import close_dangling_tool_calls
from app.config import Settings
from app.store import Store
from app.tools import ToolContext, build_registry
from app.transcript import to_transcript


def sse(events: list[dict]) -> bytes:
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events).encode()


def message_events(blocks: list[dict], stop_reason: str) -> list[dict]:
    events = [{
        "type": "message_start",
        "message": {
            "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5",
            "content": [], "stop_reason": None, "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 0},
        },
    }]
    for i, block in enumerate(blocks):
        if block["type"] == "text":
            events.append({"type": "content_block_start", "index": i, "content_block": {"type": "text", "text": ""}})
            events.append({"type": "content_block_delta", "index": i, "delta": {"type": "text_delta", "text": block["text"]}})
        else:  # tool_use
            events.append({"type": "content_block_start", "index": i,
                           "content_block": {"type": "tool_use", "id": block["id"], "name": block["name"], "input": {}}})
            events.append({"type": "content_block_delta", "index": i,
                           "delta": {"type": "input_json_delta", "partial_json": json.dumps(block["input"])}})
        events.append({"type": "content_block_stop", "index": i})
    events.append({"type": "message_delta", "delta": {"stop_reason": stop_reason, "stop_sequence": None},
                   "usage": {"output_tokens": 5}})
    events.append({"type": "message_stop"})
    return events


@pytest.fixture
def agent_and_requests(tmp_path):
    requests: list[dict] = []
    responses = [
        message_events([
            {"type": "text", "text": "Let me compute that."},
            {"type": "tool_use", "id": "toolu_1", "name": "calculator", "input": {"expression": "6*7"}},
        ], "tool_use"),
        message_events([{"type": "text", "text": "The answer is 42."}], "end_turn"),
    ]

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(json.loads(request.content))
        body = sse(responses[len(requests) - 1])
        return httpx2.Response(200, content=body, headers={"content-type": "text/event-stream"})

    client = AsyncAnthropic(api_key="test", http_client=DefaultAsyncHttpxClient(transport=httpx2.MockTransport(handler)))
    settings = Settings(data_dir=tmp_path, workspace_dir=tmp_path, enable_web_tools=False)
    ws = tmp_path / "ws"
    ws.mkdir()
    agent = Agent(client, settings, build_registry(), ToolContext(store=Store(tmp_path / "a.db"), workspace=ws))
    return agent, requests


def test_agent_runs_tool_and_finishes(agent_and_requests):
    agent, requests = agent_and_requests
    messages = [{"role": "user", "content": "What is 6*7?"}]

    async def collect():
        return [e async for e in agent.run(messages)]

    events = asyncio.run(collect())
    names = [e["event"] for e in events]

    assert "tool_start" in names and "tool_result" in names
    result = next(e for e in events if e["event"] == "tool_result")
    assert result["data"]["output"] == "42" and not result["data"]["is_error"]
    assert events[-1]["event"] == "done" and events[-1]["data"]["stop_reason"] == "end_turn"
    text = "".join(e["data"]["delta"] for e in events if e["event"] == "text")
    assert text == "Let me compute that.The answer is 42."

    # History: user, assistant(tool_use), user(tool_result), assistant(final)
    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]
    assert messages[2]["content"][0] == {"type": "tool_result", "tool_use_id": "toolu_1", "content": "42", "is_error": False}

    # The second request carried the tool result, and the request shape is what we expect.
    assert len(requests) == 2
    req = requests[1]
    assert req["model"] == "claude-opus-5"
    assert req["thinking"] == {"type": "adaptive", "display": "summarized"}
    assert req["fallbacks"] == "default"
    assert req["messages"][-1]["content"][0]["tool_use_id"] == "toolu_1"

    transcript = to_transcript(messages)
    assert [m["role"] for m in transcript] == ["user", "assistant"]
    tool_part = next(p for p in transcript[1]["parts"] if p["type"] == "tool")
    assert tool_part["output"] == "42"


def test_close_dangling_tool_calls():
    messages = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "calculator", "input": {}}]},
    ]
    close_dangling_tool_calls(messages)
    assert messages[-1]["content"][0]["tool_use_id"] == "t1"
    assert messages[-1]["content"][0]["is_error"] is True
