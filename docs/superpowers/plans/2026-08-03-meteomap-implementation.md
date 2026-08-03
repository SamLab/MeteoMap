# MeteoMap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Static website that shows a 7-day hourly forecast for Yaroslavl (57.63°N, 39.87°E) from ~13 global weather models via Open-Meteo, plus two consensus forecasts (accuracy-weighted and simple mean/median), deployed hourly to GitHub Pages.

**Architecture:** Single Python pipeline (`meteo.py` + `template.html`) run by GitHub Actions every hour (triggered by external cron-job.org via `workflow_dispatch`). It fetches each model's forecast from Open-Meteo, normalizes to hour×variable tables, computes MAE per model over the past 7/30 days (Historical Forecast API vs ERA5 archive) for accuracy weights, builds weighted + mean/median consensus, and renders a static `index.html` with embedded JSON consumed by Chart.js. No database, no own history.

**Tech Stack:** Python 3.13, `requests`, `pytest`. Chart.js 4 from CDN. GitHub Actions + GitHub Pages (`gh-pages` branch). No Node, no build step.

## Global Constraints

- Python 3.13 only; runtime dependencies: `requests>=2.28.0`; dev dependency: `pytest>=8.0.0`.
- Location fixed: Yaroslavl, `LAT=57.63`, `LON=39.87`, `TIMEZONE="Europe/Moscow"`, `FORECAST_DAYS=7`.
- No database, no API keys, no files written outside the repo except `index.html`.
- UI language: Russian. Attribution required on page: `Weather data by Open-Meteo.com` linking to https://open-meteo.com (CC BY 4.0).
- Data via Open-Meteo only: forecast endpoint `https://api.open-meteo.com/v1/forecast`, ensemble endpoint `https://api.open-meteo.com/v1/ensemble`, historical forecast endpoint `https://historical-forecast-api.open-meteo.com/v1/forecast`, archive (ERA5) endpoint `https://archive-api.open-meteo.com/v1/archive`.
- Consensus: weighted (inverse MAE) AND simple mean/median, both shown. `weather_code` by majority vote with adverse-priority tiebreak; `wind_direction_10m` by circular mean; min 3 sources per variable-hour else `null`.
- Missing values are `None` (JSON `null`), never NaN. Missing model never breaks the run — it is skipped with a warning.
- Integration tests (marked `integration`) hit the real API and are NOT run in CI; unit tests run in CI with `-m "not integration"`.
- Deploy pattern copied from MopedMap: workflow force-pushes built files to `gh-pages`; GitHub Pages serves that branch.

---

### Task 1: Project scaffolding and configuration

**Files:**
- Create: `requirements.txt`
- Create: `pytest.ini`
- Create: `meteo.py` (constants section only — empty `main()` stub so the module imports)
- Create: `tests/test_config.py`
- Create: `.gitignore` entries (add `index.html`, `.venv/`, `__pycache__/`)

**Interfaces:**
- Consumes: nothing.
- Produces: module-level constants consumed by every later task:
  - `LAT: float`, `LON: float`, `TIMEZONE: str`, `FORECAST_DAYS: int`
  - `FORECAST_MODELS: list[tuple[str, str, str]]` — `(model_code, display_name, endpoint)` where endpoint is `"forecast"` or `"ensemble"`
  - `HOURLY_VARIABLES: list[str]`, `DAILY_VARIABLES: list[str]`, `VERIFICATION_VARIABLES: list[str]`
  - `main() -> None` (stub; fully wired in Task 8)

- [ ] **Step 1: Write the failing test**

`tests/test_config.py`:
```python
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


def test_variables_nonempty():
    assert meteo.HOURLY_VARIABLES
    assert meteo.DAILY_VARIABLES
    assert meteo.VERIFICATION_VARIABLES


def test_duplicate_model_codes():
    codes = [c for c, _n, _e in meteo.FORECAST_MODELS]
    assert len(codes) == len(set(codes))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'meteo'`

- [ ] **Step 3: Create `requirements.txt`**

```
requests>=2.28.0
pytest>=8.0.0
```

- [ ] **Step 4: Create `pytest.ini`**

```ini
[pytest]
markers =
    integration: real network calls to Open-Meteo (run manually, not in CI)
```

- [ ] **Step 5: Create `meteo.py` constants**

```python
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
```

- [ ] **Step 6: Add `.gitignore` entries**

Append to existing `.gitignore`:
```
index.html
.venv/
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `python -m pytest tests/ -m "not integration" -q`
Expected: PASS (all 5 tests)

- [ ] **Step 8: Commit**

```bash
git add requirements.txt pytest.ini meteo.py tests/test_config.py .gitignore
git commit -m "feat: scaffold MeteoMap project with model registry"
```

---

### Task 2: Open-Meteo API client

**Files:**
- Modify: `meteo.py` (append API-client section)
- Test: `tests/test_client.py`

**Interfaces:**
- Consumes: `LAT`, `LON`, `FORECAST_DAYS`, `DAILY_VARIABLES` from Task 1.
- Produces:
  - `ENDPOINTS: dict[str, str]`
  - `fetch_model(code: str, endpoint: str, variables: list[str], days: int = FORECAST_DAYS, lat: float = LAT, lon: float = LON, timezone: str = "UTC") -> dict` — returns raw JSON of `/v1/forecast` or `/v1/ensemble`.
  - `fetch_historical_model(code: str, start_date: str, end_date: str, variables: list[str], lat: float = LAT, lon: float = LON) -> dict`
  - `fetch_archive(start_date: str, end_date: str, variables: list[str], lat: float = LAT, lon: float = LON) -> dict`

- [ ] **Step 1: Write the failing test**

`tests/test_client.py`:
```python
import requests

