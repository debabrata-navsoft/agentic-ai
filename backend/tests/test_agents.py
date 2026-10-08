"""Agent profiles: seeding, editing, per-user isolation, and chats bound to an agent."""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI

from app import auth
from app.agent.profiles import ALL_TOOLS, PRESETS
from app.api import router
from app.config import Settings
from tests.test_auth import signup


@pytest.fixture
def app(tmp_path, store):
    app = FastAPI()
    app.include_router(auth.router)
    app.include_router(router)
    app.state.settings = Settings(data_dir=tmp_path, workspace_dir=tmp_path / "workspace")
    app.state.store = store
    app.state.kb = None
    app.state.agent = SimpleNamespace(catalog=[{"name": n} for n in ALL_TOOLS])
    return app


def test_presets_are_seeded_once_per_user(app):
    ada = signup(app, "ada@example.com")
    agents = ada.get("/api/agents").json()
    assert [a["name"] for a in agents] == [p["name"] for p in PRESETS]
    assert ada.get("/api/agents").json() == agents  # not seeded twice
    bob = signup(app, "bob@example.com")
    assert {a["id"] for a in bob.get("/api/agents").json()}.isdisjoint(a["id"] for a in agents)


def test_create_edit_delete(app):
    ada = signup(app, "ada@example.com")
    body = {"name": "Poet", "instructions": "Answer in verse.", "tools": ["calculator", "calculator"]}
    poet = ada.post("/api/agents", json=body).json()
    assert poet["tools"] == ["calculator"] and poet["icon"] == "bot"

    edited = ada.put(f"/api/agents/{poet['id']}", json={**body, "name": "Bard", "tools": []}).json()
    assert edited["name"] == "Bard" and edited["tools"] == []

    assert ada.post("/api/agents", json={**body, "tools": ["rm_rf"]}).status_code == 422
    assert ada.delete(f"/api/agents/{poet['id']}").status_code == 204
    assert ada.delete(f"/api/agents/{poet['id']}").status_code == 404


def test_cannot_touch_another_users_agent_or_delete_the_last(app):
    ada = signup(app, "ada@example.com")
    bob = signup(app, "bob@example.com")
    ada_agent = ada.get("/api/agents").json()[0]
    assert bob.put(f"/api/agents/{ada_agent['id']}", json={"name": "Mine"}).status_code == 404
    assert bob.delete(f"/api/agents/{ada_agent['id']}").status_code == 404
    assert bob.post("/api/chat", json={"message": "hi", "agent_id": ada_agent["id"]}).status_code == 404

    *rest, last = ada.get("/api/agents").json()
    for a in rest:
        assert ada.delete(f"/api/agents/{a['id']}").status_code == 204
    assert ada.delete(f"/api/agents/{last['id']}").status_code == 409


def test_session_remembers_its_agent(app, store):
    ada = signup(app, "ada@example.com")
    user_id = ada.get("/api/auth/me").json()["id"]
    agent = ada.get("/api/agents").json()[1]
    session = store.create_session(user_id, agent_id=agent["id"])
    assert ada.get("/api/sessions").json()[0]["agent_id"] == agent["id"]
    assert ada.get(f"/api/sessions/{session['id']}").json()["agent_id"] == agent["id"]
