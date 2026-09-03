# «Спутник» (наукастинг ГМЦ) — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить на сайт вкладку «Спутник», показывающую радар-наукастинг осадков Гидрометцентра (~2 ч, кадры 10 мин), не затрагивая существующий радар.

**Architecture:** Новая страница `nowcast.html` собирается билдером из нового шаблона `nowcast_template.html` (эталон — `radar_template.html`). Вкладка «Спутник» в `template.html` открывает её в отдельном iframe `satellite-frame`. Слой осадков — свой `NowcastLayer` (чтение R-канала PNG-тайла ГМЦ → палитра PAL). Логика разбора capabilities и построения URL тайла вынесена в `tools/nowcast.py` и покрыта юнит-тестами (регрессионный замок на известный формат).

**Tech Stack:** Python (build + мета), pytest, vanilla JS + Leaflet 1.6.0 (уже в `tools/`), WMS capabilities + PNG-тайлы meteoinfo.ru.

## Global Constraints

- **НЕ изменять** `radar.html`, `radar_template.html`, `tools/build_radar.py` (для radar.html) и JS-логику вкладки «Радар» (`radar-frame`, `updateRadarFrame`).
- Реакт.composite/rainradar.ru — константы radar_template (см. там).
- Имя вкладки/страницы — **«Спутник»**; слой — **наукастинг ГМЦ** (радар осадков), не спутниковые снимки.
- Кнопки «← Радар» на странице науки **НЕТ** (отдельная вкладка).
- Библиотеки Leaflet/CSS/палитра общие из `tools/` — использовать заново, не править.
- Формат времён capabilities: ISO8601 UTC с `Z`, разделитель `,`, хронологический порядок.
- Тайт: `https://meteoinfo.ru/res/nowcast/{z}0{x}0{y}/ncgi.php?tnz={z}&tnx={x}&tny={y}&inidt={URL-encoded ISO}` — путь это конкатенация `{z}`+`0`+`{x}`+`0`+`{y}`.
- Маска слоя ~42-68°N, 18-63°E; тайлы 256×256 RGBA, CORS `*`; R-канал = интенсивность, 0 = нет осадков (прозрачный).
- CI-команда: `python -m pytest tests/ -m "not integration" -q`.
- Deploy: добавить `cp nowcast.html _site/` в `.github/workflows/deploy.yml`.

---

### Task 1: Хелперы в `tools/nowcast.py` (+ юнит-тесты)

**Files:**
- Create: `tools/nowcast.py`
- Create: `tests/test_nowcast.py`

**Interfaces:**
- Produces: `parse_capabilities_times(xml: str) -> list[str]`, `tile_path(z: int, x: int, y: int) -> str`, `tile_url(z: int, x: int, y: int, inidt: str) -> str`.
  Позже JS-шаблон использует те же правила (дублирование, запертое тестами).

- [ ] **Step 1: Write the failing test** `tests/test_nowcast.py`

```python
import pytest
from tools import nowcast

CAP = (
    '<WMT_MS_Capabilities>'
    '<Service><Name><![CDATA[WMS]]></Name></Service>'
    '<Capability><Layer><Title>R</Title>'
    '<Layer queryable="1"><Dimension name="time" units="ISO8601" current="1"/>'
    '<Extent name="time" default="2026-09-03T09:30:00.000Z">'
    '2026-09-03T09:30:00.000Z,2026-09-03T09:40:00.000Z,2026-09-03T09:50:00.000Z'
    '</Extent><Layer queryable="1"><Name>1</Name></Layer></Layer></Layer>'
    '</Capability></WMT_MS_Capabilities>'
)


def test_parse_capabilities_times_extracts_ordered_utc():
    times = nowcast.parse_capabilities_times(CAP)
    assert times == [
        "2026-09-03T09:30:00.000Z",
        "2026-09-03T09:40:00.000Z",
        "2026-09-03T09:50:00.000Z",
    ]


def test_parse_capabilities_times_empty_when_no_extent():
    assert nowcast.parse_capabilities_times("<WMT_MS_Capabilities></WMT_MS_Capabilities>") == []


def test_tile_path_concatenates_z0x0y():
    assert nowcast.tile_path(6, 39, 19) == "6039019"
    assert nowcast.tile_path(9, 312, 155) == "903120155"


def test_tile_url_builds_known_good():
    url = nowcast.tile_url(6, 39, 19, "2026-09-03T10:00:00.000Z")
    assert url == (
        "https://meteoinfo.ru/res/nowcast/6039019/ncgi.php"
        "?tnz=6&tnx=39&tny=19&inidt=2026-09-03T10%3A00%3A00.000Z"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_nowcast.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools'` (или отсутствие функций). Нужен `tools/__init__.py`? Проверить: `tools/` сейчас без `__init__.py`. См. примечание в Step 3 про `conftest.py`.

