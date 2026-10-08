"""Agent profiles: a name, extra instructions, and the subset of tools a chat may use.

Each user gets copies of these presets the first time they list agents; from then on the
copies are ordinary rows they can edit or delete (see Store.seed_agents).
"""

from typing import Any

ALL_TOOLS = [
    "calculator", "delete_note", "get_current_time", "list_documents", "list_files", "read_file",
    "save_note", "search_knowledge_base", "search_notes", "web_fetch", "web_search", "write_file",
]

PRESETS: list[dict[str, Any]] = [
    {
        "name": "Synora Prime",
        "role": "Master Orchestrator",
        "icon": "sparkles",
        "description": "General agent that plans multi-step work and chains every available tool.",
        "instructions": "",
        "tools": ALL_TOOLS,
    },
    {
        "name": "Deep Research Agent",
        "role": "Live Web & Fact Specialist",
        "icon": "globe",
        "description": "Searches the live web, reads sources, and writes cited summaries.",
        "instructions": (
            "Research questions on the live web. Search from several angles, open the most relevant "
            "pages, and cross-check important claims across sources. Cite every source by URL, note "
            "publication dates when recency matters, and say when sources disagree."
        ),
        "tools": ["calculator", "get_current_time", "save_note", "search_notes", "web_fetch", "web_search"],
    },
    {
        "name": "Software Engineer Agent",
        "role": "Code & Architecture Specialist",
        "icon": "code",
        "description": "Writes, reviews, and refactors code in your private workspace.",
        "instructions": (
            "Act as a senior software engineer. Write clean, working, idiomatic code with brief "
            "explanations. Read existing workspace files before changing them, and save complete "
            "files with write_file when the user wants code kept."
        ),
        "tools": ["get_current_time", "list_files", "read_file", "write_file"],
    },
    {
        "name": "Knowledge Base Agent",
        "role": "Document Grounding Specialist",
        "icon": "file-search",
        "description": "Answers strictly from the documents you uploaded, with file citations.",
        "instructions": (
            "Answer only from the user's uploaded documents. Search the knowledge base before "
            "answering, cite the file names you used, and say plainly when the documents don't "
            "contain the answer instead of guessing."
        ),
        "tools": ["list_documents", "search_knowledge_base"],
    },
    {
        "name": "Quantitative & Math Agent",
        "role": "Arithmetic & Exact Logic Analyst",
        "icon": "calculator",
        "description": "Exact arithmetic, financial math, and date calculations, step by step.",
        "instructions": (
            "Solve quantitative problems exactly. Use the calculator for every non-trivial "
            "arithmetic step, state the formula first, show each step, and give the final answer "
            "with units."
        ),
        "tools": ["calculator", "get_current_time"],
    },
]


def system_prompt(base: str, profile: dict[str, Any] | None) -> str:
    """The base prompt, plus the agent's role and instructions when chatting with one."""
    if not profile:
        return base
    role = f", {profile['role']}" if profile["role"] else ""
    lines = [
        base,
        f"## Your role\nIn this conversation you are {profile['name']}{role}. Only the tools provided "
        "in this request are available to you; ignore any others mentioned above.",
    ]
    if profile["instructions"]:
        lines.append(profile["instructions"])
    return "\n\n".join(lines)
