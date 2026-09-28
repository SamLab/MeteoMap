# Датчики как источник «Датчик» в «Часах» — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Собрать MQTT-метеостанции в один источник погоды «Датчик» и показать его столбиком в «Часах» для Ярославля и Цеденево, удалив слой датчиков с карты Радара.

**Architecture:** Коллектор `tools/collect_sensors.py` владеет историей: он усредняет значения по станциям и дописывает их в `sensors_history.json` по часам московского времени, `sensors.yml` коммитит оба файла раз в 15 минут. `meteo.py` на каждой сборке читает историю и для `yaroslavl`/`tsedenevo` подаёт датчики как ещё одну «модель» в `hourly_by_model` — тогда консенсус, фильтрация `None` и `min_sources` работают без отдельной постобработки. Фронтенд прячет столбик для параметров, которых датчики не измеряют.

**Tech Stack:** Python 3.13, stdlib, `paho-mqtt`, pytest; фронтенд — vanilla JS + Chart.js в `template.html`; генерация страниц — Leaflet в `radar_template.html`.

## Global Constraints

- Разрешённые параметры датчиков — **только** `temperature_2m`, `relative_humidity_2m`, `pressure_msl`. Любой другой ключ в конфиге отклоняется с `ValueError`.
- Один топик на параметр на станцию. Два топика на один параметр — `ValueError`.
- Диапазоны: `temperature_2m` −50…50, `relative_humidity_2m` 0…100 (≥99.5 — заглушка), `pressure_msl` 600…820.
- `SENSOR_LOCATIONS = {"yaroslavl", "tsedenevo"}`. Остальные семь слагов не получают код `sensors` ни при каких условиях.
- Retained-сообщения никогда не считаются данными.
- Ключ часа истории — `%Y-%m-%dT%H:00` в `Europe/Moscow`, совпадает с элементом `time[]`.
- Вес датчика — ровно вдвое больше среднего веса модели по той же переменной. Существующие веса моделей не меняются.
- Датчики не участвуют в `verification`.
- Бакет часа не пишется, если за окно не ответила ни одна станция.
- Хвост истории старше `history_days` (30) обрезается.
- Каждая задача заканчивается зелёным `pytest` и коммитом.

---

### Task 1: Строгий конфиг станций и усреднение

Переводит конфиг на канонические имена переменных `meteo.py` и вводит усреднение по станциям. История и `meteo.py` — в следующих задачах.

**Files:**
- Modify: `tools/stations.json`
- Modify: `tools/collect_sensors.py` — `KIND_RANGES`, `HUM_SENTINEL`, `parse_payload`, `load_stations`, `build_snapshot`
- Test: `tests/test_sensors.py`

**Interfaces:**
- Consumes: ничего.
- Produces:
  - `SENSOR_PARAMS: dict[str, tuple[float, float]]` — белый список параметров с диапазонами.
  - `load_stations(path) -> list[dict]` — валидирует схему; каждый `st['sensors']` это `{param_name: topic}`.
  - `parse_payload(raw) -> float | None` — без изменений по сигнатуре.
  - `validate(param, value) -> str | None` — первый аргумент теперь имя параметра из `SENSOR_PARAMS`.
  - `average_stations(per_station) -> dict` — `{param: {"value": float, "n": int, "stations": list[str]}}`; станции без живого значения параметра исключены, а не заменены нулём.

- [ ] **Step 1: Написать падающие тесты**

Добавить в `tests/test_sensors.py`:

```python
def test_config_rejects_two_topics_for_one_parameter(tmp_path):
    cfg = {
        "broker": "b", "port": 1883, "window_s": 10, "history_days": 30,
        "stations": [{
            "id": "s1", "name": "S1", "lat": 57.0, "lon": 39.0,
            "sensors": {"temperature_2m": ["a", "b"]},
        }],
    }
    p = tmp_path / "st.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    with pytest.raises(ValueError) as e:
        load_stations(str(p))
    assert "topic" in str(e.value).lower() or "строка" in str(e.value).lower()


def test_config_rejects_parameter_outside_allowlist(tmp_path):
    cfg = {
        "broker": "b", "port": 1883, "window_s": 10, "history_days": 30,
        "stations": [{
            "id": "s1", "name": "S1", "lat": 57.0, "lon": 39.0,
            "sensors": {"wind_speed_10m": "some/topic"},
        }],
    }
    p = tmp_path / "st.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    with pytest.raises(ValueError) as e:
        load_stations(str(p))
    assert "wind_speed_10m" in str(e.value)


def test_config_accepts_topic_string(tmp_path):
    cfg = {
        "broker": "b", "port": 1883, "window_s": 10, "history_days": 30,
        "stations": [{
            "id": "s1", "name": "S1", "lat": 57.0, "lon": 39.0,
            "sensors": {"temperature_2m": "some/topic"},
        }],
    }
    p = tmp_path / "st.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    got = load_stations(str(p))
    assert got[0]["sensors"]["temperature_2m"] == "some/topic"


def test_average_excludes_stations_without_live_value():
    per_station = [
        {"id": "a", "values": {"temperature_2m": 10.0}},
        {"id": "b", "values": {"temperature_2m": 20.0}},
        {"id": "c", "values": {}},
    ]
    got = average_stations(per_station)
    assert got["temperature_2m"]["value"] == 15.0
    assert got["temperature_2m"]["n"] == 2
    assert got["temperature_2m"]["stations"] == ["a", "b"]


def test_average_missing_parameter_is_absent_not_zero():
    got = average_stations([{"id": "a", "values": {"temperature_2m": 10.0}}])
    assert "pressure_msl" not in got


def test_validate_rejects_humidity_sentinel():
    assert validate("relative_humidity_2m", 99.99) is not None
    assert validate("relative_humidity_2m", 71.6) is None
```

- [ ] **Step 2: Прогнать и убедиться в падении**

Run: `& ".venv\Scripts\python.exe" -m pytest tests/test_sensors.py -q`

