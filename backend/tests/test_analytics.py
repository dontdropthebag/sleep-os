from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.analytics import baselines, chronotype, metrics, regularity, sleep_debt
from app.analytics.quality import confidence_label, score_session


def mk_session(date: str, tz: str = "UTC", in_bed: str = "23:00", wake: str = "07:00",
               tst: float | None = 420, tib: float | None = None, is_nap: bool = False,
               quality: float | None = 80, **kw):
    d = datetime.fromisoformat(date).replace(tzinfo=timezone.utc)
    ih, im = map(int, in_bed.split(":"))
    wh, wm = map(int, wake.split(":"))
    bed_day = d - timedelta(days=1) if ih > 12 else d
    in_bed_dt = bed_day.replace(hour=ih, minute=im)
    wake_dt = d.replace(hour=wh, minute=wm)
    return SimpleNamespace(
        session_date=date, timezone_name=tz, is_nap=is_nap,
        in_bed_utc=in_bed_dt, sleep_onset_utc=None, final_wake_utc=wake_dt,
        time_in_bed_min=tib if tib is not None else (wake_dt - in_bed_dt).total_seconds() / 60,
        total_sleep_min=tst, sleep_latency_min=kw.get("latency"),
        waso_min=kw.get("waso"), awakenings_count=kw.get("awakenings"),
        stage_intervals=kw.get("stages"), data_quality_score=quality,
        manually_edited=False, source=kw.get("source", "sleep_as_android"),
    )


def dates(n: int, start: str = "2026-05-01"):
    d0 = datetime.fromisoformat(start)
    return [(d0 + timedelta(days=i)).date().isoformat() for i in range(n)]


# ---------------------------------------------------------------- efficiency
def test_sleep_efficiency_formula():
    assert metrics.sleep_efficiency(420, 480) == 87.5
    assert metrics.sleep_efficiency(None, 480) is None
    assert metrics.sleep_efficiency(420, None) is None
    assert metrics.sleep_efficiency(500, 480) == 100.0  # capped


def test_rolling_averages():
    vals = [400.0] * 4 + [480.0] * 3
    assert metrics.rolling_average(vals, 7) == round((400 * 4 + 480 * 3) / 7, 1)
    assert metrics.rolling_average([420.0], 7) is None  # insufficient
    assert metrics.rolling_average([None, None, 400.0, 420.0, 440.0, 400.0], 7) == 415.0


# ---------------------------------------------------------------- regularity
def test_regularity_wraps_midnight():
    """23:50 vs 00:10 bedtimes are 20 min apart, not ~23 h."""
    sess = [mk_session(d, in_bed=("23:50" if i % 2 else "00:10"))
            for i, d in enumerate(dates(10))]
    reg = regularity.regularity_summary(sess)
    assert reg["status"] == "ok"
    assert reg["onset_sd_min"] <= 15


def test_regularity_insufficient_data():
    reg = regularity.regularity_summary([mk_session(d) for d in dates(3)])
    assert reg["status"] == "insufficient_data"


def test_social_jetlag_detects_weekend_shift():
    sess = []
    for d in dates(21, "2026-05-04"):  # starts a Monday
        day = datetime.fromisoformat(d).strftime("%a").lower()[:3]
        late = day in ("sat", "sun")
        sess.append(mk_session(d, in_bed="01:00" if late else "23:00",
                               wake="09:00" if late else "07:00"))
    reg = regularity.regularity_summary(sess)
    assert reg["social_jetlag_min"] is not None
    assert reg["social_jetlag_min"] > 60


# ---------------------------------------------------------------- sleep debt
def test_sleep_need_insufficient_data_uses_reference():
    out = sleep_debt.estimate_sleep_need([mk_session(d) for d in dates(5)], {}, {}, 480)
    assert out["status"] == "insufficient_data"
    assert 420 <= out["sleep_need_min"] <= 540
    assert out["confidence"] == "low"


def test_personal_need_from_good_nights():
    sess = [mk_session(d, tst=430 + (i % 3) * 10) for i, d in enumerate(dates(30))]
    checkins = {d: SimpleNamespace(morning_energy=8, daytime_sleepiness=2) for d in dates(30)}
    out = sleep_debt.estimate_sleep_need(sess, checkins, {}, 480)
    assert out["status"] == "ok"
    assert 420 <= out["sleep_need_min"] <= 460


