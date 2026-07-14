"""Sleep as Android importer.

Format notes (documented assumptions, verified against public SaA export docs):

* ``sleep-export.csv`` contains one *header line per record* because the
  actigraphy time columns differ per night::

      Id,Tz,From,To,Sched,Hours,Rating,Comment,Framerate,Snore,Noise,Cycles,
      DeepSleep,LenAdjust,Geo,"23:45","23:50",...,"Event","Event",...

  followed by one or more data lines for that record (multi-row records
  happen when SaA splits actigraphy/event payloads). We group every data
  line under the most recent header line and merge them.

* Dates are ``dd. MM. yyyy H:mm`` in the record's own ``Tz`` timezone.
  Decimal values may use dot or comma separators ("8.930" / "7,532").
* Records typically have **two data rows**: the first carries the movement
  (actigraphy) values under the time columns, the second — with empty
  scalar cells — carries the noise timeline under the same columns.
  (Verified against a real 2026 export.)
* ``Event`` cells look like ``LABEL-<epoch ms>`` or ``LABEL-<epoch ms>-<value>``
  (e.g. ``DEEP_START-1471410720000``, ``LUX-...-12.0``). Observed labels
  include DEEP/LIGHT/REM/AWAKE_START/_END, DHA (per-sample timestamps),
  LUX, DEVICE, SNORING, TALK, BROKEN_START/_END, TRACKING_PAUSED/RESUMED,
  TRACKING_STOPPED_BY_USER, LOW_BATTERY and ALARM_* events.
* ``Snore`` is seconds of detected snoring: ``-1`` = unavailable, ``0`` is a
  real "no snoring detected" measurement. ``Rating`` uses ``0.0`` for
  "not rated" (scale is 0.25–5.0 when set). ``DeepSleep`` is a 0..1
  device-estimated fraction (-1 = unavailable).

The original rows are preserved verbatim in ``raw_payload`` before any
normalisation. Missing values are reported as missing — never invented.
"""

import csv
import io
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from ..provenance import Confidence, MeasurementKind, Source, field_meta
from ..security.safe_zip import UnsafeZipError, open_zip, read_entry
from .base import BaseAdapter, ParsedSession, ParseIssue, ParseResult, register

HEADER_FIELDS = [
    "Id", "Tz", "From", "To", "Sched", "Hours", "Rating", "Comment",
    "Framerate", "Snore", "Noise", "Cycles", "DeepSleep", "LenAdjust", "Geo",
]

STAGE_EVENTS = {
    "DEEP_START": ("deep", "start"), "DEEP_END": ("deep", "end"),
    "LIGHT_START": ("light", "start"), "LIGHT_END": ("light", "end"),
    "REM_START": ("rem", "start"), "REM_END": ("rem", "end"),
    "AWAKE_START": ("awake", "start"), "AWAKE_END": ("awake", "end"),
}

MAX_PLAUSIBLE_TIB_MIN = 18 * 60
NAP_MAX_MIN = 3 * 60
NAP_START_HOURS = range(9, 20)  # naps start 09:00–19:59 local


