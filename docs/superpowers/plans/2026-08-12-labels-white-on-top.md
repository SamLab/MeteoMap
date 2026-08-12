# White city labels above clouds Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Показать названия городов/сёл белым цветом поверх облаков на карте радара, как на rainradar.ru.

**Architecture:** Новый `LabelsLayer` (Leaflet `GridLayer`) в pane `labels` (z-index 900, выше дождя и молний) в `radar_template.html`. Данные — JSON с `https://rainradar.ru/labels?z={z}&x={x}&y={y}` (CORS `*`): каждая запись `[id, имя, x(px слева), y(px снизу), класс 0..3]` → `div.label.l<класс>` с `<span>`-текстом, позиция `left:x px; bottom:y px` внутри тайла 256×256. Стили — белый текст, тень `rgba(0,0,0,.7)` по 4 сторонам, размеры 13/12/11/10px для l0..l3 (замерены с живого rainradar). Затем сборка `radar.html`, тесты, деплой.

**Tech Stack:** JavaScript (vanilla, ES5 — страница без транспиляции), Leaflet 1.6.0 (инлайн из `tools/leaflet.js`), Python 3 (сборка/тесты), pytest.

## Global Constraints

- Редактируется только `radar_template.html` (сборка через `tools/build_radar.py` в `radar.html`); `bot.php` не трогать; неотслеживаемые `docs/superpowers/...` файлы (план 2026-08-11, spec 2026-08-11) не коммитить.
- Код в шаблоне — ES5 (без стрелок, const/let, template literals), чтобы соответствовать остальному коду страницы.
- `map` живёт внутри IIFE `radar_template.html` — весь новый код вставляется внутрь этой IIFE.
- Зависимость от стороннего endpoint принята (spec). Ошибки запроса → пустой тайл, без сообщений пользователю.
- Игнорировать 2 пред-существующих failed-теста Open-Meteo (`test_all_forecast_models_return_data_for_yaroslavl`, `test_verification_runs_for_last_7_days`).
- Точка вставки CSS: в `<style>` шаблона, после строки `.leaflet-container .leaflet-control-attribution a{color:#415fad}` и перед `</style>`.
- Точка вставки JS: после блока молний (после строки `  },120000);`), перед `  var frames=[],idx=0,...`.
- При коммитах: `git add` только конкретных файлов (`radar_template.html`, `radar.html`, `tests/test_radar.py`), никогда `git add -A`/`git add .`.

---

### Task 1: Failing test для слоя подписей

**Files:**
- Modify: `tests/test_radar.py` (добавить тест в конец файла)

**Interfaces:**
- Consumes: существующий паттерн тестов `test_radar.py` (открытие `radar_template.html`/`radar.html` через `os.path.join(HERE, ...)`).
- Produces: `test_radar_has_labels_layer()` — проверка, что шаблон и собранный `radar.html` содержат весь слой подписей.

- [ ] **Step 1: Добавить тест в конец `tests/test_radar.py`**

Дописать после функции `test_radar_palette_has_original_rainradar_colors()` (последней в файле):

```python
def test_radar_has_labels_layer():
    with open(os.path.join(HERE, "radar_template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "LabelsLayer" in tpl
    assert "map.createPane('labels')" in tpl
    assert "rainradar.ru/labels?z=" in tpl
    assert ".leaflet-labels-pane{z-index:900}" in tpl
    assert ".label.l0>span" in tpl and ".label.l3>span" in tpl
    assert "text-shadow:-1px 0 1px" in tpl
    assert "pointer-events:none" in tpl
    assert "updateWhenZooming:false" in tpl
    assert "minZoom:5" in tpl
    with open(os.path.join(HERE, "radar.html"), encoding="utf-8") as f:
        radar = f.read()
    assert "LabelsLayer" in radar
    assert "rainradar.ru/labels?z=" in radar
    assert ".leaflet-labels-pane{z-index:900}" in radar
    assert ".label.l3>span" in radar
```

- [ ] **Step 2: Запустить тест и убедиться, что падает**

Run: `& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests/test_radar.py::test_radar_has_labels_layer -v`
Expected: FAIL (AssertionError — «LabelsLayer» отсутствует в шаблоне).

- [ ] **Step 3: Закоммитить тест**

```bash
git add tests/test_radar.py
git commit -m "test: labels layer presence in radar template"
```

---

### Task 2: Слой подписей в radar_template.html

**Files:**
- Modify: `radar_template.html` (CSS: после строки 35 `.leaflet-container .leaflet-control-attribution a{color:#415fad}`; JS: после строки 87 `  },120000);`)

**Interfaces:**
- Consumes: `map` (IIFE-переменная), существующая логика создания panes молний.
- Produces: `LabelsLayer` (GridLayer, pane `labels`, minZoom 5, maxZoom 10), зарегистрированный на карте сразу после молний.

- [ ] **Step 1: Добавить CSS-правила в `<style>`**

