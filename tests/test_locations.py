import json

import meteo


def test_locations_have_unique_slugs():
    slugs = [loc["slug"] for loc in meteo.LOCATIONS]
    assert len(slugs) == len(set(slugs))
    assert "yaroslavl" in slugs
    assert meteo.LOCATIONS[0]["name"] == "Ярославль"


def test_fetch_model_batch_splits_by_city(monkeypatch):
    calls = {}

    def fake_request(url, params, timeout):
        calls["params"] = params
        return [
            {"latitude": 57.75, "hourly": {"time": ["t"], "temperature_2m": [1.0]}},
            {"latitude": 56.5, "hourly": {"time": ["t"], "temperature_2m": [5.0]}},
        ]

    monkeypatch.setattr(meteo, "request_with_retry", fake_request)
    res = meteo.fetch_model(
        "m", "forecast", ["temperature_2m"],
        days=2, lats="57.63,56.507", lons="39.87,38.846",
    )
    assert len(res) == 2
    assert res[0]["hourly"]["temperature_2m"] == [1.0]
    assert res[1]["hourly"]["temperature_2m"] == [5.0]
    assert calls["params"]["latitude"] == "57.63,56.507"
    assert calls["params"]["longitude"] == "39.87,38.846"


def test_fetch_model_wraps_single_response(monkeypatch):
    monkeypatch.setattr(
        meteo, "request_with_retry",
        lambda *a, **k: {"latitude": 57.75, "hourly": {}},
    )
    res = meteo.fetch_model("m", "forecast", ["temperature_2m"], lats="57.63", lons="39.87")
    assert isinstance(res, list) and len(res) == 1


def test_fetch_historical_model_wraps_single_response(monkeypatch):
    monkeypatch.setattr(
        meteo, "request_with_retry",
        lambda *a, **k: {"hourly": {"time": ["t"], "temperature_2m": [1.0]}},
    )
    res = meteo.fetch_historical_model("m", "2026-07-30", "2026-08-05", ["temperature_2m"])
    assert isinstance(res, list) and len(res) == 1


def test_fetch_archive_wraps_single_response(monkeypatch):
    monkeypatch.setattr(
        meteo, "request_with_retry",
        lambda *a, **k: {"hourly": {"time": ["t"], "temperature_2m": [1.0]}},
    )
    res = meteo.fetch_archive("2026-07-30", "2026-08-05", ["temperature_2m"])
    assert isinstance(res, list) and len(res) == 1


def test_build_payload_uses_location():
    hourly = {"a": {"time": ["h0"], "data": {"temperature_2m": [1.0]}}}
    consensus = {
        "time": ["h0"], "weighted": {"temperature_2m": [1.0]},
        "mean": {"temperature_2m": [1.0]}, "median": {"temperature_2m": [1.0]},
    }
    loc = {"name": "Балакирево", "slug": "balakirevo", "lat": 56.507, "lon": 38.846}
    p = meteo.build_payload(["a"], {"a": "A"}, hourly, {}, consensus, {},
                            "2026-08-06T12:00:00+03:00", loc)
    assert p["location"] == loc


def test_render_replaces_cities_placeholder():
    template = "<script id='cities'>__CITIES__</script>"
    payload = {"location": {"name": "Ярославль"}, "generated_at": "2026-08-06T12:00:00+03:00"}
    html = meteo.render(template, payload)
    assert "__CITIES__" not in html
    assert '"slug": "yaroslavl"' in html
    assert "Балакирево" in html
