# Радар осадков (RainViewer) в MeteoMap — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить вкладку «Радар» с интерактивной картой осадков (RainViewer) в MeteoMap.

**Architecture:** Новая статичная страница `radar.html` с инлайновым Leaflet 1.6.0. Браузер тянет манифест с `api.rainviewer.com`, тайлы осадков с `tilecache.rainviewer.com`, тёмную подложку с `basemaps.cartocdn.com` (данные OSM). В `index.html` добавляется вкладка «Радар» с `<iframe>` на `radar.html?lat=..&lon=..&zoom=8`. Деплой: `radar.html` копируется в `_site/` тем же пайплайном.

**Tech Stack:** Leaflet 1.6.0 (инлайн, BSD-2), vanilla JS, RainViewer API, CartoDB dark_all, GitHub Pages.

## Global Constraints

- Внешние CDN-библиотеки запрещены; Leaflet инлайнится прямо в `radar.html`.
- Интерфейс: русский язык, тёмная тема карты, светлая тема остального сайта.
- Деплой только через существующий `deploy.yml`; без новых workflows, secrets, cron.
- Attribution обязателен: OSM, CARTO, RainViewer.
- Формат тайла RainViewer: `{host} + frame.path + "/256/{z}/{x}/{y}/2/1_1.png"`, где `host` и `frame.path` берутся из манифеста (`path` уже содержит `/v2/radar/...`).
- `bot.php` не коммитить.

---

### Task 1: Сгенерировать radar.html с инлайновым Leaflet

**Files:**
- Create: `tools/build_radar.py`
- Create: `radar_template.html`
- Create: `radar.html` (результат сборки, коммитится)
- Test: `tests/test_radar.py`

**Interfaces:**
- Produces: `radar.html` — полностью самодостаточная страница (Leaflet + приложение в одном файле).
- Consumes: `C:\Users\SamLab\AppData\Local\Temp\opencode\rainradar_bundle.js` (локальный файл, вне репозитория) — источник чистого Leaflet 1.6.0.

**Контекст:** Leaflet 1.6.0 находится внутри bundle rainradar.ru как UMD-блок от начала файла до `var Http={`. Скрипт сборки извлекает этот блок и вставляет в `radar_template.html` вместо `/*__LEAFLET__*/`.

- [ ] **Step 1: Создать `tools/build_radar.py`**

```python
#!/usr/bin/env python3
"""Собирает radar.html: инлайнит Leaflet 1.6.0 из локального bundle rainradar.ru."""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BUNDLE = os.path.join(
    os.environ.get("LOCALAPPDATA", "C:/Users/SamLab"),
    "Temp/opencode/rainradar_bundle.js",
)
TEMPLATE = os.path.join(ROOT, "radar_template.html")
OUT = os.path.join(ROOT, "radar.html")


def extract_leaflet(bundle_path):
    if not os.path.isfile(bundle_path):
        sys.exit(f"error: bundle not found: {bundle_path}")
    with open(bundle_path, encoding="utf-8", errors="replace") as f:
        s = f.read()
    i = s.find("var Http={")
    if i < 0:
        sys.exit("error: Leaflet UMD block not found in bundle")
    leaflet = s[:i]
    assert leaflet.rstrip().endswith("window.L=e});"), leaflet[-60:]
    return leaflet


def build():
    with open(TEMPLATE, encoding="utf-8") as f:
        template = f.read()
    leaflet = extract_leaflet(BUNDLE)
    assert "/*__LEAFLET__*/" in template, "placeholder missing in template"
    html = template.replace("/*__LEAFLET__*/", leaflet)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[ok] radar.html written ({os.path.getsize(OUT)} bytes)")


if __name__ == "__main__":
    build()
```

- [ ] **Step 2: Создать `radar_template.html`**

Файл содержит приложение radar.html с плейсхолдером `/*__LEAFLET__*/`:

