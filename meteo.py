"""MeteoMap — сравнение погодных моделей и усреднённый прогноз."""

LOCATIONS = [
    {"name": "Ярославль", "slug": "yaroslavl", "lat": 57.63, "lon": 39.87},
    {"name": "Цеденево", "slug": "tsedenevo", "lat": 57.533, "lon": 39.905},
    {"name": "Рыбинск", "slug": "rybinsk", "lat": 58.045, "lon": 38.845},
    {"name": "Ростов Великий", "slug": "rostov", "lat": 57.186, "lon": 39.413},
    {"name": "Петропавловка", "slug": "petropavlovka", "lat": 50.09, "lon": 40.89},
    {"name": "Москва", "slug": "moscow", "lat": 55.7558, "lon": 37.6173,
     "external": False},
    {"name": "Лоо", "slug": "loo", "lat": 43.70, "lon": 39.59},
    {"name": "Борок", "slug": "borok", "lat": 57.975, "lon": 38.227},
    {"name": "Балакирево", "slug": "balakirevo", "lat": 56.507, "lon": 38.846},
]
TIMEZONE = "Europe/Moscow"
FORECAST_DAYS = 16

# (model_code, display_name, endpoint) — endpoint: "forecast" or "ensemble"
FORECAST_MODELS = [
    ("ecmwf_ifs025", "ECMWF IFS", "forecast"),
    ("google_weathernext2_ensemble", "Google AI", "ensemble"),
    ("ncep_gefs_seamless", "NOAA GEFS", "ensemble"),
    ("ncep_gfs_seamless", "NOAA GFS", "forecast"),
    ("jma_gsm", "JMA GSM", "forecast"),
    ("gem_global", "GEM Global", "forecast"),
    ("dwd_icon_global", "DWD ICON", "forecast"),
    ("ukmo_global_deterministic_10km", "UKMO Global", "forecast"),
    ("cma_grapes_global", "CMA GRAPES", "forecast"),
    ("meteofrance_arpege_world025", "Météo-France", "forecast"),
    ("ecmwf_aifs025", "ECMWF AIFS", "forecast"),
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
    "wind_speed_10m_max", "wind_direction_10m_dominant", "sunshine_duration",
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

# Внешние источники с API-ключами (OpenWeather / Visual Crossing)
OWM_URL = "https://api.openweathermap.org/data/2.5/forecast"
OWM_CODE = "owm"
OWM_NAME = "OpenWeather"

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


VC_URL = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/"
VC_CODE = "vc"
VC_NAME = "Visual Crossing"

# Visual Crossing icon -> WMO
VC_WMO = {
    "clear-day": 0, "clear-night": 0,
    "partly-cloudy-day": 2, "partly-cloudy-night": 2,
    "cloudy": 3,
    "fog": 45, "wind": 45,
    "rain": 61, "showers-day": 80, "showers-night": 80,
    "rain-snow": 66, "rain-snow-showers-day": 67, "rain-snow-showers-night": 67,
    "sleet": 66,
    "snow": 71, "snow-showers-day": 85, "snow-showers-night": 85,
    "hail": 96,
    "thunderstorm": 95, "thunder-rain": 95,
    "thunder-showers-day": 95, "thunder-showers-night": 95,
}

MB_URL = "https://my.meteoblue.com/packages/basic-1h"
MB_CODE = "mb"
MB_NAME = "MeteoBlue"

WWO_URL = "https://api.worldweatheronline.com/premium/v1/weather.ashx"
WWO_CODE = "wwo"
WWO_NAME = "World Weather"

XW_URL = "https://data.api.xweather.com/forecasts"
XW_CODE = "xweather"
XW_NAME = "Xweather"

TW_URL = "https://api.tomorrow.io/v4/weather/forecast"
TW_CODE = "tomorrow"
TW_NAME = "Tomorrow.io"

# Tomorrow.io weather codes -> WMO
TW_WMO = {
    1000: 0, 1100: 1, 1001: 2, 1101: 2, 1002: 3, 1102: 3,
    2000: 45, 2100: 45,
    3000: 51, 3001: 51, 3002: 55,
    4000: 61, 4100: 61, 4001: 61, 4002: 65,
    4200: 80, 4300: 80, 4400: 82,
    5000: 71, 5100: 71, 5001: 71, 5002: 75,
    5200: 85, 5300: 86,
    6000: 56, 6001: 56, 6002: 57,
    6100: 66, 6200: 66, 6201: 67,
    7000: 77, 7100: 77, 7200: 77, 7300: 77,
    8000: 95, 8100: 95, 8200: 95,
}

# Meteoblue hourly pictocode -> WMO (docs.meteoblue.com/en/meteo/variables/pictograms)
MB_WMO = {
    1: 0, 2: 0, 3: 0,
    4: 1, 5: 2, 6: 2, 7: 2, 8: 2, 9: 2,
    10: 95, 11: 95, 12: 95,
    13: 0, 14: 0, 15: 0,
    16: 45, 17: 45, 18: 45,
    19: 3, 20: 3, 21: 3, 22: 3,
    23: 61,
    24: 71,
    25: 82,
    26: 71,
    27: 95, 28: 95,
    29: 71,
    30: 95,
    31: 61,
    32: 71,
    33: 61,
    34: 71,
    35: 67,
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
        "wind_speed_unit": "ms",
    }
    resp = request_with_retry(
        ENDPOINTS[endpoint], params,
        timeout=30 if endpoint == "ensemble" else 15,
    )
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
        "wind_speed_unit": "ms",
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
        "wind_speed_unit": "ms",
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


def fetch_vc(lat=None, lon=None, api_key=None):
    """Visual Crossing 15-day hourly forecast -> строки YR-подобного вида."""
    if lat is None:
        lat = LOCATIONS[0]["lat"]
    if lon is None:
        lon = LOCATIONS[0]["lon"]
    key = api_key or os.environ.get("VISUALCROSSING_KEY")
    if not key:
        print("[warn] VISUALCROSSING_KEY not set, skipping VC")
        return []
    params = {"key": key, "unitGroup": "metric", "include": "hours"}
    url = VC_URL + f"{lat}%2C{lon}"
    resp = request_with_retry(url, params, timeout=30)
    rows = []
    for day in resp.get("days", []):
        for hour in day.get("hours", []):
            ts = hour.get("datetimeEpoch")
            if ts is None:
                continue
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            wind_kph = hour.get("windspeed")
            gust_kph = hour.get("windgust")
            vis_km = hour.get("visibility")
            pressure_mb = hour.get("pressure")
            rows.append({
                "utc": dt,
                "temperature_2m": hour.get("temp"),
                "apparent_temperature": hour.get("feelslike"),
                "dew_point_2m": hour.get("dew"),
                "relative_humidity_2m": hour.get("humidity"),
                "precipitation": hour.get("precip"),
                "precipitation_probability": hour.get("precipprob"),
                "weather_code": VC_WMO.get(hour.get("icon")),
                "pressure_msl": round(pressure_mb * HPA_TO_MMHG, 1)
                if pressure_mb is not None else None,
                "cloud_cover": hour.get("cloudcover"),
                "wind_speed_10m": round(wind_kph / 3.6, 2)
                if wind_kph is not None else None,
                "wind_direction_10m": hour.get("winddir"),
                "wind_gusts_10m": round(gust_kph / 3.6, 2)
                if gust_kph is not None else None,
                "visibility": round(vis_km * 1000) if vis_km is not None else None,
            })
    return rows


def fetch_mb(lat=None, lon=None, api_key=None):
    """Meteoblue basic-1h hourly forecast -> строки YR-подобного вида."""
    if lat is None:
        lat = LOCATIONS[0]["lat"]
    if lon is None:
        lon = LOCATIONS[0]["lon"]
    key = api_key or os.environ.get("METEOBLUE_KEY")
    if not key:
        print("[warn] METEOBLUE_KEY not set, skipping MB")
        return []
    params = {
        "apikey": key,
        "lat": lat,
        "lon": lon,
        "format": "json",
    }
    resp = request_with_retry(MB_URL, params, timeout=30)
    offset = resp.get("metadata", {}).get("utc_timeoffset") or 0
    tz = timezone(timedelta(hours=offset))
    data = resp.get("data_1h", {})
    times = data.get("time") or []
    temps = data.get("temperature") or []
    feels = data.get("felttemperature") or []
    humidity = data.get("relativehumidity") or []
    precip = data.get("precipitation") or []
    precip_prob = data.get("precipitation_probability") or []
    picto = data.get("pictocode") or []
    pressure = data.get("sealevelpressure") or []
    windspeed = data.get("windspeed") or []
    winddir = data.get("winddirection") or []
    rows = []
    for i, t in enumerate(times):
        try:
            dt = datetime.strptime(t, "%Y-%m-%d %H:%M").replace(tzinfo=tz)
        except (TypeError, ValueError):
            continue
        p = pressure[i] if i < len(pressure) else None
        rows.append({
            "utc": dt.astimezone(timezone.utc),
            "temperature_2m": temps[i] if i < len(temps) else None,
            "apparent_temperature": feels[i] if i < len(feels) else None,
            "dew_point_2m": None,
            "relative_humidity_2m": humidity[i] if i < len(humidity) else None,
            "precipitation": precip[i] if i < len(precip) else None,
            "precipitation_probability": precip_prob[i] if i < len(precip_prob) else None,
            "weather_code": MB_WMO.get(picto[i]) if i < len(picto) else None,
            "pressure_msl": round(p * HPA_TO_MMHG, 1) if p is not None else None,
            "cloud_cover": None,
            "wind_speed_10m": windspeed[i] if i < len(windspeed) else None,
            "wind_direction_10m": winddir[i] if i < len(winddir) else None,
            "wind_gusts_10m": None,
            "visibility": None,
        })
    return rows


def _utc_now():
    return datetime.now(timezone.utc)


def _utc_hour_key():
    """Ключ 3-часового окна: Meteoblue опрашивается не чаще раза в 3 часа."""
    n = _utc_now()
    return f"{n:%Y%m%d}{n.hour // 3}"


def _mb_cache_path():
    return os.environ.get("MB_CACHE_FILE") or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "mb_cache.json")


