# Слой спутниковой облачности (NASA GIBS) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить на вкладку «Спутник» (`nowcast.html`) отдельный переключаемый слой спутниковой облачности из NASA GIBS (MODIS TrueColor), чтобы облака были видны всегда, в т.ч. в сухую погоду.

**Architecture:** Раздельно: (1) утилита `gibs_tile_url` в `tools/nowcast.py` + юнит-тесты; (2) клиентский слой `L.tileLayer` GIBS + кнопка-тумблер «Облачность» в `nowcast_template.html` + тест-маркер; (3) пересборка `nowcast.html`, полный прогон и интеграционная проверка. GIBS отдаёт данные только на zoom 9 → используем `L.tileLayer(..., {minNativeZoom:9, maxNativeZoom:9})`, чтобы Leaflet сам подзагружал z9-тайлы и масштабировал их под текущий зум.

**Tech Stack:** Python 3.13 (pytest), Leaflet 1.6.0 (уже инлайнится в HTML билдером), шаблоны `nowcast_template.html`, билдер `tools/build_radar.py`, источника: HTTPS NASA GIBS.

## Global Constraints

- Без ключей/токенов/регистрации. CORS источника открыт (`Access-Control-Allow-Origin: *`), проверено.
- НЕ менять: `radar.html`, `radar_template.html`, вкладку «Радар», `NowcastLayer` (наукастинг ГМЦ), слои молний.
- Источник данных — строго z=9; URL-формат:
  `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/MODIS_Terra_CorrectedReflectance_TrueColor/default/{YYYY-MM-DD}/GoogleMapsCompatible_Level9/9/{y}/{x}.jpg`
- Снимок дневной (TrueColor); ночью слой тёмный/пустой — это ожидаемое поведение, не ошибка.
- Python-команды в этом окружении (Windows PowerShell 5.1): `& "F:\Meteo\.venv\Scripts\python.exe" ...`. Не вставлять `$` в inline-PowerShell; скрипты писать в файлы.
- Текущее состояние тестов: 190 passed, 2 deselected. Цель — не сломать.

---

### Task 1: Утилита `gibs_tile_url` в `tools/nowcast.py`

**Files:**
- Modify: `F:\Meteo\tools\nowcast.py` (добавить константы и функцию в конец файла)
- Test: `F:\Meteo\tests\test_nowcast.py` (добавить тесты)

**Interfaces:**
- Consumes: ничего (расширяет существующий модуль).
- Produces: `nowcast.GIBS_BASE`, `nowcast.GIBS_PRODUCT`, `nowcast.GIBS_MATRIX`, `nowcast.gibs_tile_url(x, y, date) -> str`.

- [ ] **Step 1: Write the failing test**

Add to `F:\Meteo\tests\test_nowcast.py` (append at the end):

```python
def test_gibs_constants():
    assert "earthdata.nasa.gov" in nowcast.GIBS_BASE
    assert nowcast.GIBS_PRODUCT == "MODIS_Terra_CorrectedReflectance_TrueColor"
    assert nowcast.GIBS_MATRIX == "GoogleMapsCompatible_Level9"


def test_gibs_tile_url_builds_known_good():
    url = nowcast.gibs_tile_url(35, 22, "2026-09-03")
    assert url == (
        "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/"
        "MODIS_Terra_CorrectedReflectance_TrueColor/default/2026-09-03/"
        "GoogleMapsCompatible_Level9/9/22/35.jpg"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests/test_nowcast.py -q`
Expected: FAIL — `AttributeError: module 'tools.nowcast' has no attribute 'GIBS_BASE'`.

- [ ] **Step 3: Write minimal implementation**

Append to `F:\Meteo\tools\nowcast.py`:

```python
GIBS_BASE = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/"
GIBS_PRODUCT = "MODIS_Terra_CorrectedReflectance_TrueColor"
GIBS_MATRIX = "GoogleMapsCompatible_Level9"


def gibs_tile_url(x, y, date):
    """URL тайла NASA GIBS. z фиксирован на 9 (250m); date — 'YYYY-MM-DD' (UTC)."""
    return "{}{}/default/{}/{}/9/{}/{}.jpg".format(
        GIBS_BASE, GIBS_PRODUCT, date, GIBS_MATRIX, y, x
    )
```

- [ ] **Step 4: Run the test suite for this file**

Run: `& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests/test_nowcast.py -q`
Expected: PASS (5 tests: 3 existing + 2 new).

- [ ] **Step 5: Commit**

```bash
git add tools/nowcast.py tests/test_nowcast.py
git commit -m "feat(sputnik): GIBS tile url helper"
```

---

### Task 2: Слой облачности GIBS в `nowcast_template.html`

**Files:**
- Modify: `F:\Meteo\nowcast_template.html` (CSS ~27-29, кнопка ~54, JS ~80 и ~88-99)
- Test: `F:\Meteo\tests\test_build.py` (добавить тест-маркер)

**Interfaces:**
- Consumes: `nowcast.GIBS_*` (только как справочник URL — клиент строит URL сам; точный формат взят из Task 1).
- Produces: в `nowcast_template.html`: кнопка `#ctoggle`, слой `gibsLayer` (`L.tileLayer`), функция `pickGIBSDate()`, JS-переключатель.

