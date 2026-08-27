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


def test_verify_models_tolerates_archive_failure():
    variables = ["temperature_2m"]

    def _broken_arch(*args, **kwargs):
        raise RuntimeError("archive down")

    result = meteo.verify_models(
        ["a", "b"], variables, "2026-07-01", "2026-07-02",
        fetch_hist=_hist, fetch_arch=_broken_arch,
    )
    assert result == {
        "a": {"temperature_2m": None},
        "b": {"temperature_2m": None},
    }


def _hist_wide(code, start_date, end_date, variables):
    if code == "broken":
        raise RuntimeError("model unavailable")
    return {
        "hourly": {
            "time": ["2026-07-01T00:00", "2026-07-02T00:00"],
            "temperature_2m": [1.0, 3.0],
            "precipitation": [0.0, 0.0],
            "wind_speed_10m": [3.0, 4.0],
        }
    }


def _arch_wide(start_date, end_date, variables):
    return {
        "hourly": {
            "time": ["2026-07-01T00:00", "2026-07-02T00:00"],
            "temperature_2m": [0.0, 0.0],
            "precipitation": [0.0, 0.0],
            "wind_speed_10m": [2.0, 2.0],
        }
    }


def test_verify_windows_single_fetch_per_model():
    variables = ["temperature_2m", "precipitation", "wind_speed_10m"]
    calls = []

    def _hist(code, start_date, end_date, variables):
        calls.append((code, start_date, end_date))
        return _hist_wide(code, start_date, end_date, variables)

    windows = {
        "7d": ("2026-07-01", "2026-07-01"),
        "30d": ("2026-07-01", "2026-07-10"),
    }
    result = meteo.verify_windows(
        ["a", "broken"], variables, windows,
        fetch_hist=_hist, fetch_arch=_arch_wide,
    )
    # один вызов истории на модель на самом широком окне
    assert calls == [("a", "2026-07-01", "2026-07-10"),
                     ("broken", "2026-07-01", "2026-07-10")]
    # 7d: только 1 июля (температура |1-0|=1; ветер |3-2|=1)
    assert result["7d"]["a"]["temperature_2m"] == 1.0
    assert result["7d"]["a"]["wind_speed_10m"] == 1.0
    # 30d: обе точки (температура (|1-0|+|3-0|)/2=2; ветер (|3-2|+|4-2|)/2=1.5)
    assert result["30d"]["a"]["temperature_2m"] == 2.0
    assert result["30d"]["a"]["wind_speed_10m"] == 1.5
    # сломанная модель опущена в обоих окнах
    assert "broken" not in result["7d"]
    assert "broken" not in result["30d"]


def test_verify_models_parallel_skips_failing_models():
    variables = ["temperature_2m"]
    calls = []

    def _hist(code, start_date, end_date, variables):
        calls.append(code)
        if code == "broken":
            raise RuntimeError("model unavailable")
        return {
            "hourly": {
                "time": ["2026-07-01T00:00"],
                "temperature_2m": [1.0],
            }
        }

    def _arch(start_date, end_date, variables):
        return {"hourly": {"time": ["2026-07-01T00:00"], "temperature_2m": [0.0]}}

    result = meteo.verify_models(
        ["a", "broken", "c"], variables, "2026-07-01", "2026-07-02",
        fetch_hist=_hist, fetch_arch=_arch,
    )
    assert set(result) == {"a", "c"}
    assert "broken" not in result
    assert set(calls) == {"a", "broken", "c"}
