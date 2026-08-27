import os
from datetime import datetime, timedelta, timezone

import pytest

import meteo


def test_owm_wmo_mapping():
    assert meteo.OWM_WMO[800] == 0
    assert meteo.OWM_WMO[801] == 1
    assert meteo.OWM_WMO[804] == 3
    assert meteo.OWM_WMO[200] == 95
    assert meteo.OWM_WMO[501] == 63
    assert meteo.OWM_WMO[600] == 71
    assert meteo.OWM_WMO[741] == 45
    assert meteo.OWM_WMO[611] == 66


def test_vc_wmo_mapping():
    assert meteo.VC_WMO["clear-day"] == 0
    assert meteo.VC_WMO["partly-cloudy-day"] == 2
    assert meteo.VC_WMO["cloudy"] == 3
    assert meteo.VC_WMO["rain"] == 61
    assert meteo.VC_WMO["snow"] == 71
    assert meteo.VC_WMO["thunderstorm"] == 95


def test_mb_wmo_mapping():
    assert meteo.MB_WMO[1] == 0
    assert meteo.MB_WMO[4] == 1
    assert meteo.MB_WMO[7] == 2
    assert meteo.MB_WMO[20] == 3
    assert meteo.MB_WMO[16] == 45
    assert meteo.MB_WMO[23] == 61
    assert meteo.MB_WMO[25] == 82
    assert meteo.MB_WMO[24] == 71
    assert meteo.MB_WMO[10] == 95
    assert meteo.MB_WMO[28] == 95
    assert meteo.MB_WMO[35] == 67


def test_external_models_registry():
    codes = [c for c, _n, _f, *_ in meteo.EXTERNAL_MODELS]
    assert meteo.OWM_CODE in codes
    assert meteo.VC_CODE in codes
    assert meteo.MB_CODE in codes


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_fetch_owm_parses_three_hourly(monkeypatch):
    captured = {}

    def fake_get(url, params, timeout):
        captured["url"] = url
        captured["params"] = params
        return _FakeResponse({"list": [
            {
                "dt": 1754520000,
                "main": {"temp": 20.5, "feels_like": 19.8, "humidity": 60,
                         "pressure": 1013.0},
                "weather": [{"id": 801}],
                "clouds": {"all": 20},
                "wind": {"speed": 3.5, "deg": 180, "gust": 6.0},
                "pop": 0.3,
                "rain": {"3h": 0.2},
            },
        ]})

    monkeypatch.setattr(meteo, "_request_get", fake_get)
    rows = meteo.fetch_owm(57.63, 39.87, api_key="test")
    assert captured["url"] == meteo.OWM_URL
    assert captured["params"]["appid"] == "test"
    assert captured["params"]["units"] == "metric"
    assert len(rows) == 1
    r = rows[0]
    assert r["temperature_2m"] == 20.5
    assert r["precipitation_probability"] == 30
    assert r["weather_code"] == 1
    assert r["pressure_msl"] == round(1013.0 * meteo.HPA_TO_MMHG, 1)
    assert r["wind_speed_10m"] == 3.5
    assert r["precipitation"] == 0.2


def test_fetch_owm_requires_key(monkeypatch, capsys):
    monkeypatch.delenv("OPENWEATHER_KEY", raising=False)
    assert meteo.fetch_owm(57.63, 39.87) == []
    assert "OPENWEATHER_KEY" in capsys.readouterr().out


def test_fetch_vc_parses_hourly(monkeypatch):
    captured = {}

    def fake_get(url, params, timeout):
        captured["url"] = url
        captured["params"] = params
        return _FakeResponse({"days": [
            {"hours": [
                {
                    "datetimeEpoch": 1754520000,
                    "temp": 20.5, "feelslike": 19.8, "dew": 12.0,
                    "humidity": 60, "precip": 0.2, "precipprob": 30,
                    "icon": "rain",
                    "pressure": 1013.0, "cloudcover": 70,
                    "windspeed": 18.0, "winddir": 180, "windgust": 30.0,
                    "visibility": 10.0,
                },
            ]},
        ]})

    monkeypatch.setattr(meteo, "_request_get", fake_get)
    rows = meteo.fetch_vc(57.63, 39.87, api_key="test")
    assert captured["params"]["key"] == "test"
    assert captured["params"]["unitGroup"] == "metric"
    assert len(rows) == 1
    r = rows[0]
    assert r["temperature_2m"] == 20.5
    assert r["apparent_temperature"] == 19.8
    assert r["dew_point_2m"] == 12.0
    assert r["precipitation"] == 0.2
    assert r["precipitation_probability"] == 30
    assert r["weather_code"] == 61
    assert r["pressure_msl"] == round(1013.0 * meteo.HPA_TO_MMHG, 1)
    assert r["cloud_cover"] == 70
    assert r["wind_speed_10m"] == pytest.approx(5.0, abs=0.01)
    assert r["wind_direction_10m"] == 180
    assert r["wind_gusts_10m"] == pytest.approx(8.33, abs=0.01)
    assert r["visibility"] == 10000
    assert r["utc"].astimezone(timezone.utc) == datetime(
        2025, 8, 6, 22, 40, tzinfo=timezone.utc
    )


