"""HTTP API. All queries go through the ORM (parameterised); no raw SQL."""

import statistics
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from . import services
from .analytics import baselines, chronotype, coaching, metrics, quality, recommend, regularity, sleep_debt
from .config import settings
from .db import get_db
from .models import (AuditLog, CheckIn, HabitObservation, ImportBatch, PhysioObservation,
                     RawRecord, SleepSession, SnoreObservation, UserProfile)
from .schemas import CheckInIn, CommitIn, HabitIn, ManualSessionIn, ProfileIn, SessionPatch

router = APIRouter(prefix="/api")

DISCLAIMER = ("Educational and observational only. Consumer sleep trackers are not "
              "polysomnography; estimates can be inaccurate. This app does not diagnose "
              "any medical condition. Discuss persistent symptoms with a qualified clinician.")


# ---------------------------------------------------------------- helpers
def _profile(db: Session) -> UserProfile:
    p = db.get(UserProfile, 1)
    if p is None:
        p = UserProfile(id=1)
        db.add(p)
        db.commit()
    return p


MAX_PLAUSIBLE_MIN = 18 * 60


def _plausible(s: SleepSession) -> bool:
    """Implausible sessions (e.g. tracking left running for 30+ h) stay
    visible in the nights list with their low-confidence flag, but are
    excluded from aggregate metrics so one bad record cannot distort
    averages, debt or regularity."""
    if s.time_in_bed_min is not None and s.time_in_bed_min > MAX_PLAUSIBLE_MIN:
        return False
    if s.total_sleep_min is not None and s.total_sleep_min > MAX_PLAUSIBLE_MIN:
        return False
    return True


def _sessions(db: Session, limit_days: int | None = None,
              aggregates_only: bool = False) -> list[SleepSession]:
    q = select(SleepSession).order_by(SleepSession.session_date)
    rows = list(db.scalars(q).all())
    for s in rows:  # SQLite returns naive datetimes; restore UTC awareness
        for f in ("in_bed_utc", "sleep_onset_utc", "final_wake_utc", "out_of_bed_utc"):
            v = getattr(s, f)
            if v is not None and v.tzinfo is None:
                setattr(s, f, v.replace(tzinfo=timezone.utc))
    if aggregates_only:
        rows = [s for s in rows if _plausible(s)]
    if limit_days:
        dates = sorted({s.session_date for s in rows})[-limit_days:]
        rows = [s for s in rows if s.session_date in set(dates)]
    return rows


def _habits_by_date(db: Session) -> dict:
    return {h.date: h for h in db.scalars(select(HabitObservation)).all()}


def _checkins_by_date(db: Session, kind: str = "morning") -> dict:
    return {c.date: c for c in db.scalars(select(CheckIn).where(CheckIn.kind == kind)).all()}


def _workdays(p: UserProfile) -> set[str]:
    return set(p.workdays or ["mon", "tue", "wed", "thu", "fri"])


def _session_dict(s: SleepSession, include_detail: bool = False) -> dict:
    d = {
        "id": s.id, "session_date": s.session_date, "source": s.source,
        "timezone_name": s.timezone_name, "is_nap": s.is_nap,
        "in_bed_utc": s.in_bed_utc.isoformat() if s.in_bed_utc else None,
        "final_wake_utc": s.final_wake_utc.isoformat() if s.final_wake_utc else None,
        "time_in_bed_min": s.time_in_bed_min, "total_sleep_min": s.total_sleep_min,
        "sleep_latency_min": s.sleep_latency_min, "waso_min": s.waso_min,
        "awakenings_count": s.awakenings_count, "user_rating": s.user_rating,
        "snore_minutes": s.snore_minutes, "cycles": s.cycles,
        "deep_sleep_fraction": s.deep_sleep_fraction,
        "efficiency_pct": metrics.sleep_efficiency(s.total_sleep_min, s.time_in_bed_min),
        "data_quality_score": s.data_quality_score,
        "confidence": quality.confidence_label(s.data_quality_score),
        "manually_edited": s.manually_edited,
        "tags": s.tags, "comments": s.comments,
        "excluded_reasons": s.excluded_reasons,
    }
    if include_detail:
        d.update({
            "stage_intervals": s.stage_intervals,
            "stage_summary": metrics.stage_summary(s.stage_intervals, s.total_sleep_min),
            "continuity": metrics.continuity(s),
            "movement_timeline": s.movement_timeline,
            "noise_timeline": s.noise_timeline,
            "event_timeline": s.event_timeline,
            "field_provenance": s.field_provenance,
            "quality_breakdown": s.quality_breakdown,
        })
    return d


