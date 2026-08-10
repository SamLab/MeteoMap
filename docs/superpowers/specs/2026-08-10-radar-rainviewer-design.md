# Радар осадков (RainViewer) в MeteoMap — дизайн

Дата: 2026-08-10

## Цель

Добавить в MeteoMap вкладку «Радар» с картой осадков в реальном времени: текущий кадр, история за ~2 часа и прогноз на ~2 часа вперёд (если RainViewer отдаёт nowcast).

## Итог исследования источников

- rainradar.ru — вторичный источник; его кадры по таймстампам и геометрии совпадают с официальным RainViewer API. ToS/лицензии на сайте нет, поэтому использовать его как источник не рекомендуется.
- RainViewer API (`https://api.rainviewer.com/public/weather-maps.json`) и тайлы (`https://tilecache.rainviewer.com/...`) доступны из РФ (HTTP 200), CORS `Access-Control-Allow-Origin: *`. Заблокирован только сам сайт rainviewer.com, поэтому iframe их встроенной страницы не работает — данные тянем в браузере напрямую.
- Тайлы RainViewer — готовые RGBA-картинки 256×256 с встроенной дождевой палитрой (значение = интенсивность), формат:
  `{host}/v2/radar/{path}/256/{z}/{x}/{y}/2/1_1.png`
- Манифест: `{"radar": {"past": [{"time": ..., "path": ...}, ...], "nowcast": [...]}}`. Шаг кадров 10 мин. Сейчас `nowcast` пуст (13 кадров истории).

## Архитектура

```
Пользователь
   │  (вкладка «Радар» в index.html)
   ▼
#tab-radar  ── <iframe> ──► radar.html (GitHub Pages)
                              │
            ┌─────────────────┼─────────────────────┐
            ▼                 ▼                     ▼
   api.rainviewer.com   tilecache.rainviewer.com   basemaps.cartocdn.com
   (манифест кадров)    (тайлы осадков RGBA)       (тёмная подложка OSM)
```

- `radar.html` — новая статичная страница, собирается в `_site/` тем же пайплайном, что и `index.html`. Никаких новых workflows, secrets, cron-задач.
- Leaflet 1.6.0 инлайнится в `radar.html` (источник: bundle rainradar.ru, чистый Leaflet, BSD-2-Clause). Внешних CDN-библиотек нет (подложка и тайлы — это данные, а не библиотеки).
- Всё тянется браузером пользователя напрямую: манифест, тайлы осадков, подложка.

## Пользовательский интерфейс

- Вкладка «Радар» в шапке сайта: `<button data-tab="radar">Радар</button>`, между «Прогноз» и «Сравнение».
- Панель `#tab-radar` содержит `<iframe id="radar-frame" src="radar.html?lat=..&lon=..&zoom=8">`. Координаты — от выбранного города; при смене города src перестраивается.
- iframe растягивается на всю панель (`width:100%; height:100%; border:0`).

### Страница radar.html (тёмная тема)

- Leaflet-карта, зум 1–10, старт: центр = переданные lat/lon, zoom=8.
- Подложка: `basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png` (тёмная, на данных OSM). Attribution: `© OpenStreetMap contributors © CARTO`.
- Оверлей осадков: `L.tileLayer` по URL `https://tilecache.rainviewer.com/v2/radar/{path}/256/{z}/{x}/{y}/2/1_1.png` с подстановкой `{path}` кадра. Attribution: `© RainViewer`.
- Нижняя панель таймлайна: play/pause, ползунок 0..N-1, подпись времени кадра (мск). При загрузке — последний кадр past (текущий), без автоплея.
- Вертикальная легенда интенсивности 0–60+ (дождевые цвета).
- Индикатор статуса: «Загрузка…», «Радар недоступен» (+ ретрай каждые 30 с).

## Данные и обновление

- `fetch('https://api.rainviewer.com/public/weather-maps.json?t=' + Date.now())` — cache-bust.
- `frames = [...radar.past, ...radar.nowcast]`, `isFuture` для nowcast-кадров.
- Текущий кадр — последний `past`.
- Смена кадра — `tileLayer.setUrl(...)` (браузер кеширует тайлы).
- Автообновление манифеста каждые 5 мин: перестроить таймлайн, сохранить позицию текущего.
- Пустой nowcast → секция «вперёд» скрыта (автоматически появится, когда RainViewer начнёт отдавать прогноз).
- Тайл кадра 404 (кадр удалён) → оверлей пустой, показать ближайший доступный кадр.

## Деплой

- В `deploy.yml` в шаг «Prepare pages artifact» добавить `cp radar.html _site/`.
- Никаких новых secrets, permissions, workflows.

## Тестирование

- Юнит-тест генерации: в `index.html` присутствует вкладка `data-tab="radar"`, iframe `#radar-frame` с координатами текущего города; `radar.html` создаётся в `_site/`.
- Headless-проба (Edge, как для скроллбара): открыть `radar.html` → карта и таймлайн рендерятся, тайлы с tilecache и подложка загружаются (нет CORS-ошибок), манифест парсится, слайдер работает.

## Атрибуция и лицензии

- Leaflet — BSD-2-Clause.
- OpenStreetMap данные — ODbL (attribution обязателен): `© OpenStreetMap contributors`.
- CartoDB — attribution: `© OpenStreetMap contributors © CARTO`.
- RainViewer — бесплатно с attribution: `© RainViewer`.
