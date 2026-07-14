from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """App settings. All values overridable via environment / .env file.

    Most vars use the ``SIOS_`` prefix, but ``database_url`` and
    ``cors_origins`` also accept the unprefixed names that hosting providers
    inject (``DATABASE_URL``, ``CORS_ORIGINS``) so a Vercel Postgres / Render /
    Railway / Supabase integration works with zero extra wiring.
    """

    database_url: str = Field(
        default=f"sqlite:///{BASE_DIR / 'data' / 'sleep.db'}",
        validation_alias=AliasChoices("SIOS_DATABASE_URL", "DATABASE_URL", "POSTGRES_URL"),
    )
    # Comma-separated allowed browser origins (your deployed frontend URL in prod).
    cors_origins: str = Field(
        default="http://localhost:3000",
        validation_alias=AliasChoices("SIOS_CORS_ORIGINS", "CORS_ORIGINS"),
    )
    # Optional regex for dynamic origins, e.g. Vercel preview URLs:
    # SIOS_CORS_ORIGIN_REGEX=https://.*\.vercel\.app
    cors_origin_regex: str | None = None
    # Best-effort table creation on startup (handy for SQLite/dev). In
    # production the source of truth is `alembic upgrade head`; set false to
    # skip startup creation entirely.
    create_tables_on_startup: bool = True
    # Upload safety limits
    max_upload_bytes: int = 200 * 1024 * 1024  # 200 MB upload cap
    max_zip_entry_bytes: int = 100 * 1024 * 1024  # per-entry decompressed cap
    max_zip_total_bytes: int = 500 * 1024 * 1024  # total decompressed cap
    max_zip_entries: int = 2000
    max_zip_compression_ratio: float = 200.0  # zip-bomb guard
    # Audio: analyse locally, discard raw audio unless the user opts in
    retain_raw_audio: bool = False

    model_config = {"env_file": ".env", "env_prefix": "SIOS_", "extra": "ignore"}


settings = Settings()
