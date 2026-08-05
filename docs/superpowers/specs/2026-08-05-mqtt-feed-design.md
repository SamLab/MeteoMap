# Дизайн: MQTT-фид погоды MeteoMap

Дата: 2026-08-05
Статус: утверждено

## Цель

Отдавать данные погоды MeteoMap в MQTT-брокер третьему лицу. Подписчик получает пять топиков: текущие условия, прогноз на +3/+6/+12 часов и ближайшие осадки (дождь/гроза/град). Данные публикуются из GitHub Actions по расписанию — без постоянного процесса и без участия пользователя.

## Архитектура

```
GitHub Actions (cron, каждые 30 мин)
   └─▶ python mqtt_publish.py
         ├─▶ GET https://samlab.github.io/MeteoMap/index.html  (данные сайта)
         ├─ парсинг JSON из <script id="data" type="application/json">
         ├─ сборка 5 JSON-документов
         └─▶ MQTT publish (retain=true) → tcp://yar.gorod76.ru:1883
               city/out/pogoda/now
               city/out/pogoda/3
               city/out/pogoda/6
               city/out/pogoda/12
               city/out/pogoda/rain
```

- Брокер: `yar.gorod76.ru:1883`, TCP, **без логина/пароля** (проверено: порт открыт из интернета, DNS 212.232.62.200).
- Секреты GitHub не нужны — хост, порт и префикс топиков прописаны в workflow.
- `retain=true`: новый подписчик сразу получает последнее значение каждого топика.

## Топики и JSON

Префикс: `city/out/pogoda`. Все времена московские, ISO-8601 с `+03:00`.

### `city/out/pogoda/now` — текущие условия

```json
{
  "temperature": 23.4,
  "feels_like": 23.1,
  "weather": "Ясно",
  "wind_speed": 3.2,
  "wind_dir": "СЗ",
  "pressure": 753,
  "humidity": 45,
  "updated_at": "2026-08-05T12:50:42+03:00"
}
```

- `temperature`, `feels_like` — °C, 1 знак (как `fmt` на сайте).
- `weather` — текст погодного кода (как WCODE на сайте, например «Ясно», «Переменная облачность»).
- `wind_speed` — м/с, 1 знак; `wind_dir` — румб (`С/СВ/В/ЮВ/Ю/ЮЗ/З/СЗ`).
- `pressure` — мм рт. ст., целое.
- `humidity` — %, целое.
- `updated_at` — время публикации (момент сборки на GitHub Actions, Москва).

### `city/out/pogoda/3`, `/6`, `/12` — прогноз на горизонт

Одна схема, отличается `horizon_h` и `time`:

```json
{
  "horizon_h": 3,
  "time": "2026-08-05T15:00+03:00",
  "temperature": 22.1,
  "weather": "Переменная облачность",
  "precip_mm": 0.1,
  "precip_prob": 32,
  "wind_speed": 4.1,
  "wind_dir": "З",
  "updated_at": "2026-08-05T12:50:42+03:00"
}
```

- `time` — час прогноза (curIdx + horizon_h).
- `precip_mm` — мм, 1 знак; `precip_prob` — %, целое (0–100).
- Если горизонт выходит за пределы данных (последний час ряда) — горизонт пропускается (в топик пишется `{}` с `horizon_h`).

### `city/out/pogoda/rain` — ближайшие осадки

```json
{
  "rain": {
    "time": "2026-08-06T19:00+03:00",
    "precip_mm": 0.1,
    "probability": 32,
    "models": 5
  },
  "thunder": {
    "time": "2026-08-07T10:00+03:00",
    "precip_mm": 0.4,
    "probability": 11,
    "sources": ["UKMO Global"]
  },
  "hail": {
    "time": "2026-08-07T16:00+03:00",
    "precip_mm": 1.1,
    "probability": 59,
    "sources": ["DWD ICON"]
  }
}
```

- `rain` — ближайший час от curIdx с дождём по консенсусу `weighted.weather_code` (коды `[51,53,55,56,57,61,63,65,66,67,80,81,82]`); `models` — число моделей с таким кодом в этот час.
- `thunder` — первый час, где хоть у одной модели код в `[95,96,99]`; `sources` — имена моделей через « и ».
- `hail` — первый час, где хоть у одной модели код в `[96,99]`; `sources` — имена моделей.
- Если события нет до конца ряда — поле `null`.
- Логика и форматы идентичны боту (`build_16_line`) и заголовку «На 16 дней» сайта.

## Данные

- Источник: `https://samlab.github.io/MeteoMap/index.html` (JSON в `<script id="data" type="application/json">`, ~506 КБ).
- Парсинг: как в боте — вырезать JSON между `id="data" type="application/json">` и `</script>` через `strpos`/`substr`.
- `curIdx` = первый индекс `D.time[t] >= nowLocal` по Москве.
- Поля payload: `D.time`, `D.weighted` (`temperature_2m`, `apparent_temperature`, `precipitation`, `precipitation_probability`, `pressure_msl`, `relative_humidity_2m`, `wind_speed_10m`, `wind_direction_10m`, `weather_code`), `D.models`, `D.model_codes`, `D.model_names`.
- Давление: `HPA_TO_MMHG = 0.750061683`, округлить до целого.

## Файлы

- `.github/workflows/mqtt.yml` — cron `*/30 * * * *`; шаги: checkout, `pip install paho-mqtt`, запуск `mqtt_publish.py`.
- `mqtt_publish.py` — весь скрипт: загрузка index.html, парсинг, сборка JSON, публикация с retain.
- `tests/test_mqtt.py` — тесты логики (фикстура данных, как в тестах бота; реальная публикация не выполняется).

## Тестирование

- `tests/test_mqtt.py`: парсинг index.html, сборка каждого документа на фикстуре, соответствие значений сайту/боту, edge-case «события нет → null».
- Локальный прогон: `.venv\Scripts\python.exe` pytest (данные качаются из локального файла-фикстуры, брокер не задействуется).
- Публикация проверяется реальным прогоном workflow в GitHub (журнал Actions) и подпиской на брокер.

## Ошибки

- index.html недоступен / JSON не распарсился → публикация не выполняется, workflow падает с понятной ошибкой (журнал Actions).
- Мелкая задержка данных (retain хранит последний снапшот) допустима.

## Вне объёма (YAGNI)

- Текстовые версии топиков — только JSON.
- Логин/пароль брокера — брокер без авторизации.
- HTTP API с параметром — не делаем.
- Несколько городов — только Ярославль.
- Частота публикации быстрее 30 минут — только по запросу.
