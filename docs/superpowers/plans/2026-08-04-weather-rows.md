# Правки вкладки «Погода»: строки «На 10 дней» и «Подробно на 10 дней» — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Переформатировать строки «На 10 дней» (компактная температура, осадки в мм + вероятность, облачность) и «Подробно на 10 дней» (иконка кондиции, стрелка ветра вместо текста, осадки мм/вероятность, облачность вместо давления), плюс новая дневная переменная `cloud_cover_mean`.

**Architecture:** Изменения в двух файлах. `meteo.py` — добавить `cloud_cover_mean` в `DAILY_VARIABLES` (числовая дневная переменная; `build_payload` уже усредняет её по моделям автоматически). `template.html` — переписать `buildWeather10` и `buildWeatherDetail` и их CSS; JS-части проверяются headless-пробами (проектный инструмент `tools/headless_probe.py`), Python-часть — pytest.

**Tech Stack:** Python 3.13 + requests (venv `F:\Meteo\.venv`), шаблонизатор `meteo.py` → `index.html`, чистый JS/HTML/CSS (Chart.js уже подключён), тесты pytest, headless Edge.

## Global Constraints

- UI только русский, светлая тема; **никаких новых зависимостей/CDN** (эмодзи и глиф `↑` из системного шрифта).
- `index.html` регенерируется из `template.html`: `F:\Meteo\.venv\Scripts\python.exe meteo.py` → вывод `models=13 hours=240`.
- Тесты: `F:\Meteo\.venv\Scripts\python.exe -m pytest tests -m "not integration" -q` → до задачи 1: `53 passed, 2 deselected`; после: `54 passed, 2 deselected`.
- Пробы: `python tools\headless_probe.py <index.html> "<JS>" <outfile>` — JS передаётся аргументом, результат читается из `outfile`. Кириллица в JS-аргументе передаётся через `\uXXXX`-экраны (только ASCII), переменные окружения: `$env:PYTHONIOENCODING="utf-8"`.
- Форматтеры в `template.html` (стр. 189–192): `fmt` — 0.1 мм; `num` — целое; `temp` — `+23°`/`-3°` со знаком и градусом; `rumbFull(deg)` — полное название направления (стр. 208).
- Существующие словари: `WCODE` (стр. 193–203, `wcode(c)` → `[wtext, we]`), `PARTS=[['ночь','03'],['утро','09'],['день','15'],['вечер','21']]` (стр. 319), `partVal(day,hr,field)` (стр. 320–323), `D.daily_time` (массив `YYYY-MM-DD`).
- Правила TDD: сначала тест/проба (RED), затем реализация (GREEN), затем коммит.

---

### Task 1: Дневная переменная `cloud_cover_mean`

**Files:**
- Modify: `F:\Meteo\meteo.py:33-37` (`DAILY_VARIABLES`)
- Modify: `F:\Meteo\tests\test_render.py:4-30` (фикстура `_payload`) и добавить тест после стр. 82

**Interfaces:**
- Consumes: ничего нового — `build_payload` (метeo.py:316-336) уже перебирает `DAILY_VARIABLES` и усредняет числовые поля по моделям (`daily_consensus[v] = [mean(...)]`), строковые (`sunrise`/`sunset`) берёт из первой модели.
- Produces: в payload появляется `D.daily.cloud_cover_mean` — `list[float]` (среднее по моделям), используется в Task 2.

- [ ] **Step 1: Обновить фикстуру и написать падающий тест**

В `F:\Meteo\tests\test_render.py` в `_payload()` добавить в словарь модели `"a"` (стр. 14–17) поле `"cloud_cover_mean": [40.0]`, в словарь модели `"b"` (стр. 18–21) поле `"cloud_cover_mean": [50.0]`. Итог фикстуры:

```python
    daily = {
        "a": {"time": ["d0"], "temperature_2m_max": [5.0],
              "precipitation_probability_max": [10.0],
              "sunrise": ["2026-08-03T04:19:00"],
              "sunset": ["2026-08-03T20:33:00"],
              "cloud_cover_mean": [40.0]},
        "b": {"time": ["d0"], "temperature_2m_max": [7.0],
              "precipitation_probability_max": [30.0],
              "sunrise": ["2026-08-03T04:20:00"],
              "sunset": ["2026-08-03T20:34:00"],
              "cloud_cover_mean": [50.0]},
    }
```

После функции `test_daily_contains_new_variables` (заканчивается на стр. 82) добавить:

```python
def test_daily_cloud_cover_mean_is_averaged():
    p = _payload()
    assert p["daily"]["cloud_cover_mean"] == [45.0]
```