Вставить перед `</style>` (после строки 35):

```css
.leaflet-labels-pane{z-index:900}
.label{position:absolute;white-space:nowrap;pointer-events:none;line-height:1}
.label>span{color:#fff;font-weight:500;text-shadow:-1px 0 1px rgba(0,0,0,.7),1px 0 1px rgba(0,0,0,.7),0 1px 1px rgba(0,0,0,.7),0 -1px 1px rgba(0,0,0,.7)}
.label.l0>span{font-size:13px}
.label.l1>span{font-size:12px}
.label.l2>span{font-size:11px}
.label.l3>span{font-size:10px}
```

- [ ] **Step 2: Добавить JS-слой после блока молний**

Вставить после `  },120000);` (после обновления тайлов молний), перед `  var frames=[]`:

```js
  map.createPane('labels');
  var LabelsLayer=L.GridLayer.extend({
    options:{pane:'labels',minZoom:5,maxZoom:10,updateWhenZooming:false},
    createTile:function(coords){
      var tile=document.createElement('div');
      var url='https://rainradar.ru/labels?z='+coords.z+'&x='+coords.x+'&y='+coords.y;
      fetch(url).then(function(r){return r.json();}).then(function(labels){
        for(var i=0;i<labels.length;i++){
          var d=document.createElement('div'),s=document.createElement('span');
          d.className='label l'+labels[i][4];
          s.textContent=labels[i][1];
          d.style.left=labels[i][2]+'px';
          d.style.bottom=labels[i][3]+'px';
          d.appendChild(s);
          tile.appendChild(d);
        }
      }).catch(function(){});
      return tile;
    }
  });
  map.addLayer(new LabelsLayer());
```

Примечание: `createTile` объявлен с ОДНИМ параметром — Leaflet 1.6.0 автоматически вызывает `_tileReady` (строка `createTile.length<2&&...` в `GridLayer._addTile`) и сразу вешает класс `leaflet-tile-loaded`, поэтому div-тайл видим сразу, а подписи появляются по мере ответов fetch.

- [ ] **Step 3: Прогнать тесты**

Run: `& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests/test_radar.py -v`
Expected: `test_radar_has_labels_layer` теперь PASS по шаблону, но FAIL по `radar.html` (ещё не пересобран: asserts `"LabelsLayer" in radar` и т.п.). Остальные тесты radar проходят.

---

### Task 3: Пересборка radar.html и полный прогон

**Files:**
- Modify: `radar.html` (генерируется, не править руками)

**Interfaces:**
- Consumes: Task 2 (изменённый шаблон), `tools/build_radar.py`.
- Produces: актуальный `radar.html` с метками слоя подписей на месте плейсхолдеров.

- [ ] **Step 1: Пересобрать radar.html**

Run: `& "F:\Meteo\.venv\Scripts\python.exe" tools/build_radar.py`
Expected: `[ok] radar.html written (... bytes)`.

- [ ] **Step 2: Прогнать весь radar-набор тестов**

Run: `& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests/test_radar.py -v`
Expected: 9 passed (включая новый `test_radar_has_labels_layer`).

- [ ] **Step 3: Быстрая проверка, что собранный radar.html не сломан**

Run: `& "F:\Meteo\.venv\Scripts\python.exe" -c "d=open(r'F:\Meteo\radar.html',encoding='utf-8').read(); print('LEAFLET' if 'window.L=e' in d else 'NO-L'); print('labels' if 'rainradar.ru/labels?z=' in d else 'NO-LABELS'); print('placeholders' if '/*__LEAFLET__*/' in d else 'none')"`
Expected: `LEAFLET`, `labels`, `none`.

- [ ] **Step 4: Закоммитить шаблон и сборку**

```bash
git add radar_template.html radar.html tests/test_radar.py
git commit -m "feat: white city labels above clouds via rainradar /labels"
```

---

### Task 4: Живая проверка в headless Edge (CDP)

**Files:**
- Create (temp, вне репозитория): `C:\Users\SamLab\AppData\Local\Temp\opencode\labels_verify.py`
- Test (выполнение скрипта, результат — скриншот и текстовые проверки)

**Interfaces:**
- Consumes: собранный `radar.html` (Task 3).
- Produces: подтверждение, что подписи белые, поверх дождя и молний, на зуме 8 и 10.

- [ ] **Step 1: Написать скрипт проверки**

Создать `C:\Users\SamLab\AppData\Local\Temp\opencode\labels_verify.py` (головной Edge, CDP; открой `file:///F:/Meteo/radar.html?lat=55.75&lon=37.6&zoom=8`):

