"""Convert stored API message history into the display shape the frontend renders.

Consecutive assistant turns (separated only by tool results) are merged into one display
message whose `parts` are thinking, text, and tool entries - the same shape the UI builds
live from the SSE stream.
"""

from typing import Any


def to_transcript(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    tools_by_id: dict[str, dict[str, Any]] = {}

    def assistant_msg() -> dict[str, Any]:
        if not out or out[-1]["role"] != "assistant":
            out.append({"role": "assistant", "parts": []})
        return out[-1]

    for msg in messages:
        content = msg["content"]
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]

        if msg["role"] == "user":
            texts = [b["text"] for b in content if b.get("type") == "text"]
            for b in content:
                if b.get("type") == "tool_result" and b["tool_use_id"] in tools_by_id:
                    result = b.get("content")
                    if isinstance(result, list):
                        result = "\n".join(c.get("text", "") for c in result)
                    tools_by_id[b["tool_use_id"]].update(output=result, is_error=b.get("is_error", False))
            if texts:
                out.append({"role": "user", "text": "\n".join(texts)})
            continue

        parts = assistant_msg()["parts"]
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
                tool = {
                    "type": "tool",
                    "id": b["id"],
                    "name": b["name"],
                    "input": b.get("input"),
                    "server": kind == "server_tool_use",
                    "output": None,
                    "is_error": False,
                }
                tools_by_id[b["id"]] = tool
                parts.append(tool)
            elif kind and kind.endswith("_tool_result") and b.get("tool_use_id") in tools_by_id:
                tools_by_id[b["tool_use_id"]]["output"] = _server_result_text(b)
    return out


def _server_result_text(block: dict[str, Any]) -> str:
    content = block.get("content")
    if isinstance(content, list):
        return "\n".join(f"- {r.get('title')} — {r.get('url')}" for r in content if r.get("type") == "web_search_result")
    if isinstance(content, dict):
        if content.get("url"):
            return f"Fetched {content['url']}"
        if content.get("error_code"):
            return f"Error: {content['error_code']}"
    return block.get("type", "")