- [ ] **Step 3: Write `tools/nowcast.py`**

```python
import re
from urllib.parse import quote

CAP_URL = "https://meteoinfo.ru/hmc-output/nowcast3/nowcast.php"
TILE_BASE = "https://meteoinfo.ru/res/nowcast/"

_EXTENT_RE = re.compile(r'<Extent name="time"[^>]*>(.*?)</Extent>', re.S)


def parse_capabilities_times(xml):
    """Извлекает список времён кадров (ISO8601 UTC) из WMS-capabilities ГМЦ."""
    m = _EXTENT_RE.search(xml or "")
    if not m:
        return []
    raw = m.group(1).strip()
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]


def tile_path(z, x, y):
    """Путь сегмента тайла: `{z}0{x}0{y}` (конкатенация)."""
    return "{}{}0{}0{}".format(z, 0, x, 0, y)


def tile_url(z, x, y, inidt):
    """Полный URL тайла науки. inidt — ISO без URL-кодирования на входе."""
    path = tile_path(z, x, y)
    q = (
        "tnz={}&tnx={}&tny={}&inidt={}".format(z, x, y, quote(inidt, safe=""))
    )
    return TILE_BASE + path + "/ncgi.php?" + q
```

**Примечание по импорту `from tools import nowcast`:**
- Проверено: pytest (rootdir `F:\Meteo`, конфиг pytest.ini) подхватывает `tools/` как namespace-package (без `__init__.py`) через rootdir-вставку в `sys.path`. Как только существует `tools/nowcast.py`, `from tools import nowcast` работает. Никаких `conftest.py`/`pythonpath` добавлять не нужно.
- `tools/nowcast.py` не конфликтует с `tools/build_radar.py` (он не импортируется тестами; в Task 3 мы его обобщим отдельно).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_nowcast.py -q`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add tools/nowcast.py tests/test_nowcast.py
git commit -m "feat(nowcast): helpers to parse capabilities and build tile URLs"
```

---

### Task 2: Шаблон `nowcast_template.html` (страница «Спутник»)

**Files:**
- Create: `nowcast_template.html`

**Interfaces:**
- Consumes: правила из `tools/nowcast.py` (parse_capabilities_times/tile_url) — продублированы в JS с комментарием на исходник. Leaflet/PAL из `tools/` (заглушки `/*__LEAFLET__*/`, `/*__LEAFLET_CSS__*/`, `/*__PALETTE__*/` как в radar_template.html).
- Produces: шаблон, который Task 3 заменит заглушки и запишет в `nowcast.html`.

Это шаблон страницы полностью (не пустой класс) — все маркеры Leaflet/CSS/PALETTE как в radar_template.html, но слой осадков заменён на NowcastLayer (чтение R-канала), а таймлайн строится из capabilities ГМЦ.

- [ ] **Step 1: Создать файл `nowcast_template.html`** со следующим содержимым (эталон структуры и стилей — `radar_template.html`; ниже весь файл):

