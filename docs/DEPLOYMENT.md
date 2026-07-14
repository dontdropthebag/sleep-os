# Deployment

This is a **two-part app**: a Next.js frontend and a FastAPI backend. They
deploy as **two separate projects**. The frontend is a native Vercel fit; the
backend needs a hosted Postgres (SQLite cannot persist on serverless).

```
┌────────────────────────┐        HTTPS         ┌───────────────────────────┐
│ Next.js frontend       │  ───────────────────▶│ FastAPI backend           │
│ (Vercel)               │  NEXT_PUBLIC_API_URL  │ (Render/Railway/Fly, or   │
│                        │                       │  Vercel Python) + Postgres│
└────────────────────────┘                       └───────────────────────────┘
```

## A. Frontend → Vercel (recommended, native)

1. New Vercel Project → import the repo.
2. **Root Directory:** `frontend`
3. Framework preset **Next.js**, install/build/output all **automatic**.
4. Environment variable:
   - `NEXT_PUBLIC_API_URL` = your deployed backend URL (e.g. `https://sleep-api.onrender.com`). Public, required.
5. Deploy. Then set the backend's `SIOS_CORS_ORIGINS` to this Vercel URL.

`NEXT_PUBLIC_*` is baked into the browser bundle at build time — it is a base
URL, never a secret. Rebuild after changing it.

## B. Backend → persistent host (recommended fit) + Postgres

A migration-driven, stateful API fits a persistent host better than
serverless. Example (Render):

1. Create a **PostgreSQL** instance; copy its connection URL.
2. New **Web Service** → Root Directory `backend`.
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
     (a `Procfile` with `release: alembic upgrade head` is included).
3. Environment variables (see table in README).
4. Run migrations once: `alembic upgrade head` (the `release` phase does this
   automatically on Render/Railway/Heroku-style hosts).

`postgres://` / `postgresql://` URLs are auto-normalized to the bundled
psycopg driver — paste the provider's URL as-is.

## C. Backend → Vercel Python (optional, all-on-Vercel)

Provided but **not exercised on a live Vercel deploy from this repo**:

- `backend/api/index.py` exports the ASGI `app`; `backend/vercel.json`
  rewrites all routes to it.
- Second Vercel project, Root Directory `backend`.
- Requires a hosted Postgres via `DATABASE_URL` (Vercel Postgres integration
  injects this automatically).
- Migrations can't run per-invocation; the cold-start path best-effort-creates
  the schema (idempotent). Still run `alembic upgrade head` for real schema
  changes.

## Security notes for a public deployment

- **No authentication exists** — this was built single-user/local-first. A
  public URL means anyone with the link can read/write the data. Before
  sharing, put it behind access control (Vercel password protection / an auth
  proxy) or keep the URL private. See PRIVACY.md.
- No secrets are committed; all config is via environment variables.
- Uploads are processed in memory and never written to disk; raw audio is
  discarded. Nothing sensitive is logged.
