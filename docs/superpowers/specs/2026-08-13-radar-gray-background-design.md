# Radar: серый фон как на rainradar (без подложки)

**Дата:** 2026-08-13
**Статус:** approved

## Проблема

Подложка радара — CartoDB `light_nolabels` (светлая карта с дорогами и реками).
На rainradar.ru подложки нет: фон `rgb(172,172,172)` (#acacac), поверх — тайлы
осадков и подписи. Пользователь хочет так же.

## Решение

Убрать тайл-слой CartoDB, оставить серый фон `#acacac` (уже задан в CSS шаблона,
строка 11: `#map{position:absolute;inset:0;background:#acacac}`).

### Изменения в `radar_template.html`

Удалить блок (строки 71-73):

```js
L.tileLayer('https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}.png',{
  maxZoom:10,className:'lightbase',attribution:'© OpenStreetMap contributors © CARTO'
}).addTo(map);
```

Атрибуция CartoDB/OSM удаляется вместе с подложкой.

### Что не меняем

- Оверлей осадков (CANVAS `RecolorLayer`, manifest rainradar), молнии
  (IMGTileLayer lightningmaps), белые подписи `LabelsLayer` (z900), таймлайн,
  легенду, зум-кнопки.
- CSS `#map` фон `#acacac` — уже есть, не трогаем.

### Изменения в `tests/test_radar.py`

- `test_radar_html_is_built_and_self_contained`:
  - `"basemaps.cartocdn.com/light_nolabels" in radar` →
    `"basemaps.cartocdn.com" not in radar`;
  - `"© OpenStreetMap contributors © CARTO" in radar` → проверка фона
    `"#map{position:absolute;inset:0;background:#acacac}" in radar`.
- Новый `test_radar_has_gray_background_without_basemap`:
  - фон `#acacac` в шаблоне; `basemaps.cartocdn.com` и `tile.openstreetmap.org`
    отсутствуют.

## Критерии приёмки

1. `python -m pytest tests/test_radar.py -q` — 11 passed.
2. Полный `python -m pytest -q` — только 2 известных failed Open-Meteo.
3. Headless-проверка: фон карты `rgb(172,172,172)`, 0 carto-тайлов, осадки —
   canvas `leaflet-tile-loaded`, молнии грузятся, подписи белые 167 шт, z900.
4. Деплой через GitHub Actions, live-проверка.
