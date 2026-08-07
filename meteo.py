"""MeteoMap — сравнение погодных моделей и усреднённый прогноз."""

LOCATIONS = [
    {"name": "Ярославль", "slug": "yaroslavl", "lat": 57.63, "lon": 39.87},
    {"name": "Балакирево", "slug": "balakirevo", "lat": 56.507, "lon": 38.846},
    {"name": "Цеденево", "slug": "tsedenevo", "lat": 57.533, "lon": 39.905},
]
TIMEZONE = "Europe/Moscow"
FORECAST_DAYS = 16

# (model_code, display_name, endpoint) — endpoint: "forecast" or "ensemble"
FORECAST_MODELS = [
    ("ecmwf_ifs025", "ECMWF IFS", "forecast"),
    ("ecmwf_aifs025", "ECMWF AIFS", "forecast"),
    ("cma_grapes_global", "CMA GRAPES", "forecast"),
    ("bom_access_global", "BOM ACCESS-G", "forecast"),
    ("ncep_gfs_seamless", "NOAA GFS", "forecast"),
    ("jma_gsm", "JMA GSM", "forecast"),
    ("kma_gdps", "KMA GDPS", "forecast"),
    ("dwd_icon_global", "DWD ICON", "forecast"),
    ("gem_global", "GEM Global", "forecast"),
    ("meteofrance_arpege_world025", "Météo-France", "forecast"),
    ("ukmo_global_deterministic_10km", "UKMO Global", "forecast"),
    ("ncep_gefs_seamless", "NOAA GEFS", "ensemble"),
    ("google_weathernext2_ensemble", "Google WeatherNext 2", "ensemble"),
]

HOURLY_VARIABLES = [
    "temperature_2m", "apparent_temperature", "dew_point_2m",
    "relative_humidity_2m", "precipitation", "precipitation_probability",
    "snowfall", "weather_code", "pressure_msl", "cloud_cover",
    "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m",
    "visibility", "shortwave_radiation", "cape", "convective_inhibition",
]

DAILY_VARIABLES = [
    "temperature_2m_max", "temperature_2m_min", "precipitation_sum",
    "wind_speed_10m_max", "sunshine_duration",
    "precipitation_probability_max", "cloud_cover_mean", "relative_humidity_2m_mean",
    "sunrise", "sunset",
]

VERIFICATION_VARIABLES = [
    "temperature_2m", "precipitation", "wind_speed_10m",
]

HPA_TO_MMHG = 0.750061683

YR_URL = "https://api.met.no/weatherapi/locationforecast/2.0/compact"
YR_CODE = "yr_no"
YR_NAME = "MET Norway"

# MET Norway symbol_code (без суффикса _day/_night/_polartwilight) -> WMO
YR_BASE_WMO = {
    "clearsky": 0, "fair": 1, "partlycloudy": 2, "cloudy": 3, "fog": 45,
    "lightrainshowers": 80, "rainshowers": 80, "heavyrainshowers": 82,
    "lightrain": 61, "rain": 61, "heavyrain": 65,
    "lightsnowshowers": 85, "snowshowers": 85, "heavysnowshowers": 86,
    "lightsnow": 71, "snow": 71, "heavysnow": 73,
    "lightsleetshowers": 66, "sleetshowers": 67, "heavysleetshowers": 67,
    "lightsleet": 66, "sleet": 67, "heavysleet": 67,
    "thunder": 95, "lightthunder": 95, "heavythunder": 95,
    "thundershowers": 95, "lightthundershowers": 95, "heavythundershowers": 95,
    "rainandthunder": 95, "lightrainandthunder": 95, "heavyrainandthunder": 95,
    "sleetandthunder": 95, "lightsleetandthunder": 95, "heavysleetandthunder": 95,
    "snowandthunder": 95, "lightsnowandthunder": 95, "heavysnowandthunder": 95,
    "rainshowersandthunder": 95, "lightrainshowersandthunder": 95,
    "heavyrainshowersandthunder": 95,
    "sleetshowersandthunder": 95, "lightsleetshowersandthunder": 95,
    "heavysleetshowersandthunder": 95,
    "snowshowersandthunder": 95, "lightsnowshowersandthunder": 95,
    "heavysnowshowersandthunder": 95,
}

