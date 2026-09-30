# METAR аэропорта Ярославля шестым датчиком — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить METAR аэропорта Ярославля (`UUDL`) как шестую равноправную станцию сети датчиков.

**Architecture:** Коллектор получает третий транспорт `metar` рядом с существующими `mqtt` и `http`. `collect_http` выбирает адаптер по полю `source`, а порог свежести становится полем станции `max_age_s` вместо общей константы. Ниже `collect()` код не меняется: `meteo.py`, веса, консенсус и виджеты транспорт не знают.

**Tech Stack:** Python 3 (stdlib + `requests` + `paho-mqtt`), pytest, JSON-конфиг, GitHub Actions.

## Global Constraints

- `temperature_2m` — единственный параметр сети. `SENSOR_PARAMS` расширять нельзя.
- Комментарии и docstrings на русском, в стиле существующего кода. Комментарий объясняет «почему», а не «что».
- Новое поле `max_age_s` необязательное; значение по умолчанию — существующая константа `HTTP_MAX_AGE_S` (900). Конфиг `yartemp` не меняется ни на строчку.
- Источник: `https://aviationweather.gov/api/data/metar?format=json&ids=UUDL&hours=1`, заголовок `User-Agent`, без `Referer`.
- `fetch_metar` не бросает исключений ни при каком ответе. Любой сбой — это «нет данных», а не падение прогона.
- ICAO-код — `UUDL` (Ярославль/Туношна, 57.561/40.157). Не `ULLK`: такого кода нет в каталоге NOAA.
- `meteo.py` не меняется ни в одной задаче.
- Бэкфилл истории за 30 суток не делается.
- В справку (`template.html`) не упоминается суточное расхождение аэропорта и городских станций — решение пользователя.
- Тесты запускаются интерпретатором проекта: `.venv\Scripts\python.exe -m pytest`. Системный `python` не содержит pytest.
- `git add` — только явные пути. Untracked-файлы (`tools/collect_narodmon.py`, `tests/test_narodmon.py`, `backups/`, `remote.git/`) в коммиты не попадают.
- `sensors_history.json` отслеживается git, но коммитит его только workflow `sensors`. Ни одна задача этого плана его не меняет и не коммитит: локальная копия расходится с CI, и коммит поверх неё затёр бы опубликованную историю.
- `tools/collect_sensors.py` целиком не запускать. Живой источник проверяется прямым вызовом `fetch_metar` — он сет ходит, но историю не пишет.

---

## File Structure

| Файл | Ответственность в этой задаче |
|---|---|
| `tools/collect_sensors.py` | Новый транспорт `metar`, адаптер `fetch_metar`, per-source порог свежести, валидация `max_age_s` |
| `tools/stations.json` | Шестая станция `uudl` |
| `tests/test_sensors.py` | Тесты обоих транспортов и обновлённого конфига |
| `tests/test_render.py` | Тесты новой текстуры справки |
| `template.html` | Справка: 5 → 6 станций, источник METAR |

Разбиение по задачам — по тому, что ревьюер может принять отдельно: транспорт и свежесть (ядро), затем конфиг, затем тексты.

---

### Task 1: Per-source порог свежести

Самый маленький кусок с самостоятельной ценностью: `max_age_s` нужен и сам по себе, потому что без него METAR протухал бы всегда.

**Files:**
- Modify: `tools/collect_sensors.py:42-51` (константы), `tools/collect_sensors.py:164-186` (`collect_http`)
- Test: `tests/test_sensors.py`

**Interfaces:**
- Consumes: `HTTP_MAX_AGE_S`, `HTTP_TIMEOUT_S`, `fetch_yartemp`, `http_stations` (всё уже существует)
- Produces: `station_max_age_s(station) -> int`; `collect_http` читает порог из поля `max_age_s` станции с откатом на `HTTP_MAX_AGE_S`

- [ ] **Step 1: Написать падающий тест**

Добавить в `tests/test_sensors.py` в конец файла:

```python
# --- порог свежести у каждой станции свой -------------------------------
# METAR обновляется раз в 30 минут, поэтому общий порог в 15 минут убил бы
# его полностью: станция молчала бы в каждом прогоне. Порог становится
# свойством станции, а не свойством транспорта.


def test_station_max_age_s_defaults_to_the_shared_constant():
    assert station_max_age_s({'id': 'a'}) == HTTP_MAX_AGE_S


def test_station_max_age_s_is_taken_from_the_station():
    assert station_max_age_s({'id': 'a', 'max_age_s': 2400}) == 2400


def test_station_without_max_age_s_keeps_the_old_freshness_behaviour(tmp_path, monkeypatch):
    """Станция без нового поля ведёт себя ровно как раньше: 15 минут."""
    now = 1790708310.0
    stations = [{'id': 'yt', 'name': 'Y', 'lat': 57.6, 'lon': 39.9,
                 'source': 'http', 'sensors': {'temperature_2m': YARTEMP_URL}}]
    cfg = tmp_path / 'st.json'
    cfg.write_text(json.dumps({'stations': stations}), encoding='utf-8')
    out = tmp_path / 'sensors.json'

    monkeypatch.setattr(cs.time, 'time', lambda: now)
    # чуть старше общей границы: станция обязана промолчать, как раньше
    monkeypatch.setattr(cs, 'fetch_yartemp',
                        lambda url, **kw: ('8.09', now - HTTP_MAX_AGE_S - 60))

    cs.run(client_factory=lambda *a, **kw: _FakeClient([]), config=cfg, out=out,
           window_s=0, history=str(tmp_path / 'h.json'))

    data = json.loads(out.read_text(encoding='utf-8'))
    assert data['stations'][0]['online'] is False
```

