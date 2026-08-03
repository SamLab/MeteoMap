# Вкладка «Погода» — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить вкладку «Погода» (первая, открывается по умолчанию) с обзором погоды для непрофессионалов: текущие условия, почасовой прогноз на 48 часов, прогноз на 10 дней и подробный 10-дневный прогноз по частям суток. Все числа — взвешенный консенсус.

**Architecture:** Python (`meteo.py`) расширяет горизонт до 10 дней и дневные данные (вероятность осадков, восход/закат). Все 4 блока вкладки строит JS в `template.html` из `D.weighted` (почасовой консенсус) и `D.daily`/`D.daily_time` (дневной консенсус). Новые карточки-контейнеры добавляются в панель `#tab-weather`, словари WMO/румбов — в JS. Проверка — pytest для Python-части и headless-зонды Edge для JS-части.

**Tech Stack:** Python 3.13, `requests`, `pytest`. Chart.js 4.4.1 CDN. Edge headless для проб. Без новых зависимостей.

## Global Constraints

- Python 3.13; прогон тестов: `pytest tests/ -m "not integration" -q` (ожидание: 48 passed + новые).
- UI только русский, светлая тема, эмодзи для иконок погоды, без новых CDN/зависимостей.
- `FORECAST_DAYS=10` — график и таблица сравнения становятся 10-дневными автоматически (код не трогаем).
- Восход/закат/вероятность осадков — данные Open-Meteo; `pressure_msl` в payload уже в мм рт. ст.
- Единый источник названий дней/месяцев — существующие `DAY_NAMES`, `MONTH_NAMES` в `template.html`.
- WMO-коды и румбы — словари в JS (`WCODE`, `COMPASS`/`COMPASS_FULL`).
- Кириллица в консоли Windows искажается → все скрипты-пробы сохранять в UTF-8 файлы и запускать с `$env:PYTHONIOENCODING="utf-8"`.
- После регенерации `python meteo.py` пишет `index.html` (gitignored) — его и пробуем.

---

### Task 1: Горизонт 10 дней и новые дневные переменные (meteo.py)

**Files:**
- Modify: `meteo.py:6` (`FORECAST_DAYS`)
- Modify: `meteo.py:33-36` (`DAILY_VARIABLES`)
- Modify: `meteo.py:316-325` (`build_payload`, обработка строк `sunrise`/`sunset`)
- Test: `tests/test_config.py`
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: существующую `build_payload`, `daily_by_model`, `mean`.
- Produces: `DAILY_VARIABLES` теперь содержит `precipitation_probability_max`, `sunrise`, `sunset`; `payload["daily"]["sunrise"]`/`["sunset"]` — списки строк ISO (время Европы/Москвы) из первой модели, у которой они есть; `payload["daily"]["precipitation_probability_max"]` — список чисел (средний консенсус).

- [ ] **Step 1: Написать падающие тесты**

В `tests/test_config.py` добавить:

```python
def test_forecast_days_is_ten():
    assert meteo.FORECAST_DAYS == 10
```

В `tests/test_render.py` расширить хелпер `_payload()` (поля `daily`):

```python
    daily = {
        "a": {"time": ["d0"], "temperature_2m_max": [5.0]},
        "b": {"time": ["d0"], "temperature_2m_max": [7.0]},
    }
```
→ заменить на:

```python
    daily = {
        "a": {"time": ["d0"], "temperature_2m_max": [5.0],
              "precipitation_probability_max": [10.0],
              "sunrise": ["2026-08-03T04:19:00"],
              "sunset": ["2026-08-03T20:33:00"]},
        "b": {"time": ["d0"], "temperature_2m_max": [7.0],
              "precipitation_probability_max": [30.0],
              "sunrise": ["2026-08-03T04:20:00"],
              "sunset": ["2026-08-03T20:34:00"]},
    }
```

И добавить новые тесты:

