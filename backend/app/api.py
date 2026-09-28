import asyncio
import json
import logging

import anthropic
from fastapi import APIRouter, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.agent.loop import close_dangling_tool_calls
from app.rag import SUPPORTED_EXTENSIONS, UnsupportedFileError
from app.transcript import to_transcript

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

# Sessions with a run in progress; a second concurrent run would interleave history.
_active_sessions: set[str] = set()


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=100_000)
    session_id: str | None = None


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


def _session_or_404(request: Request, session_id: str) -> dict:
    session = request.app.state.store.get_session(session_id)
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
async def list_tools(request: Request):
    return request.app.state.agent.catalog


@router.get("/sessions")
async def list_sessions(request: Request):
    return request.app.state.store.list_sessions()


@router.post("/sessions", status_code=201)
async def create_session(request: Request):
    return request.app.state.store.create_session()


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, request: Request):
    session = _session_or_404(request, session_id)
    session["messages"] = to_transcript(session["messages"])
    return session


@router.patch("/sessions/{session_id}")
async def rename_session(session_id: str, body: RenameRequest, request: Request):
    if not request.app.state.store.rename_session(session_id, body.title):
        raise HTTPException(404, "Session not found")
    return {"id": session_id, "title": body.title}


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: str, request: Request):
    if not request.app.state.store.delete_session(session_id):
        raise HTTPException(404, "Session not found")


@router.get("/notes")
async def list_notes(request: Request, q: str = ""):
    return request.app.state.store.search_notes(q, limit=100)


@router.delete("/notes/{note_id}", status_code=204)
async def delete_note(note_id: int, request: Request):
    if not request.app.state.store.delete_note(note_id):
        raise HTTPException(404, "Note not found")


@router.get("/documents")
async def list_documents(request: Request):
    return {"documents": request.app.state.kb.list_documents(), "supported": sorted(SUPPORTED_EXTENSIONS)}


@router.post("/documents", status_code=201)
async def upload_document(file: UploadFile, request: Request):
    max_bytes = request.app.state.settings.max_upload_mb * 1024 * 1024
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(413, f"File is larger than {request.app.state.settings.max_upload_mb} MB")
    try:
        # Parsing and embedding are CPU-bound; keep them off the event loop.
        return await asyncio.to_thread(request.app.state.kb.add_document, file.filename or "upload.txt", data)
    except UnsupportedFileError as e:
        raise HTTPException(415, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.delete("/documents/{doc_id}", status_code=204)
async def delete_document(doc_id: str, request: Request):
    if not await asyncio.to_thread(request.app.state.kb.delete_document, doc_id):
        raise HTTPException(404, "Document not found")


@router.post("/chat")
async def chat(body: ChatRequest, request: Request):
    store = request.app.state.store
    agent = request.app.state.agent

    session = _session_or_404(request, body.session_id) if body.session_id else {**store.create_session(), "messages": []}

    session_id = session["id"]
    if session_id in _active_sessions:
        raise HTTPException(409, "This session is already running. Wait for it to finish.")

    messages = session["messages"]
    if not messages:
        title = body.message.strip().splitlines()[0][:60]
        store.rename_session(session_id, title)
        session["title"] = title
    messages.append({"role": "user", "content": body.message})
    start_len = len(messages)

    async def events():
        _active_sessions.add(session_id)
        try:
            yield _sse("session", {"id": session_id, "title": session["title"]})
            async for ev in agent.run(messages):
                yield _sse(ev["event"], ev["data"])
        except Exception as exc:
            log.exception("agent run failed")
            if len(messages) == start_len:
                messages.pop()  # nothing happened; don't keep the unanswered message
            yield _sse("error", {"message": _error_message(exc)})
        finally:
            close_dangling_tool_calls(messages)
            store.save_messages(session_id, messages)
            _active_sessions.discard(session_id)

    return EventSourceResponse(events())
