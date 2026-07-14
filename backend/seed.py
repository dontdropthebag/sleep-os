"""Seed the local database with ~35 nights of synthetic demo data.

Usage:  .venv/bin/python seed.py          (adds demo data)
        .venv/bin/python seed.py --reset  (wipes DB first)

All data is synthetic; no real health data is involved.
"""

import random
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import delete

from app.analytics.quality import score_session
from app.db import Base, SessionLocal, engine
from app.models import (AuditLog, CheckIn, HabitObservation, ImportBatch, PhysioObservation,
                        RawRecord, SleepSession, SnoreObservation, UserProfile)

rng = random.Random(42)
TZ = ZoneInfo("Europe/London")
DAYS = 35


def main() -> None:
    Base.metadata.create_all(engine)
    db = SessionLocal()
    if "--reset" in sys.argv:
        for m in (PhysioObservation, SnoreObservation, SleepSession, RawRecord,
                  ImportBatch, HabitObservation, CheckIn, AuditLog, UserProfile):
            db.execute(delete(m))
        db.commit()

    profile = db.get(UserProfile, 1) or UserProfile(id=1)
    profile.age_range = "30-39"
    profile.occupation = "Sales / business development"
    profile.required_wake_time = "06:30"
    profile.workdays = ["mon", "tue", "wed", "thu", "fri"]
    profile.primary_goals = ["daytime energy", "training recovery", "focus"]
    profile.sleep_concerns = ["snoring"]
    profile.current_timezone = "Europe/London"
    profile.target_sleep_minutes = 480
    db.add(profile)

    today = datetime.now(TZ).date()
    for i in range(DAYS, 0, -1):
        date = today - timedelta(days=i)
        weekend = date.weekday() >= 5
        alcohol = weekend and rng.random() < 0.5
        late_caffeine = rng.random() < 0.3

        bed_hour = 23 + (1.5 if weekend else 0) + rng.uniform(-0.4, 0.6) + (0.7 if alcohol else 0)
        wake_dt = datetime.combine(date, datetime.min.time(), TZ).replace(
            hour=8 if weekend else 6, minute=30) + timedelta(minutes=rng.randint(-15, 25))
        bed_dt = datetime.combine(date - timedelta(days=1), datetime.min.time(), TZ) + \
            timedelta(hours=bed_hour)
        tib = (wake_dt - bed_dt).total_seconds() / 60
        eff = rng.uniform(0.86, 0.94) - (0.06 if alcohol else 0) - (0.03 if late_caffeine else 0)
        tst = round(tib * eff, 1)

        # Device-estimated stages (synthetic)
        deep_frac = max(0.1, rng.uniform(0.18, 0.28) - (0.07 if alcohol else 0))
        stages, cursor = [], bed_dt + timedelta(minutes=rng.randint(8, 25))
        for stage, frac in (("light", 0.55), ("deep", deep_frac), ("rem", 0.2)):
            dur = timedelta(minutes=tst * frac)
            stages.append({"stage": stage, "start_utc": cursor.astimezone(timezone.utc).isoformat(),
                           "end_utc": (cursor + dur).astimezone(timezone.utc).isoformat()})
            cursor += dur
        n_awake = rng.randint(1, 4 if alcohol else 2)
        for _ in range(n_awake):
            t = bed_dt + timedelta(minutes=rng.uniform(60, tib - 60))
            stages.append({"stage": "awake", "start_utc": t.astimezone(timezone.utc).isoformat(),
                           "end_utc": (t + timedelta(minutes=rng.uniform(2, 12))).astimezone(timezone.utc).isoformat()})

        snore = round(rng.uniform(5, 45) + (25 if alcohol else 0), 1) if rng.random() < 0.6 else None
        s = SleepSession(
            source="sleep_as_android", source_session_id=f"seed-{date.isoformat()}",
            session_date=date.isoformat(), timezone_name="Europe/London",
            in_bed_utc=bed_dt.astimezone(timezone.utc), final_wake_utc=wake_dt.astimezone(timezone.utc),
            time_in_bed_min=round(tib, 1), total_sleep_min=tst,
            waso_min=round(n_awake * 6.0, 1), awakenings_count=n_awake,
            stage_intervals=stages, snore_minutes=snore,
            deep_sleep_fraction=round(deep_frac, 2), cycles=rng.randint(4, 6),
            user_rating=round(rng.uniform(2.5, 4.5), 1),
            tags=(["#alcohol"] if alcohol else []) + (["#late_caffeine"] if late_caffeine else []) or None,
            field_provenance={"total_sleep_min": {"original_field": "Hours", "unit": "min",
                                                  "kind": "device_estimated", "confidence": "moderate"}},
            parser_version="seed-1.0",
        )
        db.add(s)
        db.flush()
        s.data_quality_score, s.quality_breakdown = score_session(
            s, {"hrv_rmssd", "resting_hr"})

        base_hrv = 55 - (8 if alcohol else 0) + rng.uniform(-5, 5)
        db.add(PhysioObservation(session_id=s.id, date=date.isoformat(), metric="hrv_rmssd",
                                 value=round(base_hrv, 1), unit="ms", source="sleep_as_android",
                                 method="rmssd_overnight", kind="device_estimated"))
        db.add(PhysioObservation(session_id=s.id, date=date.isoformat(), metric="resting_hr",
                                 value=round(52 + (5 if alcohol else 0) + rng.uniform(-2, 2), 1),
                                 unit="bpm", source="sleep_as_android",
                                 method="sleeping_min", kind="device_estimated"))

        db.add(HabitObservation(
            date=date.isoformat(),
            caffeine_mg=rng.choice([100, 150, 200, 250]),
            last_caffeine_time="16:30" if late_caffeine else "11:30",
            alcohol_units=rng.choice([2, 3, 4]) if alcohol else 0,
            exercise_type=rng.choice(["strength", "strength", "none", "cardio"]),
            exercise_intensity=rng.choice(["moderate", "high"]),
            exercise_end_time="18:30",
            last_meal_time="21:30" if alcohol else "19:45",
            wind_down_routine=not alcohol and rng.random() < 0.6,
            travel=False, illness=False,
            sleeping_position=rng.choice(["side", "back"]),
        ))
        sleep_score = tst / 480
        db.add(CheckIn(
            date=date.isoformat(), kind="morning",
            sleep_quality=max(1, min(10, round(sleep_score * 8 + rng.uniform(-1, 1)))),
            refreshed=max(1, min(10, round(sleep_score * 8 - (2 if alcohol else 0) + rng.uniform(-1, 1)))),
            morning_energy=max(1, min(10, round(sleep_score * 8 - (2 if alcohol else 0) + rng.uniform(-1, 1)))),
            daytime_sleepiness=max(1, min(10, round((1 - sleep_score) * 10 + (2 if alcohol else 0)))),
            mood=rng.randint(5, 9), soreness=rng.randint(2, 7),
        ))

    db.add(AuditLog(action="seed", detail={"days": DAYS, "synthetic": True}))
    db.commit()
    db.close()
    print(f"Seeded {DAYS} synthetic nights (profile, sessions, physio, habits, check-ins).")


if __name__ == "__main__":
    main()
