import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.store import Store  # noqa: E402
from app.tools import ToolContext, build_registry  # noqa: E402

REGISTRY = build_registry()


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "test.db")


@pytest.fixture
def user(store):
    return store.create_user("ada@example.com", "Ada", "unused-hash")


@pytest.fixture
def ctx(tmp_path, store, user):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return ToolContext(store=store, workspace=workspace, user_id=user["id"])


def run_tool(ctx: ToolContext, name: str, args: dict) -> tuple[str, bool]:
    return asyncio.run(REGISTRY.get(name).run(args, ctx))
