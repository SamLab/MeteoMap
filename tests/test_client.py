import requests

import meteo


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_fetch_model_parameters(monkeypatch):
    captured = {}

    def fake_get(url, params, timeout):
        captured["url"] = url
        captured["params"] = params
        return _FakeResponse({"hourly": {"time": []}})

    monkeypatch.setattr(requests, "get", fake_get)
    out = meteo.fetch_model(
        "dwd_icon_global", "forecast", ["temperature_2m"],
        days=3, timezone="Europe/Moscow",
    )
    assert out == [{"hourly": {"time": []}}]
    assert captured["url"] == meteo.ENDPOINTS["forecast"]
    p = captured["params"]
    assert p["models"] == "dwd_icon_global"
    assert p["hourly"] == "temperature_2m"
    assert p["forecast_days"] == 3
    assert p["timezone"] == "Europe/Moscow"
    assert p["latitude"] == ",".join(str(loc["lat"]) for loc in meteo.LOCATIONS)
    assert p["longitude"] == ",".join(str(loc["lon"]) for loc in meteo.LOCATIONS)


def test_fetch_model_uses_ensemble_endpoint(monkeypatch):
    captured = {}

    def fake_get(url, params, timeout):
        captured["url"] = url
        return _FakeResponse({})

    monkeypatch.setattr(requests, "get", fake_get)
    meteo.fetch_model("google_weathernext", "ensemble", ["temperature_2m"])
    assert captured["url"] == meteo.ENDPOINTS["ensemble"]


def test_fetch_historical_uses_historical_endpoint(monkeypatch):
    captured = {}

    def fake_get(url, params, timeout):
        captured["url"] = url
        captured["params"] = params
        return _FakeResponse({})

    monkeypatch.setattr(requests, "get", fake_get)
    meteo.fetch_historical_model(
        "dwd_icon_global", "2026-07-27", "2026-08-02", ["temperature_2m"]
    )
    assert captured["url"] == meteo.ENDPOINTS["historical"]
    assert captured["params"]["start_date"] == "2026-07-27"
    assert captured["params"]["end_date"] == "2026-08-02"


def test_fetch_archive_uses_archive_endpoint(monkeypatch):
    captured = {}

    def fake_get(url, params, timeout):
        captured["url"] = url
        assert "models" not in params
        return _FakeResponse({})

    monkeypatch.setattr(requests, "get", fake_get)
    meteo.fetch_archive("2026-07-27", "2026-08-02", ["temperature_2m"])
    assert captured["url"] == meteo.ENDPOINTS["archive"]
