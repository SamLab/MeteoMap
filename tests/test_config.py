import re

import meteo


def test_models_registry_nonempty():
    assert meteo.FORECAST_MODELS


def test_model_codes_lowercase_snake():
    for code, _name, _endpoint in meteo.FORECAST_MODELS:
        assert code == code.lower()
        assert re.fullmatch(r"[a-z0-9_]+", code)


def test_model_endpoints_valid():
    for _code, _name, endpoint in meteo.FORECAST_MODELS:
        assert endpoint in ("forecast", "ensemble")


def test_forecast_days_is_maximum():
    assert meteo.FORECAST_DAYS == 16


def test_variables_nonempty():
    assert meteo.HOURLY_VARIABLES
    assert meteo.DAILY_VARIABLES
    assert meteo.VERIFICATION_VARIABLES


def test_cape_in_hourly_variables():
    assert "cape" in meteo.HOURLY_VARIABLES


def test_duplicate_model_codes():
    codes = [c for c, _n, _e in meteo.FORECAST_MODELS]
    assert len(codes) == len(set(codes))
