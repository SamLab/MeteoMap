# RainRadar Source Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Switch the radar overlay in `radar.html` from RainViewer to rainradar.ru, replicating the source app's resampling algorithm and palette 1:1.

**Architecture:** Replace RainViewer manifest fetch + `RecolorLayer` (TileLayer with LUT recolor) in `radar_template.html` with a rainradar manifest fetch + `L.GridLayer` that loads raw 264×264 PNG tiles, resamples them bicubically to 256×256 view tiles, and colors them via a 700-shade RGBA LUT built from the source's 10 palette stops. UI (timeline, play, zoom, OSM basemap) unchanged.

**Tech Stack:** Leaflet 1.6.0 (already inlined), vanilla JS in `radar_template.html`, Python build via `tools/build_radar.py`, pytest.

## Global Constraints

- Data source is `https://rainradar.ru/composite/` only — no `api.rainviewer.com` / `tilecache.rainviewer.com` remains anywhere in the produced `radar.html`.
- Overlay zoom range: `minZoom:3`, `maxZoom:10`, `opacity:0.9`, no `maxNativeZoom`.
- datazoom rule: `view_zoom > 7 ? 5 : view_zoom > 5 ? 4 : 3` (group index `dz-3`).
- `scale = Math.pow(2, dz - view_zoom)`; data tile `dataX=Math.floor(vx*scale)`, `dataY=Math.floor(vy*scale)`; coverage key `dataX+"|"+dataY`.
- Palette: original rainradar 10 stops `[0,[146,163,185,0]],[1,[146,161,181,.8]],[5,[103,104,158,1]],[11,[56,64,128,1]],[15,[29,175,87,1]],[30,[255,247,0,1]],[40,[255,174,0,1]],[47,[226,40,86,1]],[58,[169,10,158,1]],[60,[169,10,158,1]]`, built as CSS-linear-gradient → 700 shades LUT.
- `future` is always `false`; timeline shows last (newest) frame first; no `(прогноз)` suffix.
- All tiles/requests to rainradar.ru go through CORS (`Access-Control-Allow-Origin: *` verified), `crossOrigin='anonymous'`.
- Attribution `© rainradar.ru`.
- No external CDNs at runtime; everything inlined by `tools/build_radar.py`. `bot.php` never committed. Deploy via GitHub Actions `deploy.yml` from `main`.
- Do NOT commit files under `h:\`; commit only workspace files.

---

### Task 1: Palette LUT in tools/palette.js

**Files:**
- Modify: `F:\Meteo\tools\palette.js` (replace entire content)
- Test: `F:\Meteo\tests\test_radar.py` (`test_radar_palette_has_12_rainradar_colors` → replaced)

**Interfaces:**
- Consumes: nothing.
- Produces: `var RR_COLORS=...` (10 stops `[value,[r,g,b,a]]`), `var PAL=...` (`Uint8ClampedArray` 700×4 RGBA LUT built from `RR_COLORS`). Used by Task 2 as `PAL`.

- [ ] **Step 1: Write the failing test**

Edit `test_radar_palette_has_12_rainradar_colors` in `F:\Meteo\tests\test_radar.py` to:

```python
def test_radar_palette_has_original_rainradar_colors():
    with open(os.path.join(HERE, "tools", "palette.js"), encoding="utf-8") as f:
        pal = f.read()
    assert "var RR_COLORS=" in pal
    assert "var PAL=" in pal
    assert "146,163,185" in pal
    assert "169,10,158" in pal
    assert "var RV=" not in pal
    assert "var RR=" not in pal
    assert "var LUT=" not in pal
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_radar.py::test_radar_palette_has_original_rainradar_colors -v` (workdir `F:\Meteo`)
Expected: FAIL (old palette.js still has `var RV=`, no `var RR_COLORS=`).

- [ ] **Step 3: Write the implementation**

Replace the whole content of `F:\Meteo\tools\palette.js` with:

```js
var RR_COLORS=[[0,[146,163,185,0]],[1,[146,161,181,.8]],[5,[103,104,158,1]],[11,[56,64,128,1]],[15,[29,175,87,1]],[30,[255,247,0,1]],[40,[255,174,0,1]],[47,[226,40,86,1]],[58,[169,10,158,1]],[60,[169,10,158,1]]];
var PAL=(function(){
  var n=700,s=document.createElement('canvas'),i=s.getContext('2d'),g=i.createLinearGradient(0,0,n,0);
  s.width=n;s.height=30;
  for(var a=0;a<RR_COLORS.length-1;a++)g.addColorStop(RR_COLORS[a][0]/70,'rgba('+RR_COLORS[a][1]+')');
  i.fillStyle=g;i.fillRect(0,0,n,30);
  return i.getImageData(0,0,n,1).data;
})();
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_radar.py::test_radar_palette_has_original_rainradar_colors -v` (workdir `F:\Meteo`)
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/palette.js tests/test_radar.py
git commit -m "feat: replace palette with original rainradar stops+LUT"
```

