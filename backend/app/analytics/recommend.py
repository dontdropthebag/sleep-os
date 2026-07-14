"""Tonight's recommended sleep opportunity.

recommended lights-out = required wake - target sleep duration - expected latency

Adjustments are small and gradual: extra time in bed for recent debt is
capped, and the recommended shift from the user's recent habitual bedtime
is capped at 45 minutes per night to avoid abrupt multi-hour changes.
"""

import statistics
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

DEFAULT_LATENCY_MIN = 15
MAX_DEBT_EXTENSION_MIN = 45
MAX_NIGHTLY_SHIFT_MIN = 45


def _fmt(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def bedtime_recommendation(*, required_wake_local: str, tz_name: str,
                           sleep_need_min: float, need_confidence: str,
                           recent_latencies: list[float], net_debt_min: float | None,
                           recent_onsets_local_min: list[float] | None = None,
                           high_training_load: bool = False, illness: bool = False,
                           today: datetime | None = None) -> dict:
    tz = ZoneInfo(tz_name)
    now = today or datetime.now(tz)
    h, m = map(int, required_wake_local.split(":"))
    wake = now.astimezone(tz).replace(hour=h, minute=m, second=0, microsecond=0)
    if wake <= now.astimezone(tz):
        wake += timedelta(days=1)

    latency = statistics.median(recent_latencies) if recent_latencies else DEFAULT_LATENCY_MIN
    target = sleep_need_min
    adjustments = []
    if net_debt_min and net_debt_min > 60:
        extra = min(MAX_DEBT_EXTENSION_MIN, net_debt_min / 4)
        target += extra
        adjustments.append(f"+{round(extra)} min for recent sleep debt (capped; debt clears gradually)")
    if high_training_load:
        target += 20
        adjustments.append("+20 min for elevated training load")
    if illness:
        target += 30
        adjustments.append("+30 min while unwell")

    lights_out = wake - timedelta(minutes=target + latency)

    # Gradualism: don't ask for a jump of more than 45 min vs recent habit.
    shifted = False
    if recent_onsets_local_min:
        habitual = statistics.median(recent_onsets_local_min)
        lo_min = lights_out.hour * 60 + lights_out.minute
        lo_rel = lo_min if lo_min >= 720 else lo_min + 1440
        hab_rel = habitual if habitual >= 720 else habitual + 1440
        diff = lo_rel - hab_rel
        if abs(diff) > MAX_NIGHTLY_SHIFT_MIN:
            capped = hab_rel + (MAX_NIGHTLY_SHIFT_MIN if diff > 0 else -MAX_NIGHTLY_SHIFT_MIN)
            lights_out = lights_out.replace(hour=int(capped % 1440 // 60), minute=int(capped % 60))
            shifted = True
            adjustments.append(
                "Shift capped at 45 min/night from your recent bedtime; larger changes are "
                "recommended gradually with morning light and reduced evening light.")

    return {
        "wind_down_start_local": _fmt(lights_out - timedelta(minutes=45)),
        "lights_out_window_local": [_fmt(lights_out - timedelta(minutes=15)), _fmt(lights_out + timedelta(minutes=15))],
        "expected_sleep_onset_local": [_fmt(lights_out), _fmt(lights_out + timedelta(minutes=latency * 2))],
        "recommended_wake_window_local": [_fmt(wake - timedelta(minutes=15)), _fmt(wake + timedelta(minutes=15))],
        "target_sleep_min": round(target),
        "expected_latency_min": round(latency),
        "formula": "lights-out = required wake − target sleep − expected latency",
        "adjustments": adjustments,
        "gradual_shift_applied": shifted,
        "confidence": need_confidence if not shifted else "moderate",
    }
