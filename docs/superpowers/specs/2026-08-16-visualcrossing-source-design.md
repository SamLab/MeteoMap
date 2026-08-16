# Visual Crossing (VC) как внешний источник

Дата: 2026-08-16

## Цель

Подключить Visual Crossing (https://www.visualcrossing.com/) как ещё один внешний
источник почасовых данных в конвейер MeteoMap. Участие — только в почасовом
консенсусе и таблице «Часы», как у существующих OpenWeather и WeatherAPI.

## Предпосылки (проверено 2026-08-16)

- Free-тариф Visual Crossing: 1000 записей/день. Запрос 15-дневного прогноза с
  `include=hours` на одну локацию стоит `queryCost=1` (проверено на ключе
  пользователя). При почасовой генерации 4 города × 24 раза в день = 96
  запросов/день — в пределах лимита.
- API отдаёт почасовые данные на 15 дней для всех 4 локаций проекта
  (Ярославль, Балакирево, Цеденево, Москва), tzoffset=3 (UTC+3).
- Поля в ответе `days[].hours[]`: `datetimeEpoch` (UTC), `temp`, `feelslike`,
  `dew`, `humidity`, `precip`, `precipprob`, `preciptype`, `snow`, `windspeed`,
  `winddir`, `windgust`, `pressure`, `visibility`, `cloudcover`, `conditions`,
  `icon`.
- Иконки `icon` в реальных ответах для наших локаций: `clear-day`,
  `clear-night`, `partly-cloudy-day`, `partly-cloudy-night`, `cloudy`, `rain`.
  Полный набор возможных значений: `clear-day`, `clear-night`, `partly-cloudy-day`,
  `partly-cloudy-night`, `cloudy`, `rain`, `snow`, `fog`, `wind`, `thunderstorm`,
  `sleet`, `hail`, `showers-day`, `showers-night`, `thunder-rain`,
  `thunder-showers-day`, `thunder-showers-night`, `rain-snow`, `rain-snow-showers-day`,
  `rain-snow-showers-night`, `snow-showers-day`, `snow-showers-night`.
- Максимальный горизонт прогноза — 15 дней (не 16). Дневной блок «На 16 дней»
  внешними источниками не заполняется — это существующее поведение для всех
  внешних провайдеров, менять не требуется.

## Обозначения

- Код модели: `vc`
- Имя модели: `VC` (показывается в таблицах и attribution)
- Переменная окружения для ключа: `VISUALCROSSING_KEY`

## Изменения в meteo.py

### 1. Константы

После блока WEATHERAPI-констант (после `WEATHERAPI_NAME = "WeatherAPI"`):

```python
VC_URL = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/"
VC_CODE = "vc"
VC_NAME = "VC"
```

### 2. Маппинг icon -> WMO

```python
# Visual Crossing icon -> WMO
VC_WMO = {
    "clear-day": 0, "clear-night": 0,
    "partly-cloudy-day": 2, "partly-cloudy-night": 2,
    "cloudy": 3,
    "fog": 45, "wind": 45,
    "rain": 61, "showers-day": 80, "showers-night": 80,
    "rain-snow": 66, "rain-snow-showers-day": 67, "rain-snow-showers-night": 67,
    "sleet": 66,
    "snow": 71, "snow-showers-day": 85, "snow-showers-night": 85,
    "hail": 96,
    "thunderstorm": 95, "thunder-rain": 95,
    "thunder-showers-day": 95, "thunder-showers-night": 95,
}
```

### 3. Функция fetch_vc

По образцу `fetch_weatherapi` (метео.py:374-425), после неё:

```python
def fetch_vc(lat=None, lon=None, api_key=None):
    """Visual Crossing 15-day hourly forecast -> строки YR-подобного вида."""
    if lat is None:
        lat = LOCATIONS[0]["lat"]
    if lon is None:
        lon = LOCATIONS[0]["lon"]
    key = api_key or os.environ.get("VISUALCROSSING_KEY")
    if not key:
        print("[warn] VISUALCROSSING_KEY not set, skipping VC")
        return []
    params = {"key": key, "unitGroup": "metric", "include": "hours"}
    url = VC_URL + f"{lat}%2C{lon}"
    resp = request_with_retry(url, params, timeout=30)
    ...
```

Особенности:
- URL строится как `VC_URL + "57.63%2C39.87"`, параметры передаются словарём в
  `request_with_retry(url, params, timeout=30)` (requests сам закодирует query).
- Парсинг:
  - для каждого `day in resp.get("days", [])`, для каждого `hour in day.get("hours", [])`:
    - `utc = datetime.fromtimestamp(hour["datetimeEpoch"], tz=timezone.utc)`
    - `weather_code = VC_WMO.get(hour.get("icon"))`
    - `temperature_2m = hour.get("temp")`
    - `apparent_temperature = hour.get("feelslike")`
    - `dew_point_2m = hour.get("dew")`
    - `relative_humidity_2m = hour.get("humidity")`
    - `precipitation = hour.get("precip")`
    - `precipitation_probability = hour.get("precipprob")`
    - `pressure_msl = round(pressure * HPA_TO_MMHG, 1) if pressure is not None else None`
    - `cloud_cover = hour.get("cloudcover")`
    - `wind_speed_10m = round(windspeed / 3.6, 2) if windspeed is not None else None` (км/ч -> м/с)
    - `wind_direction_10m = hour.get("winddir")`
    - `wind_gusts_10m = round(windgust / 3.6, 2) if windgust is not None else None`
    - `visibility = round(visibility * 1000) if visibility is not None else None` (км -> м)
  - вернуть rows (список dict с ключом "utc")

### 4. Регистрация в EXTERNAL_MODELS

```python
EXTERNAL_MODELS = [
    (WEATHERAPI_CODE, WEATHERAPI_NAME, fetch_weatherapi),
    (OWM_CODE, OWM_NAME, fetch_owm),
    (VC_CODE, VC_NAME, fetch_vc),
]
```

Это автоматически даёт:
- параллельную загрузку через `fetch_external_providers` по всем городам,
- попадание в `hourly_by_model` и часовой консенсус (через `align_to_grid`),
- отображение в таблице «Часы» и attribution,
- минимальный вес (MAE нет — нет архива прогнозов; как GEFS/AIFS),
- активацию только при `ENABLE_EXTERNAL=1`.

## Изменения в справке (template.html)

В блоке «Источники данных» в списке внешних источников (строка 225) добавить:

```
<b>Visual Crossing (VC)</b>
```

## Ключ

- Переменная окружения `VISUALCROSSING_KEY` (не коммитится).
- В GitHub Actions: секрет `VISUALCROSSING_KEY`, в `deploy.yml` добавить
  `VISUALCROSSING_KEY: ${{ secrets.VISUALCROSSING_KEY }}` рядом с
  `ENABLE_EXTERNAL`.
- Локально: пользователь задаёт переменную окружения перед запуском meteo.py.

## Тесты (tests/test_external.py)

1. `test_fetch_vc_parses_hourly` — мок ответа (2 часа одного дня), проверить:
   - utc по datetimeEpoch,
   - конверсии: windspeed км/ч -> м/с (13.0 -> 3.61), windgust, visibility км -> м,
   - pressure mbar -> мм рт.ст.,
   - weather_code по icon (например "rain" -> 61),
   - precipitation_probability.
2. `test_fetch_vc_requires_key` — без ключа возвращает [] и печатает warn (как
   `test_fetch_weatherapi_requires_key`).
3. `test_external_models_registry` — дополнить: в EXTERNAL_MODELS присутствует
   `vc` (существующий тест, строка 31-...).
4. `test_render_attribution_includes_external_sources` — дополнить: содержит
   "visualcrossing.com".

## Верификация

- `python -m pytest tests/ -m "not integration" -q` — зелёный.
- Локально с `ENABLE_EXTERNAL=1` и ключом: в `data/yaroslavl.json` присутствует
  `vc` в `model_codes` и `models`, с реальными почасовыми значениями.
- После деплоя: на сайте в таблице «Часы» и attribution появляется VC.

## Что не делаем (scope-out)

- Архив прогнозов / MAE для VC (платная опция Historical Forecast).
- Дневной блок «На 16 дней» — внешние источники туда не попадают.
- Meteoblue — отдельная задача.
