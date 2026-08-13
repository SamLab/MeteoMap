# Radar: убрать чёрные подписи OSM — подложка CartoDB light_nolabels

**Дата:** 2026-08-13
**Статус:** approved

## Проблема

Подложка радара — стандартные тайлы OpenStreetMap (`{s}.tile.openstreetmap.org`),
на которых города/сёла подписаны чёрным текстом. Эти подписи перекрываются
оверлеем осадков и конфликтуют с белыми подписями поверх облаков (фича
`6a12f25`/`ea7f838`, слой `LabelsLayer`). Пользователь хочет убрать чёрные
подписи OSM, оставив светлую подложку с дорогами/реками/границами и белые
подписи городов поверх облаков.

## Решение

Заменить подложку OSM на **CartoDB `light_nolabels`** — тот же стиль, что
`light_all` раньше, но без текстового слоя подписей.

### Изменения в `radar_template.html`

1. URL тайл-слоя (строка 71):
   - было: `https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png`
   - стало: `https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}.png`
2. Attribution:
   - было: `© OpenStreetMap contributors`
   - стало: `© OpenStreetMap contributors © CARTO` (требование CartoDB)
3. Остальное не меняем: `className:'lightbase'`, `maxZoom:10`, `{s}` (Leaflet
   сам подставит `a`/`b`/`c`), оверлеи, `LabelsLayer`, таймлайн.

Примечание: subdomain `{s}` у CartoDB — `a`/`b`/`c` (как у OSM `a`/`b`/`c`),
Leaflet по умолчанию использует `abc`, ничего настраивать не нужно.

### Изменения в `tests/test_radar.py`

- `test_radar_html_is_built_and_self_contained` (строка 53):
  - `"tile.openstreetmap.org" in radar` → `"basemaps.cartocdn.com/light_nolabels" in radar`.
- Там же: assert атрибуции `© OpenStreetMap contributors © CARTO` в `radar.html`.

### Что не меняем

- `LabelsLayer` (белые подписи поверх облаков) и его стили.
- Оверлей RainViewer, молнии, палитра, легенда, таймлайн, зум-кнопки.
- `tools/leaflet.css`, сборка `build_radar.py`, `bot.php`.

## Критерии приёмки

1. `python -m pytest tests/test_radar.py -q` — весь набор radar (9 тестов) passed.
2. Полный `python -m pytest -q` — только 2 известных failed Open-Meteo.
3. В собранном `radar.html` URL подложки `basemaps.cartocdn.com/light_nolabels`,
   нет `tile.openstreetmap.org`.
4. Headless-скриншот (CDP) `radar.html?lat=55.75&lon=37.62&zoom=8`: подложка
   светлая, чёрных подписей городов нет, белые подписи поверх облаков на месте.
5. Деплой через GitHub Actions, live-проверка.