Expected: FAIL — `SENSOR_PARAMS`/`average_stations` не импортируются, `load_stations` падает на схеме-списке.

- [ ] **Step 3: Переписать конфиг `tools/stations.json`**

```json
{
  "broker": "yar.gorod76.ru",
  "port": 1883,
  "window_s": 240,
  "history_days": 30,
  "stations": [
    {
      "id": "penaty",
      "name": "Пенаты",
      "lat": 57.6304,
      "lon": 39.91527,
      "sensors": {
        "temperature_2m": "city/out/zavolga/penaty/temp/ws01",
        "relative_humidity_2m": "city/out/zavolga/penaty/hum/ws01"
      }
    },
    {
      "id": "frunze",
      "name": "ул. Фрунзе",
      "lat": 57.58337,
      "lon": 39.90823,
      "sensors": {
        "temperature_2m": "city/out/frunze/temp/left",
        "relative_humidity_2m": "city/out/frunze/hum/left",
        "pressure_msl": "city/out/frunze/press"
      }
    },
    {
      "id": "east",
      "name": "Восток",
      "lat": 57.62,
      "lon": 39.92,
      "sensors": {
        "temperature_2m": "city/out/east/temp/ds",
        "pressure_msl": "city/out/east/press"
      }
    },
    {
      "id": "bereg",
      "name": "Берег",
      "lat": 57.55,
      "lon": 39.76,
      "sensors": {
        "temperature_2m": "/bereg/2708554-1458260/tmp315/status",
        "relative_humidity_2m": "/bereg/2708554-1458260/Hum339/status"
      }
    }
  ]
}
```

Каналы выбраны пользователем 28.09.2026 по живому срезу. Станций ровно
четыре: `penaty`, `frunze`, `east`, `bereg`. Влажность `east` исключена
(38.21 % против 68–87 % у соседей). Станции `yarbatut`, `west`, обе ESPHome и
Берег-2 исключены целиком; причины — в спеке, раздел «Станции и значение».

- [ ] **Step 4: Переписать валидацию в `tools/collect_sensors.py`**

Заменить блок `KIND_RANGES`/`HUM_SENTINEL` и `validate`:

```python
# Параметры, которые реально измеряет сеть. Ключи совпадают с именами
# переменных meteo.py, поэтому подстановка в таблицу Часов не требует
# преобразований. Всё остальное (ветер, осадки, CAPE) датчики не меряют.
SENSOR_PARAMS = {
    'temperature_2m': (-50.0, 50.0),
    'relative_humidity_2m': (0.0, 100.0),
    'pressure_msl': (600.0, 820.0),
}

# Влажность 99.5+ — заведомо заглушка, а не измерение.
HUM_SENTINEL = 99.5


def validate(param, value):
    """Проверяет значение против диапазона. None — значение допустимо,
    иначе строка с причиной отброса."""
    bounds = SENSOR_PARAMS.get(param)
    if bounds is None:
        return 'unknown parameter %r' % (param,)
    if value is None:
        return 'no value'
    if value != value:  # NaN
        return 'not a number'

    low, high = bounds
    if not (low <= value <= high):
        return 'out of range [%g, %g]' % (low, high)
    if param == 'relative_humidity_2m' and value >= HUM_SENTINEL:
        return 'humidity sentinel'
    return None
```

- [ ] **Step 5: Переписать `load_stations` под строгую схему**

Внутри `load_stations` заменить проверку `sensors` (сейчас ждёт список `[kind, topic]`) на:

```python
        sensors = st['sensors']
        if not isinstance(sensors, dict) or not sensors:
            raise ValueError('station %r: sensors must be a non-empty object' % sid)
        for param, topic in sensors.items():
            if param not in SENSOR_PARAMS:
                raise ValueError(
                    'station %r: parameter %r is not measured by the network; '
                    'allowed: %s' % (sid, param, ', '.join(sorted(SENSOR_PARAMS))))
            if not isinstance(topic, str) or not topic.strip():
                raise ValueError('station %r: sensors[%r] must be a topic string'
                                 % (sid, param))
```

Добавить функцию усреднения рядом с `build_snapshot`:

```python
def average_stations(per_station):
    """Среднее по станциям для каждого параметра.

    Станция без живого значения параметра исключается из среднего, а не
    считается нулём. Возвращает {param: {"value", "n", "stations"}}.
    """
    out = {}
    for station in per_station:
        for param, value in (station.get('values') or {}).items():
            if param not in SENSOR_PARAMS:
                continue
            entry = out.setdefault(param, {'value': 0.0, 'n': 0, 'stations': []})
            entry['value'] += value
            entry['n'] += 1
            entry['stations'].append(station['id'])
    for entry in out.values():
        entry['value'] = round(entry['value'] / entry['n'], 2)
        entry['stations'].sort()
    return out
```

- [ ] **Step 6: Переписать `build_snapshot` под новую схему**

`build_snapshot` обходит `st['sensors'].items()`, где элемент — строка-топик, а не пара:

```python
        for param, topic in st['sensors'].items():
            if topic not in received:
                continue
            value = parse_payload(received[topic])
            reason = validate(param, value)
            if reason is not None:
                rejected.append({'param': param, 'topic': topic,
                                 'raw': received[topic], 'reason': reason})
                continue
            values[param] = round(value, 2)
            ts = seen.get(topic)
            if ts is not None and (last_ts is None or ts > last_ts):
                last_ts = ts
```

Ключ `'values'` в выходе теперь содержит канонические имена вместо `t1`/`h`/`p`.
Ключ `'rejected'` элемента меняется с `'key'` на `'param'`.

- [ ] **Step 7: Прогнать тесты коллектора**

Run: `& ".venv\Scripts\python.exe" -m pytest tests/test_sensors.py -q`

Expected: новые тесты PASS. Старые тесты, использовавшие схему `[kind, topic]`, нужно поправить в этом же шаге — каждый падающий старый тест переводится на строковый топик, а ожидаемые ключи `values` меняются на канонические имена.

