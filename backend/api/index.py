"""Vercel Python serverless entrypoint (OPTIONAL all-on-Vercel path).

Vercel's Python runtime serves the ASGI ``app`` exported here; ``vercel.json``
rewrites every request to this function. This lets you host the API on Vercel
instead of a persistent server.

Caveats (why a persistent host such as Render/Railway/Fly is the recommended
fit for this API):
  * Serverless functions are stateless — you MUST use a hosted Postgres
    (`DATABASE_URL`); SQLite will not persist.
  * Alembic migrations can't run per-invocation. As a fallback this entry
    best-effort-creates the schema at cold start (idempotent). For real schema
    changes still run `alembic upgrade head` against the database.

This file was added for deployment flexibility but was not exercised on a live
Vercel deployment from this environment.
"""

import logging

from app.config import settings
from app.db import Base, engine
from app.main import app  # noqa: F401 — ASGI app served by Vercel

logger = logging.getLogger("sleep_os")

if settings.create_tables_on_startup:
    try:
        Base.metadata.create_all(engine)
    except Exception as exc:  # pragma: no cover - depends on live DB
        logger.warning("Cold-start table creation skipped: %s", exc)
