"""Accounts, login cookies, per-user data isolation, and admin authorization, via the real routes."""

import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import auth
from app.api import router
from app.auth import hash_password, verify_password
from app.config import Settings
from app.store import Store


@pytest.fixture
def app(tmp_path, store):
    app = FastAPI()
    app.include_router(auth.router)
    app.include_router(router)
    app.state.settings = Settings(data_dir=tmp_path, workspace_dir=tmp_path / "workspace")
    app.state.store = store
    app.state.kb = app.state.agent = None  # these tests never reach embedding or the model
    (tmp_path / "workspace").mkdir()
    return app


def signup(app, email: str, name: str = "Someone", password: str = "correct horse") -> TestClient:
    """A client signed in as a new account (each client keeps its own cookie jar)."""
    client = TestClient(app)
    res = client.post("/api/auth/signup", json={"email": email, "name": name, "password": password})
    assert res.status_code == 201, res.text
    return client


def test_password_hashing():
    stored = hash_password("s3cret-pass")
    assert stored.startswith("scrypt$") and "s3cret-pass" not in stored
    assert verify_password("s3cret-pass", stored)
    assert not verify_password("wrong", stored)
    assert not verify_password("s3cret-pass", "garbage")


def test_first_user_is_admin(app):
    ada = signup(app, "Ada@Example.com", "Ada")
    bob = signup(app, "bob@example.com", "Bob")
    assert ada.get("/api/auth/me").json() | {"id": None, "created_at": None} == {
        "id": None, "email": "ada@example.com", "name": "Ada", "role": "admin", "disabled": False, "created_at": None,
    }
    assert bob.get("/api/auth/me").json()["role"] == "user"


def test_signup_and_login_errors(app):
    signup(app, "ada@example.com")
    client = TestClient(app)
    dup = client.post("/api/auth/signup", json={"email": "ADA@example.com", "name": "X", "password": "12345678"})
    assert dup.status_code == 409
    short = client.post("/api/auth/signup", json={"email": "new@example.com", "name": "X", "password": "short"})
    assert short.status_code == 422
    bad = client.post("/api/auth/signup", json={"email": "not-an-email", "name": "X", "password": "12345678"})
    assert bad.status_code == 422

    signup(app, "bob@example.com")
    assert client.post("/api/auth/login", json={"email": "bob@example.com", "password": "nope"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "who@example.com", "password": "nope"}).status_code == 401
    ok = client.post("/api/auth/login", json={"email": "bob@example.com", "password": "correct horse"})
    assert ok.status_code == 200 and "password_hash" not in ok.json()
    assert client.get("/api/auth/me").status_code == 200


def test_admins_cannot_use_the_regular_login(app):
    signup(app, "ada@example.com")  # first account: admin
    client = TestClient(app)
    res = client.post("/api/auth/login", json={"email": "ada@example.com", "password": "correct horse"})
    assert res.status_code == 403 and "/admin" in res.json()["detail"]
    assert auth.COOKIE not in client.cookies


def test_signup_can_be_closed(app):
    app.state.settings.allow_signup = False
    signup(app, "ada@example.com")  # the first (admin) account is always allowed
    res = TestClient(app).post("/api/auth/signup", json={"email": "b@example.com", "name": "B", "password": "12345678"})
    assert res.status_code == 403


def test_routes_require_login(app):
    client = TestClient(app)
    assert client.get("/api/health").status_code == 200
    for path in ("/api/auth/me", "/api/sessions", "/api/notes", "/api/tools", "/api/admin/users"):
        assert client.get(path).status_code == 401, path
    assert client.post("/api/chat", json={"message": "hi"}).status_code == 401


def test_logout_revokes_the_token(app):
    ada = signup(app, "ada@example.com")
    token = ada.cookies.get(auth.COOKIE)
    assert ada.post("/api/auth/logout").status_code == 204
    replay = TestClient(app, cookies={auth.COOKIE: token})
    assert replay.get("/api/auth/me").status_code == 401