- [ ] **Step 2: Запустить тест и убедиться, что он падает**

Run: `& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests/test_render.py::test_daily_cloud_cover_mean_is_averaged -q`
Expected: FAIL — `KeyError: 'cloud_cover_mean'` (переменной нет в `DAILY_VARIABLES`, `build_payload` её не эмитит).

- [ ] **Step 3: Добавить переменную в `DAILY_VARIABLES`**

В `F:\Meteo\meteo.py:33-37` заменить:

```python
DAILY_VARIABLES = [
    "temperature_2m_max", "temperature_2m_min", "precipitation_sum",
    "wind_speed_10m_max", "sunshine_duration",
    "precipitation_probability_max", "sunrise", "sunset",
]
```

на:

```python
DAILY_VARIABLES = [
    "temperature_2m_max", "temperature_2m_min", "precipitation_sum",
    "wind_speed_10m_max", "sunshine_duration",
    "precipitation_probability_max", "cloud_cover_mean", "sunrise", "sunset",
]
```

- [ ] **Step 4: Запустить тесты и убедиться, что проходят**

Run: `& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests -m "not integration" -q`
Expected: `54 passed, 2 deselected`.

- [ ] **Step 5: Закоммитить**

```bash
git add meteo.py tests/test_render.py
git commit -m "feat: add cloud_cover_mean daily variable"
```

---

### Task 2: Строки «На 10 дней» — компактная температура, осадки мм/вероятность, облачность

**Files:**
- Modify: `F:\Meteo\template.html:74` (CSS `.d10row`, `.d10pp`, `.d10n`)
- Modify: `F:\Meteo\template.html:304-318` (`buildWeather10`)

**Interfaces:**
- Consumes: `D.daily.temperature_2m_max/min`, `D.daily.precipitation_sum`, `D.daily.precipitation_probability_max`, `D.daily.cloud_cover_mean` (из Task 1), `D.daily_time`, `DOW_S`, `MONTH_NAMES`, `wcode`, `temp`, `fmt`, `num`.
- Produces: структура `.d10row` с ячейками `.d10day`, `.d10cond`, `.d10t` (температуры), `.d10mm` (мм/вероятность), `.d10cl` (облачность). Используется в Task 3 при пробе регрессии.

- [ ] **Step 1: Написать пробу-ожидание (RED)**

Создать файл `C:\Users\SamLab\AppData\Local\Temp\opencode\probe10.js` (UTF-8, только ASCII, кириллица через `\u`-экраны):

```js
addEventListener('load',function(){setTimeout(function(){
var rows=document.querySelectorAll('#weather-10 .d10row');
var bad=[];
var nochyu='\u043d\u043e\u0447\u044c\u044e',dnyom='\u0434\u043d\u0451\u043c',mm='\u043c\u043c',obl='\u043e\u0431\u043b\u0430\u043a\u0430';
for(var i=0;i<rows.length;i++){
  var t=rows[i].textContent;
  if(t.indexOf(nochyu)>=0||t.indexOf(dnyom)>=0)bad.push('lbl'+i);
  if(t.indexOf(mm)<0)bad.push('mm'+i);
  if(t.indexOf('%')<0)bad.push('pct'+i);
  if(t.indexOf(obl)<0)bad.push('cl'+i);
  if(!/[+\-]?\d+\u00b0\/[+\-]?\d+\u00b0/.test(t))bad.push('t'+i);
}
document.getElementById('probeout').textContent='rows='+rows.length+' bad='+(bad.join(',')||'none');
},2000);});
```

Прогнать на текущей (старой) странице:

```powershell
$env:PYTHONIOENCODING="utf-8"
$js = Get-Content "C:\Users\SamLab\AppData\Local\Temp\opencode\probe10.js" -Raw -Encoding UTF8
& "F:\Meteo\.venv\Scripts\python.exe" tools\headless_probe.py index.html $js C:\Users\SamLab\AppData\Local\Temp\opencode\probe10.txt
Get-Content C:\Users\SamLab\AppData\Local\Temp\opencode\probe10.txt -Encoding UTF8
```

Expected (RED): `rows=10 bad=lbl0,...` (старые строки содержат «ночью/днём» и не содержат «мм»/«облака»).

- [ ] **Step 2: Реализовать `buildWeather10`**

В `F:\Meteo\template.html:304-318` заменить функцию целиком:

```js
function buildWeather10(){
  const dt=D.daily_time||[];
  document.getElementById('weather-10').innerHTML=dt.map((day,di)=>{
    const idx=D.time.findIndex(t=>t.slice(0,10)===day&&t.slice(11,13)==='15');
    const [wtext,we]=idx<0?['','']:wcode(D.weighted.weather_code?.[idx]);
    const tmin=D.daily.temperature_2m_min?.[di];
    const tmax=D.daily.temperature_2m_max?.[di];
    const pr=D.daily.precipitation_sum?.[di];
    const pp=D.daily.precipitation_probability_max?.[di];
    const cl=D.daily.cloud_cover_mean?.[di];
    const d=new Date(day);
    return '<div class="d10row"><div class="d10day">'+DOW_S[d.getDay()]+', '+d.getDate()+' '+MONTH_NAMES[d.getMonth()].slice(0,3)+'</div>'+
      '<div class="d10cond">'+we+' '+wtext+'</div>'+
      '<div class="d10t">'+temp(tmax)+'/'+temp(tmin)+'</div>'+
      '<div class="d10mm">'+(pr==null?'—':fmt(pr)+' мм')+' / '+num(pp)+'%</div>'+
      '<div class="d10cl">облака '+(cl==null?'—':num(cl)+'%')+'</div></div>';
  }).join('');
}
```

- [ ] **Step 3: Обновить CSS**

В `F:\Meteo\template.html:74-77` заменить блок:

```css
.d10row{display:grid;grid-template-columns:100px 1fr 70px 190px;align-items:center;gap:8px;padding:9px 0;border-bottom:1px solid var(--line);font-size:13px}
.d10day{color:var(--muted)}
.d10pp{color:#1976d2}
.d10n{color:var(--muted)}
```

на:

```css
.d10row{display:grid;grid-template-columns:100px 1fr auto auto auto;align-items:center;gap:8px;padding:9px 0;border-bottom:1px solid var(--line);font-size:13px}
.d10day{color:var(--muted)}
.d10t{white-space:nowrap}
.d10mm{color:var(--muted)}
.d10cl{color:var(--muted)}
```

- [ ] **Step 4: Регенерировать и прогнать пробу (GREEN)**

```powershell
& "F:\Meteo\.venv\Scripts\python.exe" meteo.py
$env:PYTHONIOENCODING="utf-8"
$js = Get-Content "C:\Users\SamLab\AppData\Local\Temp\opencode\probe10.js" -Raw -Encoding UTF8
& "F:\Meteo\.venv\Scripts\python.exe" tools\headless_probe.py index.html $js C:\Users\SamLab\AppData\Local\Temp\opencode\probe10.txt
Get-Content C:\Users\SamLab\AppData\Local\Temp\opencode\probe10.txt -Encoding UTF8
```

Expected (GREEN): `models=13 hours=240` при регенерации; проба `rows=10 bad=none`.

- [ ] **Step 5: Контрольный прогон тестов**

Run: `& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests -m "not integration" -q`
Expected: `54 passed, 2 deselected`.

- [ ] **Step 6: Закоммитить**

```bash
git add template.html index.html
git commit -m "feat: compact temps, precipitation mm and clouds in 10-day list"
```

---

### Task 3: «Подробно на 10 дней» — иконка кондиции, стрелка ветра, осадки мм/вероятность, облачность

**Files:**
- Modify: `F:\Meteo\template.html:79-84` (CSS `.dpart` и связанные)
- Modify: `F:\Meteo\template.html:324-351` (`buildWeatherDetail`)
- Modify: `F:\Meteo\template.html:132-133` (справка)

**Interfaces:**
- Consumes: `partVal(day, hr, field)` для полей `weather_code`, `wind_speed_10m`, `wind_direction_10m`, `precipitation`, `precipitation_probability`, `relative_humidity_2m`, `cloud_cover`; `wcode`, `rumbFull`, `PARTS`, `DAY_NAMES`, `MONTH_NAMES`, `temp`, `num`.
- Produces: итоговая структура `.dpart`: `.pt` (иконка+название), `.ptemp`, `.pw` (скорость+стрелка), `.ppr` (мм/вероятность), `.phu` (влажность), `.pcl` (облачность).

- [ ] **Step 1: Написать пробу-ожидание (RED)**

Создать `C:\Users\SamLab\AppData\Local\Temp\opencode\probeDetail.js` (UTF-8, только ASCII):

