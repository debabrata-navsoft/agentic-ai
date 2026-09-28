# Frontend

This project was generated using [Angular CLI](https://github.com/angular/angular-cli) version 21.2.13.

## Development server

To start a local development server, run:

```bash
ng serve
```

Once the server is running, open your browser and navigate to `http://localhost:4200/`. The application will automatically reload whenever you modify any of the source files.

## Code scaffolding

Angular CLI includes powerful code scaffolding tools. To generate a new component, run:

```bash
ng generate component component-name
```

For a complete list of available schematics (such as `components`, `directives`, or `pipes`), run:

```bash
ng generate --help
```

## Building

To build the project run:

```bash
ng build
```

This will compile your project and store the build artifacts in the `dist/` directory. By default, the production build optimizes your application for performance and speed.

## Running unit tests

To execute unit tests with the [Vitest](https://vitest.dev/) test runner, use the following command:

```bash
ng test
```

## Running end-to-end tests

For end-to-end (e2e) testing, run:

```bash
ng e2e
```

Angular CLI does not come with an end-to-end testing framework by default. You can choose one that suits your needs.

## Additional Resources

For more information on using the Angular CLI, including detailed command references, visit the [Angular CLI Overview and Command Reference](https://angular.dev/tools/cli) page.




```
The backend runs on Python 3.12.3, with packages installed in backend/.venv. requirements.txt lists 12 packages, and pip pulled in their dependencies for 96 in total.

Core: API server and LLM

Package	Version	Used for
anthropic	1.8.0	Calls Claude (the LLM) and streams its replies
fastapi	0.141.1	REST API framework (app/api.py)
uvicorn[standard]	0.54.0	Server that runs the FastAPI app
pydantic	2.13.5	Checks request bodies and tool inputs
pydantic-settings	2.15.0	Loads AGENT_* settings from .env
sse-starlette	3.4.11	Streams agent events to the browser (SSE)
python-multipart	0.0.32	Accepts file uploads (POST /api/documents)
RAG: document search

Package	Version	Used for
chromadb	1.5.9	Vector database that stores document embeddings
pypdf	6.19.0	Reads text out of PDFs
Testing

Package	Version	Used for
pytest	9.1.1	Runs the backend tests
httpx	0.28.1	Listed in requirements, but no code uses it
Notable packages pulled in automatically

httpx2 (2.13.1): the HTTP library the Anthropic SDK is built on. The agent tests use it to fake Claude's responses.
onnxruntime (1.30.0): runs the local embedding model for RAG.
numpy (2.5.3): handles vector math for ChromaDB.
Standard library: sqlite3 is built into Python, so there's no separate database install.

To reinstall everything:


cd backend && .venv/bin/pip install -r requirements.txt
The httpx line can come out of requirements.txt, since the tests use httpx2, which the SDK already installs. Should I remove it?
```

cd backend && .venv/bin/pip install -r requirements.txt
