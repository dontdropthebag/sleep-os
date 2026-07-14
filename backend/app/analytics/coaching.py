"""Morning coaching screen.

Fixed hierarchy: what happened → what matters most (ranked: doing well /
needs improvement / not doing well) → likely contributors (with confidence)
→ today's capacity → today's actions (≤3) → tonight's target → one thing
to learn.

Tone rules: no shame, no alarmism, no false certainty, no ten-item
protocols. Normal nightly variation is treated as normal. The user already
trains 3-4x/week and eats well — actions focus on sleep behaviour and
scheduling, not generic exercise/nutrition advice.
"""

from .metrics import sleep_efficiency
from .quality import confidence_label

MAX_SUMMARY_CHARS = 200


def _hm(minutes: float | None) -> str:
    if minutes is None:
        return "unknown"
    return f"{int(minutes // 60)}h {int(minutes % 60):02d}m"


def _quality_reason(session) -> str:
    """Plain-language justification for the data-quality label."""
    if session is None or not session.quality_breakdown:
        return "No quality breakdown available."
    b = session.quality_breakdown
    good, weak = [], []
    checks = [
        ("core_timing", "start/end times directly recorded", "start or end time missing"),
        ("duration_present", "sleep duration present", "sleep duration missing"),
        ("stage_data", "stage data available", "no stage data"),
        ("plausibility", "values are plausible", "implausible values"),
        ("timezone_certainty", "timezone known", "timezone uncertain"),
        ("hrv_available", "HRV recorded", "no HRV device yet"),
    ]
    for key, ok_text, bad_text in checks:
        v = b.get(key, {}).get("value", 0)
        (good if v >= 75 else weak).append(ok_text if v >= 75 else bad_text)
    reason = "Based on: " + ", ".join(good[:4]) + "."
    if weak:
        reason += " Limits: " + ", ".join(weak[:2]) + "."
    return reason


def _rank_findings(*, session, regularity, debt, hrv_baseline, snore_avg_min,
                   sleep_need_min, efficiency) -> dict:
    """Expert sleep-hygiene ranking into doing well / improve / not doing well."""
    well, improve, poor = [], [], []

    # Duration vs need
    if session and session.total_sleep_min is not None:
        gap = sleep_need_min - session.total_sleep_min
        if gap <= 30:
            well.append({"finding": f"Sleep duration ({_hm(session.total_sleep_min)}) met your "
                                    f"{_hm(sleep_need_min)} target — the single biggest lever for "
                                    "energy, focus and recovery.", "confidence": "moderate"})
        elif gap <= 90:
            improve.append({"finding": f"About {_hm(gap)} short of target last night. Fine once in a "
                                       "while; watch that it doesn't become the norm.",
                            "confidence": "moderate"})
        else:
            poor.append({"finding": f"Sleep ran {_hm(gap)} under target — expect reduced focus and "
                                    "slower recovery today.", "confidence": "moderate"})

    # Efficiency
    if efficiency is not None:
        if efficiency >= 85:
            well.append({"finding": f"Sleep efficiency {efficiency}% — you fall and stay asleep well "
                                    "once in bed.", "confidence": "moderate"})
        elif efficiency >= 75:
            improve.append({"finding": f"Efficiency {efficiency}% — some awake time in bed. A wind-down "
                                       "routine and only going to bed when sleepy usually lift this.",
                            "confidence": "moderate"})
        else:
            poor.append({"finding": f"Efficiency {efficiency}% — a lot of awake time in bed.",
                         "confidence": "moderate"})

    # Regularity — the classic high-performance weak spot
    if regularity.get("status") == "ok":
        wake_sd = regularity.get("wake_sd_min", 0)
        onset_sd = regularity.get("onset_sd_min", 0)
        if wake_sd <= 45 and onset_sd <= 45:
            well.append({"finding": f"Consistent schedule (wake varies ±{round(wake_sd)} min) — this "
                                    "anchors your circadian rhythm.", "confidence": "moderate"})
        elif wake_sd <= 90:
            improve.append({"finding": f"Wake time varies ±{round(wake_sd)} min. Tightening this to "
                                       "under 45 min is the highest-value change for daytime energy.",
                            "confidence": "moderate"})
        else:
            poor.append({"finding": f"Wake time varies ±{round(wake_sd)} min — an irregular schedule "
                                    "works against everything else you do well. A fixed wake time, "
                                    "even after a late night, is the fix.", "confidence": "moderate"})

    # Sleep debt
    if debt.get("status") == "ok":
        nd = debt.get("net_debt_min", 0)
        if nd < 60:
            well.append({"finding": "Essentially no rolling sleep debt.", "confidence": "moderate"})
        elif nd <= 180:
            improve.append({"finding": f"Carrying ~{_hm(nd)} of sleep debt over the last "
                                       f"{debt['window']} nights. Slightly earlier lights-out clears "
                                       "it within a week.", "confidence": "moderate"})
        else:
            poor.append({"finding": f"~{_hm(nd)} of sleep debt over {debt['window']} nights — enough "
                                    "to blunt focus, mood and training recovery.",
                         "confidence": "moderate"})

    # Snoring
    if snore_avg_min is not None:
        if snore_avg_min < 10:
            well.append({"finding": f"Snoring is low (~{round(snore_avg_min)} min/night average).",
                         "confidence": "low"})
        elif snore_avg_min < 30:
            improve.append({"finding": f"Snoring averages ~{round(snore_avg_min)} min/night — worth "
                                       "tagging alcohol, congestion and sleeping position to find the "
                                       "driver.", "confidence": "low"})
        else:
            poor.append({"finding": f"Snoring averages ~{round(snore_avg_min)} min/night.",
                         "confidence": "low"})

    # HRV
    if hrv_baseline and hrv_baseline.get("status") == "ok":
        pref = hrv_baseline["preferred"]
        if pref.get("flag") == "notably_low":
            poor.append({"finding": f"HRV ({pref['current']} {pref.get('unit') or ''}) is below your "
                                    "28-day baseline.", "confidence": pref.get("confidence", "low")})

    return {"doing_well": well[:3], "needs_improvement": improve[:3], "not_doing_well": poor[:3]}


