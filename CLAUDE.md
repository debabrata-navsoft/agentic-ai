# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Synora is an agentic AI assistant: a Python/FastAPI backend runs a Claude tool-use loop (tools, long-term
memory, RAG over uploaded documents) and streams it over SSE to an Angular 21 chat UI. See README.md for
the user-facing overview and API table.

## Commands

Backend (run from `backend/`; the venv already exists at `backend/.venv`):

```bash
.venv/bin/uvicorn app.main:app --reload --port 8000      # dev server (needs ANTHROPIC_API_KEY in .env or `ant auth login`)
.venv/bin/python -m pytest -q                            # all tests
.venv/bin/python -m pytest tests/test_rag.py::test_add_search_delete -q   # single test
.venv/bin/pip install -r requirements.txt
```

This machine lacks `python3-venv`/ensurepip; if the venv must be recreated use
`python3 -m venv --without-pip .venv` and bootstrap pip with `get-pip.py`.

Frontend (run from `frontend/`):

```bash
npm start                                                # ng serve on :4200, proxies /api → :8000 (proxy.conf.json)
npx ng build
npx ng test --watch=false                                # Vitest via @angular/build:unit-test
npx ng test --watch=false --include src/app/core/utils/reduce-event.spec.ts   # single spec file
npx prettier --write "src/**/*.{ts,html,css}"            # formatting (printWidth 100, single quotes); no linter is configured
```

Backend tests never call the real API. `tests/test_agent.py` drives the real Anthropic SDK against an
`httpx2.MockTransport` returning canned SSE. `anthropic` 1.x is built on **`httpx2`**, not `httpx`: import
`httpx2` for transports and pass them via `anthropic.DefaultAsyncHttpxClient`.

## Architecture

### Request flow

`POST /api/chat` (`app/api.py`) loads the session's stored message history, appends the user message, and
returns an `EventSourceResponse` wrapping `Agent.run(messages, ctx)` (`app/agent/loop.py`). The route
builds `ctx`, a per-user `ToolContext`, for each run. `Agent.run` is an
async generator: each iteration streams one model call through `client.beta.messages.stream(...)`,
translates SDK stream events into UI events, runs requested client tools concurrently, appends the turn to
`messages` **in place**, and loops until the model stops calling tools or `AGENT_MAX_ITERATIONS` is hit.
The `finally` block in the route always persists `messages` to SQLite.

### Accounts and authorization

- `app/auth.py` owns accounts: scrypt password hashing (stdlib, no dependency), the auth/admin routes, and
  the `CurrentUser` / `AdminUser` FastAPI dependencies. Every route except `/api/health` and `/api/auth/*`
  takes `user: CurrentUser`.
- A login is a random token in the httpOnly `synora_session` cookie (path `/api`). Only its SHA-256 is
  stored (`auth_tokens`), so logout and disabling a user revoke it immediately. The frontend never handles
  the token; same-origin requests (via the dev proxy) carry the cookie.
- Roles are `user` and `admin`. The first account to sign up becomes admin and claims pre-account data:
  rows with a NULL `user_id` (`Store.create_user`) and loose workspace files (`claim_legacy_workspace`).
  Admins can't change their own role or status, so at least one admin always remains.
- Admins and users sign in separately: `POST /api/auth/login` refuses admins and
  `POST /api/auth/admin/login` (the `/admin` page, `AuthPage` with `[admin]="true"`) refuses non-admins,
  both before creating a session. Sign-up still logs in the first account, which becomes admin.
