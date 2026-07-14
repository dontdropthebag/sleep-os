"""Core sleep metrics. All formulas are transparent and documented in
docs/METRICS.md; every function returns the inputs it used so the UI can
show its work.
"""

import statistics
from datetime import datetime


def sleep_efficiency(total_sleep_min: float | None, time_in_bed_min: float | None) -> float | None:
    """total sleep time / total time in bed x 100. None when inputs missing."""
    if not total_sleep_min or not time_in_bed_min or time_in_bed_min <= 0:
        return None
    return round(min(total_sleep_min / time_in_bed_min, 1.0) * 100, 1)


def rolling_average(values: list[float | None], window: int) -> float | None:
    """Mean of the most recent `window` non-null values; needs >= window/2 points."""
    recent = [v for v in values[-window:] if v is not None]
    if len(recent) < max(2, window // 2):
        return None
    return round(statistics.mean(recent), 1)


def stage_summary(stage_intervals: list[dict] | None, total_sleep_min: float | None) -> dict | None:
    """Deep/REM/light minutes and percentages. Always device-estimated."""
    if not stage_intervals:
        return None
    mins: dict[str, float] = {}
    transitions = 0
    prev = None
    for iv in sorted(stage_intervals, key=lambda x: x["start_utc"]):
        dur = (datetime.fromisoformat(iv["end_utc"]) - datetime.fromisoformat(iv["start_utc"])).total_seconds() / 60
        mins[iv["stage"]] = mins.get(iv["stage"], 0.0) + dur
        if prev is not None and iv["stage"] != prev:
            transitions += 1
        prev = iv["stage"]
    asleep = total_sleep_min or sum(v for k, v in mins.items() if k != "awake")
    out = {"transitions": transitions, "kind": "device_estimated",
           "note": "Stage estimates from consumer devices differ from polysomnography."}
    for stage in ("deep", "rem", "light", "awake"):
        m = round(mins.get(stage, 0.0), 1)
        out[f"{stage}_min"] = m if stage in mins else None
        if stage != "awake" and asleep and stage in mins:
            out[f"{stage}_pct"] = round(m / asleep * 100, 1)
    return out


def continuity(session) -> dict:
    """Latency, WASO, awakenings, fragmentation. Missing inputs stay None."""
    awakening_durations: list[float] = []
    if session.stage_intervals:
        for iv in session.stage_intervals:
            if iv["stage"] == "awake":
                awakening_durations.append(
                    (datetime.fromisoformat(iv["end_utc"]) - datetime.fromisoformat(iv["start_utc"])).total_seconds() / 60)
    frag = None
    if session.total_sleep_min and session.awakenings_count is not None:
        frag = round(session.awakenings_count / (session.total_sleep_min / 60), 2)  # awakenings/hour
    maintenance = None
    if session.total_sleep_min and session.waso_min is not None:
        span = session.total_sleep_min + session.waso_min
        if span > 0:
            maintenance = round(session.total_sleep_min / span * 100, 1)
    return {
        "sleep_latency_min": session.sleep_latency_min,
        "waso_min": session.waso_min,
        "awakenings_count": session.awakenings_count,
        "avg_awakening_min": round(statistics.mean(awakening_durations), 1) if awakening_durations else None,
        "longest_awakening_min": round(max(awakening_durations), 1) if awakening_durations else None,
        "fragmentation_per_hour": frag,
        "sleep_maintenance_efficiency_pct": maintenance,
    }


def duration_summary(sessions: list, workdays: set[str] | None = None) -> dict:
    """Rolling averages plus workday/free-day and nap-adjusted durations.

    `sessions` are ORM sessions ordered by date ascending (naps included).
    """
    mains = [s for s in sessions if not s.is_nap]
    tst_series = [s.total_sleep_min for s in mains]
    by_date_naps: dict[str, float] = {}
    for s in sessions:
        if s.is_nap and s.total_sleep_min:
            by_date_naps[s.session_date] = by_date_naps.get(s.session_date, 0) + s.total_sleep_min

    def day_name(date_str: str) -> str:
        return datetime.fromisoformat(date_str).strftime("%a").lower()[:3]

    workdays = workdays or {"mon", "tue", "wed", "thu", "fri"}
    work = [s.total_sleep_min for s in mains if s.total_sleep_min and day_name(s.session_date) in workdays]
    free = [s.total_sleep_min for s in mains if s.total_sleep_min and day_name(s.session_date) not in workdays]

    return {
        "nights": len(mains),
        "avg_7d_min": rolling_average(tst_series, 7),
        "avg_14d_min": rolling_average(tst_series, 14),
        "avg_28d_min": rolling_average(tst_series, 28),
        "workday_avg_min": round(statistics.mean(work), 1) if len(work) >= 3 else None,
        "freeday_avg_min": round(statistics.mean(free), 1) if len(free) >= 3 else None,
        "nap_adjusted_daily_min": {
            s.session_date: round((s.total_sleep_min or 0) + by_date_naps.get(s.session_date, 0), 1)
            for s in mains[-28:]
        },
    }