```js
addEventListener('load',function(){setTimeout(function(){
var parts=document.querySelectorAll('#weather-detail .dpart');
var icons=0,arrows=0,cl=0,prec=0,hum=0,bad=0;
var obl='\u043e\u0431\u043b\u0430\u043a\u0430',vlag='\u0412\u043b\u0430\u0436\u043d\u043e\u0441\u0442\u044c',mm='\u043c\u043c';
var sev='\u0441\u0435\u0432\u0435\u0440\u043d',vost='\u0432\u043e\u0441\u0442\u043e\u0447\u043d',yuzh='\u044e\u0436\u043d',zapad='\u0437\u0430\u043f\u0430\u0434\u043d';
var iconSet=[];for(var k in WCODE){var e=WCODE[k][1];if(e&&iconSet.indexOf(e)<0)iconSet.push(e);}
for(var i=0;i<parts.length;i++){
  var p=parts[i],pt=p.querySelector('.pt').textContent,pw=p.querySelector('.pw'),t=p.textContent;
  var hasI=false;for(var j=0;j<iconSet.length;j++){if(pt.indexOf(iconSet[j])>=0){hasI=true;break;}}
  if(hasI)icons++;
  if(pw.innerHTML.indexOf('\u2191')>=0)arrows++;
  if(t.indexOf(obl)>=0)cl++;
  if(t.indexOf(mm)>=0&&t.indexOf('%')>=0)prec++;
  if(t.indexOf(vlag)>=0)hum++;
  if(pw.textContent.indexOf(sev)>=0||pw.textContent.indexOf(vost)>=0||pw.textContent.indexOf(yuzh)>=0||pw.textContent.indexOf(zapad)>=0)bad++;
}
document.getElementById('probeout').textContent='parts='+parts.length+' icons='+icons+' arrows='+arrows+' cl='+cl+' prec='+prec+' hum='+hum+' bad='+bad;
},2000);});
```

Прогнать на текущей странице (как в Task 2, Step 1, файл вывода `probeDetail.txt`).
Expected (RED): `parts=40 icons=0 arrows=0 cl=0 prec=0 hum=40 bad=40` (нет иконок/стрелок/облаков, ветер содержит «северо-…» и т.д.).

- [ ] **Step 2: Реализовать `buildWeatherDetail`**

В `F:\Meteo\template.html:324-351` заменить функцию целиком (от `function buildWeatherDetail(){` до закрывающей `}`):

```js
function buildWeatherDetail(){
  const dt=D.daily_time||[];
  document.getElementById('weather-detail').innerHTML=dt.map((day,di)=>{
    const d=new Date(day);
    const sr=(D.daily.sunrise?.[di]||'').slice(11,16)||'—';
    const ss=(D.daily.sunset?.[di]||'').slice(11,16)||'—';
    let dl='—';
    if(D.daily.sunrise?.[di]&&D.daily.sunset?.[di]){
      const ms=new Date(D.daily.sunset[di])-new Date(D.daily.sunrise[di]);
      if(!isNaN(ms))dl=Math.floor(ms/3600000)+' ч '+Math.round((ms%3600000)/60000)+' мин';
    }
    const cells=PARTS.map(x=>{
      const t=partVal(day,x[1],'temperature_2m');
      const ws=partVal(day,x[1],'wind_speed_10m');
      const wd=partVal(day,x[1],'wind_direction_10m');
      const pr=partVal(day,x[1],'precipitation');
      const pp=partVal(day,x[1],'precipitation_probability');
      const hu=partVal(day,x[1],'relative_humidity_2m');
      const cl=partVal(day,x[1],'cloud_cover');
      const [,we]=wcode(partVal(day,x[1],'weather_code'));
      const arrow=wd==null?'':' <span class="pwarrow" title="'+rumbFull(wd)+'" style="transform:rotate('+((wd+180)%360)+'deg)">↑</span>';
      return '<div class="dpart"><div class="pt">'+(we?we+' ':'')+x[0]+'</div>'+
        '<div class="ptemp">'+temp(t)+'</div>'+
        '<div class="pw">'+(ws==null?'—':num(ws)+' м/с')+arrow+'</div>'+
        '<div class="ppr">'+(pr==null?'—':num(pr)+' мм')+' / '+num(pp)+'%</div>'+
        '<div class="phu">Влажность '+(hu==null?'—':num(hu)+'%')+'</div>'+
        '<div class="pcl">облака '+(cl==null?'—':num(cl)+'%')+'</div></div>';
    }).join('');
    return '<div class="dhead">'+DAY_NAMES[d.getDay()]+', '+d.getDate()+' '+MONTH_NAMES[d.getMonth()]+'</div>'+
      '<div class="dparts">'+cells+'</div>'+
      '<div class="dsun">Восход: '+sr+' · Закат: '+ss+' · Долгота дня: '+dl+'</div>';
  }).join('');
}
```

- [ ] **Step 3: Обновить CSS**

В `F:\Meteo\template.html:79-84` заменить:

```css
.dparts{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
.dpart{background:var(--sel);border:1px solid var(--line);border-radius:8px;padding:8px 10px;font-size:12px}
.dpart .pt{color:var(--muted);font-size:11px;margin-bottom:2px}
.dpart .ptemp{font-size:17px;font-weight:600}
.dpart .pw,.dpart .ppr,.dpart .phu{margin-top:2px}
.dsun{font-size:12px;color:var(--muted);margin-top:6px}
```

на:

```css
.dparts{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
.dpart{background:var(--sel);border:1px solid var(--line);border-radius:8px;padding:8px 10px;font-size:12px}
.dpart .pt{color:var(--muted);font-size:11px;margin-bottom:2px}
.dpart .ptemp{font-size:17px;font-weight:600}
.dpart .pw,.dpart .ppr,.dpart .phu,.dpart .pcl{margin-top:2px}
.pwarrow{display:inline-block;font-size:12px;transform-origin:center}
.dsun{font-size:12px;color:var(--muted);margin-top:6px}
```

- [ ] **Step 4: Обновить справку**

В `F:\Meteo\template.html:132-133` заменить две строки:

```html
      <li><b>На 10 дней</b> — день, состояние погоды, вероятность осадков, ночная и дневная температуры.</li>
      <li><b>Подробно на 10 дней</b> — по частям суток (ночь/утро/день/вечер): температура, ветер, давление, влажность; внизу — восход/закат и долгота дня.</li>
```

на:

```html
      <li><b>На 10 дней</b> — день, состояние погоды, дневная и ночная температуры, осадки и вероятность, облачность.</li>
      <li><b>Подробно на 10 дней</b> — по частям суток (ночь/утро/день/вечер): иконка погоды, температура, ветер со стрелкой направления, осадки и вероятность, влажность, облачность; внизу — восход/закат и долгота дня.</li>
```

- [ ] **Step 5: Регенерировать и прогнать пробу (GREEN)**

```powershell
& "F:\Meteo\.venv\Scripts\python.exe" meteo.py
$env:PYTHONIOENCODING="utf-8"
$js = Get-Content "C:\Users\SamLab\AppData\Local\Temp\opencode\probeDetail.js" -Raw -Encoding UTF8
& "F:\Meteo\.venv\Scripts\python.exe" tools\headless_probe.py index.html $js C:\Users\SamLab\AppData\Local\Temp\opencode\probeDetail.txt
Get-Content C:\Users\SamLab\AppData\Local\Temp\opencode\probeDetail.txt -Encoding UTF8
```

Expected (GREEN): проба `parts=40 icons=40 arrows=40 cl=40 prec=40 hum=40 bad=0`. Допустимые отклонения (только при реальных данных): если у части суток `weather_code` вне `WCODE`/`null` — `icons` меньше 40; если `wind_direction_10m==null` — `arrows` меньше 40; если `precipitation==null` — в `.ppr` нет «мм» и `prec` меньше 40. В таких случаях итог должен быть `parts=40`, `cl=40`, `hum=40`, `bad=0`, а `icons/arrows/prec >= 38`, и расхождение нужно объяснить в отчёте. При эталонной генерации (все данные в норме) ожидается ровно `icons=40 arrows=40 prec=40`.

- [ ] **Step 6: Регрессия — проба всех блоков и переключения**

Создать `C:\Users\SamLab\AppData\Local\Temp\opencode\probeRegr.js`:

```js
addEventListener('load',function(){setTimeout(function(){
var q=function(s){return document.querySelectorAll(s).length};
var h='hours='+q('#weather-hours .hour')+' rows10='+q('#weather-10 .d10row')+' parts='+q('#weather-detail .dpart')+' now='+(document.getElementById('weather-now').textContent.length>0)+' tab='+document.querySelector('.tabs button.active').dataset.tab;
var b=document.querySelector('.tabs button[data-tab=forecast]');b.click();
setTimeout(function(){
  var c=Chart.getChart('mainChart');
  document.getElementById('probeout').textContent=h+' chart=w'+c.width+',h'+c.height+' panel='+(document.getElementById('tab-forecast').className.indexOf('active')>=0?'ok':'fail');
},1500);
},2000);});
```

Прогнать как в Step 5 (вывод `probeRegr.txt`).
Expected: `hours=48 rows10=10 parts=40 now=true tab=weather chart=w2400,h456 panel=ok`.

- [ ] **Step 7: Контрольный прогон тестов**

Run: `& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests -m "not integration" -q`
Expected: `54 passed, 2 deselected`.

- [ ] **Step 8: Закоммитить**

```bash
git add template.html index.html
git commit -m "feat: condition icons, wind arrows and precipitation mm in weather detail"
```