def _score_and_store(db: Session, s: SleepSession) -> None:
    physio = {p.metric for p in db.scalars(
        select(PhysioObservation).where(PhysioObservation.session_id == s.id)).all()}
    score, breakdown = quality.score_session(s, physio)
    s.data_quality_score, s.quality_breakdown = score, breakdown


# ---------------------------------------------------------------- profile
@router.get("/profile")
def get_profile(db: Session = Depends(get_db)):
    p = _profile(db)
    return {c.name: getattr(p, c.name) for c in UserProfile.__table__.columns}


@router.put("/profile")
def put_profile(body: ProfileIn, db: Session = Depends(get_db)):
    p = _profile(db)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    db.add(AuditLog(action="profile_edit", detail=body.model_dump(exclude_unset=True)))
    db.commit()
    return get_profile(db)


# ---------------------------------------------------------------- imports
@router.post("/imports/preview")
async def import_preview(file: UploadFile = File(...), source_hint: str | None = Form(default=None),
                         db: Session = Depends(get_db)):
    data = await file.read()
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(413, "File exceeds upload size limit")
    if not data:
        raise HTTPException(400, "Empty file")
    try:
        return services.stage_import(db, file.filename or "upload", data, source_hint)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.post("/imports/{batch_id}/commit")
def import_commit(batch_id: str, body: CommitIn, db: Session = Depends(get_db)):
    try:
        result = services.commit_import(db, batch_id, body.include_indices, body.overrides)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    for sid in result["created_session_ids"]:
        s = db.get(SleepSession, sid)
        _score_and_store(db, s)
    db.commit()
    return result


@router.get("/imports")
def list_imports(db: Session = Depends(get_db)):
    rows = db.scalars(select(ImportBatch).order_by(ImportBatch.imported_at.desc())).all()

    def _utc_iso(dt):
        if dt is None:
            return None
        return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).isoformat()

    return [{"id": b.id, "source": b.source, "filename": b.filename, "status": b.status,
             "imported_at": _utc_iso(b.imported_at),
             "parser_version": b.parser_version,
             "sessions_staged": len((b.staged_payload or {}).get("sessions", []))} for b in rows]


# ---------------------------------------------------------------- sessions
@router.get("/sessions")
def list_sessions(days: int = 60, include_naps: bool = True, db: Session = Depends(get_db)):
    rows = _sessions(db, days)
    if not include_naps:
        rows = [s for s in rows if not s.is_nap]
    return [_session_dict(s) for s in rows]


@router.get("/sessions/{session_id}")
def get_session(session_id: str, db: Session = Depends(get_db)):
    s = db.get(SleepSession, session_id)
    if s is None:
        raise HTTPException(404, "Session not found")
    return _session_dict(s, include_detail=True)


