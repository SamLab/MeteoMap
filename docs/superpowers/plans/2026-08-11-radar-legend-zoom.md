# Легенда радара как у оригинала + фикс зума — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Заменить легенду радара на оригинальную (4 подписи + 12-цветный градиент rainradar.ru) и устранить баг, из-за которого осадки на карте появляются только после зум-клика.

**Architecture:** Ленивая загрузка iframe радара в `template.html` (iframe грузится только при активации вкладки radar, чтобы Leaflet инициализировался на видимой карте, а не 0×0), плюс самовосстановление размера и один инстанс `RadarLayer` с `redraw()` в `radar_template.html`.

**Tech Stack:** HTML/CSS/JS (Leaflet 1.6), Python (pytest, сборка через `tools/build_radar.py`).

## Global Constraints

- Редактируется исходник `radar_template.html`; собранный `radar.html` генерируется `tools/build_radar.py` — правки вносятся только в шаблон.
- Легенда — непереключаемые подписи (подтверждено пользователем), НЕ кнопки.
- Оригинальный градиент легенды (12 стопов, точные значения): `#8889bd,#595a95,#454696,#36b343,#81c81e,#c2d11e,#ffd000,#f29b17,#e1782e,#d23a4b,#b3107c,#b80db2`.
- Подписи: `Облачность`, `Осадки`, `Гроза`, `Град` (точные строки).
- Тесты: `python -m pytest -q` (venv `F:\Meteo\.venv\Scripts\python.exe`); при смене города iframe URL = `radar.html?lat=<lat>&lon=<lon>&zoom=8`.
- Интеграционные тесты `tests/test_integration.py` падают в независимой сети (Open-Meteo) — это не регрессия, игнорировать.

---

### Task 1: Ленивая загрузка iframe радара в template.html

**Files:**
- Modify: `template.html:728-731` (функция `updateRadarFrame`)
- Modify: `template.html:250-255` (обработчик клика по вкладкам)
- Test: `tests/test_radar.py`

**Interfaces:**
- Consumes: `updateRadarFrame()` вызывается из `renderAll()` (строка 713).
- Produces: `updateRadarFrame()` записывает URL в `f.dataset.radarSrc` и грузит iframe, если панель `#tab-radar` активна. Клик по вкладке radar запускает отложенную загрузку.

- [ ] **Step 1: Написать падающий тест**

Добавить в конец `tests/test_radar.py`:

```python
def test_radar_frame_is_lazy_loaded_on_tab_activation():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "f.dataset.radarSrc" in tpl
    assert 'getElementById("tab-radar")' in tpl
    assert "classList.contains" in tpl
```

- [ ] **Step 2: Запустить тест и убедиться, что падает**

Run: `& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests\test_radar.py::test_radar_frame_is_lazy_loaded_on_tab_activation -q`
Expected: FAIL (assertion error)

- [ ] **Step 3: Изменить `updateRadarFrame`**

В `template.html` заменить строку 730:

```js
function updateRadarFrame(){
  const f=document.getElementById('radar-frame');
  if(!f||!D.location)return;
  const url='radar.html?lat='+D.location.lat+'&lon='+D.location.lon+'&zoom=8';
  f.dataset.radarSrc=url;
  const tab=document.getElementById('tab-radar');
  if(tab&&tab.classList.contains('active'))f.src=url;
}
```

- [ ] **Step 4: Добавить загрузку при активации вкладки radar**

В обработчике клика по вкладкам (строки 250-255) после `classList.toggle` добавить:

```js
  if(b.dataset.tab==='radar'){
    const f=document.getElementById('radar-frame');
    if(f&&f.dataset.radarSrc&&f.dataset.radarSrc!==f.dataset.loadedSrc){f.src=f.dataset.radarSrc;f.dataset.loadedSrc=f.dataset.radarSrc;}
  }
```

(Сравнение с `loadedSrc`, а не `!f.src`, чтобы iframe перезагружался при смене города, когда вкладка radar была неактивна.)

Итоговый блок вкладок:

```js
document.querySelectorAll('.tabs button').forEach(b=>b.addEventListener('click',()=>{
  document.querySelectorAll('.tabs button').forEach(x=>x.classList.remove('active'));
  b.classList.add('active');
  ['weather','forecast','radar','compare','accuracy','help'].forEach(t=>document.getElementById('tab-'+t).classList.toggle('active',b.dataset.tab===t));
  if(b.dataset.tab==='radar'){
    const f=document.getElementById('radar-frame');
    if(f&&f.dataset.radarSrc&&f.dataset.radarSrc!==f.dataset.loadedSrc){f.src=f.dataset.radarSrc;f.dataset.loadedSrc=f.dataset.radarSrc;}
  }
  if(b.dataset.tab==='forecast'&&typeof mainChart!=='undefined'&&mainChart)setTimeout(()=>mainChart.resize(),0);
}));
```

- [ ] **Step 5: Запустить radar-тесты**

Run: `& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests\test_radar.py -q`
Expected: PASS (6 passed)

- [ ] **Step 6: Commit**

```bash
git add template.html tests/test_radar.py
git commit -m "fix(radar): lazy-load radar iframe on tab activation"
```

---

### Task 2: Легенда как у оригинала в radar_template.html

**Files:**
- Modify: `radar_template.html:23-25` (CSS `#legend`)
- Modify: `radar_template.html:39` (разметка `#legend`)
- Test: `tests/test_radar.py`

**Interfaces:**
- Consumes: (none — самодостаточный CSS/HTML в шаблоне).
- Produces: легенда из 4 подписей поверх 12-цветного градиента.

- [ ] **Step 1: Написать падающий тест**

Добавить в конец `tests/test_radar.py`:

```python
def test_radar_legend_matches_original():
    with open(os.path.join(HERE, "radar_template.html"), encoding="utf-8") as f:
        tpl = f.read()
    for label in ("Облачность", "Осадки", "Гроза", "Град"):
        assert label in tpl
    assert "слабо" not in tpl
    assert "сильно" not in tpl
    assert "8889bd" in tpl and "b80db2" in tpl
```

- [ ] **Step 2: Запустить тест и убедиться, что падает**

Run: `& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests\test_radar.py::test_radar_legend_matches_original -q`
Expected: FAIL (assertion error — в шаблоне ещё есть «слабо»/«сильно»)

- [ ] **Step 3: Заменить CSS легенды**

В `radar_template.html` заменить CSS-блок `#legend` (строки 23-25) на:

```css
#legend{position:absolute;bottom:72px;left:50%;transform:translateX(-50%);z-index:1000;width:260px;height:20px;padding:0 14px;display:flex;justify-content:space-between;align-items:center;border-radius:20px;box-shadow:0 0 2px #000;background:linear-gradient(to right,#8889bd,#595a95,#454696,#36b343,#81c81e,#c2d11e,#ffd000,#f29b17,#e1782e,#d23a4b,#b3107c,#b80db2)}
#legend span{font-size:11px;color:#fff;text-shadow:0 0 4px #000;font-weight:600;white-space:nowrap}
```

- [ ] **Step 4: Заменить разметку легенды**

В `radar_template.html` заменить строку 39:

```html
<div id="legend"><span>Облачность</span><span>Осадки</span><span>Гроза</span><span>Град</span></div>
```

- [ ] **Step 5: Пересобрать radar.html**

Run: `& "F:\Meteo\.venv\Scripts\python.exe" tools\build_radar.py`
Expected: `[ok] radar.html written (… bytes)`

- [ ] **Step 6: Запустить radar-тесты**

Run: `& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests\test_radar.py -q`
Expected: PASS (7 passed)

- [ ] **Step 7: Commit**

```bash
git add radar_template.html radar.html tests/test_radar.py
git commit -m "feat(radar): original legend labels and gradient"
```

---

### Task 3: Самовосстановление размера карты и один RadarLayer в radar_template.html

**Files:**
- Modify: `radar_template.html:57` (создание map)
- Modify: `radar_template.html:170-180` (showFrame — один слой + redraw)
- Modify: `radar_template.html:216-218` (инициализация overlay)
- Test: `tools/headless_probe.py` + ручная headless-проверка

