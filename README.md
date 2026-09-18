# Paperchat

Paperchat is a retrieval-augmented generation (RAG) app: people sign in with Google, upload text-based PDFs and ask
questions. Each PDF is split into passages and embedded; each question retrieves the most relevant passages (semantic
vector search fused with keyword search) and an LLM writes an answer citing the pages it used. Any OpenAI-compatible
provider works: Google Gemini (free tier) is configured by default, OpenAI by changing a few variables.
Follow-up questions are rewritten using the conversation so references like "the second one" resolve correctly.

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

## API

All `/api` routes except `/api/config` require a signed-in session cookie. Documents are only visible to their owner.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/config` | Public limits and which sign-in methods are enabled |
| GET / DELETE | `/api/me` | Current user / delete account and all data |
| GET | `/api/documents` | List your documents |
| POST | `/api/documents` | Upload a PDF (multipart `file`), returns 202 and processes in the background |
| GET | `/api/documents/{id}` | Status and metadata |
| POST | `/api/documents/{id}/questions` | `{ "question": "...", "history": [{ "role", "content" }] }` → answer, sources, mode (`llm`, `extractive` fallback, `none`) |
| DELETE | `/api/documents/{id}` | Delete PDF, extracted text and metadata |
| GET | `/auth/google/login`, `/auth/google/callback` | Google sign-in |
| POST | `/auth/logout` | Sign out |
| GET | `/healthz`, `/readyz` | Liveness / MongoDB + Redis readiness |

## Limitations

- Only PDFs with selectable text are indexed; scanned PDFs need OCR first.
- Vectors are scored in the API process with NumPy, per document, which is fast up to the page limit. For search across
  many documents at once, move to Atlas Vector Search (vectors are already stored as BSON float32).
- Keyword retrieval (MongoDB text search, English stemming) doesn't segment Chinese, Japanese or Korean text; semantic
  retrieval still works for those languages.
- Conversations are kept in the browser tab, not stored on the server.
