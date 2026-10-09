# Synora AI

My own AI, built from scratch and run on this computer. No pretrained weights, no third-party AI APIs.
The web app has two pages:

- **Ask documents**: a chat-style search over your own files. Type a question and get an answer quoted
  from the best-matching passages, with sources (`backend/app/search.py`).
- **Write with my model**: a small GPT-style language model, trained here from random weights,
  continues text you start (`backend/app/model.py`).

```
backend/    FastAPI server, document search (app/search.py), the model (app/model.py), training (app/train.py)
frontend/   Angular 21 web app that streams text from the backend
lessons/    step-by-step learning scripts (l01_..., l02_...)
data/       training text (not committed)
```

## What it is (and isn't)

Ask documents:

- Uploaded `.txt`, `.md` and `.pdf` files go in `backend/data/docs/`, are split into ~800-character
  passages, and are ranked with BM25 (word matches weighted by how rare each word is).
- The answer is the best-matching sentences **quoted** from your documents. It can only find what's in
  them, and doesn't write new text or reason the way ChatGPT does.
- Files copied into `backend/data/docs/` by hand are picked up automatically on the next search.

Write with my model:

- A character-level transformer (~0.8M parameters, 4 layers, 128-char context) whose weights start
  random and are learned only from `data/shakespeare.txt`.
- It continues text in the style of its training data. It has no knowledge, can't answer questions, and
  isn't a chat assistant. That needs far more data, parameters and GPU compute than one CPU has.
- PyTorch provides tensors, autograd and generic layers. The tokenizer, attention, transformer
  blocks, training loop and sampling are implemented in `backend/app/model.py` and `train.py`.

## Run it

Backend (from `backend/`):

```bash
.venv/bin/python -m app.train                          # train from scratch (~10 min on 4 CPU cores)
.venv/bin/uvicorn app.main:app --reload --port 8000    # API on :8000
.venv/bin/python -m pytest -q                          # tests
```

Frontend (from `frontend/`):

```bash
npm start                    # http://localhost:4200, proxies /api to :8000
npx ng test --watch=false
```

Training writes `backend/checkpoints/model.pt` (best validation loss) and `train_log.csv`. Retrain while
the server runs, then click **Reload model** in the UI.

Train options: `--steps`, `--n-layer`, `--n-head`, `--n-embd`, `--block-size`, `--batch-size`, `--lr`,
`--data <any .txt file>`. See `python -m app.train --help`.

## API

| Method | Path                | Purpose                                                      |
| ------ | ------------------- | ------------------------------------------------------------ |
| GET    | `/api/health`       | liveness                                                     |
| GET    | `/api/model`        | is a model loaded, its size, training step and val loss      |
| POST   | `/api/model/reload` | reload `checkpoints/model.pt` from disk                      |
| POST   | `/api/generate`     | `{prompt, max_new_tokens, temperature, top_k}` → SSE stream  |
| POST   | `/api/search`       | `{query, k}` → `{answer, terms, results[], searched_passages}` |
| GET    | `/api/docs`         | list documents and their passage counts                      |
| POST   | `/api/docs`         | upload a file (multipart field `file`, max 20 MB)            |
| DELETE | `/api/docs/{name}`  | delete a document                                            |

`/api/generate` streams `data: {"text": "…"}` per character, an optional `{"notice": …}` when the prompt
contains characters the model never saw, and ends with `{"done": true}`.

## Setup from scratch

This machine lacks `python3-venv`, so the venvs were made with `python3 -m venv --without-pip .venv` and
pip bootstrapped with `get-pip.py`. With `sudo apt install python3-venv` available:

```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cd ../frontend && npm install
```

## Data

- `data/shakespeare.txt`: Tiny Shakespeare (public domain), from
  https://raw.githubusercontent.com/karpathy/char-rnn/master/data/tinyshakespeare/input.txt

## Learning progress

- [x] Phase 1, Lesson 1: environment setup, text statistics (`lessons/l01_text_stats.py`)
