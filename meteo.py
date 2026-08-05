"""MeteoMap — сравнение погодных моделей и усреднённый прогноз для Ярославля."""

LAT = 57.63
LON = 39.87
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
    return request_with_retry(ENDPOINTS[endpoint], params, timeout=15)


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
    return request_with_retry(ENDPOINTS["historical"], params, timeout=20)


def fetch_archive(start_date, end_date, variables, lat=LAT, lon=LON):
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": ",".join(variables),
        "timezone": "UTC",
    }
    return request_with_retry(ENDPOINTS["archive"], params, timeout=20)


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


def fetch_yr(lat=LAT, lon=LON):
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


def align_yr_to_grid(rows, grid, tz):
    out = {v: [None] * len(grid) for v in HOURLY_VARIABLES}
    grid_idx = {t: i for i, t in enumerate(grid)}
    for row in rows:
        key = row["utc"].astimezone(tz).strftime("%Y-%m-%dT%H:00")
        idx = grid_idx.get(key)
        if idx is None:
            continue
        for v in YR_VARIABLES:
            out[v][idx] = row[v]
    return {"time": list(grid), "data": out}


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
                  consensus, verification, generated_at):
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
        "location": {"name": "Ярославль", "lat": LAT, "lon": LON},
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
    html = template.replace(
        "__DATA__", json.dumps(payload, ensure_ascii=False)
    )
    html = html.replace("__GENERATED_AT__", payload["generated_at"])
    html = html.replace("__CITY__", payload["location"]["name"])
    html = html.replace(
        "__ATTRIBUTION__",
        '<a href="https://open-meteo.com/">Weather data by Open-Meteo.com</a>',
    )
    return html


def write_index(html, path="index.html"):
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


def moscow_now_iso():
    """Текущее московское время (UTC+3) в ISO-8601 с явным смещением."""
    return datetime.now(timezone(timedelta(hours=3))).isoformat(timespec="seconds")


def main():
    generated_at = moscow_now_iso()
    model_codes = [c for c, _n, _e in FORECAST_MODELS]
    model_names = {c: n for c, n, _e in FORECAST_MODELS}
    hourly_by_model = {}
    daily_by_model = {}
    for code, _name, endpoint in FORECAST_MODELS:
        try:
            resp = fetch_model(
                code, endpoint, HOURLY_VARIABLES,
                days=FORECAST_DAYS, timezone=TIMEZONE,
            )
        except Exception as exc:
            print(f"[warn] {code}: {exc}")
            continue
        hourly_by_model[code] = normalize_model_response(resp, HOURLY_VARIABLES)
        daily_by_model[code] = dict(resp.get("daily") or {})
    if not hourly_by_model:
        raise SystemExit("no model data available")
    verification = {}
    for days in (7, 30):
        start, end = date_window(days)
        verification[f"{days}d"] = verify_models(
            model_codes, VERIFICATION_VARIABLES, start, end
        )
    weights_by_var = {
        v: make_weights(verification["7d"], v)
        for v in VERIFICATION_VARIABLES
    }
    try:
        yr_rows = fetch_yr()
    except Exception as exc:
        print(f"[warn] {YR_CODE}: {exc}")
        yr_rows = []
    if yr_rows and hourly_by_model:
        grid = next(iter(hourly_by_model.values()))["time"]
        hourly_by_model[YR_CODE] = align_yr_to_grid(
            yr_rows, grid, timezone(timedelta(hours=3))
        )
        model_codes.append(YR_CODE)
        model_names[YR_CODE] = YR_NAME
    consensus = assemble_consensus(
        hourly_by_model, HOURLY_VARIABLES, weights_by_var
    )
    payload = build_payload(
        model_codes, model_names, hourly_by_model, daily_by_model,
        consensus, verification, generated_at,
    )
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "template.html"), encoding="utf-8") as f:
        template = f.read()
    write_index(render(template, payload))
    print(
        f"[ok] index.html written; models={len(hourly_by_model)} "
        f"hours={len(consensus['time'])}"
    )


if __name__ == "__main__":
    main()
