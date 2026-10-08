"""The agent loop on OpenAI's Chat Completions API, for chats whose provider is OpenAI.

It mirrors `Agent.run` (loop.py): the same UI events, the same client tools and system prompt.
History is stored in OpenAI's message format, so a session stays on the provider it started
with. Anthropic-hosted tools (web search / fetch) and reasoning summaries aren't available here.
"""

import asyncio
import json
import logging
from typing import Any, AsyncIterator

from openai import AsyncOpenAI

from app.agent.profiles import system_prompt
from app.agent.prompts import SYSTEM_PROMPT
from app.attachments import to_openai_content
from app.config import Settings
from app.tools import ToolContext, ToolRegistry
from app.transcript import MAX_RESULT_PREVIEW

log = logging.getLogger(__name__)

Event = dict[str, Any]


def _event(event: str, /, **data: Any) -> Event:
    return {"event": event, "data": data}


def _tool_message(call_id: str, output: str, is_error: bool) -> dict[str, Any]:
    # Tool messages have no error flag, so the prefix tells the model (and the transcript).
    return {"role": "tool", "tool_call_id": call_id, "content": f"Error: {output}" if is_error else output}


def close_dangling_openai(messages: list[dict[str, Any]]) -> None:
    """`close_dangling_tool_calls` for OpenAI history: answer calls left without a result."""
    if messages and messages[-1]["role"] == "assistant":
        for call in messages[-1].get("tool_calls") or []:
            messages.append(_tool_message(call["id"], "Interrupted before completion.", True))


class OpenAIAgent:
    # Hooks the chat route calls for whichever provider a session uses.
    close_dangling = staticmethod(close_dangling_openai)
    user_content = staticmethod(to_openai_content)

    def __init__(self, client: AsyncOpenAI, settings: Settings, registry: ToolRegistry):
        self.client = client
        self.settings = settings
        self.registry = registry
        self.tools = [
            {"type": "function", "function": {"name": d["name"], "description": d["description"], "parameters": d["input_schema"]}}
            for d in registry.definitions()
        ]

    async def run(
        self, messages: list[dict[str, Any]], ctx: ToolContext, profile: dict[str, Any] | None = None
    ) -> AsyncIterator[Event]:
        system = {"role": "system", "content": system_prompt(SYSTEM_PROMPT, profile)}
        tools = [t for t in self.tools if not profile or t["function"]["name"] in profile["tools"]]
        allowed = {t["function"]["name"] for t in tools}
        usage = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0}
        step = 0
        finish: str | None = None

        while step < self.settings.max_iterations:
            yield _event("step_start", step=step)
            request: dict[str, Any] = {
                "model": self.settings.openai_model,
                "messages": [system, *messages],
                "stream": True,
                "stream_options": {"include_usage": True},
            }
            if tools:
                request["tools"] = tools

            text = ""
            calls: dict[int, dict[str, str]] = {}  # by stream index
            async with await self.client.chat.completions.create(**request) as stream:
                async for chunk in stream:
                    if chunk.usage:
                        cached = getattr(chunk.usage.prompt_tokens_details, "cached_tokens", 0) or 0
                        usage["input_tokens"] += chunk.usage.prompt_tokens - cached
                        usage["cache_read_input_tokens"] += cached
                        usage["output_tokens"] += chunk.usage.completion_tokens
                    if not chunk.choices:
                        continue
                    choice = chunk.choices[0]
                    finish = choice.finish_reason or finish
                    if piece := choice.delta.content or choice.delta.refusal:
                        text += piece
                        yield _event("text", delta=piece)
                    for tc in choice.delta.tool_calls or []:
                        if tc.id:  # a call's first chunk carries its id and name; the rest add arguments
                            calls[tc.index] = {"id": tc.id, "name": tc.function.name, "arguments": ""}
                            yield _event("tool_start", id=tc.id, name=tc.function.name, server=False)
                        if tc.function and tc.function.arguments:
                            calls[tc.index]["arguments"] += tc.function.arguments

            ordered = [calls[i] for i in sorted(calls)]
            assistant: dict[str, Any] = {"role": "assistant", "content": text or None}
            if ordered:
                assistant["tool_calls"] = [
                    {"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": c["arguments"]}}
                    for c in ordered
                ]
            messages.append(assistant)
            if not ordered:
                break

            inputs = [self._parse(c, truncated=finish == "length") for c in ordered]
            for c, (args, _) in zip(ordered, inputs):
                yield _event("tool_input", id=c["id"], input=args)
            results = await asyncio.gather(
                *(self._run_tool(c["name"], args, error, ctx, allowed) for c, (args, error) in zip(ordered, inputs))
            )
            for c, (output, is_error) in zip(ordered, results):
                yield _event("tool_result", id=c["id"], output=output[:MAX_RESULT_PREVIEW], is_error=is_error)
                messages.append(_tool_message(c["id"], output, is_error))
            step += 1
        else:
            yield _event("notice", message=f"Stopped after {self.settings.max_iterations} steps.")

        yield _event("done", stop_reason=finish, usage=usage, steps=step + 1)

    @staticmethod
    def _parse(call: dict[str, str], truncated: bool) -> tuple[Any, str | None]:
        """(arguments, error). A cut-off call can still parse, so `truncated` calls never run."""
        if truncated:
            return None, "Tool input was truncated by the output limit; retry with less input."
        try:
            return json.loads(call["arguments"] or "{}"), None
        except ValueError:
            return call["arguments"], "Tool input was not valid JSON."

    async def _run_tool(
        self, name: str, args: Any, error: str | None, ctx: ToolContext, allowed: set[str]
    ) -> tuple[str, bool]:
        if error:
            return error, True
        tool = self.registry.get(name)
        if tool is None or name not in allowed:
            return f"Unknown tool: {name}", True
        log.info("tool %s %s", name, args)
        return await tool.run(args, ctx)
