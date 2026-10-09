"""HTTP API for the locally trained model. No third-party AI service is called."""

import json
import os
from collections.abc import Iterator
from contextlib import asynccontextmanager
from pathlib import Path

import torch
from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.model import load_checkpoint
from app.search import DocumentStore

CHECKPOINT = Path(os.environ.get("MODEL_CHECKPOINT", "checkpoints/model.pt"))
DOCS_DIR = Path(os.environ.get("DOCS_DIR", "data/docs"))
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
torch.set_num_threads(int(os.environ.get("MODEL_THREADS", os.cpu_count() or 1)))


def load_model(app: FastAPI) -> None:
    app.state.model = app.state.tok = None
    app.state.meta = {}
    if CHECKPOINT.exists():
        app.state.model, app.state.tok, app.state.meta = load_checkpoint(CHECKPOINT)


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_model(app)
    app.state.docs = DocumentStore(DOCS_DIR)
    yield


app = FastAPI(title="Synora AI", lifespan=lifespan)


class GenerateRequest(BaseModel):
    prompt: str = Field("", max_length=2000)
    max_new_tokens: int = Field(300, ge=1, le=2000)
    temperature: float = Field(0.8, ge=0.1, le=2.0)
    top_k: int | None = Field(None, ge=1)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/model")
def model_info(request: Request) -> dict:
    model = request.app.state.model
    if model is None:
        return {"loaded": False, "checkpoint": str(CHECKPOINT)}
    meta = request.app.state.meta
    return {
        "loaded": True,
        "checkpoint": str(CHECKPOINT),
        "params": model.num_params(),
        "config": vars(model.cfg),
        "vocab": "".join(request.app.state.tok.chars),
        "step": meta.get("step"),
        "val_loss": meta.get("val_loss"),
        "data": meta.get("data"),
    }


@app.post("/api/model/reload")
def reload_model(request: Request) -> dict:
    """Pick up a checkpoint written by `app.train` without restarting the server."""
    load_model(request.app)
    return model_info(request)


@app.post("/api/generate")
def generate(body: GenerateRequest, request: Request) -> StreamingResponse:
    model, tok = request.app.state.model, request.app.state.tok
    if model is None:
        raise HTTPException(503, "No trained model yet. Run `python -m app.train` in backend/ first.")

    unknown = tok.unknown(body.prompt)
    prompt = "".join(c for c in body.prompt if c not in unknown) or "\n"

    def events() -> Iterator[str]:
        if unknown:
            yield _sse({"notice": f"Ignored characters the model never saw: {''.join(sorted(unknown))}"})
        for token_id in model.generate(tok.encode(prompt), body.max_new_tokens, body.temperature, body.top_k):
            yield _sse({"text": tok.decode([token_id])})
        yield _sse({"done": True})

    # A sync iterator: Starlette runs it in a worker thread, so CPU-bound sampling doesn't block the loop.
    return StreamingResponse(events(), media_type="text/event-stream")


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    k: int = Field(5, ge=1, le=20)


@app.post("/api/search")
def search(body: SearchRequest, request: Request) -> dict:
    return request.app.state.docs.search(body.query, body.k)


@app.get("/api/docs")
def list_docs(request: Request) -> list[dict]:
    return request.app.state.docs.documents()


@app.post("/api/docs", status_code=201)
def upload_doc(file: UploadFile, request: Request) -> dict:
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File is larger than 20 MB.")
    try:
        name = request.app.state.docs.add(file.filename or "upload.txt", data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return next(d for d in request.app.state.docs.documents() if d["name"] == name)


@app.delete("/api/docs/{name}", status_code=204)
def delete_doc(name: str, request: Request) -> None:
    if not request.app.state.docs.delete(name):
        raise HTTPException(404, "No such document.")


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"
