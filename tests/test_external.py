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


def test_weatherapi_wmo_mapping():
    assert meteo.WEATHERAPI_WMO[1000] == 0
    assert meteo.WEATHERAPI_WMO[1009] == 3
    assert meteo.WEATHERAPI_WMO[1183] == 61
    assert meteo.WEATHERAPI_WMO[1195] == 65
    assert meteo.WEATHERAPI_WMO[1225] == 75
    assert meteo.WEATHERAPI_WMO[1276] == 95
    assert meteo.WEATHERAPI_WMO[1003] == 1


def test_external_models_registry():
    codes = [c for c, _n, _f in meteo.EXTERNAL_MODELS]
    assert meteo.OWM_CODE in codes
    assert meteo.WEATHERAPI_CODE in codes


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

    monkeypatch.setattr(meteo.requests, "get", fake_get)
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


def test_fetch_weatherapi_parses_hourly(monkeypatch):
    captured = {}

    def fake_get(url, params, timeout):
        captured["url"] = url
        captured["params"] = params
        return _FakeResponse({"forecast": {"forecastday": [
            {"hour": [
                {
                    "time": "2026-08-06 15:00",
                    "temp_c": 22.0, "feelslike_c": 21.5, "dewpoint_c": 12.0,
                    "humidity": 55, "cloud": 30, "pressure_mb": 1014.0,
                    "precip_mm": 0.0,
                    "wind_kph": 18.0, "wind_degree": 200, "gust_kph": 30.0,
                    "chance_of_rain": 40, "chance_of_snow": 0,
                    "vis_km": 10.0,
                    "condition": {"code": 1003},
                },
            ]},
        ]}})

    monkeypatch.setattr(meteo.requests, "get", fake_get)
    rows = meteo.fetch_weatherapi(57.63, 39.87, api_key="test")
    assert captured["url"] == meteo.WEATHERAPI_URL
    assert captured["params"]["key"] == "test"
    assert len(rows) == 1
    r = rows[0]
    assert r["temperature_2m"] == 22.0
    assert r["precipitation_probability"] == 40
    assert r["weather_code"] == 1
    assert r["pressure_msl"] == round(1014.0 * meteo.HPA_TO_MMHG, 1)
    assert r["wind_speed_10m"] == pytest.approx(5.0, abs=0.01)
    assert r["wind_gusts_10m"] == pytest.approx(8.33, abs=0.01)
    assert r["visibility"] == 10000
    assert r["utc"].astimezone(timezone.utc) == datetime(
        2026, 8, 6, 12, 0, tzinfo=timezone.utc
    )


def test_fetch_weatherapi_requires_key(monkeypatch, capsys):
    monkeypatch.delenv("WEATHERAPI_KEY", raising=False)
    assert meteo.fetch_weatherapi(57.63, 39.87) == []
    assert "WEATHERAPI_KEY" in capsys.readouterr().out


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
           "owm": {"temperature_2m": None},
           "weatherapi": {"temperature_2m": None}}
    w = meteo.make_weights(mae, "temperature_2m")
    # внешние источники получают средний вес, а не вес 1.0
    assert w["owm"] == w["weatherapi"]
    assert 0 < w["owm"] < w["a"]


def test_render_attribution_includes_external_sources():
    payload = {
        "location": meteo.LOCATIONS[0],
        "model_codes": ["a", meteo.OWM_CODE, meteo.WEATHERAPI_CODE],
        "generated_at": "2026-08-06T12:00:00+03:00",
    }
    html = meteo.render("__ATTRIBUTION__", payload)
    assert "open-meteo.com" in html
    assert "openweathermap.org" in html
    assert "weatherapi.com" in html


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
    monkeypatch.setattr(meteo.requests, "get", fake_get)
    assert meteo.fetch_owm(57.63, 39.87, api_key=None) == []
    assert captured["params"]["appid"] == "env-key"