Добавить `station_max_age_s` в импорт на строке 7-20 того же файла:

```python
    moscow_now_ts,
    record_history,
    station_max_age_s,
    trim_history,
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `.venv\Scripts\python.exe -m pytest tests/test_sensors.py -k max_age_s -v`
Expected: ошибка `ImportError: cannot import name 'station_max_age_s'` — имя ещё не существует.

- [ ] **Step 3: Реализовать минимум**

В `tools/collect_sensors.py` после функции `http_stations` (строка 105) добавить:

```python
def station_max_age_s(station):
    """Порог свежести станции в секундах.

    Общий HTTP_MAX_AGE_S описывает yartemp, который обновляется раз в 5 минут.
    Источник с другим ритмом требует другого допуска: METAR выходит раз в 30
    минут, и при общем пороге в 15 минут он протухал бы в каждом прогоне,
    то есть не дал бы ни одного числа. Поле необязательное, поэтому станции
    без него сохраняют прежнее поведение.
    """
    return station.get('max_age_s', HTTP_MAX_AGE_S)
```

В `collect_http` заменить строки 182-183:

```python
            max_age_s = station_max_age_s(st)
            if now - reading_ts > max_age_s:
                continue
```

- [ ] **Step 4: Убедиться, что тесты проходят**

Run: `.venv\Scripts\python.exe -m pytest tests/test_sensors.py -v`
Expected: все PASS, включая `test_stale_yartemp_reading_is_not_injected` и `test_fresh_yartemp_reading_is_counted_like_an_mqtt_station` — поведение yartemp не изменилось.

- [ ] **Step 5: Закоммитить**

```bash
git add tools/collect_sensors.py tests/test_sensors.py
git commit -m "feat(sensors): let each station set its own freshness threshold"
```

---

### Task 2: Валидация `max_age_s` и третье значение `source`

**Files:**
- Modify: `tools/collect_sensors.py:42-45` (`VALID_SOURCES`), `tools/collect_sensors.py:296-341` (`load_stations`), `tools/collect_sensors.py:99-105` (`http_stations`)
- Test: `tests/test_sensors.py`

**Interfaces:**
- Consumes: `load_stations`, `http_stations`, `station_max_age_s` (Task 1)
- Produces: `VALID_SOURCES == ('mqtt', 'http', 'metar')`; `http_stations` возвращает станции с `source` из `('http', 'metar')`; `load_stations` отвергает неизвестный `source` и неположительный `max_age_s`

- [ ] **Step 1: Написать падающие тесты**

Добавить в `tests/test_sensors.py`:

```python
# --- третий транспорт: metar --------------------------------------------

METAR_URL = 'https://aviationweather.gov/api/data/metar?format=json&ids=UUDL&hours=1'


def test_metar_is_a_valid_source(tmp_path):
    stations = [{'id': 'uudl', 'name': 'A', 'lat': 57.561, 'lon': 40.157,
                 'source': 'metar', 'sensors': {'temperature_2m': 'UUDL'}}]
    cfg = tmp_path / 'st.json'
    cfg.write_text(json.dumps({'stations': stations}), encoding='utf-8')
    assert load_stations(cfg)[0]['source'] == 'metar'


def test_load_stations_rejects_non_positive_max_age(tmp_path):
    """Ноль или минус означали бы «отбрасывать всё», поэтому это ошибка конфига."""
    for bad in (0, -1):
        stations = [{'id': 'yt', 'name': 'Y', 'lat': 57.6, 'lon': 39.9,
                     'source': 'http', 'max_age_s': bad,
                     'sensors': {'temperature_2m': YARTEMP_URL}}]
        cfg = tmp_path / 'st.json'
        cfg.write_text(json.dumps({'stations': stations}), encoding='utf-8')
        with pytest.raises(ValueError, match='max_age_s'):
            load_stations(cfg)


def test_load_stations_rejects_non_numeric_max_age(tmp_path):
    stations = [{'id': 'yt', 'name': 'Y', 'lat': 57.6, 'lon': 39.9,
                 'source': 'http', 'max_age_s': 'half an hour',
                 'sensors': {'temperature_2m': YARTEMP_URL}}]
    cfg = tmp_path / 'st.json'
    cfg.write_text(json.dumps({'stations': stations}), encoding='utf-8')
    with pytest.raises(ValueError, match='max_age_s'):
        load_stations(cfg)


def test_metar_station_is_polled_over_the_network_not_mqtt():
    """Обе сетевые станции попадают в http_stations, mqtt-станции - нет."""
    stations = [
        {'id': 'a', 'sensors': {'temperature_2m': 'city/out/a'}},
        {'id': 'yt', 'source': 'http',
         'sensors': {'temperature_2m': YARTEMP_URL}},
        {'id': 'uudl', 'source': 'metar',
         'sensors': {'temperature_2m': 'UUDL'}},
    ]
    assert [st['id'] for st in http_stations(stations)] == ['yt', 'uudl']