@router.post("/sessions")
def create_manual_session(body: ManualSessionIn, db: Session = Depends(get_db)):
    if body.final_wake <= body.in_bed:
        raise HTTPException(422, "final_wake must be after in_bed")
    tib = (body.final_wake - body.in_bed).total_seconds() / 60
    tst = min(body.total_sleep_min, tib) if body.total_sleep_min else None
    wake_local = body.final_wake.astimezone(ZoneInfo(body.timezone_name))
    s = SleepSession(
        source="manual", timezone_name=body.timezone_name,
        session_date=wake_local.date().isoformat(),
        in_bed_utc=body.in_bed.astimezone(timezone.utc),
        final_wake_utc=body.final_wake.astimezone(timezone.utc),
        time_in_bed_min=round(tib, 1), total_sleep_min=tst,
        sleep_latency_min=body.sleep_latency_min, awakenings_count=body.awakenings_count,
        is_nap=body.is_nap, comments=body.comments, tags=body.tags,
        field_provenance={k: {"original_field": "manual_entry", "unit": None,
                              "kind": "self_reported", "confidence": "moderate"}
                          for k in ("in_bed_utc", "final_wake_utc", "total_sleep_min")},
    )
    db.add(s)
    db.flush()
    _score_and_store(db, s)
    db.add(AuditLog(action="manual_session", detail={"session_id": s.id, "date": s.session_date}))
    db.commit()
    return _session_dict(s)


@router.patch("/sessions/{session_id}")
def patch_session(session_id: str, body: SessionPatch, db: Session = Depends(get_db)):
    s = db.get(SleepSession, session_id)
    if s is None:
        raise HTTPException(404, "Session not found")
    changes = body.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(s, k, v)
    s.manually_edited = True
    if s.in_bed_utc and s.final_wake_utc:
        s.time_in_bed_min = round((s.final_wake_utc - s.in_bed_utc).total_seconds() / 60, 1)
    _score_and_store(db, s)
    db.add(AuditLog(action="session_edit", detail={"session_id": s.id, "fields": list(changes)}))
    db.commit()
    return _session_dict(s, include_detail=True)


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str, db: Session = Depends(get_db)):
    s = db.get(SleepSession, session_id)
    if s is None:
        raise HTTPException(404, "Session not found")
    db.delete(s)
    db.add(AuditLog(action="session_delete", detail={"session_id": session_id}))
    db.commit()
    return {"deleted": session_id}


# ---------------------------------------------------------------- habits & check-ins
@router.post("/habits")
def upsert_habit(body: HabitIn, db: Session = Depends(get_db)):
    h = db.scalar(select(HabitObservation).where(HabitObservation.date == body.date))
    if h is None:
        h = HabitObservation(date=body.date)
        db.add(h)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(h, k, v)
    db.commit()
    return {c.name: getattr(h, c.name) for c in HabitObservation.__table__.columns}


@router.get("/habits")
def list_habits(days: int = 60, db: Session = Depends(get_db)):
    rows = db.scalars(select(HabitObservation).order_by(HabitObservation.date.desc())).all()[:days]
    return [{c.name: getattr(h, c.name) for c in HabitObservation.__table__.columns} for h in rows]


@router.post("/checkins")
def upsert_checkin(body: CheckInIn, db: Session = Depends(get_db)):
    c = db.scalar(select(CheckIn).where(CheckIn.date == body.date, CheckIn.kind == body.kind))
    if c is None:
        c = CheckIn(date=body.date, kind=body.kind)
        db.add(c)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(c, k, v)
    db.commit()
    return {col.name: getattr(c, col.name) for col in CheckIn.__table__.columns}


@router.get("/checkins")
def list_checkins(days: int = 60, kind: str | None = None, db: Session = Depends(get_db)):
    q = select(CheckIn).order_by(CheckIn.date.desc())
    if kind:
        q = q.where(CheckIn.kind == kind)
    rows = db.scalars(q).all()[: days * 3]
    return [{col.name: getattr(c, col.name) for col in CheckIn.__table__.columns} for c in rows]


