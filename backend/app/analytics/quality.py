"""Data-quality scoring for a single night (0-100 + component breakdown).

The score reflects how much we can trust the record — never how "well"
the user slept. Missing or uncertain data is surfaced, not hidden.
"""

SOURCE_RELIABILITY = {
    "sleep_as_android": 70,
    "oura": 80,
    "whoop": 80,
    "health_connect": 65,
    "generic_csv": 55,
    "generic_json": 55,
    "manual": 45,
}


def score_session(session, physio_metrics: set[str] | None = None,
                  conflicting_sources: bool = False) -> tuple[float, dict]:
    physio_metrics = physio_metrics or set()
    parts: dict[str, float] = {}

    parts["source_reliability"] = SOURCE_RELIABILITY.get(session.source, 50)
    parts["core_timing"] = 100 if (session.in_bed_utc and session.final_wake_utc) else 20
    parts["duration_present"] = 100 if session.total_sleep_min is not None else 30
    parts["stage_data"] = 100 if session.stage_intervals else 40
    parts["hr_coverage"] = 100 if "resting_hr" in physio_metrics else 40
    parts["hrv_available"] = 100 if "hrv_rmssd" in physio_metrics else 40
    parts["timezone_certainty"] = 100 if session.timezone_name and session.timezone_name != "UTC" else 60

    plausible = True
    if session.time_in_bed_min is not None and not (60 <= session.time_in_bed_min <= 18 * 60):
        plausible = False
    if session.total_sleep_min and session.time_in_bed_min and \
            session.total_sleep_min > session.time_in_bed_min + 1:
        plausible = False
    parts["plausibility"] = 100 if plausible else 10
    parts["manual_edits"] = 70 if session.manually_edited else 100
    parts["source_agreement"] = 50 if conflicting_sources else 100

    weights = {
        "source_reliability": 1.5, "core_timing": 2.0, "duration_present": 1.5,
        "stage_data": 0.75, "hr_coverage": 0.5, "hrv_available": 0.5,
        "timezone_certainty": 0.75, "plausibility": 2.0, "manual_edits": 0.25,
        "source_agreement": 0.75,
    }
    total_w = sum(weights.values())
    score = sum(parts[k] * weights[k] for k in parts) / total_w
    if not plausible:
        score = min(score, 45.0)  # implausible records are never above low confidence
    breakdown = {k: {"value": parts[k], "weight": weights[k]} for k in parts}
    return round(score, 1), breakdown


def confidence_label(score: float | None) -> str:
    if score is None:
        return "insufficient_data"
    if score >= 75:
        return "high"
    if score >= 55:
        return "moderate"
    return "low"