def fetch_mb_cached(lat=None, lon=None):
    """Meteoblue не чаще раза в 3 часа: переиспользуем ответ между сборками."""
    path = _mb_cache_path()
    hour = _utc_hour_key()
    try:
        with open(path, encoding="utf-8") as f:
            blob = json.load(f)
        if blob.get("hour") == hour and blob.get("rows"):
            return [dict(r, utc=datetime.fromisoformat(r["utc"]))
                    for r in blob["rows"]]
    except Exception:
        pass
    rows = fetch_mb(lat=lat, lon=lon)
    if rows:
        try:
            blob = {"hour": hour,
                    "rows": [dict(r, utc=r["utc"].isoformat()) for r in rows]}
            with open(path, "w", encoding="utf-8") as f:
                json.dump(blob, f)
        except Exception:
            pass
    return rows


# WWO weather code -> WMO (worldweatheronline.com/weather-api/api/docs/weather-icons)
WWO_WMO = {
    113: 0, 116: 2, 119: 3, 122: 3, 143: 45,
    176: 80, 179: 71, 182: 66, 185: 67,
    200: 95, 227: 71, 230: 85, 248: 48,
    260: 48, 263: 51, 266: 53, 281: 56, 284: 57,
    293: 51, 296: 53, 299: 55, 302: 61, 305: 63,
    308: 65, 311: 56, 314: 57, 317: 66, 320: 67,
    323: 71, 326: 73, 329: 77, 332: 75, 335: 77,
    338: 75, 350: 67, 353: 80, 356: 81, 359: 82,
    362: 66, 365: 67, 368: 71, 371: 77, 374: 67,
    377: 67, 386: 95, 389: 96, 392: 99, 395: 99,
}