# ---------------------------------------------------------------- metrics & analytics
@router.get("/metrics/overview")
def metrics_overview(days: int = 28, db: Session = Depends(get_db)):
    p = _profile(db)
    rows = _sessions(db, aggregates_only=True)
    duration = metrics.duration_summary(rows, _workdays(p))
    reg = regularity.regularity_summary(rows[-days:], _workdays(p))
    need = sleep_debt.estimate_sleep_need(rows, _checkins_by_date(db), _habits_by_date(db),
                                          p.target_sleep_minutes)
    debt7 = sleep_debt.rolling_debt(rows, need["sleep_need_min"], 7)
    debt14 = sleep_debt.rolling_debt(rows, need["sleep_need_min"], 14)
    trend = [{"date": s.session_date, "total_sleep_min": s.total_sleep_min,
              "time_in_bed_min": s.time_in_bed_min,
              "efficiency_pct": metrics.sleep_efficiency(s.total_sleep_min, s.time_in_bed_min),
              "is_nap": s.is_nap,
              "onset_utc": s.in_bed_utc.isoformat() if s.in_bed_utc else None,
              "wake_utc": s.final_wake_utc.isoformat() if s.final_wake_utc else None,
              "timezone_name": s.timezone_name}
             for s in rows[-days * 2:]]
    if duration.get("avg_7d_min") and need.get("sleep_need_min"):
        ratio = duration["avg_7d_min"] / need["sleep_need_min"]
        need["fulfillment_10"] = max(1, min(10, round(ratio * 10)))
        need["fulfillment_note"] = (
            f"7-day average ({round(duration['avg_7d_min'])} min) vs your "
            f"{round(need['sleep_need_min'])} min target. 10 = fully meeting your sleep need.")
    return {"duration": duration, "regularity": reg, "sleep_need": need,
            "debt_7d": debt7, "debt_14d": debt14, "trend": trend,
            "hide_nightly_scores": p.hide_nightly_scores, "disclaimer": DISCLAIMER}


@router.get("/metrics/chronotype")
def get_chronotype(db: Session = Depends(get_db)):
    p = _profile(db)
    return chronotype.estimate_chronotype(_sessions(db, aggregates_only=True), _habits_by_date(db),
                                          _workdays(p), p.required_wake_time)


@router.get("/metrics/baselines/{metric}")
def get_baseline(metric: str, db: Session = Depends(get_db)):
    p = _profile(db)
    obs = db.scalars(select(PhysioObservation).where(PhysioObservation.metric == metric)
                     .order_by(PhysioObservation.date)).all()
    preferred = (p.preferred_sources or {}).get(metric)
    return baselines.baseline_summary(list(obs), metric, preferred)


@router.get("/metrics/snoring")
def snoring_summary(days: int = 28, db: Session = Depends(get_db)):
    rows = [s for s in _sessions(db, days, aggregates_only=True) if not s.is_nap]
    with_data = [s for s in rows if s.snore_minutes is not None]
    if len(with_data) < 3:
        return {"status": "insufficient_data", "nights_with_snore_data": len(with_data),
                "note": "Snoring analytics need at least 3 nights with snore data. "
                        "A phone microphone or wearable cannot confirm or exclude sleep apnea."}
    vals = [s.snore_minutes for s in with_data]
    heavy = [s for s in with_data if s.snore_minutes and s.time_in_bed_min
             and s.snore_minutes / s.time_in_bed_min > 0.15]
    return {
        "status": "ok",
        "nights_with_snore_data": len(with_data),
        "avg_snore_min": round(statistics.mean(vals), 1),
        "median_snore_min": round(statistics.median(vals), 1),
        "max_snore_min": round(max(vals), 1),
        "heavy_nights": len(heavy),
        "trend": [{"date": s.session_date, "snore_min": s.snore_minutes,
                   "pct_of_night": round(s.snore_minutes / s.time_in_bed_min * 100, 1)
                   if s.time_in_bed_min else None} for s in with_data],
        "detection_confidence": "low",
        "medical_note": ("Snoring alone does not diagnose sleep apnea, and this data cannot "
                         "exclude it. If snoring is combined with witnessed breathing pauses, "
                         "gasping, significant daytime sleepiness, morning headaches, or waking "
                         "with a racing heart, a discussion with a healthcare professional "
                         "about a sleep assessment would be reasonable."),
    }


