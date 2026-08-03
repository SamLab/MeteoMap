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


import requests

ENDPOINTS = {
    "forecast": "https://api.open-meteo.com/v1/forecast",
    "ensemble": "https://api.open-meteo.com/v1/ensemble",
    "historical": "https://historical-forecast-api.open-meteo.com/v1/forecast",
    "archive": "https://archive-api.open-meteo.com/v1/archive",
}


def fetch_model(code, endpoint, variables, days=FORECAST_DAYS,
                lat=LAT, lon=LON, timezone="UTC"):
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(variables),
        "daily": ",".join(DAILY_VARIABLES),
        "timezone": timezone,
        "forecast_days": days,
        "models": code,
    }
    resp = requests.get(ENDPOINTS[endpoint], params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch_historical_model(code, start_date, end_date, variables,
                           lat=LAT, lon=LON):
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": ",".join(variables),
        "timezone": "UTC",
        "models": code,
    }
    resp = requests.get(ENDPOINTS["historical"], params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def fetch_archive(start_date, end_date, variables, lat=LAT, lon=LON):
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": ",".join(variables),
        "timezone": "UTC",
    }
    resp = requests.get(ENDPOINTS["archive"], params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def normalize_model_response(resp, variables):
    hourly = resp.get("hourly") or {}
    times = hourly.get("time") or []
    data = {}
    for var in variables:
        arr = hourly.get(var)
        data[var] = list(arr) if arr is not None else [None] * len(times)
    return {"time": list(times), "data": data}


import math
from collections import Counter

# WMO weather-code priority: higher = more adverse (used for tie-breaks)
WEATHER_PRIORITY = {
    0: 0, 1: 1, 2: 1, 3: 1, 45: 2, 48: 2,
    51: 3, 53: 3, 55: 3, 56: 3, 57: 3,
    61: 4, 63: 4, 65: 4, 66: 4, 67: 4,
    71: 5, 73: 5, 75: 5, 77: 5,
    80: 4, 81: 4, 82: 4, 85: 5, 86: 5,
    95: 6, 96: 7, 99: 7,
}


def mean(values):
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def median(values):
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    n = len(vals)
    mid = n // 2
    if n % 2:
        return vals[mid]
    return (vals[mid - 1] + vals[mid]) / 2


def circular_mean(degrees):
    vals = [v for v in degrees if v is not None]
    if not vals:
        return None
    xs = sum(math.cos(math.radians(v)) for v in vals)
    ys = sum(math.sin(math.radians(v)) for v in vals)
    return math.degrees(math.atan2(round(ys, 12) or 0.0, round(xs, 12) or 0.0)) % 360


def weather_code_consensus(codes):
    vals = [c for c in codes if c is not None]
    if not vals:
        return None
    counts = Counter(vals)
    top_count = max(counts.values())
    top = [c for c, n in counts.items() if n == top_count]
    if len(top) == 1:
        return top[0]
    return max(top, key=lambda c: WEATHER_PRIORITY.get(c, 0))


def make_weights(mae_by_model, variable):
    inv = {}
    for code, mae in mae_by_model.items():
        m = mae.get(variable)
        if m is not None and m > 0:
            inv[code] = 1.0 / m
    if not inv:
        return {code: 1.0 / len(mae_by_model) for code in mae_by_model}
    avg = sum(inv.values()) / len(inv)
    for code in mae_by_model:
        if code not in inv:
            inv[code] = avg
    total = sum(inv.values())
    return {code: w / total for code, w in inv.items()}


def weighted_consensus(values, weights):
    pairs = [
        (v, w) for v, w in zip(values, weights)
        if v is not None and w is not None
    ]
    if not pairs:
        return None
    total = sum(w for _, w in pairs)
    if total <= 0:
        return None
    return sum(v * w for v, w in pairs) / total


def main() -> None:
    pass


if __name__ == "__main__":
    main()