```python
import json, time, subprocess, urllib.request, websocket

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
port = 9364
out = r"C:\Users\SamLab\AppData\Local\Temp\opencode"
proc = subprocess.Popen([EDGE, "--headless=new", "--remote-debugging-port=%d" % port,
                         "--user-data-dir=%s\\cdp_lbl" % out, "--remote-allow-origins=*",
                         "--window-size=1400,900", "about:blank"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
def gj(u): return json.loads(urllib.request.urlopen(u, timeout=5).read())
ws_url = None
for _ in range(40):
    try:
        for p in gj("http://127.0.0.1:%d/json" % port):
            if p.get('type') == 'page': ws_url = p['webSocketDebuggerUrl']; break
        if ws_url: break
    except Exception: pass
    time.sleep(0.5)
ws = websocket.create_connection(ws_url, timeout=120)
mid = 0
def cmd(method, params=None):
    global mid
    mid += 1
    ws.send(json.dumps({'id': mid, 'method': method, 'params': params or {}}))
    return mid
def wait(i, t=120):
    t0 = time.time()
    while time.time() - t0 < t:
        m = json.loads(ws.recv())
        if m.get('id') == i: return m
def js(expr):
    return wait(cmd('Runtime.evaluate', {'expression': expr, 'returnByValue': True})).get('result', {}).get('result', {}).get('value')

cmd('Page.enable'); cmd('Runtime.enable'); time.sleep(0.3)
cmd('Page.navigate', {'url': 'file:///F:/Meteo/radar.html?lat=55.75&lon=37.6&zoom=8'})
time.sleep(14)
check = js("""JSON.stringify((function(){
  var labels=document.querySelectorAll('.label');
  var out={count:labels.length};
  if(labels.length){
    var s=getComputedStyle(labels[0].querySelector('span'));
    out.fontSize=s.fontSize; out.color=s.color; out.textShadow=s.textShadow;
    out.fontWeight=s.fontWeight; out.whiteSpace=getComputedStyle(labels[0]).whiteSpace;
  }
  var panes=Array.prototype.slice.call(document.querySelectorAll('.leaflet-pane'));
  out.paneOrder=panes.map(function(p){return p.className.replace('leaflet-pane ','');});
  var lp=document.querySelector('.leaflet-labels-pane');
  out.labelsZ = lp ? getComputedStyle(lp).zIndex : null;
  var pe=labels.length ? getComputedStyle(labels[0]).pointerEvents : null;
  out.pointerEvents=pe;
  return out;
})())""")
print(check)
shot = wait(cmd('Page.captureScreenshot', {'format': 'png', 'captureBeyondViewport': True}))
open(out + "\\labels_z8.png", 'wb').write(__import__('base64').b64decode(shot['result']['data']))
ws.close(); proc.kill()
```

- [ ] **Step 2: Запустить и проверить вывод**

Run: `& "F:\Meteo\.venv\Scripts\python.exe" C:\Users\SamLab\AppData\Local\Temp\opencode\labels_verify.py`
Expected в JSON-выводе:
- `count > 0`;
- `color = "rgb(255, 255, 255)"`, `textShadow` содержит `rgba(0, 0, 0, 0.7)`;
- `fontSize` — одно из `13px/12px/11px/10px`;
- `paneOrder` содержит `labels` ПОСЛЕ `lightning-0`/`lightning-1` (дольше всех созданных);
- `labelsZ = "900"`, `pointerEvents = "none"`.

- [ ] **Step 3: Проверка зумы 10**

Повторить Step 2 с `zoom=10` в URL (изменить URL в скрипте на `?lat=55.75&lon=37.6&zoom=10`), ожидать `count > 0` (появятся сёла, классы l2/l3).

- [ ] **Step 4: Проверить отсутствие ошибок сети подписей**

В том же скрипте (z8) до закрытия выполнить:
```
js("JSON.stringify(window.__perf=performance.getEntriesByType('resource').filter(function(r){return r.name.indexOf('labels')>=0}).map(function(r){return r.name}))")
```
Expected: массив URL `/labels?z=8&x=…&y=…` (непустой) — запросы уходят и без ошибок.

---

### Task 5: Деплой и live-проверка

**Files:**
- Actions: `git push`, workflow `deploy.yml` (GitHub Actions).

**Interfaces:**
- Consumes: закоммиченные изменения (Task 3) в ветке `main`.
- Produces: опубликованная версия на GitHub Pages.

- [ ] **Step 1: Push**

```bash
git push
```

- [ ] **Step 2: Дождаться деплоя**

Открыть Actions (GitHub, repo MeteoMap, вкладка Actions) и дождаться зелёного run'а. Записать номер run'а.

- [ ] **Step 3: Live-проверка**

Повторить Task 4, заменив `file:///F:/Meteo/radar.html?…` на `https://samlab.github.io/MeteoMap/radar.html?lat=55.75&lon=37.6&zoom=8` (URL кодировать: `%3F` не нужен — Query в URL задаётся как есть). Ожидать те же результаты, что в Task 4.

- [ ] **Step 4: Показать пользователю скриншот**

Сообщить путь скриншота `C:\Users\SamLab\AppData\Local\Temp\opencode\labels_z8.png` и итоги live-проверки.
