"""Import staging, duplicate detection and commit logic."""

import hashlib
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from .adapters import ParsedSession, ParseResult, get_adapter
from .models import AuditLog, ImportBatch, PhysioObservation, RawRecord, SleepSession

DUP_OVERLAP_FRACTION = 0.5


def _session_date(ps: ParsedSession) -> str:
    """Nights are attributed to the local date of the final awakening."""
    wake = ps.final_wake_utc or ps.in_bed_utc
    return wake.astimezone(ZoneInfo(ps.timezone_name)).date().isoformat()


def _overlap_min(a_start, a_end, b_start, b_end) -> float:
    latest = max(a_start, b_start)
    earliest = min(a_end, b_end)
    return max(0.0, (earliest - latest).total_seconds() / 60)


def find_duplicates(db: Session, ps: ParsedSession) -> list[str]:
    """A likely duplicate overlaps >=50% of either window, or matches the
    same source-session id from the same source."""
    dupes = []
    if ps.source_session_id:
        existing = db.scalars(select(SleepSession).where(
            SleepSession.source == ps.source,
            SleepSession.source_session_id == ps.source_session_id)).all()
        dupes.extend(s.id for s in existing)
    if ps.in_bed_utc and ps.final_wake_utc:
        candidates = db.scalars(select(SleepSession).where(
            SleepSession.session_date == _session_date(ps))).all()
        for s in candidates:
            if s.id in dupes or not s.in_bed_utc or not s.final_wake_utc:
                continue
            ov = _overlap_min(_aware(s.in_bed_utc), _aware(s.final_wake_utc), ps.in_bed_utc, ps.final_wake_utc)
            mine = (ps.final_wake_utc - ps.in_bed_utc).total_seconds() / 60
            theirs = (_aware(s.final_wake_utc) - _aware(s.in_bed_utc)).total_seconds() / 60
            if mine > 0 and theirs > 0 and (ov / mine >= DUP_OVERLAP_FRACTION or ov / theirs >= DUP_OVERLAP_FRACTION):
                dupes.append(s.id)
    return dupes


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _serialize_session(ps: ParsedSession, db: Session) -> dict:
    return {
        "source": ps.source,
        "source_session_id": ps.source_session_id,
        "session_date": _session_date(ps),
        "timezone_name": ps.timezone_name,
        "in_bed_utc": ps.in_bed_utc.isoformat() if ps.in_bed_utc else None,
        "sleep_onset_utc": ps.sleep_onset_utc.isoformat() if ps.sleep_onset_utc else None,
        "final_wake_utc": ps.final_wake_utc.isoformat() if ps.final_wake_utc else None,
        "out_of_bed_utc": ps.out_of_bed_utc.isoformat() if ps.out_of_bed_utc else None,
        "time_in_bed_min": ps.time_in_bed_min,
        "total_sleep_min": ps.total_sleep_min,
        "sleep_latency_min": ps.sleep_latency_min,
        "waso_min": ps.waso_min,
        "awakenings_count": ps.awakenings_count,
        "stage_intervals": ps.stage_intervals,
        "is_nap": ps.is_nap,
        "user_rating": ps.user_rating,
        "comments": ps.comments,
        "tags": ps.tags,
        "snore_minutes": ps.snore_minutes,
        "noise_level": ps.noise_level,
        "cycles": ps.cycles,
        "deep_sleep_fraction": ps.deep_sleep_fraction,
        "movement_timeline": ps.movement_timeline,
        "noise_timeline": ps.noise_timeline,
        "event_timeline": ps.event_timeline,
        "field_provenance": ps.field_provenance,
        "missing_metrics": ps.missing_metrics,
        "raw_payload": ps.raw_payload,
        "physio": ps.physio,
        "likely_duplicate_of": find_duplicates(db, ps),
    }


def stage_import(db: Session, filename: str, data: bytes, source_hint: str | None) -> dict:
    adapter = get_adapter(filename, data, source_hint)
    result: ParseResult = adapter.parse(filename, data)
    sessions = [_serialize_session(ps, db) for ps in result.sessions]
    batch = ImportBatch(
        source=result.source,
        filename=filename,
        file_sha256=hashlib.sha256(data).hexdigest(),
        parser_version=result.parser_version,
        staged_payload={
            "sessions": sessions,
            "issues": [vars(i) for i in result.issues],
            "extras": {k: v for k, v in result.extras.items() if k != "noise_json"},
        },
    )
    db.add(batch)
    db.add(AuditLog(action="import_staged", detail={
        "filename": filename, "source": result.source, "sessions": len(sessions),
        "sha256": batch.file_sha256}))
    db.commit()
    return {
        "batch_id": batch.id,
        "source": result.source,
        "parser_version": result.parser_version,
        "sessions": sessions,
        "issues": [vars(i) for i in result.issues],
        "extras": batch.staged_payload["extras"],
    }


def commit_import(db: Session, batch_id: str, include_indices: list[int] | None,
                  overrides: dict[int, dict] | None = None) -> dict:
    batch = db.get(ImportBatch, batch_id)
    if batch is None or batch.status != "staged":
        raise ValueError("Batch not found or already committed/discarded")
    payload = batch.staged_payload or {"sessions": []}
    created, skipped = [], []
    for i, s in enumerate(payload["sessions"]):
        if include_indices is not None and i not in include_indices:
            skipped.append({"index": i, "reason": "excluded_by_user"})
            continue
        if s.get("likely_duplicate_of") and (include_indices is None or i not in include_indices):
            skipped.append({"index": i, "reason": "likely_duplicate"})
            continue
        s = dict(s)
        # Manual corrections from the preview screen
        if overrides and i in overrides:
            s.update({k: v for k, v in overrides[i].items() if k in s})
            s["manually_edited"] = True
        raw = RawRecord(batch_id=batch.id, source=s["source"], record_kind="sleep",
                        payload=s.pop("raw_payload", {}))
        db.add(raw)
        db.flush()
        physio = s.pop("physio", []) or []
        s.pop("likely_duplicate_of", None)
        missing = s.pop("missing_metrics", None)
        sess = SleepSession(
            batch_id=batch.id, raw_record_id=raw.id, parser_version=batch.parser_version,
            manually_edited=s.pop("manually_edited", False),
            **{k: (_parse_dt(v) if k.endswith("_utc") else v) for k, v in s.items()},
        )
        if missing:
            prov = dict(sess.field_provenance or {})
            prov["_missing_metrics"] = missing
            sess.field_provenance = prov
        db.add(sess)
        db.flush()
        for p in physio:
            db.add(PhysioObservation(
                session_id=sess.id, date=sess.session_date, batch_id=batch.id,
                source=sess.source, **p))
        created.append(sess.id)
    batch.status = "committed"
    db.add(AuditLog(action="import_committed", detail={
        "batch_id": batch.id, "created": len(created), "skipped": skipped}))
    db.commit()
    return {"created_session_ids": created, "skipped": skipped}


def _parse_dt(v):
    return datetime.fromisoformat(v) if isinstance(v, str) else v
