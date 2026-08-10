# Radar: OSM подложка как на MopedMap

**Дата:** 2026-08-10
**Статус:** approved

## Проблема

Подложка радара сейчас — `basemaps.cartocdn.com/light_all` с CSS-фильтром
`filter:grayscale(1) brightness(0.72)`. Из-за обесцвечивания названия городов
серые, плохо читаются. Пользователь хочет, чтобы карта выглядела как на
`https://samlab.github.io/MopedMap/` — там стандартная цветная подложка
OpenStreetMap, названия городов на русском и контрастные.

## Решение

Заменить подложку радара на стандартные тайлы OpenStreetMap, убрать серый
фильтр. Ничего больше не менять: оверлей осадков, палитру, таймлайн, легенду,
зум-кнопки, сборку CSS/JS — не трогаем.

### Изменения в `radar_template.html`

1. URL тайл-слоя:
   - было: `https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png`
   - стало: `https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png` (как в MopedMap)
2. Attribution:
   - было: `© OpenStreetMap contributors © CARTO`
   - стало: `© OpenStreetMap contributors`
3. CSS-правило `.lightbase .leaflet-tile{filter:grayscale(1) brightness(0.72)}`
   удалить. `className:'lightbase'` можно оставить (фильтр больше не вешается),
   либо убрать для чистоты — оставляем, безвредно.
4. `maxZoom` подложки оставить 10 (оверлей ограничен `maxNativeZoom:7`, выше
   подложка просто нужна для фона).

### Изменения в `tests/test_radar.py`

- `test_radar_html_is_built_and_self_contained`:
  - `"basemaps.cartocdn.com" in radar` → `"tile.openstreetmap.org" in radar`.
- `test_radar_uses_light_rainradar_theme`:
  - `"light_all" in radar` → `"tile.openstreetmap.org" in radar`.
  - `"grayscale(1) brightness(0.72)" in radar` → assert отсутствия
    `grayscale(1) brightness(0.72)`.
  - `"dark_all" not in radar` и прочие проверки оставить.

### Что не меняем

- Оверлей RainViewer (`RecolorLayer`, `maxNativeZoom:7`, выбор последнего
  past-кадра) — работает, деплоен в `a2c2b14`.
- Палитра rainradar, легенда, таймлайн, зум-кнопки.
- `tools/leaflet.css` инлайн, сборка `build_radar.py`.

## Критерии приёмки

1. `python -m pytest tests/test_radar.py -q` — 5 passed.
2. Headless-скриншот `radar.html?lat=55.8&lon=14.06&zoom=7`: подложка цветная
   OSM, на карте видны пиксели палитры осадков (не только в легенде).
3. В собранном `radar.html` нет `basemaps.cartocdn.com` и нет
   `grayscale(1) brightness(0.72)`.
4. Деплой через GitHub Actions, live-проверка скриншотом.