import meteo


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_fetch_model_parameters(monkeypatch):
    captured = {}

    def fake_get(url, params, timeout):
        captured["url"] = url
        captured["params"] = params
        return _FakeResponse({"hourly": {"time": []}})

    monkeypatch.setattr(requests, "get", fake_get)
    out = meteo.fetch_model(
        "dwd_icon_global", "forecast", ["temperature_2m"],
        days=3, timezone="Europe/Moscow",
    )
    assert out == {"hourly": {"time": []}}
    assert captured["url"] == meteo.ENDPOINTS["forecast"]
    p = captured["params"]
    assert p["models"] == "dwd_icon_global"
    assert p["hourly"] == "temperature_2m"
    assert p["forecast_days"] == 3
    assert p["timezone"] == "Europe/Moscow"
    assert p["latitude"] == meteo.LAT
    assert p["longitude"] == meteo.LON


def test_fetch_model_uses_ensemble_endpoint(monkeypatch):
    captured = {}

    def fake_get(url, params, timeout):
        captured["url"] = url
        return _FakeResponse({})

    monkeypatch.setattr(requests, "get", fake_get)
    meteo.fetch_model("google_weathernext", "ensemble", ["temperature_2m"])
    assert captured["url"] == meteo.ENDPOINTS["ensemble"]


def test_fetch_historical_uses_historical_endpoint(monkeypatch):
    captured = {}

    def fake_get(url, params, timeout):
        captured["url"] = url
        captured["params"] = params
        return _FakeResponse({})

    monkeypatch.setattr(requests, "get", fake_get)
    meteo.fetch_historical_model(
        "dwd_icon_global", "2026-07-27", "2026-08-02", ["temperature_2m"]
    )
    assert captured["url"] == meteo.ENDPOINTS["historical"]
    assert captured["params"]["start_date"] == "2026-07-27"
    assert captured["params"]["end_date"] == "2026-08-02"


