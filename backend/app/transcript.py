"""Convert stored API message history into the display shape the frontend renders.

Consecutive assistant turns (separated only by tool results) are merged into one display
message whose `parts` are thinking, text, and tool entries - the same shape the UI builds
live from the SSE stream. The server-tool helpers here are shared with the agent loop so
live and reloaded sessions render identically.
"""

import json
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


def _attachment(block: dict[str, Any]) -> dict[str, Any] | None:
    """Display info for a file the user attached (see app/attachments.py), or None."""
    source = block.get("source") or {}
    if block.get("type") == "image" and source.get("type") == "base64":
        url = f"data:{source['media_type']};base64,{source['data']}"
        return {"name": "image", "media_type": source["media_type"], "url": url}
    if block.get("type") == "document":
        media_type = "application/pdf" if source.get("type") == "base64" else "text/plain"
        return {"name": block.get("title") or "document", "media_type": media_type}
    return None


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
            texts = [b["text"] for b in content if b.get("type") == "text"]
            attachments = [a for b in content if (a := _attachment(b))]
            if texts or attachments:
                entry: dict[str, Any] = {"role": "user", "text": "\n".join(texts)}
                if attachments:
                    entry["attachments"] = attachments
                out.append(entry)
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


def _openai_attachment(part: dict[str, Any]) -> dict[str, Any] | None:
    """Display info for a file in an OpenAI user message (see attachments.to_openai_content)."""
    if part.get("type") == "image_url":
        url = part["image_url"]["url"]
        return {"name": "image", "media_type": url[5 : url.find(";")], "url": url}
    if part.get("type") == "file":
        return {"name": part["file"].get("filename") or "document", "media_type": "application/pdf"}
    text = part.get("text", "")
    if part.get("type") == "text" and text.startswith('<document name="'):
        return {"name": text[16 : text.find('">')], "media_type": "text/plain"}
    return None


def openai_transcript(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """`to_transcript` for sessions stored in OpenAI Chat Completions format."""
    out: list[dict[str, Any]] = []
    tools_by_id: dict[str, dict[str, Any]] = {}

    for msg in messages:
        role, content = msg["role"], msg.get("content")
        if role == "tool":
            if tool := tools_by_id.get(msg["tool_call_id"]):
                is_error = content.startswith("Error: ")
                tool.update(output=content.removeprefix("Error: ")[:MAX_RESULT_PREVIEW], is_error=is_error)
            continue
        if role == "user":
            parts = [{"type": "text", "text": content}] if isinstance(content, str) else content
            attachments = [a for p in parts if (a := _openai_attachment(p))]
            texts = [p["text"] for p in parts if p.get("type") == "text" and not _openai_attachment(p)]
            entry: dict[str, Any] = {"role": "user", "text": "\n".join(texts)}
            if attachments:
                entry["attachments"] = attachments
            out.append(entry)
            continue

        if not out or out[-1]["role"] != "assistant":
            out.append({"role": "assistant", "parts": []})
        parts = out[-1]["parts"]
        if content:
            parts.append({"type": "text", "text": content})
        for call in msg.get("tool_calls") or []:
            try:
                args = json.loads(call["function"]["arguments"] or "{}")
            except ValueError:
                args = call["function"]["arguments"]
            tools_by_id[call["id"]] = tool = {
                "type": "tool", "id": call["id"], "name": call["function"]["name"], "input": args,
                "server": False, "output": None, "is_error": False,
            }
            parts.append(tool)
    return out