def test_good_nights_exclude_alcohol_illness_travel():
    sess = [mk_session(d, tst=400) for d in dates(30)]
    checkins = {d: SimpleNamespace(morning_energy=9, daytime_sleepiness=1) for d in dates(30)}
    habits = {d: SimpleNamespace(illness=True, travel=False, alcohol_units=0) for d in dates(30)}
    out = sleep_debt.estimate_sleep_need(sess, checkins, habits, 480)
    assert out["status"] == "insufficient_good_nights"


def test_rolling_debt_and_partial_recovery():
    sess = [mk_session(d, tst=420) for d in dates(6)] + [mk_session(dates(7)[-1], tst=600)]
    out = sleep_debt.rolling_debt(sess, 480, 7)
    assert out["status"] == "ok"
    assert out["gross_debt_min"] == 360
    # One long night must NOT fully clear the debt
    assert out["net_debt_min"] >= 180


# ---------------------------------------------------------------- chronotype
def test_chronotype_insufficient_data():
    out = chronotype.estimate_chronotype([mk_session(d) for d in dates(5)], {}, {"mon"}, None)
    assert out["category"] == "insufficient_data"


def test_chronotype_excludes_travel_illness_alcohol():
    sess = [mk_session(d) for d in dates(20)]
    habits = {d: SimpleNamespace(travel=(i < 3), illness=(3 <= i < 5), alcohol_units=5 if 5 <= i < 7 else 0,
                                 timezone_change=False)
              for i, d in enumerate(dates(20))}
    out = chronotype.estimate_chronotype(sess, habits, {"mon", "tue", "wed", "thu", "fri"}, None)
    reasons = {r for e in out["excluded"] for r in e["reasons"]}
    assert {"travel", "illness", "alcohol"} <= reasons


def test_chronotype_later_category():
    sess = []
    for d in dates(30, "2026-05-04"):
        day = datetime.fromisoformat(d).strftime("%a").lower()[:3]
        free = day in ("sat", "sun")
        sess.append(mk_session(d, in_bed="02:00" if free else "00:30",
                               wake="10:30" if free else "07:00", tst=440))
    out = chronotype.estimate_chronotype(sess, {}, {"mon", "tue", "wed", "thu", "fri"}, None)
    assert out["category"] == "later"
    assert "circadian" in out["method"]  # honesty note present


def test_chronotype_all_nighter_excluded():
    sess = [mk_session(d) for d in dates(20)]
    sess.append(mk_session("2026-05-21", tib=60, tst=50))  # near all-nighter
    out = chronotype.estimate_chronotype(sess, {}, {"mon"}, None)
    assert any("implausible_duration" in e["reasons"] for e in out["excluded"])


# ---------------------------------------------------------------- baselines
def mk_obs(date, value, source="oura", method="rmssd_overnight", metric="hrv_rmssd"):
    return SimpleNamespace(date=date, value=value, source=source, method=method,
                           metric=metric, unit="ms")


def test_baseline_medians_and_deviation():
    obs = [mk_obs(d, 50 + (i % 5)) for i, d in enumerate(dates(30))]
    out = baselines.baseline_summary(obs, "hrv_rmssd")
    g = out["preferred"]
    assert g["median_7d"] is not None and g["median_28d"] is not None
    assert "deviation_from_baseline" in g


def test_conflicting_devices_never_blended():
    obs = ([mk_obs(d, 50, source="oura", method="rmssd_overnight") for d in dates(10)]
           + [mk_obs(d, 80, source="whoop", method="rmssd_slow_wave") for d in dates(10)])
    out = baselines.baseline_summary(obs, "hrv_rmssd")
    assert len(out["groups"]) == 2
    assert "note" in out
    medians = {g["median_7d"] for g in out["groups"]}
    assert medians == {50, 80}  # kept separate, never averaged


def test_missing_hrv_reports_no_data():
    assert baselines.baseline_summary([], "hrv_rmssd")["status"] == "no_data"


def test_preferred_source_respected():
    obs = ([mk_obs(d, 50, source="oura") for d in dates(10)]
           + [mk_obs(d, 80, source="whoop") for d in dates(5)])
    out = baselines.baseline_summary(obs, "hrv_rmssd", preferred_source="whoop")
    assert out["preferred"]["source"] == "whoop"


# ---------------------------------------------------------------- quality
def test_quality_score_penalises_implausible():
    good = mk_session("2026-06-01")
    bad = mk_session("2026-06-02", tib=30 * 60)
    assert score_session(good)[0] > score_session(bad)[0]


def test_confidence_labels():
    assert confidence_label(None) == "insufficient_data"
    assert confidence_label(80) == "high"
    assert confidence_label(60) == "moderate"
    assert confidence_label(30) == "low"
