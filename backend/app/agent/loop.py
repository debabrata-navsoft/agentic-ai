"""The agent loop: stream a model turn, run requested tools, feed results back, repeat.

`Agent.run()` is an async generator of UI events (dicts with "event" and "data"), so the
API layer can forward them as Server-Sent Events while the agent works.
"""

import asyncio
import logging
from typing import Any, AsyncIterator

from anthropic import AsyncAnthropic

from app.agent.profiles import system_prompt
from app.agent.prompts import SYSTEM_PROMPT
from app.config import Settings
from app.tools import SERVER_TOOL_CATALOG, SERVER_TOOLS, ToolContext, ToolRegistry
from app.transcript import MAX_RESULT_PREVIEW, is_server_result, summarize_server_result

log = logging.getLogger(__name__)

Event = dict[str, Any]
MAX_JSON_RETRIES = 2


def _event(event: str, /, **data: Any) -> Event:
    return {"event": event, "data": data}


def _dump_block(block: Any) -> dict[str, Any]:
    data = block.to_dict(mode="json", exclude_none=True)
    data.pop("parsed_output", None)  # SDK-side helper field, not part of the API shape
    return data


def _tool_result(tool_use_id: str, content: str, is_error: bool) -> dict[str, Any]:
    return {"type": "tool_result", "tool_use_id": tool_use_id, "content": content, "is_error": is_error}


def _echo_content(blocks: list[Any]) -> list[Any]:
    """Blocks to append to history as the assistant turn.

    After a mid-output server-side fallback, only text and paired server-tool blocks from
    before the last `fallback` marker may be echoed back; everything after it echoes as-is.
    """
    boundary = max((i for i, b in enumerate(blocks) if b.type == "fallback"), default=None)
    if boundary is None:
        return blocks
    before, after = blocks[:boundary], blocks[boundary + 1 :]
    result_ids = {getattr(b, "tool_use_id", None) for b in before if is_server_result(b.type)}
    kept_server_ids = {b.id for b in before if b.type == "server_tool_use" and b.id in result_ids}
    kept = [
        b
        for b in before
        if b.type == "text"
        or (b.type == "server_tool_use" and b.id in kept_server_ids)
        or (is_server_result(b.type) and getattr(b, "tool_use_id", None) in kept_server_ids)
    ]
    return kept + after


def close_dangling_tool_calls(messages: list[dict[str, Any]]) -> None:
    """If a run was interrupted between a tool call and its result, answer the call with
    an error so the stored history stays valid for the next request."""
    if not messages or messages[-1]["role"] != "assistant":
        return
    pending = [b["id"] for b in messages[-1]["content"] if b.get("type") == "tool_use"]
    if pending:
        messages.append(
            {"role": "user", "content": [_tool_result(i, "Interrupted before completion.", True) for i in pending]}
        )