@router.get("/coaching/today")
def coaching_today(db: Session = Depends(get_db)):
    p = _profile(db)
    rows = _sessions(db, aggregates_only=True)
    mains = [s for s in rows if not s.is_nap]
    last = mains[-1] if mains else None
    habits = _habits_by_date(db)
    checkins = _checkins_by_date(db)
    need = sleep_debt.estimate_sleep_need(rows, checkins, habits, p.target_sleep_minutes)
    debt = sleep_debt.rolling_debt(rows, need["sleep_need_min"], 7)
    reg = regularity.regularity_summary(rows[-28:], _workdays(p))
    hrv_obs = db.scalars(select(PhysioObservation).where(PhysioObservation.metric == "hrv_rmssd")
                         .order_by(PhysioObservation.date)).all()
    hrv = baselines.baseline_summary(list(hrv_obs), "hrv_rmssd",
                                     (p.preferred_sources or {}).get("hrv_rmssd")) if hrv_obs else None

    tonight = None
    if p.required_wake_time:
        latencies = [s.sleep_latency_min for s in mains[-14:] if s.sleep_latency_min is not None]
        onsets = []
        for s in mains[-14:]:
            onset = s.sleep_onset_utc or s.in_bed_utc
            if onset:
                local = onset.astimezone(ZoneInfo(s.timezone_name))
                onsets.append(local.hour * 60 + local.minute)
        today_hb = habits.get(last.session_date) if last else None
        tonight = recommend.bedtime_recommendation(
            required_wake_local=p.required_wake_time, tz_name=p.current_timezone or "UTC",
            sleep_need_min=need["sleep_need_min"], need_confidence=need["confidence"],
            recent_latencies=latencies, net_debt_min=debt.get("net_debt_min"),
            recent_onsets_local_min=onsets or None,
            illness=bool(today_hb and today_hb.illness))

    duration = metrics.duration_summary(rows, _workdays(p))
    snore_vals = [s.snore_minutes for s in mains[-28:] if s.snore_minutes is not None]
    snore_avg = round(statistics.mean(snore_vals), 1) if len(snore_vals) >= 3 else None
    return {
        "coaching": coaching.build_morning_coaching(
            session=last, duration_summary=duration, regularity=reg, debt=debt,
            hrv_baseline=hrv, habits=habits.get(last.session_date) if last else None,
            checkin=checkins.get(last.session_date) if last else None,
            tonight=tonight, sleep_need_min=need["sleep_need_min"], snore_avg_min=snore_avg),
        "session": _session_dict(last) if last else None,
        "sleep_need": need,
        "disclaimer": DISCLAIMER,
    }


