from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


def normalize_db_url(url: str) -> str:
    """Accept the DB URLs hosting providers hand out and route them to the
    driver we ship.

    Vercel Postgres / Supabase / Neon / Railway commonly emit ``postgres://``
    or ``postgresql://`` URLs. SQLAlchemy needs an explicit driver, and we
    bundle psycopg (v3), so map those to ``postgresql+psycopg://``. SQLite and
    already-qualified URLs are left untouched.
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def _make_engine(url: str | None = None):
    url = normalize_db_url(url or settings.database_url)
    if url.startswith("sqlite"):
        db_path = url.split("///", 1)[-1]
        if db_path and db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        return create_engine(url, connect_args={"check_same_thread": False})
    # Server databases (Postgres): pre-ping so connections recycled by the
    # provider or dropped between serverless invocations don't surface as
    # errors on the next request.
    return create_engine(url, pool_pre_ping=True)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