- [ ] **Step 8: Закоммитить**

```bash
git add tools/stations.json tools/collect_sensors.py tests/test_sensors.py
git commit -m "feat(sensors): one value per parameter per station

Stations declared three temperature channels each, plus derived aggregates
like temp_min and indoor readings. Averaging channels gave Yarbatut triple
weight and mixed indoor with outdoor, so the config now maps exactly one
topic to each measurable parameter and the average is taken across stations.

The parameter allowlist keeps wind and rain out of the column: the network
measures them nowhere, and wiring the dead yarecologia topics in would put
16-month-old numbers next to live ones."
```

---

### Task 2: Накопление истории по часам

**Files:**
- Modify: `tools/collect_sensors.py` — добавить `load_history`, `record_history`, `trim_history`, вызов из `run`
- Test: `tests/test_sensors.py`

**Interfaces:**
- Consumes: `average_stations(per_station) -> dict` из Task 1; формат `stations.json` с ключом `history_days`.
- Produces:
  - `load_history(path) -> dict` — возвращает `{"hours": {...}}`; отсутствующий файл даёт `{"hours": {}}`; нечитаемый JSON даёт `{"hours": {}}` без исключения.
  - `record_history(hours, hour_key, per_station, now) -> bool` — дописывает значения станций в бакет `hour_key`; возвращает `False` и ничего не пишет, если `per_station` пуст.
  - `trim_history(hours, history_days, now) -> dict` — удаляет баеты старше `history_days`.
  - `moscow_hour_key(now_ts) -> str` — `%Y-%m-%dT%H:00` в `Europe/Moscow`.
  - Записывает `sensors_history.json` в корень репозитория.

- [ ] **Step 1: Написать падающие тесты**

Добавить в `tests/test_sensors.py`:

```python
def test_record_history_merges_same_hour():
    hours = {"hours": {}}
    ok = record_history(hours, "2026-09-28T12:00",
                        [{"id": "a", "values": {"temperature_2m": 10.0}}], 0)
    assert ok is True
    ok = record_history(hours, "2026-09-28T12:00",
                        [{"id": "a", "values": {"temperature_2m": 12.0}}], 0)
    assert ok is True
    assert hours["hours"]["2026-09-28T12:00"]["samples"] == 2
    assert hours["hours"]["2026-09-28T12:00"]["stations"]["a"]["temperature_2m"] == [10.0, 12.0]


def test_record_history_new_hour_creates_bucket():
    hours = {"hours": {}}
    record_history(hours, "2026-09-28T13:00",
                   [{"id": "a", "values": {"temperature_2m": 10.0}}], 0)
    assert list(hours["hours"]) == ["2026-09-28T13:00"]


def test_record_history_skips_empty_run():
    hours = {"hours": {}}
    assert record_history(hours, "2026-09-28T12:00", [], 0) is False
    assert hours["hours"] == {}


def test_record_history_keeps_stations_equal_weight():
    hours = {"hours": {}}
    # Одна станция с одним замером не должна получать вес шести станций.
    record_history(hours, "2026-09-28T12:00", [
        {"id": "a", "values": {"temperature_2m": 10.0}},
        {"id": "b", "values": {"temperature_2m": 20.0}},
        {"id": "c", "values": {"temperature_2m": 30.0}},
        {"id": "d", "values": {"temperature_2m": 40.0}},
        {"id": "e", "values": {"temperature_2m": 50.0}},
        {"id": "f", "values": {"temperature_2m": 60.0}},
    ], 0)
    record_history(hours, "2026-09-28T12:00",
                   [{"id": "a", "values": {"temperature_2m": 100.0}}], 0)
    got = history_hour_value(hours["hours"]["2026-09-28T12:00"], "temperature_2m")
    # a: (10+100)/2 = 55, остальные 20..60 -> (55+20+30+40+50+60)/6 = 42.5
    assert got["value"] == 42.5
    assert got["n"] == 6


def test_trim_history_drops_old_buckets():
    hours = {"hours": {
        "2026-08-01T10:00": {"samples": 1, "stations": {}},
        "2026-09-28T10:00": {"samples": 1, "stations": {}},
    }}
    now = moscow_now_ts("2026-09-28T12:00")
    got = trim_history(hours, 30, now)
    assert list(got["hours"]) == ["2026-09-28T10:00"]


def test_load_history_missing_file_is_empty(tmp_path):
    got = load_history(str(tmp_path / "nope.json"))
    assert got == {"hours": {}}


def test_load_history_corrupt_file_is_empty(tmp_path):
    p = tmp_path / "h.json"
    p.write_text("{not json", encoding="utf-8")
    assert load_history(str(p)) == {"hours": {}}
```

- [ ] **Step 2: Прогнать и убедиться в падении**

Run: `& ".venv\Scripts\python.exe" -m pytest tests/test_sensors.py -q`

Expected: FAIL — функции не существуют.

- [ ] **Step 3: Реализовать историю в `tools/collect_sensors.py`**

Добавить импорт и константы:

```python
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
```

