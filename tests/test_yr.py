from datetime import datetime, timedelta, timezone

import meteo


def test_yr_symbol_mapping_day_night_suffixes():
    assert meteo.yr_symbol_wmo("fair_night") == 1
    assert meteo.yr_symbol_wmo("clearsky_day") == 0
    assert meteo.yr_symbol_wmo("partlycloudy_polartwilight") == 2


def test_yr_symbol_mapping_precipitation():
    assert meteo.yr_symbol_wmo("rain") == 61
    assert meteo.yr_symbol_wmo("heavyrain") == 65
    assert meteo.yr_symbol_wmo("heavyrainshowers_day") == 82
    assert meteo.yr_symbol_wmo("heavysnow") == 73
    assert meteo.yr_symbol_wmo("lightsnowshowers_night") == 85


def test_yr_symbol_mapping_thunder_and_unknown():
    assert meteo.yr_symbol_wmo("thunder") == 95
    assert meteo.yr_symbol_wmo("rainshowersandthunder") == 95
    assert meteo.yr_symbol_wmo("unknown_symbol") is None
    assert meteo.yr_symbol_wmo(None) is None


def test_align_yr_to_grid_places_values_on_moscow_hours():
    tz = timezone(timedelta(hours=3))
    grid = [
        "2026-08-06T00:00", "2026-08-06T01:00", "2026-08-06T02:00",
    ]
    rows = [
        {
            "utc": datetime(2026, 8, 5, 21, 0, tzinfo=timezone.utc),
            "temperature_2m": 17.3, "wind_speed_10m": 1.6,
            "wind_direction_10m": 94.3, "relative_humidity_2m": 87.7,
            "cloud_cover": 33.6, "pressure_msl": 762.8,
            "weather_code": 1, "precipitation": 0.0,
        },
        {
            "utc": datetime(2026, 8, 5, 22, 0, tzinfo=timezone.utc),
            "temperature_2m": 16.6, "wind_speed_10m": 1.4,
            "wind_direction_10m": 95.8, "relative_humidity_2m": 92.3,
            "cloud_cover": 1.6, "pressure_msl": 762.7,
            "weather_code": 0, "precipitation": 0.0,
        },
    ]
    out = meteo.align_yr_to_grid(rows, grid, tz)
    assert out["time"] == grid
    assert out["data"]["temperature_2m"] == [17.3, 16.6, None]
    assert out["data"]["weather_code"] == [1, 0, None]
    assert out["data"]["cape"] == [None, None, None]
    assert out["data"]["convective_inhibition"] == [None, None, None]


def test_align_yr_to_grid_skips_out_of_range_points():
    tz = timezone(timedelta(hours=3))
    grid = ["2026-08-06T00:00"]
    rows = [
        {
            "utc": datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc),
            "temperature_2m": 9.0, "wind_speed_10m": None,
            "wind_direction_10m": None, "relative_humidity_2m": None,
            "cloud_cover": None, "pressure_msl": None,
            "weather_code": None, "precipitation": None,
        },
    ]
    out = meteo.align_yr_to_grid(rows, grid, tz)
    assert out["data"]["temperature_2m"] == [None]