```html
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Спутник — наукастинг — MeteoMap</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{background:#acacac;color:#42434b;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;overflow:hidden}
#map{position:absolute;inset:0;background:#acacac}
#timeline{position:absolute;left:0;right:0;bottom:0;z-index:1000;background:#fff;border-top:1px solid #d8d8d8;padding:10px 14px;display:flex;align-items:center;gap:14px}
#play{width:48px;height:48px;border-radius:50%;background:#fff;box-shadow:0 2px 2px rgba(85,85,85,.4);color:#42434b;font-size:16px;cursor:pointer;flex:none;display:flex;align-items:center;justify-content:center;border:0}
#play:hover{background:#f2f2f2}
#segwrap{flex:1;position:relative;height:10px;cursor:pointer}
#segs{position:absolute;left:0;right:0;top:0;bottom:0;display:flex;gap:1px}
#segs div{flex:1;position:relative;cursor:pointer}
#segs div:after{content:'';display:block;position:absolute;background-color:#42434b;opacity:.35;left:0;right:0;top:0;bottom:0;border-radius:2px}
#segs div.on:after{opacity:1}
#segs div:first-child:after{border-radius:9px 2px 2px 9px}
#segs div:last-child:after{border-radius:2px 9px 9px 2px}
#time{font-size:12px;color:#fff;min-width:66px;text-align:center;padding:2px 8px;background-color:#415fad;border-radius:10px;flex:none;font-variant-numeric:tabular-nums}
#legend{position:absolute;bottom:72px;left:50%;transform:translateX(-50%);z-index:1000;width:260px;height:20px;padding:0 14px;display:flex;justify-content:space-between;align-items:center;border-radius:20px;box-shadow:0 0 2px #000;background:linear-gradient(to right,#8889bd,#595a95,#454696,#36b343,#81c81e,#c2d11e,#ffd000,#f29b17,#e1782e,#d23a4b,#b3107c,#b80db2)}
#legend span{font-size:11px;color:#fff;text-shadow:0 0 4px #000;font-weight:600;white-space:nowrap}
#status{position:absolute;top:10px;left:50%;transform:translateX(-50%);z-index:1000;background:#fff;border:1px solid #d8d8d8;color:#42434b;border-radius:8px;padding:6px 14px;font-size:12px;display:none;box-shadow:0 1px 3px rgba(0,0,0,.2)}
#status.show{display:block}
#ltoggle{position:absolute;top:10px;right:10px;z-index:1000;background:#42434b;color:#fff;border:0;border-radius:18px;padding:6px 14px;font-size:12px;cursor:pointer;font-weight:600;box-shadow:0 1px 3px rgba(0,0,0,.3);display:flex;align-items:center;gap:6px}
#ltoggle.on{background:#f29b17;color:#fff}
#ltoggle .ltdot{width:8px;height:8px;border-radius:50%;background:#fff;display:inline-block}
/*__LEAFLET_CSS__*/
.leaflet-container{background:#acacac}
.leaflet-bar a,.leaflet-bar a:hover{background-color:#42434b;width:35px;height:35px;line-height:35px;text-align:center;text-decoration:none;color:#fff;margin-bottom:10px;border-radius:50%;font-size:28px}
.leaflet-bar a.leaflet-disabled{cursor:default;background-color:#42434b;color:#5f6065}
.leaflet-container .leaflet-control-attribution{font-size:10px;background:rgba(255,255,255,.8);color:#666}
.leaflet-container .leaflet-control-attribution a{color:#415fad}
.leaflet-labels-pane{z-index:900}
.label{position:absolute;pointer-events:none}
.label::before{content:" ";position:absolute;left:-3px;bottom:-3px;border:1px solid #000;border-radius:50%;width:6px;height:6px;background-color:#eee}
.label>span{position:absolute;left:-9px;bottom:5px;white-space:nowrap;color:#fff;font-weight:500;text-shadow:-1px 0 1px rgba(0,0,0,.7),1px 0 1px rgba(0,0,0,.7),0 1px 1px rgba(0,0,0,.7),0 -1px 1px rgba(0,0,0,.7)}
.label.l0>span{font-size:13px}
.label.l1>span{font-size:12px}
.label.l2>span{font-size:11px}
.label.l3>span,.label.l4>span{font-size:10px}
.label.l1::before,.label.l2::before{left:-2px;bottom:-2px;width:4px;height:4px}
.label.l3::before,.label.l4::before{left:-1px;bottom:-1px;width:2px;height:2px}
.label.l3 span,.label.l4 span{left:-7px}
.leaflet-lightning-0-pane,.leaflet-lightning-1-pane{filter:sepia(1) hue-rotate(330deg) saturate(12) brightness(2) drop-shadow(0 0 3px #ff003c) drop-shadow(0 0 6px #ff003c)}
.leaflet-lightning-1-pane{filter:sepia(1) hue-rotate(330deg) saturate(8) brightness(1.6) drop-shadow(0 0 3px #cc0033) drop-shadow(0 0 5px #cc0033)}
</style>
</head>
<body>
<div id="map"></div>
<div id="status"></div>
<button id="ltoggle" title="Молнии: свежие — светло-голубые, постарше — тёмно-голубые"><span class="ltdot"></span>Молнии</button>
<div id="legend"><span>Слабо</span><span>Умеренно</span><span>Сильно</span><span>Очень сильно</span></div>
<div id="timeline">
  <button id="play" title="Воспроизвести">▶</button>
  <div id="segwrap"><div id="segs"></div></div>
  <span id="time">—</span>
</div>
<script>
/*__LEAFLET__*/
</script>
<script>
/*__PALETTE__*/
</script>
<script>
(function(){
  var params=new URLSearchParams(location.search);
  var lat=parseFloat(params.get('lat'))||57.63;
  var lon=parseFloat(params.get('lon'))||39.87;
  var zoom=parseInt(params.get('zoom')||'8',10);
  var map=L.map('map',{zoomControl:true,minZoom:3,maxZoom:10,fadeAnimation:false}).setView([lat,lon],zoom);
  setTimeout(function(){
    if(map.getContainer().offsetWidth===0||map.getContainer().offsetHeight===0)map.invalidateSize();
  },50);

  L.tileLayer('https://rainradar.ru/tiles?z={z}&x={x}&y={y}',{
    tms:true,minZoom:3,maxZoom:10,zIndex:998
  }).addTo(map);

  map.createPane('lightning-0');
  map.createPane('lightning-1');
  var ltBase='https://images.lightningmaps.org/blitzortung/europe/index.php?tile&zoom={z}&x={x}&y={y}&type=';
  var lt0=L.tileLayer(ltBase+'0&_t='+Date.now(),{opacity:0.9,maxZoom:19,pane:'lightning-0',attribution:'Молнии: <a href="https://www.blitzortung.org">Blitzortung.org</a>'});
  var lt1=L.tileLayer(ltBase+'1&_t='+Date.now(),{opacity:0.9,maxZoom:19,pane:'lightning-1'});
  var lightningGroup=L.layerGroup([lt0,lt1]).addTo(map);
  var elLt=document.getElementById('ltoggle');
  var ltOn=true;
  elLt.classList.add('on');
  elLt.addEventListener('click',function(){
    ltOn=!ltOn;
    if(ltOn){lightningGroup.addTo(map);elLt.classList.add('on');}
    else{map.removeLayer(lightningGroup);elLt.classList.remove('on');}
  });
  setInterval(function(){
    lt0.setUrl(ltBase+'0&_t='+Date.now());
    lt1.setUrl(ltBase+'1&_t='+Date.now());
  },120000);

  map.createPane('labels');
  var LabelsLayer=L.GridLayer.extend({
    options:{pane:'labels',minZoom:5,maxZoom:10,updateWhenZooming:false},
    createTile:function(coords){
      var tile=document.createElement('div');
      tile.style.width='256px';
      tile.style.height='256px';
      var url='https://rainradar.ru/labels?z='+coords.z+'&x='+coords.x+'&y='+coords.y;
      fetch(url).then(function(r){return r.json();}).then(function(labels){
        for(var i=0;i<labels.length;i++){
          var d=document.createElement('div'),s=document.createElement('span');
          d.className='label l'+labels[i][4];
          s.textContent=labels[i][1];
          d.style.left=labels[i][2]+'px';
          d.style.bottom=labels[i][3]+'px';
          d.appendChild(s);
          tile.appendChild(d);
        }
      }).catch(function(){});
      return tile;
    }
  });
  map.addLayer(new LabelsLayer());

  // Наукастинг ГМЦ: capabilities (см. tools/nowcast.py:parse_capabilities_times)
  var CAP_URL='https://meteoinfo.ru/hmc-output/nowcast3/nowcast.php';
  // Разбор времён из <Extent name="time">...</Extent> (ISO8601 UTC, разделитель ,)
  function parseTimes(xml){
    var m=new RegExp('<Extent name="time"[^>]*>(.*?)</Extent>','s').exec(xml||'');
    if(!m)return [];
    return m[1].trim().split(',').map(function(s){return s.trim();}).filter(Boolean);
  }
  // URL тайла: путь = {z}+'0'+{x}+'0'+{y} (см. tools/nowcast.py:tile_url)
  function tileURL(z,x,y,inidt){
    var path=z+'0'+x+'0'+y;
    return 'https://meteoinfo.ru/res/nowcast/'+path+'/ncgi.php?tnz='+z+'&tnx='+x+'&tny='+y+'&inidt='+encodeURIComponent(inidt);
  }
  function fmtUTC(iso){
    var d=new Date(iso);
    if(isNaN(d))return iso;
    var p=function(n){return (n<10?'0':'')+n;};
    return p(d.getDate())+'.'+p(d.getMonth()+1)+' '+p(d.getHours())+':'+p(d.getMinutes())+' UTC';
  }

  var frames=[],idx=0,playing=false,timer=null,overlay=null,cur=null;
  var elPlay=document.getElementById('play');
  var elTime=document.getElementById('time');
  var elSegs=document.getElementById('segs');
  var elStatus=document.getElementById('status');

  function setStatus(t){elStatus.textContent=t;elStatus.classList.add('show');}
  function clearStatus(){elStatus.classList.remove('show');}

  var cache={};
  function loadRaw(url,cb){
    if(cache[url]){cb(cache[url]);return;}
    var img=new Image();
    img.crossOrigin='anonymous';
    img.onload=function(){
      try{
        var c=document.createElement('canvas');c.width=256;c.height=256;
        var ctx=c.getContext('2d');ctx.drawImage(img,0,0);
        var id=ctx.getImageData(0,0,256,256);
        var d=id.data,a=new Uint8Array(d);
        cache[url]=a;cb(a);
      }catch(e){cb(null);}
    };
    img.onerror=function(){cb(null);};
    img.src=url;
  }

  // Прямой 1:1 рендер: каждый пиксель читает R-канал тайла того же зума.
  function renderTile(coords){
    var tile=document.createElement('canvas');
    tile.width=256;tile.height=256;
    var url=tileURL(coords.z,coords.x,coords.y,cur.time);
    loadRaw(url,function(raw){
      if(!raw){tile.complete=false;return;}
      try{
        var out=new Uint8ClampedArray(256*256*4);
        for(var i=0;i<256;i++)for(var j=0;j<256;j++){
          var r=raw[(i*256+j)*4];
          if(r>2){
            var ii=Math.round(r/255*(PAL.length-4));
            if(ii<0)ii=0;
            if(ii>PAL.length-4)ii=PAL.length-4;
            var oi=(i*256+j)*4;
            out[oi]=PAL[ii];out[oi+1]=PAL[ii+1];out[oi+2]=PAL[ii+2];out[oi+3]=PAL[ii+3];
          }
        }
        tile.getContext('2d').putImageData(new ImageData(out,256,256),0,0);
        tile.complete=true;
      }catch(e){tile.complete=false;}
    });
    return tile;
  }

  var NowcastLayer=L.GridLayer.extend({
    options:{minZoom:3,maxZoom:10,opacity:0.9,attribution:'Наукастинг: <a href="https://meteoinfo.ru/nowcasting">Гидрометцентр</a>'},
    createTile:function(coords,done){
      var tile=renderTile(coords);
      setTimeout(function poll(){
        if(tile.complete===true){done(null,tile);}
        else if(tile.complete===false){done(new Error('tile error'),tile);}
        else{setTimeout(poll,30);}
      },0);
      return tile;
    }
  });

  function renderSegs(){
    elSegs.innerHTML='';
    frames.forEach(function(f,i){
      var d=document.createElement('div');
      d.title=fmtUTC(f.time);
      d.addEventListener('click',function(){showFrame(i);});
      elSegs.appendChild(d);
    });
    elSegs.childNodes.forEach(function(c,j){c.classList.toggle('on',j===idx);});
  }

  function showFrame(i){
    if(!frames.length)return;
    i=Math.max(0,Math.min(frames.length-1,i));
    idx=i;cur=frames[i];
    if(overlay){overlay.redraw();}
    else{overlay=new NowcastLayer({}).addTo(map);}
    elTime.textContent=fmtUTC(cur.time);
    if(elSegs.children.length===frames.length){
      for(var j=0;j<elSegs.children.length;j++)elSegs.children[j].classList.toggle('on',j===i);
    }
  }

  function togglePlay(){
    if(!frames.length)return;
    playing=!playing;
    elPlay.textContent=playing?'⏸':'▶';
    elPlay.classList.toggle('playing',playing);
    if(playing){
      if(idx>=frames.length-1)showFrame(0);
      timer=setInterval(function step(){
        if(idx+1<frames.length){showFrame(idx+1);}
        else{playing=false;elPlay.textContent='▶';elPlay.classList.remove('playing');clearInterval(timer);timer=null;}
      },600);
    }else{clearInterval(timer);timer=null;}
  }

  elPlay.addEventListener('click',togglePlay);
  elSegs.addEventListener('click',function(e){
    var t=e.target;
    while(t&&t!==elSegs&&t.parentNode!==elSegs)t=t.parentNode;
    if(t&&t!==elSegs&&t.parentNode===elSegs){
      if(playing){playing=false;elPlay.textContent='▶';elPlay.classList.remove('playing');clearInterval(timer);timer=null;}
      showFrame(Array.prototype.indexOf.call(elSegs.children,t));
    }
  });

  var loading=false;
  function load(){
    if(loading)return;
    loading=true;
    setStatus('Загрузка…');
    var ctrl=typeof AbortController!=='undefined'?new AbortController():null;
    var tid=ctrl?setTimeout(function(){ctrl.abort();},15000):null;
    fetch(CAP_URL+'?t='+Math.floor(Date.now()/1e3),{cache:'no-store',signal:ctrl?ctrl.signal:undefined})
      .then(function(r){if(!r.ok)throw new Error('HTTP '+r.status);return r.text();})
      .then(function(txt){
        if(tid)clearTimeout(tid);
        var times=parseTimes(txt);
        var last=times.length?times[times.length-1]:null;
        if(!times.length||!last){throw new Error('нет кадров');}
        frames=times.map(function(t){
          return {time:t,current:t===last};
        });
        if(overlay){map.removeLayer(overlay);overlay=null;}
        renderSegs();
        showFrame(frames.length-1);
        clearStatus();
        loading=false;
      })
      .catch(function(e){
        if(tid)clearTimeout(tid);
        loading=false;
        setStatus('Наукастинг недоступен: '+e.message);
        setTimeout(load,30000);
      });
  }

  load();
  setInterval(load,5*60*1000); // автообновление кадров раз в 5 минут
})();
</script>
</body>
</html>
```

