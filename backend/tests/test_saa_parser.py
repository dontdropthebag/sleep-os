from datetime import datetime
from zoneinfo import ZoneInfo

from app.adapters.sleep_as_android import SleepAsAndroidAdapter as A
from tests.conftest import epoch_ms, make_zip, saa_record


def _parse_csv(text: str):
    return A.parse("sleep-export.csv", text.encode())


def test_valid_zip_parses():
    tz = ZoneInfo("Europe/London")
    csv = saa_record("100", "Europe/London",
                     datetime(2026, 6, 1, 23, 30, tzinfo=tz), datetime(2026, 6, 2, 7, 0, tzinfo=tz),
                     hours=7.0, movement=[10.0, 20.0, 5.0])
    result = A.parse("export.zip", make_zip({"sleep-export.csv": csv.encode()}))
    assert len(result.sessions) == 1
    s = result.sessions[0]
    assert s.time_in_bed_min == 450.0
    assert s.total_sleep_min == 420.0
    assert s.timezone_name == "Europe/London"
    assert len(s.movement_timeline) == 3
    assert s.raw_payload["rows"]  # original preserved


def test_backup_csv_accepted():
    tz = ZoneInfo("UTC")
    csv = saa_record("101", "UTC", datetime(2026, 6, 1, 23, 0, tzinfo=tz),
                     datetime(2026, 6, 2, 6, 0, tzinfo=tz), hours=6.5)
    result = A.parse("export.zip", make_zip({"sleep-export.backup.csv": csv.encode()}))
    assert len(result.sessions) == 1


def test_missing_sleep_export_csv():
    result = A.parse("export.zip", make_zip({"noise.json": b"{}"}))
    assert result.sessions == []
    assert any("does not contain" in i.message for i in result.issues)


def test_malformed_csv_reports_errors():
    result = _parse_csv('"garbage","row","without","header"\n')
    assert result.sessions == []
    assert any(i.severity == "error" for i in result.issues)


def test_malformed_dates_skipped_with_error():
    tz = ZoneInfo("UTC")
    good = saa_record("1", "UTC", datetime(2026, 6, 1, 23, 0, tzinfo=tz),
                      datetime(2026, 6, 2, 6, 0, tzinfo=tz), hours=6)
    bad = good.replace("01. 06. 2026 23:00", "not-a-date").replace('"1"', '"2"', 1)
    result = _parse_csv(good + bad)
    assert len(result.sessions) == 1
    assert any("malformed" in i.message.lower() or "missing" in i.message.lower()
               for i in result.issues)


def test_multi_row_record_merges_events():
    """One header followed by two data rows must yield one session."""
    tz = ZoneInfo("UTC")
    start = datetime(2026, 6, 1, 23, 0, tzinfo=tz)
    end = datetime(2026, 6, 2, 7, 0, tzinfo=tz)
    rec = saa_record("55", "UTC", start, end, hours=7.5,
                     events=[f"DEEP_START-{epoch_ms(start)}", f"DEEP_END-{epoch_ms(end)}"])
    header, data = rec.strip().split("\n")
    extra_row = data.replace(f"DEEP_START-{epoch_ms(start)}", f"AWAKE_START-{epoch_ms(start)}") \
                    .replace(f"DEEP_END-{epoch_ms(end)}", f"AWAKE_END-{epoch_ms(start + (end - start) / 8)}")
    result = _parse_csv(header + "\n" + data + "\n" + extra_row + "\n")
    assert len(result.sessions) == 1
    labels = {e["label"] for e in result.sessions[0].event_timeline}
    assert {"DEEP_START", "AWAKE_START"} <= labels


def test_session_crossing_midnight():
    tz = ZoneInfo("America/New_York")
    result = _parse_csv(saa_record("7", "America/New_York",
                                   datetime(2026, 6, 1, 22, 45, tzinfo=tz),
                                   datetime(2026, 6, 2, 6, 15, tzinfo=tz), hours=7))
    s = result.sessions[0]
    assert s.time_in_bed_min == 450.0
    assert s.final_wake_utc > s.in_bed_utc


def test_dst_change_duration_correct():
    """US spring-forward 2026-03-08: 23:00 -> 07:00 wall clock is only 7h real time."""
    tz = ZoneInfo("America/New_York")
    result = _parse_csv(saa_record("8", "America/New_York",
                                   datetime(2026, 3, 7, 23, 0, tzinfo=tz),
                                   datetime(2026, 3, 8, 7, 0, tzinfo=tz)))
    assert result.sessions[0].time_in_bed_min == 420.0  # not 480