```python
def test_daily_contains_new_variables():
    p = _payload()
    assert p["daily"]["precipitation_probability_max"] == [20.0]
    assert p["daily"]["sunrise"] == ["2026-08-03T04:19:00"]
    assert p["daily"]["sunset"] == ["2026-08-03T20:33:00"]


def test_daily_string_fields_take_first_model():
    p = _payload()
    # строки берутся из первой модели с данными, а не усредняются
    assert p["daily"]["sunrise"][0] == "2026-08-03T04:19:00"
    assert isinstance(p["daily"]["sunrise"][0], str)


def test_daily_time_passthrough():
    hourly = {"a": {"time": ["h0"], "data": {"temperature_2m": [1.0]}}}
    consensus = {
        "time": ["h0"],
        "weighted": {"temperature_2m": [1.0]},
        "mean": {"temperature_2m": [1.0]},
        "median": {"temperature_2m": [1.0]},
    }
    daily = {"a": {"time": ["2026-08-03", "2026-08-04"], "temperature_2m_max": [5.0, 6.0]}}
    p = meteo.build_payload(
        ["a"], {"a": "A"}, hourly, daily, consensus, {},
        "2026-08-03T12:00:00+03:00",
    )
    assert p["daily_time"] == ["2026-08-03", "2026-08-04"]
    assert p["daily"]["temperature_2m_max"] == [5.0, 6.0]
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `pytest tests/test_config.py::test_forecast_days_is_ten tests/test_render.py::test_daily_contains_new_variables tests/test_render.py::test_daily_time_passthrough -q`
Expected: FAIL (FORECAST_DAYS ещё 7; `sunrise`/`sunset` отсутствуют в payload).

- [ ] **Step 3: Реализовать изменения в meteo.py**

`meteo.py:6`:

```python
FORECAST_DAYS = 10
```

`meteo.py:33-36`:

```python
DAILY_VARIABLES = [
    "temperature_2m_max", "temperature_2m_min", "precipitation_sum",
    "wind_speed_10m_max", "sunshine_duration",
    "precipitation_probability_max", "sunrise", "sunset",
]
```

В `build_payload` заменить цикл построения `daily_consensus` (строки 318–325):

```python
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
```

- [ ] **Step 4: Прогнать тесты**

Run: `pytest tests/ -m "not integration" -q`
Expected: PASS (48 passed + 4 новых). Падение `test_daily_string_fields_take_first_model` проверяет именно поведение «первая модель», а не усреднение.

- [ ] **Step 5: Коммит**

```bash
git add meteo.py tests/test_config.py tests/test_render.py
git commit -m "feat: 10-day horizon and daily precipitation probability, sunrise, sunset"
```

---

### Task 2: Вкладка «Погода» — каркас, активна по умолчанию

**Files:**
- Modify: `template.html` (кнопки вкладок, панель `#tab-weather`, CSS, JS-список вкладок)

**Interfaces:**
- Consumes: `D` (payload), существующую структуру вкладок.
- Produces: панель `#tab-weather` с четырьмя пустыми контейнерами: `#weather-now`, `#weather-hours`, `#weather-10`, `#weather-detail`. Список вкладок JS: `['weather','forecast','compare','accuracy','help']`. По умолчанию активна `weather`.

- [ ] **Step 1: Добавить кнопку и панель**

В `.tabs` (строка ~68) — кнопку «Погода» первой:

```html
<div class="tabs">
  <button class="active" data-tab="weather">Погода</button>
  <button data-tab="forecast">Прогноз</button>
  <button data-tab="compare">Сравнение</button>
  <button data-tab="accuracy">Точность</button>
  <button data-tab="help">Справка</button>
</div>
```

Убрать `active` у `#tab-forecast` и вставить панель перед ней:

```html
<div id="tab-weather" class="panel active">
  <div class="card"><h3 class="tstab">Сейчас</h3><div id="weather-now"></div></div>
  <div class="card"><h3 class="tstab">По часам</h3><div class="hours" id="weather-hours"></div></div>
  <div class="card"><h3 class="tstab">На 10 дней</h3><div id="weather-10"></div></div>
  <div class="card"><h3 class="tstab">Подробно на 10 дней</h3><div id="weather-detail"></div></div>
</div>
<div id="tab-forecast" class="panel">
```

- [ ] **Step 2: CSS**

В `<style>` после строки `#tab-help.active{overflow:auto}` (строка ~23) добавить:

```css
#tab-weather.active{overflow:auto}
#tab-weather .card{flex:none}
```

- [ ] **Step 3: JS-список вкладок**

Заменить в обработчике клика по вкладкам (строка ~157):

```js
['forecast','compare','accuracy','help'].forEach(...)
```
на:
```js
['weather','forecast','compare','accuracy','help'].forEach(...)
```

- [ ] **Step 4: Проба (headless)**