def fetch_wwo(lat=None, lon=None, api_key=None):
    """World Weather Online 14-day hourly forecast -> строки YR-подобного вида."""
    if lat is None:
        lat = LOCATIONS[0]["lat"]
    if lon is None:
        lon = LOCATIONS[0]["lon"]
    key = api_key or os.environ.get("WWO_KEY")
    if not key:
        print("[warn] WWO_KEY not set, skipping WWO")
        return []
    params = {
        "key": key,
        "q": f"{lat},{lon}",
        "format": "json",
        "tp": "1",
        "num_of_days": 5,
        "includelocation": "1",
    }
    resp = request_with_retry(WWO_URL, params, timeout=30)
    data = resp.get("data", resp)
    if data.get("error"):
        print(f"[warn] wwo World Weather Online: {data['error']}")
        return []
    rows = []
    for day in data.get("weather", []):
        for h in day.get("hourly", []):
            time_str = h.get("time")
            if time_str is None:
                continue
            try:
                hh = int(time_str) // 100
                dt = datetime.strptime(
                    day["date"] + f" {hh:02d}:00", "%Y-%m-%d %H:%M"
                ).replace(tzinfo=timezone.utc)
            except (KeyError, ValueError):
                continue
            wind_kph = h.get("windspeedKmph")
            gust_kph = h.get("WindGustKmph")
            pressure = h.get("pressure")
            wwo_code = h.get("weatherCode")
            try:
                wmo_code = WWO_WMO.get(int(wwo_code)) if wwo_code is not None else None
            except (TypeError, ValueError):
                wmo_code = None
            rows.append({
                "utc": dt,
                "temperature_2m": _float(h.get("tempC")),
                "apparent_temperature": _float(h.get("FeelsLikeC")),
                "dew_point_2m": _float(h.get("DewPointC")),
                "relative_humidity_2m": _float(h.get("humidity")),
                "precipitation": _float(h.get("precipMM")),
                "precipitation_probability": _float(h.get("chanceofrain")),
                "weather_code": wmo_code,
                "pressure_msl": round(float(pressure) * HPA_TO_MMHG, 1)
                if pressure is not None else None,
                "cloud_cover": _float(h.get("cloudcover")),
                "wind_speed_10m": round(float(wind_kph) / 3.6, 2)
                if wind_kph is not None else None,
                "wind_direction_10m": _float(h.get("winddirDegree")),
                "wind_gusts_10m": round(float(gust_kph) / 3.6, 2)
                if gust_kph is not None else None,
                "visibility": round(float(h.get("visibility", 0)) * 1000)
                if h.get("visibility") is not None else None,
            })
    return rows


