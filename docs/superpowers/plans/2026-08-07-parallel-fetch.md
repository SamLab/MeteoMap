# Параллелизация сетевых запросов в meteo.py — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Сократить шаг `Generate site` в GitHub Actions с ~6 мин до ~1.5-2 мин, распараллелив сетевые загрузки в `meteo.py`.

**Architecture:** Три независимых блока сетевой загрузки (forecast 13 моделей, верификация hist/archive, внешние провайдеры YR/OWM/WeatherAPI) переводятся на `ThreadPoolExecutor(max_workers=5)`. Загрузочные циклы выносятся в отдельные функции (`fetch_all_forecasts`, `fetch_external_providers`), тело цикла по городам — в `build_city_payload`, чтобы каждую можно было протестировать с моками без сети. Логика консенсуса и записи не меняется.

**Tech Stack:** Python 3.13, stdlib `concurrent.futures`, `requests` (как сейчас), pytest.

## Global Constraints

- Не добавлять новых зависимостей (только stdlib `concurrent.futures`).
- `max_workers=5` везде (компромисс скорость / rate-limit 429).
- Ретраи и таймауты `request_with_retry` не трогать.
- Кэши `_hist_cache`/`_arch_cache` и их ключи не менять.
- Порядок результатов (order по кодам/городам) сохранять детерминированным.
- `verify_models` должен продолжать принимать callable-моки (`fetch_hist`, `fetch_arch`) из существующих тестов.
- Маркер `integration` не запускать в CI: `pytest tests/ -m "not integration"`.

---

### Task 1: `fetch_all_forecasts` — параллельные батч-запросы по моделям

**Files:**
- Modify: `meteo.py` (добавить функцию после `request_with_retry`, перед `fetch_model`)
- Test: `tests/test_fetch.py` (новый файл)

**Interfaces:**
- Consumes: `fetch_model(code, endpoint, variables, days, timezone)` — существует.
- Produces: `fetch_all_forecasts(models, variables, days, timezone, max_workers=5) -> dict[str, list]` — отображает каждый `code` в список ответов по городам (как `fetch_model`). При исключении модели — `[warn]` и код пропускается (кода нет в результате).

- [ ] **Step 1: Написать падающие тесты**

Создать `tests/test_fetch.py`:

```python
import meteo


def test_fetch_all_forecasts_returns_all_models(monkeypatch):
    calls = []

    def fake_fetch_model(code, endpoint, variables, days=None, timezone=None):
        calls.append((code, endpoint))
        return [{"model": code}]

    monkeypatch.setattr(meteo, "fetch_model", fake_fetch_model)
    models = [("a", "A", "forecast"), ("b", "B", "ensemble")]
    res = meteo.fetch_all_forecasts(models, ["temperature_2m"], 2, "UTC", max_workers=2)
    assert set(res) == {"a", "b"}
    assert res["a"] == [{"model": "a"}]
    assert res["b"] == [{"model": "b"}]
    assert set(calls) == {("a", "forecast"), ("b", "ensemble")}


def test_fetch_all_forecasts_skips_failures(monkeypatch):
    def fake_fetch_model(code, endpoint, variables, days=None, timezone=None):
        if code == "bad":
            raise RuntimeError("boom")
        return [{"model": code}]

    monkeypatch.setattr(meteo, "fetch_model", fake_fetch_model)
    models = [("good", "G", "forecast"), ("bad", "B", "forecast")]
    res = meteo.fetch_all_forecasts(models, ["t"], 2, "UTC", max_workers=2)
    assert "good" in res
    assert "bad" not in res
```

- [ ] **Step 2: Запустить тест, убедиться что падает**

Run: `F:\Meteo\.venv\Scripts\python.exe -m pytest tests/test_fetch.py -q`
Expected: FAIL — `AttributeError: module 'meteo' has no attribute 'fetch_all_forecasts'`

- [ ] **Step 3: Реализовать `fetch_all_forecasts`**

В `meteo.py`, сразу после `request_with_retry` (после строки 157):

```python
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
```

- [ ] **Step 4: Запустить тест, убедиться что проходит**

