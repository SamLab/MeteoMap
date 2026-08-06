# Multi-location (3 города) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить переключение между Ярославлем, Балакирево и Цеденево по клику на название города в шапке, с данными в отдельных JSON на город.

**Architecture:** Backend (`meteo.py`) переводится с констант `LAT/LON` на список `LOCATIONS`; каждая модель фетчится одним батч-запросом на все города (Open-Meteo возвращает массив по городам — проверено), данные разбираются по городам, консенсус/верификация/payload считаются на город. Выход: лёгкий `index.html` со списком городов (`__CITIES__`) + `data/<slug>.json` на город. Frontend (`template.html`): `fetch('data/<slug>.json')` → `D=json` → `renderAll()`; селектор города в шапке, выбор в localStorage.

**Tech Stack:** Python 3.13, requests, pytest; статический HTML/JS (без сборки), Chart.js CDN; GitHub Pages + Actions.

## Global Constraints

- UI только русский, светлая тема, без новых CDN.
- В интерфейсе имена: «Ярославль», «Балакирево», «Цеденево» (как в `LOCATIONS`).
- Локации: Ярославль (57.63, 39.87), Балакирево (56.507, 38.846), Цеденево (57.533, 39.905). Все — Europe/Moscow.
- Деплой в этой сессии НЕ выполняется (пользователь проверит перед коммитом/пушем).
- Тесты: `& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests -m "not integration" -q` → ожидается 88 passed (без новых) / с новыми — больше, 2 deselected.
- `bot.php` НЕ коммитить (содержит живой токен).

---

### Task 1: Backend — список локаций и батчинг fetch

**Files:**
- Modify: `F:\Meteo\meteo.py:3-5` (константы), `meteo.py:117-154` (fetch-функции), `meteo.py:532-587` (`main()`)
- Test: `F:\Meteo\tests\test_locations.py` (new)

**Interfaces:**
- Consumes: существующие `fetch_model`, `fetch_yr`, `verify_models`, `assemble_consensus`, `build_payload`.
- Produces:
  - `LOCATIONS = [{"name", "slug", "lat", "lon"}, ...]` (3 города)
  - `fetch_model(code, endpoint, variables, days, lats="a,b", lons="x,y", timezone) -> list[dict]` (список ответов по городам; одиночный dict оборачивается в `[dict]`)
  - `build_payload(..., location: dict)` — имя города из параметра
  - `write_city_files(payload_by_city, template) -> None` — пишет `index.html` и `data/<slug>.json`

- [ ] **Step 1: Write failing tests** (`tests/test_locations.py`)

```python
import meteo


def test_fetch_model_batch_splits_by_city(monkeypatch):
    calls = {}

    def fake_request(url, params, timeout):
        calls["params"] = params
        return [{"latitude": 57.75, "hourly": {"time": ["t"], "temperature_2m": [1.0]}},
                {"latitude": 56.5, "hourly": {"time": ["t"], "temperature_2m": [5.0]}}]

    monkeypatch.setattr(meteo, "request_with_retry", fake_request)
    res = meteo.fetch_model("m", "forecast", ["temperature_2m"],
                            days=2, lats="57.63,56.507", lons="39.87,38.846")
    assert len(res) == 2
    assert res[0]["hourly"]["temperature_2m"] == [1.0]
    assert res[1]["hourly"]["temperature_2m"] == [5.0]
    assert calls["params"]["latitude"] == "57.63,56.507"
    assert calls["params"]["longitude"] == "39.87,38.846"


def test_fetch_model_wraps_single_response(monkeypatch):
    monkeypatch.setattr(meteo, "request_with_retry",
                        lambda *a, **k: {"latitude": 57.75, "hourly": {}})
    res = meteo.fetch_model("m", "forecast", ["temperature_2m"], lats="57.63", lons="39.87")
    assert isinstance(res, list) and len(res) == 1


def test_locations_have_unique_slugs():
    slugs = [loc["slug"] for loc in meteo.LOCATIONS]
    assert len(slugs) == len(set(slugs))
    assert "yaroslavl" in slugs
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests/test_locations.py -q`
Expected: FAIL (нет `LOCATIONS`, `fetch_model` без `lats`)

- [ ] **Step 3: Implement**