```html
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Радар осадков — MeteoMap</title>
<style>
:root{--dark:#14161c;--panel:#1d2027;--line:#2a2e37;--text:#e8eaf0;--muted:#9aa3b8}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{background:var(--dark);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;overflow:hidden}
#map{position:absolute;inset:0;background:var(--dark)}
.leaflet-container{background:var(--dark)}
.leaflet-control-attribution{font-size:10px;background:rgba(20,22,28,.75);color:var(--muted)}
.leaflet-control-attribution a{color:#c7d2e0}
#timeline{position:absolute;left:0;right:0;bottom:0;z-index:1000;background:var(--panel);border-top:1px solid var(--line);padding:10px 14px;display:flex;align-items:center;gap:14px}
#play{width:40px;height:40px;border-radius:50%;border:1px solid var(--line);background:#262a33;color:var(--text);font-size:15px;cursor:pointer;flex:none}
#play:hover{background:#2e333e}
#time{font-size:12px;color:var(--muted);min-width:120px;flex:none;font-variant-numeric:tabular-nums}
#slider{flex:1;accent-color:#e09b00;height:4px;cursor:pointer}
#legend{position:absolute;right:14px;bottom:80px;z-index:1000;background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:8px;text-align:center;font-size:10px;color:var(--muted)}
#legend .grad{width:16px;height:120px;margin:4px auto;border-radius:3px;background:linear-gradient(180deg,#169810 0%,#b6e90c 25%,#fbf205 40%,#f19a09 55%,#f21b0b 75%,#c40a85 90%,#8d1fb8 100%)}
#legend .lbl{font-size:9px}
#status{position:absolute;top:10px;left:50%;transform:translateX(-50%);z-index:1000;background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:6px 14px;font-size:12px;display:none}
#status.show{display:block}
</style>
</head>
<body>
<div id="map"></div>
<div id="status"></div>
<div id="legend">Интенсивность<div class="grad"></div><div class="lbl">слабо → сильно</div></div>
<div id="timeline">
  <button id="play" title="Воспроизвести">▶</button>
  <span id="time">—</span>
  <input id="slider" type="range" min="0" value="0">
</div>
<script>
/*__LEAFLET__*/
</script>
<script>
(function(){
  var params=new URLSearchParams(location.search);
  var lat=parseFloat(params.get('lat'))||57.63;
  var lon=parseFloat(params.get('lon'))||39.87;
  var zoom=parseInt(params.get('zoom')||'8',10);
  var map=L.map('map',{zoomControl:true}).setView([lat,lon],zoom);
  L.tileLayer('https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',{
    maxZoom:10,attribution:'© OpenStreetMap contributors © CARTO'
  }).addTo(map);

  var frames=[],idx=0,playing=false,timer=null,overlay=null,host='';
  var elPlay=document.getElementById('play');
  var elTime=document.getElementById('time');
  var elSlider=document.getElementById('slider');
  var elStatus=document.getElementById('status');

  function setStatus(t){elStatus.textContent=t;elStatus.classList.add('show');}
  function clearStatus(){elStatus.classList.remove('show');}
  function fmtTime(ts){
    var d=new Date(ts*1000);
    var p=function(n){return (n<10?'0':'')+n;};
    return p(d.getDate())+'.'+p(d.getMonth()+1)+' '+p(d.getHours())+':'+p(d.getMinutes());
  }

  function showFrame(i){
    if(!frames.length)return;
    i=Math.max(0,Math.min(frames.length-1,i));
    idx=i;var f=frames[i];
    if(overlay){map.removeLayer(overlay);}
    overlay=L.tileLayer(host+f.path+'/256/{z}/{x}/{y}/2/1_1.png',{
      maxZoom:10,attribution:'© RainViewer',opacity:0.85
    }).addTo(map);
    elSlider.value=i;
    elTime.textContent=fmtTime(f.time)+(f.future?' (прогноз)':'');
  }

  function togglePlay(){
    if(!frames.length)return;
    playing=!playing;
    elPlay.textContent=playing?'⏸':'▶';
    if(playing){
      timer=setInterval(function(){showFrame(idx+1<frames.length?idx+1:0);},600);
    }else{clearInterval(timer);timer=null;}
  }

  elPlay.addEventListener('click',togglePlay);
  elSlider.addEventListener('input',function(){
    if(playing){playing=false;elPlay.textContent='▶';clearInterval(timer);timer=null;}
    showFrame(parseInt(elSlider.value,10));
  });

  function load(){
    setStatus('Загрузка…');
    fetch('https://api.rainviewer.com/public/weather-maps.json?t='+Date.now(),{cache:'no-store'})
      .then(function(r){if(!r.ok)throw new Error('HTTP '+r.status);return r.json();})
      .then(function(d){
        host=d.host||'https://tilecache.rainviewer.com';
        var past=(d.radar&&d.radar.past||[]).map(function(f){return {time:f.time,path:f.path,future:false};});
        var now=(d.radar&&d.radar.nowcast||[]).map(function(f){return {time:f.time,path:f.path,future:true};});
        frames=past.concat(now);
        if(!frames.length)throw new Error('нет кадров');
        elSlider.max=frames.length-1;
        var cur=frames.map(function(f){return f.future;}).indexOf(false);
        showFrame(cur>=0?cur:0);
        clearStatus();
      })
      .catch(function(e){
        setStatus('Радар недоступен: '+e.message);
        setTimeout(load,30000);
      });
  }

  load();
  setInterval(load,5*60*1000);
})();
</script>
</body>
</html>
```