def test_metar_station_is_never_subscribed_over_mqtt():
    """Токен UUDL - это не топик брокера: в подписку он попасть не должен."""
    stations = [
        {'id': 'a', 'sensors': {'temperature_2m': 'city/out/a'}},
        {'id': 'uudl', 'source': 'metar',
         'sensors': {'temperature_2m': 'UUDL'}},
    ]
    client = _FakeClient([('city/out/a', '20.4', False)])
    cs.collect(client, stations, 0)
    assert client.subs == ['city/out/a']
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `.venv\Scripts\python.exe -m pytest tests/test_sensors.py -k "metar or max_age" -v`
Expected: `test_metar_is_a_valid_source` и `test_metar_station_is_polled_over_the_network_not_mqtt` — FAIL (`source` не в `VALID_SOURCES`, станция не выбрана). Тесты на `max_age_s` — FAIL (валидации нет).

- [ ] **Step 3: Реализовать минимум**

В `tools/collect_sensors.py` заменить строку 45:

```python
VALID_SOURCES = ('mqtt', 'http', 'metar')
```

Заменить `http_stations` (строки 99-105):

```python
def http_stations(stations):
    """Станции, которые опрашиваются по сети, а не слушаются по MQTT.

    Их два вида: http разбирает ответ веб-страницы, metar - сводку аэропорта
    из JSON API. Оба опрашиваются, поэтому и живут в одной выборке; чем
    разбирать ответ, решает collect_http по полю source. Отсутствие поля
    означает mqtt, поэтому существующие станции в stations.json не меняются
    и не обязаны знать про этот выбор.
    """
    return [st for st in stations if st.get('source', 'mqtt') in ('http', 'metar')]
```

В `load_stations` после проверки `source` (строки 328-331) вставить:

```python
        if 'max_age_s' in st:
            raw_age = st['max_age_s']
            if isinstance(raw_age, bool) or not isinstance(raw_age, (int, float)):
                raise ValueError('station %r: max_age_s must be a number'
                                 % (sid,))
            if raw_age <= 0:
                raise ValueError('station %r: max_age_s must be positive: %s'
                                 % (sid, raw_age))
```

- [ ] **Step 4: Убедиться, что тесты проходят**

Run: `.venv\Scripts\python.exe -m pytest tests/test_sensors.py -v`
Expected: все PASS.

- [ ] **Step 5: Закоммитить**

```bash
git add tools/collect_sensors.py tests/test_sensors.py
git commit -m "feat(sensors): accept metar as a third station source"
```

---

### Task 3: Адаптер `fetch_metar`

**Files:**
- Modify: `tools/collect_sensors.py` (константы после строки 60; функции после `fetch_yartemp`, строка 161)
- Test: `tests/test_sensors.py`

**Interfaces:**
- Consumes: `SENSOR_PARAMS`, `HTTP_TIMEOUT_S`, существующие `_FakeSession` / `_FakeResponse` из `tests/test_sensors.py:867-890`
- Produces: `parse_metar_report_time(text) -> float | None`, `fetch_metar(url, timeout_s=HTTP_TIMEOUT_S, now=None, session=None) -> (str, float) | (None, None)` — значение строкой, метка наблюдения числом

- [ ] **Step 1: Написать падающий тест**

Добавить в `tests/test_sensors.py`:

```python
# --- METAR аэропорта: NOAA, JSON, раз в 30 минут --------------------------
# Ответ - JSON-массив сводок, свежая первая. Берётся temp как значение и
# reportTime как метка наблюдения: время отдачи ответа не годится, оно
# ничего не говорит о свежести показания.

# 2026-09-30T09:30:00Z = 12:30 МСК
METAR_REPORT_ISO = '2026-09-30T09:30:00.000Z'


def _metar_body(temp='16.0', report_time=METAR_REPORT_ISO):
    return json.dumps([{'icaoId': 'UUDL',
                        'temp': temp,
                        'reportTime': report_time,
                        'rawOb': 'UUDL 093000Z 09004MPS 060V110 9999 FEW045 16/09 Q1011'}])


def test_fetch_metar_takes_temperature_and_observation_time():
    """temp - значение, reportTime - метка наблюдения в unix-времени."""
    want_ts = datetime(2026, 9, 30, 9, 30, tzinfo=timezone.utc).timestamp()
    payload, reading_ts = fetch_metar(
        METAR_URL, now=want_ts, session=_FakeSession(_metar_body()))
    assert payload == '16.0'
    assert reading_ts == pytest.approx(want_ts)


def test_fetch_metar_sends_a_user_agent():
    """NOAA требует представиться; Referer не нужен и не шлётся."""
    session = _FakeSession(_metar_body())
    fetch_metar(METAR_URL, now=1.0, session=session)
    url, kw = session.calls[0]
    assert url == METAR_URL
    assert 'User-Agent' in kw['headers']
    assert 'Referer' not in kw['headers']


def test_fetch_metar_parses_report_time_without_milliseconds():
    """reportTime приходит с миллисекундами; datetime.fromisoformat их не ест."""
    ts = datetime(2026, 9, 30, 9, 30, tzinfo=timezone.utc).timestamp()
    payload, reading_ts = fetch_metar(
        METAR_URL, now=ts, session=_FakeSession(_metar_body()))
    assert reading_ts == pytest.approx(ts)


def test_fetch_metar_returns_none_on_empty_list():
    assert fetch_metar(METAR_URL, now=1.0,
                       session=_FakeSession('[]')) == (None, None)


def test_fetch_metar_returns_none_on_missing_temperature():
    body = json.dumps([{'icaoId': 'UUDL', 'reportTime': METAR_REPORT_ISO}])
    assert fetch_metar(METAR_URL, now=1.0,
                       session=_FakeSession(body)) == (None, None)


def test_fetch_metar_returns_none_on_missing_report_time():
    body = json.dumps([{'icaoId': 'UUDL', 'temp': '16.0'}])
    assert fetch_metar(METAR_URL, now=1.0,
                       session=_FakeSession(body)) == (None, None)


def test_fetch_metar_returns_none_on_unparsable_report_time():
    assert fetch_metar(
        METAR_URL, now=1.0,
        session=_FakeSession(_metar_body(report_time='вчера'))) == (None, None)


def test_fetch_metar_rejects_temperature_out_of_range():
    """За пределами физики значение не должно доходить до словарей."""
    assert fetch_metar(
        METAR_URL, now=1.0,
        session=_FakeSession(_metar_body(temp='99.0'))) == (None, None)


def test_fetch_metar_survives_html_instead_of_json():
    """Смена формата на сайте - тишина, а не падение публикации."""
    assert fetch_metar(
        METAR_URL, now=1.0,
        session=_FakeSession('<html>maintenance</html>')) == (None, None)


def test_fetch_metar_survives_network_error():
    assert fetch_metar(
        METAR_URL, now=1.0,
        session=_FakeSession(raises=OSError('connection reset'))) == (None, None)


def test_fetch_metar_survives_http_error():
    assert fetch_metar(
        METAR_URL, now=1.0,
        session=_FakeSession('oops', status=503)) == (None, None)
```