```python
HISTORY_TZ = ZoneInfo('Europe/Moscow')
HISTORY_DEFAULT_DAYS = 30


def moscow_hour_key(now_ts):
    """Ключ бакета истории: локальный московский час в формате time[]."""
    return datetime.fromtimestamp(now_ts, HISTORY_TZ).strftime('%Y-%m-%dT%H:00')


def moscow_now_ts(hour_key):
    """Обратное преобразование ключа в unix-время, для отсечения старого."""
    return datetime.strptime(hour_key, '%Y-%m-%dT%H:%M').replace(
        tzinfo=HISTORY_TZ).timestamp()


def load_history(path):
    """Читает историю. Отсутствующий или битый файл — пустая история,
    а не ошибка: сборка сайта не должна зависеть от накопленного."""
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {'hours': {}}
    if not isinstance(data, dict) or not isinstance(data.get('hours'), dict):
        return {'hours': {}}
    return data


def record_history(hours, hour_key, per_station, _now):
    """Дописывает значения станций в бакет часа. Пустой прогон не пишется."""
    live = [s for s in per_station if s.get('values')]
    if not live:
        return False
    bucket = hours['hours'].setdefault(hour_key, {'samples': 0, 'stations': {}})
    for station in live:
        entry = bucket['stations'].setdefault(station['id'], {})
        for param, value in station['values'].items():
            entry.setdefault(param, []).append(value)
    bucket['samples'] += 1
    return True


def history_hour_value(bucket, param):
    """Значение часа: среднее по станциям от средних по замерам станции.

    Станции равноправны независимо от того, сколько прогонов их видели.
    """
    per_station = []
    for sid, values in (bucket.get('stations') or {}).items():
        samples = values.get(param)
        if not samples:
            continue
        per_station.append(mean(samples))
    if not per_station:
        return None
    return {'value': round(sum(per_station) / len(per_station), 2),
            'n': len(per_station)}


def trim_history(hours, history_days, now):
    """Удаляет бакеты старше history_days."""
    cutoff = moscow_hour_key(now - history_days * 86400)
    hours['hours'] = {k: v for k, v in hours['hours'].items() if k >= cutoff}
    return hours
```

Добавить локальный помощник `mean`, если его нет:

```python
def mean(values):
    values = list(values)
    return sum(values) / len(values) if values else None
```

- [ ] **Step 4: Вызвать запись истории из `run`**

В `run` после вычисления `snapshot` и до записи `sensors.json`:

```python
    history_path = os.path.join(ROOT, 'sensors_history.json')
    history = load_history(history_path)
    now = time.time()
    record_history(history, moscow_hour_key(now), snapshot['stations'], now)
    trim_history(history, int(settings.get('history_days', HISTORY_DEFAULT_DAYS)), now)
    with open(history_path, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
        f.write('\n')
```

- [ ] **Step 5: Прогнать тесты**

Run: `& ".venv\Scripts\python.exe" -m pytest tests/test_sensors.py -q`

Expected: PASS.

- [ ] **Step 6: Проверить реальным прогоном**

Run: `& ".venv\Scripts\python.exe" tools\collect_sensors.py --window 60`

Expected: `[ok] ... 4/4 stations online` и создан `sensors_history.json` с одним бакетом. Затем проверить `sensors_history.json` — внутри `hours` ключ вида `2026-09-28T12:00` и `stations` с id из конфига.

- [ ] **Step 7: Закоммитить**

```bash
git add tools/collect_sensors.py tests/test_sensors.py
git commit -m "feat(sensors): accumulate per-station readings by Moscow hour

History is stored per station rather than as a pre-averaged number, so every
station keeps equal weight no matter how many of the 15-minute runs saw it.
A run where no station answered writes nothing, keeping empty averages out
of the record."
```

---

### Task 3: Вес датчика в консенсусе

**Files:**
- Modify: `meteo.py` — добавить константы и `apply_sensor_weights` рядом с `make_weights`
- Test: `tests/test_weights.py`

**Interfaces:**
- Consumes: ничего.
- Produces:
  - `SENSOR_CODE = 'sensors'`, `SENSOR_NAME = 'Датчик'`
  - `SENSOR_VARS = ('temperature_2m', 'relative_humidity_2m', 'pressure_msl')`
  - `apply_sensor_weights(weights_by_var, model_codes) -> None` — мутирует `weights_by_var`: для каждой переменной из `SENSOR_VARS` проставляет `SENSOR_CODE` с весом ровно вдвое больше среднего веса моделей. Если переменной нет в `weights_by_var`, создаёт её с весами `1.0` на модель и `2.0` на датчики.

- [ ] **Step 1: Написать падающие тесты**

Добавить в `tests/test_weights.py`:

```python
def test_sensor_weight_is_double_average_model():
    wbv = {"temperature_2m": {"a": 0.05, "b": 0.05, "c": 0.05}}
    apply_sensor_weights(wbv, ["a", "b", "c"])
    assert wbv["temperature_2m"]["sensors"] == 2 * 0.05


def test_sensor_weight_added_for_variable_without_weights():
    # relative_humidity_2m нет в weights_by_var: текущий код подставляет
    # всем моделям fallback 1.0. Датчик должен получить вдвое больше.
    wbv = {"temperature_2m": {"a": 0.5, "b": 0.5}}
    apply_sensor_weights(wbv, ["a", "b"])
    assert wbv["relative_humidity_2m"] == {"a": 1.0, "b": 1.0, "sensors": 2.0}


def test_sensor_weight_leaves_model_weights_untouched():
    before = {"a": 0.3, "b": 0.7}
    wbv = {"temperature_2m": dict(before)}
    apply_sensor_weights(wbv, ["a", "b"])
    assert wbv["temperature_2m"]["a"] == before["a"]
    assert wbv["temperature_2m"]["b"] == before["b"]


def test_sensor_weight_untouched_variables_absent():
    wbv = {"precipitation": {"a": 0.5, "b": 0.5}}
    apply_sensor_weights(wbv, ["a", "b"])
    assert wbv["precipitation"] == {"a": 0.5, "b": 0.5}
```

- [ ] **Step 2: Прогнать и убедиться в падении**

Run: `& ".venv\Scripts\python.exe" -m pytest tests/test_weights.py -q`

Expected: FAIL — `apply_sensor_weights` не импортируется.

- [ ] **Step 3: Реализовать в `meteo.py`**

Добавить рядом с `make_weights` (`meteo.py:1068`):