def test_timezone_travel_sessions_keep_own_tz():
    tz1, tz2 = ZoneInfo("Europe/London"), ZoneInfo("Asia/Tokyo")
    csv = saa_record("1", "Europe/London", datetime(2026, 6, 1, 23, 0, tzinfo=tz1),
                     datetime(2026, 6, 2, 7, 0, tzinfo=tz1), hours=7) + \
          saa_record("2", "Asia/Tokyo", datetime(2026, 6, 3, 23, 0, tzinfo=tz2),
                     datetime(2026, 6, 4, 7, 0, tzinfo=tz2), hours=7)
    result = _parse_csv(csv)
    assert [s.timezone_name for s in result.sessions] == ["Europe/London", "Asia/Tokyo"]
    # UTC instants must reflect the offset difference
    assert result.sessions[0].in_bed_utc.hour == 22  # BST = UTC+1
    assert result.sessions[1].in_bed_utc.hour == 14  # JST = UTC+9


def test_nap_vs_main_sleep():
    tz = ZoneInfo("UTC")
    csv = saa_record("1", "UTC", datetime(2026, 6, 2, 14, 0, tzinfo=tz),
                     datetime(2026, 6, 2, 14, 40, tzinfo=tz), hours=0.6) + \
          saa_record("2", "UTC", datetime(2026, 6, 2, 23, 0, tzinfo=tz),
                     datetime(2026, 6, 3, 7, 0, tzinfo=tz), hours=7.5)
    result = _parse_csv(csv)
    assert result.sessions[0].is_nap is True
    assert result.sessions[1].is_nap is False


def test_missing_stages_reported_not_invented():
    tz = ZoneInfo("UTC")
    result = _parse_csv(saa_record("1", "UTC", datetime(2026, 6, 1, 23, 0, tzinfo=tz),
                                   datetime(2026, 6, 2, 7, 0, tzinfo=tz), hours=7))
    s = result.sessions[0]
    assert s.stage_intervals is None
    assert s.waso_min is None
    assert "stage_intervals" in s.missing_metrics
    assert "sleep_latency_min" in s.missing_metrics  # SaA never exports latency


def test_implausible_duration_flagged():
    tz = ZoneInfo("UTC")
    result = _parse_csv(saa_record("1", "UTC", datetime(2026, 6, 1, 8, 0, tzinfo=tz),
                                   datetime(2026, 6, 2, 9, 0, tzinfo=tz)))
    assert any("Implausible" in i.message for i in result.issues)


def test_stage_events_become_intervals():
    tz = ZoneInfo("UTC")
    start = datetime(2026, 6, 1, 23, 0, tzinfo=tz)
    mid = datetime(2026, 6, 2, 1, 0, tzinfo=tz)
    result = _parse_csv(saa_record(
        "1", "UTC", start, datetime(2026, 6, 2, 7, 0, tzinfo=tz), hours=7,
        events=[f"DEEP_START-{epoch_ms(start)}", f"DEEP_END-{epoch_ms(mid)}",
                f"AWAKE_START-{epoch_ms(mid)}",
                f"AWAKE_END-{epoch_ms(datetime(2026, 6, 2, 1, 10, tzinfo=tz))}"]))
    s = result.sessions[0]
    stages = {iv["stage"] for iv in s.stage_intervals}
    assert stages == {"deep", "awake"}
    assert s.waso_min == 10.0
    assert s.awakenings_count == 1


def test_snore_seconds_converted_and_negative_dropped():
    tz = ZoneInfo("UTC")
    csv = saa_record("1", "UTC", datetime(2026, 6, 1, 23, 0, tzinfo=tz),
                     datetime(2026, 6, 2, 7, 0, tzinfo=tz), snore="600") + \
          saa_record("2", "UTC", datetime(2026, 6, 2, 23, 0, tzinfo=tz),
                     datetime(2026, 6, 3, 7, 0, tzinfo=tz), snore="-1")
    result = _parse_csv(csv)
    assert result.sessions[0].snore_minutes == 10.0
    assert result.sessions[1].snore_minutes is None


def test_audio_metadata_without_audio_ok():
    """noise.json present but no /rec audio files — parse succeeds, extras noted."""
    tz = ZoneInfo("UTC")
    csv = saa_record("1", "UTC", datetime(2026, 6, 1, 23, 0, tzinfo=tz),
                     datetime(2026, 6, 2, 7, 0, tzinfo=tz), hours=7)
    result = A.parse("export.zip", make_zip({
        "sleep-export.csv": csv.encode(), "noise.json": b'[{"from": 1, "to": 2}]'}))
    assert len(result.sessions) == 1
    assert "noise_json" in result.extras
    assert "audio_files" not in result.extras