Добавить `fetch_metar` в импорт на строке 7-20 того же файла (рядом с `fetch_yartemp`):

```python
    average_stations,
    fetch_metar,
    fetch_yartemp,
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `.venv\Scripts\python.exe -m pytest tests/test_sensors.py -k metar -v`
Expected: `ImportError: cannot import name 'fetch_metar'`.

- [ ] **Step 3: Реализовать минимум**

В `tools/collect_sensors.py` после строки 60 (`YARTEMP_REFERER`) добавить константу:

```python
# Идентификация, которую NOAA требует от автоматических запросов. Без неё
# ответ может прийти 403. Referer не шлём: источник его не требует и он
# ничего не значит для API.
NOAA_USER_AGENT = 'meteomap-yaroslavl/1.0 (github.com/meteomap)'
```

После `fetch_yartemp` (конец на строке 161) добавить две функции:

```python
def parse_metar_report_time(text):
    """Разбирает reportTime NOAA в unix-время. None - если разобрать нельзя.

    Строка приходит с миллисекундами ('2026-09-30T09:30:00.000Z'), которые
    datetime.fromisoformat не принимает, поэтому хвост отсекается до разбора.
    Метка наблюдения нужна и для бакета часа, и для проверки свежести,
    поэтому неразобранное время означает отказ от показания.
    """
    if not isinstance(text, str) or not text.strip():
        return None
    cleaned = text.strip()
    if cleaned.endswith('Z'):
        cleaned = cleaned[:-1]
    if '.' in cleaned:
        cleaned = cleaned.split('.', 1)[0]
    try:
        moment = datetime.fromisoformat(cleaned)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.timestamp()


def fetch_metar(url, timeout_s=HTTP_TIMEOUT_S, now=None, session=None):
    """Опрашивает METAR-сводку аэропорта. Возвращает (payload, reading_ts).

    Ответ - JSON-массив, свежая сводка первая. Берутся ровно два поля: temp
    как значение и reportTime как метка наблюдения. Время отдачи ответа не
    годится: между сводками проходит полчаса, и подставь мы его вместо
    reportTime, прогон объявил бы получасовую давность свежим замером.

    Не бросает исключений ни при каком ответе - публикация sensors_history.json
    не должна зависеть от чужого сервиса. Смена формата, HTML вместо JSON,
    обрыв сети - всё это «нет данных», станция просто молчит.
    """
    now = time.time() if now is None else now
    if session is None:
        import requests

        session = requests.Session()
    try:
        response = session.get(url, timeout=timeout_s,
                               headers={'User-Agent': NOAA_USER_AGENT})
        response.raise_for_status()
        text = response.text
    except Exception:
        return None, None

    if not text:
        return None, None
    try:
        report = json.loads(text)
    except ValueError:
        return None, None
    if not isinstance(report, list) or not report:
        return None, None
    newest = report[0]
    if not isinstance(newest, dict):
        return None, None

    reading_ts = parse_metar_report_time(newest.get('reportTime'))
    if reading_ts is None:
        return None, None

    # Температура проверяется здесь, а не в validate(): validate() живёт в
    # общем снимке и не знает, откуда пришли данные. Мусор или физически
    # невозможное число не должны попасть в бакет истории.
    temp = newest.get('temp')
    if temp is None or isinstance(temp, bool):
        return None, None
    try:
        number = float(temp)
    except (TypeError, ValueError):
        return None, None
    low, high = SENSOR_PARAMS['temperature_2m']
    if not (low <= number <= high):
        return None, None
    # Значение возвращается строкой, как у fetch_yartemp, чтобы build_snapshot
    # не различал транспорты.
    return str(number), reading_ts