---

### Task 2: RainRadar data loading + resampling overlay in radar_template.html

**Files:**
- Modify: `F:\Meteo\radar_template.html` (JS section between `<script>` tags at lines ~52-193; legend gradient line 24; no other UI changes)
- Test: `F:\Meteo\tests\test_radar.py`

**Interfaces:**
- Consumes: `RR_COLORS`, `PAL` from Task 1 (inlined via `/*__PALETTE__*/`).
- Produces: manifest fetch + `RadarLayer` GridLayer in `radar.html`; frames array `{time, sets}` where `sets[0..2]` are coverage objects `{"x|y":1}`.

- [ ] **Step 1: Write the failing test**

Replace `test_radar_html_is_built_and_self_contained`, `test_radar_uses_light_rainradar_theme`, `test_radar_palette_has_12_rainradar_colors` in `F:\Meteo\tests\test_radar.py` with:

```python
def test_radar_html_is_built_and_self_contained():
    with open(os.path.join(HERE, "radar.html"), encoding="utf-8") as f:
        radar = f.read()
    assert "/*__LEAFLET__*/" not in radar
    assert "/*__PALETTE__*/" not in radar
    assert "/*__LEAFLET_CSS__*/" not in radar
    assert ".leaflet-tile-container" in radar
    assert "window.L=e" in radar
    assert "var RR_COLORS=" in radar
    assert "var PAL=" in radar
    assert "rainradar.ru/composite/manifest.json" in radar
    assert "tile.openstreetmap.org" in radar
    assert "maxNativeZoom:7" not in radar
    assert "tilecache.rainviewer.com" not in radar
    assert "api.rainviewer.com" not in radar
    assert "RainViewer" not in radar
    assert "RadarLayer" in radar


def test_radar_uses_rainradar_overlay():
    with open(os.path.join(HERE, "radar.html"), encoding="utf-8") as f:
        radar = f.read()
    assert "Math.pow(2,dz-z)" in radar
    assert "dataX+'|'+dataY" in radar
    assert "minZoom:3" in radar
    assert "maxZoom:10" in radar
    assert "opacity:0.9" in radar
    assert "crossOrigin='anonymous'" in radar
    assert "© rainradar.ru" in radar


def test_radar_palette_has_original_rainradar_colors():
    with open(os.path.join(HERE, "tools", "palette.js"), encoding="utf-8") as f:
        pal = f.read()
    assert "var RR_COLORS=" in pal
    assert "var PAL=" in pal
    assert "146,163,185" in pal
    assert "169,10,158" in pal
    assert "var RV=" not in pal
    assert "var RR=" not in pal
    assert "var LUT=" not in pal
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_radar.py -v` (workdir `F:\Meteo`)
Expected: FAIL (current `radar.html` has `maxNativeZoom:7`, `api.rainviewer.com`, no `RadarLayer`). Note: test reads built `radar.html`; first run may fail also on stale build — that's fine.

- [ ] **Step 3: Write the implementation**

In `F:\Meteo\radar_template.html`:

3a. Update the legend gradient (line 24) to original rainradar colors:

```html
#legend .g{width:180px;height:10px;border-radius:9px;background:linear-gradient(to right,#92a1b5,#67689e,#384080,#1daf57,#fff700,#ffae00,#e22856,#a90a9e);margin:0 8px}
```

3b. Replace the entire IIFE `<script>` block (current lines 52-193) with:

```html
<script>
(function(){
  var params=new URLSearchParams(location.search);
  var lat=parseFloat(params.get('lat'))||57.63;
  var lon=parseFloat(params.get('lon'))||39.87;
  var zoom=parseInt(params.get('zoom')||'8',10);
  var map=L.map('map',{zoomControl:true,minZoom:3,maxZoom:10}).setView([lat,lon],zoom);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{
    maxZoom:10,className:'lightbase',attribution:'© OpenStreetMap contributors'
  }).addTo(map);

  var frames=[],idx=0,playing=false,timer=null,overlay=null,cur=null;
  var elPlay=document.getElementById('play');
  var elTime=document.getElementById('time');
  var elSegs=document.getElementById('segs');
  var elStatus=document.getElementById('status');

  function setStatus(t){elStatus.textContent=t;elStatus.classList.add('show');}
  function clearStatus(){elStatus.classList.remove('show');}
  function fmtTime(ts){
    var d=new Date(ts*1000);
    var p=function(n){return (n<10?'0':'')+n;};
    return p(d.getDate())+'.'+p(d.getMonth()+1)+' '+p(d.getHours())+':'+p(d.getMinutes());
  }
  function getDataZoom(z){return z>7?5:z>5?4:3;}
  function getScale(dz,z){return Math.pow(2,dz-z);}

  var rawCache={};
  function loadRaw(url,cb){
    if(rawCache[url]){cb(rawCache[url]);return;}
    var img=new Image();
    img.crossOrigin='anonymous';
    img.onload=function(){
      try{
        var c=document.createElement('canvas');c.width=264;c.height=264;
        var ctx=c.getContext('2d');ctx.drawImage(img,0,0);
        var id=ctx.getImageData(0,0,264,264);
        var d=id.data,a=new Uint8Array(264*264);
        for(var i=0;i<d.length;i+=4)a[i/4]=d[i];
        rawCache[url]=a;cb(a);
      }catch(e){cb(null);}
    };
    img.onerror=function(){cb(null);};
    img.src=url;
  }

  function renderTile(e,vx,vy,dz,z,sets){
    var scale=getScale(dz,z);
    var dataX=Math.floor(vx*scale),dataY=Math.floor(vy*scale);
    var tile=document.createElement('canvas');
    tile.width=256;tile.height=256;
    if(!sets[dz-3]||!sets[dz-3][dataX+'|'+dataY]){tile.complete=true;return tile;}
    var url='https://rainradar.ru/composite/'+cur.time+'/'+dz+'/'+dataX+'_'+dataY+'.png';
    loadRaw(url,function(raw){
      if(!raw){tile.complete=false;return;}
      try{
        var B=256*vx,Y=256*vy,K=256*dataX,V=256*dataY;
        var out=new Uint8ClampedArray(256*256*4);
        var X=-1,Q=-1;
        for(var m=0;m<256;m++)for(var h=0;h<256;h++){
          var N=(B+m)*scale-K,D=(Y+h)*scale-V;
          var s=Math.floor(D),o=Math.floor(N),n=N-o,C=D-s;
          if(o!==X||s!==Q){
            var l=o+3+(s+3)*264,c=o+3+(s+4)*264,r=o+3+(s+5)*264,a=o+3+(s+6)*264;
            var E=raw[l],k=raw[l+1],d=raw[l+2],P=raw[l+3];
            var u=raw[c],A=raw[c+1],x=raw[c+2],S=raw[c+3];
            var O=raw[r],w=raw[r+1],_=raw[r+2],R=raw[r+3];
            var g=raw[a],p=raw[a+1],f=raw[a+2],M=raw[a+3];
            var H=3*(k-d)+P-E+2*E-5*k+4*d-P;
            var W=3*(A-x)+S-u+2*u-5*A+4*x-S;
            var G=3*(w-_)+R-O+2*O-5*w+4*_-R;
            var U=3*(p-f)+M-g+2*g-5*p+4*f-M;
            X=o;Q=s;
          }
          var b=.5*(d-E+H*n*n)*n+k;
          var j=.5*(x-u+W*n*n)*n+A;
          var y=.5*(_-O+G*n*n)*n+w;
          var L=.5*(f-g+U*n*n)*n+p;
          var v=.5*(y-b+(2*b-5*j+4*y-L+(3*(j-y)+L-b)*C)*C)*C+j;
          if(v>0){
            var ii=Math.round(v/70*700)*4;
            if(ii>PAL.length-4)ii=PAL.length-4;
            var oi=(h*256+m)*4;
            out[oi]=PAL[ii];out[oi+1]=PAL[ii+1];out[oi+2]=PAL[ii+2];out[oi+3]=PAL[ii+3];
          }
        }
        tile.getContext('2d').putImageData(new ImageData(out,256,256),0,0);
        tile.complete=true;
      }catch(e){tile.complete=false;}
    });
    return tile;
  }

  var RadarLayer=L.GridLayer.extend({
    options:{minZoom:3,maxZoom:10,opacity:0.9,attribution:'© rainradar.ru'},
    createTile:function(coords,done){
      var tile=renderTile(coords.x,coords.y,coords.z,getDataZoom(coords.z),cur.sets);
      var self=this;
      var check=function(){
        if(tile.complete){done(null,tile);}
        else if(tile.complete===false){done(new Error('tile error'),tile);}
        else{setTimeout(check,30);}
      };
      check();
      return tile;
    }
  });

  function renderSegs(){
    elSegs.innerHTML='';
    frames.forEach(function(f,i){
      var d=document.createElement('div');
      d.title=fmtTime(f.time);
      d.addEventListener('click',function(){showFrame(i);});
      elSegs.appendChild(d);
    });
    elSegs.childNodes.forEach(function(c,j){c.classList.toggle('on',j===idx);});
  }

  function showFrame(i){
    if(!frames.length)return;
    i=Math.max(0,Math.min(frames.length-1,i));
    idx=i;cur=frames[i];
    if(overlay){map.removeLayer(overlay);}
    overlay=new RadarLayer('',{}).addTo(map);
    elTime.textContent=fmtTime(cur.time);
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
      timer=setInterval(function(){showFrame(idx+1<frames.length?idx+1:0);},600);
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

  function load(){
    setStatus('Загрузка…');
    fetch('https://rainradar.ru/composite/manifest.json?t='+Math.floor(Date.now()/1e3),{cache:'no-store'})
      .then(function(r){if(!r.ok)throw new Error('HTTP '+r.status);return r.json();})
      .then(function(d){
        frames=d.map(function(f){
          var sets=[{},{},{}];
          for(var g=0;g<3;g++){
            var list=f[1][g]||[];
            for(var i2=0;i2<list.length;i2++)sets[g][list[i2][0]+'|'+list[i2][1]]=1;
          }
          return {time:f[0],sets:sets,future:false};
        }).sort(function(a,b){return a.time-b.time;});
        if(!frames.length)throw new Error('нет кадров');
        renderSegs();
        showFrame(frames.length-1);
        clearStatus();
      })
      .catch(function(e){
        setStatus('Радар недоступен: '+e.message);
        setTimeout(load,30000);
      });
  }

  load();
  setInterval(load,5*60*1000);
})();
</script>
```