- [ ] **Step 2: Верифицировать, что маркеры на месте и структура корректна**

Run: `python -m pytest tests/test_radar.py -q` (убедиться, что старые тесты не зависят от отсутствия nowcast_template).
Затем простой синтаксический контроль JS (нет спелл-ошибок) — поискать `'{'`/`'}'` баланс вручную нельзя, поэтому:
Run: `python -c "import pathlib; s=pathlib.Path('nowcast_template.html').read_text(encoding='utf-8'); [print('missing', m) for m in ('/*__LEAFLET__*/','/*__LEAFLET_CSS__*/','/*__PALETTE__*/') if m not in s]; print('markers ok')"`
Expected: `markers ok`.

- [ ] **Step 3: Commit**

```bash
git add nowcast_template.html
git commit -m "feat(nowcast): add satelite/nowcast page template (ГМЦ)"
```

---

### Task 3: Обобщить билдер (radar + nowcast) и собрать `nowcast.html`

**Files:**
- Modify: `tools/build_radar.py`
- Create (результат сборки): `nowcast.html`
- Test: `tests/test_build.py` (новый)

**Interfaces:**
- Consumes: `nowcast_template.html` (Task 2), `tools/leaflet.js`, `tools/leaflet.css`, `tools/palette.js`.
- Produces: `nowcast.html` на диске; гарантия, что `radar.html` пересобирается так же, как раньше.

