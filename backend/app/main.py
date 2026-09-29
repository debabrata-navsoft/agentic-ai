import logging
from contextlib import asynccontextmanager

from anthropic import AsyncAnthropic
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import auth
from app.agent import Agent
from app.api import router
from app.config import get_settings
from app.rag import KnowledgeBase
from app.store import Store
from app.tools import build_registry

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    store = Store(settings.db_path)
    kb = KnowledgeBase(settings.vector_db_path, store)
    # An empty/unset key falls through to the SDK's own lookup: ANTHROPIC_API_KEY,
    # ANTHROPIC_AUTH_TOKEN, or an `ant auth login` profile.
    client = AsyncAnthropic(api_key=settings.anthropic_api_key) if settings.anthropic_api_key else AsyncAnthropic()
    app.state.settings = settings
    app.state.store = store
    app.state.kb = kb
    # Tool context is per user, so the route builds it for each run (see api.chat).
    app.state.agent = Agent(client=client, settings=settings, registry=build_registry())
    yield
    await client.close()


app = FastAPI(title="Synora Agent API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,  # the login cookie
)
app.include_router(auth.router)
app.include_router(router)
