import meteo


def test_normalize_present_variables():
    resp = {
        "hourly": {
            "time": ["t0", "t1"],
            "temperature_2m": [1.0, 2.0],
            "relative_humidity_2m": [80.0, 85.0],
        }
    }
    out = meteo.normalize_model_response(
        resp, ["temperature_2m", "relative_humidity_2m", "wind_speed_10m"]
    )
    assert out["time"] == ["t0", "t1"]
    assert out["data"]["temperature_2m"] == [1.0, 2.0]
    assert out["data"]["relative_humidity_2m"] == [80.0, 85.0]
    assert out["data"]["wind_speed_10m"] == [None, None]


def test_normalize_missing_hourly_block():
    out = meteo.normalize_model_response({}, ["temperature_2m"])
    assert out["time"] == []
    assert out["data"]["temperature_2m"] == []


def test_normalize_keeps_nulls_from_api():
    resp = {"hourly": {"time": ["t0"], "temperature_2m": [None]}}
    out = meteo.normalize_model_response(resp, ["temperature_2m"])
    assert out["data"]["temperature_2m"] == [None]
