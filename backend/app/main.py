import logging
from contextlib import asynccontextmanager

from anthropic import AsyncAnthropic
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent import Agent
from app.api import router
from app.config import get_settings
from app.rag import KnowledgeBase
from app.store import Store
from app.tools import ToolContext, build_registry

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    store = Store(settings.db_path)
    kb = KnowledgeBase(settings.vector_db_path, store)
    # Credentials resolve from ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, or an `ant auth login` profile.
    client = AsyncAnthropic()
    app.state.settings = settings
    app.state.store = store
    app.state.kb = kb
    app.state.agent = Agent(
        client=client,
        settings=settings,
        registry=build_registry(),
        ctx=ToolContext(store=store, workspace=settings.workspace_dir, kb=kb),
    )
    yield
    await client.close()


app = FastAPI(title="Atlas Agent API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
