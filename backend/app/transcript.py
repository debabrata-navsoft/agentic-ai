"""Convert stored API message history into the display shape the frontend renders.

Consecutive assistant turns (separated only by tool results) are merged into one display
message whose `parts` are thinking, text, and tool entries - the same shape the UI builds
live from the SSE stream. The server-tool helpers here are shared with the agent loop so
live and reloaded sessions render identically.
"""

from typing import Any

MAX_RESULT_PREVIEW = 2000


def is_server_result(kind: str | None) -> bool:
    return bool(kind) and kind.endswith("_tool_result") and kind != "tool_result"


def summarize_server_result(block: dict[str, Any]) -> tuple[str, bool]:
    """(display text, is_error) for a web_search / web_fetch result block."""
    content = block.get("content")
    if isinstance(content, list):  # web search success: list of results
        lines = [f"- {r.get('title')} — {r.get('url')}" for r in content if r.get("type") == "web_search_result"]
        return "\n".join(lines) or "No results", False
    if isinstance(content, dict):
        if content.get("error_code"):
            return f"Error: {content['error_code']}", True
        if content.get("url"):
            return f"Fetched {content['url']}", False
    return block.get("type", ""), False


def to_transcript(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    tools_by_id: dict[str, dict[str, Any]] = {}

    for msg in messages:
        content = msg["content"]
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]

        if msg["role"] == "user":
            for b in content:
                if b.get("type") == "tool_result" and b["tool_use_id"] in tools_by_id:
                    result = b.get("content")
                    if isinstance(result, list):
                        result = "\n".join(c.get("text", "") for c in result)
                    tools_by_id[b["tool_use_id"]].update(
                        output=result[:MAX_RESULT_PREVIEW], is_error=b.get("is_error", False)
                    )
            if texts := [b["text"] for b in content if b.get("type") == "text"]:
                out.append({"role": "user", "text": "\n".join(texts)})
            continue

        if not out or out[-1]["role"] != "assistant":
            out.append({"role": "assistant", "parts": []})
        parts = out[-1]["parts"]
        for b in content:
            kind = b.get("type")
            if kind == "text":
                if parts and parts[-1]["type"] == "text":
                    parts[-1]["text"] += b["text"]
                else:
                    parts.append({"type": "text", "text": b["text"]})
            elif kind == "thinking" and b.get("thinking"):
                parts.append({"type": "thinking", "text": b["thinking"]})
            elif kind in ("tool_use", "server_tool_use"):
                tools_by_id[b["id"]] = tool = {
                    "type": "tool", "id": b["id"], "name": b["name"], "input": b.get("input"),
                    "server": kind == "server_tool_use", "output": None, "is_error": False,
                }
                parts.append(tool)
            elif is_server_result(kind) and b.get("tool_use_id") in tools_by_id:
                output, is_error = summarize_server_result(b)
                tools_by_id[b["tool_use_id"]].update(output=output, is_error=is_error)
    return out