В `meteo.py` заменить строки 3-5:

```python
LOCATIONS = [
    {"name": "Ярославль", "slug": "yaroslavl", "lat": 57.63, "lon": 39.87},
    {"name": "Балакирево", "slug": "balakirevo", "lat": 56.507, "lon": 38.846},
    {"name": "Цеденево", "slug": "tsedenevo", "lat": 57.533, "lon": 39.905},
]
TIMEZONE = "Europe/Moscow"
FORECAST_DAYS = 16
```

`fetch_model` (заменить сигнатуру, строки 117-128):

```python
def fetch_model(code, endpoint, variables, days=FORECAST_DAYS,
                lats=None, lons=None, timezone="UTC"):
    lats = lats or ",".join(str(l["lat"]) for l in LOCATIONS)
    lons = lons or ",".join(str(l["lon"]) for l in LOCATIONS)
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
```

`fetch_historical_model` и `fetch_archive` — добавить параметры `lats/lons` с тем же фолбэком (батч), обернуть ответ в список (аналогично). `fetch_yr` — уже принимает `lat/lon`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests -m "not integration" -q`
Expected: PASS (старые 88 + новые)

- [ ] **Step 5: Commit**

```bash
git add meteo.py tests/test_locations.py
git commit -m "feat(backend): LOCATIONS list and batched fetch per city"
```

---

### Task 2: Backend — main() цикл по городам, файлы на город

**Files:**
- Modify: `F:\Meteo\meteo.py:467-519` (`build_payload`, `render`), `meteo.py:532-587` (`main()`)
- Test: `F:\Meteo\tests\test_render.py`, `F:\Meteo\tests\test_locations.py`

**Interfaces:**
- Consumes: `LOCATIONS`, батч-`fetch_model`, `fetch_yr(lat, lon)`, `verify_models`, `assemble_consensus`.
- Produces:
  - `build_payload(model_codes, model_names, hourly_by_model, daily_by_model, consensus, verification, generated_at, location) -> dict` (location: dict из LOCATIONS)
  - `render(template, payload) -> str` — подставляет `__CITIES__` (JSON список), без `__DATA__`-замены на город
  - `main()` — пишет `index.html` + `data/<slug>.json`

- [ ] **Step 1: Write failing tests**

В `tests/test_locations.py`:

```python
def test_build_payload_uses_location(tmp_path):
    hourly = {"a": {"time": ["h0"], "data": {"temperature_2m": [1.0]}}}
    consensus = {
        "time": ["h0"], "weighted": {"temperature_2m": [1.0]},
        "mean": {"temperature_2m": [1.0]}, "median": {"temperature_2m": [1.0]},
    }
    loc = {"name": "Балакирево", "slug": "balakirevo", "lat": 56.507, "lon": 38.846}
    p = meteo.build_payload(["a"], {"a": "A"}, hourly, {}, consensus, {},
                            "2026-08-06T12:00:00+03:00", loc)
    assert p["location"] == loc


def test_render_replaces_cities_placeholder():
    template = "<script id='cities'>__CITIES__</script>"
    html = meteo.render(template, {"location": {"name": "Ярославль"}, "generated_at": "x"})
    assert "__CITIES__" in html  # __CITIES__ остаётся, заменяется в render() ниже
    html2 = meteo.render(template.replace("__CITIES__", json.dumps(meteo.LOCATIONS)),
                         {"location": {"name": "Ярославль"}, "generated_at": "x"})
    assert "yaroslavl" in html2
```

(проверка полного `render` с `__CITIES__` идёт в Task 3 после правки шаблона)
```

В `tests/test_render.py` обновить `test_payload_contains_key_sections` — передать `location={"name": "Ярославль", "slug": "yaroslavl", "lat": 57.63, "lon": 39.87}`. Добавить в `tests/test_locations.py`:

```python
def test_render_replaces_cities_placeholder():
    template = "<script id='cities'>__CITIES__</script>"
    payload = {"location": {"name": "Ярославль"}, "generated_at": "2026-08-06T12:00:00+03:00"}
    html = meteo.render(template, payload)
    assert "__CITIES__" not in html
    assert '"slug": "yaroslavl"' in html
```

- [ ] **Step 2: Run to verify fail**

