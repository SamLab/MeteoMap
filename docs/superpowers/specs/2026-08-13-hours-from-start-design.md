# Index: префикс «С HH:MM» в заголовке часов вместо «Далее»

**Дата:** 2026-08-13
**Статус:** approved

## Проблема

Заголовок часов «Далее без дождя, до +13° в 18:00 и +12° в 23:00» начинается
со слова «Далее», но пользователь хочет видеть, с какого часа начинается
отсчёт: «С 17:00 без дождя, до +13° в 18:00 и +12° в 23:00».

## Решение

Правки в `template.html` (исходник; `index.html` пересобирается
`meteo.render()` в CI, вручную не коммитим):

В `buildWeatherHours` (строка ~353) заменить префикс:

```js
// было
th.textContent='Далее '+parts.join(', ');
// стало
th.textContent='С '+D.time[hs].slice(11,16)+' '+parts.join(', ');
```

- `hs` уже вычислен (`const hs=Math.min(curIdx+1,D.time.length-1);`) — это час,
  с которого начинается расчёт заголовка. В примере пользователя «17:00» —
  это и есть следующий час.
- Остальные части заголовка (дождь, max/min) не меняются.

### Что не меняем

- `meteo.py`, `bot.php`, данные — не трогаем.
- Логику расчёта `parts`, `rainHour`, `tiMax/tiMin`, ленту часов — не трогаем.

### Изменения в `tests/test_radar.py`

В `test_hours_title_uses_remaining_today_window` заменить ассерт
`th.textContent='Далее '+parts.join(', ')` на
`th.textContent='С '+D.time[hs].slice(11,16)+' '+parts.join(', ')`.

## Критерии приёмки

1. `python -m pytest tests/test_radar.py -q` — все passed.
2. Полный `python -m pytest -q` — только 2 известных failed Open-Meteo.
3. Headless-проверка: заголовок вида «С 17:00 без дождя, до +13° в 18:00 и +12° в 23:00»,
   где «17:00» = `D.time[hs].slice(11,16)`.
4. Деплой через GitHub Actions, live-проверка.