> Требование «НЕ изменять build_radar.py» относится к его роли в production radar.html. Здесь мы его обобщаем, но **сон = результат radar.html обязан остаться идентичным** (тест ниже это проверяет).

- [ ] **Step 1: Write the failing test** `tests/test_build.py`

```python
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(HERE, "tools")
BUILD = os.path.join(TOOLS, "build_radar.py")
NOWCAST_TEMPLATE = os.path.join(HERE, "nowcast_template.html")
NOWCAST_OUT = os.path.join(HERE, "nowcast.html")


def test_nowcast_template_has_required_placeholders():
    with open(NOWCAST_TEMPLATE, encoding="utf-8") as f:
        s = f.read()
    for m in ("/*__LEAFLET__*/", "/*__LEAFLET_CSS__*/", "/*__PALETTE__*/"):
        assert m in s


def test_build_script_defines_nowcast_output():
    with open(BUILD, encoding="utf-8") as f:
        s = f.read()
    assert "nowcast_template.html" in s
    assert "nowcast.html" in s
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_build.py -q`
Expected: FAIL — `nowcast_template.html` есть (Task2), но билдер ещё не пишет nowcast.html, поэтому `test_build_script_defines_nowcast_output` падает.

- [ ] **Step 3: Modify `tools/build_radar.py`** — обобщить на несколько HTML:

Заменить содержимое файла целиком:

```python
#!/usr/bin/env python3
"""Собирает radar.html и nowcast.html: инлайнит Leaflet 1.6.0, CSS и палитру
из tools/ в HTML-шаблоны (radar_template.html, nowcast_template.html)."""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LEAFLET = os.path.join(ROOT, "tools", "leaflet.js")
LEAFLET_CSS = os.path.join(ROOT, "tools", "leaflet.css")
PALETTE = os.path.join(ROOT, "tools", "palette.js")

# name -> (template, out)
TARGETS = {
    "radar": (os.path.join(ROOT, "radar_template.html"),
              os.path.join(ROOT, "radar.html")),
    "nowcast": (os.path.join(ROOT, "nowcast_template.html"),
                os.path.join(ROOT, "nowcast.html")),
}

MARKERS = ("/*__LEAFLET__*/", "/*__LEAFLET_CSS__*/", "/*__PALETTE__*/")


def _read(p):
    with open(p, encoding="utf-8", errors="replace") as f:
        return f.read()


def build(name=None):
    for p in (LEAFLET, LEAFLET_CSS, PALETTE):
        if not os.path.isfile(p):
            sys.exit(f"error: missing {p}")
    assets = {
        "/*__LEAFLET__*/": _read(LEAFLET),
        "/*__LEAFLET_CSS__*/": _read(LEAFLET_CSS),
        "/*__PALETTE__*/": _read(PALETTE),
    }
    targets = {name: TARGETS[name]} if name else TARGETS
    for n, (tpl, out) in targets.items():
        if not os.path.isfile(tpl):
            sys.exit(f"error: template not found: {tpl}")
        template = _read(tpl)
        for marker in MARKERS:
            assert marker in template, f"placeholder missing in {tpl}: {marker}"
        html = template
        for marker, content in assets.items():
            html = html.replace(marker, content)
        with open(out, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[ok] {out} written ({os.path.getsize(out)} bytes)")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        build(sys.argv[1])
    else:
        build()
```

- [ ] **Step 4: Run tests to verify they pass + собрать оба HTML**

Run: `python -m pytest tests/test_build.py -q` → 2 passed.
Run: `python tools/build_radar.py` → выводит `[ok] .../radar.html` и `[ok] .../nowcast.html` (оба).

- [ ] **Step 5: Регрессия — radar.html не изменился по содержимому**