class Agent:
    def __init__(self, client: AsyncAnthropic, settings: Settings, registry: ToolRegistry):
        self.client = client
        self.settings = settings
        self.registry = registry
        web = settings.enable_web_tools
        self.tools = registry.definitions() + (SERVER_TOOLS if web else [])
        self.catalog = registry.catalog() + (SERVER_TOOL_CATALOG if web else [])

    def _request(
        self, messages: list[dict[str, Any]], system: str, tools: list[dict[str, Any]]
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.settings.model,
            "max_tokens": self.settings.max_tokens,
            "system": system,
            "messages": messages,
            "thinking": {"type": "adaptive", "display": "summarized"},
            "output_config": {"effort": self.settings.effort},
            "cache_control": {"type": "ephemeral"},
        }
        if self.settings.enable_fallbacks:
            kwargs["betas"] = ["server-side-fallback-2026-07-01"]
            kwargs["fallbacks"] = "default"
        if tools:
            kwargs["tools"] = tools
        return kwargs

    async def run(
        self, messages: list[dict[str, Any]], ctx: ToolContext, profile: dict[str, Any] | None = None
    ) -> AsyncIterator[Event]:
        """Run until the model stops calling tools. Appends every turn to `messages` in place.

        `ctx` scopes client tools to the user who owns the conversation. `profile` (an agent
        from the store) adds its instructions and limits the run to its tools.
        """
        system = system_prompt(SYSTEM_PROMPT, profile)
        # Filtering keeps the registry's sorted order, so each agent's prefix caches stably.
        tools = [t for t in self.tools if t["name"] in profile["tools"]] if profile else self.tools
        allowed = {t["name"] for t in tools}
        usage = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0}
        json_retries = 0
        step = 0
        stop_reason: str | None = None

        while step < self.settings.max_iterations:
            yield _event("step_start", step=step)
            try:
                async with self.client.beta.messages.stream(**self._request(messages, system, tools)) as stream:
                    async for ev in stream:
                        out = self._translate(ev)
                        if out:
                            yield out
                    response = await stream.get_final_message()
                json_retries = 0
            except ValueError:
                # Tool-input JSON the SDK couldn't parse at all (eager input streaming).
                # There's no tool_use_id to answer, so discard and re-issue the turn.
                json_retries += 1
                yield _event("step_discard", step=step, reason="malformed tool input")
                if json_retries > MAX_JSON_RETRIES:
                    raise
                continue

            for key in usage:
                usage[key] += getattr(response.usage, key, 0) or 0
            stop_reason = response.stop_reason

            if stop_reason == "refusal":
                # Content is empty or partial; don't keep a partial answer in history.
                details = response.stop_details
                yield _event("step_discard", step=step, reason="refusal")
                yield _event(
                    "refusal",
                    category=getattr(details, "category", None),
                    explanation=getattr(details, "explanation", None),
                )
                break

            content = _echo_content(response.content)
            messages.append({"role": "assistant", "content": [_dump_block(b) for b in content]})

            if stop_reason == "pause_turn":
                # A server tool paused a long turn; re-send so the model resumes it.
                step += 1
                continue

            tool_uses = [b for b in content if b.type == "tool_use"]
            if not tool_uses:
                break

            for b in tool_uses:
                yield _event("tool_input", id=b.id, input=b.input)

            if stop_reason == "max_tokens":
                # Tool input was cut off; a truncated input still parses, so don't run it.
                results = [("Tool input was truncated by max_tokens; retry with less input.", True)] * len(tool_uses)
            else:
                results = await asyncio.gather(*(self._run_tool(b, ctx, allowed) for b in tool_uses))

            tool_results = []
            for block, (output, is_error) in zip(tool_uses, results):
                yield _event("tool_result", id=block.id, output=output[:MAX_RESULT_PREVIEW], is_error=is_error)
                tool_results.append(_tool_result(block.id, output, is_error))
            # All results go back in a single user message (keeps parallel tool use working).
            messages.append({"role": "user", "content": tool_results})
            step += 1
        else:
            yield _event("notice", message=f"Stopped after {self.settings.max_iterations} steps.")

        yield _event("done", stop_reason=stop_reason, usage=usage, steps=step + 1)

    async def _run_tool(self, block: Any, ctx: ToolContext, allowed: set[str]) -> tuple[str, bool]:
        tool = self.registry.get(block.name)
        if tool is None or block.name not in allowed:
            return f"Unknown tool: {block.name}", True
        log.info("tool %s %s", block.name, block.input)
        return await tool.run(block.input, ctx)

    @staticmethod
    def _translate(ev: Any) -> Event | None:
        """Map an SDK stream event to a UI event (or None to skip it)."""
        if ev.type == "text":
            return _event("text", delta=ev.text)
        if ev.type == "thinking":
            return _event("thinking", delta=ev.thinking)
        if ev.type == "content_block_start":
            block = ev.content_block
            if block.type in ("tool_use", "server_tool_use"):
                return _event("tool_start", id=block.id, name=block.name, server=block.type == "server_tool_use")
            if block.type == "fallback":
                return _event("notice", message=f"Continuing on fallback model {block.to.model}.")
        if ev.type == "content_block_stop":
            block = ev.content_block
            if block.type == "server_tool_use":
                return _event("tool_input", id=block.id, input=block.input)
            if is_server_result(block.type):
                output, is_error = summarize_server_result(_dump_block(block))
                return _event("tool_result", id=block.tool_use_id, output=output, is_error=is_error)
        return None