```python
SENSOR_CODE = "sensors"
SENSOR_NAME = "Датчик"
# Параметры, которые сеть датчиков реально измеряет. Ветер, осадки,
# облачность, CAPE и WMO недоступны: подставлять их значило бы выдать
# внешний источник за «Датчик».
SENSOR_VARS = ("temperature_2m", "relative_humidity_2m", "pressure_msl")


def apply_sensor_weights(weights_by_var, model_codes):
    """Проставляет датчику вес вдвое больше среднего веса модели.

    Вес используется в weighted_consensus только как отношение, поэтому
    нормировка на единицу не нужна и веса моделей не трогаются.

    Для переменных, которых нет в weights_by_var, текущий assemble_consensus
    подставляет всем моделям fallback 1.0. Здесь это поведение воспроизводится
    явно (1.0 на модель), а датчику достаётся 2.0, то есть двойной вес.
    """
    for var in SENSOR_VARS:
        weights = weights_by_var.get(var)
        if not weights:
            weights = {code: 1.0 for code in model_codes}
            weights_by_var[var] = weights
        present = [w for code, w in weights.items() if code != SENSOR_CODE]
        if not present:
            continue
        weights[SENSOR_CODE] = 2.0 * (sum(present) / len(present))
```

- [ ] **Step 4: Прогнать тесты**

Run: `& ".venv\Scripts\python.exe" -m pytest tests/test_weights.py -q`

Expected: PASS.

- [ ] **Step 5: Закоммитить**

```bash
git add meteo.py tests/test_weights.py
git commit -m "feat: give the sensor average double weight in the consensus

The weight is relative to the average model weight, not an absolute number:
weighted_consensus divides by the sum of weights, so only the ratio matters.
For relative_humidity_2m and pressure_msl there is no entry in
weights_by_var at all, and the current code falls back to 1.0 for every
model, so those two are set explicitly to keep the double weight and leave
model weights exactly as they were."
```

---

### Task 4: Инъекция «Датчика» в `meteo.py` только для двух локаций

**Files:**
- Modify: `meteo.py` — добавить `SENSOR_LOCATIONS`, `load_sensor_model`; вызов в `build_city_payload` между циклом провайдеров и `assemble_consensus`
- Test: `tests/test_locations.py`, `tests/test_generation.py`

**Interfaces:**
- Consumes: `SENSOR_CODE`, `SENSOR_NAME`, `SENSOR_VARS`, `apply_sensor_weights` из Task 3; `history_hour_value` из Task 2 (воспроизводится локально в `meteo.py`).
- Produces:
  - `SENSOR_LOCATIONS = {"yaroslavl", "tsedenevo"}`
  - `load_sensor_model(grid, path=None) -> dict | None` — возвращает `{"time": grid, "data": {var: [float|None] * len(grid)}}` или `None`, если истории нет. Часы без данных дают `None`, а не 0.
  - `build_city_payload` для слагов из `SENSOR_LOCATIONS` добавляет `SENSOR_CODE` в `hourly_by_model`, `city_codes`, `city_names`.

- [ ] **Step 1: Написать падающие тесты**

Добавить в `tests/test_locations.py`:

```python
def test_sensor_model_fills_past_hours_and_nulls_the_rest(tmp_path):
    hist = {"hours": {"2026-09-28T10:00": {
        "samples": 2, "stations": {
            "a": {"temperature_2m": [10.0, 12.0]},
            "b": {"temperature_2m": [20.0, 20.0]},
        }},
        "2026-09-28T11:00": {
        "samples": 1, "stations": {
            "a": {"pressure_msl": [760.0]}}}}}
    p = tmp_path / "sensors_history.json"
    p.write_text(json.dumps(hist), encoding="utf-8")
    grid = ["2026-09-28T09:00", "2026-09-28T10:00", "2026-09-28T11:00",
            "2026-09-28T12:00"]
    model = load_sensor_model(grid, str(p))
    assert model["time"] == grid
    assert model["data"]["temperature_2m"] == [None, 16.0, None, None]
    assert model["data"]["pressure_msl"] == [None, None, 760.0, None]
    assert model["data"]["relative_humidity_2m"] == [None, None, None, None]


def test_sensor_model_missing_history_is_none(tmp_path):
    assert load_sensor_model(["2026-09-28T10:00"], str(tmp_path / "nope.json")) is None


def test_sensor_model_corrupt_history_is_none(tmp_path):
    p = tmp_path / "h.json"
    p.write_text("{oops", encoding="utf-8")
    assert load_sensor_model(["2026-09-28T10:00"], str(p)) is None


def test_sensors_absent_for_other_cities():
    assert SENSOR_LOCATIONS == {"yaroslavl", "tsedenevo"}
    for slug in ["rybinsk", "rostov", "petropavlovka", "moscow", "loo",
                 "borok", "batumi"]:
        assert slug not in SENSOR_LOCATIONS
```

Добавить в `tests/test_generation.py`:

```python
def test_yaroslavl_payload_gains_sensors_column(tmp_path):
    ...
```

Для последнего теста используй существующий фикстур построения payload в
`tests/test_generation.py`: собери `raw_by_model` для одного моделя, подложи
`hourly_by_model` с датчиком через `load_sensor_model` и проверь, что
`payload["model_codes"]` содержит `SENSOR_CODE`, а
`payload["model_names"][SENSOR_CODE] == "Датчик"`, и что
`payload["models"][SENSOR_CODE]["temperature_2m"]` — список длины
`len(payload["time"])`.

- [ ] **Step 2: Прогнать и убедиться в падении**

Run: `& ".venv\Scripts\python.exe" -m pytest tests/test_locations.py tests/test_generation.py -q`

Expected: FAIL — `load_sensor_model`, `SENSOR_LOCATIONS` не существуют.

- [ ] **Step 3: Реализовать загрузку в `meteo.py`**

Добавить рядом с `SENSOR_VARS` из Task 3:

```python
SENSOR_LOCATIONS = {"yaroslavl", "tsedenevo"}
SENSOR_HISTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "sensors_history.json")


def _sensor_hour_value(bucket, var):
    """Значение часа: среднее по станциям от средних по замерам станции."""
    per_station = []
    for values in (bucket.get("stations") or {}).values():
        samples = values.get(var)
        if not samples:
            continue
        per_station.append(sum(samples) / len(samples))
    if not per_station:
        return None
    return round(sum(per_station) / len(per_station), 2)


def load_sensor_model(grid, path=None):
    """Собирает псевдо-модель «Датчик» по оси grid.

    Возвращает None, если истории нет или она нечитаема: столбик тогда просто
    не появляется, а сборка продолжается. Часы без наблюдений дают None, а не
    0, чтобы weighted_consensus их отбросил.
    """
    path = path or SENSOR_HISTORY
    try:
        with open(path, encoding="utf-8") as f:
            history = json.load(f)
    except (OSError, ValueError):
        return None
    hours = history.get("hours") if isinstance(history, dict) else None
    if not isinstance(hours, dict) or not hours:
        return None

    data = {}
    found = False
    for var in SENSOR_VARS:
        column = []
        for hour in grid:
            bucket = hours.get(hour)
            value = _sensor_hour_value(bucket, var) if bucket else None
            if value is not None:
                found = True
            column.append(value)
        data[var] = column
    if not found:
        return None
    return {"time": list(grid), "data": data}
```

- [ ] **Step 4: Вызвать инъекцию в `build_city_payload`**

В `meteo.py` в `build_city_payload`, сразу после цикла `for code, name, _fn, *_ in providers:` (после строки с `city_names[code] = name`) и **до** вызова `assemble_consensus`, вставить:

```python
    if loc["slug"] in SENSOR_LOCATIONS:
        sensor_model = load_sensor_model(grid)
        if sensor_model:
            hourly_by_model[SENSOR_CODE] = sensor_model
            city_codes.append(SENSOR_CODE)
            city_names[SENSOR_CODE] = SENSOR_NAME
            apply_sensor_weights(weights_by_var, city_codes)
            print(f"[info] {loc['name']}: sensor column with "
                  f"{sum(1 for v in sensor_model['data'].values() if any(x is not None for x in v))} "
                  f"parameters")
```

- [ ] **Step 5: Прогнать тесты**

Run: `& ".venv\Scripts\python.exe" -m pytest tests/ -m "not integration" -q`

Expected: PASS, включая 308 существующих тестов. Если падают тесты, считающие
число моделей для `yaroslavl`/`tsedenevo`, обновить ожидания: моделей стало
13, а не 12. Если падает проверка, что `verification` содержит только внешних
модели, убедиться, что `SENSOR_CODE` в `verification` не попадает — датчики
умышленно не участвуют.

- [ ] **Step 6: Прогнать тесты с реальной историей**

Run: `& ".venv\Scripts\python.exe" -m pytest tests/ -m "not integration" -q`
с существующим `sensors_history.json` из Task 2.

Expected: PASS, в выводе `meteo.py` при реальной сборке печатается строка
`[info] Ярославль: sensor column with N parameters`.

- [ ] **Step 7: Закоммитить**

```bash
git add meteo.py tests/test_locations.py tests/test_generation.py
git commit -m "feat: add the Dатчик pseudo-source to Yaroslavl and Tsedenevo

Sensors are fed into hourly_by_model as one more source, so assemble_consensus
handles weighting, min_sources and None-skipping with no extra code. Only
past hours carry values, which leaves the forecast rows untouched because
weighted_consensus drops None.

Deliberately excluded from verification: it scores historical forecasts, and
an observation would corrupt the MAE model that make_weights derives from."
```

---

### Task 5: Фильтр столбика по параметру в `template.html`

**Files:**
- Modify: `template.html` — `cmpColOrder` (~:1098), вызов в `setVar` (~:986), `updateLegend` (~:1082), `buildCmpTable` (~:1110)
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: `SENSOR_CODE` и список `SENSOR_VARS` во фронтенде — объявляются в JS рядом с `CHART_VARS`.
- Produces: `cmpColOrder(codes, v)` — второй аргумент `v` имя переменной; код `sensors` отбрасывается, если `v` не в списке измеряемых.

- [ ] **Step 1: Написать падающий тест**

Добавить в `tests/test_render.py` тест, проверяющий текст `template.html`:

```python
def test_cmp_col_order_filters_sensor_for_unmeasured_variable():
    html = read_template()
    assert "const SENSOR_VARS=['temperature_2m','relative_humidity_2m','pressure_msl'];" in html
    assert "c!==SENSOR_CODE" in html or "!(c===SENSOR_CODE" in html
    assert "cmpColOrder(codes,v)" in html
    assert "cmpColOrder(codes,cmpVar)" in html
```

Используй уже существующий в этом файле способ чтения `template.html`
(в нём уже есть чтение шаблона для других проверок) — новый способ не изобретай.

- [ ] **Step 2: Прогнать и убедиться в падении**

Run: `& ".venv\Scripts\python.exe" -m pytest tests/test_render.py -q`

Expected: FAIL — строки отсутствуют.

- [ ] **Step 3: Изменить `cmpColOrder`**

Было:

```js
  function cmpColOrder(codes){
    const out=codes.filter(c=>c!=='vc'&&c!=='mb'&&c!=='wwo'&&c!=='xweather'&&c!=='tomorrow');
```

Стало:

```js
  function cmpColOrder(codes,v){
    const sensorOk=v==null||SENSOR_VARS.indexOf(v)>=0;
    const out=codes.filter(c=>c!=='vc'&&c!=='mb'&&c!=='wwo'&&c!=='xweather'&&c!=='tomorrow'&&!(c===SENSOR_CODE&&!sensorOk));
```

- [ ] **Step 4: Обновить три вызова**

В `setVar` строка `const cc=cmpColOrder(codes);` → `const cc=cmpColOrder(codes,v);`
В `updateLegend` строка `cmpColOrder(codes).forEach((c,i)=>{` → `cmpColOrder(codes,curVar).forEach((c,i)=>{`
В `buildCmpTable` строка `const cc=cmpColOrder(codes);` → `const cc=cmpColOrder(codes,cmpVar);`