YR_VARIABLES = [
    "temperature_2m", "wind_speed_10m", "wind_direction_10m",
    "relative_humidity_2m", "cloud_cover", "pressure_msl",
    "weather_code", "precipitation",
]

# Внешние источники с API-ключами (коды WeatherAPI.com / OpenWeather)
OWM_URL = "https://api.openweathermap.org/data/2.5/forecast"
OWM_CODE = "owm"
OWM_NAME = "OpenWeather"
WEATHERAPI_URL = "https://api.weatherapi.com/v1/forecast.json"
WEATHERAPI_CODE = "weatherapi"
WEATHERAPI_NAME = "WeatherAPI.com"

# OpenWeather condition id -> WMO
OWM_WMO = {
    200: 95, 201: 95, 202: 95, 210: 95, 211: 95, 212: 95, 221: 95,
    230: 95, 231: 95, 232: 95,
    300: 51, 301: 51, 302: 55, 310: 51, 311: 53, 312: 55,
    313: 53, 314: 55, 321: 53,
    500: 61, 501: 63, 502: 65, 503: 65, 504: 65, 511: 66,
    520: 80, 521: 81, 522: 82, 531: 82,
    600: 71, 601: 73, 602: 75, 611: 66, 612: 67, 613: 67,
    615: 66, 616: 67, 620: 85, 621: 86, 622: 86,
    701: 45, 711: 45, 721: 45, 731: 45, 741: 45, 751: 45,
    761: 45, 762: 45, 771: 45, 781: 95,
    800: 0, 801: 1, 802: 2, 803: 3, 804: 3,
}

# WeatherAPI.com condition code -> WMO
WEATHERAPI_WMO = {
    1000: 0, 1003: 1, 1006: 2, 1009: 3, 1030: 45,
    1063: 61, 1066: 71, 1069: 66, 1072: 51, 1087: 95,
    1114: 75, 1117: 75, 1135: 45, 1147: 48,
    1150: 51, 1153: 51, 1168: 56, 1171: 57,
    1180: 61, 1183: 61, 1186: 63, 1189: 63, 1192: 65, 1195: 65,
    1198: 66, 1201: 67, 1204: 66, 1207: 67,
    1210: 71, 1213: 71, 1216: 73, 1219: 73, 1222: 75, 1225: 75,
    1237: 77,
    1240: 80, 1243: 81, 1246: 82,
    1249: 66, 1252: 67,
    1255: 85, 1258: 86,
    1261: 77, 1264: 77,
    1273: 95, 1276: 95, 1279: 95, 1282: 95,
}


import requests
import time

ENDPOINTS = {
    "forecast": "https://api.open-meteo.com/v1/forecast",
    "ensemble": "https://ensemble-api.open-meteo.com/v1/ensemble",
    "historical": "https://historical-forecast-api.open-meteo.com/v1/forecast",
    "archive": "https://archive-api.open-meteo.com/v1/archive",
}


def request_with_retry(url, params, timeout, get=None, max_retries=2,
                       base_delay=5.0):
    get = get or requests.get
    for attempt in range(max_retries + 1):
        try:
            resp = get(url, params=params, timeout=timeout)
            code = getattr(resp, "status_code", None)
            retryable = code == 429 or (code is not None and code >= 500)
            if retryable and attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                print(f"[retry] HTTP {code} retry in {delay:.0f}s "
                      f"({attempt + 1}/{max_retries})")
                time.sleep(delay)
                continue
            resp.raise_for_status()
            return resp.json()
        except (requests.exceptions.Timeout,
                requests.exceptions.ConnectionError) as exc:
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                print(f"[retry] {exc} retry in {delay:.0f}s "
                      f"({attempt + 1}/{max_retries})")
                time.sleep(delay)
                continue
            raise


