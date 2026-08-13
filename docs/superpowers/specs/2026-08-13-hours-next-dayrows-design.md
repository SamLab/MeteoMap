# Index: «Далее» со следующего часа + разделение суток и max/min в «Часы»

**Дата:** 2026-08-13
**Статус:** approved

## Проблема

1. Заголовок часов «Далее дождь в 16:00, до +13° в 18:00 и +12° в 23:00»
   считает события начиная с текущего часа `curIdx`. Пользователь хочет,
   чтобы учитывался следующий час (не текущий).
2. В таблице «Часы» (вкладка compare) max/min-обводка считается только для
   текущих суток, а сами сутки не разделены визуально. Пользователь хочет:
   строки-заголовки с датой между сутками и обводку max/min для каждых суток.

## Решение

Правки в `template.html` (исходник; `index.html` пересобирается
`meteo.render()` в CI, вручную не коммитим):

### 1. Заголовок «Далее ...» — со следующего часа

В `buildWeatherHours` (строки 326–353): лента часов остаётся от `curIdx`,
а расчёт заголовка (max/min, дождь) сдвигается на следующий час:

```js
const start=curIdx;                                  // лента — без изменений
const hs=Math.min(curIdx+1,D.time.length-1);         // заголовок: со следующего часа
const today=D.time[hs]?D.time[hs].slice(0,10):'';
const isToday=j=>D.time[j]&&D.time[j].slice(0,10)===today&&j>=hs;
```

- `tiMax`/`tiMin` и `rainHour` ищутся через `isToday` → текущий час не учитывается.
- Если `curIdx` — последний час суток, `hs` переходит на следующий день
  (заголовок про завтра).
- Лента `D.time.slice(start,start+48)` не меняется (текущий час остаётся первым).

### 2. Таблица «Часы»: строки с датой + max/min по каждым суткам

В `buildCmpTable` (строки 644–685):

**Препроход** — вместо глобальных `gmx/gmn/idxMx/idxMn` по текущим суткам —
пер-сутки карты индексов max/min:

```js
const dayMx={},dayMn={};
D.time.forEach((t,i)=>{
  if(isWc)return;
  const day=t.slice(0,10);
  const nums=codes.map(c=>D.models[c]?D.models[c][cmpVar]?.[i]:undefined).filter(v=>typeof v==='number');
  if(nums.length){
    const mx=Math.max(...nums),mn=Math.min(...nums);
    if(!(day in dayMx)||mx>dayMx[day][1])dayMx[day]=[i,mx];
    if(!(day in dayMn)||mn<dayMn[day][1])dayMn[day]=[i,mn];
  }
});
```

**Генерация строк** — перед первой строкой каждых новых суток вставляется
строка-заголовок с датой на всю ширину:

```js
let prevDay='';
const rows=D.time.map((t,i)=>{
  const day=t.slice(0,10);
  const drow=(day!==prevDay)&&(prevDay=t,'<tr class="dayrow"><td colspan="'+(3+codes.length)+'">'+
    DAY_NAMES_SHORT[new Date(t).getDay()]+' '+new Date(t).getDate()+' '+MONTH_NAMES[new Date(t).getMonth()]+'</td></tr>');
  ...
  const inMx=dayMx[day]&&dayMx[day][0]===i;
  const inMn=dayMn[day]&&dayMn[day][0]===i;
  return drow+`<tr class="${i===curIdx?'now':''}${inMx?' mxrow':''}${inMn?' mnrow':''}">${cells}</tr>`;
}).join('');
```

- Формат даты: короткий день (`DAY_NAMES_SHORT`), число, месяц в род. падеже
  (`MONTH_NAMES`), например «Чт 13 августа».
- `colspan` = 3 служебных + число моделей.
- `inMx`/`inMn` — только если строка совпадает с индексом max/min своих суток.
- `tr.now` (текущий час) и `td.ext` (жирные экстремумы в строке) не меняются.

**CSS** после `tr.mnrow td`:

```css
tr.dayrow td{padding:6px 8px;background:var(--line);color:var(--muted);font-weight:600;border:none}
```

### Что не меняем

- `meteo.py`, `bot.php`, данные — не трогаем.
- Вкладки weather/radar, `radar_template.html` — не трогаем.
- Логику `td.ext`, `tr.now`, `tr.mxrow`/`tr.mnrow` стили — не трогаем.

### Изменения в `tests/test_radar.py`

- Обновить `test_hours_title_uses_remaining_today_window`: проверить
  `const hs=Math.min(curIdx+1,D.time.length-1);`, `j>=hs`, `'Далее '`.
- Обновить `test_compare_rows_highlight_day_max_min`: заменить ассерты
  `gmx/gmn/idxMx/idxMn`/`today` на `dayMx`/`dayMn` (карты по суткам),
  `!(day in dayMx)` / `!(day in dayMn)`; добавить ассерты на `tr.dayrow`,
  `colspan="'+(3+codes.length)+'"`, `prevDay`, `inMx`/`inMn`.
- Остальные тесты вкладки compare (`test_compare_tab_named_chasy`) не меняются.

## Критерии приёмки

1. `python -m pytest tests/test_radar.py -q` — все passed.
2. Полный `python -m pytest -q` — только 2 известных failed Open-Meteo.
3. Headless-проверка: заголовок «Далее ...» не учитывает текущий час;
   в таблице «Часы» между сутками строки с датой («Чт 13 августа»);
   каждая строка max/min своих суток имеет пунктир (красный/синий);
   `tr.now` сохранён.
4. Деплой через GitHub Actions, live-проверка.