- [ ] **Step 5: Объявить константы в JS**

Рядом с `CHART_VARS` (`template.html:288`) добавить:

```js
  const SENSOR_CODE='sensors',SENSOR_NAME='Датчик';
  const SENSOR_VARS=['temperature_2m','relative_humidity_2m','pressure_msl'];
```

- [ ] **Step 6: Прогнать тесты**

Run: `& ".venv\Scripts\python.exe" -m pytest tests/test_render.py -q`

Expected: PASS.

- [ ] **Step 7: Проверить в браузере**

Открыть `index.html` для Ярославля, перейти на «Часы». Ожидается столбик «Датчик»
и линия в легенде. Переключить параметр на ветер — столбик и линия должны
исчезнуть полностью, а не стать пустыми. Переключить город на Москву — столбика
нет вообще.

- [ ] **Step 8: Закоммитить**

```bash
git add template.html tests/test_render.py
git commit -m "feat(clock): hide the sensor column for parameters it cannot measure

Without the filter the column would render as an empty grey strip whenever a
variable outside the three measured ones is selected, and the legend would
list a series with no data."
```

---

### Task 6: Удаление слоя датчиков с Радара

**Files:**
- Modify: `radar_template.html` — удалить строки 135–218, кнопку `#stoggle`, CSS `.leaflet-stations-pane`/`.stlabel`/`.station-pop`/`.strow`/`.stoff`
- Delete: `tests/test_radar_stations.py`
- Modify: `tests/test_radar.py` — добавить тест-страж
- Regenerate: `radar.html`

**Interfaces:**
- Consumes: ничего.
- Produces: `radar_template.html` и `radar.html` без слоя станций; тест-страж в `tests/test_radar.py`.

- [ ] **Step 1: Написать падающий тест-страж**

Добавить в `tests/test_radar.py`:

```python
def test_radar_template_has_no_station_layer():
    src = read_template()  # используй существующий хелпер чтения в файле
    for banned in ["createPane('stations')", "ST_LABELS", "stoggle",
                   "stations.json", "stDraw", "leaflet-stations-pane",
                   "stlabel"]:
        assert banned not in src, banned
```

- [ ] **Step 2: Прогнать и убедиться в падении**

Run: `& ".venv\Scripts\python.exe" -m pytest tests/test_radar.py -q`

Expected: FAIL — `createPane('stations')` ещё присутствует.

- [ ] **Step 3: Удалить блок из `radar_template.html`**

Удалить строки 135–218 целиком (от `  // ---- Метеостанции сети` до
`  map.on('zoomend',function(){\n    if(stOn) stLoad();\n  });`
включительно), кнопку `<button id="stoggle">Датчики</button>` и CSS-правила
`.leaflet-stations-pane`, `.stlabel`, `.station-pop`, `.strow`, `.stoff`,
`.strow.stoff`, а также стили кнопки-переключателя `#stoggle`.

- [ ] **Step 4: Удалить `tests/test_radar_stations.py`**

```bash
git rm tests/test_radar_stations.py
```

- [ ] **Step 5: Пересобрать `radar.html`**

Run: `& ".venv\Scripts\python.exe" tools\build_radar.py radar`

Expected: `[ok] F:\Meteo\radar.html written (... bytes)`

- [ ] **Step 6: Прогнать тесты**

Run: `& ".venv\Scripts\python.exe" -m pytest -q`

Expected: PASS. Тестов станет меньше на число удалённых в
`tests/test_radar_stations.py`.

- [ ] **Step 7: Проверить headless**

Run:

```powershell
& ".venv\Scripts\python.exe" tools\headless_probe.py radar.html "C:\Users\SamLab\AppData\Local\Temp\opencode\probe_clean.js" "C:\Users\SamLab\AppData\Local\Temp\opencode\probe_clean.txt"
```

`probe_clean.js`:

```js
(function () {
  var errs = [];
  window.onerror = function (m) { errs.push(String(m)); };
  var lines = [];
  setTimeout(function () {
    lines.push('stations_pane=' + !!document.querySelector('.leaflet-stations-pane'));
    lines.push('toggle_button=' + !!document.getElementById('stoggle'));
    lines.push('markers=' + document.querySelectorAll('.station-pop').length);
    lines.push('errors=' + (errs.length ? errs.join(' | ') : 'none'));
    document.getElementById('probeout').textContent = lines.join('\n');
  }, 4000);
})();
```

Expected: `stations_pane=false`, `toggle_button=false`, `markers=0`,
`errors=none`.

- [ ] **Step 8: Закоммитить**

```bash
git add radar_template.html radar.html tests/test_radar.py
git commit -m "refactor(radar): drop the station layer

The clock tab turned out to be a 384-row hourly grid, so sensors belong there
as a source column rather than as map markers. The guard test fails if the
layer comes back through a later template edit."
```

---

### Task 7: Workflow и публикация

**Files:**
- Modify: `.github/workflows/sensors.yml` — коммитить второй файл
- Modify: `.github/workflows/deploy.yml` — убрать `cp -f sensors.json _site/`
- Test: `tests/test_render.py` или новый `tests/test_workflows.py`

**Interfaces:**
- Consumes: `sensors_history.json` из Task 2.
- Produces: `sensors.yml` коммитит `sensors.json` и `sensors_history.json`; `deploy.yml` больше не публикует `sensors.json` в `_site/`.

- [ ] **Step 1: Написать падающие тесты**

Добавить в `tests/test_render.py`:

```python
def test_sensors_workflow_commits_history():
    yml = read_workflow("sensors.yml")
    assert "sensors_history.json" in yml
    assert "git add sensors.json sensors_history.json" in yml


def test_deploy_no_longer_publishes_snapshot():
    yml = read_workflow("deploy.yml")
    assert "sensors.json _site/" not in yml
```

`read_workflow` — чтение `.github/workflows/<name>` относительно корня репозитория.

