"""Physiological baselines (HRV, resting HR, respiratory rate).

Baselines are personal: 7/28/60-day medians with median absolute deviation.
Observations are grouped by (source, method) and never blended across
materially different measurement methods.
"""

import statistics
from collections import defaultdict


def _median_mad(values: list[float]) -> tuple[float, float]:
    med = statistics.median(values)
    mad = statistics.median([abs(v - med) for v in values]) if len(values) > 1 else 0.0
    return med, mad


def baseline_summary(observations: list, metric: str, preferred_source: str | None = None) -> dict:
    """`observations` ordered by date ascending, each with .source/.method/.value/.date."""
    groups: dict[tuple[str, str], list] = defaultdict(list)
    for o in observations:
        if o.metric == metric:
            groups[(o.source, o.method or "unspecified")].append(o)

    if not groups:
        return {"status": "no_data", "metric": metric}

    out_groups = []
    for (source, method), obs in groups.items():
        values = [o.value for o in obs]
        entry = {
            "source": source, "method": method, "n": len(values),
            "current": values[-1], "current_date": obs[-1].date,
            "unit": obs[-1].unit,
        }
        for window, label in ((7, "median_7d"), (28, "median_28d"), (60, "median_60d")):
            recent = values[-window:]
            if len(recent) >= max(3, window // 4):
                med, mad = _median_mad(recent)
                entry[label] = round(med, 1)
                entry[f"mad_{label.split('_')[1]}"] = round(mad, 1)
        base = entry.get("median_28d") or entry.get("median_7d")
        if base is not None:
            entry["deviation_from_baseline"] = round(values[-1] - base, 1)
            mad = entry.get("mad_28d") or entry.get("mad_7d") or 0
            if mad > 0:
                z = (values[-1] - base) / (1.4826 * mad)
                entry["robust_z"] = round(z, 2)
                entry["flag"] = "notably_low" if z < -1.5 else "notably_high" if z > 1.5 else "within_normal_range"
        entry["confidence"] = "high" if len(values) >= 28 else "moderate" if len(values) >= 7 else "low"
        out_groups.append(entry)

    preferred = None
    if preferred_source:
        preferred = next((g for g in out_groups if g["source"] == preferred_source), None)
    if preferred is None:
        preferred = max(out_groups, key=lambda g: g["n"])

    result = {"status": "ok", "metric": metric, "groups": out_groups, "preferred": preferred}
    if len(out_groups) > 1:
        result["note"] = ("Multiple sources/methods present. Values are kept separate because "
                         "different measurement methods are not directly comparable. "
                         "You can change the preferred source in Settings.")
    return result