def test_fetch_vc_requires_key(monkeypatch, capsys):
    monkeypatch.delenv("VISUALCROSSING_KEY", raising=False)
    assert meteo.fetch_vc(57.63, 39.87) == []
    assert "VISUALCROSSING_KEY" in capsys.readouterr().out


def test_fetch_mb_parses_hourly(monkeypatch):
    captured = {}

    def fake_get(url, params, timeout):
        captured["url"] = url
        captured["params"] = params
        return _FakeResponse({"metadata": {
            "name": "Yaroslavl", "utc_timeoffset": 3.0, "timezone_abbrevation": "MSK",
        }, "data_1h": {
            "time": ["2026-08-06 15:00"],
            "pictocode": [28],
            "temperature": [20.5], "felttemperature": [19.8],
            "precipitation": [0.2], "precipitation_probability": [40],
            "relativehumidity": [60], "sealevelpressure": [1013.0],
            "windspeed": [5.0], "winddirection": [180],
        }})

    monkeypatch.setattr(meteo, "_request_get", fake_get)
    rows = meteo.fetch_mb(57.63, 39.87, api_key="test")
    assert captured["url"] == meteo.MB_URL
    assert captured["params"]["apikey"] == "test"
    assert captured["params"]["format"] == "json"
    assert len(rows) == 1
    r = rows[0]
    assert r["temperature_2m"] == 20.5
    assert r["apparent_temperature"] == 19.8
    assert r["precipitation"] == 0.2
    assert r["precipitation_probability"] == 40
    assert r["weather_code"] == 95
    assert r["pressure_msl"] == round(1013.0 * meteo.HPA_TO_MMHG, 1)
    assert r["relative_humidity_2m"] == 60
    assert r["wind_speed_10m"] == 5.0
    assert r["wind_direction_10m"] == 180
    assert r["utc"].astimezone(timezone.utc) == datetime(
        2026, 8, 6, 12, 0, tzinfo=timezone.utc
    )


def test_fetch_mb_requires_key(monkeypatch, capsys):
    monkeypatch.delenv("METEOBLUE_KEY", raising=False)
    assert meteo.fetch_mb(57.63, 39.87) == []
    assert "METEOBLUE_KEY" in capsys.readouterr().out


def test_fetch_wwo_parses_string_weathercode(monkeypatch):
    captured = {}

    def fake_get(url, params, timeout):
        captured["url"] = url
        captured["params"] = params
        return _FakeResponse({"data": {"weather": [
            {"date": "2026-08-28", "hourly": [
                {"time": "500", "tempC": "18", "FeelsLikeC": "17",
                 "humidity": "70", "precipMM": "0.2", "chanceofrain": "30",
                 "weatherCode": "176", "pressure": "1013",
                 "cloudcover": "60", "windspeedKmph": "10",
                 "WindGustKmph": "20", "winddirDegree": "180",
                 "visibility": "10"},
            ]},
        ]}})

    monkeypatch.setattr(meteo, "_request_get", fake_get)
    rows = meteo.fetch_wwo(57.63, 39.87, api_key="test")
    assert rows[0]["weather_code"] == 80
    assert rows[0]["precipitation_probability"] == 30
    assert rows[0]["precipitation"] == 0.2


def test_fetch_wwo_requires_key(monkeypatch, capsys):
    monkeypatch.delenv("WWO_KEY", raising=False)
    assert meteo.fetch_wwo(57.63, 39.87) == []
    assert "WWO_KEY" in capsys.readouterr().out


_ROW = {"utc": datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc),
        "temperature_2m": 20.0}


def test_fetch_mb_cached_reuses_same_hour(monkeypatch, tmp_path):
    calls = []

    def fake_fetch(lat=None, lon=None):
        calls.append((lat, lon))
        return [dict(_ROW)]

    monkeypatch.setattr(meteo, "fetch_mb", fake_fetch)
    monkeypatch.setenv("MB_CACHE_FILE", str(tmp_path / "mb_cache.json"))
    r1 = meteo.fetch_mb_cached(lat=57.533, lon=39.905)
    r2 = meteo.fetch_mb_cached(lat=57.533, lon=39.905)
    assert len(calls) == 1
    assert calls[0] == (57.533, 39.905)
    assert r2[0]["temperature_2m"] == 20.0
    assert r2[0]["utc"] == _ROW["utc"]


