# Paperchat

Paperchat is a small, self-hosted PDF question-and-answer workspace. It accepts text-based PDFs, extracts and indexes page chunks in a background worker, then returns page-linked excerpts or (optionally) a grounded OpenAI answer.

## Run locally

```bash
cp .env.example .env
docker compose -f docker-compose.prod.yml up --build
```

Open `http://localhost:8000`. MongoDB, Valkey, the API, and the extraction worker run as separate services. Uploaded PDFs live in the named `uploads` volume; MongoDB stores document metadata and extracted chunks.

Set `OPENAI_API_KEY` in `.env` to enable generated answers. Without it, the application remains usable and clearly returns the relevant indexed excerpts instead. The API is intentionally unauthenticated for single-user/self-hosted deployment; place it behind an authenticated reverse proxy before exposing it publicly.

## API

- `POST /api/documents` — multipart PDF upload (25 MB default)
- `GET /api/documents/{id}` — indexing status and metadata
- `POST /api/documents/{id}/questions` — JSON `{ "question": "..." }`
- `DELETE /api/documents/{id}` — remove document, chunks, and stored PDF
- `GET /healthz` — process health check

## Limitations

Only PDFs with selectable text are currently indexed. OCR, user accounts, conversation persistence, and semantic-vector retrieval are deliberately not claimed by this implementation.
