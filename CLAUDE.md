# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Paperchat: users sign in with Google, upload text-based PDFs and ask questions with page-cited answers. FastAPI API +
React/Vite frontend served from the same origin, an RQ worker that extracts PDF text, MongoDB, Redis/Valkey, and
S3-compatible object storage. Production target is Render (`render.yaml`, `docs/DEPLOYMENT.md`).

## Commands

```bash
# Backend (Python 3.12; 3.11 also works)
pip install -r requirements-dev.txt
python -m app.main                 # API on $PORT (8000); reloads when APP_ENV=development
python -m app.worker               # RQ worker; uses SimpleWorker + timer timeouts on Windows
python -m pytest                   # API tests skip unless MongoDB is reachable at TEST_MONGO_URL
python -m pytest tests/test_api.py::test_documents_are_private_to_their_owner

# Frontend (Node 20.19+)
cd frontend
npm run dev                        # :5173, proxies /api, /auth, /healthz to :8000 (PAPERCHAT_BACKEND_URL)
npm run lint && npm run typecheck && npm test
npx vitest run src/api/client.test.ts
npm run build                      # → frontend/dist, which FastAPI serves

# Everything in containers (development mode, local-developer sign-in)
docker compose up --build
```

## Architecture

**Request path.** `app/server.py:create_app` builds the app; shared resources (async Mongo client/db, async Redis for
rate limits, RQ queue on a sync Redis connection, storage backend, Authlib OAuth client) are created in the lifespan
handler and read through dependencies in `app/deps.py`. `create_app` accepts `queue`, `redis` and `storage` overrides —
tests pass fakeredis, an `is_async=False` queue (jobs run inline) and `LocalStorage`.

**Middleware order (outermost first):** `BodySizeLimitMiddleware` (rejects oversized bodies before multipart spooling)
→ `SecurityMiddleware` (blocks unsafe methods whose `Origin` isn't `PUBLIC_BASE_URL`/`CORS_ORIGINS`, adds CSP/HSTS and
cache headers, JSON request logs) → Starlette `SessionMiddleware` (only OAuth state, cookie `paperchat_oauth`) →
optional CORS. The CSP is `'self'`-only: no inline scripts/styles in `index.html`, no third-party origins except Google
avatar images. Keep new frontend assets bundled.

**Auth.** Google OAuth code flow in `app/routes/auth.py`; users upserted by `(provider, provider_id)`. Login sessions are
server-side: the `paperchat_session` cookie holds a random token, Mongo `sessions` stores its SHA-256 with a TTL index.
`POST /auth/dev-login` exists only when `DEV_LOGIN_ENABLED` and not production.

**Ownership.** Every document query filters by `owner_id`; other users' documents return 404, never 403. `chunks` carry
both `file_id` and `owner_id`. Serialized documents never expose `storage_key` or `owner_id`.

**Document lifecycle.** `POST /api/documents` validates (extension/content type, `%PDF-` magic, size, per-user count,
upload rate) → inserts `files` doc `uploading` → `storage.save` → `queued` → `enqueue_processing` (job id
`process-<id>`, `on_failure` callback). Worker `process_file` (`app/queue/workers.py`) opens its own sync
`MongoClient` per job, downloads via `storage.local_copy`, extracts per-page chunks, then sets `ready` or `failed`.
`UserFacingError` messages are shown to users; anything else becomes a generic message and is logged. Documents stuck in
a pending status longer than `max(3 × WORKER_TIMEOUT_SECONDS, 30 min)` are marked failed lazily on list/get
(`fail_stalled_documents`). Timestamps: always update `updated_at`, which the stall check relies on.

**Storage.** Web and worker only share PDFs through `app/services/storage.py` (`LocalStorage` for dev, `S3Storage` for
R2/S3). Never pass filesystem paths between processes. Production validation forces `STORAGE_BACKEND=s3`.

**RAG pipeline.** All OpenAI calls live in `app/services/ai.py` and raise `AIServiceError` (never SDK exceptions).
Worker: chunks (1200 chars, 180 overlap, per page) are embedded in batches (`embed_texts`, unit-normalised float32) and
stored on each chunk as a BSON float32 vector (`embedding`); the document records `embedding_signature`
(`model:dimensions`). An embedding failure fails the document. Questions (`app/services/answering.py:answer`): if the
request has `history`, `standalone_question` rewrites it; the query is embedded; `retrieve_chunks` fuses NumPy cosine
ranking over the document's vectors with MongoDB `$text` ranking (compound index `(file_id, text)`, so queries must match
`file_id`) via reciprocal rank fusion; `generate_answer` writes a page-cited answer from numbered excerpts plus history.
Semantic retrieval is skipped when `embedding_signature` doesn't match current settings. Degradation: no key or query
embedding failure → keyword only; generation failure → `mode: "extractive"` passages; nothing retrieved →
`mode: "none"`. Tests replace `ai.embed_texts` / `standalone_question` / `generate_answer` with fakes (`tests/test_rag.py`)
and override settings via the `settings_overrides` fixture. Rate limits (`app/services/ratelimit.py`) fail closed.

**Config.** `app/config.py` is pydantic-settings; `get_settings()` is cached and validates production requirements
(https URL, 32+ char `SESSION_SECRET`, Google and OpenAI credentials, s3 storage, no dev login). Worker code calls
`get_settings()` directly, so tests monkeypatch `app.queue.workers.get_settings`.

**Frontend.** `frontend/src/api/client.ts` wraps fetch (cookies included, tolerant of non-JSON error bodies) and uses
XHR for upload progress; `VITE_API_BASE_URL` is empty for same-origin. Each question sends the last 6 completed turns
as `history` (`historyFor`). TanStack Query hooks in `api/queries.ts` poll
document status with backoff and reset `me` to `null` on any 401, which sends `RequireAuth` to `/login`. Conversations
live in `sessionStorage` per document (`lib/useConversation.ts`); the server stores no chat history. `DocumentPage`
renders `DocumentView` with `key={id}` so local state resets between documents. eslint-plugin-react-hooks v7 rules are
on — avoid `setState` inside effects.

**Serving the SPA.** `app/routes/spa.py` is registered last: it serves files from `frontend/dist` and falls back to
`index.html`, but never for `api/`, `auth/` or `assets/` prefixes (those 404 as JSON). `/assets` is mounted as
immutable static files.

## Deployment notes

- One `Dockerfile` (node build stage → python runtime) for both Render services; the worker's `dockerCommand` is
  `python -m app.worker`. The image defaults to `APP_ENV=production`.
- Render Key Value must use `maxmemoryPolicy: noeviction` so queued jobs aren't evicted.
- `docker-compose.yml` is for local full-stack testing only (development mode).