Run: `& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests/test_locations.py tests/test_render.py -q`
Expected: FAIL

- [ ] **Step 3: Implement**

`build_payload` (строки 467-506): сигнатура `..., generated_at, location`; строка 490 заменить на `"location": location`.

`render` (строки 509-519):

```python
def render(template, payload):
    html = template.replace(
        "__CITIES__", json.dumps(
            [{"name": l["name"], "slug": l["slug"], "lat": l["lat"], "lon": l["lon"]}
             for l in LOCATIONS], ensure_ascii=False))
    html = html.replace("__DATA__", json.dumps(payload, ensure_ascii=False))
    html = html.replace("__GENERATED_AT__", payload["generated_at"])
    html = html.replace("__CITY__", payload["location"]["name"])
    html = html.replace(
        "__ATTRIBUTION__",
        '<a href="https://open-meteo.com/">Weather data by Open-Meteo.com</a>',
    )
    return html
```

`main()` (строки 532-587) переписать: один батч-запрос на модель для всех городов, затем цикл по городам разбирает ответы по индексу:

```python
def main():
    generated_at = moscow_now_iso()
    model_codes = [c for c, _n, _e in FORECAST_MODELS]
    model_names = {c: n for c, n, _e in FORECAST_MODELS}

    # один батч-запрос на модель: ответ = список по городам
    raw_by_model = {}
    for code, _name, endpoint in FORECAST_MODELS:
        try:
            raw_by_model[code] = fetch_model(code, endpoint, HOURLY_VARIABLES,
                                             days=FORECAST_DAYS, timezone=TIMEZONE)
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
        weights_by_var = {
            v: make_weights(verification["7d"], v)
            for v in VERIFICATION_VARIABLES
        }
        try:
            yr_rows = fetch_yr(lat=loc["lat"], lon=loc["lon"])
        except Exception as exc:
            print(f"[warn] {YR_CODE} {loc['name']}: {exc}")
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
        payload_by_city[loc["slug"]] = build_payload(
            model_codes, model_names, hourly_by_model, daily_by_model,
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
```

Для верификации на город нужны обёртки `_city_hist`/`_city_arch`, которые внутри батч-запроса берут `resp[idx]`. Добавить выше `main()`:

```python
def _city_hist(loc):
    def f(code, start, end, variables):
        resp = fetch_historical_model(code, start, end, variables)
        return resp[LOCATIONS.index(loc)]
    return f

def _city_arch(loc):
    def f(start, end, variables):
        resp = fetch_archive(start, end, variables)
        return resp[LOCATIONS.index(loc)]
    return f
```

**Важно:** `index.html` содержит инлайн-данные первого города (Ярославль) через `__DATA__` — открытие без HTTP-сервера показывает Ярославль. Фронт при переключении грузит `data/<slug>.json`.

- [ ] **Step 4: Run to verify pass**

Run: `& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests -m "not integration" -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add meteo.py tests/test_locations.py tests/test_render.py
git commit -m "feat(backend): per-city consensus, payload, data/*.json output"
```

---

### Task 3: Frontend — селектор города и renderAll()

**Files:**
- Modify: `F:\Meteo\template.html` (шапка, `__CITIES__`, конец скрипта)
- Test: headless-проба (после Task 4)

**Interfaces:**
- Consumes: `__CITIES__` (JSON: [{name, slug, lat, lon}]), `__DATA__` (payload первого города), `data/<slug>.json` (payload любого города).
- Produces: `renderAll()`, `loadCity(slug)`, селектор в шапке.

- [ ] **Step 1: Header selector + data bootstrap**

В шапке (`template.html` ~строка 14, после `<h1>`):

```html
<h1>MeteoMap — <span class="citysel" id="citysel" title="Сменить город">Ярославль ▾</span></h1>
<ul id="citymenu" class="citymenu"></ul>
```

CSS (рядом с `.tabs`):

```css
.citysel{cursor:pointer;border-bottom:1px dashed var(--accent)}
.citymenu{display:none;position:absolute;z-index:50;background:var(--card);border:1px solid var(--line);border-radius:8px;list-style:none;padding:4px 0;box-shadow:0 4px 14px rgba(0,0,0,.12)}
.citymenu.open{display:block}
.citymenu li{padding:6px 14px;cursor:pointer;font-size:14px}
.citymenu li:hover{background:var(--sel)}
```