from concurrent.futures import ThreadPoolExecutor


def fetch_all_forecasts(models, variables, days, timezone, max_workers=5):
    """Параллельные батч-запросы по всем моделям. Возвращает {code: [ответы по городам]}."""
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        future_by_code = {
            code: ex.submit(
                fetch_model, code, endpoint, variables,
                days=days, timezone=timezone,
            )
            for code, _name, endpoint in models
        }
    raw = {}
    for code, _name, _endpoint in models:
        try:
            raw[code] = future_by_code[code].result()
        except Exception as exc:
            print(f"[warn] {code}: {exc}")
    return raw


def fetch_model(code, endpoint, variables, days=FORECAST_DAYS,
                lats=None, lons=None, timezone="UTC"):
    if lats is None:
        lats = ",".join(str(loc["lat"]) for loc in LOCATIONS)
    if lons is None:
        lons = ",".join(str(loc["lon"]) for loc in LOCATIONS)
    params = {
        "latitude": lats,
        "longitude": lons,
        "hourly": ",".join(variables),
        "daily": ",".join(DAILY_VARIABLES),
        "timezone": timezone,
        "forecast_days": days,
        "models": code,
    }
    resp = request_with_retry(ENDPOINTS[endpoint], params, timeout=15)
    return resp if isinstance(resp, list) else [resp]


def fetch_historical_model(code, start_date, end_date, variables,
                           lats=None, lons=None):
    if lats is None:
        lats = ",".join(str(loc["lat"]) for loc in LOCATIONS)
    if lons is None:
        lons = ",".join(str(loc["lon"]) for loc in LOCATIONS)
    params = {
        "latitude": lats,
        "longitude": lons,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": ",".join(variables),
        "timezone": "UTC",
        "models": code,
    }
    resp = request_with_retry(ENDPOINTS["historical"], params, timeout=20)
    return resp if isinstance(resp, list) else [resp]


def fetch_archive(start_date, end_date, variables, lats=None, lons=None):
    if lats is None:
        lats = ",".join(str(loc["lat"]) for loc in LOCATIONS)
    if lons is None:
        lons = ",".join(str(loc["lon"]) for loc in LOCATIONS)
    params = {
        "latitude": lats,
        "longitude": lons,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": ",".join(variables),
        "timezone": "UTC",
    }
    resp = request_with_retry(ENDPOINTS["archive"], params, timeout=20)
    return resp if isinstance(resp, list) else [resp]


def normalize_model_response(resp, variables):
    hourly = resp.get("hourly") or {}
    times = hourly.get("time") or []
    data = {}
    for var in variables:
        arr = hourly.get(var)
        if arr is None:
            data[var] = [None] * len(times)
        elif var == "pressure_msl":
            data[var] = [
                round(v * HPA_TO_MMHG, 1) if v is not None else None for v in arr
            ]
        elif var == "precipitation":
            data[var] = [max(0.0, v) if v is not None else None for v in arr]
        else:
            data[var] = list(arr)
    return {"time": list(times), "data": data}