def _num(s: str | None) -> float | None:
    if s is None:
        return None
    s = s.strip().replace(",", ".")
    if s in ("", "-1", "-1.0"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _dt(s: str | None, tz: ZoneInfo) -> datetime | None:
    if not s or not s.strip():
        return None
    for fmt in ("%d. %m. %Y %H:%M", "%d. %m. %Y %H:%M:%S"):
        try:
            return datetime.strptime(s.strip(), fmt).replace(tzinfo=tz).astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def _parse_events(cells: list[str]) -> list[dict]:
    events = []
    for cell in cells:
        cell = cell.strip()
        if not cell or "-" not in cell:
            continue
        parts = cell.split("-")
        label = parts[0]
        try:
            ts_ms = int(parts[1])
        except (IndexError, ValueError):
            continue
        ev = {"label": label, "t_utc": datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()}
        if len(parts) > 2:
            ev["value"] = _num(parts[2])
        events.append(ev)
    return events


def _stage_intervals(events: list[dict]) -> list[dict]:
    """Pair *_START/*_END events into device-estimated stage intervals."""
    intervals: list[dict] = []
    open_stage: dict[str, str] = {}
    for ev in sorted(events, key=lambda e: e["t_utc"]):
        info = STAGE_EVENTS.get(ev["label"])
        if not info:
            continue
        stage, edge = info
        if edge == "start":
            open_stage[stage] = ev["t_utc"]
        elif stage in open_stage:
            intervals.append({"stage": stage, "start_utc": open_stage.pop(stage), "end_utc": ev["t_utc"]})
    return intervals


@register
class SleepAsAndroidAdapter(BaseAdapter):
    name = Source.SLEEP_AS_ANDROID.value
    parser_version = "1.0.0"

    @classmethod
    def sniff(cls, filename: str, data: bytes) -> bool:
        fn = filename.lower()
        if fn.endswith(".zip"):
            try:
                zf = open_zip(data)
            except UnsafeZipError:
                return False
            names = [n.rsplit("/", 1)[-1] for n in zf.namelist()]
            return "sleep-export.csv" in names or "sleep-export.backup.csv" in names
        head = data[:200].decode("utf-8", errors="replace")
        return fn.endswith(".csv") and head.startswith("Id,Tz,From,To,Sched")

    @classmethod
    def parse(cls, filename: str, data: bytes) -> ParseResult:
        result = ParseResult(source=cls.name, parser_version=cls.parser_version)
        csv_bytes: bytes | None = None

        if filename.lower().endswith(".zip"):
            try:
                zf = open_zip(data)
            except UnsafeZipError as e:
                result.issues.append(ParseIssue("error", str(e)))
                return result
            by_base = {n.rsplit("/", 1)[-1]: n for n in zf.namelist()}
            csv_name = by_base.get("sleep-export.csv") or by_base.get("sleep-export.backup.csv")
            if not csv_name:
                result.issues.append(ParseIssue(
                    "error", "ZIP does not contain sleep-export.csv or sleep-export.backup.csv"))
                return result
            csv_bytes = read_entry(zf, csv_name)
            if "noise.json" in by_base:
                result.extras["noise_json"] = read_entry(zf, by_base["noise.json"]).decode("utf-8", "replace")
            if "prefs.xml" in by_base:
                result.extras["prefs_xml_present"] = True
            if "alarms.json" in by_base:
                result.extras["alarms_json_present"] = True
            audio_files = [n for n in zf.namelist() if "/rec" in n or n.startswith("rec")]
            if audio_files:
                result.extras["audio_files"] = audio_files
                result.issues.append(ParseIssue(
                    "info", f"{len(audio_files)} audio file(s) present; audio analysis is a Phase-3 feature "
                            "and raw audio is not retained."))
        else:
            csv_bytes = data

        cls._parse_csv(csv_bytes.decode("utf-8", errors="replace"), result)
        return result

    # ------------------------------------------------------------------
    @classmethod
    def _parse_csv(cls, text: str, result: ParseResult) -> None:
        rows = list(csv.reader(io.StringIO(text)))
        # Group rows into records: each header line starts a new record.
        records: list[dict] = []
        current: dict | None = None
        for i, row in enumerate(rows):
            if not row or all(not c.strip() for c in row):
                continue
            if row[0] == "Id" and row[1:3] == ["Tz", "From"]:
                current = {"header": row, "data_rows": [], "line": i + 1}
                records.append(current)
            elif current is None:
                result.issues.append(ParseIssue("error", f"Line {i + 1}: data row before any header row"))
            else:
                current["data_rows"].append(row)

        if not records:
            result.issues.append(ParseIssue("error", "No Sleep as Android records found in CSV"))
            return

        for rec in records:
            cls._parse_record(rec, result)

    @classmethod
    def _parse_record(cls, rec: dict, result: ParseResult) -> None:
        header, data_rows = rec["header"], rec["data_rows"]
        if not data_rows:
            result.issues.append(ParseIssue("warning", f"Line {rec['line']}: header row without data row"))
            return
        # Merge multi-row records: first row wins for scalar fields; movement
        # and event columns are concatenated across rows.
        row = data_rows[0]
        fields = dict(zip(HEADER_FIELDS, row[: len(HEADER_FIELDS)]))
        raw_payload = {"header": header, "rows": data_rows}

        tz_name = fields.get("Tz", "").strip() or "UTC"
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            result.issues.append(ParseIssue("warning", f"Unknown timezone {tz_name!r}; assuming UTC",
                                            record_ref=fields.get("Id")))
            tz, tz_name = ZoneInfo("UTC"), "UTC"

        start = _dt(fields.get("From"), tz)
        end = _dt(fields.get("To"), tz)
        if start is None or end is None:
            result.issues.append(ParseIssue("error", "Missing or malformed From/To timestamp",
                                            record_ref=fields.get("Id")))
            return
        if end <= start:
            result.issues.append(ParseIssue("error", "Record ends before it starts",
                                            record_ref=fields.get("Id")))
            return

        # Split trailing columns into per-row timelines and event cells.
        # Row 0 carries movement (actigraphy) under the time columns; later
        # rows (empty scalar cells) carry the noise timeline under the same
        # columns. Event cells are merged across all rows.
        movement, noise_timeline, event_cells = [], [], []
        n_scalar = len(HEADER_FIELDS)
        for row_idx, r in enumerate(data_rows):
            for j, cell in enumerate(r[n_scalar:]):
                col = header[n_scalar + j] if n_scalar + j < len(header) else "Event"
                if col == "Event":
                    event_cells.append(cell)
                else:
                    v = _num(cell)
                    if v is not None:
                        target = movement if row_idx == 0 else noise_timeline
                        target.append({"t_local": col, "value": v})
        events = _parse_events(event_cells)
        stage_intervals = _stage_intervals(events)

        awake_min = sum(
            (datetime.fromisoformat(iv["end_utc"]) - datetime.fromisoformat(iv["start_utc"])).total_seconds() / 60
            for iv in stage_intervals if iv["stage"] == "awake"
        )
        awakenings = sum(1 for iv in stage_intervals if iv["stage"] == "awake") or None

        tib_min = (end - start).total_seconds() / 60
        hours = _num(fields.get("Hours"))
        # "Hours" is SaA's tracked duration (pauses/adjustments applied), not
        # actual sleep — it does not subtract awake periods. Where awake
        # events exist we subtract them so TST means "asleep", keeping
        # efficiency honest instead of a flat ~100%.
        tst_min = hours * 60 if hours and hours > 0 else None
        if tst_min is not None and awake_min:
            tst_min = max(0.0, tst_min - awake_min)
        if tst_min is not None and tst_min > tib_min:
            tst_min = tib_min  # device estimate cannot exceed time in bed

        missing = []
        if tst_min is None:
            missing.append("total_sleep_min")
        if not stage_intervals:
            missing.append("stage_intervals")
            missing.append("waso_min")
        missing.append("sleep_latency_min")  # SaA does not export latency directly

        if tib_min > MAX_PLAUSIBLE_TIB_MIN:
            result.issues.append(ParseIssue(
                "warning", f"Implausible time in bed ({tib_min / 60:.1f} h); review before committing",
                record_ref=fields.get("Id")))

        start_local = start.astimezone(tz)
        is_nap = tib_min < NAP_MAX_MIN and start_local.hour in NAP_START_HOURS

        deep_frac = _num(fields.get("DeepSleep"))
        if deep_frac is not None and not (0 <= deep_frac <= 1):
            deep_frac = None
        # Snore: -1/blank = unavailable (_num -> None); 0 is a real measurement.
        snore_s = _num(fields.get("Snore"))
        # Rating: SaA exports 0.0 when the night was never rated.
        rating = _num(fields.get("Rating"))
        if rating is not None and rating <= 0:
            rating = None
        comment = (fields.get("Comment") or "").strip()
        tags = [w[1:] for w in comment.split() if w.startswith("#")]

        prov = {
            "in_bed_utc": field_meta("From", "datetime", MeasurementKind.MEASURED, Confidence.HIGH),
            "final_wake_utc": field_meta("To", "datetime", MeasurementKind.MEASURED, Confidence.HIGH),
            "total_sleep_min": field_meta("Hours − AWAKE events", "min", MeasurementKind.DEVICE_ESTIMATED),
            "stage_intervals": field_meta("Event(DEEP/LIGHT/REM/AWAKE)", None, MeasurementKind.DEVICE_ESTIMATED, Confidence.LOW),
            "deep_sleep_fraction": field_meta("DeepSleep", "fraction", MeasurementKind.DEVICE_ESTIMATED, Confidence.LOW),
            "snore_minutes": field_meta("Snore", "min", MeasurementKind.DEVICE_ESTIMATED, Confidence.LOW),
            "noise_level": field_meta("Noise", "relative", MeasurementKind.MEASURED, Confidence.MODERATE),
            "user_rating": field_meta("Rating", "0-5", MeasurementKind.SELF_REPORTED, Confidence.HIGH),
            "movement_timeline": field_meta("actigraphy columns (row 1)", "relative", MeasurementKind.MEASURED),
            "noise_timeline": field_meta("noise columns (row 2)", "relative", MeasurementKind.MEASURED),
        }

        result.sessions.append(ParsedSession(
            source=cls.name,
            source_session_id=fields.get("Id"),
            timezone_name=tz_name,
            in_bed_utc=start,
            sleep_onset_utc=None,  # SaA does not export onset; never invent it
            final_wake_utc=end,
            out_of_bed_utc=None,
            time_in_bed_min=round(tib_min, 1),
            total_sleep_min=round(tst_min, 1) if tst_min is not None else None,
            sleep_latency_min=None,
            waso_min=round(awake_min, 1) if stage_intervals else None,
            awakenings_count=awakenings,
            stage_intervals=stage_intervals or None,
            is_nap=is_nap,
            user_rating=rating,
            comments=comment or None,
            tags=tags or None,
            snore_minutes=round(snore_s / 60, 1) if snore_s is not None and snore_s >= 0 else None,
            noise_level=_num(fields.get("Noise")),
            cycles=int(c) if (c := _num(fields.get("Cycles"))) and c > 0 else None,
            deep_sleep_fraction=deep_frac,
            movement_timeline=movement or None,
            noise_timeline=noise_timeline or None,
            event_timeline=events or None,
            field_provenance=prov,
            raw_payload=raw_payload,
            missing_metrics=missing,
        ))