Note: `renderTile` returns the tile synchronously (canvas). Coverage is checked synchronously against `sets[dz-3]`. `loadRaw` is async — the `check()` loop in `createTile` polls `tile.complete` (set in the async callback). `vars` inside the `if(o!==X||s!==Q)` block are function-scoped (no `let`), matching the minified source semantics.

- [ ] **Step 4: Rebuild and run tests**

Run (workdir `F:\Meteo`):
```
python tools/build_radar.py
python -m pytest tests/test_radar.py -v
```
Expected: build prints `[ok] radar.html written (...)`, all radar tests PASS.

- [ ] **Step 5: Commit**

```bash
git add radar_template.html radar.html tests/test_radar.py
git commit -m "feat: switch radar overlay to rainradar.ru with bicubic resampling"
```

---

### Task 3: Live verification against rainradar.ru

**Files:**
- None created (verification only, via headless probe in `C:\Users\SamLab\AppData\Local\Temp\opencode`).

- [ ] **Step 1: Write a headless probe** (`C:\Users\SamLab\AppData\Local\Temp\opencode\check_rainradar.py`):

```python
import json, sys, time
import urllib.request
from selenium import webdriver
from selenium.webdriver.edge.options import Options

BASE = "file:///F:/Meteo/radar.html"

def fetch(url):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()

def main():
    m = json.loads(fetch("https://rainradar.ru/composite/manifest.json?t=" + str(int(time.time()))))
    newest = m[0]
    ts = newest[0]
    groups = newest[1]
    print("manifest frames:", len(m), "newest ts:", ts)
    print("group counts z3/z4/z5:", len(groups[0]), len(groups[1]), len(groups[2]))

    opt = Options()
    opt.add_argument("--headless")
    opt.add_argument("--window-size=1200,900")
    drv = webdriver.Edge(options=opt)
    try:
        drv.get(BASE + "?lat=57.55&lon=35.03&zoom=8")
        time.sleep(12)
        canvas_js = """
        var canvases = document.querySelectorAll('.leaflet-tile-pane canvas');
        var hits = 0, total = 0;
        for (var i = 0; i < canvases.length; i++) {
          var c = canvases[i];
          var w = c.width, h = c.height;
          if (w !== 256 || h !== 256) continue;
          var ctx = c.getContext('2d');
          var id = ctx.getImageData(0, 0, w, h).data;
          for (var j = 0; j < id.length; j += 4) {
            total++;
            if (id[j+3] > 0) hits++;
          }
        }
        return {hits: hits, total: total};
        """
        res = drv.execute_script(canvas_js)
        print("radar.html overlay non-transparent pixels:", res)
        status = drv.execute_script("return document.getElementById('status').textContent;")
        print("status:", repr(status))
        assert res["hits"] > 0, "no precipitation pixels rendered over Tver"
        print("LIVE CHECK PASSED")
    finally:
        drv.quit()

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run probe**

Run: `python C:\Users\SamLab\AppData\Local\Temp\opencode\check_rainradar.py`
Expected: `radar.html overlay non-transparent pixels: {'hits': >0, ...}`, `status: ''`, `LIVE CHECK PASSED`. If hits == 0, debug: fetch one data tile for Tver from `https://rainradar.ru/composite/{ts}/5/{dataX}_{dataY}.png` and verify non-zero red channel.

- [ ] **Step 3: (no commit — verification only)**

---

### Task 4: Full test suite + deploy

**Files:**
- None (runs + pushes).

- [ ] **Step 1: Run full test suite**

Run (workdir `F:\Meteo`): `python -m pytest -q`
Expected: all tests PASS (any pre-existing unrelated failures noted, not caused by this change).

- [ ] **Step 2: Confirm deploy pipeline config**

Read `F:\Meteo\.github\workflows\deploy.yml` — confirm it builds on push to `main` and deploys `radar.html` (and other static files).

- [ ] **Step 3: Push to deploy**

```bash
git add -A
git commit -m "feat: switch radar overlay source to rainradar.ru"
git push origin main
```
Expected: GitHub Actions `deploy.yml` runs to SUCCESS.

- [ ] **Step 4: Verify live URL**

Fetch the deployed page (from the Actions artifact/URL), run `python -m pytest tests/test_radar.py` against the deployed `radar.html` if the URL serves it; otherwise confirm CI green.