```

- [ ] **Step 4: Убедиться, что тесты проходят**

Run: `.venv\Scripts\python.exe -m pytest tests/test_sensors.py -v`
Expected: все PASS.

- [ ] **Step 5: Закоммитить**

```bash
git add tools/collect_sensors.py tests/test_sensors.py
git commit -m "feat(sensors): read temperature from NOAA METAR reports"
```

---

### Task 4: Развести адаптеры в `collect_http`

Пока `collect_http` зовёт `fetch_yartemp` для всех сетевых станций, METAR не заработает. Это чистое соединение уже написанного.

**Files:**
- Modify: `tools/collect_sensors.py:164-186`
- Test: `tests/test_sensors.py`

**Interfaces:**
- Consumes: `fetch_yartemp`, `fetch_metar`, `station_max_age_s`, `http_stations` (Task 1-3)
- Produces: `station_fetcher(station) -> callable`; `collect_http(received, seen, stations, now, timeout_s=HTTP_TIMEOUT_S)` — выбор адаптера изнутри, параметр `fetcher` удалён: разбор определяется транспортом станции, а не внешним переопределением

- [ ] **Step 1: Написать падающий тест**

Добавить в `tests/test_sensors.py`:

```python
def test_collect_http_picks_the_adapter_matching_the_source(tmp_path, monkeypatch):
    """Каждая сетевая станция получает свой разбор ответа, не чужой."""
    now = 1790708310.0
    stations = [
        {'id': 'yt', 'name': 'Y', 'lat': 57.6, 'lon': 39.9, 'source': 'http',
         'sensors': {'temperature_2m': YARTEMP_URL}},
        {'id': 'uudl', 'name': 'A', 'lat': 57.561, 'lon': 40.157,
         'source': 'metar', 'max_age_s': 2400,
         'sensors': {'temperature_2m': 'UUDL'}},
    ]
    cfg = tmp_path / 'st.json'
    cfg.write_text(json.dumps({'stations': stations}), encoding='utf-8')
    out = tmp_path / 'sensors.json'
    metar_ts = now - 600

    seen_by = {}

    def fake_yartemp(url, **kw):
        seen_by['yartemp'] = url
        return '8.090', now - 60

    def fake_metar(url, **kw):
        seen_by['metar'] = url
        return '16.0', metar_ts

    monkeypatch.setattr(cs.time, 'time', lambda: now)
    monkeypatch.setattr(cs, 'fetch_yartemp', fake_yartemp)
    monkeypatch.setattr(cs, 'fetch_metar', fake_metar)

    cs.run(client_factory=lambda *a, **kw: _FakeClient([]), config=cfg, out=out,
           window_s=0, history=str(tmp_path / 'h.json'))

    # каждый адаптер вызван только для своей станции
    assert seen_by == {'yartemp': YARTEMP_URL, 'metar': 'UUDL'}
    data = json.loads(out.read_text(encoding='utf-8'))
    by_id = {st['id']: st for st in data['stations']}
    assert by_id['uudl']['values']['temperature_2m'] == pytest.approx(16.0)
    assert by_id['yt']['values']['temperature_2m'] == pytest.approx(8.09)


def test_fresh_metar_reading_lands_in_the_hour_of_the_observation(tmp_path, monkeypatch):
    """Бакет берётся от reportTime, а не от часа прогона.

    Прогон в 13:05 МСК, а сам замер сделан в 12:30. Замер обязан лечь в бакет
    12:00, иначе подпись на сайте сказала бы «обновилось в 13:00» про
    показание получасовой давности.
    """
    run_ts = datetime(2026, 9, 30, 10, 5, tzinfo=timezone.utc).timestamp()  # 13:05 МСК
    obs_ts = datetime(2026, 9, 30, 9, 30, tzinfo=timezone.utc).timestamp()  # 12:30 МСК
    stations = [{'id': 'uudl', 'name': 'A', 'lat': 57.561, 'lon': 40.157,
                 'source': 'metar', 'max_age_s': 2400,
                 'sensors': {'temperature_2m': 'UUDL'}}]
    cfg = tmp_path / 'st.json'
    cfg.write_text(json.dumps({'stations': stations}), encoding='utf-8')
    out = tmp_path / 'sensors.json'
    hist = tmp_path / 'h.json'

    monkeypatch.setattr(cs.time, 'time', lambda: run_ts)
    monkeypatch.setattr(cs, 'fetch_metar', lambda url, **kw: ('16.0', obs_ts))

    cs.run(client_factory=lambda *a, **kw: _FakeClient([]), config=cfg, out=out,
           window_s=0, history=str(hist))

    hours = json.loads(hist.read_text(encoding='utf-8'))['hours']
    assert list(hours) == ['2026-09-30T12:00']


def test_stale_metar_reading_is_not_injected(tmp_path, monkeypatch):
    """Сводка старше собственного порога станции не попадает в среднее."""
    now = 1790708310.0
    stations = [{'id': 'uudl', 'name': 'A', 'lat': 57.561, 'lon': 40.157,
                 'source': 'metar', 'max_age_s': 2400,
                 'sensors': {'temperature_2m': 'UUDL'}}]
    cfg = tmp_path / 'st.json'
    cfg.write_text(json.dumps({'stations': stations}), encoding='utf-8')
    out = tmp_path / 'sensors.json'

    monkeypatch.setattr(cs.time, 'time', lambda: now)
    monkeypatch.setattr(cs, 'fetch_metar',
                        lambda url, **kw: ('16.0', now - 2400 - 60))

    cs.run(client_factory=lambda *a, **kw: _FakeClient([]), config=cfg, out=out,
           window_s=0, history=str(tmp_path / 'h.json'))

    data = json.loads(out.read_text(encoding='utf-8'))
    assert data['stations'][0]['online'] is False
    assert data['stations'][0]['values'] == {}