В начале `<script>` (заменить строку 204):

```js
const CITIES=JSON.parse(document.getElementById('cities').textContent);
let D=JSON.parse(document.getElementById('data').textContent);
const codes=D.model_codes, names=D.model_names;
```

Добавить функции после объявления `names`:

```js
function renderAll(){
  codes=D.model_codes; names=D.model_names;
  curIdx=Math.max(0,D.time.findIndex(t=>t>=curHour));
  document.title='MeteoMap — '+D.location.name;
  const g=document.getElementById('generated');
  if(g)g.textContent=D.generated_at;
  buildConditions(); buildWeatherNow(); buildWeatherHours();
  buildWeather10(); buildWeatherDetail(); buildWarnings();
  buildVarSel('varsel',setVar); buildVarSel('varsel2',v=>{cmpVar=v;buildCmpTable();},CHART_VARS.concat(['weather_code']));
  makeMainChart(); buildCmpTable(); buildMaeTables();
  const cs=document.getElementById('citysel');
  if(cs)cs.childNodes[0].textContent=D.location.name;
}
async function loadCity(slug){
  try{
    const r=await fetch('data/'+slug+'.json',{cache:'no-cache'});
    if(!r.ok)throw new Error('HTTP '+r.status);
    D=await r.json();
    renderAll();
  }catch(e){
    alert('Не удалось загрузить данные города: '+e.message);
  }
}
function setupCitySel(){
  const sel=document.getElementById('citysel');
  const menu=document.getElementById('citymenu');
  if(!sel||!menu)return;
  CITIES.forEach(c=>{
    const li=document.createElement('li');
    li.textContent=c.name;
    li.addEventListener('click',()=>{
      localStorage.setItem('city',c.slug);
      menu.classList.remove('open');
      loadCity(c.slug);
    });
    menu.appendChild(li);
  });
  sel.addEventListener('click',e=>{e.stopPropagation();menu.classList.toggle('open');});
  document.addEventListener('click',()=>menu.classList.remove('open'));
}
```

**Замечание:** `curHour` сейчас считается на строке ~250 от `D.time` — перенести его вычисление в `renderAll()` (пересчитывать при смене города). В коде выше `curIdx` пересчитывается в `renderAll`; `curHour` оставить как есть (время сейчас — общее для всех городов в МСК, ок).

- [ ] **Step 2: Replace bottom render calls**

Заменить строки 680-690:

```js
setupCitySel();
renderAll();
```

И удалить старый блок построчного вызова `buildXxx()`.

- [ ] **Step 3: `__CITIES__` + `__DATA__` в шаблоне**

Строка ~202: заменить

```html
<script id="cities" type="application/json">__CITIES__</script>
<script id="data" type="application/json">__DATA__</script>
```

(render() в Python оставляет `__DATA__`-замену на город, `__CITIES__` — список.)

- [ ] **Step 4: Commit**

```bash
git add template.html
git commit -m "feat(frontend): city selector, renderAll, loadCity fetch"
```

---

### Task 4: Dеплой-workflow + headless-проба через HTTP

**Files:**
- Modify: `F:\Meteo\.github\workflows\deploy.yml` (строка 38), `F:\Meteo\tools\headless_probe.py`
- Test: локальный прогон + проба

