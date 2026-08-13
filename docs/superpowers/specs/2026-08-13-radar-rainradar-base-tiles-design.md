# Radar: подложка дорог/рек как на rainradar (/tiles?z=)

**Дата:** 2026-08-13
**Статус:** approved

## Проблема

В предыдущем изменении (gray-background) подложку радара убрали целиком —
остался только серый фон `#acacac`. Пользователь заметил, что на rainradar.ru
дороги и реки видны, а у нас — нет.

Исследование показало: дороги/реки на rainradar даёт их собственный слой
`https://rainradar.ru/tiles?z={z}&x={x}&y={y}` (`tms:true`, `minZoom:3`,
`maxZoom:10`, `zIndex:998`). Тайлы — полупрозрачные тёмные линии (на z8 32%
пикселей непрозрачны, статичны, цветных осадков не содержат). Поверх этого
слоя рисуются осадки (canvas RadarLayer) и белые подписи.

## Решение

Добавить в `radar_template.html` базовый тайл-слой rainradar. Исследование
живого rainradar показало: их подложка подключается с `zIndex:998` и лежит
ПОВЕРХ canvas-осадков (RadarLayer GridLayer с дефолтным zIndex 1, оба в
tile-pane). Полупрозрачные тёмные линии дорог/рек поверх полупрозрачных
облаков (палитра alpha 0–1) дают эффект «дороги и реки видно сквозь облака».

```js
L.tileLayer('https://rainradar.ru/tiles?z={z}&x={x}&y={y}',{
  tms:true,minZoom:3,maxZoom:10,zIndex:998
}).addTo(map);
```

Порядок слоёв сверху вниз: подписи (pane z900) → молнии (pane z400) →
подложка `/tiles?z=` (zIndex 998 внутри tile-pane 200) → осадки (canvas
GridLayer zIndex 1) → фон `#acacac`. Тайлы подложки прозрачны, кроме тёмных
линий дорог/рек, поэтому они просвечивают поверх осадков, как на rainradar.

### Что не меняем

- CSS фон `#map{background:#acacac}` — остаётся.
- Оверлей осадков (composite + RadarLayer), LabelsLayer, молнии, таймлайн,
  легенда — не трогаем.
- `basemaps.cartocdn.com` / `tile.openstreetmap.org` — по-прежнему отсутствуют.

### Изменения в `tests/test_radar.py`

- `test_radar_html_is_built_and_self_contained`: добавить проверки
  `"rainradar.ru/tiles?z={z}&x={x}&y={y}" in radar` и `"tms:true" in radar`;
  существующие проверки отсутствия cartocdn/osm оставить.
- Переименовать `test_radar_has_gray_background_without_basemap` →
  `test_radar_has_rainradar_base_below_gray_background`:
  - фон `#acacac` в шаблоне;
  - базовая подложка `rainradar.ru/tiles?z=` присутствует, `tms:true`,
    `zIndex:998` (поверх осадков, как на rainradar);
  - `basemaps.cartocdn.com` и `tile.openstreetmap.org` отсутствуют.

## Критерии приёмки

1. `python -m pytest tests/test_radar.py -q` — 11 passed.
2. Полный `python -m pytest -q` — только 2 известных failed Open-Meteo.
3. Headless-проверка: подложка грузится (`rainradar.ru/tiles?z=` IMG-тайлы),
   лежит ПОВЕРХ canvas-осадков (zIndex 998 vs 1), фон `rgb(172,172,172)`,
   дороги/реки видны сквозь облака.
4. Деплой через GitHub Actions, live-проверка.
