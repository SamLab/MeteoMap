import meteo


def test_model_order():
    codes = [c for c, _n, _e in meteo.FORECAST_MODELS]
    wanted = [
        "ecmwf_ifs025", "google_weathernext2_ensemble", "ncep_aigfs025",
        "ncep_gefs_seamless", "ncep_gfs_seamless", "jma_gsm", "gem_global",
        "dwd_icon_global",
        "ukmo_global_deterministic_10km", "cma_grapes_global",
        "meteofrance_arpege_world025",
    ]
    idx = [codes.index(c) for c in wanted]
    assert idx == sorted(idx)
    ext = [c for c, _n, _fn, *_ in meteo.EXTERNAL_MODELS]
    assert ext == [meteo.TT_CODE, meteo.OWM_CODE, meteo.VC_CODE, meteo.MB_CODE, meteo.WWO_CODE, meteo.XW_CODE, meteo.TW_CODE]


def test_aigfs_model_registered():
    codes = [c for c, _n, _e in meteo.FORECAST_MODELS]
    assert "ncep_aigfs025" in codes


def test_daily_variables_include_dominant_wind_direction():
    assert "wind_direction_10m_dominant" in meteo.DAILY_VARIABLES
    assert "wind_speed_10m_max" in meteo.DAILY_VARIABLES


def test_fetch_all_forecasts_returns_all_models(monkeypatch):
    calls = []

    def fake_fetch_model(code, endpoint, variables, days=None, timezone=None):
        calls.append((code, endpoint))
        return [{"model": code}]

    monkeypatch.setattr(meteo, "fetch_model", fake_fetch_model)
    models = [("a", "A", "forecast"), ("b", "B", "ensemble")]
    res = meteo.fetch_all_forecasts(models, ["temperature_2m"], 2, "UTC", max_workers=2)
    assert set(res) == {"a", "b"}
    assert res["a"] == [{"model": "a"}]
    assert res["b"] == [{"model": "b"}]
    assert set(calls) == {("a", "forecast"), ("b", "ensemble")}


def test_fetch_all_forecasts_skips_failures(monkeypatch):
    def fake_fetch_model(code, endpoint, variables, days=None, timezone=None):
        if code == "bad":
            raise RuntimeError("boom")
        return [{"model": code}]

    monkeypatch.setattr(meteo, "fetch_model", fake_fetch_model)
    models = [("good", "G", "forecast"), ("bad", "B", "forecast")]
    res = meteo.fetch_all_forecasts(models, ["t"], 2, "UTC", max_workers=2)
    assert "good" in res
    assert "bad" not in res


def test_fetch_external_providers_fills_all_cities(monkeypatch):
    def fake_fetch(lat=None, lon=None):
        return [{"utc": None, "temperature_2m": lat}]

    providers = [("p1", "P1", fake_fetch), ("p2", "P2", fake_fetch)]
    locs = [
        {"name": "Ярославль", "slug": "yaroslavl", "lat": 57.63, "lon": 39.87},
        {"name": "Балакирево", "slug": "balakirevo", "lat": 56.507, "lon": 38.846},
    ]
    res = meteo.fetch_external_providers(providers, locs, max_workers=2)
    assert set(res["p1"]) == {"yaroslavl", "balakirevo"}
    assert res["p1"]["yaroslavl"] == [{"utc": None, "temperature_2m": 57.63}]
    assert res["p2"]["balakirevo"] == [{"utc": None, "temperature_2m": 56.507}]


def test_fetch_external_providers_tolerates_failure():
    def bad_fetch(lat=None, lon=None):
        raise RuntimeError("down")

    providers = [("p", "P", bad_fetch)]
    locs = [
        {"name": "Ярославль", "slug": "yaroslavl", "lat": 57.63, "lon": 39.87},
    ]
    res = meteo.fetch_external_providers(providers, locs, max_workers=2)
    assert res["p"]["yaroslavl"] == []


from datetime import datetime, timezone, timedelta


def test_fetch_model_requests_wind_in_ms(monkeypatch):
    captured = {}

    def fake_retry(url, params, timeout):
        captured["params"] = params
        return {"hourly": {}, "daily": {}}

    monkeypatch.setattr(meteo, "request_with_retry", fake_retry)
    meteo.fetch_model("a", "forecast", ["wind_speed_10m"])
    assert captured["params"]["wind_speed_unit"] == "ms"


def test_fetch_historical_and_archive_wind_in_ms(monkeypatch):
    captured = []

    def fake_retry(url, params, timeout):
        captured.append(params)
        return {"hourly": {}}

    monkeypatch.setattr(meteo, "request_with_retry", fake_retry)
    meteo.fetch_historical_model("a", "2026-08-01", "2026-08-07", ["wind_speed_10m"])
    meteo.fetch_archive("2026-08-01", "2026-08-07", ["wind_speed_10m"])
    assert all(p.get("wind_speed_unit") == "ms" for p in captured)



def test_build_city_payload_with_external(monkeypatch):
    loc = meteo.LOCATIONS[0]
    raw = {
        "ecmwf_ifs025": [{
            "hourly": {"time": ["2026-08-07T00:00"], "temperature_2m": [10.0]},
            "daily": {},
        }],
    }
    utc_dt = datetime(2026, 8, 6, 21, 0, tzinfo=timezone.utc)  # = 2026-08-07T00:00 MSK
    external_rows = {
        meteo.YR_CODE: {loc["slug"]: [{"utc": utc_dt, "temperature_2m": 11.0}]},
        "owm": {loc["slug"]: [{"utc": utc_dt, "temperature_2m": 9.0}]},
    }
    monkeypatch.setattr(
        meteo, "verify_windows",
        lambda *a, **k: {
            "7d": {"ecmwf_ifs025": {v: 1.0 for v in meteo.VERIFICATION_VARIABLES}},
            "30d": {"ecmwf_ifs025": {v: 1.0 for v in meteo.VERIFICATION_VARIABLES}},
        },
    )
    p = meteo.build_city_payload(loc, raw, external_rows, "2026-08-07T00:00:00+03:00", True)
    assert "ecmwf_ifs025" in p["model_codes"]
    assert meteo.YR_CODE in p["model_codes"]
    assert "owm" in p["model_codes"]
    assert p["location"] == loc