- [ ] **Step 1: Workflow копирует data/**

Заменить в `deploy.yml` строку 38:

```yaml
          cp index.html /tmp/ghpages/
          cp -r data /tmp/ghpages/
```

- [ ] **Step 2: headless_probe через HTTP**

Переписать `tools/headless_probe.py`, чтобы вместо `file://` поднимался локальный HTTP-сервер:

```python
import http.server, functools, os, subprocess, sys, tempfile, threading
import time, socketserver

def main():
    src = sys.argv[1]
    probe_js = sys.argv[2]
    out = sys.argv[3]
    html = open(src, encoding="utf-8").read()
    if os.path.isfile(probe_js):
        probe_js = open(probe_js, encoding="utf-8").read()
    wrapper = '<div id="probeout"></div>\n<script>\n' + probe_js + "\n</script>"
    page = html.replace("</body>", wrapper + "</body>")
    tmp = tempfile.mkdtemp(prefix="probe_")
    open(os.path.join(tmp, "index.html"), "w", encoding="utf-8").write(page)
    data_dir = os.path.join(os.path.dirname(os.path.abspath(src)), "data")
    if os.path.isdir(data_dir):
        subprocess.run(["cp", "-r", data_dir, tmp], shell=False,
                       capture_output=True, check=True)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                directory=tmp)
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as httpd:
        port = httpd.server_address[1]
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        edge = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        if not os.path.exists(edge):
            edge = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
        cmd = (f'"{edge}" --headless --disable-gpu --window-size=1366,900 '
               f'--virtual-time-budget=8000 --dump-dom "http://127.0.0.1:{port}/index.html"')
        res = subprocess.run(cmd, capture_output=True, shell=True)
        httpd.shutdown()
    raw = res.stdout.decode("utf-8", errors="replace")
    i = raw.find('<div id="probeout">')
    j = raw.find('<!--PROBE_END-->', i)
    if j < 0:
        j = raw.find("</div>", i)
    text = raw[i + len('<div id="probeout">'):j]
    open(out, "w", encoding="utf-8").write(text)
    print(text)

main()
```

- [ ] **Step 3: Probe script — переключение города**

`C:\Users\SamLab\AppData\Local\Temp\opencode\probe_city.js`:

```js
(async()=>{
try{
  await new Promise(r=>setTimeout(r,400));
  const sel=document.getElementById('citysel');
  const out=[];
  out.push('title='+document.title);
  out.push('citysel='+sel.childNodes[0].textContent);
  out.push('cities='+CITIES.map(c=>c.name).join('|'));
  sel.click();
  await new Promise(r=>setTimeout(r,200));
  const items=[...document.querySelectorAll('#citymenu li')].map(x=>x.textContent);
  out.push('menu='+items.join('|'));
  document.querySelectorAll('#citymenu li')[1].click();
  await new Promise(r=>setTimeout(r,800));
  out.push('after_click_title='+document.title);
  out.push('after_click_city='+sel.childNodes[0].textContent);
  out.push('temp_now='+D.weighted.temperature_2m[curIdx]);
  document.getElementById('probeout').innerHTML=out.join('<br>')+'<!--PROBE_END-->';
}catch(e){document.getElementById('probeout').innerHTML='ERR '+e.message+'<!--PROBE_END-->';}
})();
```

- [ ] **Step 4: Регенерировать и прогнать**

Run: `& "F:\Meteo\.venv\Scripts\python.exe" meteo.py 2>&1 | Select-Object -Last 2`
Run: `& "F:\Meteo\.venv\Scripts\python.exe" "F:\Meteo\tools\headless_probe.py" "F:\Meteo\index.html" "C:\Users\SamLab\AppData\Local\Temp\opencode\probe_city.js" "C:\Users\SamLab\AppData\Local\Temp\opencode\probe_city.txt"`
Expected: title и город меняются на Балакирево после клика; menu содержит 3 города.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/deploy.yml tools/headless_probe.py
git commit -m "chore: copy data/ in deploy workflow; headless probe over HTTP"
```

---

### Task 5: Полный прогон тестов и верификация

- [ ] **Step 1: Все тесты**

Run: `& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests -m "not integration" -q`
Expected: PASS (88 + новые, 2 deselected)

- [ ] **Step 2: Регенерация**

Run: `& "F:\Meteo\.venv\Scripts\python.exe" meteo.py 2>&1 | Select-Object -Last 3`
Expected: `[ok] index.html + 3 city json written` (могут быть `[warn]` 429 у ensemble — ок)

- [ ] **Step 3: Проверка файлов**

Run: `Get-ChildItem data | Select-Object Name,Length`
Expected: `balakirevo.json`, `tsedenevo.json`, `yaroslavl.json` (каждый ~300-600KB)

- [ ] **Step 4: Пробы**

Прогнать probe_city.js (см. Task 4) + старые пробы (CIN, scroll, parts) на переключённом городе.

- [ ] **Step 5: Отчёт пользователю**

Ничего не коммитить/пушить без явного «деплой». Составить сводку: что изменено, как проверить, что осталось.
