"""Generic sleep CSV adapter.

Accepts a simple CSV with ISO-8601 timestamps::

    date,start,end,total_sleep_min,timezone,hrv_rmssd,resting_hr,...

Required: ``start``, ``end`` (ISO-8601, with offset or paired with
``timezone``). Everything else optional and reported as missing when absent.
Also used for Oura/WHOOP-style flat CSV exports until dedicated adapters
land (Phase 2) — the column map below covers their common field names.
"""

import csv
import io
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from ..provenance import Confidence, MeasurementKind, Source, field_meta
from .base import BaseAdapter, ParsedSession, ParseIssue, ParseResult, register

COLUMN_ALIASES = {
    "start": {"start", "bedtime_start", "sleep_onset", "in_bed", "from"},
    "end": {"end", "bedtime_end", "wake_time", "out_of_bed", "to"},
    "total_sleep_min": {"total_sleep_min", "total_sleep_duration_min", "asleep_min"},
    "hrv_rmssd": {"hrv_rmssd", "average_hrv", "hrv"},
    "resting_hr": {"resting_hr", "lowest_heart_rate", "resting_heart_rate"},
    "resp_rate": {"resp_rate", "respiratory_rate", "average_breath"},
    "timezone": {"timezone", "tz"},
    "is_nap": {"is_nap", "nap"},
}


def _find(cols: list[str], canonical: str) -> str | None:
    lower = {c.lower().strip(): c for c in cols}
    for alias in COLUMN_ALIASES.get(canonical, set()):
        if alias in lower:
            return lower[alias]
    return None


def _iso(s: str | None, tz_name: str | None) -> datetime | None:
    if not s or not s.strip():
        return None
    try:
        dt = datetime.fromisoformat(s.strip())
    except ValueError:
        return None
    if dt.tzinfo is None:
        try:
            dt = dt.replace(tzinfo=ZoneInfo(tz_name or "UTC"))
        except Exception:
            dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@register
class GenericCsvAdapter(BaseAdapter):
    name = Source.GENERIC_CSV.value
    parser_version = "1.0.0"

    @classmethod
    def sniff(cls, filename: str, data: bytes) -> bool:
        if not filename.lower().endswith(".csv"):
            return False
        head = data[:500].decode("utf-8", errors="replace").splitlines()
        if not head:
            return False
        cols = [c.strip() for c in head[0].split(",")]
        return _find(cols, "start") is not None and _find(cols, "end") is not None

    @classmethod
    def parse(cls, filename: str, data: bytes) -> ParseResult:
        result = ParseResult(source=cls.name, parser_version=cls.parser_version)
        reader = csv.DictReader(io.StringIO(data.decode("utf-8", errors="replace")))
        cols = reader.fieldnames or []
        col = {k: _find(cols, k) for k in COLUMN_ALIASES}
        if not col["start"] or not col["end"]:
            result.issues.append(ParseIssue("error", "CSV must contain start and end columns"))
            return result

        for i, row in enumerate(reader, start=2):
            tz_name = (row.get(col["timezone"]) or "UTC").strip() if col["timezone"] else "UTC"
            start = _iso(row.get(col["start"]), tz_name)
            end = _iso(row.get(col["end"]), tz_name)
            if start is None or end is None or end <= start:
                result.issues.append(ParseIssue("error", f"Row {i}: missing or invalid start/end"))
                continue
            tib = (end - start).total_seconds() / 60

            def num(key: str) -> float | None:
                c = col.get(key)
                if not c:
                    return None
                try:
                    return float(row[c]) if row.get(c, "").strip() else None
                except (ValueError, TypeError):
                    return None

            tst = num("total_sleep_min")
            if tst is not None and tst > tib:
                tst = tib
            physio = []
            for metric, method, unit in (
                ("hrv_rmssd", "unknown_csv_method", "ms"),
                ("resting_hr", "unknown_csv_method", "bpm"),
                ("resp_rate", "unknown_csv_method", "breaths/min"),
            ):
                v = num(metric)
                if v is not None:
                    physio.append({
                        "metric": metric, "value": v, "unit": unit, "method": method,
                        "kind": MeasurementKind.DEVICE_ESTIMATED.value,
                        "confidence": Confidence.MODERATE.value,
                        "original_field": col.get(metric),
                    })

            missing = [m for m, v in (("total_sleep_min", tst), ("hrv_rmssd", num("hrv_rmssd")),
                                      ("stage_intervals", None)) if v is None]
            is_nap_raw = (row.get(col["is_nap"]) or "").strip().lower() if col["is_nap"] else ""
            local_start = start.astimezone(ZoneInfo(tz_name)) if tz_name else start
            is_nap = is_nap_raw in ("1", "true", "yes") or (
                is_nap_raw == "" and tib < 180 and 9 <= local_start.hour < 20)

            result.sessions.append(ParsedSession(
                source=cls.name,
                source_session_id=f"{filename}:{i}",
                timezone_name=tz_name,
                in_bed_utc=start,
                sleep_onset_utc=None,
                final_wake_utc=end,
                out_of_bed_utc=None,
                time_in_bed_min=round(tib, 1),
                total_sleep_min=round(tst, 1) if tst is not None else None,
                is_nap=is_nap,
                field_provenance={
                    "in_bed_utc": field_meta(col["start"], "datetime", MeasurementKind.MEASURED, Confidence.MODERATE),
                    "final_wake_utc": field_meta(col["end"], "datetime", MeasurementKind.MEASURED, Confidence.MODERATE),
                    "total_sleep_min": field_meta(col.get("total_sleep_min") or "n/a", "min",
                                                  MeasurementKind.DEVICE_ESTIMATED),
                },
                raw_payload=dict(row),
                missing_metrics=missing,
                physio=physio,
            ))
        return result