@router.get("/reports/weekly")
def weekly_report(db: Session = Depends(get_db)):
    p = _profile(db)
    rows = _sessions(db, aggregates_only=True)
    week = [s for s in rows if not s.is_nap][-7:]
    if len(week) < 3:
        return {"status": "insufficient_data", "nights": len(week),
                "note": "Weekly report needs at least 3 nights."}
    tsts = [s.total_sleep_min for s in week if s.total_sleep_min]
    effs = [e for s in week if (e := metrics.sleep_efficiency(s.total_sleep_min, s.time_in_bed_min))]
    reg = regularity.regularity_summary(week, _workdays(p))
    need = sleep_debt.estimate_sleep_need(rows, _checkins_by_date(db), _habits_by_date(db),
                                          p.target_sleep_minutes)
    debt = sleep_debt.rolling_debt(rows, need["sleep_need_min"], 7)
    checkins = _checkins_by_date(db)
    energies = [(d, c.morning_energy) for d, c in checkins.items()
                if c.morning_energy is not None and any(s.session_date == d for s in week)]
    best = max(energies, key=lambda x: x[1]) if energies else None
    worst = min(energies, key=lambda x: x[1]) if energies else None
    quality_issues = [f"{s.session_date}: {quality.confidence_label(s.data_quality_score)} confidence"
                      for s in week if (s.data_quality_score or 100) < 55]
    focus = "Keep your current routine — it is working."
    if reg.get("status") == "ok" and reg.get("wake_sd_min", 0) > 45:
        focus = "Pick one wake time and hold it all seven days, including free days."
    elif debt.get("status") == "ok" and debt.get("net_debt_min", 0) > 120:
        focus = "Bring bedtime forward by 30 minutes to work down accumulated sleep debt."
    # ---- Patterns & continuity over the last 14 nights ----
    recent14 = [s for s in rows if not s.is_nap][-14:]
    eff14 = [(s.session_date, e) for s in recent14
             if (e := metrics.sleep_efficiency(s.total_sleep_min, s.time_in_bed_min)) is not None]
    eff_trend = None
    if len(eff14) >= 8:
        half = len(eff14) // 2
        first = statistics.mean(e for _, e in eff14[:half])
        second = statistics.mean(e for _, e in eff14[half:])
        delta = round(second - first, 1)
        direction = "improving" if delta > 1.5 else "declining" if delta < -1.5 else "stable"
        eff_trend = {"direction": direction, "first_half_pct": round(first, 1),
                     "second_half_pct": round(second, 1), "change_pct": delta}

    bed_irregular = []
    onsets_local = []
    for s in recent14:
        if s.in_bed_utc:
            local = s.in_bed_utc.astimezone(ZoneInfo(s.timezone_name))
            m = local.hour * 60 + local.minute
            if m < 720:
                m += 1440  # map early-morning bedtimes past midnight
            onsets_local.append((s.session_date, m, local.strftime("%H:%M")))
    if len(onsets_local) >= 5:
        med = statistics.median(m for _, m, _ in onsets_local)
        bed_irregular = [{"date": d, "bedtime_local": t, "deviation_min": round(m - med)}
                         for d, m, t in onsets_local if abs(m - med) > 90]

    circadian = None
    if reg.get("status") == "ok":
        mid_sd = reg.get("midpoint_sd_min", 0)
        tier = ("well anchored" if mid_sd <= 30 else
                "moderately consistent" if mid_sd <= 60 else "irregular")
        circadian = {"midpoint_sd_min": mid_sd, "assessment": tier,
                     "summary": f"Your sleep midpoint varies by about {round(mid_sd)} minutes — "
                                f"your circadian rhythm is {tier}."}

    debt_education = None
    if debt.get("status") == "ok" and debt.get("net_debt_min", 0) > 60:
        debt_education = (
            f"You are carrying about {round(debt['net_debt_min'] / 60, 1)} hours of estimated sleep "
            "debt. As Matthew Walker lays out in Why We Sleep, routinely sleeping under about seven "
            "hours degrades attention, memory consolidation, emotional regulation, immune function "
            "and physical recovery — and the effects compound before you notice them. Lost sleep is "
            "not fully repaid by one long lie-in, which is why this app credits recovery sleep at "
            "only half value. The reliable fix is protecting a consistent 7.5-8.5 hour opportunity "
            "every night — your best return on investment for energy, focus and training.")

    return {
        "status": "ok", "nights": len(week),
        "avg_total_sleep_min": round(statistics.mean(tsts), 1) if tsts else None,
        "avg_efficiency_pct": round(statistics.mean(effs), 1) if effs else None,
        "patterns": {"efficiency_trend": eff_trend,
                     "irregular_bedtimes": bed_irregular,
                     "circadian_rhythm": circadian},
        "sleep_debt_education": debt_education,
        "regularity": reg,
        "bedtime_range": [min(s.in_bed_utc.astimezone(ZoneInfo(s.timezone_name)).strftime("%H:%M")
                              for s in week if s.in_bed_utc),
                          max(s.in_bed_utc.astimezone(ZoneInfo(s.timezone_name)).strftime("%H:%M")
                              for s in week if s.in_bed_utc)],
        "wake_range": [min(s.final_wake_utc.astimezone(ZoneInfo(s.timezone_name)).strftime("%H:%M")
                           for s in week if s.final_wake_utc),
                       max(s.final_wake_utc.astimezone(ZoneInfo(s.timezone_name)).strftime("%H:%M")
                           for s in week if s.final_wake_utc)],
        "sleep_debt": debt,
        "best_energy_day": {"date": best[0], "energy": best[1]} if best else None,
        "lowest_energy_day": {"date": worst[0], "energy": worst[1]} if worst else None,
        "data_quality_issues": quality_issues,
        "recommended_focus": focus,
        "note": "Trends matter more than any single night.",
    }


