# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Paperchat: a self-hosted, unauthenticated PDF Q&A service. FastAPI API + static single-page UI, an RQ worker that extracts text from PDFs, MongoDB for metadata/chunks, Valkey (Redis-compatible) as the job queue. Only text-based PDFs are supported (no OCR); retrieval is keyword overlap, not vector search.

## Commands

```bash
# Full stack (mongo, valkey, app on :8000, worker) — needs a .env (copy .env.example)
docker compose -f docker-compose.prod.yml up --build

# API only, with reload (expects Mongo/Valkey reachable, e.g. inside the devcontainer)
./run.sh            # uvicorn app.server:app --host 0.0.0.0 --port 8000 --reload

# Worker (listens on the "documents" queue)
rq worker documents --url "$REDIS_URL"

# Tests (pure unit tests; no Mongo/Redis needed)
python -m pytest
python -m pytest tests/test_core.py::test_split_text_preserves_content_and_bounds_chunks
```

The `.venv`/`venv` directories were created inside the Linux devcontainer (`bin/`, not `Scripts/`) and won't work from Windows directly. The devcontainer (`.devcontainer/`) provides Python 3.12 plus `mongo` and `valkey` services under those hostnames, which match the config defaults. `freeze.sh` overwrites `requirements.txt` with `pip freeze`, so avoid it unless you intend to repin everything.

## Architecture

Request flow for a document:

1. `POST /api/documents` (`app/server.py`) inserts a `files` doc with status `uploading`, streams the upload to `UPLOAD_DIR/<id>.pdf` via `app/utils/file.py:save_upload` (enforces size limit and `%PDF-` magic bytes), sets status `queued`, and enqueues `app.queue.workers.process_file` on RQ.
2. The worker (`app/queue/workers.py`) runs **synchronously** in a separate process: it opens its own blocking `pymongo.MongoClient` (not the async client), extracts per-page text with `pdfplumber`, splits it with `split_text` (1200 chars, 180 overlap, word-boundary aware), replaces the document's rows in `chunks`, and sets status `processing` → `ready` or `failed` (with `error`).
3. The UI (`app/static/app.js`) polls `GET /api/documents/{id}` while status is `queued`/`processing`.
4. `POST /api/documents/{id}/questions` requires status `ready`, ranks up to 500 chunks by term overlap (`app/services/answering.py:retrieve_chunks`, terms = alphanumeric words ≥3 chars), then calls `answer_question` in a thread. If `OPENAI_API_KEY` is unset it returns the top excerpts (`mode: "extractive"`); otherwise it calls the OpenAI Responses API (`mode: "llm"`). The `openai` import is intentionally lazy.

Key points:

- **Two Mongo clients:** the API uses `pymongo.AsyncMongoClient` (`app/db/client.py` → `db.py` → `collections/files.py`, collections `files` and `chunks`); the worker uses a sync client per job. Chunks reference files via `file_id` (an ObjectId).
- **Config** lives in `app/config.py` as a frozen dataclass read from env at import time. Defaults assume docker hostnames (`mongo`, `valkey`) and `/data/uploads`.
- Every DB-backed endpoint calls `require_database()` first so Mongo outages become a 503.
- The API process and the worker must share the upload volume (`uploads` in compose), since the worker reads the file path stored in Mongo.
- In `docker-compose.prod.yml` the worker's Redis URL is hardcoded (`redis://valkey:6379/0`) rather than read from `REDIS_URL`.
- `app/static/` holds minified, single-line HTML/JS/CSS served at `/static` and `/`. The JS duplicates the 25 MB upload limit on the client side, so keep it in sync with `MAX_UPLOAD_MB`.