Создать файл `tools/headless_probe.py`:

```python
import os
import subprocess
import sys
import tempfile

def main():
    src = sys.argv[1]      # path to index.html (regenerated)
    probe_js = sys.argv[2] # JS, выполняется после загрузки страницы
    out = sys.argv[3]      # path to output .txt (UTF-8)
    html = open(src, encoding="utf-8").read()
    wrapper = (
        '<div id="probeout"></div>\n<script>\n' + probe_js + "\n</script>"
    )
    page = html.replace("</body>", wrapper + "</body>")
    tmp = os.path.join(tempfile.gettempdir(), "probe_page.html")
    open(tmp, "w", encoding="utf-8").write(page)
    edge = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    if not os.path.exists(edge):
        edge = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
    cmd = (
        f'"{edge}" --headless --disable-gpu --window-size=1366,900 '
        f'--virtual-time-budget=8000 --dump-dom "file:///{tmp}"'
    )
    res = subprocess.run(cmd, capture_output=True, shell=True)
    raw = res.stdout.decode("utf-8", errors="replace")
    i = raw.find('<div id="probeout">')
    j = raw.find("</div>", i)
    text = raw[i + len('<div id="probeout">'):j]
    open(out, "w", encoding="utf-8").write(text)
    print(text)

main()
```

Затем:

```bash
.\.venv\Scripts\python.exe meteo.py
$env:PYTHONIOENCODING="utf-8"
& ".\.venv\Scripts\python.exe" tools\headless_probe.py index.html "addEventListener('load',function(){setTimeout(function(){var b=document.querySelector('.tabs button.active');var p=document.querySelector('.panel.active');document.getElementById('probeout').textContent='tab='+(b?b.dataset.tab:'none')+' panel='+(p?p.id:'none')+' cont='+(document.getElementById('weather-hours')?'ok':'missing');},2000);});" C:\Users\SamLab\AppData\Local\Temp\opencode\t2.txt
```

Expected: `tab=weather panel=tab-weather cont=ok`

- [ ] **Step 5: Коммит**

```bash
git add template.html tools/headless_probe.py
git commit -m "feat: weather tab skeleton, active by default"
```

---

### Task 3: Словари WMO/румбов и блок «Сейчас»

**Files:**
- Modify: `template.html` (JS-словари, `buildWeatherNow`, CSS)

**Interfaces:**
- Consumes: `D.weighted` (почасовой консенсус), `D.daily.sunrise/sunset`, `D.generated_at`, `curIdx`, `DAY_NAMES`, `MONTH_NAMES`, существующий `fmt`.
- Produces: глобальные `WCODE`, `rumbShort`, `rumbFull`, `temp`, `num`, `buildWeatherNow()`. Заполняет `#weather-now`.

- [ ] **Step 1: Словари и хелперы**

Вставить после `const fmtTime=...` (около строки 142):

```js
const temp=v=>v==null?'—':(Math.round(v)>0?'+':'')+Math.round(v)+'°';
const num=v=>v==null||v===undefined?'—':Math.round(v);
const WCODE={
0:['Ясно','☀️'],1:['В основном ясно','🌤️'],2:['Переменная облачность','⛅'],3:['Пасмурно','☁️'],
45:['Туман','🌫️'],48:['Изморозь','🌫️'],
51:['Небольшая морось','🌦️'],53:['Морось','🌦️'],55:['Сильная морось','🌧️'],
56:['Ледяная морось','🌧️'],57:['Ледяная морось','🌧️'],
61:['Небольшой дождь','🌦️'],63:['Дождь','🌧️'],65:['Сильный дождь','🌧️'],
66:['Ледяной дождь','🌧️'],67:['Ледяной дождь','🌧️'],
71:['Небольшой снег','🌨️'],73:['Снег','❄️'],75:['Сильный снег','❄️'],77:['Снежные зерна','❄️'],
80:['Небольшой ливень','🌧️'],81:['Ливень','🌧️'],82:['Сильный ливень','⛈️'],
85:['Снегопад','🌨️'],86:['Снегопад','🌨️'],
95:['Гроза','⛈️'],96:['Гроза с градом','⛈️'],99:['Гроза с градом','⛈️']};
const wcode=c=>WCODE[c]||['—',''];
const COMPASS=['С','СВ','В','ЮВ','Ю','ЮЗ','З','СЗ'];
const COMPASS_FULL=['северный','северо-восточный','восточный','юго-восточный','южный','юго-западный','западный','северо-западный'];
const rumbShort=deg=>deg==null?'—':COMPASS[Math.round(deg/45)%8];
const rumbFull=deg=>deg==null?'—':COMPASS_FULL[Math.round(deg/45)%8];
```

