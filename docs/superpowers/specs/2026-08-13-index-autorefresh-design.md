# Index: автообновление данных каждые 5 минут

**Дата:** 2026-08-13
**Статус:** approved

## Проблема

Страница https://samlab.github.io/MeteoMap/ загружает данные города один раз
при открытии (`loadCity` → `fetch('data/'+slug+'.json',{cache:'no-cache'})`)
и больше не обновляет их, пока пользователь не перезагрузит вкладку
вручную. Пользователь хочет, чтобы вкладка обновлялась сама каждые 5 минут.

## Решение

Мягкое обновление: каждые 5 минут повторно запрашивать JSON текущего города
и перерисовывать страницу, не трогая состояние вкладки (активная вкладка,
скролл, выбранный город). При ошибке сети/HTTP во время фонового
обновления — молча пропускать цикл (без `alert`), текущие данные остаются.

Правки в `template.html` (исходник; `index.html` пересобирается
`meteo.render()` в CI, вручную не коммитим):

### 1. Тихий режим у `loadCity` (строки 740–749)

```js
async function loadCity(slug,silent){
  try{
    const r=await fetch('data/'+slug+'.json',{cache:'no-cache'});
    if(!r.ok)throw new Error('HTTP '+r.status);
    D=await r.json();
    renderAll();
  }catch(e){
    if(!silent)alert('Не удалось загрузить данные города: '+e.message);
  }
}
```

- Ручной выбор города (`loadCity(c.slug)` в `setupCitySel`) — без `silent`,
  поведение прежнее: alert при ошибке.
- Автообновление вызывает `loadCity(slug,true)` — ошибки молча игнорируются.

### 2. Таймер автообновления (после `setupCitySel();renderAll();`, строка 768–769)

```js
setInterval(()=>loadCity(D.location.slug,true),5*60*1000);
```

- `D.location.slug` — текущий отображаемый город, обновляется после каждого
  `loadCity`. Таймер всегда перезапрашивает именно тот город, что на экране,
  даже если пользователь переключился через меню.
- Не используем `localStorage.getItem('city')`: при старте страница рендерит
  инлайн-данные (`__DATA__` = первый город), а localStorage — только выбор
  через меню. `D.location.slug` всегда отражает реально показанный город.

### Что не меняем

- `meteo.py`, `bot.php`, данные — не трогаем.
- Режим генерации данных (раз в час GitHub Actions) — не меняем; fetch
  использует `cache:'no-cache'`, страница всегда получает свежий JSON.
- `radar.html` / `radar_template.html` — не трогаем.

### Изменения в `tests/test_radar.py`

Добавить тест `test_index_autorefreshes_every_5_minutes`:
- в `template.html` присутствует
  `setInterval(()=>loadCity(D.location.slug,true),5*60*1000)`;
- `loadCity(slug,silent)` и `if(!silent)alert` — тихий режим;
- в сгенерированном `meteo.render(tpl,_payload())` тоже присутствует таймер.

## Критерии приёмки

1. `python -m pytest tests/test_radar.py -q` — 13 passed.
2. Полный `python -m pytest -q` — только 2 известных failed Open-Meteo.
3. Headless-проверка: через 5+ мин (или после ручного триггера)
   происходит fetch `data/<slug>.json` и перерисовка; состояние вкладки
   сохраняется; при ошибке сети alert не появляется.
4. Деплой через GitHub Actions, live-проверка.
