# Privacy

Sleep and bedroom-audio data are among the most sensitive personal data. This project's
posture:

## Where data lives

- Everything is processed and stored **locally** in `backend/data/sleep.db` (SQLite).
- No cloud services, no telemetry, no advertising trackers, no analytics SDKs.
- Health data is never sold or shared. There is nothing in the code that could.

## Audio

- Sleep audio is analysed **locally**; raw audio is **discarded after analysis** unless
  `SIOS_RETAIN_RAW_AUDIO=true` is set explicitly.
- Bedroom speech is **never transcribed**. The (Phase 3) classifier is limited to
  snore / cough / movement / environmental categories, and flags "possible speech" only to
  *exclude* it from analysis.
- Audio is never uploaded to any external AI service. Adding any such integration would
  require explicit, informed opt-in.

## Controls

- **Export all data:** Privacy screen → JSON download (or `GET /api/privacy/export`).
- **Delete all data:** Privacy screen, type `DELETE` (or
  `POST /api/privacy/delete-all?confirm=DELETE`). Deletion is complete and audited.
- **Clinician export:** a concise, diagnosis-free summary for a medical appointment.
- **Audit log:** every import, edit, export and deletion recorded locally.

## Technical safeguards

- Safe ZIP handling: path-traversal rejection, symlink rejection, per-entry and total
  decompressed-size caps, compression-ratio (zip-bomb) checks, entry-count limits, streaming
  read caps; archives are never extracted to disk.
- Upload size limits and content sniffing before parsing.
- All database access through the ORM with bound parameters — no raw SQL.
- Input validation with Pydantic on every write endpoint.
- CORS restricted to the local frontend origin.
- Secrets/config via environment variables only (`.env.example`); nothing hard-coded.
- If cloud sync is ever added it must ship with authentication, encryption in transit and
  at rest, and remain opt-in. Encryption at rest for the local DB is on the roadmap
  (SQLCipher); until then, full-disk encryption (FileVault) is recommended.
