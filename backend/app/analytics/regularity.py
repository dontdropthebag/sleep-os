"""Sleep-timing regularity.

Onset/wake/midpoint are handled as *local wall-clock minutes* on a circular
scale so a 23:50 vs 00:10 bedtime counts as a 20-minute spread, not 23 hours.
"""

import math
import statistics
from datetime import datetime
from zoneinfo import ZoneInfo

MIN_NIGHTS = 5


def _local_minutes(dt_utc: datetime, tz_name: str) -> float:
    local = dt_utc.astimezone(ZoneInfo(tz_name))
    return local.hour * 60 + local.minute + local.second / 60


def circular_mean_minutes(minutes: list[float]) -> float:
    angles = [m / 1440 * 2 * math.pi for m in minutes]
    s = sum(math.sin(a) for a in angles) / len(angles)
    c = sum(math.cos(a) for a in angles) / len(angles)
    mean = math.atan2(s, c) / (2 * math.pi) * 1440
    return mean % 1440


def circular_sd_minutes(minutes: list[float]) -> float:
    """Std dev around the circular mean, expressed in minutes."""
    if len(minutes) < 2:
        return 0.0
    mean = circular_mean_minutes(minutes)
    devs = []
    for m in minutes:
        d = (m - mean) % 1440
        if d > 720:
            d -= 1440
        devs.append(d)
    return statistics.pstdev(devs)


def _fmt(mins: float) -> str:
    return f"{int(mins // 60) % 24:02d}:{int(mins % 60):02d}"


def regularity_summary(sessions: list, workdays: set[str] | None = None) -> dict:
    """SD of onset/wake/midpoint, workday-vs-free-day shift, social jetlag."""
    mains = [s for s in sessions if not s.is_nap and s.in_bed_utc and s.final_wake_utc]
    if len(mains) < MIN_NIGHTS:
        return {"status": "insufficient_data", "nights": len(mains), "nights_required": MIN_NIGHTS}

    onsets, wakes, midpoints = [], [], []
    work_mid, free_mid = [], []
    workdays = workdays or {"mon", "tue", "wed", "thu", "fri"}
    for s in mains:
        onset = s.sleep_onset_utc or s.in_bed_utc  # documented fallback
        onsets.append(_local_minutes(onset, s.timezone_name))
        wakes.append(_local_minutes(s.final_wake_utc, s.timezone_name))
        mid_utc = onset + (s.final_wake_utc - onset) / 2
        mid = _local_minutes(mid_utc, s.timezone_name)
        midpoints.append(mid)
        day = datetime.fromisoformat(s.session_date).strftime("%a").lower()[:3]
        (work_mid if day in workdays else free_mid).append(mid)

    social_jetlag = None
    if len(work_mid) >= 3 and len(free_mid) >= 3:
        d = (circular_mean_minutes(free_mid) - circular_mean_minutes(work_mid)) % 1440
        if d > 720:
            d -= 1440
        social_jetlag = round(d, 1)

    return {
        "status": "ok",
        "nights": len(mains),
        "onset_sd_min": round(circular_sd_minutes(onsets), 1),
        "wake_sd_min": round(circular_sd_minutes(wakes), 1),
        "midpoint_sd_min": round(circular_sd_minutes(midpoints), 1),
        "mean_onset_local": _fmt(circular_mean_minutes(onsets)),
        "mean_wake_local": _fmt(circular_mean_minutes(wakes)),
        "mean_midpoint_local": _fmt(circular_mean_minutes(midpoints)),
        "social_jetlag_min": social_jetlag,
        "note": "Onset falls back to in-bed time when the device did not record sleep onset.",
    }
