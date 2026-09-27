# Deploying Paperchat to Render

The blueprint deploys **one web service** that also runs the document worker, plus a Key Value instance for the job
queue. MongoDB, file storage, Google sign-in and the AI provider are external accounts you create once.

```
Browser ──HTTPS──▶ paperchat-web (FastAPI + React + document worker in the same process)
                     ├─▶ MongoDB Atlas          users, sessions, documents, text, vectors
                     ├─▶ paperchat-redis        Render Key Value: job queue + rate limits
                     ├─▶ Supabase / R2 / S3     the uploaded PDFs
                     └─▶ Gemini or OpenAI       embeddings + answers
```

Everything below fits free tiers. The two things to know about free on Render:

- the web service **sleeps after 15 minutes** without traffic, and the next visit takes ~40 seconds to wake it;
- the Key Value instance **does not save to disk**, so a restart loses queued jobs. A document caught mid-queue is
  marked failed by the stalled-job check and can be uploaded again.

To remove both limits later, give the service a paid plan and split the worker out again — the commented-out worker
in [render.yaml](../render.yaml) is ready for that.

## 1. MongoDB Atlas (free, no card)

1. Sign up at [mongodb.com/atlas](https://www.mongodb.com/atlas), create a **free M0 cluster**.
2. **Database Access** → add a user with a password, with *Read and write to any database*.
3. **Network Access** → add `0.0.0.0/0`. Render's outbound IPs are not fixed on the free plan, so access is
   protected by the password alone. Use a long random one.
4. **Connect** → *Drivers* → copy the `mongodb+srv://…` string and put your password into it. That is `MONGO_URL`.

## 2. Supabase Storage (free, no card)

1. Sign up at [supabase.com](https://supabase.com) and create a project. Note its **region**.
2. **Storage** → *New bucket* → name it `paperchat`, leave it **private**.
3. **Project Settings** → *Storage* → *S3 connection*: copy the **endpoint** and **region**, then
   *New access key* to get the key id and secret.
4. That gives you `S3_BUCKET=paperchat`, `S3_ENDPOINT_URL` (like
   `https://<ref>.storage.supabase.co/storage/v1/s3`), `S3_REGION`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`.

Cloudflare R2 or AWS S3 work the same way; only the endpoint and region differ.

## 3. Gemini API key (free)

[aistudio.google.com/apikey](https://aistudio.google.com/apikey) → *Create API key*. That is `AI_API_KEY`.
On the free tier Google may use prompts to improve its products — fine for a demo, not for other people's private
documents. Switch to a paid tier or OpenAI before that matters.

## 4. Deploy on Render

1. Sign up at [render.com](https://render.com) with GitHub and allow access to the repository.
2. **New** → **Blueprint** → pick `ProjectPDF` → Render reads `render.yaml`.
3. It asks for the `sync: false` values. Fill in everything except the two Google ones, which need the URL that does
   not exist yet:
   - `PUBLIC_BASE_URL` → `https://paperchat-web.onrender.com` (correct it in step 6 if Render picks another name)
   - `MONGO_URL`, the five `S3_*` values, `AI_API_KEY`
   - `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` → put `placeholder` in both for now
4. Apply. The first build takes a few minutes. It will deploy but **refuse to serve**, because the Google
   credentials are placeholders — that is expected and the log says so.
5. Copy the service URL from the top of the Render page.

## 5. Google sign-in

1. [console.cloud.google.com](https://console.cloud.google.com) → create a project.
2. **APIs & Services** → **OAuth consent screen**: *External*, app name, your email for support and developer
   contact. Add the app home page (`<URL>/`) and privacy policy (`<URL>/privacy`). Scopes: `openid`, `email`,
   `profile` — no Google review needed for these.
3. Publish the consent screen. While it is in *Testing*, only accounts you list under *Test users* can sign in.
4. **Credentials** → *Create credentials* → *OAuth client ID* → **Web application**:
   - Authorised JavaScript origin: `https://<your-service>.onrender.com`
   - Authorised redirect URI: `https://<your-service>.onrender.com/auth/google/callback`
5. Copy the client ID and secret.

## 6. Finish the deploy

In Render → your service → **Environment**, replace `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` and (if the URL
differs) `PUBLIC_BASE_URL`. Save — Render redeploys automatically.

The service is healthy when `/healthz` answers. `/readyz` additionally checks MongoDB and Redis.

The app refuses to start in production if a setting is missing or unsafe: an `http://` URL, a short session secret,
missing Google or AI credentials, local file storage, or the developer sign-in left on. The deploy log names the
problem.

## 7. Check it works

1. Open the URL, sign in with Google.
2. Upload a PDF, wait for the summary, ask a question, try Search.
3. Sign in with a second Google account and confirm the first account's documents are not listed.
4. Set a spending limit with your AI provider.
5. Read `/privacy` and adjust it to how you actually run the service.

## If something fails

| Symptom | Cause |
| --- | --- |
| Deploy log: `AI_API_KEY is required in production` (or similar) | A `sync: false` value is still missing; the message names it |
| `redirect_uri_mismatch` on sign-in | The redirect URI in Google must match `PUBLIC_BASE_URL` + `/auth/google/callback` exactly, including `https` |
| Documents stay "Queued" | `RUN_WORKER_IN_WEB` is not `true`, or the Key Value instance is unreachable |
| Upload fails with "couldn't store your PDF" | Wrong bucket name, endpoint or region, or the access key lacks write permission |
| First visit takes ~40s | The free instance was asleep. Expected |
| Processing fails on a big PDF | 512 MB is tight while indexing: lower `MAX_PAGES` / `MAX_UPLOAD_MB`, or move to a paid plan |

## Operations

| Task | How |
| --- | --- |
| Logs | Render → service → *Logs*. Requests are JSON lines with `request_id`, `status`, `duration_ms` |
| Stay awake / faster | Upgrade the service plan; then split the worker out (uncomment it in `render.yaml`, set `RUN_WORKER_IN_WEB=false`) |
| Sign everyone out | Delete every document in the Atlas `sessions` collection |
| Change AI provider or embedding model | `AI_BASE_URL`, `AI_CHAT_MODEL`, `AI_EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS`. Documents embedded with a different model fall back to keyword search until re-uploaded |
| Tune limits | `USER_MAX_DOCUMENTS`, `RATE_LIMIT_QUESTIONS_PER_MINUTE`, `RATE_LIMIT_QUESTIONS_PER_DAY`, `RATE_LIMIT_UPLOADS_PER_HOUR` |
