from datetime import date, timedelta

import meteo


def test_compute_mae_basic():
    assert abs(meteo.compute_mae([1.0, 3.0, 2.0], [0.0, 1.0, 4.0]) - 5.0 / 3.0) < 1e-6


def test_compute_mae_skips_none():
    assert meteo.compute_mae([1.0, None, 2.0], [0.0, 5.0, 4.0]) == 1.5


def test_compute_mae_no_pairs():
    assert meteo.compute_mae([None, None], [0.0, 1.0]) is None


def test_date_window_ends_yesterday():
    start, end = meteo.date_window(7)
    today = date.today()
    assert end == (today - timedelta(days=1)).isoformat()
    assert start == (today - timedelta(days=7)).isoformat()


def _hist(code, start_date, end_date, variables):
    if code == "broken":
        raise RuntimeError("model unavailable")
    return {
        "hourly": {
            "time": ["2026-07-01T00:00", "2026-07-01T01:00"],
            "temperature_2m": [1.0, 2.0],
            "precipitation": [0.0, 0.0],
            "wind_speed_10m": [3.0, 4.0],
        }
    }


def _arch(start_date, end_date, variables):
    return {
        "hourly": {
            "time": ["2026-07-01T00:00", "2026-07-01T01:00"],
            "temperature_2m": [0.0, 0.0],
            "precipitation": [0.0, 0.0],
            "wind_speed_10m": [2.0, 2.0],
        }
    }


def test_verify_models_computes_mae_and_skips_failures():
    variables = ["temperature_2m", "precipitation", "wind_speed_10m"]
    result = meteo.verify_models(
        ["a", "broken"], variables, "2026-07-01", "2026-07-02",
        fetch_hist=_hist, fetch_arch=_arch,
    )
    assert "broken" not in result
    assert abs(result["a"]["temperature_2m"] - 1.5) < 1e-6
    assert result["a"]["precipitation"] == 0.0
    assert abs(result["a"]["wind_speed_10m"] - 1.5) < 1e-6