def _float(v):
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# Xweather coded weather -> WMO
XW_CLOUD = {"CL": 0, "FW": 10, "SC": 50, "BK": 80, "OV": 100}
XW_WX = {"R": 61, "RW": 80, "RS": 66, "IP": 66, "ZR": 66, "ZL": 56,
         "S": 71, "SW": 85, "SN": 71, "SI": 66,
         "T": 95, "TO": 99,
         "L": 51, "ZF": 56, "F": 45, "BR": 45, "H": 45}


def _xw_wmo(code_str):
    if not code_str:
        return None
    parts = code_str.split(":")
    wx = parts[2].strip() if len(parts) > 2 else ""
    if wx in XW_WX:
        return XW_WX[wx]
    cloud = parts[0].strip() if parts else ""
    if cloud in XW_CLOUD:
        cv = XW_CLOUD[cloud]
        return 0 if cv < 15 else (2 if cv < 40 else 3)
    return None


def fetch_xw(lat=None, lon=None, api_key=None):
    """Xweather 15-day hourly forecast -> строки YR-подобного вида."""
    if lat is None:
        lat = LOCATIONS[0]["lat"]
    if lon is None:
        lon = LOCATIONS[0]["lon"]
    key = api_key or os.environ.get("XWEATHER_KEY")
    if not key:
        print("[warn] XWEATHER_KEY not set, skipping Xweather")
        return []
    url = f"{XW_URL}/{lat},{lon}"
    params = {"filter": "1hr", "limit": "360"}
    if "_" in key:
        cid, csec = key.split("_", 1)
        params["client_id"] = cid
        params["client_secret"] = csec
    else:
        params["client_id"] = key
        params["client_secret"] = key
    resp = request_with_retry(url, params, timeout=30)
    rows = []
    for place in resp.get("response", []):
        for p in place.get("periods", []):
            ts = p.get("timestamp")
            if ts is None:
                continue
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            wind_mps = p.get("windSpeedMPS")
            gust_mps = p.get("windGustMPS")
            rows.append({
                "utc": dt,
                "temperature_2m": p.get("tempC"),
                "apparent_temperature": p.get("feelslikeC"),
                "dew_point_2m": p.get("dewpointC"),
                "relative_humidity_2m": p.get("humidity"),
                "precipitation": p.get("precipMM"),
                "precipitation_probability": p.get("pop"),
                "weather_code": _xw_wmo(p.get("weatherPrimaryCoded")),
                "pressure_msl": p.get("pressureMB"),
                "cloud_cover": p.get("sky"),
                "wind_speed_10m": wind_mps,
                "wind_direction_10m": p.get("windDirDEG"),
                "wind_gusts_10m": gust_mps,
                "visibility": round(p.get("visibilityKM", 0) * 1000)
                if p.get("visibilityKM") is not None else None,
            })
    return rows


