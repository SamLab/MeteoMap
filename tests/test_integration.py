"""Интеграционные тесты: реальные сетевые запросы к Open-Meteo.

Запуск вручную (не в CI):
    python -m pytest tests/ -m integration -q

Используются только API без ключей (forecast/ensemble/historical/archive).
Могут флакуать из-за доступности моделей на стороне Open-Meteo.
"""

import pytest

import meteo

pytestmark = pytest.mark.integration

_TARGET = meteo.LOCATIONS[0]  # Ярославль


def test_all_forecast_models_return_data_for_yaroslavl():
    working = []
    broken = []
    for code, _name, endpoint in meteo.FORECAST_MODELS:
        try:
            resp = meteo.fetch_model(
                code, endpoint, ["temperature_2m"], days=1, timezone="UTC",
                lats=str(_TARGET["lat"]), lons=str(_TARGET["lon"]),
            )
        except Exception as exc:
            broken.append((code, str(exc)))
            continue
        first = resp[0] if isinstance(resp, list) else resp
        if (first.get("hourly") or {}).get("time"):
            working.append(code)
        else:
            broken.append((code, "empty hourly response"))
    print("working:", working)
    print("broken:", broken)
    assert not broken, f"broken models: {broken}"


def test_verification_runs_for_last_7_days():
    start, end = meteo.date_window(7)
    # производственный путь: город-обёртки выбирают ответ конкретного города
    result = meteo.verify_windows(
        ["dwd_icon_global", "ncep_gfs_seamless"],
        meteo.VERIFICATION_VARIABLES,
        {"7d": (start, end)},
        fetch_hist=meteo._city_hist(_TARGET),
        fetch_arch=meteo._city_arch(_TARGET),
    )
    assert result
    for code, mae in result["7d"].items():
        assert mae["temperature_2m"] is not None
        assert mae["wind_speed_10m"] is not None