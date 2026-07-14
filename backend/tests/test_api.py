from datetime import datetime
from zoneinfo import ZoneInfo

from tests.conftest import make_zip, saa_record

TZ = ZoneInfo("Europe/London")


def _upload(client, csv_text: str, filename="export.zip"):
    data = make_zip({"sleep-export.csv": csv_text.encode()})
    return client.post("/api/imports/preview",
                       files={"file": (filename, data, "application/zip")})


def _one_night(record_id="1", day=1):
    return saa_record(record_id, "Europe/London",
                      datetime(2026, 6, day, 23, 0, tzinfo=TZ),
                      datetime(2026, 6, day + 1, 7, 0, tzinfo=TZ), hours=7.2)


def test_import_preview_and_commit_flow(client):
    r = _upload(client, _one_night())
    assert r.status_code == 200
    body = r.json()
    assert len(body["sessions"]) == 1
    assert body["sessions"][0]["likely_duplicate_of"] == []

    r2 = client.post(f"/api/imports/{body['batch_id']}/commit", json={})
    assert r2.status_code == 200
    assert len(r2.json()["created_session_ids"]) == 1

    sessions = client.get("/api/sessions").json()
    assert len(sessions) == 1
    assert sessions[0]["data_quality_score"] is not None
    assert sessions[0]["confidence"] in ("high", "moderate", "low")


def test_duplicate_import_detected_and_skipped(client):
    r1 = _upload(client, _one_night())
    client.post(f"/api/imports/{r1.json()['batch_id']}/commit", json={})
    r2 = _upload(client, _one_night())
    dupes = r2.json()["sessions"][0]["likely_duplicate_of"]
    assert dupes  # flagged in preview
    r3 = client.post(f"/api/imports/{r2.json()['batch_id']}/commit", json={})
    assert r3.json()["created_session_ids"] == []
    assert r3.json()["skipped"][0]["reason"] == "likely_duplicate"
    assert len(client.get("/api/sessions").json()) == 1


def test_session_detail_has_provenance(client):
    r = _upload(client, _one_night())
    client.post(f"/api/imports/{r.json()['batch_id']}/commit", json={})
    sid = client.get("/api/sessions").json()[0]["id"]
    detail = client.get(f"/api/sessions/{sid}").json()
    assert detail["field_provenance"]["total_sleep_min"]["kind"] == "device_estimated"
    assert detail["field_provenance"]["user_rating"]["kind"] == "self_reported"


def test_manual_session_and_patch(client):
    r = client.post("/api/sessions", json={
        "in_bed": "2026-06-05T23:00:00+01:00", "final_wake": "2026-06-06T06:30:00+01:00",
        "timezone_name": "Europe/London", "total_sleep_min": 400})
    assert r.status_code == 200
    sid = r.json()["id"]
    assert r.json()["source"] == "manual"
    r2 = client.patch(f"/api/sessions/{sid}", json={"is_nap": False, "comments": "corrected"})
    assert r2.json()["manually_edited"] is True


def test_manual_session_rejects_invalid(client):
    r = client.post("/api/sessions", json={
        "in_bed": "2026-06-06T23:00:00Z", "final_wake": "2026-06-06T22:00:00Z"})
    assert r.status_code == 422


def test_habits_and_checkins_roundtrip(client):
    r = client.post("/api/habits", json={"date": "2026-06-02", "caffeine_mg": 200,
                                         "last_caffeine_time": "15:30", "alcohol_units": 2})
    assert r.status_code == 200
    r2 = client.post("/api/habits", json={"date": "2026-06-02", "alcohol_units": 3})
    assert r2.json()["alcohol_units"] == 3  # upsert
    assert r2.json()["caffeine_mg"] == 200  # earlier fields kept

    c = client.post("/api/checkins", json={"date": "2026-06-02", "kind": "morning",
                                           "morning_energy": 7, "sleep_quality": 6})
    assert c.status_code == 200
    bad = client.post("/api/checkins", json={"date": "2026-06-02", "kind": "morning",
                                             "morning_energy": 15})
    assert bad.status_code == 422