def test_users_only_see_their_own_data(app, store):
    ada = signup(app, "ada@example.com")
    bob = signup(app, "bob@example.com")
    ada_id = ada.get("/api/auth/me").json()["id"]

    session = ada.post("/api/sessions").json()
    note = store.add_note(ada_id, "Secret", "Ada's note", [])

    assert [s["id"] for s in ada.get("/api/sessions").json()] == [session["id"]]
    assert bob.get("/api/sessions").json() == []
    assert bob.get(f"/api/sessions/{session['id']}").status_code == 404
    assert bob.patch(f"/api/sessions/{session['id']}", json={"title": "mine"}).status_code == 404
    assert bob.delete(f"/api/sessions/{session['id']}").status_code == 404
    assert bob.post("/api/chat", json={"message": "hi", "session_id": session["id"]}).status_code == 404

    assert bob.get("/api/notes").json() == []
    assert bob.delete(f"/api/notes/{note['id']}").status_code == 404
    assert [n["id"] for n in ada.get("/api/notes").json()] == [note["id"]]


def test_admin_can_manage_users(app):
    ada = signup(app, "ada@example.com")
    bob = signup(app, "bob@example.com")
    ada_id = ada.get("/api/auth/me").json()["id"]
    bob_id = bob.get("/api/auth/me").json()["id"]

    assert bob.get("/api/admin/users").status_code == 403
    assert bob.patch(f"/api/admin/users/{ada_id}", json={"disabled": True}).status_code == 403
    assert [u["email"] for u in ada.get("/api/admin/users").json()] == ["ada@example.com", "bob@example.com"]
    assert ada.patch(f"/api/admin/users/{ada_id}", json={"role": "user"}).status_code == 400
    assert ada.patch("/api/admin/users/missing", json={"disabled": True}).status_code == 404

    assert ada.patch(f"/api/admin/users/{bob_id}", json={"disabled": True}).json()["disabled"] is True
    assert bob.get("/api/auth/me").status_code == 401  # existing login is revoked
    relogin = TestClient(app).post("/api/auth/login", json={"email": "bob@example.com", "password": "correct horse"})
    assert relogin.status_code == 403

    ada.patch(f"/api/admin/users/{bob_id}", json={"disabled": False, "role": "admin"})
    bob = TestClient(app)
    bob.post("/api/auth/admin/login", json={"email": "bob@example.com", "password": "correct horse"})
    assert bob.get("/api/admin/users").status_code == 200


def test_first_user_claims_pre_account_data(tmp_path):
    # A database from before accounts existed: owned tables have no user_id column.
    db = tmp_path / "old.db"
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE sessions (id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at TEXT NOT NULL,
                               updated_at TEXT NOT NULL, messages TEXT NOT NULL DEFAULT '[]');
        CREATE TABLE notes (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, content TEXT NOT NULL,
                            tags TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL);
        INSERT INTO sessions (id, title, created_at, updated_at) VALUES ('s1', 'Old chat', 'x', 'x');
        INSERT INTO notes (title, content, created_at) VALUES ('Old', 'note', 'x');
    """)
    conn.commit()
    conn.close()

    store = Store(db)
    first = store.create_user("ada@example.com", "Ada", "h")
    second = store.create_user("bob@example.com", "Bob", "h")
    assert [s["id"] for s in store.list_sessions(first["id"])] == ["s1"]
    assert len(store.search_notes(first["id"])) == 1
    assert store.list_sessions(second["id"]) == []


def test_first_user_claims_legacy_workspace(app, tmp_path):
    (tmp_path / "workspace" / "report.md").write_text("old")
    ada = signup(app, "ada@example.com")
    ada_id = ada.get("/api/auth/me").json()["id"]
    assert (tmp_path / "workspace" / ada_id / "report.md").read_text() == "old"
    assert not (tmp_path / "workspace" / "report.md").exists()


def test_admin_login_only_admits_admins(app):
    signup(app, "ada@example.com")  # first account: admin
    signup(app, "bob@example.com")
    creds = {"password": "correct horse"}
    bob = TestClient(app)
    res = bob.post("/api/auth/admin/login", json={**creds, "email": "bob@example.com"})
    assert res.status_code == 403 and auth.COOKIE not in bob.cookies  # no session for non-admins
    ada = TestClient(app)
    assert ada.post("/api/auth/admin/login", json={**creds, "email": "ada@example.com"}).json()["role"] == "admin"
    assert ada.get("/api/auth/me").status_code == 200
    assert ada.post("/api/auth/admin/login", json={**creds, "password": "wrong", "email": "ada@example.com"}).status_code == 401
