# Atlas — Agentic AI Assistant

A full-stack agentic AI app: a **FastAPI** backend runs a Claude-powered agent loop with tools,
memory, and RAG, and an **Angular** frontend streams the agent's reasoning, tool calls, and answers live.

```
Angular 21 (Chat UI)
   │
   │  HTTP (REST) / SSE (streaming)
   ▼
Python Backend
   ├── FastAPI           app/api.py
   ├── Agent             app/agent/loop.py      understand → choose tool → execute → observe → repeat
   ├── LLM               Claude (claude-opus-5, adaptive thinking)
   ├── Tools             app/tools/             web search/fetch, calculator, clock, files
   ├── Memory            app/tools/memory.py    long-term notes shared across chats
   └── RAG               app/rag/               upload → chunk → embed → retrieve
        ├── Database     SQLite                 sessions, notes, document metadata
        └── Vector DB    ChromaDB               chunk embeddings (local all-MiniLM-L6-v2)
```

## Project layout

```
agentic-ai/
├── backend/                  Python · FastAPI · Anthropic SDK
│   ├── app/
│   │   ├── main.py           App factory, CORS, lifespan wiring
│   │   ├── api.py            REST + SSE endpoints
│   │   ├── config.py         Settings (AGENT_* env vars)
│   │   ├── store.py          SQLite: sessions + long-term notes
│   │   ├── transcript.py     API history → UI display shape
│   │   ├── agent/
│   │   │   ├── loop.py       Streaming agent loop (tool calls, pause_turn, refusals, fallbacks)
│   │   │   └── prompts.py    System prompt
│   │   ├── rag/
│   │   │   ├── chunking.py   Text/PDF extraction, paragraph-aware chunking with overlap
│   │   │   └── knowledge_base.py  ChromaDB vector store: add, search, delete
│   │   └── tools/
│   │       ├── base.py       Tool framework (Pydantic-validated inputs)
│   │       ├── utility.py    calculator, get_current_time
│   │       ├── memory.py     save_note, search_notes, delete_note
│   │       ├── knowledge.py  search_knowledge_base, list_documents (RAG retrieval)
│   │       └── files.py      list_files, read_file, write_file (sandboxed workspace)
│   └── tests/
└── frontend/                 Angular 21 · signals · standalone components
    └── src/app/
        ├── core/
        │   ├── models/       chat.models.ts — shared types
        │   ├── services/     agent-api.ts (HTTP + SSE), chat-store.ts (signal state)
        │   └── utils/        reduce-event.ts — stream event → message reducer
        ├── shared/pipes/     markdown.pipe.ts
        └── features/
            ├── sidebar/      Chats · Docs (upload) · Memory · Tools panel
            └── chat/
                ├── chat-panel/   Thread, welcome screen, composer
                └── message/      One message: text, reasoning, tool cards
```

## How the agent works

1. The user's message is appended to the session history and sent to Claude (`claude-opus-5`,
   adaptive thinking) with the tool definitions.
2. The response streams back; text, reasoning summaries, and tool activity are forwarded to the
   browser as Server-Sent Events.
3. If Claude requests tools, the backend validates inputs, runs them concurrently, and sends the
   results back. This repeats until Claude answers without calling tools (capped at
   `AGENT_MAX_ITERATIONS`).
4. The full history (including thinking and tool blocks) is saved to SQLite so a conversation
   can be resumed later.

**Tools:** web search and web fetch (run by Anthropic's servers), calculator, clock, long-term memory
shared across chats, RAG search over uploaded documents, and file read/write confined to
`backend/workspace/`.

## How RAG works

1. **Ingest:** upload a file from the Docs tab (`POST /api/documents`). Text is extracted (PDF via
   `pypdf`), split into ~1000-character chunks with 150 characters of overlap, embedded locally with
   all-MiniLM-L6-v2, and stored in ChromaDB (`backend/data/chroma/`).
2. **Retrieve:** when a question may be answered by your documents, the agent calls
   `search_knowledge_base`, which embeds the query and returns the top passages by cosine similarity.
3. **Generate:** Claude answers from those passages and cites the source file names.

The embedding model (~80 MB) downloads on first upload and is cached in `~/.cache/chroma`.

## Run it

**Backend** (Python 3.10+):

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # then set ANTHROPIC_API_KEY in .env
uvicorn app.main:app --reload --port 8000
```

**Frontend:**

```bash
cd frontend
npm install
npm start                          # http://localhost:4200, proxies /api → :8000
```

## Tests

```bash
cd backend && pytest               # tools, RAG, and agent loop against a mocked HTTP transport
cd frontend && npx ng test --watch=false
```

## API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/chat` | `{message, session_id?}` → SSE stream of agent events |
| `GET` | `/api/sessions` | List conversations |
| `GET` / `PATCH` / `DELETE` | `/api/sessions/{id}` | Read transcript / rename / delete |
| `GET` / `POST` | `/api/documents` | List / upload (multipart `file`) RAG documents |
| `DELETE` | `/api/documents/{id}` | Remove a document and its vectors |
| `GET` | `/api/notes` | Long-term memory (`?q=` to search) |
| `DELETE` | `/api/notes/{id}` | Forget a note |
| `GET` | `/api/tools` | Tool catalog |
| `GET` | `/api/health` | Model and settings |

SSE events: `session`, `step_start`, `text`, `thinking`, `tool_start`, `tool_input`,
`tool_result`, `step_discard`, `refusal`, `notice`, `error`, `done`.

## Configuration

All settings are environment variables. See `backend/.env.example`:
`AGENT_MODEL`, `AGENT_EFFORT` (`low`…`max`), `AGENT_MAX_TOKENS`, `AGENT_MAX_ITERATIONS`,
`AGENT_ENABLE_WEB_TOOLS`, `AGENT_ENABLE_FALLBACKS`, `AGENT_DATA_DIR`, `AGENT_WORKSPACE_DIR`,
`AGENT_CORS_ORIGINS`.

Server-side refusal fallbacks are on by default: if Claude's safety classifiers decline a request,
the API re-runs it on a recommended fallback model instead of returning a refusal.