def test_metar_freshness_uses_its_own_threshold_not_the_shared_one(tmp_path, monkeypatch):
    """Полчаса - протухло для yartemp, но в пределах допуска METAR."""
    now = 1790708310.0
    stations = [
        {'id': 'yt', 'name': 'Y', 'lat': 57.6, 'lon': 39.9, 'source': 'http',
         'sensors': {'temperature_2m': YARTEMP_URL}},
        {'id': 'uudl', 'name': 'A', 'lat': 57.561, 'lon': 40.157,
         'source': 'metar', 'max_age_s': 2400,
         'sensors': {'temperature_2m': 'UUDL'}},
    ]
    cfg = tmp_path / 'st.json'
    cfg.write_text(json.dumps({'stations': stations}), encoding='utf-8')
    out = tmp_path / 'sensors.json'
    aged = now - 2000

    monkeypatch.setattr(cs.time, 'time', lambda: now)
    monkeypatch.setattr(cs, 'fetch_yartemp', lambda url, **kw: ('8.090', aged))
    monkeypatch.setattr(cs, 'fetch_metar', lambda url, **kw: ('16.0', aged))

    cs.run(client_factory=lambda *a, **kw: _FakeClient([]), config=cfg, out=out,
           window_s=0, history=str(tmp_path / 'h.json'))

    data = json.loads(out.read_text(encoding='utf-8'))
    by_id = {st['id']: st for st in data['stations']}
    assert by_id['yt']['online'] is False
    assert by_id['uudl']['online'] is True


def test_failing_metar_does_not_break_other_stations(tmp_path, monkeypatch):
    """Отвал аэропорта не должен обнулять ни MQTT, ни yartemp."""
    now = 1790708310.0
    stations = [
        {'id': 'a', 'name': 'A', 'lat': 57.0, 'lon': 39.0,
         'sensors': {'temperature_2m': 'city/out/a'}},
        {'id': 'yt', 'name': 'Y', 'lat': 57.6, 'lon': 39.9, 'source': 'http',
         'sensors': {'temperature_2m': YARTEMP_URL}},
        {'id': 'uudl', 'name': 'Air', 'lat': 57.561, 'lon': 40.157,
         'source': 'metar', 'max_age_s': 2400,
         'sensors': {'temperature_2m': 'UUDL'}},
    ]
    cfg = tmp_path / 'st.json'
    cfg.write_text(json.dumps({'stations': stations}), encoding='utf-8')
    out = tmp_path / 'sensors.json'
    fake = _FakeClient([('city/out/a', '20.4', False)])

    monkeypatch.setattr(cs.time, 'time', lambda: now)
    monkeypatch.setattr(cs, 'fetch_yartemp', lambda url, **kw: ('8.090', now - 60))
    monkeypatch.setattr(cs, 'fetch_metar', lambda url, **kw: (None, None))

    cs.run(client_factory=lambda *a, **kw: fake, config=cfg, out=out, window_s=0,
           history=str(tmp_path / 'h.json'))

    data = json.loads(out.read_text(encoding='utf-8'))
    by_id = {st['id']: st for st in data['stations']}
    assert by_id['a']['values']['temperature_2m'] == pytest.approx(20.4)
    assert by_id['yt']['online'] is True
    assert by_id['uudl']['online'] is False
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `.venv\Scripts\python.exe -m pytest tests/test_sensors.py -k metar -v`
Expected: `test_collect_http_picks_the_adapter_matching_the_source` — FAIL с `AssertionError: {'yartemp': ...}` без ключа `metar`, потому что `fetch_metar` никто не зовёт.

- [ ] **Step 3: Реализовать минимум**

В `tools/collect_sensors.py` перед `collect_http` (строка 164) добавить:

```python
def station_fetcher(station):
    """Адаптер разбора ответа для сетевой станции.

    Транспорт один - HTTP, но формат ответа разный: yartemp отдаёт строку с
    полями через ';', аэропорт отдаёт JSON-сводку. Разбор выбирается здесь,
    чтобы collect_http не ветвился по source на каждую станцию.
    """
    if station.get('source') == 'metar':
        return fetch_metar
    return fetch_yartemp
```

Заменить сигнатуру `collect_http` (строка 164), убрав параметр `fetcher`:

```python
def collect_http(received, seen, stations, now, timeout_s=HTTP_TIMEOUT_S):
```

Заменить docstring `collect_http`, первая строка которого сейчас говорит «Опрашивает HTTP-станции», на:

```
    """Опрашивает сетевые станции и кладёт ответы в те же словари, что и MQTT.

    Ключом служит URL из sensors - ровно то, что лежит в конфиге, поэтому
    build_snapshot не различает транспорты и не меняется. Протухший или
    непригодный ответ в словари не попадает: станция станет offline сама.
    """
```

Заменить тело `collect_http` (строки 171-186) на:

```python
    for st in http_stations(stations):
        fetcher = station_fetcher(st)
        for param, url in st['sensors'].items():
            payload, reading_ts = fetcher(url, now=now, timeout_s=timeout_s)
            if payload is None:
                continue
            # Часы источника могут спешить на несколько секунд. Метка из
            # будущего прошла бы проверку свежести и выглядела бы свежее
            # прогона, поэтому она прижимается к времени опроса.
            if reading_ts > now:
                reading_ts = now
            max_age_s = station_max_age_s(st)
            if now - reading_ts > max_age_s:
                continue
            received[url] = payload
            seen[url] = reading_ts
            break
```

- [ ] **Step 4: Убедиться, что тесты проходят**

Run: `.venv\Scripts\python.exe -m pytest tests/test_sensors.py -v`
Expected: все PASS.

- [ ] **Step 5: Закоммитить**

```bash
git add tools/collect_sensors.py tests/test_sensors.py
git commit -m "feat(sensors): route each network station to its own parser"
```