def test_metrics_overview_insufficient_data_states(client):
    out = client.get("/api/metrics/overview").json()
    assert out["regularity"]["status"] == "insufficient_data"
    assert out["sleep_need"]["status"] == "insufficient_data"
    assert "disclaimer" in out


def test_coaching_today_structure(client):
    r = _upload(client, _one_night())
    client.post(f"/api/imports/{r.json()['batch_id']}/commit", json={})
    client.put("/api/profile", json={"required_wake_time": "06:30",
                                     "current_timezone": "Europe/London"})
    out = client.get("/api/coaching/today").json()
    c = out["coaching"]
    for key in ("what_happened", "data_quality_reason", "what_matters_most",
                "likely_contributors", "todays_capacity", "todays_actions",
                "tonights_target", "one_thing_to_learn"):
        assert key in c
    assert len(c["what_happened"]) <= 200  # brief summary requirement
    assert len(c["todays_actions"]) <= 3
    ranked = c["what_matters_most"]
    for bucket in ("doing_well", "needs_improvement", "not_doing_well"):
        assert bucket in ranked
        assert len(ranked[bucket]) <= 3
    assert c["tonights_target"]["target_sleep_min"] > 0


def test_weekly_report(client):
    csv = "".join(_one_night(str(i), day=i) for i in range(1, 8))
    r = _upload(client, csv)
    client.post(f"/api/imports/{r.json()['batch_id']}/commit", json={})
    out = client.get("/api/reports/weekly").json()
    assert out["status"] == "ok"
    assert out["avg_total_sleep_min"] is not None
    assert out["recommended_focus"]


def test_export_and_delete_all(client):
    r = _upload(client, _one_night())
    client.post(f"/api/imports/{r.json()['batch_id']}/commit", json={})
    client.post("/api/habits", json={"date": "2026-06-02", "caffeine_mg": 100})

    export = client.get("/api/privacy/export").json()
    assert export["sessions"] and export["habits"] and export["raw_records"]

    assert client.post("/api/privacy/delete-all").status_code == 400  # needs confirm
    out = client.post("/api/privacy/delete-all", params={"confirm": "DELETE"}).json()
    assert out["deleted"]["sleep_sessions"] == 1
    assert client.get("/api/sessions").json() == []
    assert client.get("/api/habits").json() == []
    # Deletion itself is audited
    audit = client.get("/api/privacy/audit").json()
    assert any(a["action"] == "delete_all" for a in audit)


def test_chronotype_endpoint_insufficient(client):
    out = client.get("/api/metrics/chronotype").json()
    assert out["category"] == "insufficient_data"


def test_snoring_insufficient(client):
    out = client.get("/api/metrics/snoring").json()
    assert out["status"] == "insufficient_data"
    assert "apnea" in out["note"]


def test_implausible_session_excluded_from_aggregates_but_listed(client):
    """A runaway 33h tracking session stays in the nights list but must not
    distort rolling averages or debt."""
    csv = "".join(_one_night(str(i), day=i) for i in range(1, 8))
    csv += saa_record("999", "Europe/London",
                      datetime(2026, 6, 9, 8, 0, tzinfo=TZ),
                      datetime(2026, 6, 10, 18, 0, tzinfo=TZ), hours=33.9)
    r = _upload(client, csv)
    client.post(f"/api/imports/{r.json()['batch_id']}/commit",
                json={"include_indices": list(range(8))})
    sessions = client.get("/api/sessions").json()
    assert len(sessions) == 8  # still listed
    outlier = next(s for s in sessions if s["time_in_bed_min"] > 1000)
    assert outlier["confidence"] == "low"
    overview = client.get("/api/metrics/overview").json()
    assert overview["duration"]["nights"] == 7  # outlier not aggregated
    assert overview["duration"]["avg_7d_min"] < 600