def fetch_tomorrow(lat=None, lon=None, api_key=None):
    """Tomorrow.io hourly forecast -> строки YR-подобного вида."""
    if lat is None:
        lat = LOCATIONS[0]["lat"]
    if lon is None:
        lon = LOCATIONS[0]["lon"]
    key = api_key or os.environ.get("TOMORROW_KEY")
    if not key:
        print("[warn] TOMORROW_KEY not set, skipping Tomorrow.io")
        return []
    fields = [
        "temperature", "temperatureApparent", "dewPoint",
        "humidity", "precipitationProbability", "precipitationIntensity",
        "weatherCode", "cloudCover", "pressureSurfaceLevel",
        "windSpeed", "windDirection", "windGust",
        "visibility",
    ]
    params = {
        "location": f"{lat},{lon}",
        "timesteps": "1h",
        "units": "metric",
        "fields": ",".join(fields),
        "apikey": key,
    }
    resp = request_with_retry(TW_URL, params, timeout=30)
    rows = []
    hourly = resp.get("timelines", {}).get("hourly", resp.get("data", {}).get("timelines", {}).get("hourly", []))
    for entry in hourly:
        ts = entry.get("time")
        if ts is None:
            continue
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        v = entry.get("values", {})
        wmo = TW_WMO.get(v.get("weatherCode"))
        rows.append({
            "utc": dt,
            "temperature_2m": v.get("temperature"),
            "apparent_temperature": v.get("temperatureApparent"),
            "dew_point_2m": v.get("dewPoint"),
            "relative_humidity_2m": v.get("humidity"),
            "precipitation": v.get("precipitationIntensity"),
            "precipitation_probability": v.get("precipitationProbability"),
            "weather_code": wmo,
            "pressure_msl": v.get("pressureSurfaceLevel"),
            "cloud_cover": v.get("cloudCover"),
            "wind_speed_10m": v.get("windSpeed"),
            "wind_direction_10m": v.get("windDirection"),
            "wind_gusts_10m": v.get("windGust"),
            "visibility": round(v.get("visibility", 0) * 1000)
            if v.get("visibility") is not None else None,
        })
    return rows


_EXT = ["yaroslavl", "tsedenevo"]
EXTERNAL_MODELS = [
    (OWM_CODE, OWM_NAME, fetch_owm, _EXT),
    (VC_CODE, VC_NAME, fetch_vc, _EXT),
    (MB_CODE, MB_NAME, fetch_mb_cached, ["tsedenevo"]),
    (WWO_CODE, WWO_NAME, fetch_wwo, _EXT),
    (XW_CODE, XW_NAME, fetch_xw, _EXT),
    (TW_CODE, TW_NAME, fetch_tomorrow, _EXT),
]


def fetch_external_providers(providers, locations, max_workers=5):
    """Параллельно грузит строки внешних провайдеров по всем городам.
    Возвращает {code: {slug: rows}}."""
    def _fetch(code, name, fetch_fn, loc):
        try:
            return code, loc["slug"], fetch_fn(lat=loc["lat"], lon=loc["lon"])
        except Exception as exc:
            print(f"[warn] {code} {name}: {exc}")
            return code, loc["slug"], []

    out = {}
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = []
        for item in providers:
            code, name, fn = item[0], item[1], item[2]
            slugs = item[3] if len(item) > 3 else None
            locs = [l for l in locations if slugs is None or l["slug"] in slugs]
            for loc in locs:
                futures.append(ex.submit(_fetch, code, name, fn, loc))
        for f in futures:
            code, slug, rows = f.result()
            out.setdefault(code, {})[slug] = rows
    return out


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


_EXTERNAL_LOW = {OWM_CODE, VC_CODE, MB_CODE, WWO_CODE, TW_CODE}
_EXTERNAL_MED = {XW_CODE}

