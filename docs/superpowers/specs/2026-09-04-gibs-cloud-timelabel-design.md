# Metka vremeni snimka oblachnosti (GIBS) — Design

## Opisanie

Na knopke-tumblere «Oblachnost» (#ctoggle) pokazyvat metku vremeni snimka oblachnosti po moskovskomu vremeni (MSK, UTC+3). Polzovatel: «ukazyvaj na karte oblachnosti ot kakogo vremeni snimok po moskovskomu vremeni».

Resheniya (ustanovleny s polzovatelem):
- Metka na **knopke `#ctoggle`** (malenkiy tekst sprava ot nazvaniya).
- Format: **data po MSK + pometka o dnevnom snimke Terra** (~13:30 MSK). Bez vydumannogo tochnogo vremeni — GIBS daet snimok po date, ne po vremeni.

## Kontekst (sushchestvuyushchee)

V `nowcast_template.html` uzhe yest:
- Knopka: `<button id="ctoggle" title="..."><span class="ltdot"></span>Oblachnost</button>`.
- `pickGIBSDate(cb)` vozvrashchaet `ds` — datu snimka v UTC (`YYYY-MM-DD`), podbiraya posledniy dostupnyy den.
- `showCloudLayer()` → `pickGIBSDate(function(ds){...})` sozdayet `L.tileLayer` GIBS.

Prichina: snimok MODIS Terra dnevnoi (~10:30 UTC / ~13:30 MSK v tot zhe den'), poetomu data po MSK sovpadayet s UTC-datoy iz URL.

## Arhitektura / komponenty

### 1. HTML — knopka s podpisью
`nowcast_template.html`, stroka knopki `#ctoggle`:
```html
<button id="ctoggle" title="Sputnikovaya oblachnost NASA GIBS (dnevnoi snimok MODIS Terra, ~13:30 MSK)"><span class="ltdot"></span>Oblachnost<span id="ctime"></span></button>
```
- `#ctime` — malenkiy tekst (podpis), zapolnyaetsya JS.

### 2. CSS — stili podpisi
Posle `#ctoggle.on .ltdot{...}`:
```css
#ctoggle #ctime{font-size:10px;opacity:.85;font-weight:400;white-space:nowrap}
```

### 3. JS — zapolnenie podpisi v MSK
V `showCloudLayer()`, vnutri `pickGIBSDate(function(ds){ ... });`, do sozdaniya sloya dobavit:

```js
  function mskLabel(ds){
    // ds='YYYY-MM-DD' (UTC, dnevnoi snimok Terra => tot zhe den' v MSK)
    var p=ds.split('-'); // [YYYY,MM,DD]
    return p[2]+'.'+p[1]+' MSK · den (Terra)';
  }
  var elCtime=document.getElementById('ctime');
```
i ustanovit podpis:
```js
  elCtime.textContent=' · '+mskLabel(ds);
```

Prilozhenie (zdes) — polnyy modificirovannyy fragment `showCloudLayer()` (snachala podpis, potom sloy):
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
        attribution:'Sputnik: <a href="https://earthdata.nasa.gov/">NASA GIBS</a>'
      }).addTo(map);
    });
  }
```

Primechaniya:
- Podpis ustanavlivaetsya odin raz pri pervom pokaze sloya (gibsLayer sozdactsya odnazhdy). Pri vyklyuchenii/vklyuchenii sloya podpis sohranyaetsya — korrektno.
- Esli `pickGIBSDate` ne naidet srok (set', okno snimka), fallback na segodnyashnyuyu dato — metka oboznachit segodnyashniy den'. Eto dopustimo (dnevnoi snimok Terra za segodnya obyvno dostupen posle ~13:30 MSK).

### 4. Test (marker)
`tests/test_build.py` — dobavit:
```python
def test_nowcast_template_has_cloud_timelabel():
    with open(NOWCAST_TEMPLATE, encoding="utf-8") as f:
        s = f.read()
    assert 'id="ctime"' in s
    assert "mskLabel" in s
    assert "MSK · den (Terra)" in s
```

## Failly
- Modify: `F:\Meteo\nowcast_template.html` (knopka ~54, CSS posle stroki `#ctoggle.on .ltdot`, JS `showCloudLayer` ~100).
- Modify: `F:\Meteo\tests\test_build.py` (novyy marker-test).
- Rebuild: `F:\Meteo\nowcast.html` (billerom `tools/build_radar.py`).
- Bez izmeneniy: `tools/nowcast.py`, `radar.html`, `radar_template.html`, deploy.yml.

## Testirovanie
- Marker-test `test_nowcast_template_has_cloud_timelabel` — PASS.
- Polnyy progon: `python -m pytest tests/ -m "not integration" -q` → 194 passed (193 + 1 novyy).
- Regressiya: `radar.html` byte-identical.
- Zhivaya proverka: v razvernutoy `nowcast.html` knopka «Oblachnost» pokazyvaet podpis tipa « · 04.09 MSK · den (Terra)».

## Gorizont / ne podlezhit izmeneniyu
- Istochnik (NASA GIBS), logika vybora daty — ne menyaem.
- Ne vyvodim tochnoye vremya (net v GIBS URL) — tolko data po MSK + pometka o dnevnom snimke Terra.
