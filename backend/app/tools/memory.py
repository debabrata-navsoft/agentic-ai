"""Long-term memory: notes persist in SQLite and are shared across all chat sessions."""

import json

from pydantic import Field

from app.tools.base import Tool, ToolContext, ToolError, ToolInput


class SaveNoteInput(ToolInput):
    title: str = Field(description="Short title for the note")
    content: str = Field(description="The information to remember")
    tags: list[str] = Field(default_factory=list, description="Optional tags for later lookup")


def save_note(args: SaveNoteInput, ctx: ToolContext) -> str:
    note = ctx.store.add_note(args.title, args.content, args.tags)
    return f"Saved note #{note['id']}: {note['title']}"


class SearchNotesInput(ToolInput):
    query: str = Field(default="", description="Text to search for; empty returns the most recent notes")
    limit: int = Field(default=10, ge=1, le=50)


def search_notes(args: SearchNotesInput, ctx: ToolContext) -> str:
    notes = ctx.store.search_notes(args.query, args.limit)
    if not notes:
        return "No matching notes."
    return json.dumps(notes, indent=2)


class DeleteNoteInput(ToolInput):
    note_id: int = Field(description="ID of the note to delete")


def delete_note(args: DeleteNoteInput, ctx: ToolContext) -> str:
    if not ctx.store.delete_note(args.note_id):
        raise ToolError(f"Note #{args.note_id} not found")
    return f"Deleted note #{args.note_id}"


TOOLS = [
    Tool(
        name="save_note",
        description="Save a note to long-term memory. Memory persists across conversations, so "
        "use it for user preferences, facts about the user, and results worth reusing.",
        input_model=SaveNoteInput,
        handler=save_note,
    ),
    Tool(
        name="search_notes",
        description="Search long-term memory notes by keyword. Check memory when the user refers "
        "to something from a previous conversation or asks what you remember.",
        input_model=SearchNotesInput,
        handler=search_notes,
    ),
    Tool(
        name="delete_note",
        description="Delete a note from long-term memory by ID.",
        input_model=DeleteNoteInput,
        handler=delete_note,
    ),
]
