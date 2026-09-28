"""Sandboxed file tools. Every path is resolved inside the workspace directory."""

from pathlib import Path

from pydantic import Field

from app.tools.base import Tool, ToolContext, ToolError, ToolInput

MAX_READ_BYTES = 200_000


def _resolve(ctx: ToolContext, path: str) -> Path:
    # Model-supplied paths are untrusted: reject anything that escapes the workspace
    # (`..`, absolute paths, symlinks pointing outside).
    root = ctx.workspace.resolve()
    target = (root / path).resolve()
    if not target.is_relative_to(root):
        raise ToolError(f"Path '{path}' is outside the workspace")
    return target


class ListFilesInput(ToolInput):
    path: str = Field(default=".", description="Directory relative to the workspace root")


def list_files(args: ListFilesInput, ctx: ToolContext) -> str:
    target = _resolve(ctx, args.path)
    if not target.is_dir():
        raise ToolError(f"Not a directory: {args.path}")
    root = ctx.workspace.resolve()
    entries = []
    for p in sorted(target.iterdir()):
        rel = p.relative_to(root)
        entries.append(f"{rel}/" if p.is_dir() else f"{rel} ({p.stat().st_size} bytes)")
    return "\n".join(entries) or "(empty)"


class ReadFileInput(ToolInput):
    path: str = Field(description="File path relative to the workspace root")


def read_file(args: ReadFileInput, ctx: ToolContext) -> str:
    target = _resolve(ctx, args.path)
    if not target.is_file():
        raise ToolError(f"File not found: {args.path}")
    if target.stat().st_size > MAX_READ_BYTES:
        raise ToolError(f"File is larger than {MAX_READ_BYTES} bytes")
    return target.read_text(encoding="utf-8", errors="replace")


class WriteFileInput(ToolInput):
    path: str = Field(description="File path relative to the workspace root")
    content: str = Field(description="Full text content to write (overwrites the file)")


def write_file(args: WriteFileInput, ctx: ToolContext) -> str:
    target = _resolve(ctx, args.path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(args.content, encoding="utf-8")
    return f"Wrote {len(args.content)} characters to {args.path}"


TOOLS = [
    Tool(
        name="list_files",
        label="List files",
        description="List files in the agent's workspace directory.",
        input_model=ListFilesInput,
        handler=list_files,
    ),
    Tool(
        name="read_file",
        label="Read file",
        description="Read a UTF-8 text file from the agent's workspace.",
        input_model=ReadFileInput,
        handler=read_file,
    ),
    Tool(
        name="write_file",
        label="Write file",
        description="Create or overwrite a text file in the agent's workspace. Use this for "
        "deliverables the user asks you to produce (reports, code, drafts).",
        input_model=WriteFileInput,
        handler=write_file,
    ),
]
