# Deploying Paperchat to Render

Production runs as two Render services built from the same `Dockerfile`, plus managed data services:

```
Browser ──HTTPS──▶ paperchat-web (FastAPI + built React app, same origin)
                     ├─▶ MongoDB Atlas            users, sessions, documents, extracted text
                     ├─▶ paperchat-redis           Render Key Value: job queue + rate limits
                     ├─▶ Cloudflare R2 / AWS S3    uploaded PDFs (private bucket)
                     └─▶ OpenAI                    question embedding + generated answer
paperchat-worker ──▶ Key Value (jobs) ──▶ R2/S3 (download PDF) ──▶ OpenAI (chunk embeddings) ──▶ Atlas (text + vectors)
```

`render.yaml` creates `paperchat-web`, `paperchat-worker` and `paperchat-redis`. Atlas, the bucket and Google OAuth are
set up by hand once, below. Pick one region for everything (the Blueprint uses `oregon`; Atlas `us-west-2` is closest).

## 1. MongoDB Atlas

1. Create a cluster. M0 (free) works for a trial; use M10 or larger for real users (backups, no shared-tier limits).
2. **Database Access** → add a user with *Read and write to any database* (or scoped to the `paperchat` database).
3. **Network Access** → allow Render's outbound IPs (Render dashboard → service → *Connect* → *Outbound*), or
   `0.0.0.0/0` if you accept relying on the password alone.
4. Copy the `mongodb+srv://…` connection string. This is `MONGO_URL`.

Indexes (including the text index used for search and TTL index for sessions) are created automatically when the
web service starts.

## 2. Object storage (Cloudflare R2 shown; S3 works the same)

1. Create a bucket, e.g. `paperchat-documents`. Leave public access **off**.
2. Create an API token with *Object Read & Write* on that bucket only.
3. Note: `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, and
   `S3_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com` with `S3_REGION=auto`.
   For AWS S3 leave `S3_ENDPOINT_URL` empty and set `S3_REGION` to the bucket's region.

## 3. Google sign-in

1. Google Cloud Console → *APIs & Services* → *OAuth consent screen*: user type **External**, app name, support email,
   and the app's home page and privacy policy URLs (`<PUBLIC_BASE_URL>/privacy`). Scopes: `openid`, `email`, `profile`.
2. Publish the consent screen (these scopes don't require Google verification).
3. *Credentials* → *Create credentials* → *OAuth client ID* → **Web application**.
   - Authorised JavaScript origin: `<PUBLIC_BASE_URL>`
   - Authorised redirect URI: `<PUBLIC_BASE_URL>/auth/google/callback`
4. Copy `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`.

`PUBLIC_BASE_URL` is the address users open: `https://paperchat-web.onrender.com` (your service's onrender.com URL),
or your custom domain once it's attached. If it changes, update it on Render **and** in the Google client.

## 4. Apply the Blueprint

1. Push this branch to GitHub and merge it to `main`.
2. Render dashboard → *New* → *Blueprint* → pick the repository. Render reads `render.yaml`.
3. Fill in the prompted values: `PUBLIC_BASE_URL`, `MONGO_URL`, the `S3_*` values, `GOOGLE_CLIENT_*` and
   `OPENAI_API_KEY`. `SESSION_SECRET` is generated for you.
4. Apply. The web service is healthy when `/healthz` responds; `/readyz` additionally checks MongoDB and Redis.

The services refuse to start in production if a required setting is missing or unsafe (http URL, short session secret,
missing Google or OpenAI credentials, local storage, developer sign-in enabled). The error is printed in the deploy log.

Deploys run automatically after GitHub Actions checks pass on `main` (`autoDeployTrigger: checksPass`).

## 5. Custom domain (optional)

Render → `paperchat-web` → *Settings* → *Custom Domains*. Then update `PUBLIC_BASE_URL` and the Google OAuth origin and
redirect URI to the new domain.

## 6. After the first deploy

- Sign in with Google, upload a PDF, ask a question, delete it.
- Sign in as a second Google account and confirm the first account's documents are not listed.
- Set a monthly usage limit in the OpenAI dashboard.
- Add an uptime check against `https://<domain>/readyz`.
- Review the privacy notice at `/privacy` (`frontend/src/pages/PrivacyPage.tsx`) and adjust it to your operation.

## Operations

| Task | How |
| --- | --- |
| Logs | Render → service → *Logs*. Web requests are JSON lines with `request_id`, `status`, `duration_ms`. |
| Scale web | Increase instances, or set `WEB_CONCURRENCY` for more uvicorn workers per instance. |
| Scale processing | Add worker instances; each processes one PDF at a time. |
| Worker out of memory | Raise `paperchat-worker` to `1c-2g`, or lower `MAX_PAGES` / `MAX_UPLOAD_MB`. Documents whose job died are marked failed automatically. |
| Rotate `SESSION_SECRET` | Only protects the short-lived OAuth state cookie; rotating it doesn't sign anyone out. |
| Sign everyone out | Delete all documents in the Atlas `sessions` collection. |
| Change embedding model or size | Set `OPENAI_EMBEDDING_MODEL` / `EMBEDDING_DIMENSIONS`. Existing documents fall back to keyword retrieval until they are re-uploaded. |
| Tune limits | `USER_MAX_DOCUMENTS`, `RATE_LIMIT_QUESTIONS_PER_MINUTE`, `RATE_LIMIT_QUESTIONS_PER_DAY`, `RATE_LIMIT_UPLOADS_PER_HOUR`. |
