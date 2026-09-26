# Paperchat

Paperchat is a retrieval-augmented generation (RAG) app for PDFs. Sign in with Google, upload a text-based PDF, and
get three things:

- **Summary** — an overview and key points with page references, generated automatically after upload (one pass for
  documents that fit the model's context, hierarchical map-reduce for longer ones) and regenerable on demand.
- **Search** — type a phrase and get the passages that match by meaning as well as by wording, with page numbers and
  highlighted terms. No model call at answer time, so it is instant and costs nothing.
- **Chat** — ask questions and get an answer citing the pages it used; follow-ups are rewritten using the conversation
  so references like "the second one" resolve correctly.

Retrieval puts semantic vector search first and backfills with MongoDB keyword search, a choice measured rather than
assumed — see **[eval/README.md](eval/README.md)**, which scores retrieval on a fixed question set (hit@k, MRR, nDCG)
and records why rank fusion and cross-encoder reranking are *not* used when embeddings are available. Any OpenAI-compatible provider works: Google
Gemini (free tier) is configured by default, OpenAI by changing a few variables.

- **Frontend:** React + TypeScript + Vite (`frontend/`), built into the same Docker image and served by the API.
- **API:** FastAPI (`app/`) with Google sign-in, server-side sessions, per-user documents and rate limits.
- **Worker:** RQ worker that downloads each PDF from storage, extracts and chunks text with pdfplumber, embeds the
  chunks with the AI provider and stores text + vectors in MongoDB.
- **Data:** MongoDB (users, sessions, documents, text), Redis/Valkey (queue, rate limits), S3-compatible storage (PDFs).

Production deployment on Render: **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)**.

## Run locally

### Option A — everything in Docker

```bash
docker compose up --build
```

Open http://localhost:8000 and choose **Continue as local developer**. Uploaded PDFs are kept in a Docker volume.

### Option B — hot reload

Requires Python 3.12, Node 22 (20.19+ works), and MongoDB and Redis/Valkey reachable on localhost (local installs, or
open the repository in the dev container, which provides both).

```bash
cp .env.example .env         # then set AI_API_KEY (free Gemini key: https://aistudio.google.com/apikey)
pip install -r requirements-dev.txt
python -m app.main          # API on :8000 (auto-reloads)
python -m app.worker        # document worker, in a second terminal
cd frontend && npm ci && npm run dev   # UI on http://localhost:5173, proxies /api and /auth to :8000
```

To try Google sign-in locally, create an OAuth client with redirect URI `http://localhost:5173/auth/google/callback`,
set `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` in `.env`, and keep `PUBLIC_BASE_URL=http://localhost:5173`.

## Tests

```bash
python -m pytest                       # API tests need MongoDB at TEST_MONGO_URL (default mongodb://localhost:27017)
cd frontend && npm run lint && npm run typecheck && npm test
```

## Measuring retrieval

```bash
python -m eval.runner                  # compares keyword / vector / fusion / reranked retrieval
python -m eval.runner --configs keyword    # works without an AI provider
```

Results and method: **[eval/README.md](eval/README.md)**.

## API

All `/api` routes except `/api/config` require a signed-in session cookie. Documents are only visible to their owner.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/config` | Public limits and which sign-in methods are enabled |
| GET / DELETE | `/api/me` | Current user / delete account and all data |
| GET | `/api/documents` | List your documents |
| POST | `/api/documents` | Upload a PDF (multipart `file`), returns 202 and processes in the background |
| GET | `/api/documents/{id}` | Status and metadata |
| GET | `/api/documents/{id}/search` | `?q=...&limit=10` → ranked passages with page numbers, no answer generated |
| POST | `/api/documents/{id}/summary` | Regenerate the summary → `{ summary, key_points }` |
| POST | `/api/documents/{id}/questions` | `{ "question": "...", "history": [{ "role", "content" }] }` → answer, sources, mode (`llm`, `extractive` fallback, `none`) |
| DELETE | `/api/documents/{id}` | Delete PDF, extracted text and metadata |
| GET | `/auth/google/login`, `/auth/google/callback` | Google sign-in |
| POST | `/auth/logout` | Sign out |
| GET | `/healthz`, `/readyz` | Liveness / MongoDB + Redis readiness |

## Limitations

- Only PDFs with selectable text are indexed; scanned PDFs need OCR first.
- Vectors are scored in the API process with NumPy, per document, which is fast up to the page limit. For search across
  many documents at once, move to Atlas Vector Search (vectors are already stored as BSON float32).
- The evaluation set (51 questions over 39 synthetic pages) was written alongside the system it tests. It is a
  regression check and a way to compare retrieval configurations, not evidence about PDFs in general.
- Keyword retrieval (MongoDB text search, English stemming) doesn't segment Chinese, Japanese or Korean text; semantic
  retrieval still works for those languages.
- Conversations are kept in the browser tab, not stored on the server.
