import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class UserProfile(Base):
    """Single-user profile. Editable; algorithms must not hard-code demographics."""

    __tablename__ = "user_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    age_range: Mapped[str | None] = mapped_column(String, nullable=True)  # e.g. "30-39"
    sex: Mapped[str | None] = mapped_column(String, nullable=True)
    height_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    occupation: Mapped[str | None] = mapped_column(String, nullable=True)
    work_schedule: Mapped[str | None] = mapped_column(String, nullable=True)
    required_wake_time: Mapped[str | None] = mapped_column(String, nullable=True)  # "HH:MM" local
    workdays: Mapped[list | None] = mapped_column(JSON, nullable=True)  # ["mon",...]
    training_schedule: Mapped[str | None] = mapped_column(Text, nullable=True)
    travel_status: Mapped[str | None] = mapped_column(String, nullable=True)
    primary_goals: Mapped[list | None] = mapped_column(JSON, nullable=True)
    sleep_concerns: Mapped[list | None] = mapped_column(JSON, nullable=True)
    preferred_units: Mapped[str] = mapped_column(String, default="metric")
    current_timezone: Mapped[str] = mapped_column(String, default="UTC")
    # Sleep-need preference used until a personal estimate exists (minutes)
    target_sleep_minutes: Mapped[int] = mapped_column(Integer, default=480)
    # Orthosomnia guard: hide nightly detail scores, show weekly trends only
    hide_nightly_scores: Mapped[bool] = mapped_column(Boolean, default=False)
    # Preferred source per metric when devices disagree, e.g. {"hrv": "oura"}
    preferred_sources: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ImportBatch(Base):
    """One uploaded file / manual import. Staged first, committed after preview."""

    __tablename__ = "import_batches"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    source: Mapped[str] = mapped_column(String)
    filename: Mapped[str | None] = mapped_column(String, nullable=True)
    file_sha256: Mapped[str | None] = mapped_column(String, nullable=True)
    parser_version: Mapped[str] = mapped_column(String)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    status: Mapped[str] = mapped_column(String, default="staged")  # staged|committed|discarded
    # Full preview payload (sessions, issues, duplicates) kept until commit
    staged_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    sessions: Mapped[list["SleepSession"]] = relationship(back_populates="batch")


class RawRecord(Base):
    """Original source rows, preserved verbatim before normalisation."""

    __tablename__ = "raw_records"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    batch_id: Mapped[str] = mapped_column(ForeignKey("import_batches.id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(String)
    record_kind: Mapped[str] = mapped_column(String)  # sleep|noise|prefs|other
    payload: Mapped[dict] = mapped_column(JSON)


class SleepSession(Base):
    __tablename__ = "sleep_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    batch_id: Mapped[str | None] = mapped_column(
        ForeignKey("import_batches.id", ondelete="SET NULL"), nullable=True
    )
    raw_record_id: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str] = mapped_column(String)
    source_session_id: Mapped[str | None] = mapped_column(String, nullable=True)
    parser_version: Mapped[str | None] = mapped_column(String, nullable=True)

    # Night attribution: date of the morning of final awakening (local)
    session_date: Mapped[str] = mapped_column(String, index=True)  # YYYY-MM-DD
    timezone_name: Mapped[str] = mapped_column(String, default="UTC")

    # All instants stored as UTC; local wall-clock kept via timezone_name
    in_bed_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sleep_onset_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    final_wake_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    out_of_bed_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    time_in_bed_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_sleep_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    sleep_latency_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    waso_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    awakenings_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Device-estimated stage intervals: [{stage, start_utc, end_utc}]
    stage_intervals: Mapped[list | None] = mapped_column(JSON, nullable=True)
    is_nap: Mapped[bool] = mapped_column(Boolean, default=False)

    user_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    snore_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    noise_level: Mapped[float | None] = mapped_column(Float, nullable=True)
    cycles: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deep_sleep_fraction: Mapped[float | None] = mapped_column(Float, nullable=True)  # device est.
    movement_timeline: Mapped[list | None] = mapped_column(JSON, nullable=True)
    noise_timeline: Mapped[list | None] = mapped_column(JSON, nullable=True)
    event_timeline: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Per-field provenance: {canonical_field: {original_field, unit, kind, confidence}}
    field_provenance: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    data_quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality_breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    manually_edited: Mapped[bool] = mapped_column(Boolean, default=False)
    excluded_reasons: Mapped[list | None] = mapped_column(JSON, nullable=True)  # travel/illness/...

    batch: Mapped[ImportBatch | None] = relationship(back_populates="sessions")


