import asyncio

import pytest

from app.store import Store
from app.tools import ToolContext, build_registry


@pytest.fixture
def ctx(tmp_path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    return ToolContext(store=Store(tmp_path / "t.db"), workspace=ws)


def run(ctx, name, args):
    return asyncio.run(build_registry().get(name).run(args, ctx))


def test_calculator(ctx):
    assert run(ctx, "calculator", {"expression": "(2 + 3) * sqrt(16)"}) == ("20.0", False)
    assert run(ctx, "calculator", {"expression": "1/0"}) == ("Division by zero", True)


def test_calculator_rejects_code(ctx):
    out, is_error = run(ctx, "calculator", {"expression": "__import__('os').system('ls')"})
    assert is_error


def test_invalid_input_is_error(ctx):
    out, is_error = run(ctx, "calculator", {"expr": "1+1"})
    assert is_error and "Invalid input" in out


def test_time(ctx):
    out, is_error = run(ctx, "get_current_time", {"timezone": "Asia/Kolkata"})
    assert not is_error and "+05:30" in out
    assert run(ctx, "get_current_time", {"timezone": "Mars/Base"})[1]


def test_notes_roundtrip(ctx):
    run(ctx, "save_note", {"title": "Language", "content": "User prefers Python", "tags": ["pref"]})
    out, _ = run(ctx, "search_notes", {"query": "python"})
    assert "User prefers Python" in out
    assert run(ctx, "delete_note", {"note_id": 1}) == ("Deleted note #1", False)
    assert run(ctx, "search_notes", {"query": "python"})[0] == "No matching notes."


def test_files_confined_to_workspace(ctx):
    assert not run(ctx, "write_file", {"path": "docs/a.txt", "content": "hi"})[1]
    assert run(ctx, "read_file", {"path": "docs/a.txt"}) == ("hi", False)
    assert "docs/" in run(ctx, "list_files", {})[0]
    out, is_error = run(ctx, "read_file", {"path": "../../etc/passwd"})
    assert is_error and "outside the workspace" in out
    assert run(ctx, "write_file", {"path": "/tmp/evil", "content": "x"})[1]


def test_definitions_are_sorted_and_valid():
    defs = build_registry().definitions()
    names = [d["name"] for d in defs]
    assert names == sorted(names)
    for d in defs:
        assert d["input_schema"]["type"] == "object"
        assert d["input_schema"]["additionalProperties"] is False
