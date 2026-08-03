import pytest

import meteo

pytestmark = pytest.mark.integration


def test_all_forecast_models_return_data_for_yaroslavl():
    working = []
    broken = []
    for code, _name, endpoint in meteo.FORECAST_MODELS:
        try:
            resp = meteo.fetch_model(
                code, endpoint, ["temperature_2m"], days=1, timezone="UTC"
            )
        except Exception as exc:
            broken.append((code, str(exc)))
            continue
        if (resp.get("hourly") or {}).get("time"):
            working.append(code)
        else:
            broken.append((code, "empty hourly response"))
    print("working:", working)
    print("broken:", broken)
    assert not broken, f"broken models: {broken}"


def test_verification_runs_for_last_7_days():
    start, end = meteo.date_window(7)
    result = meteo.verify_models(
        ["dwd_icon_global", "ncep_gfs_seamless"],
        meteo.VERIFICATION_VARIABLES, start, end,
    )
    assert result
    for code, mae in result.items():
        assert mae["temperature_2m"] is not None
        assert mae["wind_speed_10m"] is not None
