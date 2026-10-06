# Metka vremeni snimka oblachnosti (GIBS) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pokazyvat na knopke-tumblere «Oblachnost» (#ctoggle) metku vremeni snimka oblachnosti po moskovskomu vremeni (format: data po MSK + pometka o dnevnom snimke Terra).

**Architecture:** V `nowcast_template.html` dobavit element `#ctime` v knopku, stili dlya nego, i v JS (`showCloudLayer`, vnutri callbacka `pickGIBSDate`) ustanovit podpis. Perepobrat `nowcast.html` billerom. GIBS daet snimok po date (UTC); tak kak snímok MODIS Terra dnevnoi (~13:30 MSK tot zhe den'), data po MSK sovpadayet s UTC-datoi iz URL.

**Tech Stack:** HTML/JS (Leaflet), Python biller `tools/build_radar.py`, pytest.

## Global Constraints

- Kritika metki: **na samoy knopke #ctoggle**, malenkiy tekst sprava.
- Format: **data po MSK + «den (Terra)»**, bez vydumannogo tochnogo vremeni.
- NE menyaem: `tools/nowcast.py`, istochnik (NASA GIBS), logiku vybora daty (`pickGIBSDate`), `radar.html`, `radar_template.html`, deploy.yml.
- Tekushchiy progon testov: 193 passed. Cel — 194 passed.
- Python v etom okruzhenii (Windows PowerShell): `& "F:\Meteo\.venv\Scripts\python.exe" ...`.
- Kod na LK bazirovan na podtverzhdennom dizayne `docs/superpowers/specs/2026-09-04-gibs-cloud-timelabel-design.md` i identichen yemu.

---

### Task 1: Podpis vremeni snimka na knopke «Oblachnost»

**Files:**
- Modify: `F:\Meteo\nowcast_template.html` (stroka 59 knopka; posle stroki 33 CSS; JS `showCloudLayer` na str. 115-124)
- Test: `F:\Meteo\tests\test_build.py` (dobavit marker-test)

**Interfaces:**
- Consumes: sushchestvuyushchiy klyuchevoy element `#ctoggle` i funktsiya `pickGIBSDate(cb)` s `cb(ds)`, gde `ds = 'YYYY-MM-DD'` (UTC-dата snimka).
- Produces: element `#ctime` v knopke s podpisью; funktsiya `mskLabel(d)` (lokalnaya v `showCloudLayer`).

- [ ] **Step 1: Write the failing marker test**

Dobavit v `F:\Meteo\tests\test_build.py` (v konec faila):

```python
def test_nowcast_template_has_cloud_timelabel():
    with open(NOWCAST_TEMPLATE, encoding="utf-8") as f:
        s = f.read()
    assert 'id="ctime"' in s
    assert "mskLabel" in s
    assert "MSK · den (Terra)" in s
```

- [ ] **Step 2: Run test to verify it fails**

Run: `& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests/test_build.py::test_nowcast_template_has_cloud_timelabel -q`
Expected: FAIL (`assert 'id="ctime"' in s` — ne naydeno).

- [ ] **Step 3: Add `#ctime` span to the button**

Modify: `F:\Meteo\nowcast_template.html` stroka 59.

Old:
```html
<button id="ctoggle" title="Спутниковая облачность NASA GIBS (дневной снимок)"><span class="ltdot"></span>Облачность</button>
```
New:
```html
<button id="ctoggle" title="Спутниковая облачность NASA GIBS (дневной снимок MODIS Terra, ~13:30 МСК)"><span class="ltdot"></span>Облачность<span id="ctime"></span></button>
```

- [ ] **Step 4: Add CSS for `#ctime`**

Modify: `F:\Meteo\nowcast_template.html` — dobavit posle stroki 33 (`#ctoggle.on .ltdot{background:#fff}`).

New:
```css
#ctoggle #ctime{font-size:10px;opacity:.85;font-weight:400;white-space:nowrap}
```

- [ ] **Step 5: Set the timelabel in JS**

Modify: `F:\Meteo\nowcast_template.html` — zamenit telo `showCloudLayer` (str. 115-124).

Old:
```js
  function showCloudLayer(){
    if(gibsLayer){map.addLayer(gibsLayer);return;}
    pickGIBSDate(function(ds){
      if(!ds)return;
      gibsLayer=L.tileLayer(GIBS_BASE+GIBS_PRODUCT+'/default/'+ds+'/GoogleMapsCompatible_Level9/9/{y}/{x}.jpg',{
        minZoom:3,maxZoom:10,minNativeZoom:9,maxNativeZoom:9,zIndex:900,opacity:0.9,
        attribution:'Спутник: <a href="https://earthdata.nasa.gov/">NASA GIBS</a>'
      }).addTo(map);
    });
  }
```
New:
```js
  function showCloudLayer(){
    if(gibsLayer){map.addLayer(gibsLayer);return;}
    pickGIBSDate(function(ds){
      if(!ds)return;
      function mskLabel(d){
        var p=d.split('-');
        return p[2]+'.'+p[1]+' MSK · den (Terra)';
      }
      document.getElementById('ctime').textContent=' · '+mskLabel(ds);
      gibsLayer=L.tileLayer(GIBS_BASE+GIBS_PRODUCT+'/default/'+ds+'/GoogleMapsCompatible_Level9/9/{y}/{x}.jpg',{
        minZoom:3,maxZoom:10,minNativeZoom:9,maxNativeZoom:9,zIndex:900,opacity:0.9,
        attribution:'Спутник: <a href="https://earthdata.nasa.gov/">NASA GIBS</a>'
      }).addTo(map);
    });
  }
```

- [ ] **Step 6: Run the marker test**

Run: `& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests/test_build.py::test_nowcast_template_has_cloud_timelabel -q`
Expected: PASS.

- [ ] **Step 7: Run all build tests**

Run: `& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests/test_build.py -q`
Expected: PASS (6 tests: 5 sushchestvuyushchikh + 1 novyy).

- [ ] **Step 8: Commit**

```bash
git add nowcast_template.html tests/test_build.py
git commit -m "feat(sputnik): show cloud capture timelabel (MSK) on toggle button"
```

---

### Task 2: Pereborka `nowcast.html` i polnyy progon

**Files:**
- Modify: `F:\Meteo\nowcast.html` (peresoedinit billerom)

**Interfaces:**
- Consumes: `nowcast_template.html` (posle Task 1).
- Produces: obnovlennyy `nowcast.html` s metkoy; potverzhdenie regressii `radar.html`.

- [ ] **Step 1: Rebuild both pages**

Run: `& "F:\Meteo\.venv\Scripts\python.exe" tools/build_radar.py`
Expected: `[ok] F:\Meteo\radar.html written (...)`, `[ok] F:\Meteo\nowcast.html written (...)`.

- [ ] **Step 2: Verify radar.html byte-identical**

Run: `git -C F:\Meteo diff --stat radar.html`
Expected: (no output) — bez izmeneniy.

- [ ] **Step 3: Verify nowcast.html contains the timelabel markers**

Run (PowerShell):
```powershell
$s=[System.IO.File]::ReadAllText('F:\Meteo\nowcast.html'); foreach($m in @('id="ctime"','mskLabel','MSK · den (Terra)')){ Write-Output ("{0}: {1}" -f $m, ([regex]::Matches($s,[regex]::Escape($m))).Count) }
```
Expected: kazhdyy marker >= 1.

- [ ] **Step 4: Run full test suite**

Run: `& "F:\Meteo\.venv\Scripts\python.exe" -m pytest tests/ -m "not integration" -q`
Expected: PASS — 194 passed, 2 deselected.

- [ ] **Step 5: Commit**

```bash
git add nowcast.html
git commit -m "build(sputnik): rebuild nowcast.html with cloud timelabel"
```

---

## Self-Review

- Spec-coverage: knopka (#ctime) — T1 S3; CSS — T1 S4; JS podpis (mskLabel) — T1 S5; test — T1 S1; pereborka+regressiya — T2. Pokryto.
- Placeholder scan: bez TBD/TODO; polnyy kod v kazhdom шаге.
- Type consistency: `mskLabel(d)` — `d='YYYY-MM-DD'`, `p[2]`=den, `p[1]`=mesyac → format `DD.MM MSK · den (Terra)`. `#ctime` tekst ustanavlivaetsya cherez `textContent`. Soglasovano mezhdu T1 shagami.
- Primechanie: `#ctime` v testakh proveryaetsya po markeru `id="ctime"`, `mskLabel`, `MSK · den (Terra)` — vse budet prisutstvovat posle T1.