- [ ] **Step 2: Прогнать и убедиться в падении**

Run: `& ".venv\Scripts\python.exe" -m pytest tests/test_render.py -q`

Expected: FAIL.

- [ ] **Step 3: Обновить `sensors.yml`**

Заменить шаг `Commit snapshot`:

```yaml
      - name: Commit snapshot
        run: |
          if git diff --quiet -- sensors.json sensors_history.json; then
            echo "nothing to commit"
            exit 0
          fi
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add sensors.json sensors_history.json
          git commit -m "chore: refresh station snapshot"
          git push
```

- [ ] **Step 4: Убрать публикацию из `deploy.yml`**

Удалить строку `cp -f sensors.json _site/ || echo "no station snapshot yet"`
и комментарий над ней из блока `Prepare pages artifact`.

- [ ] **Step 5: Прогнать все тесты**

Run: `& ".venv\Scripts\python.exe" -m pytest -q`

Expected: PASS.

- [ ] **Step 6: Закоммитить**

```bash
git add .github/workflows/sensors.yml .github/workflows/deploy.yml tests/test_render.py
git commit -m "ci: commit sensor history and stop publishing the snapshot

History has to survive between workflow runs: data/ is gitignored and each CI
run starts from a clean checkout, so an accumulating file committed every 15
minutes is the only durable store. The snapshot itself is no longer fetched
by any page and does not need to reach the site."
```

---

### Task 8: Сквозная проверка и документация

**Files:**
- Modify: `docs/superpowers/specs/2026-09-28-sensors-as-clock-column-design.md` — отметить статус
- Modify: `data/sensors_yar.json` — удалить, черновик устарел

**Interfaces:**
- Consumes: всё из Task 1–7.
- Produces: зелёный полный набор тестов, задеплоенная функциональность, обновлённая документация.

- [ ] **Step 1: Удалить устаревший черновик инвентаря**

```bash
git rm --cached data/sensors_yar.json 2>$null; Remove-Item data/sensors_yar.json -ErrorAction SilentlyContinue
```

Файл был черновиком предыдущей инвентаризации и содержит retained-мусор
(давление `-14.0`, влажность `99.99`), который уже не соответствует действительности.

- [ ] **Step 2: Прогнать полный набор тестов**

Run: `& ".venv\Scripts\python.exe" -m pytest -q`

Expected: PASS, ноль падений.

- [ ] **Step 3: Прогнать реальный сбор коллектора**

Run: `& ".venv\Scripts\python.exe" tools\collect_sensors.py --window 240`

Expected: `[ok] ... N/4 stations online`, созданные `sensors.json` и
`sensors_history.json`. Затем проверить, что в `sensors_history.json` ключ бакета
совпадает с текущим московским часом.

- [ ] **Step 4: Проверить полную сборку сайта**

Run: `$env:OPENWEATHER_KEY=""; & ".venv\Scripts\python.exe" meteo.py`

Ожидается либо успешная генерация, либо ошибка внешнего API из-за пустых
ключей — важно лишь отсутствие `KeyError`/`NameError` и наличие строки
`[info] Ярославль: sensor column` либо её отсутствия при пустой истории.

- [ ] **Step 5: Закоммитить и запушить**

```bash
git add -A
git commit -m "docs: mark the sensor clock column spec as implemented"
git push origin main
```

- [ ] **Step 6: Дождаться деплоя и проверить вживую**

```bash
gh run watch --exit-status
```

Затем проверить, что `data/yaroslavl.json` на сайте содержит `"sensors"` в
`model_codes` и `"Датчик"` в `model_names`, а `data/moscow.json` — не содержит.

## Self-Review

**Покрытие спеки:**

| Раздел спеки | Задача |
|---|---|
| Усреднение по станциям, одно значение на параметр | Task 1 |
| Строгая схема конфига, белый список параметров | Task 1 |
| История по часам, обрезка, пустой прогон | Task 2 |
| Вес вдвое больше среднего, оба случая весов | Task 3 |
| Инъекция только в `yaroslavl`/`tsedenevo` | Task 4 |
| Фильтр столбика по параметру | Task 5 |
| Удаление слоя Радара, тест-страж | Task 6 |
| `deploy.yml` без публикации, коммит истории | Task 7 |
| Валидация числа моделей (12→13) | Task 4, шаг 5 |

**Найденные при самопроверке и исправленные расхождения:**

1. Исходная формула спеки `w_sensors = 2 / (N + 2)` с перенормировкой неверна
   для `relative_humidity_2m` и `pressure_msl`: этих переменных нет в
   `VERIFICATION_VARIABLES`, поэтому `weights_by_var` для них пуст, и
   перенормировка дала бы датчику вес одной модели вместо двойного. Заменено на
   `w_sensors = 2 × mean(веса моделей)` без перенормировки — веса используются
   как отношения, сумма не обязана равняться 1. Спека исправлена, Task 3
   покрывает оба случая тестами.
2. Подсчёт каналов температуры в спеке был 19, фактически 20 (из них 18
   физических датчиков). Исправлено в спеке.
3. В Task 4 число моделей для `yaroslavl`/`tsedenevo` меняется с 12 на 13,
   что может сломать существующие тесты. Вынесено в явный шаг 5 Task 4.

**Типы и имена согласованы:** `SENSOR_CODE`, `SENSOR_NAME`, `SENSOR_VARS`,
`SENSOR_LOCATIONS`, `apply_sensor_weights`, `load_sensor_model`,
`SENSOR_PARAMS`, `average_stations`, `load_history`, `record_history`,
`history_hour_value`, `trim_history`, `moscow_hour_key` — каждое определено в
одной задаче и используется в следующих под тем же именем. `history_hour_value`
(Task 2) и `_sensor_hour_value` (Task 4) намеренно дублируют логику: Task 2
живёт в `tools/collect_sensors.py`, Task 4 — в `meteo.py`, и связать эти модули
импортом значило бы сделать генератор сайта зависимым от paho.
