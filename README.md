# Paperchat

Paperchat lets people sign in with Google, upload text-based PDFs and ask questions about them. Answers cite the pages
they come from. Without an OpenAI key it returns the most relevant passages instead of generated answers.

- **Frontend:** React + TypeScript + Vite (`frontend/`), built into the same Docker image and served by the API.
- **API:** FastAPI (`app/`) with Google sign-in, server-side sessions, per-user documents and rate limits.
- **Worker:** RQ worker that downloads each PDF from storage, extracts text with pdfplumber and indexes it in MongoDB.
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
cp .env.example .env
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
| POST | `/api/documents/{id}/questions` | `{ "question": "..." }` → answer, sources, mode |
| DELETE | `/api/documents/{id}` | Delete PDF, extracted text and metadata |
| GET | `/auth/google/login`, `/auth/google/callback` | Google sign-in |
| POST | `/auth/logout` | Sign out |
| GET | `/healthz`, `/readyz` | Liveness / MongoDB + Redis readiness |

## Limitations

- Only PDFs with selectable text are indexed; scanned PDFs need OCR first.
- Retrieval uses MongoDB full-text search (English stemming), not semantic vectors. It works for questions that share
  words with the document and does not segment Chinese, Japanese or Korean text.
- Conversations are kept in the browser tab, not stored on the server.