def make_weights(mae_by_model, variable):
    inv = {}
    for code, mae in mae_by_model.items():
        m = mae.get(variable)
        if m is not None and m > 0:
            inv[code] = 1.0 / m
    if not inv:
        return {code: 1.0 / len(mae_by_model) for code in mae_by_model}
    lowest = min(inv.values())
    verified = sorted(inv.values())
    mid = verified[len(verified) // 2]
    for code in mae_by_model:
        if code in inv:
            continue
        if code in _EXTERNAL_MED:
            inv[code] = mid
        else:
            inv[code] = lowest
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
    with ThreadPoolExecutor(max_workers=5) as ex:
        future_by_code = {
            code: ex.submit(fetch_hist, code, start_date, end_date, variables)
            for code in model_codes
        }
    for code in model_codes:
        try:
            resp = future_by_code[code].result()
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
    if VC_CODE in codes:
        attribs.append('<a href="https://www.visualcrossing.com/">Visual Crossing</a>')
    if MB_CODE in codes:
        attribs.append('<a href="https://www.meteoblue.com/">Meteoblue</a>')
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


def build_city_payload(loc, raw_by_model, external_rows, generated_at, external_enabled):
    model_codes = [c for c, _n, _e in FORECAST_MODELS]
    model_names = {c: n for c, n, _e in FORECAST_MODELS}
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
        return None

    verification = {}
    for days in (7, 30):
        start, end = date_window(days)
        verification[f"{days}d"] = verify_models(
            model_codes, VERIFICATION_VARIABLES, start, end,
            fetch_hist=_city_hist(loc), fetch_arch=_city_arch(loc),
        )
    if external_enabled:
        for code, _name, _fn, *_ in EXTERNAL_MODELS:
            verification["7d"][code] = {v: None for v in VERIFICATION_VARIABLES}
            verification["30d"][code] = {v: None for v in VERIFICATION_VARIABLES}
    weights_by_var = {
        v: make_weights(verification["7d"], v)
        for v in VERIFICATION_VARIABLES
    }

    grid = next(iter(hourly_by_model.values()))["time"]
    city_codes = list(model_codes)
    city_names = dict(model_names)
    providers = [(YR_CODE, YR_NAME, fetch_yr)] + list(EXTERNAL_MODELS[:1])
    if external_enabled:
        providers = providers + list(EXTERNAL_MODELS[1:])
    for code, name, _fn, *_ in providers:
        rows = external_rows.get(code, {}).get(loc["slug"], [])
        if not rows:
            continue
        if code == YR_CODE:
            hourly_by_model[YR_CODE] = align_yr_to_grid(
                rows, grid, timezone(timedelta(hours=3))
            )
        else:
            hourly_by_model[code] = align_to_grid(
                rows, grid, timezone(timedelta(hours=3))
            )
        city_codes.append(code)
        city_names[code] = name

    consensus = assemble_consensus(
        hourly_by_model, HOURLY_VARIABLES, weights_by_var
    )
    return build_payload(
        city_codes, city_names, hourly_by_model, daily_by_model,
        consensus, verification, generated_at, loc,
    )


def main():
    generated_at = moscow_now_iso()
    raw_by_model = fetch_all_forecasts(
        FORECAST_MODELS, HOURLY_VARIABLES,
        days=FORECAST_DAYS, timezone=TIMEZONE,
    )
    if not raw_by_model:
        raise SystemExit("no model data available")

    external_enabled = os.environ.get("ENABLE_EXTERNAL") == "1"
    providers = [(YR_CODE, YR_NAME, fetch_yr, _EXT)]
    if external_enabled:
        providers = providers + list(EXTERNAL_MODELS)
    external_rows = fetch_external_providers(
        providers, [loc for loc in LOCATIONS if loc.get("external", True)]
    )

    payload_by_city = {}
    for loc in LOCATIONS:
        payload = build_city_payload(
            loc, raw_by_model, external_rows, generated_at, external_enabled,
        )
        if payload is not None:
            payload_by_city[loc["slug"]] = payload

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
    write_index(render(template, payload_by_city[LOCATIONS[0]["slug"]]))
    print(f"[ok] index.html + {len(payload_by_city)} city json written")


if __name__ == "__main__":
    main()
