import asyncio
import json
import logging

import anthropic
from fastapi import APIRouter, HTTPException, Request, UploadFile
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sse_starlette.sse import EventSourceResponse

from app.agent.loop import close_dangling_tool_calls
from app.agent.profiles import PRESETS
from app.attachments import MAX_ATTACHMENTS, Attachment, AttachmentError, user_content
from app.auth import CurrentUser
from app.rag import SUPPORTED_EXTENSIONS, UnsupportedFileError
from app.tools import ToolContext
from app.transcript import to_transcript

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

# Sessions with a run in progress; a second concurrent run would interleave history.
_active_sessions: set[str] = set()


class ChatRequest(BaseModel):
    message: str = Field(default="", max_length=100_000)
    attachments: list[Attachment] = Field(default_factory=list, max_length=MAX_ATTACHMENTS)
    session_id: str | None = None
    agent_id: str | None = None  # only used when starting a new session

    @model_validator(mode="after")
    def _not_empty(self):
        if not self.message.strip() and not self.attachments:
            raise ValueError("Send a message or attach a file")
        return self


class AgentIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=60)
    role: str = Field(default="", max_length=80)
    icon: str = Field(default="bot", max_length=40)
    description: str = Field(default="", max_length=500)
    instructions: str = Field(default="", max_length=8000)
    tools: list[str] = Field(default_factory=list, max_length=50)


class RenameRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)


def _error_message(exc: Exception) -> str:
    # The SDK raises TypeError when no credential source resolves at all.
    if isinstance(exc, anthropic.AuthenticationError) or "Could not resolve authentication" in str(exc):
        return "Authentication failed - set ANTHROPIC_API_KEY (or run `ant auth login`) for the backend."
    if isinstance(exc, anthropic.RateLimitError):
        return "Rate limited by the Claude API. Wait a moment and try again."
    if isinstance(exc, anthropic.BadRequestError):
        return f"The Claude API rejected the request: {exc.message}"
    if isinstance(exc, anthropic.APIStatusError):
        return f"Claude API error ({exc.status_code}): {exc.message}"
    if isinstance(exc, anthropic.APIConnectionError):
        return "Could not reach the Claude API. Check the backend's network connection."
    return f"Unexpected error: {type(exc).__name__}: {exc}"


def _session_or_404(request: Request, user: dict, session_id: str) -> dict:
    # Another user's session is reported as missing, not forbidden, so IDs don't leak.
    session = request.app.state.store.get_session(user["id"], session_id)
    if session is None:
        raise HTTPException(404, "Session not found")
    return session


def _sse(event: str, data: dict) -> dict:
    return {"event": event, "data": json.dumps(data)}


@router.get("/health")
async def health(request: Request):
    s = request.app.state.settings
    return {"status": "ok", "model": s.model, "effort": s.effort, "web_tools": s.enable_web_tools}


@router.get("/tools")
async def list_tools(request: Request, _: CurrentUser):
    return request.app.state.agent.catalog


def _agent_fields(request: Request, body: AgentIn) -> dict:
    known = {t["name"] for t in request.app.state.agent.catalog}
    if unknown := sorted(set(body.tools) - known):
        raise HTTPException(422, f"Unknown tools: {', '.join(unknown)}")
    return {**body.model_dump(), "tools": sorted(set(body.tools))}


def _user_agents(store, user_id: str) -> list[dict]:
    # A user's first look at agents gives them editable copies of the built-in ones.
    return store.list_agents(user_id) or store.seed_agents(user_id, PRESETS)


@router.get("/agents")
async def list_agents(request: Request, user: CurrentUser):
    return _user_agents(request.app.state.store, user["id"])


@router.post("/agents", status_code=201)
async def create_agent(body: AgentIn, request: Request, user: CurrentUser):
    store = request.app.state.store
    _user_agents(store, user["id"])
    return store.create_agent(user["id"], _agent_fields(request, body))


@router.put("/agents/{agent_id}")
async def update_agent(agent_id: str, body: AgentIn, request: Request, user: CurrentUser):
    agent = request.app.state.store.update_agent(user["id"], agent_id, _agent_fields(request, body))
    if agent is None:
        raise HTTPException(404, "Agent not found")
    return agent


@router.delete("/agents/{agent_id}", status_code=204)
async def delete_agent(agent_id: str, request: Request, user: CurrentUser):
    store = request.app.state.store
    agents = store.list_agents(user["id"])
    if all(a["id"] != agent_id for a in agents):
        raise HTTPException(404, "Agent not found")
    if len(agents) == 1:
        raise HTTPException(409, "Keep at least one agent.")
    store.delete_agent(user["id"], agent_id)


