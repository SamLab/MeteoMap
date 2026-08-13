# Index: вкладка «Часы», пунктирные max/min-строки, «Далее »

**Дата:** 2026-08-13
**Статус:** approved

## Проблема

1. В таблице сравнения моделей по часам текущий час выделен сплошной рамкой
   (`tr.now`), но пользователь не видит, в какие часы текущих суток ожидается
   максимум и минимум выбранного параметра.
2. Вкладка называется «Сравнение», пользователь хочет название «Часы».
3. Текст «Дальше ...» в заголовке часов пользователь хочет заменить на
   «Далее ...».

## Решение

Правки в `template.html` (исходник; `index.html` пересобирается
`meteo.render()` в CI, вручную не коммитим):

### 1. Пунктирные max/min-строки в `buildCmpTable` (строки 644–670)

Для каждой строки текущих суток считается максимум (`mx`) и минимум (`mn`)
значений среди всех моделей (как в существующей логике `td.ext`). Затем по
всем строкам текущих суток ищется глобальный максимум из `mx` (`idxMx`) и
глобальный минимум из `mn` (`idxMn`). Строкам с этими индексами добавляются
классы `mxrow` / `mnrow` в дополнение к существующему `now`.

Первый проход перед `rows`:

```js
const today=D.time[curIdx]?.slice(0,10)||'';
let idxMx=-1,idxMn=-1,gmx=-Infinity,gmn=Infinity;
D.time.forEach((t,i)=>{
  if(!isWc&&t.slice(0,10)===today){
    const vals=codes.map(c=>D.models[c]?D.models[c][cmpVar]?.[i]:undefined);
    const nums=vals.filter(v=>typeof v==='number');
    if(nums.length){
      const mx=Math.max(...nums),mn=Math.min(...nums);
      if(mx>gmx){gmx=mx;idxMx=i;}
      if(mn<gmn){gmn=mn;idxMn=i;}
    }
  }
});
```

- `weather_code` пропускаем (категориальный, как в существующей логике `ext`).
- Если max и min приходятся на один час — строка получает оба класса
  (`mxrow mnrow`), это допустимо.
- Если в текущих сутках нет данных — `idxMx=idxMn=-1`, классы не применяются.

Строка 667 (генерация `tr`):

```js
return `<tr class="${i===curIdx?'now':''}${i===idxMx?' mxrow':''}${i===idxMn?' mnrow':''}">${cells}</tr>`;
```

CSS после строки 74:

```css
tr.mxrow td{border-top:2px dashed #d32f2f;border-bottom:2px dashed #d32f2f}
tr.mnrow td{border-top:2px dashed #1976d2;border-bottom:2px dashed #1976d2}
```

### 2. «Сравнение» → «Часы»

- Строка 132: `<button data-tab="compare">Часы</button>`
- Строка 186: `<h2>Часы</h2>`

### 3. «Дальше » → «Далее »

- Строка 351: `th.textContent='Далее '+parts.join(', ')`

### Что не меняем

- `meteo.py`, `bot.php`, данные — не трогаем.
- Вкладки weather/radar, `radar_template.html` — не трогаем.
- Логику `td.ext` (жирные экстремумы в строке) и `tr.now` — не трогаем,
  max/min-строки добавляются в дополнение к ним.

### Изменения в `tests/test_radar.py`

- Обновить существующий ассерт «Дальше» на «Далее».
- Новый тест `test_compare_rows_highlight_day_max_min`:
  - CSS-правила `tr.mxrow td` и `tr.mnrow td` с `dashed` и цветами
    `#d32f2f`/`#1976d2`;
  - в `buildCmpTable` есть расчёт `today`, `gmx`/`gmn` по строкам текущих
    суток (`t.slice(0,10)===today`) и применение классов `mxrow`/`mnrow`.
- Новый тест `test_compare_tab_named_chasy`:
  - кнопка `data-tab="compare"` с текстом «Часы»;
  - `<h2>Часы</h2>`.

## Критерии приёмки

1. `python -m pytest tests/test_radar.py -q` — 14 passed.
2. Полный `python -m pytest -q` — только 2 известных failed Open-Meteo.
3. Headless-проверка: в таблице «Часы» у строк текущих суток с глобальным
   max/min среди моделей пунктирные границы (max — красная, min — синяя),
   текущий час сохраняет `tr.now`; заголовок h2 «Часы»; «Далее ...».
4. Деплой через GitHub Actions, live-проверка.