Run: `F:\Meteo\.venv\Scripts\python.exe -m pytest tests/test_fetch.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Прогнать всю тестовую базу**

Run: `F:\Meteo\.venv\Scripts\python.exe -m pytest tests/ -m "not integration" -q`
Expected: PASS (все существующие тесты зелёные)

- [ ] **Step 6: Commit**

```bash
git add meteo.py tests/test_fetch.py
git commit -m "feat: parallel forecast fetches via fetch_all_forecasts"
```

---

### Task 2: Параллельная верификация в `verify_models`

**Files:**
- Modify: `meteo.py` (`verify_models`, строки ~548-571)
- Test: `tests/test_verification.py` (дополнить)

**Interfaces:**
- Consumes: `fetch_hist(code, start, end, variables)`, `fetch_arch(start, end, variables)` — callables (моки в тестах).
- Produces: `verify_models(model_codes, variables, start_date, end_date, fetch_hist=None, fetch_arch=None) -> dict[code, dict[var, mae]]` — поведение идентично текущему: `fetch_arch` один раз до циклов; на каждую модель `fetch_hist` параллельно; исключение модели → `[warn] verify {code}: {exc}` и код пропускается. Порядок ключей в `result` — как в `model_codes`.

- [ ] **Step 1: Написать падающий тест на толерантность к параллельным исключениям**

Дополнить `tests/test_verification.py`:

```python
def test_verify_models_parallel_skips_failing_models():
    variables = ["temperature_2m"]
    calls = []

    def _hist(code, start_date, end_date, variables):
        calls.append(code)
        if code == "broken":
            raise RuntimeError("model unavailable")
        return {
            "hourly": {
                "time": ["2026-07-01T00:00"],
                "temperature_2m": [1.0],
            }
        }

    def _arch(start_date, end_date, variables):
        return {"hourly": {"time": ["2026-07-01T00:00"], "temperature_2m": [0.0]}}

    result = meteo.verify_models(
        ["a", "broken", "c"], variables, "2026-07-01", "2026-07-02",
        fetch_hist=_hist, fetch_arch=_arch,
    )
    assert set(result) == {"a", "c"}
    assert "broken" not in result
    assert set(calls) == {"a", "broken", "c"}
```

- [ ] **Step 2: Запустить тест**

Run: `F:\Meteo\.venv\Scripts\python.exe -m pytest tests/test_verification.py::test_verify_models_parallel_skips_failing_models -q`
Expected: PASS — это регрессионный тест: он зелёный и до, и после правки. Его ценность — подтвердить, что параллельная реализация сохраняет то же поведение (все модели вызываются, сломанная пропускается, остальные в результате).

- [ ] **Step 3: Реализовать параллельную верификацию**

Заменить цикл `for code in model_codes:` внутри `verify_models` на:

```python
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
```

(`ThreadPoolExecutor` уже импортирован в Task 1.)

- [ ] **Step 4: Запустить тесты верификации**

Run: `F:\Meteo\.venv\Scripts\python.exe -m pytest tests/test_verification.py -q`
Expected: PASS (3 старых + 1 новый)

- [ ] **Step 5: Прогнать всю тестовую базу**

Run: `F:\Meteo\.venv\Scripts\python.exe -m pytest tests/ -m "not integration" -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add meteo.py tests/test_verification.py
git commit -m "perf: parallel model verification in verify_models"
```

---

### Task 3: `fetch_external_providers` — параллельная загрузка YR/OWM/WeatherAPI

**Files:**
- Modify: `meteo.py` (добавить функцию после `EXTERNAL_MODELS`, перед `import math`)
- Test: `tests/test_fetch.py` (дополнить)

**Interfaces:**
- Consumes: список `providers` из кортежей `(code, name, fetch_fn)`, где `fetch_fn(lat=None, lon=None) -> list[dict]` (сигнатура как `fetch_yr`, `fetch_owm`, `fetch_weatherapi`); `LOCATIONS`.
- Produces: `fetch_external_providers(providers, locations, max_workers=5) -> dict[code, dict[slug, rows]]`. При исключении провайдера — `[warn] {code} {name}: {exc}` и `rows = []`.

- [ ] **Step 1: Написать падающие тесты**

Дополнить `tests/test_fetch.py`:

```python
def test_fetch_external_providers_fills_all_cities(monkeypatch):
    def fake_fetch(lat=None, lon=None):
        return [{"utc": None, "temperature_2m": lat}]

    providers = [("p1", "P1", fake_fetch), ("p2", "P2", fake_fetch)]
    locs = [
        {"name": "Ярославль", "slug": "yaroslavl", "lat": 57.63, "lon": 39.87},
        {"name": "Балакирево", "slug": "balakirevo", "lat": 56.507, "lon": 38.846},
    ]
    res = meteo.fetch_external_providers(providers, locs, max_workers=2)
    assert set(res["p1"]) == {"yaroslavl", "balakirevo"}
    assert res["p1"]["yaroslavl"] == [{"utc": None, "temperature_2m": 57.63}]
    assert res["p2"]["balakirevo"] == [{"utc": None, "temperature_2m": 56.507}]