Контекст текущего файла (для точной вставки) — `nowcast_template.html`:
- CSS `#ltoggle` на строках 27-29; `#ltoggle.on{...}` строка 28.
- Кнопка `#ltoggle` на строке 54.
- Базовый слой `L.tileLayer('https://rainradar.ru/tiles?...')` на строках 78-80.
- Логика молний `ltoggle` на строках 88-99 (переменные `ltOn`, `elLt`).

- [ ] **Step 1: Write the failing marker test**

Add to `F:\Meteo\tests\test_build.py` (append at end, `NOWCAST_TEMPLATE` уже определена вверху файла):

```python
def test_nowcast_template_has_gibs_cloud_layer():
    with open(NOWCAST_TEMPLATE, encoding="utf-8") as f:
        s = f.read()
    assert 'id="ctoggle"' in s
    assert "gibsLayer" in s
    assert "earthdata.nasa.gov" in s
    assert "maxNativeZoom" in s
```

- [ ] **Step 2: Run test to verify it fails**

Run: `& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests/test_build.py::test_nowcast_template_has_gibs_cloud_layer -q`
Expected: FAIL (assertion `id="ctoggle"` fails — not present yet).

- [ ] **Step 3: Add `#ctoggle` CSS and button**

CSS — immediately after the existing `#ltoggle .ltdot{...}` line (`nowcast_template.html` line ~29), add:

```css
#ctoggle{position:absolute;top:54px;right:10px;z-index:1000;background:#42434b;color:#fff;border:0;border-radius:18px;padding:6px 14px;font-size:12px;cursor:pointer;font-weight:600;box-shadow:0 1px 3px rgba(0,0,0,.3);display:flex;align-items:center;gap:6px}
#ctoggle.on{background:#f29b17;color:#fff}
```

Button — immediately after the existing `#ltoggle` button line (`nowcast_template.html` line ~54), add:

```html
<button id="ctoggle" title="Спутниковая облачность NASA GIBS (дневной снимок)"><span class="ltdot"></span>Облачность</button>
```

- [ ] **Step 4: Add `gibsLayer` and logic in JS**

After the base tile layer block (after line ~80, `}).addTo(map);`), insert the full GIBS block below:

```js
  // Слой спутниковой облачности NASA GIBS (MODIS TrueColor). Тайлы только на z=9;
  // maxNativeZoom:9/minNativeZoom:9 заставляют Leaflet подгружать z9 и масштабировать под зум карты.
  var GIBS_BASE='https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/';
  var GIBS_PRODUCT='MODIS_Terra_CorrectedReflectance_TrueColor';
  var gibsDate=null;
  function probeDay(url,cb){
    var img=new Image();img.crossOrigin='anonymous';
    img.onload=function(){cb(true);};
    img.onerror=function(){cb(false);};
    img.src=url;
  }
  function pickGIBSDate(cb){
    if(gibsDate){cb(gibsDate);return;}
    var i=0;
    (function next(){
      if(i>=5){gibsDate=new Date().toISOString().slice(0,10);cb(gibsDate);return;}
      var dd=new Date();dd.setUTCDate(dd.getUTCDate()-i);
      var ds=dd.toISOString().slice(0,10);
      var url=GIBS_BASE+GIBS_PRODUCT+'/default/'+ds+'/GoogleMapsCompatible_Level9/9/0/0.jpg';
      probeDay(url,function(ok){
        if(ok){gibsDate=ds;cb(ds);}
        else{i++;next();}
      });
    })();
  }
  var elCt=document.getElementById('ctoggle');
  var cloudOn=true;
  var gibsLayer=null;
  function showCloudLayer(){
    if(gibsLayer){map.addLayer(gibsLayer);return;}
    pickGIBSDate(function(ds){
      if(!ds)return;
      gibsLayer=L.tileLayer(GIBS_BASE+GIBS_PRODUCT+'/default/'+ds+'/GoogleMapsCompatible_Level9/9/{y}/{x}.jpg',{
        minZoom:3,maxZoom:10,minNativeZoom:9,maxNativeZoom:9,zIndex:900,opacity:0.9,
        attribution:'Спутник: <a href="https://earthdata.nasa.gov/">NASA GIBS</a>'
      }).addTo(map);
    });
  }
  function hideCloudLayer(){if(gibsLayer)map.removeLayer(gibsLayer);}
  elCt.classList.add('on');
  showCloudLayer();
  elCt.addEventListener('click',function(){
    cloudOn=!cloudOn;
    if(cloudOn){elCt.classList.add('on');showCloudLayer();}
    else{elCt.classList.remove('on');hideCloudLayer();}
  });
```

- [ ] **Step 5: Run the marker test**

Run: `& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests/test_build.py::test_nowcast_template_has_gibs_cloud_layer -q`
Expected: PASS.

- [ ] **Step 6: Run the build-file tests + radar-affected build test**

