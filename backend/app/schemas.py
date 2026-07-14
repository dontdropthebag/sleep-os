"""Pydantic I/O schemas (validation layer for the API)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Scale = Field(default=None, ge=1, le=10)


class ProfileIn(BaseModel):
    age_range: str | None = None
    sex: str | None = None
    height_cm: float | None = Field(default=None, gt=50, lt=280)
    weight_kg: float | None = Field(default=None, gt=20, lt=400)
    occupation: str | None = None
    work_schedule: str | None = None
    required_wake_time: str | None = None
    workdays: list[str] | None = None
    training_schedule: str | None = None
    travel_status: str | None = None
    primary_goals: list[str] | None = None
    sleep_concerns: list[str] | None = None
    preferred_units: Literal["metric", "imperial"] | None = None
    current_timezone: str | None = None
    target_sleep_minutes: int | None = Field(default=None, ge=300, le=720)
    hide_nightly_scores: bool | None = None
    preferred_sources: dict[str, str] | None = None

    @field_validator("required_wake_time")
    @classmethod
    def _hhmm(cls, v):
        if v is not None:
            h, m = v.split(":")
            assert 0 <= int(h) < 24 and 0 <= int(m) < 60
        return v


class ManualSessionIn(BaseModel):
    """Manual sleep entry — self-reported."""

    in_bed: datetime
    final_wake: datetime
    timezone_name: str = "UTC"
    total_sleep_min: float | None = Field(default=None, gt=0, le=18 * 60)
    sleep_latency_min: float | None = Field(default=None, ge=0, le=300)
    awakenings_count: int | None = Field(default=None, ge=0, le=50)
    is_nap: bool = False
    comments: str | None = None
    tags: list[str] | None = None


class SessionPatch(BaseModel):
    """Manual correction of an imported session."""

    in_bed_utc: datetime | None = None
    final_wake_utc: datetime | None = None
    total_sleep_min: float | None = Field(default=None, gt=0, le=18 * 60)
    is_nap: bool | None = None
    comments: str | None = None
    tags: list[str] | None = None
    excluded_reasons: list[str] | None = None


class HabitIn(BaseModel):
    date: str
    caffeine_mg: float | None = Field(default=None, ge=0, le=2000)
    first_caffeine_time: str | None = None
    last_caffeine_time: str | None = None
    alcohol_units: float | None = Field(default=None, ge=0, le=40)
    last_alcohol_time: str | None = None
    nicotine: bool | None = None
    cannabis: bool | None = None
    medication: str | None = None
    supplements: str | None = None
    last_meal_time: str | None = None
    meal_size: Literal["light", "moderate", "heavy"] | None = None
    exercise_type: str | None = None
    exercise_intensity: Literal["low", "moderate", "high"] | None = None
    exercise_end_time: str | None = None
    morning_light_start: str | None = None
    morning_light_minutes: float | None = Field(default=None, ge=0, le=600)
    evening_screens: Literal["none", "light", "heavy"] | None = None
    wind_down_routine: bool | None = None
    nap_start: str | None = None
    nap_minutes: float | None = Field(default=None, ge=0, le=300)
    hydration: str | None = None
    illness: bool | None = None
    pain: bool | None = None
    travel: bool | None = None
    timezone_change: bool | None = None
    bedroom_temp: str | None = None
    bedroom_noise: str | None = None
    bedroom_light: str | None = None
    sleeping_position: Literal["back", "side", "front", "varies"] | None = None
    partner_in_room: bool | None = None


class CheckInIn(BaseModel):
    date: str
    kind: Literal["morning", "midday", "evening"]
    sleep_quality: int | None = Scale
    refreshed: int | None = Scale
    morning_energy: int | None = Scale
    daytime_sleepiness: int | None = Scale
    mood: int | None = Scale
    soreness: int | None = Scale
    energy: int | None = Scale
    focus: int | None = Scale
    stress: int | None = Scale
    motivation: int | None = Scale
    mental_clarity: int | None = Scale
    physical_fatigue: int | None = Scale
    afternoon_crash: int | None = Scale
    workout_quality: int | None = Scale


class CommitIn(BaseModel):
    include_indices: list[int] | None = None
    overrides: dict[int, dict] | None = None