- [ ] **Step 3: Запустить сборку**

Run: `python tools/build_radar.py`
Expected: `[ok] radar.html written (... bytes)` и файл `radar.html` создан в корне репозитория.

- [ ] **Step 4: Headless-проверка radar.html**

Скрипт-проба: `C:\Users\SamLab\AppData\Local\Temp\opencode\run_feasibility.py` (адаптировать под `radar.html` с URL `file:///F:/Meteo/radar.html`), или прямая команда:

```powershell
& "F:\Meteo\.venv\Scripts\python.exe" -c "import sys,subprocess,re; sys.stdout.reconfigure(encoding='utf-8',errors='replace'); edge=r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'; cmd=[edge,'--headless','--disable-gpu','--no-first-run','--window-size=1366,900','--virtual-time-budget=15000','--dump-dom','file:///F:/Meteo/radar.html?lat=57.63&lon=39.87&zoom=8']; r=subprocess.run(cmd,capture_output=True,timeout=60); out=r.stdout.decode('utf-8',errors='replace'); print('images:',out.count('<img')); print('has leaflet map:', 'leaflet' in out.lower() or 'leaflet' in out)" 
```

Expected: `images:` > 0 (загрузились тайлы подложки и/или осадков), нет JS-ошибок в stderr, страница не пустая. Оверлей осадков фактически грузится — проверить, что `out` содержит img с `tilecache.rainviewer.com`.

- [ ] **Step 5: Коммит**

```bash
git add tools/build_radar.py radar_template.html radar.html
git commit -m "feat(radar): self-contained radar.html with inlined Leaflet"
```

---

### Task 2: Добавить вкладку «Радар» в index.html

**Files:**
- Modify: `template.html` (CSS строки 27-29, вкладки 126-132, панели 133-192, JS табов 243-248, JS renderAll 705-719)
- Test: `tests/test_radar.py` (дополнить)

**Interfaces:**
- Consumes: `D.location.lat/lon` (есть в payload: `build_payload` кладёт `location` = запись из `LOCATIONS` с полями name/slug/lat/lon).
- Produces: вкладка `data-tab="radar"`, панель `#tab-radar` с `<iframe id="radar-frame">`, JS обновляет `src` при смене города.

- [ ] **Step 1: Добавить CSS для вкладки радара**

В `template.html` строку 28 заменить:

```css
#tab-compare.active,#tab-accuracy.active,#tab-help.active{overflow:auto}
```

на:

```css
#tab-compare.active,#tab-accuracy.active,#tab-help.active{overflow:auto}
#tab-radar.active{overflow:hidden}
#tab-radar{min-height:0}
#radar-frame{width:100%;height:100%;border:0;display:block}
```

- [ ] **Step 2: Добавить кнопку вкладки**

Строку 129 (после `<button data-tab="forecast">Прогноз</button>`) заменить на:

```html
  <button data-tab="forecast">Прогноз</button>
  <button data-tab="radar">Радар</button>
```

- [ ] **Step 3: Добавить панель с iframe**

После закрытия `#tab-forecast` (строка 147) вставить:

```html
<div id="tab-radar" class="panel">
  <iframe id="radar-frame" title="Радар осадков"></iframe>
</div>
```

- [ ] **Step 4: Обновить JS переключения вкладок**

Строку 246 заменить:

```js
  ['weather','forecast','compare','accuracy','help'].forEach(t=>document.getElementById('tab-'+t).classList.toggle('active',b.dataset.tab===t));
```

на:

```js
  ['weather','forecast','radar','compare','accuracy','help'].forEach(t=>document.getElementById('tab-'+t).classList.toggle('active',b.dataset.tab===t));
```

- [ ] **Step 5: Добавить функцию обновления iframe по городу**

В `renderAll()` (строка ~705) добавить вызов. Строку:

```js
  buildConditions(); buildWeatherNow(); buildWeatherHours();
```

заменить на:

```js
  updateRadarFrame();
  buildConditions(); buildWeatherNow(); buildWeatherHours();
```

И добавить функцию перед `renderAll()`:

```js
function updateRadarFrame(){
  const f=document.getElementById('radar-frame');
  if(f&&D.location){f.src='radar.html?lat='+D.location.lat+'&lon='+D.location.lon+'&zoom=8';}
}
```

- [ ] **Step 6: Написать юнит-тест**

В `tests/test_radar.py` добавить:

```python
def test_index_has_radar_tab_and_iframe(tmp_path):
    import os
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(here, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    html = meteo.render(tpl, _payload())
    assert 'data-tab="radar"' in html
    assert 'id="radar-frame"' in html
    assert 'updateRadarFrame()' in html
```

- [ ] **Step 7: Прогнать тесты**

Run: `python -m pytest tests/ -m "not integration" -q`
Expected: все тесты PASS (включая новые).

- [ ] **Step 8: Перегенерировать index.html локально (без сети) и headless-проверить вкладку**

Использовать `regen_index.py` (в Temp) или: прогнать сборку через `python meteo.py` НЕ требуется (нужна сеть). Вместо этого — инъекция фикса в live-копию как раньше, либо локальная перегенерация с payload из embedded JSON (см. `regen_live.py` в Temp).

Headless-проба через `tools/headless_probe.py`:
- Probe JS: проверить, что после клика по `[data-tab="radar"]` панель активна и `#radar-frame` имеет `src` с `lat=57.63`.

- [ ] **Step 9: Коммит**

```bash
git add template.html tests/test_radar.py
git commit -m "feat(site): add radar tab with iframe to radar.html"
```

---

### Task 3: Обновить deploy.yml

**Files:**
- Modify: `.github/workflows/deploy.yml` (шаг «Prepare pages artifact», строки 45-51)

- [ ] **Step 1: Добавить сборку и копирование radar.html**

Шаг заменить:

```yaml
      - name: Prepare pages artifact
        run: |
          mkdir -p _site
          cp index.html _site/
          cp -r data _site/
          echo "" > _site/.nojekyll
```

на:

```yaml
      - name: Build radar page
        run: python tools/build_radar.py

      - name: Prepare pages artifact
        run: |
          mkdir -p _site
          cp index.html _site/
          cp radar.html _site/
          cp -r data _site/
          echo "" > _site/.nojekyll
```

