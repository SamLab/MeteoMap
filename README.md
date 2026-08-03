# MeteoMap

Сравнение погодных моделей и усреднённый прогноз для Ярославля.

- Источник: [Open-Meteo](https://open-meteo.com/) (CC BY 4.0)
- Обновление: раз в час (GitHub Actions, запуск через cron-job.org)
- Модели: ECMWF IFS/AIFS, NOAA GFS, DWD ICON, GEM, UKMO, ARPEGE, JMA GSM, KMA GDPS, ACCESS-G, GRAPES, GEFS, WeatherNext 2
- Консенсус: взвешенный по MAE (7/30 дней) + простое среднее/медиана. Модели без архивных данных (AIFS, ACCESS-G, GDPS, GEFS) получают средний вес остальных.

## Локальный запуск

```bash
pip install -r requirements.txt
python meteo.py
# открыть index.html
```

## Тесты

```bash
python -m pytest tests/ -m "not integration" -q   # юнит
python -m pytest tests/ -m integration -q          # интеграционные (реальный API)
```
