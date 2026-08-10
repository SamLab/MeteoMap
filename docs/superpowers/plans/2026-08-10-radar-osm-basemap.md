# Radar OSM Basemap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Заменить подложку радара на стандартную цветную OSM (как MopedMap), чтобы русские названия городов были читаемыми.

**Architecture:** Меняется только тайл-слой подложки в `radar_template.html` (URL на `{s}.tile.openstreetmap.org`, attribution `© OpenStreetMap contributors`) и удаляется CSS-фильтр `grayscale(1) brightness(0.72)` с `.lightbase .leaflet-tile`. Оверлей RainViewer, палитра, таймлайн не трогаются. Тесты в `tests/test_radar.py` обновляются на новые URL/атрибуты, затем `radar.html` пересобирается через `tools/build_radar.py` и деплоится через GitHub Actions.

**Tech Stack:** Leaflet 1.6.0 (инлайн в radar.html), Python (сборка/тесты), GitHub Pages.

## Global Constraints

- Внешние CDN запрещены в рантайме; Leaflet JS/CSS инлайнятся из `tools/leaflet.js` и `tools/leaflet.css` через `tools/build_radar.py`.
- URL подложки: `https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png` (точно как MopedMap).
- Attribution подложки: `© OpenStreetMap contributors`.
- CSS-правило `.lightbase .leaflet-tile{filter:grayscale(1) brightness(0.72)}` должно быть удалено из `radar_template.html`.
- `bot.php` никогда не коммитить (содержит секрет `BOT_TOKEN`).
- `maxZoom:10` подложки и `maxNativeZoom:7` оверлея остаются без изменений.
- Палитра, легенда, таймлайн, зум-кнопки — не менять.

---

### Task 1: Обновить тесты под OSM-подложку

**Files:**
- Modify: `tests/test_radar.py:42-67`
- Test: `tests/test_radar.py` (весь файл)

**Interfaces:**
- Consumes: существующий собранный `radar.html` (в нём ещё CARTO) — тесты временно упадут, это ожидаемо до Task 2.
- Produces: обновлённые asserts, которые после Task 2 снова пройдут.

- [ ] **Step 1: Изменить два теста**

В `tests/test_radar.py`:

`test_radar_html_is_built_and_self_contained` (строка ~52):
- заменить `assert "basemaps.cartocdn.com" in radar` на `assert "tile.openstreetmap.org" in radar`.

`test_radar_uses_light_rainradar_theme` (строки ~61-64):
- заменить `assert "light_all" in radar` на `assert "tile.openstreetmap.org" in radar`;
- заменить `assert "grayscale(1) brightness(0.72)" in radar` на `assert "grayscale(1) brightness(0.72)" not in radar`;
- строки `assert "dark_all" not in radar`, `assert "#acacac" in radar`, `assert "#415fad" in radar`, палитровый assert, `assert "RecolorLayer" in radar` — оставить без изменений.

- [ ] **Step 2: Прогнать тесты — ожидаем падение 2 тестов**

Run: `python -m pytest tests/test_radar.py -q`
Expected: `3 passed, 2 failed` — упавшие: `test_radar_html_is_built_and_self_contained` (нет `tile.openstreetmap.org`) и `test_radar_uses_light_rainradar_theme` (нет `tile.openstreetmap.org`; `grayscale(1) brightness(0.72)` всё ещё присутствует).

- [ ] **Step 3: Закоммитить изменение тестов (красные тесты)**

```bash
git add tests/test_radar.py
git commit -m "test(radar): expect OSM basemap instead of CARTO light_all"
```

---

### Task 2: Заменить подложку в template и пересобрать

**Files:**
- Modify: `radar_template.html:59-61` (URL и attribution тайл-слоя)
- Modify: `radar_template.html:10-13` (удалить `.lightbase .leaflet-tile` правило)
- Regenerate: `radar.html` (через `python tools/build_radar.py`)

**Interfaces:**
- Consumes: Task 1 (тесты теперь ожидают OSM).
- Produces: `radar_template.html` с OSM-подложкой и `radar.html` без `basemaps.cartocdn.com` / `grayscale(1) brightness(0.72)`.

- [ ] **Step 1: Заменить URL и attribution тайл-слоя**

В `radar_template.html` строки 59-60:

Было:
```js
  L.tileLayer('https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png',{
    maxZoom:10,className:'lightbase',attribution:'© OpenStreetMap contributors © CARTO'
  }).addTo(map);
```