def build_morning_coaching(*, session, duration_summary: dict, regularity: dict,
                           debt: dict, hrv_baseline: dict | None, habits, checkin,
                           tonight: dict | None, sleep_need_min: float,
                           snore_avg_min: float | None = None) -> dict:
    eff = sleep_efficiency(session.total_sleep_min, session.time_in_bed_min) if session else None

    # ---- What happened (≤200 chars) -------------------------------------
    if session:
        what_happened = (f"In bed {_hm(session.time_in_bed_min)}, asleep {_hm(session.total_sleep_min)}"
                         + (f" ({eff}% efficiency)" if eff is not None else "")
                         + f". Data quality: {confidence_label(session.data_quality_score)}.")
        if len(what_happened) > MAX_SUMMARY_CHARS:
            what_happened = what_happened[:MAX_SUMMARY_CHARS - 1] + "…"
    else:
        what_happened = "No sleep session was recorded for last night."

    # ---- What matters most (ranked) --------------------------------------
    ranked = _rank_findings(session=session, regularity=regularity, debt=debt,
                            hrv_baseline=hrv_baseline, snore_avg_min=snore_avg_min,
                            sleep_need_min=sleep_need_min, efficiency=eff)

    # ---- Likely contributors ---------------------------------------------
    contributors = []
    if habits:
        if (habits.alcohol_units or 0) > 0:
            contributors.append({"factor": f"Alcohol ({habits.alcohol_units} units)",
                                 "confidence": "moderate",
                                 "note": "Alcohol commonly reduces sleep quality and HRV."})
        if habits.last_caffeine_time and habits.last_caffeine_time >= "14:00":
            contributors.append({"factor": f"Caffeine as late as {habits.last_caffeine_time}",
                                 "confidence": "low"})
        if habits.last_meal_time and habits.last_meal_time >= "21:00":
            contributors.append({"factor": f"Late final meal ({habits.last_meal_time})", "confidence": "low"})
        if habits.travel or habits.timezone_change:
            contributors.append({"factor": "Travel / timezone change", "confidence": "moderate",
                                 "note": "Temporary disruption — not a baseline change."})
        if habits.illness:
            contributors.append({"factor": "Illness", "confidence": "moderate"})
    if not contributors:
        contributors.append({"factor": "No tagged behaviours for last night",
                             "confidence": "insufficient_data",
                             "note": "Tag habits to help separate causes from noise."})

    # ---- Today's capacity -------------------------------------------------
    slept_ok = session is not None and session.total_sleep_min is not None and \
        session.total_sleep_min >= sleep_need_min - 60
    hrv_flag = (hrv_baseline or {}).get("preferred", {}).get("flag") if hrv_baseline and \
        hrv_baseline.get("status") == "ok" else None
    hrv_ok = hrv_flag != "notably_low"

    def cap(good: bool, mixed_reason: bool) -> str:
        return "typical" if good else ("somewhat reduced" if mixed_reason else "reduced")

    capacity = {
        "physical_recovery": cap(slept_ok and hrv_ok, slept_ok or hrv_ok),
        "cognitive_energy": cap(slept_ok, hrv_ok),
        "stress_resilience": cap(slept_ok and hrv_ok, slept_ok or hrv_ok),
        "sleepiness_risk": "elevated" if (debt.get("net_debt_min") or 0) > 120 or not slept_ok else "typical",
        "training_readiness": cap(slept_ok and hrv_ok, slept_ok or hrv_ok),
        "note": "System-derived estimates from sleep and physiology trends — not medical "
                "measurements. Your training and nutrition are assumed handled; these reflect "
                "sleep's contribution only.",
    }
    if checkin and checkin.morning_energy is not None:
        capacity["your_reported_morning_energy"] = f"{checkin.morning_energy}/10"

    # ---- Today's actions (≤3, sleep-focused) ------------------------------
    actions = []
    if regularity.get("status") == "ok" and regularity.get("wake_sd_min", 0) > 45:
        actions.append("Anchor tomorrow's wake time to your target, then get outdoor light within an hour.")
    if not slept_ok:
        actions.append("Protect tonight's sleep opportunity — front-load demanding work earlier today.")
    if (debt.get("net_debt_min") or 0) > 120:
        actions.append("Bring lights-out forward ~30 min tonight; debt clears through consistency, not one long sleep.")
    if not actions:
        actions.append("Nothing needs fixing today — keep your current routine.")
    actions = actions[:3]

    return {
        "what_happened": what_happened,
        "data_quality_reason": _quality_reason(session),
        "what_matters_most": ranked,
        "likely_contributors": contributors[:4],
        "todays_capacity": capacity,
        "todays_actions": actions,
        "tonights_target": tonight,
        "one_thing_to_learn": (
            "Tag tonight's caffeine timing — a few tagged nights make the habit-impact "
            "analysis meaningful." if not habits or not habits.last_caffeine_time else
            "Consider a simple experiment: consistent wake time for 7 days."),
    }
