"""MeteoMap — сравнение погодных моделей и усреднённый прогноз для Ярославля."""

LAT = 57.63
LON = 39.87
TIMEZONE = "Europe/Moscow"
FORECAST_DAYS = 7

# (model_code, display_name, endpoint) — endpoint: "forecast" or "ensemble"
FORECAST_MODELS = [
    ("ecmwf_ifs025", "ECMWF IFS 0.25°", "forecast"),
    ("ecmwf_aifs025", "ECMWF AIFS", "forecast"),
    ("cma_grapes_global", "CMA GRAPES", "forecast"),
    ("bom_access_global", "BOM ACCESS-G", "forecast"),
    ("ncep_gfs_seamless", "NOAA GFS", "forecast"),
    ("jma_gsm", "JMA GSM", "forecast"),
    ("kma_gdps", "KMA GDPS", "forecast"),
    ("dwd_icon_global", "DWD ICON", "forecast"),
    ("gem_global", "GEM Global", "forecast"),
    ("meteofrance_arpege_world025", "Météo-France ARPEGE", "forecast"),
    ("ukmo_global_deterministic_10km", "UKMO Global", "forecast"),
    ("ncep_gefs_seamless", "NOAA GEFS (ensemble mean)", "ensemble"),
    ("google_weathernext", "Google WeatherNext", "ensemble"),
]

HOURLY_VARIABLES = [
    "temperature_2m", "apparent_temperature", "dew_point_2m",
    "relative_humidity_2m", "precipitation", "precipitation_probability",
    "snowfall", "weather_code", "pressure_msl", "cloud_cover",
    "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m",
    "visibility", "shortwave_radiation",
]

DAILY_VARIABLES = [
    "temperature_2m_max", "temperature_2m_min", "precipitation_sum",
    "wind_speed_10m_max", "sunshine_duration",
]

VERIFICATION_VARIABLES = [
    "temperature_2m", "precipitation", "wind_speed_10m",
]


def main() -> None:
    pass


if __name__ == "__main__":
    main()
