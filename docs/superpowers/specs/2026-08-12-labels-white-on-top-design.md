# Дизайн: белые подписи городов поверх облаков (как на rainradar.ru)

Дата: 2026-08-12
Статус: принято (источник — endpoint rainradar `/labels`; OSM-подложка остаётся как есть)

## Контекст / Проблема

На карте радара (`radar_template.html` → `radar.html`) названия городов и сёл — чёрные подписи OSM, встроенные в подложку. Дождевые тайлы (`RadarLayer`) рисуются поверх подложки, поэтому подписи скрываются под облаками/осадками. Пользователь просит «как на rainradar.ru»: названия белым цветом и поверх облаков, чтобы всегда были видны.

## Проверенные факты о механизме rainradar (реверс-инжиниринг)

### Endpoint подписей
`GET https://rainradar.ru/labels?z={z}&x={x}&y={y}`

Ответ — JSON-массив записей:
```
[[id, имя, x(px, от левого края тайла), y(px, от НИЖНЕГО края тайла), класс_важности], ...]
```
- координаты `(x,y)` — стандартные XYZ-координаты WebMercator (как у нашей карты);
- позиция в тайле: `left: x px`, `bottom: y px` внутри 256×256 тайла;
- класс важности 0..3 → стили подписей (0 — крупные города, 3 — мелкие сёла);
- CORS: `Access-Control-Allow-Origin: *` (проверено с Origin `https://samlab.github.io`);
- покрытие глобальное: Москва (кириллица), Рома, Париж, Сидней, Нью-Йорк; подписи появляются с `z5`, на `z3–z4` endpoint отдаёт пустой массив;
- данные статичные (география), пригодны к HTTP-кэшированию.

### Как рендерит rainradar (`LabelsLayer`, извлечено из bundle.js)
- `L.GridLayer.extend`, `options: {zIndex:"999", updateWhenZooming:false, updateWhenIdle:false}`;
- `createTile`: `div.leaflet-tile.labels`; запрос через Worker (`/js/renderLabel.js`) по `url = "z="+e.z+"&x="+e.x+"&y="+e.y"`;
- по ответу для каждой записи создаётся `div.label.l<класс>` с вложенным `<span>` (текст названия), `style.left = x+"px"`, `style.bottom = y+"px"`;
- DOM: `map.on("zoomstart", removeFrom)` / `map.on("zoomend", addTo)`.

### Стили подписей (замерено через CDP на живом rainradar.ru)
| класс | font-size | color | font-weight | text-shadow |
|-------|-----------|-------|-------------|-------------|
| l0 | 13px | `#fff` | 500 | `rgba(0,0,0,.7)` по 4 сторонам (по 1px) |
| l1 | 12px | `#fff` | 500 | то же |
| l2 | 11px | `#fff` | 500 | то же |
| l3 | 10px | `#fff` | 500 | то же |

`white-space: nowrap`, `position: absolute`.

## Целевая архитектура

Меняется только `radar_template.html` (собирается в `radar.html` через `tools/build_radar.py`). UI, радар и молнии не меняются.

### Стек слоёв (снизу вверх)
`OSM-подложка` → `радар (RadarLayer)` → `молнии (lightning-0/1)` → **`подписи` (новый pane `labels`, z-index 900)**.

### 1. CSS (в `<style>` шаблона)
- `.leaflet-labels-pane{z-index:900}` — выше кастомных panes молний (у них z-index 400, подписаны раньше);
- `.label{position:absolute;white-space:nowrap;pointer-events:none;line-height:1}`
- `.label>span{color:#fff;font-weight:500;text-shadow:-1px 0 1px rgba(0,0,0,.7),1px 0 1px rgba(0,0,0,.7),0 1px 1px rgba(0,0,0,.7),0 -1px 1px rgba(0,0,0,.7)}`
- размеры: `.label.l0>span{font-size:13px}` … `.label.l3>span{font-size:10px}`.

`pointer-events:none` — чтобы подписи не перехватывали клики/перетаскивание карты (в отличие от rainradar, где это не нужно из-за особенностей их UI).

### 2. Слой `LabelsLayer` (JS в IIFE карты)
```
map.createPane('labels');
var LabelsLayer=L.GridLayer.extend({
  options:{pane:'labels',minZoom:5,maxZoom:10,updateWhenZooming:false},
  createTile:function(coords){
    var tile=document.createElement('div');           // Leaflet добавит .leaflet-tile
    var url='https://rainradar.ru/labels?z='+coords.z+'&x='+coords.x+'&y='+coords.y;
    fetch(url).then(function(r){return r.json();}).then(function(labels){
      for(var i=0;i<labels.length;i++){
        var d=document.createElement('div'),s=document.createElement('span');
        d.className='label l'+labels[i][4];
        s.textContent=labels[i][1];
        d.style.left=labels[i][2]+'px'; d.style.bottom=labels[i][3]+'px';
        d.appendChild(s); tile.appendChild(d);
      }
    }).catch(function(){});
    return tile;
  }
});
map.addLayer(new LabelsLayer());
```
- запросы идут в обычный HTTP-кэш браузера (данные статичные), никаких `no-store`;
- `minZoom:5` — endpoint на z3–z4 пустой, ниже z5 тайлы не создаются;
- `updateWhenZooming:false` — без мигания подписей при анимации зума;
- ошибка запроса → тайл остаётся пустым (подписи декоративны, радар не блокируют);
- асинхронная вставка в уже отцепленный тайл безвредна (привязанный к детачу div просто не показывается).

### 3. Тестирование (`tests/test_radar.py`)
Новый тест `test_radar_has_labels_layer`:
- в `radar_template.html` есть `LabelsLayer`, `map.createPane('labels')`, `rainradar.ru/labels?z=`, CSS-правила `.leaflet-labels-pane{z-index:900}`, `.label`, `.label.l0..l3`;
- в собранном `radar.html` (после `tools/build_radar.py`) присутствует та же логика (места `__LEAFLET__`/блоков подставлены).

### 4. Проверка
- `pytest tests/test_radar.py` + полный pytest (2 пред-существующих failed-теста Open-Meteo игнорировать);
- headless-скриншот (Edge CDP): на зуме 8 над областью с осадками белые подписи видны ПОВЕРХ дождя/облачности; на зуме 7 и 10 тоже;
- сверка позиций/набора названий с живым rainradar.ru (тот же тайл `z/x/y`);
- сборка, коммит, push, деплой (workflow `deploy.yml`), live-проверка на `https://samlab.github.io/MeteoMap/radar.html`.

## Ошибки и деградация

- Endpoint `/labels` недоступен → подписи не появляются, карта работает как раньше (без сообщений пользователю — подписи вторичны);
- зависимость от стороннего endpoint принята сознательно (как и для composite-тайлов, источник которых уже используется).

## Вне скоупа

- Удаление/осветление чёрных подписей OSM с подложки. Решение пользователя: «оставить как есть, попробуем; если что — уберём чёрные» (при желании отдельной задачей можно перейти на бесшумную подложку rainradar).
- Собственный источник подписей (Overpass/Nominatim) — не нужен, endpoint rainradar глобальный.
