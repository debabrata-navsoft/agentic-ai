"""The OpenAI agent loop, driven through the real OpenAI SDK against canned SSE."""

import asyncio
import json

import httpx2
import pytest
from openai import AsyncOpenAI, DefaultAsyncHttpxClient

from app.agent.openai_loop import OpenAIAgent, close_dangling_openai
from app.attachments import to_openai_content
from app.config import Settings
from app.tools import build_registry
from app.transcript import openai_transcript


def chunk(delta: dict | None = None, finish: str | None = None, usage: dict | None = None) -> dict:
    choices = [] if delta is None else [{"index": 0, "delta": delta, "finish_reason": finish}]
    return {"id": "c1", "object": "chat.completion.chunk", "created": 0, "model": "gpt-5", "choices": choices,
            "usage": usage}


def sse(chunks: list[dict]) -> bytes:
    return b"".join(f"data: {json.dumps(c)}\n\n".encode() for c in chunks) + b"data: [DONE]\n\n"


USAGE = {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110,
         "prompt_tokens_details": {"cached_tokens": 40}}


@pytest.fixture
def agent_and_requests(tmp_path, ctx):
    requests: list[dict] = []
    responses = [
        [
            chunk({"role": "assistant", "content": "Let me compute that."}),
            chunk({"tool_calls": [{"index": 0, "id": "call_1", "type": "function",
                                   "function": {"name": "calculator", "arguments": '{"expr'}}]}),
            chunk({"tool_calls": [{"index": 0, "function": {"arguments": 'ession": "6*7"}'}}]}, "tool_calls"),
            chunk(usage=USAGE),
        ],
        [chunk({"content": "The answer is 42."}, "stop"), chunk(usage=USAGE)],
    ]

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(json.loads(request.content))
        return httpx2.Response(200, content=sse(responses[len(requests) - 1]),
                               headers={"content-type": "text/event-stream"})

    client = AsyncOpenAI(api_key="test", http_client=DefaultAsyncHttpxClient(transport=httpx2.MockTransport(handler)))
    agent = OpenAIAgent(client, Settings(data_dir=tmp_path, workspace_dir=tmp_path), build_registry())
    return agent, ctx, requests


def collect(agent, messages, ctx, profile=None):
    async def run():
        return [e async for e in agent.run(messages, ctx, profile)]

    return asyncio.run(run())


def test_openai_agent_runs_tool_and_finishes(agent_and_requests):
    agent, ctx, requests = agent_and_requests
    messages = [{"role": "user", "content": "What is 6*7?"}]
    events = collect(agent, messages, ctx)

    names = [e["event"] for e in events]
    assert names.count("step_start") == 2 and "tool_start" in names
    result = next(e for e in events if e["event"] == "tool_result")["data"]
    assert result == {"id": "call_1", "output": "42", "is_error": False}
    assert "".join(e["data"]["delta"] for e in events if e["event"] == "text") == "Let me compute that.The answer is 42."
    assert events[-1]["data"]["usage"] == {"input_tokens": 120, "output_tokens": 20, "cache_read_input_tokens": 80}

    assert [m["role"] for m in messages] == ["user", "assistant", "tool", "assistant"]
    assert messages[1]["tool_calls"][0]["function"] == {"name": "calculator", "arguments": '{"expression": "6*7"}'}
    assert messages[2] == {"role": "tool", "tool_call_id": "call_1", "content": "42"}

    req = requests[1]
    assert req["model"] == "gpt-5" and req["stream"] is True
    assert req["messages"][0]["role"] == "system"  # the system prompt is never stored in history
    assert {t["function"]["name"] for t in req["tools"]} >= {"calculator", "read_file"}

    transcript = openai_transcript(messages)
    assert [m["role"] for m in transcript] == ["user", "assistant"]
    tool = next(p for p in transcript[1]["parts"] if p["type"] == "tool")
    assert tool["input"] == {"expression": "6*7"} and tool["output"] == "42"


def test_openai_profile_limits_tools(agent_and_requests):
    agent, ctx, requests = agent_and_requests
    profile = {"name": "Clock", "role": "", "instructions": "Be brief.", "tools": ["get_current_time"]}
    events = collect(agent, [{"role": "user", "content": "6*7?"}], ctx, profile)

    assert [t["function"]["name"] for t in requests[0]["tools"]] == ["get_current_time"]
    assert requests[0]["messages"][0]["content"].endswith("Be brief.")
    result = next(e for e in events if e["event"] == "tool_result")["data"]
    assert result["is_error"] and "Unknown tool" in result["output"]


def test_close_dangling_and_attachments():
    messages = [{"role": "assistant", "content": None, "tool_calls": [{"id": "c9", "type": "function",
                                                                     "function": {"name": "x", "arguments": "{}"}}]}]
    close_dangling_openai(messages)
    assert messages[-1] == {"role": "tool", "tool_call_id": "c9", "content": "Error: Interrupted before completion."}

    blocks = [
        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "QUJD"}},
        {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": "UERG"}, "title": "a.pdf"},
        {"type": "document", "source": {"type": "text", "media_type": "text/plain", "data": "hello"}, "title": "n.md"},
        {"type": "text", "text": "summarize"},
    ]
    parts = to_openai_content(blocks)
    assert parts[0] == {"type": "image_url", "image_url": {"url": "data:image/png;base64,QUJD"}}
    assert parts[1]["file"] == {"filename": "a.pdf", "file_data": "data:application/pdf;base64,UERG"}
    [user] = openai_transcript([{"role": "user", "content": parts}])
    assert user["text"] == "summarize"
    assert [a["name"] for a in user["attachments"]] == ["image", "a.pdf", "n.md"]