# ---------------------------------------------------------------- privacy
@router.get("/privacy/export")
def export_all(db: Session = Depends(get_db)):
    def dump(model):
        return [{c.name: (v.isoformat() if isinstance(v := getattr(r, c.name), datetime) else v)
                 for c in model.__table__.columns} for r in db.scalars(select(model)).all()]

    db.add(AuditLog(action="export", detail={"scope": "all"}))
    db.commit()
    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "profile": dump(UserProfile), "sessions": dump(SleepSession),
        "physio": dump(PhysioObservation), "snore": dump(SnoreObservation),
        "habits": dump(HabitObservation), "checkins": dump(CheckIn),
        "imports": dump(ImportBatch), "raw_records": dump(RawRecord),
        "audit_log": dump(AuditLog),
    }


@router.get("/privacy/clinician-report")
def clinician_report(db: Session = Depends(get_db)):
    p = _profile(db)
    rows = _sessions(db)
    mains = [s for s in rows if not s.is_nap][-28:]
    if len(mains) < 5:
        return {"status": "insufficient_data", "nights": len(mains)}
    tsts = [s.total_sleep_min for s in mains if s.total_sleep_min]
    snores = [s.snore_minutes for s in mains if s.snore_minutes is not None]
    return {
        "status": "ok",
        "purpose": "Concise summary for discussion with a clinician. Contains no diagnoses.",
        "period": [mains[0].session_date, mains[-1].session_date],
        "nights": len(mains),
        "avg_total_sleep_min": round(statistics.mean(tsts), 1) if tsts else None,
        "sleep_timing_regularity": regularity.regularity_summary(mains, _workdays(p)),
        "snoring": {"nights_with_data": len(snores),
                    "avg_min": round(statistics.mean(snores), 1) if snores else None},
        "reported_concerns": p.sleep_concerns,
        "data_sources": sorted({s.source for s in mains}),
        "limitations": ("Consumer-device estimates; not polysomnography. Sleep stages and "
                        "snoring are device-estimated and can be inaccurate. No diagnostic "
                        "claim is made or implied."),
    }


@router.post("/privacy/delete-all")
def delete_all(confirm: str = "", db: Session = Depends(get_db)):
    if confirm != "DELETE":
        raise HTTPException(400, 'Pass confirm="DELETE" to erase all personal data.')
    counts = {}
    for model in (PhysioObservation, SnoreObservation, SleepSession, RawRecord,
                  ImportBatch, HabitObservation, CheckIn, UserProfile):
        counts[model.__tablename__] = db.execute(delete(model)).rowcount
    db.add(AuditLog(action="delete_all", detail=counts))
    db.commit()
    return {"deleted": counts, "note": "Audit log entry retained to record the deletion."}


@router.get("/privacy/audit")
def audit_log(db: Session = Depends(get_db)):
    rows = db.scalars(select(AuditLog).order_by(AuditLog.at.desc())).all()[:200]
    return [{"at": r.at.isoformat() if r.at else None, "action": r.action, "detail": r.detail}
            for r in rows]
