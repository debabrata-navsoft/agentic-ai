import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.store import Store  # noqa: E402
from app.tools import ToolContext, build_registry  # noqa: E402

REGISTRY = build_registry()


@pytest.fixture
def ctx(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return ToolContext(store=Store(tmp_path / "test.db"), workspace=workspace)


def run_tool(ctx: ToolContext, name: str, args: dict) -> tuple[str, bool]:
    return asyncio.run(REGISTRY.get(name).run(args, ctx))
