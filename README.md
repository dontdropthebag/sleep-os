# Sleep Intelligence OS

A **local-first personal sleep analytics and coaching system**. It ingests sleep data from
multiple sources (starting with Sleep as Android), computes transparent sleep and recovery
metrics, estimates your chronotype, recommends sleep/wake schedules, and produces a calm
morning coaching report — all on your own machine.

> **This is not a medical device.** It is educational and observational. Consumer sleep
> trackers are not polysomnography, and nothing here diagnoses insomnia, sleep apnea, or any
> other condition. See [docs/MEDICAL_LIMITATIONS.md](docs/MEDICAL_LIMITATIONS.md).

## 1. Prerequisites

- Python 3.11+ (developed on 3.14)
- Node.js 20+ (developed on 25)
- *(optional)* Docker + Docker Compose

## 2. Installation

```bash
make setup          # creates backend/.venv and installs frontend node_modules
```

Or with Docker: `docker compose up --build` (backend :8000, frontend :3000).

## 3. One-command local startup

```bash
make dev            # backend on http://localhost:8000, UI on http://localhost:3000
```

Want demo data first? `make seed` loads 35 synthetic nights (profile, sleep, HRV, habits,
check-ins) so every screen has something to show. Run it any time; `--reset` wipes first.

## 4. Uploading a Sleep as Android ZIP

1. In Sleep as Android: *Settings → Services → Export data* (or automatic backup ZIP).
2. Open **Import** in the UI → choose the ZIP (or a bare `sleep-export.csv`).
3. Review the **preview**: every detected session, its timezone, missing metrics, parse
   warnings, and likely duplicates (unticked by default).
4. Click **Save** — only then is anything written to the database. Original rows are
   preserved verbatim alongside the normalised session.

ZIPs are inspected safely (path-traversal, zip-bomb and symlink guards; size caps). A
generic CSV (`start,end,total_sleep_min,timezone,hrv_rmssd,...` with ISO-8601 timestamps)
also works. Manual entry: `POST /api/sessions` or the Nights screen.

## 5. Entering habits and check-ins

- **Habits** screen: caffeine (mg + timing), alcohol, meals, exercise, morning light,
  screens, travel, illness, bedroom environment, sleeping position — all optional, upserted
  per date.
- **Check-in** screen: morning (sleep quality, refreshed, energy, sleepiness, mood,
  soreness) plus optional midday/evening check-ins, all 1–10 sliders.

These feed sleep-need estimation, chronotype exclusion rules, and the coaching report.

## 6. How calculations work

Every formula is documented in [docs/METRICS.md](docs/METRICS.md) and surfaced in the UI
with provenance (measured / device-estimated / self-reported / system-derived) and a
confidence label. Highlights:

- **Efficiency** = total sleep ÷ time in bed × 100
- **Regularity** = circular SD of onset/wake/midpoint + social jetlag
- **Sleep need** = 7–9 h reference until 28 valid nights exist, then the median of your
  high-energy, low-sleepiness nights (excluding alcohol/illness/travel)
- **Chronotype** = debt-corrected free-day sleep midpoint (MSFsc-style), with travel,
  illness, alcohol and alarm-constrained nights excluded
- **Tonight's plan** = required wake − target sleep − median latency, shift capped at
  45 min/night

Missing data is shown as missing — never invented.

## 7. Running tests

```bash
make test           # 52 backend pytest tests + frontend vitest
make lint           # ruff + tsc --noEmit
```

## 8. Deleting all data

**Privacy** screen → type `DELETE` → *Delete all personal data* (or
`POST /api/privacy/delete-all?confirm=DELETE`). This erases sessions, raw records, physio,
habits, check-ins and profile; the deletion itself is recorded in the local audit log. You
can export everything as JSON first, or generate a clinician summary. All data lives in
`backend/data/sleep.db` on your machine — deleting that file is the nuclear option.

## 9. Known limitations

- Phase 1 + core Phase 2 are implemented. **Not yet built:** dedicated Oura/WHOOP/Health
  Connect adapters (the generic CSV adapter covers flat exports), snore **audio** analysis
  (metadata only), habit-impact statistics, N-of-1 experiments, the trained personal energy
  model, and travel-mode guidance. Stubs return honest `insufficient_data` / not-implemented
  responses rather than fake numbers.
- Sleep as Android does not export sleep latency or onset; those show as "not recorded".
  The parser has been verified against a real 2026 export (two-row records with movement +
  noise timelines, dot decimals, `Snore=0` as a true zero, `Rating=0.0` as unrated,
  DHA/LUX/TALK/DEVICE events); anonymised structural fixtures cover all of it.
- Sessions with implausible durations (> 18 h, e.g. tracking left running) stay visible in
  Nights with low confidence but are excluded from averages, debt and regularity.
- Sleep-stage data is device-estimated and low-confidence by design.
- Single-user, no authentication — intended to run on your own machine only.
- Docker configs are provided but were not verified on this machine (no Docker installed).

## Deployment

Deploy the **frontend to Vercel** (root directory `frontend/`, Next.js preset) and the
**backend to a persistent Python host with hosted Postgres** (SQLite can't persist on
serverless). Full step-by-step, environment variables and the optional all-on-Vercel path
are in **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)**. Note: the app has **no authentication**
— gate the URL before exposing health data publicly.

More docs: [DEPLOYMENT.md](docs/DEPLOYMENT.md) · [ARCHITECTURE.md](docs/ARCHITECTURE.md) ·
[METRICS.md](docs/METRICS.md) · [PRIVACY.md](docs/PRIVACY.md) ·
[MEDICAL_LIMITATIONS.md](docs/MEDICAL_LIMITATIONS.md)