def test_fetch_external_providers_tolerates_failure():
    def bad_fetch(lat=None, lon=None):
        raise RuntimeError("down")

    providers = [("p", "P", bad_fetch)]
    locs = [
        {"name": "Ярославль", "slug": "yaroslavl", "lat": 57.63, "lon": 39.87},
    ]
    res = meteo.fetch_external_providers(providers, locs, max_workers=2)
    assert res["p"]["yaroslavl"] == []
```

- [ ] **Step 2: Запустить тесты, убедиться что падают**

Run: `F:\Meteo\.venv\Scripts\python.exe -m pytest tests/test_fetch.py -q`
Expected: FAIL — `AttributeError: module 'meteo' has no attribute 'fetch_external_providers'`

- [ ] **Step 3: Реализовать `fetch_external_providers`**

В `meteo.py`, сразу после `EXTERNAL_MODELS` (после строки 403):

```python
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
        futures = [
            ex.submit(_fetch, code, name, fn, loc)
            for code, _name, fn in providers
            for loc in locations
        ]
        for f in futures:
            code, slug, rows = f.result()
            out.setdefault(code, {})[slug] = rows
    return out
```

- [ ] **Step 4: Запустить тесты, убедиться что проходят**

Run: `F:\Meteo\.venv\Scripts\python.exe -m pytest tests/test_fetch.py -q`
Expected: PASS (2 старых + 2 новых)

- [ ] **Step 5: Прогнать всю тестовую базу**

Run: `F:\Meteo\.venv\Scripts\python.exe -m pytest tests/ -m "not integration" -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add meteo.py tests/test_fetch.py
git commit -m "feat: parallel external provider fetches"
```

---

### Task 4: `build_city_payload` + переписать `main()` на новые функции

**Files:**
- Modify: `meteo.py` (`main()`, строки ~741-845; добавить `build_city_payload` перед `main`)
- Test: `tests/test_fetch.py` (дополнить)

**Interfaces:**
- Consumes: `fetch_all_forecasts`, `fetch_external_providers`, `_city_hist`, `_city_arch`, `normalize_model_response`, `verify_models`, `make_weights`, `align_to_grid`, `align_yr_to_grid`, `assemble_consensus`, `build_payload`.
- Produces: `build_city_payload(loc, raw_by_model, external_rows, generated_at, external_enabled) -> dict` (payload для одного города). `external_rows` — как возвращает `fetch_external_providers`, ключи-коды включают `YR_CODE`.

- [ ] **Step 1: Написать падающий тест**

Дополнить `tests/test_fetch.py`:

```python
from datetime import datetime, timezone, timedelta


def test_build_city_payload_with_external(monkeypatch):
    loc = meteo.LOCATIONS[0]
    raw = {
        "ecmwf_ifs025": [{
            "hourly": {"time": ["2026-08-07T00:00"], "temperature_2m": [10.0]},
            "daily": {},
        }],
    }
    utc_dt = datetime(2026, 8, 6, 21, 0, tzinfo=timezone.utc)  # = 2026-08-07T00:00 MSK
    external_rows = {
        meteo.YR_CODE: {loc["slug"]: [{"utc": utc_dt, "temperature_2m": 11.0}]},
        "owm": {loc["slug"]: [{"utc": utc_dt, "temperature_2m": 9.0}]},
    }
    monkeypatch.setattr(
        meteo, "verify_models",
        lambda *a, **k: {
            "ecmwf_ifs025": {v: 1.0 for v in meteo.VERIFICATION_VARIABLES},
        },
    )
    p = meteo.build_city_payload(loc, raw, external_rows, "2026-08-07T00:00:00+03:00", True)
    assert "ecmwf_ifs025" in p["model_codes"]
    assert meteo.YR_CODE in p["model_codes"]
    assert "owm" in p["model_codes"]
    assert p["location"] == loc
