"""Minimal tool framework: a Pydantic model describes (and validates) each tool's input."""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from pydantic import BaseModel, ConfigDict, ValidationError

from app.store import Store

if TYPE_CHECKING:
    from app.rag import KnowledgeBase


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


@dataclass
class ToolContext:
    store: Store
    workspace: Path
    kb: "KnowledgeBase | None" = None


class ToolError(Exception):
    """Raise from a handler to return an `is_error` tool_result with this message."""


@dataclass
class Tool:
    name: str
    label: str  # shown in the UI
    description: str
    input_model: type[ToolInput]
    handler: Callable[[Any, ToolContext], str]

    def definition(self) -> dict[str, Any]:
        schema = self.input_model.model_json_schema()
        schema.pop("title", None)
        for prop in schema.get("properties", {}).values():
            prop.pop("title", None)
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": schema,
            # Stream tool inputs as they're generated; we validate them ourselves below.
            "eager_input_streaming": True,
        }

    async def run(self, raw_input: Any, ctx: ToolContext) -> tuple[str, bool]:
        """Validate and execute in a worker thread. Returns (content, is_error)."""
        try:
            args = self.input_model.model_validate(raw_input)
        except ValidationError as e:
            return f"Invalid input for {self.name}: {e.errors(include_url=False)}", True
        try:
            return str(await asyncio.to_thread(self.handler, args, ctx)), False
        except ToolError as e:
            return str(e), True
        except Exception as e:  # tool bugs shouldn't kill the agent loop
            return f"{type(e).__name__}: {e}", True


class ToolRegistry:
    def __init__(self, tools: list[Tool]):
        # Sorted, and built once: a byte-stable tool list keeps prompt caching hitting.
        self._tools = {t.name: t for t in sorted(tools, key=lambda t: t.name)}
        self._definitions = [t.definition() for t in self._tools.values()]

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def definitions(self) -> list[dict[str, Any]]:
        return self._definitions

    def catalog(self) -> list[dict[str, Any]]:
        return [{"name": t.name, "label": t.label, "description": t.description, "server": False}
                for t in self._tools.values()]
