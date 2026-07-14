# Architecture

## Overview

```
┌─────────────────────┐         ┌──────────────────────────────────┐
│  Next.js frontend   │  HTTP   │  FastAPI backend                 │
│  (TypeScript,       │ ──────▶ │  ┌────────────┐  ┌────────────┐  │
│   Tailwind,         │  JSON   │  │ adapters/  │  │ analytics/ │  │
│   Recharts)         │         │  │ (plugins)  │  │ (pure fns) │  │
└─────────────────────┘         │  └─────┬──────┘  └─────▲──────┘  │
                                │        ▼               │         │
                                │  ┌──────────────────────────┐    │
                                │  │ SQLAlchemy ORM + Alembic │    │
                                │  └────────────┬─────────────┘    │
                                └───────────────┼──────────────────┘
                                                ▼
                                      SQLite (backend/data/sleep.db)
```

Local-first: everything runs on the user's machine. No external services, no paid APIs.

## Backend layout

| Path | Responsibility |
|---|---|
| `app/config.py` | Pydantic settings; all limits/URLs via `SIOS_*` env vars |
| `app/db.py` | Engine/session factory; SQLite now, PostgreSQL later by changing `SIOS_DATABASE_URL` |
| `app/models.py` | Canonical entities (profile, import batches, raw records, sessions, physio, snore, habits, check-ins, audit log) |
| `app/provenance.py` | Measurement-kind / confidence vocabulary attached to every metric |
| `app/security/safe_zip.py` | ZIP guards: traversal, bombs, symlinks, size caps, in-memory only |
| `app/adapters/` | Plugin importers (`register` + `sniff` + `parse`); emit canonical `ParsedSession`s |
| `app/analytics/` | Pure, unit-tested functions: metrics, regularity, sleep debt, baselines, chronotype, quality, recommendations, coaching |
| `app/services.py` | Import staging → preview → commit, duplicate detection |
| `app/api.py` | HTTP layer; ORM-only (parameterised) queries |
| `alembic/` | Migrations (`alembic upgrade head`) |
| `seed.py` | Synthetic demo data |

## Key design decisions

1. **Adapters are plugins.** A new device = one new file subclassing `BaseAdapter`. The
   analytics engine only sees canonical `ParsedSession` objects. Sniffing picks the adapter
   automatically; a `source_hint` can force one.
2. **Preview-then-commit imports.** Parsing stages the payload on the `ImportBatch` row;
   nothing touches `sleep_sessions` until the user commits. Duplicates (same source id, or
   ≥50 % window overlap) are flagged in the preview and skipped unless explicitly included.
3. **Raw records preserved.** Original rows are stored verbatim in `raw_records` before any
   normalisation, so parser upgrades can re-run against originals.
4. **Provenance everywhere.** Each canonical field carries `{original_field, unit, kind,
   confidence}`; each physio observation carries `source` + `method`. Baselines group by
   (source, method) and never blend incompatible methods.
5. **UTC + timezone name.** All instants stored as UTC; the session's IANA timezone
   reproduces local wall-clock. This makes DST and timezone travel correct by construction
   (tested).
6. **Night attribution:** a session belongs to the local date of its final awakening.
   Naps (< 3 h, starting 09:00–19:59 local) are separate and excluded from nightly stats.
7. **Insufficient-data as a first-class state.** Every analytic returns
   `status: insufficient_data` with the threshold rather than a guess.
8. **PostgreSQL path:** swap `SIOS_DATABASE_URL`; Alembic migrations use `render_as_batch`
   for SQLite compatibility but are portable.

## Frontend layout

Next.js App Router, client components fetching JSON from the API
(`NEXT_PUBLIC_API_URL`). Screens: Today (coaching), Nights (+detail), Weekly, Trends,
Chronotype, HRV & Recovery, Snoring, Habits, Check-in, Import, Settings, Privacy.
Shared UI in `src/components/ui.tsx` (cards, stat tiles, confidence/kind badges,
disclaimer). Charts are Recharts with `role="img"` + text summaries for accessibility.

## Phase 3 seams (not yet implemented)

- **Audio pipeline:** `SnoreObservation` model and FFmpeg-based analysis slot behind the
  import centre; raw audio discarded unless `SIOS_RETAIN_RAW_AUDIO=true`.
- **Habit impact / experiments / personal model:** analytics modules will follow the same
  pure-function pattern with time-aware splits; API stubs already return honest
  insufficient-data states.
