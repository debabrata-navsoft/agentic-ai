from app.tools import files, knowledge, memory, utility
from app.tools.base import ToolContext, ToolRegistry

# Anthropic-hosted tools: they run on Anthropic's servers, so there's nothing to execute locally.
SERVER_TOOLS = [
    {"type": "web_search_20260209", "name": "web_search", "max_uses": 8},
    {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 8},
]
SERVER_TOOL_CATALOG = [
    {"name": "web_search", "label": "Web search", "description": "Search the web (Anthropic-hosted).", "server": True},
    {"name": "web_fetch", "label": "Fetch page", "description": "Read a web page (Anthropic-hosted).", "server": True},
]


def build_registry() -> ToolRegistry:
    return ToolRegistry([*utility.TOOLS, *memory.TOOLS, *files.TOOLS, *knowledge.TOOLS])


__all__ = ["SERVER_TOOLS", "SERVER_TOOL_CATALOG", "ToolContext", "ToolRegistry", "build_registry"]