- Passwords: `POST /api/auth/password` (change; signs out the user's other logins),
  `/api/auth/forgot` (always 202, so it doesn't reveal which emails exist; sends after responding) and
  `/api/auth/reset`. Reset tokens are single-use and hashed (`password_resets`). `app/mailer.py` emails
  the link via `AGENT_SMTP_*`, or logs it when no SMTP host is set. The frontend reads
  `/reset-password?token=` into `AuthStore.resetToken` before the URL sync rewrites the address.
- Frontend pages map to URLs in `app.ts` (`PATHS`; Users is `/admin`). `ChatStore.canView` is the route
  guard: `setActiveView` sends a refused page to the chat.
- Everything user-owned is scoped by `user_id`. `Store` methods take `user_id` first. Another user's
  session or note is reported as 404, not 403. Tools read `ctx.user_id`, and each user's file workspace is
  `AGENT_WORKSPACE_DIR/<user_id>`.
- RAG ownership lives in SQLite only. `KnowledgeBase.search` restricts Chroma with
  `where={"doc_id": {"$in": <user's doc ids>}}`, so Chroma metadata has no user field.
- Frontend: `AuthStore` holds `user`/`ready`. `App` shows `AuthPage` until signed in and resets and
  reloads `ChatStore` when the user ID changes. `authInterceptor` (HttpClient) and `ApiError.status === 401`
  (the `fetch`-based chat) call `AuthStore.expire()`.

### The SSE event protocol is a cross-stack contract

Event names and payloads (`session`, `step_start`, `text`, `thinking`, `tool_start`, `tool_input`,
`tool_result`, `step_discard`, `refusal`, `notice`, `error`, `done`) are produced in `loop.py`
(`Agent.run` and `Agent._translate`) plus `api.py` (`session`, `error`). They are consumed by
`frontend/src/app/core/utils/reduce-event.ts`. Changing an event means changing both sides.

`step_start`/`step_discard` exist so the UI can roll back a model step the backend threw away (a refusal,
or tool-input JSON that failed to parse). The reducer records the part index on the message
(`stepStart`) at each `step_start` and truncates back to it.

There are two sources of the display shape (`parts`: text / thinking / tool / notice):
- live: the SSE reducer, `reduce-event.ts`
- reloaded sessions: `backend/app/transcript.py`, which converts stored API history into the same shape

Both must match `core/models/chat.models.ts`. `transcript.py` also owns `summarize_server_result`,
`is_server_result` and `MAX_RESULT_PREVIEW`. The loop imports them, so live and reloaded sessions render
server-tool results identically.

### Message history invariants

Session history is stored as raw Anthropic API message dicts, including thinking blocks, `tool_use`,
server-tool blocks and `tool_result`. It is sent back verbatim on the next turn. Keep it **append-only**:
editing earlier turns invalidates thinking blocks and the prompt cache.
- Assistant content is serialized with `_dump_block` (SDK `to_dict`, minus the SDK-only `parsed_output`).
- After a server-side refusal fallback, `_echo_content` strips blocks that must not be echoed from before
  the `fallback` marker.
- `close_dangling_tool_calls` answers any `tool_use` left without a result (client disconnect mid-tool) so
  the stored history stays valid.
- If a run fails before producing anything, the route pops the user message it added.
- A refused turn is never appended.
- `_active_sessions` (an in-process set) blocks concurrent runs on one session. This assumes a single
  uvicorn worker.

### Claude request shape

Built in `Agent._request`:
- model `claude-opus-5` with `thinking: {type: "adaptive", display: "summarized"}` (the UI shows reasoning
  summaries)
- `output_config.effort` and top-level `cache_control` (auto prompt caching)
- server-side refusal fallbacks: `fallbacks: "default"` + beta `server-side-fallback-2026-07-01`, toggled
  by `AGENT_ENABLE_FALLBACKS`

These parameters assume the Opus 5 / Fable family. Switching `AGENT_MODEL` to an older model (e.g. Haiku
4.5) requires changing the thinking/effort/fallback params.

For prompt-cache stability:
- `prompts.py` is deliberately static, with no dates or per-request data. The agent gets the date from
  the `get_current_time` tool.
- `ToolRegistry.definitions()` returns tools sorted by name.

The loop handles these stop reasons:
- `pause_turn`: re-send to resume the server tool
- `max_tokens` with pending tool calls: return error tool_results instead of running truncated inputs
- `refusal`

### Tools

- Client tools live in `app/tools/*.py`.
  - Each tool is a `Tool(name, description, input_model, handler)`. `input_model` subclasses `ToolInput`
    (Pydantic, `extra="forbid"`), and its JSON schema becomes `input_schema`.
  - Tools are declared with `eager_input_streaming: true`, so the API does not validate inputs.
    `Tool.run` validates with Pydantic and turns failures into `is_error` tool_results.
  - Handlers are plain sync functions, and `Tool.run` runs them in a worker thread. Raise `ToolError`
    for an expected, model-visible error.
  - Handlers get a `ToolContext` (`store`, `workspace`, `user_id`, `kb`), built per run. Always pass
    `ctx.user_id` to `Store`/`KnowledgeBase` calls.
- To add a tool:
  1. Add the `Tool` to its module's `TOOLS` list. Its `label` is what the UI shows, served via
     `/api/tools`, so there is no frontend change.
  2. Make sure the module is included in `build_registry()` (`app/tools/__init__.py`).
  3. Mention the tool in `agent/prompts.py`.
  4. Put the tool's main argument first in its input model; the UI previews the first input value.
- `ToolRegistry` builds the sorted definitions once, and `Agent` caches `tools` (sent to the API) and
  `catalog` (served to the UI) at construction.
- Server tools (`web_search_20260209`, `web_fetch_20260209`) are plain dicts in `SERVER_TOOLS`, with UI
  metadata in `SERVER_TOOL_CATALOG`. Anthropic
  runs them, and their results arrive as content blocks (`server_tool_use`, `*_tool_result`), never
  through local execution. `AGENT_ENABLE_WEB_TOOLS` gates them.
- File tools resolve every path inside `AGENT_WORKSPACE_DIR` and reject escapes (`files.py::_resolve`).

### Agent profiles

- An agent is a per-user `agents` row: name, role, icon, description, `instructions`, and a `tools`
  list of tool names. `GET /api/agents` seeds a user's editable copies of `PRESETS`
  (`app/agent/profiles.py`) the first time; a user must keep at least one agent.
- A session stores `agent_id` when it is created (`ChatRequest.agent_id` is ignored for existing
  sessions). NULL, or an agent that was deleted, means plain Synora with every tool.
- `Agent.run(messages, ctx, profile)` appends the profile's role and instructions to `SYSTEM_PROMPT`
  (`system_prompt()`), sends only the profile's tools (filtered, so order stays sorted), and rejects
  calls to any other tool. The profile is re-read every turn, so edits apply to existing chats.

### Providers (Claude and OpenAI)

- `app.state.runners` maps a provider to its loop: `"anthropic"` (`Agent`, always) and `"openai"`
  (`OpenAIAgent` in `app/agent/openai_loop.py`, only when `OPENAI_API_KEY` is set).
- A session's `provider` is fixed when it is created: the agent's `provider`, or else
  `AGENT_DEFAULT_PROVIDER`. NULL means anthropic. Its history is stored in that provider's message
  format, so the route uses the runner's `user_content` / `close_dangling` hooks and
  `TRANSCRIPTS[provider]` (`to_transcript` / `openai_transcript`).
- `OpenAIAgent` uses Chat Completions streaming and yields the same UI events as `Agent`. It has no
  server tools (web search/fetch) and no thinking events. Tool results that are errors carry an
  `Error: ` prefix, since Chat Completions tool messages have no error flag. `tests/test_openai.py`
  drives the real `openai` SDK (also `httpx2`-based) against canned SSE.

### Persistence and RAG

- `app/store.py` is one SQLite connection (`check_same_thread=False`, guarded by a lock) with tables
  `users`, `auth_tokens`, `sessions` (history JSON), `notes` (long-term memory shared across one user's
  sessions), and `documents` (RAG
  document metadata).
- RAG (`app/rag/`) splits storage across two stores: document metadata goes in SQLite, and chunk text plus
  vectors go in ChromaDB (`data/chroma`). Chunk IDs are `"{doc_id}:{i}"` with `doc_id` in the metadata for
  deletes.
- The Chroma collection is created with `embedding_function=None`, and `KnowledgeBase` computes embeddings
  itself and passes them explicitly. This keeps the embedder injectable: tests pass a hashed bag-of-words
  `fake_embedder` so no model download is needed.
- The default embedder (Chroma's ONNX all-MiniLM-L6-v2, ~80 MB to `~/.cache/chroma`) loads lazily on first
  use.
- Upload parsing and embedding are CPU-bound and run via `asyncio.to_thread`.
- App singletons (`settings`, `store`, `kb`, `agent`) are created in the FastAPI `lifespan` in `main.py` and
  read from `request.app.state`.
- All settings are `AGENT_*` env vars (`app/config.py`, see `.env.example`). Runtime data goes in
  `backend/data/` and `backend/workspace/`, both gitignored.

### Frontend

- Angular 21, standalone components, signals, zoneless (no zone.js).
- Layout: `core/` (models, `AgentApi`, `ChatStore`, reducer), `shared/` (markdown pipe), `features/`
  (`sidebar`, `chat/chat-panel`, `chat/message`).
- `ChatStore` (`core/services/chat-store.ts`) is the single root-provided state container. Components read
  its signals directly.
- `reduceEvent` must stay pure and return new objects. `Message` is `OnPush` and only re-renders when it
  receives a new message reference.
- `ChatStore.send` queues stream events and applies them once per `requestAnimationFrame`
  (`events.reduce(reduceEvent, msg)`). Applying them per token would re-parse the message's Markdown on
  every token.
- `/api/chat` is POST, so `AgentApi.chat` reads the SSE body from `fetch()` and parses frames by hand
  (`parseSseFrame`), because `EventSource` only supports GET. It normalizes sse-starlette's `\r\n` and
  skips `:` keep-alive comments. Everything else uses `HttpClient`.
- Icons are `@lucide/angular`, used by name (`<svg lucideIcon="file-text">`, with the component importing
  `LucideDynamicIcon`). Every name must be listed in `core/icons.ts` (`APP_ICONS`). `app.config.ts` and
  `app.spec.ts` both register that list, since TestBed doesn't load the app config.
- Styles:
  - Component styles are scoped. `src/styles.css` holds only theme variables and rules shared across
    components.
  - `.markdown` rules must stay global, because rendered Markdown is inserted via `[innerHTML]` and scoped
    styles don't reach it.
  - `angular.json` enforces per-component CSS budgets of 4 kB (warning) and 8 kB (error).