Run: `& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests/test_build.py -q`
Expected: PASS (all build tests, including the GIBS marker and existing ones).

- [ ] **Step 7: Commit**

```bash
git add nowcast_template.html tests/test_build.py
git commit -m "feat(sputnik): add GIBS cloud layer toggle"
```

---

### Task 3: Пересборка `nowcast.html` и интеграционная проверка

**Files:**
- Modify: `F:\Meteo\nowcast.html` (пересоздаётся билдером из шаблона)
- Test: `F:\Meteo\tests\test_build.py` (уже покрывает сборку — `test_builder_produces_nowcast_html`)

**Interfaces:**
- Consumes: `nowcast_template.html` (после Task 2).
- Produces: обновлённый `nowcast.html` с GIBS-слоем; подтверждение регрессии `radar.html` (byte-identical).

- [ ] **Step 1: Rebuild both pages**

Run: `& "F:\Meteo\.venv\Scripts\python.exe" tools/build_radar.py`
Expected: `[ok] F:\Meteo\nowcast.html written (...)`, `[ok] F:\Meteo\radar.html written (...)`.

- [ ] **Step 2: Verify radar.html is byte-identical**

Run: `git -C F:\Meteo diff --stat radar.html`
Expected: empty output (no diff).

- [ ] **Step 3: Verify nowcast.html contains the cloud layer**

Run: `Select-String -Path 'F:\Meteo\nowcast.html' -Pattern 'ctoggle','earthdata','maxNativeZoom' | Measure-Object | Select-Object -ExpandProperty Count`
Expected: 3 matching lines exist (count >= 3). (If Select-String with these literal patterns is flaky in PowerShell, grep the file with the compile tool instead — the check is: all three markers present.)

- [ ] **Step 4: Run full test suite**

Run: `& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests/ -m "not integration" -q`
Expected: PASS — 193 passed, 2 deselected (после Task 1: +2 `test_gibs_*` в test_nowcast; после Task 2: +1 `test_nowcast_template_has_gibs_cloud_layer` в test_build; было 190).

- [ ] **Step 5: Integration check (manual, network)**

Write `C:\Users\SamLab\AppData\Local\Temp\opencode\verify_gibs.py`:

```python
import sys, urllib.request
sys.path.insert(0, r"F:\Meteo")
from tools import nowcast as nc

def get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, dict(r.getheaders()), r.read()

# Yaroslavl z9
import math
def deg2tile(lat, lon, z):
    latr=math.radians(lat); n=2.0**z
    return int((lon+180)/360*n), int((1-math.asinh(math.tan(latr))/math.pi)/2*n)
x, y = deg2tile(57.63, 39.87, 9)
for date in ("2026-09-03", "2026-09-02"):
    s, h, b = get(nc.gibs_tile_url(x, y, date))
    print(date, s, h.get("Content-Type"), len(b), "ACAO", h.get("Access-Control-Allow-Origin"))
print("GIBS INTEGRATION DONE")
```

Run: `& "F:\Meteo\.venv\Scripts\python.exe" "C:\Users\SamLab\AppData\Local\Temp\opencode\verify_gibs.py"`
Expected: at least one `200 image/jpeg len>2000 ACAO *` line (день с доступным дневным снимком). 400 на каком-то дне допустим — это дневное окно.

- [ ] **Step 6: Commit rebuilt artifact**

```bash
git add nowcast.html
git commit -m "build(sputnik): rebuild nowcast.html with GIBS cloud layer"
```

---

## Self-Review (проверка перед передачей)

### Покрытие спеки
- Кнопка-тумблер `#ctoggle` «Облачность» включённая по умолчанию — Task 2 (класс `.on`, `showCloudLayer()` при init) ✓
- Слой `L.tileLayer` GIBS с `minNativeZoom:9`/`maxNativeZoom:9` — Task 2 ✓
- Порядок слоёв: `gibsLayer` `zIndex:900` < базы `zIndex:998`? — валидно: нижнее значение = слой ниже в стеке zIndex Leaflet. Наукастинг (`NowcastLayer`) добавляется позже и без zIndex — по умолчанию выше. Оставлено как в текущей разметке; осадки поверх облаков ✓ (см. примечание).
- Утилита `gibs_tile_url` + тесты — Task 1 ✓
- Пересборка `nowcast.html`, регрессия `radar.html`, интеграция — Task 3 ✓
- deploy.yml не меняется (уже копирует nowcast.html) ✓

### Примечание по zIndex/порядку
`rainradar.ru/tiles` задан `zIndex:998`; `gibsLayer` задан `zIndex:900` → у Leaflet меньший zIndex = ниже. `NowcastLayer`, молнии, labels добавляются без явного `zIndex` → они выше `zIndex:900`. Т.е. облачность под наукастингом — корректно. База (998) выше облачности (900) — это существующее поведение (базовая карта под слоями), не трогаем.

### Открытое поведение (документировано, не блокер)
- Даже если дневного снимка нет (ночь/утро до пролёта), слой просто пустой — ожидаемо.
- Дата выбирается `pickGIBSDate` перебором до 4 дней назад; невыполнение сети → fallback на сегодня.