def yr_symbol_wmo(code):
    if not code:
        return None
    base = code
    for suffix in ("_day", "_night", "_polartwilight"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    return YR_BASE_WMO.get(base)


def fetch_yr(lat=None, lon=None):
    if lat is None:
        lat = LOCATIONS[0]["lat"]
    if lon is None:
        lon = LOCATIONS[0]["lon"]
    resp = requests.get(
        YR_URL,
        params={"lat": lat, "lon": lon},
        headers={"User-Agent": "MeteoMap/1.0 (https://samlab.github.io/MeteoMap)"},
        timeout=20,
    )
    resp.raise_for_status()
    rows = []
    for p in resp.json()["properties"]["timeseries"]:
        t = datetime.fromisoformat(p["time"].replace("Z", "+00:00"))
        inst = p["data"]["instant"]["details"]
        n1 = p["data"].get("next_1_hours", {}) or {}
        n1s = n1.get("summary", {}) or {}
        n1d = n1.get("details", {}) or {}
        n6s = (p["data"].get("next_6_hours", {}) or {}).get("summary", {}) or {}
        code = n1s.get("symbol_code") or n6s.get("symbol_code")
        hpa = inst.get("air_pressure_at_sea_level")
        rows.append({
            "utc": t,
            "temperature_2m": inst.get("air_temperature"),
            "wind_speed_10m": inst.get("wind_speed"),
            "wind_direction_10m": inst.get("wind_from_direction"),
            "relative_humidity_2m": inst.get("relative_humidity"),
            "cloud_cover": inst.get("cloud_area_fraction"),
            "pressure_msl": round(hpa * HPA_TO_MMHG, 1) if hpa is not None else None,
            "weather_code": yr_symbol_wmo(code),
            "precipitation": n1d.get("precipitation_amount"),
        })
    return rows


def align_to_grid(rows, grid, tz):
    """Раскладывает строки источников (с ключом utc) по часовой сетке."""
    out = {v: [None] * len(grid) for v in HOURLY_VARIABLES}
    grid_idx = {t: i for i, t in enumerate(grid)}
    for row in rows:
        key = row["utc"].astimezone(tz).strftime("%Y-%m-%dT%H:00")
        idx = grid_idx.get(key)
        if idx is None:
            continue
        for v in HOURLY_VARIABLES:
            if v in row:
                out[v][idx] = row[v]
    return {"time": list(grid), "data": out}


def align_yr_to_grid(rows, grid, tz):
    return align_to_grid(rows, grid, tz)


def fetch_owm(lat=None, lon=None, api_key=None):
    """OpenWeatherMap 5-day/3-hour forecast -> строки YR-подобного вида."""
    if lat is None:
        lat = LOCATIONS[0]["lat"]
    if lon is None:
        lon = LOCATIONS[0]["lon"]
    key = api_key or os.environ.get("OPENWEATHER_KEY")
    if not key:
        print("[warn] OPENWEATHER_KEY not set, skipping OWM")
        return []
    params = {"lat": lat, "lon": lon, "appid": key,
              "units": "metric", "lang": "ru"}
    resp = request_with_retry(OWM_URL, params, timeout=20)
    rows = []
    for item in resp.get("list", []):
        dt = datetime.fromtimestamp(item["dt"], tz=timezone.utc)
        main = item.get("main") or {}
        wind = item.get("wind") or {}
        clouds = item.get("clouds") or {}
        w = (item.get("weather") or [{}])[0]
        rain = (item.get("rain") or {}).get("3h")
        snow = (item.get("snow") or {}).get("3h")
        pop = item.get("pop")
        hpa = main.get("pressure")
        prec = 0.0
        if rain is not None:
            prec += rain
        if snow is not None:
            prec += snow
        rows.append({
            "utc": dt,
            "temperature_2m": main.get("temp"),
            "apparent_temperature": main.get("feels_like"),
            "relative_humidity_2m": main.get("humidity"),
            "precipitation": prec,
            "precipitation_probability": round(pop * 100) if pop is not None else None,
            "weather_code": OWM_WMO.get(w.get("id")),
            "pressure_msl": round(hpa * HPA_TO_MMHG, 1) if hpa is not None else None,
            "cloud_cover": clouds.get("all"),
            "wind_speed_10m": wind.get("speed"),
            "wind_direction_10m": wind.get("deg"),
            "wind_gusts_10m": wind.get("gust"),
        })
    return rows


def fetch_weatherapi(lat=None, lon=None, api_key=None):
    """WeatherAPI.com 3-day hourly forecast -> строки YR-подобного вида."""
    if lat is None:
        lat = LOCATIONS[0]["lat"]
    if lon is None:
        lon = LOCATIONS[0]["lon"]
    key = api_key or os.environ.get("WEATHERAPI_KEY")
    if not key:
        print("[warn] WEATHERAPI_KEY not set, skipping WeatherAPI")
        return []
    params = {"key": key, "q": f"{lat},{lon}", "days": 3, "lang": "ru"}
    resp = request_with_retry(WEATHERAPI_URL, params, timeout=20)
    rows = []
    tz_msk = timezone(timedelta(hours=3))
    for day in resp.get("forecast", {}).get("forecastday", []):
        for hour in day.get("hour", []):
            t = datetime.strptime(hour["time"][:16], "%Y-%m-%d %H:%M")
            dt = t.replace(tzinfo=tz_msk).astimezone(timezone.utc)
            cond = hour.get("condition") or {}
            wind_kph = hour.get("wind_kph")
            gust_kph = hour.get("gust_kph")
            vis_km = hour.get("vis_km")
            pressure_mb = hour.get("pressure_mb")
            cr = hour.get("chance_of_rain")
            cs = hour.get("chance_of_snow")
            prob = None
            if cr is not None and cs is not None:
                prob = max(cr, cs)
            elif cr is not None:
                prob = cr
            elif cs is not None:
                prob = cs
            rows.append({
                "utc": dt,
                "temperature_2m": hour.get("temp_c"),
                "apparent_temperature": hour.get("feelslike_c"),
                "dew_point_2m": hour.get("dewpoint_c"),
                "relative_humidity_2m": hour.get("humidity"),
                "precipitation": hour.get("precip_mm"),
                "precipitation_probability": prob,
                "weather_code": WEATHERAPI_WMO.get(cond.get("code")),
                "pressure_msl": round(pressure_mb * HPA_TO_MMHG, 1)
                if pressure_mb is not None else None,
                "cloud_cover": hour.get("cloud"),
                "wind_speed_10m": round(wind_kph / 3.6, 2)
                if wind_kph is not None else None,
                "wind_direction_10m": hour.get("wind_degree"),
                "wind_gusts_10m": round(gust_kph / 3.6, 2)
                if gust_kph is not None else None,
                "visibility": round(vis_km * 1000) if vis_km is not None else None,
            })
    return rows


EXTERNAL_MODELS = [
    (OWM_CODE, OWM_NAME, fetch_owm),
    (WEATHERAPI_CODE, WEATHERAPI_NAME, fetch_weatherapi),
]


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


# Семейства погодных кодов: сперва выбираем семейство большинством голосов,
# внутри семейства — самый частый код (tie-break по неблагоприятности).
# Это не даёт «пасмурно» (1 код) победить, когда ясно/переменная облачность
# суммарно в большинстве (3+3+1 против 3).
WEATHER_FAMILIES = {
    "clear": {0, 1, 2},      # ясно, в основном ясно, переменная облачность
    "overcast": {3},          # пасмурно
    "fog": {45, 48},
    "drizzle": {51, 53, 55, 56, 57},
    "rain": {61, 63, 65, 66, 67},
    "snow": {71, 73, 75, 77},
    "showers": {80, 81, 82},
    "snow_showers": {85, 86},
    "thunderstorm": {95, 96, 99},
}


def _weather_family(code):
    for fam, members in WEATHER_FAMILIES.items():
        if code in members:
            return fam
    return None


def _family_priority(fam):
    members = WEATHER_FAMILIES.get(fam)
    if members is None:
        return WEATHER_PRIORITY.get(fam, 0)
    return max(WEATHER_PRIORITY.get(c, 0) for c in members)


def weather_code_consensus(codes):
    vals = [c for c in codes if c is not None]
    if not vals:
        return None
    fam_of = {c: _weather_family(c) or c for c in set(vals)}
    fam_votes = Counter(fam_of[c] for c in vals)
    top_count = max(fam_votes.values())
    top_fams = [f for f, n in fam_votes.items() if n == top_count]
    if len(top_fams) == 1:
        fam = top_fams[0]
    else:
        fam = max(top_fams, key=lambda f: (_family_priority(f), max(c for c in vals if fam_of[c] == f)))
    members = [c for c in vals if fam_of[c] == fam]
    counts = Counter(members)
    top_count = max(counts.values())
    top = [c for c, n in counts.items() if n == top_count]
    if len(top) == 1:
        return top[0]
    return max(top, key=lambda c: (WEATHER_PRIORITY.get(c, 0), c))


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


from datetime import date, timedelta


def date_window(days):
    today = date.today()
    end = today - timedelta(days=1)
    start = today - timedelta(days=days)
    return start.isoformat(), end.isoformat()


def compute_mae(predicted, actual):
    pairs = [
        (p, a) for p, a in zip(predicted, actual)
        if p is not None and a is not None
    ]
    if not pairs:
        return None
    return sum(abs(p - a) for p, a in pairs) / len(pairs)


def verify_models(model_codes, variables, start_date, end_date,
                  fetch_hist=None, fetch_arch=None):
    fetch_hist = fetch_hist or fetch_historical_model
    fetch_arch = fetch_arch or fetch_archive
    try:
        actual_data = normalize_model_response(
            fetch_arch(start_date, end_date, variables), variables
        )["data"]
    except Exception as exc:
        print(f"[warn] verify archive: {exc}")
        return {code: {v: None for v in variables} for code in model_codes}
    result = {}
    for code in model_codes:
        try:
            resp = fetch_hist(code, start_date, end_date, variables)
        except Exception as exc:
            print(f"[warn] verify {code}: {exc}")
            continue
        model_data = normalize_model_response(resp, variables)["data"]
        result[code] = {
            v: compute_mae(model_data[v], actual_data[v])
            for v in variables
        }
    return result


def assemble_consensus(hourly_by_model, variables, weights_by_var, min_sources=2):
    hours = None
    for model in hourly_by_model.values():
        if model["time"]:
            hours = model["time"]
            break
    if hours is None:
        return {
            "time": [], "weighted": {}, "mean": {}, "median": {}, "models": {},
        }
    n = len(hours)
    model_codes = list(hourly_by_model)
    weighted = {v: [None] * n for v in variables}
    mean_out = {v: [None] * n for v in variables}
    median_out = {v: [None] * n for v in variables}
    models_out = {c: {v: [None] * n for v in variables} for c in model_codes}
    for i in range(n):
        for v in variables:
            per_model = []
            for code in model_codes:
                arr = hourly_by_model[code]["data"].get(v)
                val = arr[i] if arr and i < len(arr) else None
                models_out[code][v][i] = val
                per_model.append(val)
            present = [x for x in per_model if x is not None]
            if len(present) < min_sources:
                continue
            if v == "weather_code":
                vote = weather_code_consensus(present)
                weighted[v][i] = vote
                mean_out[v][i] = vote
                median_out[v][i] = vote
                continue
            wv = weights_by_var.get(v, {})
            weights = [wv.get(code, 1.0) for code in model_codes]
            weighted[v][i] = weighted_consensus(per_model, weights)
            mean_out[v][i] = mean(per_model)
            if v == "wind_direction_10m":
                median_out[v][i] = circular_mean(per_model)
            else:
                median_out[v][i] = median(per_model)
    return {
        "time": hours,
        "weighted": weighted,
        "mean": mean_out,
        "median": median_out,
        "models": models_out,
    }


import json
import os
from datetime import datetime, timezone


def _models_with_data(model_codes, hourly_by_model):
    """Коды моделей, у которых есть хотя бы одно значение среди почасовых данных."""
    return [
        code for code in model_codes
        if any(
            v is not None
            for arr in (hourly_by_model.get(code, {}).get("data") or {}).values()
            for v in arr
        )
    ]


def build_payload(model_codes, model_names, hourly_by_model, daily_by_model,
                  consensus, verification, generated_at, location):
    codes = _models_with_data(model_codes, hourly_by_model) or list(model_codes)
    dvars = list(DAILY_VARIABLES)
    TIME_DAILY = {"sunrise", "sunset"}
    daily_consensus = {}
    for v in dvars:
        cols = [m[v] for m in daily_by_model.values() if m.get(v)]
        if not cols:
            continue
        if v in TIME_DAILY:
            daily_consensus[v] = list(cols[0])
        else:
            length = max(len(c) for c in cols)
            daily_consensus[v] = [
                mean([c[i] for c in cols if i < len(c)]) for i in range(length)
            ]
    daily_time = next(
        (m.get("time") for m in daily_by_model.values() if m.get("time")),
        None,
    )
    return {
        "generated_at": generated_at,
        "location": location,
        "model_codes": codes,
        "model_names": {c: model_names[c] for c in codes},
        "variables": list(HOURLY_VARIABLES),
        "daily_variables": dvars,
        "time": consensus["time"],
        "weighted": consensus["weighted"],
        "mean": consensus["mean"],
        "median": consensus["median"],
        "models": {
            code: hourly_by_model[code]["data"]
            for code in codes if code in hourly_by_model
        },
        "daily": daily_consensus,
        "daily_time": daily_time,
        "verification": verification,
    }


def render(template, payload):
    cities = json.dumps(
        [{"name": l["name"], "slug": l["slug"], "lat": l["lat"], "lon": l["lon"]}
         for l in LOCATIONS], ensure_ascii=False)
    html = template.replace("__CITIES__", cities)
    html = html.replace(
        "__DATA__", json.dumps(payload, ensure_ascii=False)
    )
    html = html.replace("__GENERATED_AT__", payload["generated_at"])
    html = html.replace("__CITY__", payload["location"]["name"])
    codes = set(payload.get("model_codes") or [])
    attribs = ['<a href="https://open-meteo.com/">Weather data by Open-Meteo.com</a>']
    if YR_CODE in codes:
        attribs.append('<a href="https://www.met.no/">MET Norway</a>')
    if OWM_CODE in codes:
        attribs.append('<a href="https://openweathermap.org/">OpenWeather</a>')
    if WEATHERAPI_CODE in codes:
        attribs.append('<a href="https://www.weatherapi.com/">WeatherAPI.com</a>')
    html = html.replace("__ATTRIBUTION__", " · ".join(attribs))
    return html


def write_index(html, path="index.html"):
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


def moscow_now_iso():
    """Текущее московское время (UTC+3) в ISO-8601 с явным смещением."""
    return datetime.now(timezone(timedelta(hours=3))).isoformat(timespec="seconds")


_hist_cache = {}
_arch_cache = {}


def _city_hist(loc):
    idx = LOCATIONS.index(loc)

    def f(code, start, end, variables):
        key = (code, start, end, tuple(variables))
        if key not in _hist_cache:
            _hist_cache[key] = fetch_historical_model(code, start, end, variables)
        return _hist_cache[key][idx]
    return f


def _city_arch(loc):
    idx = LOCATIONS.index(loc)

    def f(start, end, variables):
        key = (start, end, tuple(variables))
        if key not in _arch_cache:
            _arch_cache[key] = fetch_archive(start, end, variables)
        return _arch_cache[key][idx]
    return f


def main():
    generated_at = moscow_now_iso()
    model_codes = [c for c, _n, _e in FORECAST_MODELS]
    model_names = {c: n for c, n, _e in FORECAST_MODELS}

    # один батч-запрос на модель: ответ = список по городам
    raw_by_model = {}
    for code, _name, endpoint in FORECAST_MODELS:
        try:
            raw_by_model[code] = fetch_model(
                code, endpoint, HOURLY_VARIABLES,
                days=FORECAST_DAYS, timezone=TIMEZONE,
            )
        except Exception as exc:
            print(f"[warn] {code}: {exc}")
    if not raw_by_model:
        raise SystemExit("no model data available")

    payload_by_city = {}
    for loc in LOCATIONS:
        idx = LOCATIONS.index(loc)
        hourly_by_model = {}
        daily_by_model = {}
        for code, responses in raw_by_model.items():
            if idx >= len(responses):
                print(f"[warn] {code}: no data for {loc['name']}")
                continue
            data = responses[idx]
            hourly_by_model[code] = normalize_model_response(data, HOURLY_VARIABLES)
            daily_by_model[code] = dict(data.get("daily") or {})
        if not hourly_by_model:
            print(f"[warn] no model data for {loc['name']}")
            continue

        verification = {}
        for days in (7, 30):
            start, end = date_window(days)
            verification[f"{days}d"] = verify_models(
                model_codes, VERIFICATION_VARIABLES, start, end,
                fetch_hist=_city_hist(loc), fetch_arch=_city_arch(loc),
            )
        # внешние источники: историю MAE не считаем → нейтральный (средний) вес
        external_enabled = os.environ.get("ENABLE_EXTERNAL") == "1"
        for code, _name, _fn in EXTERNAL_MODELS:
            if not external_enabled:
                continue
            verification["7d"][code] = {v: None for v in VERIFICATION_VARIABLES}
            verification["30d"][code] = {v: None for v in VERIFICATION_VARIABLES}
        weights_by_var = {
            v: make_weights(verification["7d"], v)
            for v in VERIFICATION_VARIABLES
        }
        try:
            yr_rows = fetch_yr(lat=loc["lat"], lon=loc["lon"])
        except Exception as exc:
            print(f"[warn] {YR_CODE} {loc['name']}: {exc}")
            yr_rows = []
        city_codes = list(model_codes)
        city_names = dict(model_names)
        if not hourly_by_model:
            print(f"[warn] no hourly data for {loc['name']}")
            continue
        grid = next(iter(hourly_by_model.values()))["time"]
        if yr_rows:
            hourly_by_model[YR_CODE] = align_yr_to_grid(
                yr_rows, grid, timezone(timedelta(hours=3))
            )
            city_codes.append(YR_CODE)
            city_names[YR_CODE] = YR_NAME
        for code, name, fetch_fn in EXTERNAL_MODELS:
            if not external_enabled:
                break
            try:
                rows = fetch_fn(lat=loc["lat"], lon=loc["lon"])
            except Exception as exc:
                print(f"[warn] {code} {loc['name']}: {exc}")
                rows = []
            if rows:
                hourly_by_model[code] = align_to_grid(
                    rows, grid, timezone(timedelta(hours=3))
                )
                city_codes.append(code)
                city_names[code] = name
        consensus = assemble_consensus(
            hourly_by_model, HOURLY_VARIABLES, weights_by_var
        )
        payload_by_city[loc["slug"]] = build_payload(
            city_codes, city_names, hourly_by_model, daily_by_model,
            consensus, verification, generated_at, loc,
        )

    if not payload_by_city:
        raise SystemExit("no city data available")

    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "template.html"), encoding="utf-8") as f:
        template = f.read()
    os.makedirs(os.path.join(here, "data"), exist_ok=True)
    for slug, payload in payload_by_city.items():
        with open(os.path.join(here, "data", f"{slug}.json"), "w",
                  encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False))
    # index.html рендерится с городом по умолчанию (первым)
    write_index(render(template, payload_by_city[LOCATIONS[0]["slug"]]))
    print(f"[ok] index.html + {len(payload_by_city)} city json written")


if __name__ == "__main__":
    main()