---

### Task 5: Станция UUDL в конфиге

**Files:**
- Modify: `tools/stations.json:43-52`
- Modify: `tests/test_sensors.py:1042-1052`

**Interfaces:**
- Consumes: `load_stations` с `source: "metar"` и `max_age_s` (Task 1-2)
- Produces: `stations.json` с шестью станциями; тест конфига переписан

- [ ] **Step 1: Написать падающий тест**

Заменить `test_repository_config_has_five_stations_with_one_http` в `tests/test_sensors.py` на:

```python
def test_repository_config_has_six_stations_with_two_network_sources():
    with open(cs.DEFAULT_CONFIG, encoding='utf-8') as f:
        settings = json.load(f)
    stations = settings['stations']
    assert len(stations) == 6
    http = [st for st in stations if st.get('source') == 'http']
    metar = [st for st in stations if st.get('source') == 'metar']
    assert len(http) == 1
    assert http[0]['id'] == 'yartemp'
    assert len(metar) == 1
    assert metar[0]['id'] == 'uudl'
    # у всех станций только температура, как и у MQTT-станций
    for st in stations:
        assert list(st['sensors']) == ['temperature_2m']


def test_metar_station_in_config_points_at_uudl_with_its_own_threshold():
    """Код аэропорта и его собственный порог закреплены конфигом.

    UUDL - аэропорт Ярославля; ULLK в каталоге NOAA не существует, и первая
    попытка работы с ним молча дала ложный вывод, что станция не отдаёт METAR.
    """
    with open(cs.DEFAULT_CONFIG, encoding='utf-8') as f:
        settings = json.load(f)
    metar = [st for st in settings['stations'] if st.get('source') == 'metar'][0]
    assert metar['sensors']['temperature_2m'] == 'UUDL'
    # 30-минутная периодичность источника плюс запас
    assert metar['max_age_s'] == 2400
    # координаты аэропорта из каталога NOAA, а не координаты соседней станции
    assert (metar['lat'], metar['lon']) == (57.561, 40.157)
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `.venv\Scripts\python.exe -m pytest tests/test_sensors.py -k repository_config -v`
Expected: FAIL — `assert 5 == 6`.

- [ ] **Step 3: Добавить станцию в конфиг**

В `tools/stations.json` заменить закрывающую часть массива станций (строки 43-52) на:

```json
    {
      "id": "yartemp",
      "name": "Ярославль, yartemp.com",
      "lat": 57.62,
      "lon": 39.92,
      "source": "http",
      "sensors": {
        "temperature_2m": "https://yartemp.com/webdata/"
      }
    },
    {
      "id": "uudl",
      "name": "Ярославль, аэропорт (METAR)",
      "lat": 57.561,
      "lon": 40.157,
      "source": "metar",
      "max_age_s": 2400,
      "sensors": {
        "temperature_2m": "UUDL"
      }
    }
  ]
}
```

- [ ] **Step 4: Убедиться, что тесты проходят**

Run: `.venv\Scripts\python.exe -m pytest tests/test_sensors.py -v`
Expected: все PASS, включая `test_repository_stations_config_is_valid` и `test_repository_stations_config_window_covers_the_slowest_station`.

- [ ] **Step 5: Проверить на настоящем источнике, не трогая историю**

Run: `.venv\Scripts\python.exe -c "import json,time; from tools import collect_sensors as cs; print(cs.fetch_metar('https://aviationweather.gov/api/data/metar?format=json&ids=UUDL&hours=1', now=time.time()))"`

Expected: пара вида `('16.0', 1759...)` — температура строкой и метка наблюдения
числом. Если `(None, None)`, запустить ещё раз: скорее всего, это ограничение
частоты запросов NOAA.

**Не запускать `tools/collect_sensors.py` целиком.** Файл `sensors_history.json`
отслеживается git, и локальный прогон перезапишет его расходящейся с CI копией.
Проверка живого адаптера через прямой вызов безопасна: история не пишется.

- [ ] **Step 6: Закоммитить**

```bash
git add tools/stations.json tests/test_sensors.py
git commit -m "feat(sensors): add UUDL METAR as sixth Yaroslavl station"
```

---

### Task 6: Справка на сайте

**Files:**
- Modify: `template.html:242`, `template.html:247`, `template.html:250`, `template.html:256`
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: реальный состав станции из Task 5
- Produces: справка, где названы шесть станций и источник METAR

- [ ] **Step 1: Написать падающие тесты**

Добавить в `tests/test_render.py` рядом с `test_help_credits_yartemp_as_a_station_source`:

```python
def test_help_lists_six_stations_and_credits_noaa_metar():
    """В справке шесть станций, аэропорт назван, источник данных указан.

    NOAA отдаёт открытые данные без требования атрибуции, но ссылка нужна
    пользователю, чтобы проверить, откуда взялось число.
    """
    with open('template.html', encoding='utf-8') as f:
        template = f.read()
    assert 'Станций шесть' in template
    assert 'https://aviationweather.gov/' in template
    assert 'METAR' in template
    assert 'раз в 30 минут' in template


def test_help_does_not_promise_a_five_station_network():
    """Старое «пять станций» должно уйти вместе со сменой состава сети."""
    with open('template.html', encoding='utf-8') as f:
        template = f.read()
    assert 'Станций пять' not in template
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `.venv\Scripts\python.exe -m pytest tests/test_render.py -k help -v`
Expected: FAIL — `'Станций шесть' not found`.