```

- [ ] **Step 2: Запустить тест, убедиться что падает**

Run: `F:\Meteo\.venv\Scripts\python.exe -m pytest tests/test_fetch.py::test_build_city_payload_with_external -q`
Expected: FAIL — `AttributeError: module 'meteo' has no attribute 'build_city_payload'`

- [ ] **Step 3: Добавить `build_city_payload`**

В `meteo.py`, сразу перед `def main():`:

```python
def build_city_payload(loc, raw_by_model, external_rows, generated_at, external_enabled):
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
        for code, _name, _fn in EXTERNAL_MODELS:
            verification["7d"][code] = {v: None for v in VERIFICATION_VARIABLES}
            verification["30d"][code] = {v: None for v in VERIFICATION_VARIABLES}
    weights_by_var = {
        v: make_weights(verification["7d"], v)
        for v in VERIFICATION_VARIABLES
    }

    grid = next(iter(hourly_by_model.values()))["time"]
    city_codes = list(model_codes)
    city_names = dict(model_names)
    providers = [(YR_CODE, YR_NAME, fetch_yr)]
    if external_enabled:
        providers = providers + list(EXTERNAL_MODELS)
    for code, name, _fn in providers:
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
```

- [ ] **Step 4: Переписать `main()`**

Заменить тело `main()` (строки 742-845) на:

```python
def main():
    generated_at = moscow_now_iso()
    raw_by_model = fetch_all_forecasts(
        FORECAST_MODELS, HOURLY_VARIABLES,
        days=FORECAST_DAYS, timezone=TIMEZONE,
    )
    if not raw_by_model:
        raise SystemExit("no model data available")

    external_enabled = os.environ.get("ENABLE_EXTERNAL") == "1"
    providers = [(YR_CODE, YR_NAME, fetch_yr)]
    if external_enabled:
        providers = providers + list(EXTERNAL_MODELS)
    external_rows = fetch_external_providers(providers, LOCATIONS)

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
```

- [ ] **Step 5: Запустить тест**

Run: `F:\Meteo\.venv\Scripts\python.exe -m pytest tests/test_fetch.py::test_build_city_payload_with_external -q`
Expected: PASS

- [ ] **Step 6: Прогнать всю тестовую базу**

Run: `F:\Meteo\.venv\Scripts\python.exe -m pytest tests/ -m "not integration" -q`
Expected: PASS

- [ ] **Step 7: Локальный прогон с замером времени (без ключей — провайдеры off)**

Run: `F:\Meteo\.venv\Scripts\python.exe -c "import time, meteo; t=time.time(); meteo.main(); print('elapsed', round(time.time()-t, 1), 's')"`
Expected: `[ok] index.html + 3 city json written`; elapsed заметно меньше, чем раньше (порядок 1-2 мин; точное число зависит от сети).

- [ ] **Step 8: Прогнать `git diff` — убедиться, что `bot.php` не закоммичен**

Run: `git status --short`
Expected: только ожидаемые изменения; `bot.php` отмечен как `M` (не стейджится).

- [ ] **Step 9: Commit**

```bash
git add meteo.py tests/test_fetch.py
git commit -m "refactor: main uses parallel fetches via build_city_payload"
```

- [ ] **Step 10: Push и дождаться деплоя**

Run: `git push origin main`
Затем: `gh run list --limit 5` — дождаться `success`.
Ожидаемый шаг `Generate site` — ~1.5-2 мин.

- [ ] **Step 11: Проверить live**

Run: `F:\Meteo\.venv\Scripts\python.exe C:\Users\SamLab\AppData\Local\Temp\opencode\check_live.py`
Expected: свежий `generated_at`, 3 города в `data/`, 13 моделей, external `['owm', 'weatherapi']`.