def test_fetch_mb_cached_refetches_next_hour(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(meteo, "fetch_mb",
                        lambda lat=None, lon=None: calls.append(1) or [dict(_ROW)])
    monkeypatch.setenv("MB_CACHE_FILE", str(tmp_path / "mb_cache.json"))
    meteo.fetch_mb_cached()
    monkeypatch.setattr(meteo, "_utc_hour_key", lambda: "2099123123")
    meteo.fetch_mb_cached()
    assert len(calls) == 2


def test_utc_hour_key_buckets_3_hours(monkeypatch):
    cases = {
        datetime(2026, 8, 24, 10, 0): "202608243",
        datetime(2026, 8, 24, 12, 59): "202608244",
        datetime(2026, 8, 24, 14, 30): "202608244",
        datetime(2026, 8, 24, 15, 0): "202608245",
        datetime(2026, 8, 24, 2, 5): "202608240",
        datetime(2026, 8, 24, 0, 0): "202608240",
    }
    for now, key in cases.items():
        monkeypatch.setattr(meteo, "_utc_now", lambda n=now: n)
        assert meteo._utc_hour_key() == key


def test_fetch_mb_cached_no_cache_on_failure(monkeypatch, tmp_path):
    def boom(lat=None, lon=None):
        raise RuntimeError("down")

    monkeypatch.setattr(meteo, "fetch_mb", boom)
    path = tmp_path / "mb_cache.json"
    monkeypatch.setenv("MB_CACHE_FILE", str(path))
    with pytest.raises(RuntimeError):
        meteo.fetch_mb_cached()
    assert not path.exists()


def test_mb_only_for_tsedenevo():
    for code, _name, _fn, *rest in meteo.EXTERNAL_MODELS:
        slugs = rest[0] if rest else None
        if code == meteo.MB_CODE:
            assert slugs == ["tsedenevo"]
        elif slugs is not None:
            assert set(slugs) == set(meteo._EXT)



def test_align_to_grid_places_external_rows():
    tz = timezone(timedelta(hours=3))
    grid = ["2026-08-06T15:00", "2026-08-06T16:00", "2026-08-06T17:00"]
    rows = [
        {"utc": datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc),
         "temperature_2m": 22.0, "weather_code": 1},
    ]
    out = meteo.align_to_grid(rows, grid, tz)
    assert out["data"]["temperature_2m"] == [22.0, None, None]
    assert out["data"]["weather_code"] == [1, None, None]
    assert out["data"]["cape"] == [None, None, None]


def test_align_to_grid_skips_missing_hours():
    tz = timezone(timedelta(hours=3))
    grid = ["2026-08-06T15:00"]
    rows = [
        {"utc": datetime(2026, 8, 6, 13, 0, tzinfo=timezone.utc),
         "temperature_2m": 22.0},
    ]
    out = meteo.align_to_grid(rows, grid, tz)
    assert out["data"]["temperature_2m"] == [None]


def test_external_models_get_neutral_weight():
    mae = {"a": {"temperature_2m": 1.0}, "b": {"temperature_2m": 2.0},
           "owm": {"temperature_2m": None}}
    w = meteo.make_weights(mae, "temperature_2m")
    # внешние источники получают средний вес, а не вес 1.0
    assert 0 < w["owm"] < w["a"]


def test_render_attribution_includes_external_sources():
    payload = {
        "location": meteo.LOCATIONS[0],
        "model_codes": ["a", meteo.OWM_CODE,
                        meteo.VC_CODE, meteo.MB_CODE],
        "generated_at": "2026-08-06T12:00:00+03:00",
    }
    html = meteo.render("__ATTRIBUTION__", payload)
    assert "open-meteo.com" in html
    assert "openweathermap.org" in html
    assert "weatherapi.com" not in html
    assert "visualcrossing.com" in html
    assert "meteoblue.com" in html


def test_render_attribution_omits_absent_sources():
    payload = {
        "location": meteo.LOCATIONS[0],
        "model_codes": ["a"],
        "generated_at": "2026-08-06T12:00:00+03:00",
    }
    html = meteo.render("__ATTRIBUTION__", payload)
    assert "open-meteo.com" in html
    assert "openweathermap.org" not in html
    assert "weatherapi.com" not in html


def test_env_key_fallback(monkeypatch):
    captured = {}

    def fake_get(url, params, timeout):
        captured["params"] = params
        return _FakeResponse({"list": []})

    monkeypatch.setenv("OPENWEATHER_KEY", "env-key")
    monkeypatch.setattr(meteo, "_request_get", fake_get)
    assert meteo.fetch_owm(57.63, 39.87, api_key=None) == []
    assert captured["params"]["appid"] == "env-key"