@router.get("/sessions")
async def list_sessions(request: Request, user: CurrentUser):
    return request.app.state.store.list_sessions(user["id"])


@router.post("/sessions", status_code=201)
async def create_session(request: Request, user: CurrentUser):
    return request.app.state.store.create_session(user["id"])


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, request: Request, user: CurrentUser):
    session = _session_or_404(request, user, session_id)
    session["messages"] = to_transcript(session["messages"])
    return session


@router.patch("/sessions/{session_id}")
async def rename_session(session_id: str, body: RenameRequest, request: Request, user: CurrentUser):
    if not request.app.state.store.rename_session(user["id"], session_id, body.title):
        raise HTTPException(404, "Session not found")
    return {"id": session_id, "title": body.title}


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: str, request: Request, user: CurrentUser):
    if not request.app.state.store.delete_session(user["id"], session_id):
        raise HTTPException(404, "Session not found")


@router.get("/notes")
async def list_notes(request: Request, user: CurrentUser, q: str = ""):
    return request.app.state.store.search_notes(user["id"], q, limit=100)


@router.delete("/notes/{note_id}", status_code=204)
async def delete_note(note_id: int, request: Request, user: CurrentUser):
    if not request.app.state.store.delete_note(user["id"], note_id):
        raise HTTPException(404, "Note not found")


@router.get("/documents")
async def list_documents(request: Request, user: CurrentUser):
    return {"documents": request.app.state.kb.list_documents(user["id"]), "supported": sorted(SUPPORTED_EXTENSIONS)}


@router.post("/documents", status_code=201)
async def upload_document(file: UploadFile, request: Request, user: CurrentUser):
    max_bytes = request.app.state.settings.max_upload_mb * 1024 * 1024
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(413, f"File is larger than {request.app.state.settings.max_upload_mb} MB")
    try:
        # Parsing and embedding are CPU-bound; keep them off the event loop.
        return await asyncio.to_thread(
            request.app.state.kb.add_document, user["id"], file.filename or "upload.txt", data
        )
    except UnsupportedFileError as e:
        raise HTTPException(415, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.delete("/documents/{doc_id}", status_code=204)
async def delete_document(doc_id: str, request: Request, user: CurrentUser):
    if not await asyncio.to_thread(request.app.state.kb.delete_document, user["id"], doc_id):
        raise HTTPException(404, "Document not found")


@router.post("/chat")
async def chat(body: ChatRequest, request: Request, user: CurrentUser):
    store = request.app.state.store
    agent = request.app.state.agent
    settings = request.app.state.settings

    # Validate attachments before creating a session for them.
    try:
        content = user_content(body.message, body.attachments, settings.max_upload_mb * 1024 * 1024)
    except AttachmentError as e:
        raise HTTPException(422, str(e))

    if body.session_id:
        session = _session_or_404(request, user, body.session_id)
    else:
        if body.agent_id and store.get_agent(user["id"], body.agent_id) is None:
            raise HTTPException(404, "Agent not found")
        session = {**store.create_session(user["id"], agent_id=body.agent_id), "messages": []}

    session_id = session["id"]
    if session_id in _active_sessions:
        raise HTTPException(409, "This session is already running. Wait for it to finish.")

    messages = session["messages"]
    if not messages:
        title = (body.message.strip() or body.attachments[0].name).splitlines()[0][:60]
        store.rename_session(user["id"], session_id, title)
        session["title"] = title
    messages.append({"role": "user", "content": content})
    start_len = len(messages)

    workspace = settings.user_workspace(user["id"])
    workspace.mkdir(parents=True, exist_ok=True)
    ctx = ToolContext(store=store, workspace=workspace, user_id=user["id"], kb=request.app.state.kb)
    # The agent's current settings apply on every turn, so edits take effect in existing chats.
    profile = store.get_agent(user["id"], session["agent_id"]) if session.get("agent_id") else None

    async def events():
        _active_sessions.add(session_id)
        try:
            yield _sse("session", {"id": session_id, "title": session["title"], "agent_id": session.get("agent_id")})
            async for ev in agent.run(messages, ctx, profile):
                yield _sse(ev["event"], ev["data"])
        except Exception as exc:
            log.exception("agent run failed")
            if len(messages) == start_len:
                messages.pop()  # nothing happened; don't keep the unanswered message
            yield _sse("error", {"message": _error_message(exc)})
        finally:
            close_dangling_tool_calls(messages)
            if messages:
                store.save_messages(session_id, messages)
            else:
                # The first message failed outright; don't leave an empty chat in the sidebar.
                store.delete_session(user["id"], session_id)
            _active_sessions.discard(session_id)

    return EventSourceResponse(events())
