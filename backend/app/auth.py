"""Accounts: password hashing, the login cookie, and the current-user / admin dependencies.

A login is an opaque random token in an httpOnly cookie; only its hash is stored (see Store),
so signing out or disabling a user takes effect immediately.
"""

import asyncio
import hashlib
import hmac
import secrets
import sqlite3
from datetime import timedelta
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

COOKIE = "synora_session"
SCRYPT = {"n": 2**14, "r": 8, "p": 1}

router = APIRouter(prefix="/api")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **SCRYPT)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt, digest = stored.split("$")
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), **SCRYPT)
    except ValueError:
        return False
    return hmac.compare_digest(actual.hex(), digest)


# Checked against when the email is unknown, so a failed login takes the same time either way.
_DUMMY_HASH = hash_password(secrets.token_hex(16))


async def current_user(request: Request) -> dict[str, Any]:
    token = request.cookies.get(COOKIE)
    user = request.app.state.store.get_user_by_token(token) if token else None
    if user is None:
        raise HTTPException(401, "Not signed in")
    return user


CurrentUser = Annotated[dict[str, Any], Depends(current_user)]


async def admin_user(user: CurrentUser) -> dict[str, Any]:
    if user["role"] != "admin":
        raise HTTPException(403, "Admins only")
    return user


AdminUser = Annotated[dict[str, Any], Depends(admin_user)]


def claim_legacy_workspace(root: Path, user_id: str) -> None:
    """Move files written before accounts existed into the first user's workspace."""
    target = root / user_id
    target.mkdir(parents=True, exist_ok=True)
    for entry in root.iterdir():
        if entry != target:
            entry.rename(target / entry.name)


# ---- request models ------------------------------------------------------


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class SignupRequest(Credentials):
    name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=256)


class UserUpdate(BaseModel):
    role: Literal["user", "admin"] | None = None
    disabled: bool | None = None


# ---- routes --------------------------------------------------------------


def _start_login(request: Request, response: Response, user: dict[str, Any]) -> dict[str, Any]:
    settings = request.app.state.settings
    ttl = timedelta(days=settings.login_days)
    token = request.app.state.store.create_token(user["id"], ttl)
    response.set_cookie(
        COOKIE, token, max_age=int(ttl.total_seconds()), path="/api",
        httponly=True, samesite="lax", secure=settings.cookie_secure,
    )
    return user


@router.post("/auth/signup", status_code=201)
async def signup(body: SignupRequest, request: Request, response: Response):
    store, settings = request.app.state.store, request.app.state.settings
    if not settings.allow_signup and store.list_users():
        raise HTTPException(403, "Sign-up is closed. Ask an admin for an account.")
    # scrypt is deliberately slow; keep it off the event loop.
    password_hash = await asyncio.to_thread(hash_password, body.password)
    try:
        user = store.create_user(body.email, body.name.strip(), password_hash)
    except sqlite3.IntegrityError:
        raise HTTPException(409, "An account with this email already exists")
    if user["role"] == "admin":  # only the very first account is created as admin
        claim_legacy_workspace(settings.workspace_dir, user["id"])
    return _start_login(request, response, user)


async def _sign_in(request: Request, response: Response, body: Credentials, *, admin: bool) -> dict[str, Any]:
    """Admins sign in only on the admin page and everyone else only on the regular one."""
    creds = request.app.state.store.get_user_credentials(body.email)
    ok = await asyncio.to_thread(verify_password, body.password, creds["password_hash"] if creds else _DUMMY_HASH)
    if creds is None or not ok:
        raise HTTPException(401, "Incorrect email or password")
    if creds["disabled"]:
        raise HTTPException(403, "This account has been disabled")
    if (creds["role"] == "admin") != admin:
        raise HTTPException(403, "This account is not an admin. Use the regular sign-in page." if admin
                            else "Admin accounts sign in on the admin page (/admin).")
    creds.pop("password_hash")
    return _start_login(request, response, creds)


@router.post("/auth/login")
async def login(body: Credentials, request: Request, response: Response):
    return await _sign_in(request, response, body, admin=False)


@router.post("/auth/admin/login")
async def admin_login(body: Credentials, request: Request, response: Response):
    return await _sign_in(request, response, body, admin=True)


@router.post("/auth/logout", status_code=204)
async def logout(request: Request, response: Response):
    if token := request.cookies.get(COOKIE):
        request.app.state.store.delete_token(token)
    response.delete_cookie(COOKIE, path="/api")


@router.get("/auth/me")
async def me(user: CurrentUser):
    return user


@router.get("/admin/users")
async def list_users(request: Request, _: AdminUser):
    return request.app.state.store.list_users()


@router.patch("/admin/users/{user_id}")
async def update_user(user_id: str, body: UserUpdate, request: Request, admin: AdminUser):
    if user_id == admin["id"]:
        raise HTTPException(400, "You can't change your own role or status")
    user = request.app.state.store.update_user(user_id, role=body.role, disabled=body.disabled)
    if user is None:
        raise HTTPException(404, "User not found")
    return user