**Важно:** в CI `tools/build_radar.py` не найдёт bundle по локальному пути `LOCALAPPDATA/Temp/opencode/...`. Нужно, чтобы bundle был в репозитории. Поэтому leaflet извлекается один раз и коммитится отдельным файлом `tools/leaflet.js`; `build_radar.py` читает его. Отредактировать `tools/build_radar.py` в Task 1 → заменить `BUNDLE` на `tools/leaflet.js` и добавить `tools/leaflet.js` (143KB) в коммит Task 1.

- [ ] **Step 2: Проверить, что leaflet коммитится в репозиторий**

В Task 1 Step 5 коммит должен включать `tools/leaflet.js` (извлечённый листинг `leaflet_standalone.js` из Temp). В `build_radar.py` изменить:

```python
BUNDLE = os.path.join(os.environ.get("LOCALAPPDATA", "C:/Users/SamLab"), "Temp/opencode/rainradar_bundle.js")
```

на:

```python
BUNDLE = os.path.join(ROOT, "tools", "leaflet.js")
```

- [ ] **Step 3: Коммит**

```bash
git add .github/workflows/deploy.yml tools/build_radar.py tools/leaflet.js
git commit -m "ci: build and deploy radar.html to Pages"
```

---

### Task 4: Финальная проверка (локальная headless-проба полного сайта)

**Files:**
- Test: `tools/headless_probe.py` + временный probe-скрипт

- [ ] **Step 1: Локальная регенерация index.html с вкладкой радара**

Перегенерировать `index.html` из обновлённого `template.html` (regen-скрипт из Temp с payload из live `index.html`), положить рядом `radar.html` (уже собран), запустить headless-probe: клик по вкладке «Радар» → панель активна, iframe `src` содержит координаты города.

- [ ] **Step 2: Проверить переключение города**

Probe: сменить город через `loadCity('balakirevo')` → `#radar-frame.src` содержит `lat=56.507`.

- [ ] **Step 3: Прогнать полный набор тестов**

Run: `python -m pytest tests/ -m "not integration" -q`
Expected: все PASS (сейчас 114; с новыми тестами — больше).

---

### Task 5: Пуш и деплой

- [ ] **Step 1: Проверить git status**

Run: `git status --short`
Expected: изменённые файлы (index.html не должен быть изменён, если не перегенерирован вручную; data/ не коммитить).

- [ ] **Step 2: Запушить в main**

```bash
git push origin main
```

- [ ] **Step 3: Дождаться деплоя**

Run: `gh run list --workflow=deploy.yml --limit=3`
Expected: новый run в статусе success после завершения. Дождаться через `gh run watch <id>`.

- [ ] **Step 4: Проверить live-страницу**

Открыть `https://samlab.github.io/MeteoMap/index.html`, вкладка «Радар», карта отображается, тайлы грузятся, таймлайн работает (текущий кадр без автоплея).

---

## Self-Review

**Spec coverage:**
- Вкладка «Радар» в шапке — Task 2. ✓
- iframe на radar.html с lat/lon/zoom — Task 2 (JS updateRadarFrame). ✓
- Leaflet инлайн без CDN — Task 1. ✓
- Тёмная подложка CartoDB — Task 1 (tileLayer dark_all). ✓
- Оверлей RainViewer, формат host+path — Task 1. ✓
- Таймлайн: текущий кадр без автоплея, история + nowcast (future-флаг), автообновление 5 мин — Task 1. ✓
- Пустой nowcast скрывает «вперёд» — Task 1 (метка «(прогноз)» появляется только у future-кадров; при пустом nowcast кадров с меткой нет). ✓
- Ошибки: статус + ретрай 30 с — Task 1. ✓
- Деплой: cp radar.html в _site — Task 3. ✓
- Attribution OSM/CARTO/RainViewer — Task 1. ✓
- Юнит-тесты + headless-проба — Task 2/4. ✓

**Placeholder scan:** нет TBD/TODO; код полный в каждом шаге.

**Type consistency:** `updateRadarFrame` определён в Task 2 и вызывается там же; `build_radar.py` `BUNDLE` заменяется в Task 3 (leaflet в репо); имена элементов (id) совпадают между template и JS.