def test_audio_without_metadata_noted():
    tz = ZoneInfo("UTC")
    csv = saa_record("1", "UTC", datetime(2026, 6, 1, 23, 0, tzinfo=tz),
                     datetime(2026, 6, 2, 7, 0, tzinfo=tz), hours=7)
    result = A.parse("export.zip", make_zip({
        "sleep-export.csv": csv.encode(), "rec/2026-06-02.m4a": b"\x00fakeaudio"}))
    assert result.extras.get("audio_files")
    assert any("Phase-3" in i.message for i in result.issues)


# ------------------------------------------------------------------
# Structural fixtures mirroring a real 2026 export (fully anonymised):
# dot decimals, two data rows per record (movement row + noise row with
# empty scalar cells), DHA/LUX/SNORING/TALK/DEVICE events, Rating 0.0
# (= unrated), Snore 0 (= measured zero).
# ------------------------------------------------------------------
REAL_STYLE_RECORD = (
    'Id,Tz,From,To,Sched,Hours,Rating,Comment,Framerate,Snore,Noise,Cycles,DeepSleep,LenAdjust,Geo,'
    '"23:57","00:07","00:17","Event","Event","Event","Event"\n'
    '"1783864638786","Australia/Melbourne","12. 07. 2026 23:57","13. 07. 2026 8:52",'
    '"25. 07. 2026 0:37","8.930","0.0"," #home","10008","0","0.031717934","6","0.25925925","0","x1",'
    '"10.0","1.9324399","6.6076317",'
    '"DHA-1783864638786","LUX-1783864639178-12.0","SNORING-1783785181728","DEVICE-1783896770341-4.12052E-39"\n'
    '"","","","","","","","","","","","","","","",'
    '"652.8237","152.62614","179.59608","TALK-1783720275214","","",""\n'
)


def test_real_style_two_row_record():
    result = _parse_csv(REAL_STYLE_RECORD)
    assert len(result.sessions) == 1
    s = result.sessions[0]
    # Movement only from row 1; noise only from row 2 — never mixed.
    assert [m["value"] for m in s.movement_timeline] == [10.0, 1.9324399, 6.6076317]
    assert [n["value"] for n in s.noise_timeline] == [652.8237, 152.62614, 179.59608]
    # Dot decimals parsed; Hours 8.930 h capped at TIB and converted to minutes.
    assert s.total_sleep_min == 535.0
    assert s.timezone_name == "Australia/Melbourne"
    # Events from both rows merged, incl. scientific-notation values.
    labels = {e["label"] for e in s.event_timeline}
    assert {"DHA", "LUX", "SNORING", "DEVICE", "TALK"} <= labels


def test_rating_zero_means_unrated():
    result = _parse_csv(REAL_STYLE_RECORD)
    assert result.sessions[0].user_rating is None


def test_snore_zero_is_a_measurement_not_missing():
    result = _parse_csv(REAL_STYLE_RECORD)
    assert result.sessions[0].snore_minutes == 0.0


def test_alarms_json_noted_in_extras():
    tz = ZoneInfo("UTC")
    csv = saa_record("1", "UTC", datetime(2026, 6, 1, 23, 0, tzinfo=tz),
                     datetime(2026, 6, 2, 7, 0, tzinfo=tz), hours=7)
    result = A.parse("export.zip", make_zip({
        "sleep-export.csv": csv.encode(), "alarms.json": b"[]"}))
    assert result.extras.get("alarms_json_present") is True


def test_tst_subtracts_detected_awake_time():
    """SaA 'Hours' is tracked duration, not sleep; awake events must be
    subtracted so efficiency is not a flat 100%."""
    tz = ZoneInfo("UTC")
    start = datetime(2026, 6, 1, 23, 0, tzinfo=tz)
    result = _parse_csv(saa_record(
        "1", "UTC", start, datetime(2026, 6, 2, 7, 0, tzinfo=tz), hours=8.0,
        events=[f"AWAKE_START-{epoch_ms(datetime(2026, 6, 2, 2, 0, tzinfo=tz))}",
                f"AWAKE_END-{epoch_ms(datetime(2026, 6, 2, 2, 30, tzinfo=tz))}"]))
    s = result.sessions[0]
    assert s.waso_min == 30.0
    assert s.total_sleep_min == 450.0  # 480 tracked - 30 awake