Стало:
```js
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{
    maxZoom:10,className:'lightbase',attribution:'© OpenStreetMap contributors'
  }).addTo(map);
```

- [ ] **Step 2: Удалить серый фильтр**

В `radar_template.html` строку 13 (внутри `<style>`, блок кастомных правил после `/*__LEAFLET_CSS__*/`):
```css
.lightbase .leaflet-tile{filter:grayscale(1) brightness(0.72)}
```
— удалить целиком.

- [ ] **Step 3: Пересобрать radar.html**

Run: `python tools/build_radar.py`
Expected: `[ok] radar.html written (... bytes)`

- [ ] **Step 4: Прогнать тесты — должны пройти**

Run: `python -m pytest tests/test_radar.py -q`
Expected: `5 passed in 0.xx s`

- [ ] **Step 5: Headless-проверка осадков на OSM-подложке**

Запустить проверку скриншотом. Скрипты уже существуют в `C:\Users\SamLab\AppData\Local\Temp\opencode\`. Сначала пересоздать инструментированные копии из пересобранного `radar.html`:

```powershell
& "F:\Meteo\.venv\Scripts\python.exe" "C:\Users\SamLab\AppData\Local\Temp\opencode\make_fs.py"
& "F:\Meteo\.venv\Scripts\python.exe" "C:\Users\SamLab\AppData\Local\Temp\opencode\fix_shots2.py"
& "F:\Meteo\.venv\Scripts\python.exe" "C:\Users\SamLab\AppData\Local\Temp\opencode\fix_analyze.py" "C:\Users\SamLab\AppData\Local\Temp\opencode\fixf0.png"
& "F:\Meteo\.venv\Scripts\python.exe" "C:\Users\SamLab\AppData\Local\Temp\opencode\fix_analyze.py" "C:\Users\SamLab\AppData\Local\Temp\opencode\fixfL.png"
```

`make_fs.py` пишет `radar_f0_new.html` (показывает frame 0) и `radar_fL_new.html` (последний past-кадр); `fix_shots2.py` снимает `fixf0.png`/`fixfL.png` в headless Edge 1366x900; `fix_analyze.py` считает «дождевые» пиксели (палитра осадков) по скриншоту.

Expected: оба скриншота содержат осадки (rainpix >> 0) с разными значениями между кадрами (кадры меняются). Подложка теперь цветная OSM (в доминирующих цветах скриншота появятся цвета OSM-карты, а не только серые тона).

- [ ] **Step 6: Закоммитить**

```bash
git add radar_template.html radar.html
git commit -m "feat(radar): use OSM basemap with readable Russian labels"
```

---

### Task 3: Деплой и live-проверка

**Files:**
- Modify: нет (используется существующий `.github/workflows/deploy.yml`)
- Deploy: `radar.html` через GitHub Actions

**Interfaces:**
- Consumes: Task 2 (закоммиченный `radar.html`).
- Produces: задеплоенная live-версия `https://samlab.github.io/MeteoMap/radar.html` с OSM-подложкой.

- [ ] **Step 1: Пуш в main**

```bash
git push origin main
```

- [ ] **Step 2: Дождаться деплоя**

```bash
gh run list --workflow=deploy.yml --limit 1 --json databaseId,status,conclusion,headSha
gh run watch <run_id> --exit-status --interval 15
```
Expected: job `build-deploy` завершается success.

- [ ] **Step 3: Live-проверка**

Снять headless-скриншот `https://samlab.github.io/MeteoMap/radar.html?lat=55.8&lon=14.06&zoom=7` и прогнать `fix_analyze.py`. Expected: на карте видны пиксели осадков.

Также проверить, что live `radar.html` содержит `tile.openstreetmap.org` и не содержит `basemaps.cartocdn.com`:

```powershell
$r = Invoke-WebRequest -Uri "https://samlab.github.io/MeteoMap/radar.html" -UseBasicParsing
$c = $r.Content
Write-Output ("has_osm: " + ($c -match "tile\.openstreetmap\.org"))
Write-Output ("no_carto: " + (-not ($c -match "basemaps\.cartocdn\.com")))
Write-Output ("no_grayscale: " + (-not ($c -match "grayscale\(1\) brightness\(0\.72\)")))
```
Expected: все три — `True`.

- [ ] **Step 4: Итоговый коммит-состояние**

Убедиться, что `bot.php` не закоммичен: `git status --short` — среди изменённых файлов `bot.php` быть не должно.