Run: `git diff --stat radar.html`
Expected: **пусто** (radar.html не изменился). Если отличается — билдер изменил продукт радара; проверить, что порядок замен не влияет (радар не содержит nowcast-специфики).

- [ ] **Step 6: Проверить nowcast.html корректно собран**

Run: `python -c "import pathlib; s=pathlib.Path('nowcast.html').read_text(encoding='utf-8'); assert 'function parseTimes' in s; assert 'ncgi.php' in s; assert '/res/nowcast/' in s; assert 'L.map(' in s; print('nowcast.html ok', len(s))"`
Expected: `nowcast.html ok <размер>`.

- [ ] **Step 7: Commit**

```bash
git add tools/build_radar.py tests/test_build.py nowcast.html
git commit -m "feat(nowcast): generalize builder to emit nowcast.html"
```

---

### Task 4: Вкладка «Спутник» в `template.html` (шапка сайта)

**Files:**
- Modify: `template.html`
- Test: `tests/test_radar.py` (добавить ассерты в этой же записи) либо новый `tests/test_sputnik_tab.py`

**Interfaces:**
- Consumes: `nowcast.html` (Task 3) как iframe src.
- Produces: кнопка `data-tab="satellite"`, панель `#tab-satellite` с `#satellite-frame`, ленивая установка src, вызов в `updateSputnikFrame()`.

- [ ] **Step 1: Добавить кнопку в шапку вкладок**

В `template.html` строка 159 (`<button data-tab="radar">Радар</button>`) — сразу после неё добавить:

```html
  <button data-tab="satellite">Спутник</button>
```

- [ ] **Step 2: Добавить панель** — после панели радара (строка 175 `</div>` у `#tab-radar`) вставить:

```html
<div id="tab-satellite" class="panel">
  <iframe id="satellite-frame" title="Спутник"></iframe>
</div>
```

- [ ] **Step 3: Включить вкладку в переключение** — строка 311:

`['weather','forecast','radar','compare','accuracy','help']` → добавить `'satellite'`:

```js
  ['weather','forecast','radar','compare','accuracy','satellite','help'].forEach(t=>document.getElementById('tab-'+t).classList.toggle('active',b.dataset.tab===t));
```

- [ ] **Step 4: Ленивая загрузка iframe** — в том же обработчике после `if(b.dataset.tab==='radar'){...}` (строка 312-315) добавить:

```js
  if(b.dataset.tab==='satellite'){
    const f=document.getElementById('satellite-frame');
    if(f&&f.dataset.sputnikSrc&&f.dataset.sputnikSrc!==f.dataset.loadedSputnik){f.src=f.dataset.sputnikSrc;f.dataset.loadedSputnik=f.dataset.sputnikSrc;}
  }
```

- [ ] **Step 5: Функция установки URL** — рядом с `updateRadarFrame` (строка 982-990) добавить и вызвать:

```js
function updateSputnikFrame(){
  const f=document.getElementById('satellite-frame');
  if(!f||!D.location)return;
  const url='nowcast.html?lat='+D.location.lat+'&lon='+D.location.lon+'&zoom=8';
  if(f.dataset.sputnikSrc===url)return;
  f.dataset.sputnikSrc=url;
  const tab=document.getElementById('tab-satellite');
  if(tab&&tab.classList.contains('active'))f.src=url;
}
```

И в `renderAll()`, сразу после `updateRadarFrame();` (строка 967) добавить вызов:

```js
  updateSputnikFrame();
```

- [ ] **Step 6: Write the failing test** — добавить в `tests/test_radar.py`:

```python
def test_index_has_sputnik_tab_and_iframe():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert 'data-tab="satellite"' in tpl
    assert '<button data-tab="satellite">Спутник</button>' in tpl
    assert 'id="satellite-frame"' in tpl
    assert "updateSputnikFrame()" in tpl
    assert "'satellite'" in tpl
```

- [ ] **Step 7: Run test to verify it passes**

Run: `python -m pytest tests/test_radar.py -q`
Expected: новый тест + старые проходят (все PASS).

- [ ] **Step 8: Commit**

```bash
git add template.html tests/test_radar.py
git commit -m "feat(nowcast): add Спутник tab in site header"
```

---

### Task 5: Deploy — копировать `nowcast.html` в `_site`

**Files:**
- Modify: `.github/workflows/deploy.yml`

- [ ] **Step 1: Добавить копирование** — строка 64 area (после `cp radar.html _site/`):

```yaml
          cp nowcast.html _site/
```

