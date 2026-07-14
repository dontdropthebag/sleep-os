"""Chronotype estimation.

Categories: earlier / intermediate / later / insufficient_data /
schedule_constrained. Based on free-day sleep midpoint corrected for
workday sleep debt (MSFsc-style), never on animal archetypes, and never
claimed to measure circadian phase directly.

Exclusion rules (excluded or down-weighted):
travel nights, illness, heavy alcohol, all-nighters/implausible nights,
low data quality, alarm-constrained free days (wake within 15 min of the
required wake time suggests an alarm).
"""

import statistics
from datetime import datetime
from zoneinfo import ZoneInfo

MIN_NIGHTS = 14
PREFERRED_NIGHTS = 28
EARLIER_MIDPOINT = 3.5 * 60  # local midpoint before 03:30
LATER_MIDPOINT = 5.5 * 60  # local midpoint after 05:30


def _midpoint_local_min(s) -> float | None:
    onset = s.sleep_onset_utc or s.in_bed_utc
    if not onset or not s.final_wake_utc:
        return None
    mid = onset + (s.final_wake_utc - onset) / 2
    local = mid.astimezone(ZoneInfo(s.timezone_name))
    m = local.hour * 60 + local.minute
    return m if m < 720 else m - 1440  # map evening midpoints to negative


def estimate_chronotype(sessions: list, habits_by_date: dict, workdays: set[str],
                        required_wake_local: str | None) -> dict:
    mains = [s for s in sessions if not s.is_nap and s.in_bed_utc and s.final_wake_utc]
    usable, excluded = [], []
    for s in mains:
        hb = habits_by_date.get(s.session_date)
        reasons = []
        if hb is not None:
            if hb.travel or hb.timezone_change:
                reasons.append("travel")
            if hb.illness:
                reasons.append("illness")
            if (hb.alcohol_units or 0) >= 3:
                reasons.append("alcohol")
        if s.time_in_bed_min is not None and (s.time_in_bed_min < 120 or s.time_in_bed_min > 16 * 60):
            reasons.append("implausible_duration")
        if s.data_quality_score is not None and s.data_quality_score < 40:
            reasons.append("low_data_quality")
        if reasons:
            excluded.append({"date": s.session_date, "reasons": reasons})
        else:
            usable.append(s)

    if len(usable) < MIN_NIGHTS:
        return {"category": "insufficient_data", "nights_used": len(usable),
                "nights_required": MIN_NIGHTS, "excluded": excluded, "confidence": "insufficient_data"}

    free_mids, work_tst, free_tst, alarm_free_days = [], [], [], 0
    for s in usable:
        day = datetime.fromisoformat(s.session_date).strftime("%a").lower()[:3]
        mid = _midpoint_local_min(s)
        if mid is None:
            continue
        if day in workdays:
            if s.total_sleep_min:
                work_tst.append(s.total_sleep_min)
        else:
            # Alarm-constrained free day: wake within 15 min of required wake
            if required_wake_local and s.final_wake_utc:
                wake_local = s.final_wake_utc.astimezone(ZoneInfo(s.timezone_name))
                req_h, req_m = map(int, required_wake_local.split(":"))
                if abs((wake_local.hour * 60 + wake_local.minute) - (req_h * 60 + req_m)) <= 15:
                    alarm_free_days += 1
                    continue
            free_mids.append(mid)
            if s.total_sleep_min:
                free_tst.append(s.total_sleep_min)

    if len(free_mids) < 4:
        return {"category": "schedule_constrained", "nights_used": len(usable),
                "free_nights_usable": len(free_mids), "alarm_constrained_free_days": alarm_free_days,
                "excluded": excluded, "confidence": "low",
                "note": "Too few unconstrained free days to separate preference from schedule."}

    msf = statistics.median(free_mids)  # free-day midpoint, minutes after midnight
    # Debt correction: if free-day sleep exceeds workday sleep, part of the
    # late free-day midpoint is recovery, not preference (MSFsc idea).
    msf_sc = msf
    if work_tst and free_tst:
        oversleep = statistics.median(free_tst) - statistics.median(work_tst)
        if oversleep > 0:
            msf_sc = msf - oversleep / 2

    if msf_sc < EARLIER_MIDPOINT:
        category = "earlier"
    elif msf_sc > LATER_MIDPOINT:
        category = "later"
    else:
        category = "intermediate"

    confidence = "high" if len(usable) >= PREFERRED_NIGHTS and len(free_mids) >= 8 else "moderate"
    h, m = int(msf_sc // 60) % 24, int(msf_sc % 60)
    return {
        "category": category,
        "corrected_midpoint_local": f"{h:02d}:{m:02d}",
        "free_day_midpoint_nights": len(free_mids),
        "nights_used": len(usable),
        "excluded": excluded,
        "alarm_constrained_free_days": alarm_free_days,
        "confidence": confidence,
        "method": "Median free-day sleep midpoint corrected for workday sleep debt (MSFsc-style). "
                  "This is a behavioural estimate, not a direct measurement of circadian phase.",
    }