- [ ] **Step 2: CSS блока «Сейчас»**

В `<style>` добавить:

```css
.wnow{display:flex;align-items:center;gap:28px;flex-wrap:wrap;padding:4px 2px}
.wbig{font-size:52px;font-weight:700}
.wcond{font-size:17px;margin-top:2px}
.wfeel{font-size:13px;color:var(--muted)}
.wdet{display:flex;gap:18px;flex-wrap:wrap;font-size:12px}
.wd .wdv{font-weight:600}
.wd .wdl{color:var(--muted);font-size:11px}
```

- [ ] **Step 3: Функция buildWeatherNow**

Вставить рядом с `buildConditions()` (около строки ~190):

```js
function buildWeatherNow(){
  const w=D.weighted;
  const [wtext,we]=wcode(w.weather_code?.[curIdx]);
  const sr=(D.daily.sunrise?.[0]||'').slice(11,16)||'—';
  const ss=(D.daily.sunset?.[0]||'').slice(11,16)||'—';
  let dl='—';
  if(D.daily.sunrise?.[0]&&D.daily.sunset?.[0]){
    const ms=new Date(D.daily.sunset[0])-new Date(D.daily.sunrise[0]);
    if(!isNaN(ms))dl=Math.floor(ms/3600000)+' ч '+Math.round((ms%3600000)/60000)+' мин';
  }
  const wind=w.wind_speed_10m?.[curIdx];
  const dir=w.wind_direction_10m?.[curIdx];
  const det=[
    ['Ветер',wind==null?'—':num(wind)+' м/с, '+rumbShort(dir)],
    ['Давление',num(w.pressure_msl?.[curIdx])+' мм рт. ст.'],
    ['Влажность',num(w.relative_humidity_2m?.[curIdx])+'%'],
    ['Восход / закат',sr+' / '+ss],
    ['Долгота дня',dl],
    ['Обновлено',(D.generated_at||'').slice(11,16)]
  ];
  document.getElementById('weather-now').innerHTML=
    '<div class="wnow"><div class="wmain">'+we+' <span class="wbig">'+temp(w.temperature_2m?.[curIdx])+'</span>'+
    '<div class="wfeel">Ощущается как '+temp(w.apparent_temperature?.[curIdx])+'</div>'+
    '<div class="wcond">'+wtext+'</div></div>'+
    '<div class="wdet">'+det.map(x=>'<div class="wd"><div class="wdv">'+x[1]+'</div><div class="wdl">'+x[0]+'</div></div>').join('')+'</div></div>';
}
```

- [ ] **Step 4: Вызов + проба**

Добавить внизу (после `buildConditions();`):

```js
buildWeatherNow();
```

Проба:

```bash
.\.venv\Scripts\python.exe meteo.py
& ".\.venv\Scripts\python.exe" tools\headless_probe.py index.html "addEventListener('load',function(){setTimeout(function(){var h=document.getElementById('weather-now').textContent;var out='len='+h.length+' hasDeg='+(h.indexOf('°')>=0)+' hasSun='+(/\/\d\d:\d\d/.test(h));document.getElementById('probeout').textContent=out;},2000);});" C:\Users\SamLab\AppData\Local\Temp\opencode\t3.txt
```

Expected: `len>`0 `hasDeg=true` `hasSun=true`

- [ ] **Step 5: Коммит**

```bash
git add template.html
git commit -m "feat: current conditions block with weather icons and details"
```

---

### Task 4: Блок «По часам» (48 часов)

**Files:**
- Modify: `template.html` (CSS `.hours`, `buildWeatherHours`, вызов)

**Interfaces:**
- Consumes: `D.time`, `D.weighted` (`weather_code`, `temperature_2m`, `precipitation_probability`), `curIdx`, `wcode`, `temp`, `num`.
- Produces: `buildWeatherHours()` — заполняет `#weather-hours` ячейками на 48 часов от `curIdx`.

- [ ] **Step 1: CSS**