- [ ] **Step 2: Проверить YAML** — согласуется с соседними строками (отступ 10 пробелов, как соседние `cp ... _site/`).

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/deploy.yml
git commit -m "chore(nowcast): ship nowcast.html to Pages"
```

---

### Task 6: Полный прогон тестов и ручная интеграционная проверка

**Files:** нет изменений кода (только проверка).

- [ ] **Step 1: Прогнать весь pytest (без сети)**

Run: `python -m pytest tests/ -m "not integration" -q`
Expected: **все PASS** (ранее 181; плюс новые test_nowcast/test_build/test_radar). Зафиксировать число.

- [ ] **Step 2: Локальная сборка** 

Run: `python tools/build_radar.py` → оба HTML собраны. `git diff --stat radar.html` пустой.

- [ ] **Step 3: Интеграционная проверка (используя сеть; НЕ в CI)**

Скрипт `C:\Users\SamLab\AppData\Local\Temp\opencode\verify_nowcast.py`:

```python
import json, sys
sys.path.insert(0, r"F:\Meteo")
from tools import nowcast
import urllib.request

def get(u, timeout=40):
    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, dict(r.getheaders()), r.read()

s, h, body = get(nowcast.CAP_URL)
print("capabilities status", s, "ACAO", h.get("Access-Control-Allow-Origin"))
times = nowcast.parse_capabilities_times(body.decode("utf-8", "replace"))
print("frames:", len(times), "first", times[0] if times else None, "last", times[-1] if times else None)
assert len(times) >= 1

# тайл на Ярославль (z=7, x/y по deg2tile)
import math
def deg2tile(lat, lon, z):
    latr = math.radians(lat); n = 2.0**z
    return int((lon+180)/360*n), int((1-math.asinh(math.tan(latr))/math.pi)/2*n)
z, x, y = 7, *deg2tile(57.63, 39.87, 7)
url = nowcast.tile_url(z, x, y, times[-1])
s2, h2, body2 = get(url)
print("tile status", s2, "content-type", h2.get("Content-Type"), "len", len(body2))
assert s2 == 200 and body2[:8] == b"\x89PNG\r\n\x1a\n"
print("INTEGRATION OK")
```

Run: `& "F:\Meteo\.venv\Scripts\python.exe" "C:\Users\SamLab\AppData\Local\Temp\opencode\verify_nowcast.py"`
Expected: `capabilities status 200`, `frames: N`, `tile status 200`, `INTEGRATION OK`.

- [ ] **Step 4: Ручная проверка в браузере** (пользователю): открыть сайт → вкладка «Спутник» → карта отображает базу, подписи, молнии, таймлайн (10-мин кадры), кнопку play, легенду. В сухую погоду тайлы прозрачны (норма). Вкладка «Радар» по-прежнему работает.

- [ ] **Step 5: Завершение** — если всё ок, финальный коммит обновлений (если появились) и предложить деплой/мерж по `finishing-a-development-branch` skill.

---

## Self-Review (проверка перед передачей)

### Покрытие спеки
- Вкладка «Спутник» отдельная со своим iframe — Task 4 ✓
- Отдельная страница nowcast.html, билдер, «не трогать радар» (radar.html/radar_template не правятся содержательно; билдер обобщён с регрессионной защитой radar.html) — Task 3, 5 ✓
- База-карта, подписи, молнии, таймлайн+play, легенда — Task 2 ✓
- Слой наукастинга: чтение R-канала → PAL — Task 2 (renderTile, NowcastLayer) ✓
- Автообновление раз в 5 минут — Task 2 (`setInterval(load,5*60*1000)`) ✓
- Ошибки → статус + повтор — Task 2 (catch → setStatus → setTimeout(load,30000)) ✓
- Юнит-тесты парсинга/URL — Task 1 ✓; сборка — Task 3 ✓; деплой — Task 5 ✓
- Кнопки «← Радар» НЕТ — не добавляется ✓

### Проверка на плейсхолдеры
- Нет «TBD/TODO/аналогично» — код выписан полностью в каждом шаге.
- Дублированный JS-код (lightning/labels) приведён полностью, не «как в радаре».

### Типовая согласованность
- `parse_capabilities_times` (Python) и `parseTimes` (JS) — оба возвращают упорядоченный список ISO-строк; `tile_path`/`tile_url` и `tileURL` (JS) строят один формат `{z}0{x}0{y}`; длина пути тестируется в Task 1 (`6039019`).
- `tile_url(z,x,y,inidt)` и `tileURL(z,x,y,inidt)` сигнатуры совпадают.
- `renderTile`/`NowcastLayer`/`showFrame`/`load` согласованы внутри Task 2 (одни имена `cur.time`, `frames`, `overlay`, `elSegs`).

### Открытое замечание
- B `Task 2` JS использует `.filter(Boolean)` и `String.prototype.trim` — совместимо с современными браузерами (и так используется в radar_template). Ок.
- Восстановление из кэша при ошибке (как radar `rr_manifest`) для наукастинга не делаем — горизонт всего 2 ч, кэш малополезен. Это осознанное упрощение (YAGNI).