- [ ] **Step 3: Обновить справку**

В `template.html` заменить строку 242 на:

```html
    <p>Собственная сеть метеостанций — единственный источник на сайте, который не прогнозирует, а меряет. Он есть только у Ярославля и Цеденево; у остальных городов такого источника нет. Станций шесть, все в Ярославле: четыре из сети <b>yar.gorod76.ru</b> по MQTT, независимый датчик <a href="https://yartemp.com/" target="_blank" rel="noopener">YarTemp</a> по HTTP и аэропорт по сводкам METAR.</p>
```

В `template.html` в пункте про молчание станции (строка 247) заменить фрагмент:

```html
Показание YarTemp отбрасывается, если оно старше 15 минут: там в снимке есть время самого замера.
```

на:

```html
Показание YarTemp отбрасывается, если оно старше 15 минут: там в снимке есть время самого замера. METAR выходит раз в 30 минут, поэтому его порог — 40 минут.
```

После пункта про YarTemp (строка 250) добавить новый:

```html
      <li><b>METAR аэропорта.</b> Температура в аэропорту Ярославля (Туношна) берётся из сводок METAR — стандартной погодной сводки, которую составляет метеослужба и передаёт <a href="https://aviationweather.gov/" target="_blank" rel="noopener">aviationweather.gov</a>, открытый сервис NOAA. Сводки выходят раз в 30 минут и измеряются с точностью до целого градуса, тогда как остальные станции дают десятые доли.</li>
```

В `template.html` в пункте «Станции, чьи показания идут в среднее и минимум» (строка 256) заменить:

```html
четыре станции в Ярославле из сети <b>yar.gorod76.ru</b> (Пенаты, ул. Фрунзе, Восток, Берег) и независимый датчик <a href="https://yartemp.com/" target="_blank" rel="noopener">YarTemp</a> в самом Ярославле. YarTemp обновляет данные раз в 5 минут, и его чтение отбрасывается, если оно старше 15 минут, — тогда в этом часе остаётся среднее по остальным станциям. У Цеденево своих станций нет, «датчики» там — те же пять.
```

на:

```html
четыре станции в Ярославле из сети <b>yar.gorod76.ru</b> (Пенаты, ул. Фрунзе, Восток, Берег), независимый датчик <a href="https://yartemp.com/" target="_blank" rel="noopener">YarTemp</a> в самом Ярославле и аэропорт по сводкам METAR. YarTemp обновляет данные раз в 5 минут, и его чтение отбрасывается, если оно старше 15 минут, — тогда в этом часе остаётся среднее по остальным станциям. METAR выходит раз в 30 минут, его порог — 40 минут. У Цеденево своих станций нет, «датчики» там — те же шесть.
```

- [ ] **Step 4: Убедиться, что тесты проходят**

Run: `.venv\Scripts\python.exe -m pytest tests/test_render.py -v`
Expected: все PASS.

- [ ] **Step 5: Прогнать весь набор**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: все PASS, ни одного падения.

- [ ] **Step 6: Закоммитить**

```bash
git add template.html tests/test_render.py
git commit -m "docs(help): list the airport METAR as the sixth station"
```

---

### Task 7: Принять работу

**Files:**
- Файлы не меняются. Только проверки.

**Interfaces:**
- Consumes: всё из Task 1-6
- Produces: подтверждение, что фича работает на настоящих данных

- [ ] **Step 1: Убедиться, что рабочее дерево чистое**

Run: `git status --short`
Expected: только untracked-файлы, которые были до задачи (`backups/`, `remote.git/`, `tools/collect_narodmon.py`, `tests/test_narodmon.py`, старые планы и спеки). Ни одного изменённого отслеживаемого файла.

- [ ] **Step 2: Прогнать адаптер на живом источнике**

Run: `.venv\Scripts\python.exe -c "import json,time; from tools import collect_sensors as cs; stations=cs.load_stations(cs.DEFAULT_CONFIG); st=[s for s in stations if s.get('source')=='metar'][0]; p,ts=cs.fetch_metar(st['sensors']['temperature_2m'], now=time.time()); print(p, ts, int(time.time()-ts))"`

Expected: температура строкой, метка числом, возраст меньше `2400` — то есть
сводка не старше собственного порога станции.

**Не запускать `tools/collect_sensors.py` целиком.** `sensors_history.json`
отслеживается git, а локальная копия уже расходится с той, что коммитит CI;
полный прогон перезаписал бы файл и в следующем коммите продвинул бы в
историю мусор. Живой коллектор всё равно отработает в workflow `sensors`.

- [ ] **Step 3: Проверить, что бакет пришёл в час наблюдения**

Запустить workflow `sensors` вручную и дождаться его коммита, затем посмотреть
`git log -1 --stat -- sensors_history.json` и открыть добавленный бакет: в
`hours` должен появиться ключ `uudl`, а `stations.uudl.temperature_2m` —
список из одного числа. Ключ бакета должен совпадать с часом METAR, а не с
часом прогона. Если не совпадает, вернуться к Task 4 Step 1.

- [ ] **Step 4: Отправить в main и задеплоить**

```bash
git push origin main
```

Дождаться workflow `deploy`, затем проверить живую страницу: раздел «Датчики» называет шесть станций, надстрочная цифра у колонки «Датчик» для свежих часов показывает ⁶.

- [ ] **Step 5: Сообщить результат**

Пользователю: номера коммитов, номер прогона deploy, и отдельно — фактический `age_s` METAR, чтобы он сам увидел ритм 30 минут.