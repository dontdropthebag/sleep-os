import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .api import DISCLAIMER, router
from .config import settings
from .db import Base, engine

logger = logging.getLogger("sleep_os")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Best-effort so local/SQLite "just works". In production the source of
    # truth is `alembic upgrade head`; a transient DB blip on a serverless
    # cold start must not permanently break the function, so we log and carry
    # on rather than crash at import time.
    if settings.create_tables_on_startup:
        try:
            Base.metadata.create_all(engine)
        except Exception as exc:  # pragma: no cover - depends on live DB
            logger.warning("Startup table creation skipped: %s", exc)
    yield


app = FastAPI(title="Sleep Intelligence OS", version=__version__, lifespan=lifespan,
              description="Local-first personal sleep analytics. " + DISCLAIMER)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_origin_regex=settings.cors_origin_regex,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok", "version": __version__}