```css
.hours{display:flex;overflow-x:auto;padding:4px 0}
.hour{flex:none;width:64px;text-align:center;font-size:12px;padding:4px 2px;border-right:1px solid var(--line)}
.hour .ht{color:var(--muted);font-size:11px}
.hour .he{font-size:18px;line-height:1.3}
.hour .htemp{font-weight:600;font-size:14px}
.hour .hpp{color:#1976d2;font-size:11px;min-height:14px}
```

- [ ] **Step 2: buildWeatherHours**

```js
function buildWeatherHours(){
  const w=D.weighted;
  const start=curIdx;
  document.getElementById('weather-hours').innerHTML=
    D.time.slice(start,start+48).map((t,i)=>{
      const j=start+i;
      const [wtext,we]=wcode(w.weather_code?.[j]);
      const pp=w.precipitation_probability?.[j];
      return '<div class="hour"><div class="ht">'+t.slice(11,16)+'</div>'+
        '<div class="he">'+we+'</div><div class="htemp">'+temp(w.temperature_2m?.[j])+'</div>'+
        '<div class="hpp">'+(pp>0?num(pp)+'%':'&nbsp;')+'</div></div>';
    }).join('');
}
```

- [ ] **Step 3: Вызов + проба**

Добавить после `buildWeatherNow();`:

```js
buildWeatherHours();
```

Проба:

```bash
.\.venv\Scripts\python.exe meteo.py
& ".\.venv\Scripts\python.exe" tools\headless_probe.py index.html "addEventListener('load',function(){setTimeout(function(){var hs=document.querySelectorAll('#weather-hours .hour');document.getElementById('probeout').textContent='cells='+hs.length+' first='+hs[0].querySelector('.ht').textContent;},2000);});" C:\Users\SamLab\AppData\Local\Temp\opencode\t4.txt
```

Expected: `cells=48 first=` (первый час = текущий час `HH:MM`).

- [ ] **Step 4: Коммит**

```bash
git add template.html
git commit -m "feat: hourly strip for next 48 hours"
```

---

### Task 5: Блок «На 10 дней»

**Files:**
- Modify: `template.html` (CSS `.d10row` и т.п., `buildWeather10`, вызов)

**Interfaces:**
- Consumes: `D.daily_time`, `D.daily` (`temperature_2m_min/max`, `precipitation_probability_max`), `D.weighted.weather_code` в 15:00 каждого дня, `DOW_S`, `MONTH_NAMES`, `wcode`, `temp`, `num`.
- Produces: `buildWeather10()` — заполняет `#weather-10`.

- [ ] **Step 1: CSS + массив коротких дней недели**

CSS:

```css
.d10row{display:grid;grid-template-columns:100px 1fr 70px 190px;align-items:center;gap:8px;padding:9px 0;border-bottom:1px solid var(--line);font-size:13px}
.d10day{color:var(--muted)}
.d10pp{color:#1976d2}
.d10n{color:var(--muted)}
```

JS (рядом с `DAY_NAMES`):

```js
const DOW_S=['Вс','Пн','Вт','Ср','Чт','Пт','Сб'];
```

- [ ] **Step 2: buildWeather10**

```js
function buildWeather10(){
  const dt=D.daily_time||[];
  document.getElementById('weather-10').innerHTML=dt.map((day,di)=>{
    const idx=D.time.findIndex(t=>t.slice(0,10)===day&&t.slice(11,13)==='15');
    const [wtext,we]=idx<0?['','']:wcode(D.weighted.weather_code?.[idx]);
    const pp=D.daily.precipitation_probability_max?.[di];
    const tmin=D.daily.temperature_2m_min?.[di];
    const tmax=D.daily.temperature_2m_max?.[di];
    const d=new Date(day);
    return '<div class="d10row"><div class="d10day">'+DOW_S[d.getDay()]+', '+d.getDate()+' '+MONTH_NAMES[d.getMonth()].slice(0,3)+'</div>'+
      '<div class="d10cond">'+we+' '+wtext+'</div>'+
      '<div class="d10pp">'+(pp>0?num(pp)+'%':'')+'</div>'+
      '<div class="d10t"><span class="d10n">ночью '+temp(tmin)+'</span> / днём '+temp(tmax)+'</div></div>';
  }).join('');
}
```

- [ ] **Step 3: Вызов + проба**

Добавить после `buildWeatherHours();`:

```js
buildWeather10();
```

Проба:

```bash
.\.venv\Scripts\python.exe meteo.py
& ".\.venv\Scripts\python.exe" tools\headless_probe.py index.html "addEventListener('load',function(){setTimeout(function(){var r=document.querySelectorAll('#weather-10 .d10row');document.getElementById('probeout').textContent='rows='+r.length+' first='+r[0].querySelector('.d10day').textContent;},2000);});" C:\Users\SamLab\AppData\Local\Temp\opencode\t5.txt
```

Expected: `rows=10 first=` (вида `Пн, 3 авг`).

- [ ] **Step 4: Коммит**

```bash
git add template.html
git commit -m "feat: 10-day forecast list"
```

---

### Task 6: Блок «Подробно на 10 дней» (части суток)

**Files:**
- Modify: `template.html` (CSS `.dparts`, `buildWeatherDetail`, вызов)

**Interfaces:**
- Consumes: `D.daily_time`, `D.daily.sunrise/sunset`, `D.weighted` в часы 03/09/15/21, `DAY_NAMES`, `MONTH_NAMES`, `temp`, `num`, `rumbFull`.
- Produces: `buildWeatherDetail()` — заполняет `#weather-detail`.

- [ ] **Step 1: CSS**

```css
.dhead{font-size:14px;font-weight:600;margin:12px 0 6px}
.dparts{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
.dpart{background:var(--sel);border:1px solid var(--line);border-radius:8px;padding:8px 10px;font-size:12px}
.dpart .pt{color:var(--muted);font-size:11px;margin-bottom:2px}
.dpart .ptemp{font-size:17px;font-weight:600}
.dpart .pw,.dpart .ppr,.dpart .phu{margin-top:2px}
.dsun{font-size:12px;color:var(--muted);margin-top:6px}
```

- [ ] **Step 2: buildWeatherDetail**

```js
const PARTS=[['ночь','03'],['утро','09'],['день','15'],['вечер','21']];
function partVal(day,hr,field){
  const idx=D.time.findIndex(t=>t.slice(0,10)===day&&t.slice(11,13)===hr);
  return idx>=0?D.weighted[field]?.[idx]:null;
}
function buildWeatherDetail(){
  const dt=D.daily_time||[];
  document.getElementById('weather-detail').innerHTML=dt.map((day,di)=>{
    const d=new Date(day);
    const sr=(D.daily.sunrise?.[di]||'').slice(11,16)||'—';
    const ss=(D.daily.sunset?.[di]||'').slice(11,16)||'—';
    let dl='—';
    if(D.daily.sunrise?.[di]&&D.daily.sunset?.[di]){
      const ms=new Date(D.daily.sunset[di])-new Date(D.daily.sunrise[di]);
      if(!isNaN(ms))dl=Math.floor(ms/3600000)+' ч '+Math.round((ms%3600000)/60000)+' мин';
    }
    const cells=PARTS.map(x=>{
      const t=partVal(day,x[1],'temperature_2m');
      const ws=partVal(day,x[1],'wind_speed_10m');
      const wd=partVal(day,x[1],'wind_direction_10m');
      const pr=partVal(day,x[1],'pressure_msl');
      const hu=partVal(day,x[1],'relative_humidity_2m');
      return '<div class="dpart"><div class="pt">'+x[0]+'</div>'+
        '<div class="ptemp">'+temp(t)+'</div>'+
        '<div class="pw">'+(ws==null?'—':num(ws)+' м/с, '+rumbFull(wd))+'</div>'+
        '<div class="ppr">'+(pr==null?'—':num(pr)+' мм')+'</div>'+
        '<div class="phu">'+(hu==null?'—':num(hu)+'%')+'</div></div>';
    }).join('');
    return '<div class="dhead">'+DAY_NAMES[d.getDay()]+', '+d.getDate()+' '+MONTH_NAMES[d.getMonth()]+'</div>'+
      '<div class="dparts">'+cells+'</div>'+
      '<div class="dsun">Восход: '+sr+' · Закат: '+ss+' · Долгота дня: '+dl+'</div>';
  }).join('');
}
```

- [ ] **Step 3: Вызов + проба**

Добавить после `buildWeather10();`:

```js
buildWeatherDetail();
```

Проба:

```bash
.\.venv\Scripts\python.exe meteo.py
& ".\.venv\Scripts\python.exe" tools\headless_probe.py index.html "addEventListener('load',function(){setTimeout(function(){var heads=document.querySelectorAll('#weather-detail .dhead');var parts=document.querySelectorAll('#weather-detail .dpart');document.getElementById('probeout').textContent='days='+heads.length+' parts='+parts.length+' firstHead='+heads[0].textContent;},2000);});" C:\Users\SamLab\AppData\Local\Temp\opencode\t6.txt
```

Expected: `days=10 parts=40 firstHead=` (вида `Понедельник, 3 августа`).

- [ ] **Step 4: Коммит**

```bash
git add template.html
git commit -m "feat: detailed 10-day forecast by parts of day"
```

---

### Task 7: Справка и финальная верификация

**Files:**
- Modify: `template.html` (блок `#tab-help`)

**Interfaces:**
- Consumes: текущий текст Справки.
- Produces: обновлённый текст Справки (описание вкладки «Погода», горизонт 10 дней).

- [ ] **Step 1: Обновить Справку**

В `#tab-help`:

1. В разделе «Прогноз» заменить первый абзац:

```html
<p>Вкладка открывается по умолчанию: здесь текущая погода и прогноз на 7 дней вперёд по всем моделям.</p>
```
на:
```html
<p>Подробная почасовая вкладка: прогноз на 10 дней вперёд по всем моделям.</p>
```

2. Перед разделом «Прогноз» добавить раздел «Погода»:

```html
<h2>Погода</h2>
<p>Открывается по умолчанию: обзор погоды для непрофессионалов. Все числа — взвешенный консенсус (единый прогноз всех моделей с учётом их точности).</p>
<ul>
  <li><b>Сейчас</b> — температура, ощущается, состояние погоды, ветер, давление, влажность, восход/закат, долгота дня.</li>
  <li><b>По часам</b> — следующие 48 часов: время, иконка, температура, вероятность осадков.</li>
  <li><b>На 10 дней</b> — день, состояние погоды, вероятность осадков, ночная и дневная температуры.</li>
  <li><b>Подробно на 10 дней</b> — по частям суток (ночь/утро/день/вечер): температура, ветер, давление, влажность; внизу — восход/закат и долгота дня.</li>
</ul>
```

- [ ] **Step 2: Полный прогон**

```bash
.\.venv\Scripts\python.exe -m pytest tests/ -m "not integration" -q
```
Expected: все PASS.

```bash
.\.venv\Scripts\python.exe meteo.py
```
Expected: `[ok] index.html written; models=... hours=240`

Проба всех блоков:

```bash
& ".\.venv\Scripts\python.exe" tools\headless_probe.py index.html "addEventListener('load',function(){setTimeout(function(){var o='hours='+document.querySelectorAll('#weather-hours .hour').length+' rows10='+document.querySelectorAll('#weather-10 .d10row').length+' parts='+document.querySelectorAll('#weather-detail .dpart').length+' now='+(document.getElementById('weather-now').textContent.length>0);document.getElementById('probeout').textContent=o;},2000);});" C:\Users\SamLab\AppData\Local\Temp\opencode\t7.txt
```

Expected: `hours=48 rows10=10 parts=40 now=true`

Дополнительно проверить, что вкладка по умолчанию — «Погода» и переключение на «Прогноз» работает (клик по кнопке):

```bash
& ".\.venv\Scripts\python.exe" tools\headless_probe.py index.html "addEventListener('load',function(){setTimeout(function(){var b=document.querySelector('.tabs button[data-tab=forecast]');b.click();var o=(document.getElementById('tab-forecast').className.indexOf('active')>=0)&&(document.getElementById('tab-weather').className.indexOf('active')<0)?'switch=ok':'switch=fail';document.getElementById('probeout').textContent=o;},2000);});" C:\Users\SamLab\AppData\Local\Temp\opencode\t7b.txt
```

Expected: `switch=ok`

- [ ] **Step 3: Коммит**

```bash
git add template.html
git commit -m "docs: update help for weather tab and 10-day horizon"
```

- [ ] **Step 4: Деплой**

```bash
git push origin main
$id = gh run list --workflow=deploy.yml --limit 1 --json databaseId --jq '.[0].databaseId'
gh run watch $id --exit-status
```
Expected: `success`. После — повторная headless-проба live-страницы (скачать `https://samlab.github.io/MeteoMap/` в файл, прогнать `tools/headless_probe.py`).