**Interfaces:**
- Consumes: `RadarLayer` (существующий), `cur.sets` из `frames`.
- Produces: `overlay` создаётся один раз после первой загрузки кадров; переключение кадров вызывает `overlay.redraw()`; при 0×0 выполняется `map.invalidateSize()`.

- [ ] **Step 1: Добавить invalidateSize после создания карты**

В `radar_template.html` после строки 57 (`var map=L.map(...)`) добавить:

```js
  setTimeout(function(){
    if(map.getContainer().offsetWidth===0||map.getContainer().offsetHeight===0)map.invalidateSize();
  },50);
```

- [ ] **Step 2: Создавать overlay один раз и использовать redraw**

В `radar_template.html` заменить функцию `showFrame` (строки 170-180) на:

```js
  function showFrame(i){
    if(!frames.length)return;
    i=Math.max(0,Math.min(frames.length-1,i));
    idx=i;cur=frames[i];
    if(!overlay){overlay=new RadarLayer({}).addTo(map);}
    else{overlay.redraw();}
    elTime.textContent=fmtTime(cur.time);
    if(elSegs.children.length===frames.length){
      for(var j=0;j<elSegs.children.length;j++)elSegs.children[j].classList.toggle('on',j===i);
    }
  }
```

Проверить, что нигде в `showFrame`/`togglePlay` больше нет `map.removeLayer(overlay)` или `new RadarLayer` (кроме инициализации). Если есть в обработчике клика по `elSegs` (строка ~197) — там только `showFrame(...)`, менять не нужно.

- [ ] **Step 3: Сбросить overlay при перезагрузке кадров**

В `load()` после строки `frames=d.map(...)` (перед `renderSegs()`) убедиться, что overlay сбрасывается при получении нового манифеста. Добавить в начало `.then(function(d){`:

```js
        if(overlay){map.removeLayer(overlay);overlay=null;}
```

- [ ] **Step 4: Пересобрать radar.html**

Run: `& "F:\Meteo\.venv\Scripts\python.exe" tools\build_radar.py`
Expected: `[ok] radar.html written (… bytes)`

- [ ] **Step 5: Headless-проверка рендера после зума**

Создать временный probe `C:\Users\SamLab\AppData\Local\Temp\opencode\probe_verify.py` (по образцу из сессии: инжектит `<div id="probeout">` + скрипт, эмулирующий клик `+`/`−` и снимающий `hits` по canvas) для `file:///...radar.html?lat=57.55&lon=35.03&zoom=8`. Ожидание: после зум-цикла `hits>0` и `canv>=8` на всех шагах (эмулировать: initial, after+, after-).

- [ ] **Step 6: Headless-проверка ленивой загрузки в index.html**

По образцу `probe_idx3.py` (см. сессию): собранный index.html, панель radar скрыта. Ожидание: до активации вкладки `tiles=0`, после активации без зум-клика `canv>=8`, `hits>0`.

- [ ] **Step 7: Полный прогон radar-тестов**

Run: `& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests\test_radar.py -q`
Expected: PASS (7 passed)

- [ ] **Step 8: Commit**

```bash
git add radar_template.html radar.html
git commit -m "fix(radar): invalidate size on 0x0 init, single layer redraw"
```

---

### Task 4: Финальная верификация и интеграция

**Files:**
- Test: `tests/test_radar.py`
- Deploy: GitHub Actions (push main)

**Interfaces:**
- Consumes: все изменения Tasks 1-3.

- [ ] **Step 1: Полный pytest**

Run: `& "F:\Meteo\.venv\Scripts\python.exe" -m pytest -q`
Expected: 2 failed (test_integration, независимая сеть) + остальные PASS. Убедиться, что `tests/test_radar.py` даёт 7 passed.

- [ ] **Step 2: Push main**

```bash
git push origin main
```

- [ ] **Step 3: Дождаться GitHub Actions и проверить успех**

Run: `gh run list --limit 1`
Expected: последний run для push — `completed` / `success`.

- [ ] **Step 4: Live-проверка деплоя**

Run: скачать `https://samlab.github.io/MeteoMap/radar.html` и проверить, что содержит `Облачность`, `Осадки`, `Гроза`, `Град`, `8889bd`, `b80db2`; headless-probe продакшн-URL: `hits>0`.
