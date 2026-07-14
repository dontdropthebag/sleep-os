"""Sleep-need estimation and rolling sleep debt.

Until 28 valid nights exist, sleep need comes from the broad adult evidence
range (7-9 h) anchored to the user's preference. After that, personal need
is the median sleep on "good-outcome" nights: high morning energy, low
sleepiness, no illness/alcohol/travel disruption.

One long night does not erase chronic restriction — debt is reported over
rolling windows, never as "cleared" by a single recovery night.
"""

import statistics

REFERENCE_RANGE_MIN = (420, 540)  # 7-9 h adult guidance
PERSONAL_ESTIMATE_MIN_NIGHTS = 28
GOOD_ENERGY_THRESHOLD = 7
LOW_SLEEPINESS_THRESHOLD = 4


def estimate_sleep_need(sessions: list, checkins_by_date: dict, habits_by_date: dict,
                        preference_min: int = 480) -> dict:
    """Personal sleep-need estimate. sessions = main sleeps, date ascending."""
    valid = [s for s in sessions if not s.is_nap and s.total_sleep_min]
    if len(valid) < PERSONAL_ESTIMATE_MIN_NIGHTS:
        return {
            "status": "insufficient_data",
            "nights": len(valid),
            "nights_required": PERSONAL_ESTIMATE_MIN_NIGHTS,
            "sleep_need_min": max(REFERENCE_RANGE_MIN[0], min(preference_min, REFERENCE_RANGE_MIN[1])),
            "basis": "evidence_range_and_preference",
            "confidence": "low",
        }

    good_nights = []
    for s in valid:
        ci = checkins_by_date.get(s.session_date)
        hb = habits_by_date.get(s.session_date)
        if ci is None:
            continue
        if (ci.morning_energy or 0) >= GOOD_ENERGY_THRESHOLD and \
           (ci.daytime_sleepiness or 10) <= LOW_SLEEPINESS_THRESHOLD:
            if hb is not None and (hb.illness or hb.travel or (hb.alcohol_units or 0) > 2):
                continue
            good_nights.append(s.total_sleep_min)

    if len(good_nights) < 5:
        return {
            "status": "insufficient_good_nights",
            "nights": len(valid),
            "good_nights": len(good_nights),
            "sleep_need_min": max(REFERENCE_RANGE_MIN[0], min(preference_min, REFERENCE_RANGE_MIN[1])),
            "basis": "evidence_range_and_preference",
            "confidence": "low",
        }

    need = statistics.median(good_nights)
    need = max(REFERENCE_RANGE_MIN[0] - 30, min(need, REFERENCE_RANGE_MIN[1] + 30))
    return {
        "status": "ok",
        "nights": len(valid),
        "good_nights": len(good_nights),
        "sleep_need_min": round(need),
        "basis": "median_sleep_on_high_energy_low_sleepiness_nights",
        "confidence": "moderate" if len(good_nights) >= 10 else "low",
    }


def rolling_debt(sessions: list, sleep_need_min: float, window: int) -> dict:
    """Cumulative (need - actual) over the last `window` nights, floored at 0."""
    mains = [s for s in sessions if not s.is_nap and s.total_sleep_min is not None]
    recent = mains[-window:]
    if len(recent) < max(3, window // 2):
        return {"status": "insufficient_data", "nights": len(recent), "window": window}
    debt = sum(max(0.0, sleep_need_min - s.total_sleep_min) for s in recent)
    surplus = sum(max(0.0, s.total_sleep_min - sleep_need_min) for s in recent)
    # Surplus offsets at most half of accumulated debt: recovery sleep helps
    # but does not fully reverse restriction.
    net = max(0.0, debt - min(surplus, debt * 0.5))
    return {
        "status": "ok",
        "window": window,
        "nights": len(recent),
        "gross_debt_min": round(debt),
        "surplus_min": round(surplus),
        "net_debt_min": round(net),
        "note": "Recovery sleep offsets at most half of recent shortfall in this model.",
    }