def test_fetch_archive_uses_archive_endpoint(monkeypatch):
    captured = {}

    def fake_get(url, params, timeout):
        captured["url"] = url
        assert "models" not in params
        return _FakeResponse({})

    monkeypatch.setattr(requests, "get", fake_get)
    meteo.fetch_archive("2026-07-27", "2026-08-02", ["temperature_2m"])
    assert captured["url"] == meteo.ENDPOINTS["archive"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_client.py -v`
Expected: FAIL — `AttributeError: module 'meteo' has no attribute 'ENDPOINTS'`

- [ ] **Step 3: Write the implementation**

Append to `meteo.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_client.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add meteo.py tests/test_client.py
git commit -m "feat: add Open-Meteo API client"
```

---

### Task 3: Normalization of model responses

**Files:**
- Modify: `meteo.py`
- Test: `tests/test_normalize.py`

**Interfaces:**
- Consumes: nothing beyond stdlib.
- Produces:
  - `normalize_model_response(resp: dict, variables: list[str]) -> dict` — returns `{"time": list[str], "data": {var: list[float|None]}}` where a variable absent from the API response becomes a list of `None` of the same length as `time`.

- [ ] **Step 1: Write the failing test**

`tests/test_normalize.py`:
```python
import meteo


def test_normalize_present_variables():
    resp = {
        "hourly": {
            "time": ["t0", "t1"],
            "temperature_2m": [1.0, 2.0],
            "relative_humidity_2m": [80.0, 85.0],
        }
    }
    out = meteo.normalize_model_response(
        resp, ["temperature_2m", "relative_humidity_2m", "wind_speed_10m"]
    )
    assert out["time"] == ["t0", "t1"]
    assert out["data"]["temperature_2m"] == [1.0, 2.0]
    assert out["data"]["relative_humidity_2m"] == [80.0, 85.0]
    assert out["data"]["wind_speed_10m"] == [None, None]


def test_normalize_missing_hourly_block():
    out = meteo.normalize_model_response({}, ["temperature_2m"])
    assert out["time"] == []
    assert out["data"]["temperature_2m"] == []


def test_normalize_keeps_nulls_from_api():
    resp = {"hourly": {"time": ["t0"], "temperature_2m": [None]}}
    out = meteo.normalize_model_response(resp, ["temperature_2m"])
    assert out["data"]["temperature_2m"] == [None]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_normalize.py -v`
Expected: FAIL — `AttributeError: module 'meteo' has no attribute 'normalize_model_response'`

- [ ] **Step 3: Write the implementation**

Append to `meteo.py`:
```python
def normalize_model_response(resp, variables):
    hourly = resp.get("hourly") or {}
    times = hourly.get("time") or []
    data = {}
    for var in variables:
        arr = hourly.get(var)
        data[var] = list(arr) if arr is not None else [None] * len(times)
    return {"time": list(times), "data": data}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_normalize.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add meteo.py tests/test_normalize.py
git commit -m "feat: normalize model API responses to hour-by-variable tables"
```

---

### Task 4: Statistics helpers

**Files:**
- Modify: `meteo.py`
- Test: `tests/test_stats.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `mean(values: list[float|None]) -> float|None`
  - `median(values: list[float|None]) -> float|None`
  - `circular_mean(degrees: list[float|None]) -> float|None` (result in [0, 360))
  - `weather_code_consensus(codes: list[int|None]) -> int|None`

- [ ] **Step 1: Write the failing test**

`tests/test_stats.py`:
```python
import meteo


def test_mean_basic():
    assert meteo.mean([1.0, 2.0, 3.0]) == 2.0


def test_mean_skips_none():
    assert meteo.mean([1.0, None, 3.0]) == 2.0


def test_mean_all_none():
    assert meteo.mean([None, None]) is None


def test_median_even():
    assert meteo.median([4.0, 1.0, 7.0, 2.0]) == 3.0


def test_median_odd_skips_none():
    assert meteo.median([10.0, None, 1.0, 5.0, 3.0]) == 4.0


def test_median_all_none():
    assert meteo.median([None]) is None


def test_circular_mean_north():
    assert abs(meteo.circular_mean([350.0, 10.0]) - 0.0) < 1e-6


def test_circular_mean_skips_none():
    assert abs(meteo.circular_mean([90.0, None, 270.0]) - 0.0) < 1e-6


def test_circular_mean_empty():
    assert meteo.circular_mean([]) is None


def test_weather_code_unique_winner():
    assert meteo.weather_code_consensus([61, 61, 80, 0]) == 61


def test_weather_code_tiebreak_by_adversity():
    # counts tie 61 vs 80 → both "rain", pick 61 by priority list order
    assert meteo.weather_code_consensus([61, 80, 80, 61]) == 80


def test_weather_code_skips_none():
    assert meteo.weather_code_consensus([None, 0, 0]) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_stats.py -v`
Expected: FAIL — `AttributeError: module 'meteo' has no attribute 'mean'`

- [ ] **Step 3: Write the implementation**

Append to `meteo.py`:
```python
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
    return math.degrees(math.atan2(ys, xs)) % 360


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
```

Note: `test_weather_code_tiebreak_by_adversity` uses codes 61 and 80, which both have priority 4 — so the assertion `== 80` would fail. The real tiebreak test needs different priorities. Correct test:

```python
def test_weather_code_tiebreak_by_adversity():
    # 61 (rain) and 71 (snow) tie in count → snow (priority 5) wins
    assert meteo.weather_code_consensus([61, 71, 71, 61]) == 71
```

Replace the erroneous test above with this version before running.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_stats.py -v`
Expected: PASS (13 tests)

- [ ] **Step 5: Commit**

```bash
git add meteo.py tests/test_stats.py
git commit -m "feat: add statistics helpers for consensus"
```

---

### Task 5: Accuracy weights and weighted consensus

**Files:**
- Modify: `meteo.py`
- Test: `tests/test_weights.py`

**Interfaces:**
- Consumes: `mean` (not needed directly); `VERIFICATION_VARIABLES` implied by caller.
- Produces:
  - `make_weights(mae_by_model: dict[str, dict[str, float|None]], variable: str) -> dict[str, float]` — normalized weights over all models in `mae_by_model`; models missing a positive MAE get the average inverse-MAE weight; if no model has a positive MAE, all get equal weight.
  - `weighted_consensus(values: list[float|None], weights: list[float]) -> float|None` — weights align with `values` by index; `None` values excluded and remaining weights renormalized by their sum.

- [ ] **Step 1: Write the failing test**

`tests/test_weights.py`:
```python
import meteo


def test_make_weights_inverse_mae():
    mae = {"a": {"temperature_2m": 1.0}, "b": {"temperature_2m": 3.0}}
    w = meteo.make_weights(mae, "temperature_2m")
    assert abs(w["a"] - 0.75) < 1e-6
    assert abs(w["b"] - 0.25) < 1e-6


def test_make_weights_missing_gets_average():
    mae = {
        "a": {"temperature_2m": 1.0},
        "b": {"temperature_2m": 2.0},
        "c": {},  # no data → gets average inverse weight
    }
    w = meteo.make_weights(mae, "temperature_2m")
    assert abs(sum(w.values()) - 1.0) < 1e-6
    inv = [1.0, 0.5]
    avg = sum(inv) / 2
    total = sum(inv) + avg
    assert abs(w["c"] - avg / total) < 1e-6


def test_make_weights_all_missing_equal():
    mae = {"a": {}, "b": {}}
    w = meteo.make_weights(mae, "temperature_2m")
    assert abs(w["a"] - 0.5) < 1e-6
    assert abs(w["b"] - 0.5) < 1e-6


def test_weighted_consensus_basic():
    assert abs(meteo.weighted_consensus([0.0, 10.0], [0.25, 0.75]) - 7.5) < 1e-6


def test_weighted_consensus_skips_none_and_renormalizes():
    # weights 0.25/0.75, second value None → uses only first, normalized to 1.0
    assert meteo.weighted_consensus([5.0, None], [0.25, 0.75]) == 5.0


def test_weighted_consensus_all_none():
    assert meteo.weighted_consensus([None, None], [0.5, 0.5]) is None


def test_weighted_consensus_zero_weight_total():
    assert meteo.weighted_consensus([1.0, 2.0], [0.0, 0.0]) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_weights.py -v`
Expected: FAIL — `AttributeError: module 'meteo' has no attribute 'make_weights'`

- [ ] **Step 3: Write the implementation**

Append to `meteo.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_weights.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add meteo.py tests/test_weights.py
git commit -m "feat: add accuracy weights and weighted consensus"
```

---

### Task 6: Verification (MAE per model)

**Files:**
- Modify: `meteo.py`
- Test: `tests/test_verification.py`

**Interfaces:**
- Consumes: `fetch_historical_model`, `fetch_archive` (Task 2) — injected for tests; `normalize_model_response` (Task 3).
- Produces:
  - `date_window(days: int) -> tuple[str, str]` — `(start_date, end_date)` ISO strings covering the last `days` calendar days ending yesterday.
  - `compute_mae(predicted: list[float|None], actual: list[float|None]) -> float|None`
  - `verify_models(model_codes: list[str], variables: list[str], start_date: str, end_date: str, fetch_hist=None, fetch_arch=None) -> dict[str, dict[str, float|None]]`

- [ ] **Step 1: Write the failing test**

`tests/test_verification.py`:
```python
from datetime import date, timedelta

import meteo


def test_compute_mae_basic():
    # MAE of |1-0|,|3-1|,|2-4| = 5/3 (the literal 3.0 here is MSE, wrong)
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_verification.py -v`
Expected: FAIL — `AttributeError: module 'meteo' has no attribute 'date_window'`

- [ ] **Step 3: Write the implementation**

Append to `meteo.py`:
```python
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
    actual_data = normalize_model_response(
        fetch_arch(start_date, end_date, variables), variables
    )["data"]
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_verification.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add meteo.py tests/test_verification.py
git commit -m "feat: add MAE verification against ERA5 archive"
```

---

### Task 7: Consensus assembly

**Files:**
- Modify: `meteo.py`
- Test: `tests/test_consensus.py`

**Interfaces:**
- Consumes: `mean`, `median`, `circular_mean`, `weather_code_consensus` (Task 4); `weighted_consensus` (Task 5).
- Produces:
  - `assemble_consensus(hourly_by_model: dict[str, dict], variables: list[str], weights_by_var: dict[str, dict[str, float]], min_sources: int = 3) -> dict`
  - Input `hourly_by_model`: `{code: {"time": list[str], "data": {var: list[float|None]}}}`
  - Output (columnar): `{"time": list[str], "weighted": {var: list}, "mean": {var: list}, "median": {var: list}, "models": {code: {var: list}}}`

- [ ] **Step 1: Write the failing test**

`tests/test_consensus.py`:
```python
import meteo


def _series(a, b, c, var="temperature_2m"):
    data = {}
    for code, vals in (("a", a), ("b", b), ("c", c)):
        data[code] = {"time": ["h0", "h1"], "data": {var: vals}}
    return data


def test_assemble_weighted_and_mean():
    hb = _series([0.0, 10.0], [10.0, 0.0], [5.0, 5.0])
    weights = {"temperature_2m": {"a": 0.5, "b": 0.5, "c": 0.0}}
    out = meteo.assemble_consensus(
        hb, ["temperature_2m"], weights, min_sources=2
    )
    assert out["time"] == ["h0", "h1"]
    assert abs(out["weighted"]["temperature_2m"][0] - 5.0) < 1e-6
    assert abs(out["mean"]["temperature_2m"][0] - 5.0) < 1e-6
    assert abs(out["median"]["temperature_2m"][0] - 5.0) < 1e-6
    assert out["models"]["a"]["temperature_2m"] == [0.0, 10.0]


def test_assemble_min_sources_threshold():
    hb = _series([1.0], [None], [None], var="temperature_2m")
    out = meteo.assemble_consensus(
        hb, ["temperature_2m"], {"temperature_2m": {}}, min_sources=3
    )
    assert out["weighted"]["temperature_2m"][0] is None
    assert out["mean"]["temperature_2m"][0] is None


def test_assemble_wind_direction_uses_circular_median():
    hb = {
        "a": {"time": ["h0"], "data": {"wind_direction_10m": [350.0]}},
        "b": {"time": ["h0"], "data": {"wind_direction_10m": [10.0]}},
        "c": {"time": ["h0"], "data": {"wind_direction_10m": [0.0]}},
    }
    out = meteo.assemble_consensus(
        hb, ["wind_direction_10m"],
        {"wind_direction_10m": {}}, min_sources=2
    )
    m = out["median"]["wind_direction_10m"][0]
    assert m is not None and (abs(m - 0.0) < 1e-6 or abs(m - 360.0) < 1e-6)


def test_assemble_weather_code_by_majority():
    hb = _series([61, 0], [61, 0], [80, 0], var="weather_code")
    out = meteo.assemble_consensus(
        hb, ["weather_code"], {"weather_code": {}}, min_sources=2
    )
    assert out["weighted"]["weather_code"][0] == 61
    assert out["weighted"]["weather_code"][1] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_consensus.py -v`
Expected: FAIL — `AttributeError: module 'meteo' has no attribute 'assemble_consensus'`

- [ ] **Step 3: Write the implementation**

Append to `meteo.py`:
```python
def assemble_consensus(hourly_by_model, variables, weights_by_var, min_sources=3):
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_consensus.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add meteo.py tests/test_consensus.py
git commit -m "feat: assemble per-hour weighted and simple consensus"
```

---

### Task 8: Payload builder, template.html, and renderer

**Files:**
- Create: `template.html`
- Modify: `meteo.py`
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: `assemble_consensus` (Task 7), `HOURLY_VARIABLES`, `DAILY_VARIABLES`, `LAT`, `LON` (Task 1), `mean` (Task 4).
- Produces:
  - `build_payload(model_codes: list[str], model_names: dict[str, str], hourly_by_model: dict, daily_by_model: dict[str, dict], consensus: dict, verification: dict, generated_at: str) -> dict`
  - `render(template: str, payload: dict) -> str`
  - `write_index(html: str, path: str = "index.html") -> None`
  - `main()` — full pipeline (fetch all models, normalize, verify, build weights, assemble consensus, build payload, read `template.html`, render, write `index.html`).

- [ ] **Step 1: Write the failing test**

`tests/test_render.py`:
```python
import meteo


def _payload():
    hourly = {
        "a": {"time": ["h0"], "data": {"temperature_2m": [1.0]}},
        "b": {"time": ["h0"], "data": {"temperature_2m": [3.0]}},
    }
    consensus = meteo.assemble_consensus(
        hourly, ["temperature_2m"],
        {"temperature_2m": {"a": 0.5, "b": 0.5}}, min_sources=2
    )
    daily = {
        "a": {"time": ["d0"], "temperature_2m_max": [5.0]},
        "b": {"time": ["d0"], "temperature_2m_max": [7.0]},
    }
    verification = {
        "7d": {"a": {"temperature_2m": 1.0}, "b": {"temperature_2m": 2.0}},
        "30d": {},
    }
    return meteo.build_payload(
        ["a", "b"], {"a": "Model A", "b": "Model B"},
        hourly, daily, consensus, verification, "2026-08-03T12:00:00+03:00",
    )


def test_payload_contains_key_sections():
    p = _payload()
    assert p["location"]["name"] == "Ярославль"
    assert p["generated_at"].startswith("2026-08-03")
    assert p["model_names"]["a"] == "Model A"
    assert p["time"] == ["h0"]
    assert p["weighted"]["temperature_2m"] == [2.0]
    assert p["mean"]["temperature_2m"] == [2.0]
    assert p["median"]["temperature_2m"] == [2.0]
    assert p["models"]["a"]["temperature_2m"] == [1.0]
    assert p["daily"]["temperature_2m_max"] == [6.0]
    assert p["verification"]["7d"]["a"]["temperature_2m"] == 1.0


def test_render_replaces_placeholders_and_keeps_attribution():
    template = (
        "<title>__CITY__</title><span id='generated'>__GENERATED_AT__</span>"
        "<script id='data' type='application/json'>__DATA__</script>"
    )
    html = meteo.render(template, _payload())
    assert "Ярославль" in html
    assert "2026-08-03T12:00:00+03:00" in html
    assert '"temperature_2m"' in html
    assert "</script>" not in html.replace(
        "<script id='data' type='application/json'>", ""
    ).split("</script>")[0]


def test_render_attribution_link(tmp_path):
    template = (
        "<script id='data' type='application/json'>__DATA__</script>"
        "__ATTRIBUTION__"
    )
    # render() adds attribution; verify it appears
    html = meteo.render(template, _payload())
    assert "open-meteo.com" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_render.py -v`
Expected: FAIL — `AttributeError: module 'meteo' has no attribute 'build_payload'`

- [ ] **Step 3: Implement `build_payload`, `render`, `write_index`, `main`**

Append to `meteo.py`:
```python
import json
import os
from datetime import datetime


def build_payload(model_codes, model_names, hourly_by_model, daily_by_model,
                  consensus, verification, generated_at):
    dvars = list(DAILY_VARIABLES)
    daily_consensus = {}
    for v in dvars:
        cols = [m[v] for m in daily_by_model.values() if m.get(v)]
        if not cols:
            continue
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
        "model_codes": model_codes,
        "model_names": model_names,
        "variables": list(HOURLY_VARIABLES),
        "daily_variables": dvars,
        "time": consensus["time"],
        "weighted": consensus["weighted"],
        "mean": consensus["mean"],
        "median": consensus["median"],
        "models": {
            code: hourly_by_model[code]["data"]
            for code in model_codes if code in hourly_by_model
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
    return html


def write_index(html, path="index.html"):
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    generated_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z")
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
```

- [ ] **Step 4: Create `template.html`**

Full file content (Chart.js from CDN, dark theme, 3 tabs, embedded JSON):

```html
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MeteoMap — Ярославль</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
:root{--bg:#0f1320;--card:#1a2035;--line:#2a3350;--text:#e8ecf5;--muted:#8a93a8;--accent:#ffd54a;--mean:#64b5f6;--sel:#232c48}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;padding:16px}
.wrap{max-width:1200px;margin:0 auto}
header{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;margin-bottom:16px}
h1{font-size:22px}
header .meta{color:var(--muted);font-size:13px}
.tabs{display:flex;gap:8px;margin-bottom:16px}
.tabs button{background:var(--card);color:var(--muted);border:1px solid var(--line);padding:8px 16px;border-radius:8px;cursor:pointer;font-size:14px}
.tabs button.active{color:var(--bg);background:var(--accent);border-color:var(--accent)}
.panel{display:none}
.panel.active{display:block}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin-bottom:16px}
.conds{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px}
.cond{text-align:center}
.cond .val{font-size:26px;font-weight:600}
.cond .lab{font-size:12px;color:var(--muted)}
.varsel{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px}
.varsel button{background:var(--sel);color:var(--text);border:1px solid var(--line);padding:6px 12px;border-radius:6px;cursor:pointer;font-size:13px}
.varsel button.active{background:var(--accent);color:var(--bg);border-color:var(--accent)}
.legend{display:flex;flex-wrap:wrap;gap:8px;font-size:12px;color:var(--muted);margin-top:10px}
.legend label{display:flex;align-items:center;gap:5px;cursor:pointer}
.legend .dot{width:10px;height:10px;border-radius:50%;display:inline-block}
.tblwrap{overflow-x:auto}
table{border-collapse:collapse;font-size:12px;width:100%}
th,td{padding:4px 8px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
th:first-child,td:first-child{text-align:left;position:sticky;left:0;background:var(--bg)}
th{color:var(--muted);font-weight:500}
td.plus{color:#ff8a80}
td.minus{color:#80d8ff}
.attrib{margin-top:20px;color:var(--muted);font-size:12px;text-align:center}
a{color:var(--accent)}
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>🌤 MeteoMap — <span id="city">__CITY__</span></h1>
  <span class="meta">Обновлено: <span id="generated">__GENERATED_AT__</span> (раз в час)</span>
</header>
<div class="tabs">
  <button class="active" data-tab="forecast">Прогноз</button>
  <button data-tab="compare">Сравнение</button>
  <button data-tab="accuracy">Точность</button>
</div>
<div id="tab-forecast" class="panel active">
  <div class="card"><div class="conds" id="conditions"></div></div>
  <div class="card">
    <div class="varsel" id="varsel"></div>
    <canvas id="mainChart" height="120"></canvas>
    <div class="legend" id="legend"></div>
  </div>
</div>
<div id="tab-compare" class="panel">
  <div class="card">
    <div class="varsel" id="varsel2"></div>
    <div class="tblwrap"><table id="cmpTable"></table></div>
  </div>
</div>
<div id="tab-accuracy" class="panel">
  <div class="card"><canvas id="maeChart" height="90"></canvas></div>
  <div class="card"><div class="tblwrap"><table id="mae7"></table></div></div>
  <div class="card"><div class="tblwrap"><table id="mae30"></table></div></div>
</div>
<div class="attrib">Погодные модели: ECMWF, NOAA, DWD, Météo-France, UK Met Office, Environment Canada, JMA, KMA, BOM, CMA, Google.
  <a href="https://open-meteo.com/">Weather data by Open-Meteo.com</a> (CC BY 4.0)</div>
</div>
<script id="data" type="application/json">__DATA__</script>
<script>
const D=JSON.parse(document.getElementById('data').textContent);
const codes=D.model_codes, names=D.model_names;
const VAR_NAMES={
 temperature_2m:'Температура (°C)',apparent_temperature:'Ощущается (°C)',dew_point_2m:'Точка росы (°C)',
 relative_humidity_2m:'Влажность (%)',precipitation:'Осадки (мм)',precipitation_probability:'Вероятность осадков (%)',
 snowfall:'Снег (см)',weather_code:'Погода (WMO)',pressure_msl:'Давление (гПа)',cloud_cover:'Облачность (%)',
 wind_speed_10m:'Ветер (м/с)',wind_direction_10m:'Направление ветра (°)',wind_gusts_10m:'Порывы (м/с)',
 visibility:'Видимость (м)',shortwave_radiation:'Радиация (Вт/м²)'};
const CHART_VARS=['temperature_2m','wind_speed_10m','precipitation','relative_humidity_2m','pressure_msl','cloud_cover'];
const PALETTE=['#7fb3d5','#9d8cf5','#f5a25c','#8fd58f','#e06c6c','#5cc7d5','#c5b45c','#d58fd5','#6c8ae0','#a5d57a','#e08ac0','#7ad5b5','#d5a05c'];
const modelColor=i=>PALETTE[i%PALETTE.length];
const fmt=v=>v===null||v===undefined?'—':(Math.round(v*10)/10);
const fmtTime=t=>t.slice(5,10).replace('-','.')+' '+t.slice(11,16);

// tabs
document.querySelectorAll('.tabs button').forEach(b=>b.addEventListener('click',()=>{
  document.querySelectorAll('.tabs button').forEach(x=>x.classList.remove('active'));
  b.classList.add('active');
  ['forecast','compare','accuracy'].forEach(t=>document.getElementById('tab-'+t).classList.toggle('active',b.dataset.tab===t));
}));

// variable selector
function buildVarSel(id,onSel){
  const el=document.getElementById(id);
  CHART_VARS.forEach(v=>{
    const b=document.createElement('button');
    b.textContent=VAR_NAMES[v];b.dataset.v=v;
    b.addEventListener('click',()=>{el.querySelectorAll('button').forEach(x=>x.classList.remove('active'));b.classList.add('active');onSel(v);});
    el.appendChild(b);
  });
  el.querySelector('button').classList.add('active');
}

// conditions
const nowLocal=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Moscow',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).format(new Date());
const curHour=nowLocal.replace(', ','T').slice(0,13)+':00';
let curIdx=D.time.findIndex(t=>t>=curHour);
if(curIdx<0)curIdx=0;
function buildConditions(){
  const w=D.weighted;
  const list=[
    ['Температура',fmt(w.temperature_2m?.[curIdx])+'°'],
    ['Ощущается',fmt(w.apparent_temperature?.[curIdx])+'°'],
    ['Ветер',fmt(w.wind_speed_10m?.[curIdx])+' м/с'],
    ['Порывы',fmt(w.wind_gusts_10m?.[curIdx])+' м/с'],
    ['Осадки',fmt(w.precipitation?.[curIdx])+' мм'],
    ['Вероятность',fmt(w.precipitation_probability?.[curIdx])+'%'],
    ['Давление',fmt(w.pressure_msl?.[curIdx])+' гПа'],
    ['Облачность',fmt(w.cloud_cover?.[curIdx])+'%']];
  const mx=D.daily.temperature_2m_max?.[0], mn=D.daily.temperature_2m_min?.[0], pr=D.daily.precipitation_sum?.[0];
  if(mx!==undefined&&mx!==null)list.push(['Макс сегодня',fmt(mx)+'°']);
  if(mn!==undefined&&mn!==null)list.push(['Мин сегодня',fmt(mn)+'°']);
  if(pr!==undefined&&pr!==null)list.push(['Осадки за день',fmt(pr)+' мм']);
  document.getElementById('conditions').innerHTML=list.map(([l,v])=>`<div class="cond"><div class="val">${v}</div><div class="lab">${l}</div></div>`).join('');
}

// main chart
let mainChart,curVar='temperature_2m';
function setVar(v){
  curVar=v;
  const d=mainChart.data;
  d.datasets=codes.map((c,i)=>({label:names[c],data:(D.models[c]?D.models[c][v]:[])||[],borderColor:modelColor(i),borderWidth:1,pointRadius:0,tension:0.2,spanGaps:false}));
  d.datasets.push({label:'Консенсус (взвеш.)',data:(D.weighted[v]||[]).map(x=>x),borderColor:'#ffd54a',borderWidth:3,pointRadius:0,tension:0.2});
  d.datasets.push({label:'Среднее',data:(D.mean[v]||[]).map(x=>x),borderColor:'#64b5f6',borderWidth:2,borderDash:[6,4],pointRadius:0,tension:0.2});
  if(v==='precipitation'){
    d.datasets.push({label:'Вероятность осадков (%)',data:(D.weighted.precipitation_probability||[]).map(x=>x),borderColor:'#4dd0e1',borderWidth:2,borderDash:[2,2],pointRadius:0,yAxisID:'y1'});
  }else{
    d.datasets=d.datasets.filter(ds=>ds.label!=='Вероятность осадков (%)');
  }
  mainChart.options.scales.y.title.text=VAR_NAMES[v];
  mainChart.options.scales.y.title.display=true;
  mainChart.update();
  updateLegend();
}
function makeMainChart(){
  const ctx=document.getElementById('mainChart').getContext('2d');
  mainChart=new Chart(ctx,{type:'line',data:{labels:D.time.map(fmtTime),datasets:[]},options:{
    responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},
    scales:{
      x:{ticks:{color:'#8a93a8',maxTicksLimit:14},grid:{color:'#232c48'}},
      y:{ticks:{color:'#8a93a8'},grid:{color:'#232c48'},title:{display:false,text:''}},
      y1:{position:'right',min:0,max:100,ticks:{color:'#4dd0e1',callback:v=>v+'%'},grid:{display:false}}
    },
    plugins:{legend:{display:false},tooltip:{mode:'index',intersect:false}}
  }});
  setVar(CHART_VARS[0]);
}
function updateLegend(){
  const el=document.getElementById('legend');
  el.innerHTML='';
  codes.forEach((c,i)=>{
    const ds=mainChart.data.datasets[i];
    if(!ds)return;
    const lab=document.createElement('label');
    const cb=document.createElement('input');cb.type='checkbox';cb.checked=!ds.hidden;
    cb.addEventListener('change',()=>{ds.hidden=!cb.checked;mainChart.update();});
    lab.appendChild(cb);
    lab.innerHTML+='<span class="dot" style="background:'+modelColor(i)+'"></span>'+names[c];
    el.appendChild(lab);
  });
}

// comparison table
let cmpVar='temperature_2m';
function buildCmpTable(){
  const el=document.getElementById('cmpTable');
  const cols=[{t:'Время'}].concat(codes.map(c=>({t:names[c]}))).concat([{t:'Взвеш.'},{t:'Среднее'}]);
  const head='<tr>'+cols.map(c=>`<th>${c.t}</th>`).join('')+'</tr>';
  const rows=D.time.map((t,i)=>{
    let cells=`<td>${fmtTime(t)}</td>`;
    const w=D.weighted[cmpVar]?.[i];
    codes.forEach((c)=>{
      const v=D.models[c]?D.models[c][cmpVar]?.[i];
      let cls='';
      if(typeof v==='number'&&typeof w==='number')cls=(v>w?'plus':'minus');
      cells+=`<td class="${cls}">${fmt(v)}</td>`;
    });
    cells+=`<td><b>${fmt(w)}</b></td>`;
    cells+=`<td>${fmt(D.mean[cmpVar]?.[i])}</td>`;
    return `<tr>${cells}</tr>`;
  }).join('');
  el.innerHTML=head+rows;
}

// accuracy
function meanOf(o,keys){const a=keys.map(k=>o[k]).filter(x=>typeof x==='number');return a.length?a.reduce((s,x)=>s+x,0)/a.length:null;}
function buildMaeTables(){
  const vnames=['temperature_2m','precipitation','wind_speed_10m'];
  ['7d','30d'].forEach(days=>{
    const ver=D.verification[days]||{};
    const el=document.getElementById(days==='7d'?'mae7':'mae30');
    const head='<tr><th>Модель</th>'+vnames.map(v=>`<th>${VAR_NAMES[v]}</th>`).join('')+'<th>Средн.</th></tr>';
    const rows=codes.filter(c=>ver[c]).map(c=>{
      const cells=vnames.map(v=>{const m=ver[c][v];return `<td>${m===null||m===undefined?'—':m.toFixed(2)}</td>`;});
      const a=meanOf(ver[c],vnames);
      return `<tr><td>${names[c]}</td>${cells.join('')}<td>${a===null?'—':a.toFixed(2)}</td></tr>`;
    }).join('');
    el.innerHTML=head+rows;
  });
  const ver=D.verification['7d']||{};
  const vnames2=['temperature_2m','precipitation','wind_speed_10m'];
  const items=codes.filter(c=>ver[c]).map(c=>({c,avg:meanOf(ver[c],vnames2)}));
  items.sort((a,b)=>b.avg-a.avg);
  new Chart(document.getElementById('maeChart').getContext('2d'),{type:'bar',
    data:{labels:items.map(x=>names[x.c]),datasets:[{label:'Средний MAE за 7 дней',data:items.map(x=>x.avg),backgroundColor:PALETTE.slice(0,items.length)}]},
    options:{plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>'MAE: '+(c.parsed.y===null?'—':c.parsed.y.toFixed(2))}}},
      scales:{x:{ticks:{color:'#8a93a8'}},y:{ticks:{color:'#8a93a8'},grid:{color:'#232c48'}}}}});
}

buildConditions();
buildVarSel('varsel',setVar);
buildVarSel('varsel2',v=>{cmpVar=v;buildCmpTable();});
makeMainChart();
buildCmpTable();
buildMaeTables();
</script>
</body>
</html>
```

- [ ] **Step 5: Run render tests**

Run: `python -m pytest tests/test_render.py -v`
Expected: PASS (3 tests)

Note: `test_render_attribution_link` passes only because `render()` substitutes the `__ATTRIBUTION__` placeholder with the Open-Meteo attribution link. The test template does NOT itself contain `open-meteo.com` (this note was previously wrong). The real `template.html` hardcodes its attribution and does not use the placeholder — the substitution is a no-op there; verify against `template.html` in Step 6.

- [ ] **Step 6: Run the full unit suite**

Run: `python -m pytest tests/ -m "not integration" -q`
Expected: PASS (all tests)

- [ ] **Step 7: Local end-to-end smoke run**

Run: `python meteo.py`
Expected: prints `[ok] index.html written; models=N hours=168` (N may be < 13 if some codes are invalid — Task 10 fixes codes). Then open `index.html` locally and verify the three tabs render.

- [ ] **Step 8: Commit**

```bash
git add meteo.py template.html tests/test_render.py
git commit -m "feat: build payload and render static index.html"
```

---

### Task 9: GitHub Actions workflow and README

**Files:**
- Create: `.github/workflows/deploy.yml`
- Create: `README.md`

**Interfaces:**
- Consumes: `meteo.py` producing `index.html` (Task 8).
- Produces: hourly CI deployment to `gh-pages`.

- [ ] **Step 1: Create `.github/workflows/deploy.yml`**

```yaml
name: Deploy MeteoMap to Pages

on:
  schedule:
    - cron: '0 * * * *'
  workflow_dispatch:
  push:
    branches: [main]

permissions:
  contents: write

jobs:
  build-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5

      - uses: actions/setup-python@v5
        with:
          python-version: '3.13'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run unit tests
        run: python -m pytest tests/ -m "not integration" -q

      - name: Generate site
        run: python meteo.py

      - name: Deploy to gh-pages
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          rm -rf /tmp/ghpages
          mkdir /tmp/ghpages
          cp index.html /tmp/ghpages/
          echo "" > /tmp/ghpages/.nojekyll
          cd /tmp/ghpages
          git init
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git remote add origin "https://x-access-token:${GITHUB_TOKEN}@github.com/${{ github.repository }}.git"
          git add -A
          git commit -m "deploy: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
          git push -f origin HEAD:gh-pages
```

- [ ] **Step 2: Create `README.md`**

```markdown
# MeteoMap

Сравнение погодных моделей и усреднённый прогноз для Ярославля.

- Источник: [Open-Meteo](https://open-meteo.com/) (CC BY 4.0)
- Обновление: раз в час (GitHub Actions, запуск через cron-job.org)
- Модели: ECMWF IFS/AIFS, NOAA GFS, DWD ICON, GEM, UKMO, ARPEGE, JMA GSM, KMA GDPS, ACCESS-G, GRAPES, GEFS, WeatherNext
- Консенсус: взвешенный по MAE (7/30 дней) + простое среднее/медиана

## Локальный запуск

```bash
pip install -r requirements.txt
python meteo.py
# открыть index.html
```

## Тесты

```bash
python -m pytest tests/ -m "not integration" -q   # юнит
python -m pytest tests/ -m integration -q          # интеграционные (реальный API)
```
```

- [ ] **Step 3: Verify workflow syntax locally**

Run: `python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/deploy.yml')); print('yaml ok')"`
Expected: `yaml ok`. If PyYAML is not installed, install it (`pip install pyyaml`) or verify by reading the file (the workflow is copied verbatim from the working MopedMap pattern).

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/deploy.yml README.md
git commit -m "feat: add hourly deploy workflow and README"
```

---

### Task 10: Integration tests and model-code verification

**Files:**
- Create: `tests/test_integration.py`
- Modify: `meteo.py` (`FORECAST_MODELS` codes fixed as needed)

**Interfaces:**
- Consumes: `fetch_model`, `fetch_historical_model`, `fetch_archive`, `verify_models`, `date_window` (Tasks 2, 6).
- Produces: verified `FORECAST_MODELS` codes that all return data for Yaroslavl.

- [ ] **Step 1: Write the integration test**

`tests/test_integration.py`:
```python
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
```

- [ ] **Step 2: Run integration tests locally**

Run: `python -m pytest tests/test_integration.py -v`
Expected: `test_verification_runs_for_last_7_days` PASS. `test_all_forecast_models_return_data_for_yaroslavl` may FAIL — `broken` prints the models whose codes are wrong. This is expected on first run.

- [ ] **Step 3: Fix model codes against real API**

For every code in the printed `broken` list, look up the correct Open-Meteo model code:
- Forecast API models: https://open-meteo.com/en/docs — the `models=` parameter values are shown in the URL builder when selecting each model in the "Weather models" dropdown.
- Ensemble API models (GEFS, WeatherNext): https://open-meteo.com/en/docs/ensemble-api

Update the `FORECAST_MODELS` tuples in `meteo.py` with the correct codes/display names. Remove from the list any model that Open-Meteo does not serve for Russia at all (e.g. regional models that genuinely do not exist globally), keeping at least 8 models.

- [ ] **Step 4: Re-run integration tests**

Run: `python -m pytest tests/test_integration.py -v`
Expected: PASS (2 tests) — `broken` list empty.

- [ ] **Step 5: Re-run full unit suite**

Run: `python -m pytest tests/ -m "not integration" -q`
Expected: PASS.

- [ ] **Step 6: Regenerate site and commit**

Run: `python meteo.py`
Expected: `[ok] index.html written; models=N hours=168` with all N models working. Then commit:
```bash
git add meteo.py tests/test_integration.py
git commit -m "fix: pin verified Open-Meteo model codes"
```

---

### Task 11: Deployment setup on GitHub

**Files:** none (GitHub settings + external cron)

**Interfaces:**
- Consumes: `gh-pages` branch produced by Task 9's workflow.

- [ ] **Step 1: Create GitHub repo and push**

Create a new GitHub repository named `MeteoMap` under the user's account, then:
```bash
git remote add origin https://github.com/<user>/MeteoMap.git
git branch -M main
git push -u origin main
```

- [ ] **Step 2: Enable GitHub Pages**

Repo → Settings → Pages → Source: "Deploy from a branch" → branch `gh-pages` → root `/`. (Same setting as the MopedMap project.)

- [ ] **Step 3: Verify first deployment**

Run the workflow manually: Repo → Actions → "Deploy MeteoMap to Pages" → Run workflow. Confirm the job succeeds and the site is live at `https://<user>.github.io/MeteoMap/`.

- [ ] **Step 4: Configure cron-job.org**

On https://cron-job.org create a cron job that runs every hour and POSTs:
```
POST https://api.github.com/repos/<user>/MeteoMap/actions/workflows/deploy.yml/dispatches
Content-Type: application/json
Authorization: Bearer <PAT with repo or actions:write scope>
{"ref": "main"}
```
Replace `<user>` and `<PAT>` with the user's values (same setup as the MopedMap project).

- [ ] **Step 5: Verify hourly schedule works**

Wait for the next cron-jobs.org trigger (or trigger it manually once) and confirm a new run appears in Actions and `gh-pages` updates. Confirm the site header shows a fresh "Обновлено" timestamp.

---

## Self-Review Notes

- **Spec coverage:** Sections 3 (models/variables/endpoints) → Tasks 1-3, 10; 5 (normalization) → Task 3; 6 (verification) → Task 6; 7 (consensus) → Tasks 4-5, 7; 8 (UI) → Task 8; 9 (errors) → Tasks 2-3, 6, 8 (`main` warns and skips); 10 (tests) → Tasks 2-8, 10; 4.2 (deploy) → Tasks 9, 11. Section 7's spec diagram `hours:[{...}]` is implemented columnar (smaller JSON); same data, documented in Task 8.
- **Type consistency:** `FORECAST_MODELS` is `(code, display_name, endpoint)` everywhere. `consensus` output keys (`time`, `weighted`, `mean`, `median`, `models`) are consumed identically in `build_payload` and `template.html`.
- **Caveat:** `make_weights` uses the 7-day MAE in `main()`; 30-day MAE is shown in the accuracy tab only. This matches the spec (weights from verification; both windows displayed).