class PhysioObservation(Base):
    """One physiological metric reading attributed to a night or a day."""

    __tablename__ = "physio_observations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    session_id: Mapped[str | None] = mapped_column(
        ForeignKey("sleep_sessions.id", ondelete="CASCADE"), nullable=True
    )
    date: Mapped[str] = mapped_column(String, index=True)
    metric: Mapped[str] = mapped_column(String, index=True)  # hrv_rmssd|resting_hr|resp_rate|spo2|skin_temp_dev|steps|training_load
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str] = mapped_column(String)
    # HRV method matters: rmssd_overnight vs rmssd_morning_spot etc. Never blend methods.
    method: Mapped[str | None] = mapped_column(String, nullable=True)
    kind: Mapped[str] = mapped_column(String)  # MeasurementKind value
    confidence: Mapped[str] = mapped_column(String, default="moderate")
    original_field: Mapped[str | None] = mapped_column(String, nullable=True)
    batch_id: Mapped[str | None] = mapped_column(String, nullable=True)


class SnoreObservation(Base):
    __tablename__ = "snore_observations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    session_id: Mapped[str | None] = mapped_column(
        ForeignKey("sleep_sessions.id", ondelete="CASCADE"), nullable=True
    )
    date: Mapped[str] = mapped_column(String, index=True)
    recording_start_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recording_end_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    events: Mapped[list | None] = mapped_column(JSON, nullable=True)  # [{t_utc, duration_s, loudness, label}]
    total_snore_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    background_noise: Mapped[float | None] = mapped_column(Float, nullable=True)
    audio_confidence: Mapped[str] = mapped_column(String, default="low")
    non_snore_flag: Mapped[bool] = mapped_column(Boolean, default=False)  # speech/env noise suspected
    source: Mapped[str] = mapped_column(String)


class HabitObservation(Base):
    """Daily habit log. All self-reported."""

    __tablename__ = "habit_observations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    date: Mapped[str] = mapped_column(String, index=True, unique=True)
    caffeine_mg: Mapped[float | None] = mapped_column(Float, nullable=True)
    first_caffeine_time: Mapped[str | None] = mapped_column(String, nullable=True)  # "HH:MM"
    last_caffeine_time: Mapped[str | None] = mapped_column(String, nullable=True)
    alcohol_units: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_alcohol_time: Mapped[str | None] = mapped_column(String, nullable=True)
    nicotine: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    cannabis: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    medication: Mapped[str | None] = mapped_column(String, nullable=True)
    supplements: Mapped[str | None] = mapped_column(String, nullable=True)
    last_meal_time: Mapped[str | None] = mapped_column(String, nullable=True)
    meal_size: Mapped[str | None] = mapped_column(String, nullable=True)  # light|moderate|heavy
    exercise_type: Mapped[str | None] = mapped_column(String, nullable=True)
    exercise_intensity: Mapped[str | None] = mapped_column(String, nullable=True)
    exercise_end_time: Mapped[str | None] = mapped_column(String, nullable=True)
    morning_light_start: Mapped[str | None] = mapped_column(String, nullable=True)
    morning_light_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    evening_screens: Mapped[str | None] = mapped_column(String, nullable=True)  # none|light|heavy
    wind_down_routine: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    nap_start: Mapped[str | None] = mapped_column(String, nullable=True)
    nap_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    hydration: Mapped[str | None] = mapped_column(String, nullable=True)
    illness: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    pain: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    travel: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    timezone_change: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    bedroom_temp: Mapped[str | None] = mapped_column(String, nullable=True)
    bedroom_noise: Mapped[str | None] = mapped_column(String, nullable=True)
    bedroom_light: Mapped[str | None] = mapped_column(String, nullable=True)
    sleeping_position: Mapped[str | None] = mapped_column(String, nullable=True)
    partner_in_room: Mapped[bool | None] = mapped_column(Boolean, nullable=True)


class CheckIn(Base):
    """Subjective check-ins. morning|midday|evening, all 1-10 scales."""

    __tablename__ = "checkins"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    date: Mapped[str] = mapped_column(String, index=True)
    kind: Mapped[str] = mapped_column(String)  # morning|midday|evening
    # Morning
    sleep_quality: Mapped[int | None] = mapped_column(Integer, nullable=True)
    refreshed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    morning_energy: Mapped[int | None] = mapped_column(Integer, nullable=True)
    daytime_sleepiness: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mood: Mapped[int | None] = mapped_column(Integer, nullable=True)
    soreness: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Midday / evening
    energy: Mapped[int | None] = mapped_column(Integer, nullable=True)
    focus: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stress: Mapped[int | None] = mapped_column(Integer, nullable=True)
    motivation: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mental_clarity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    physical_fatigue: Mapped[int | None] = mapped_column(Integer, nullable=True)
    afternoon_crash: Mapped[int | None] = mapped_column(Integer, nullable=True)
    workout_quality: Mapped[int | None] = mapped_column(Integer, nullable=True)


class AuditLog(Base):
    """Audit trail for imports, edits and deletions."""

    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    action: Mapped[str] = mapped_column(String)  # import|commit|edit|delete|export|delete_all
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
