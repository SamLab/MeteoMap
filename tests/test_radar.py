import os

import meteo

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _payload():
    hourly = {
        "a": {"time": ["h0"], "data": {"temperature_2m": [1.0]}},
    }
    consensus = meteo.assemble_consensus(
        hourly, ["temperature_2m"],
        {"temperature_2m": {"a": 1.0}}, min_sources=1
    )
    daily = {}
    verification = {"7d": {}, "30d": {}}
    return meteo.build_payload(
        ["a"], {"a": "Model A"}, hourly, daily, consensus,
        verification, "2026-08-03T12:00:00+03:00", meteo.LOCATIONS[0],
    )


def test_index_has_radar_tab_and_iframe():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    html = meteo.render(tpl, _payload())
    assert 'data-tab="radar"' in html
    assert 'id="radar-frame"' in html
    assert "updateRadarFrame()" in html


def test_index_autorefreshes_every_5_minutes():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "async function loadCity(slug,silent)" in tpl
    assert "if(!silent)alert('Не удалось загрузить данные города: '+e.message)" in tpl
    assert "setInterval(()=>loadCity(D.location.slug,true),5*60*1000)" in tpl
    html = meteo.render(tpl, _payload())
    assert "setInterval(()=>loadCity(D.location.slug,true),5*60*1000)" in html


def test_hours_title_uses_remaining_today_window():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "const start=curIdx;" in tpl
    assert "const hs=Math.min(curIdx+1,D.time.length-1);" in tpl
    assert "isToday=j=>D.time[j]&&D.time[j].slice(0,10)===today&&j>=hs" in tpl
    assert "const th=document.getElementById('hourstitle')" in tpl
    assert "th.textContent='Далее '+parts.join(', ')" in tpl


def test_compare_rows_highlight_day_max_min():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "tr.mxrow td{border-top:2px dashed #d32f2f;border-bottom:2px dashed #d32f2f}" in tpl
    assert "tr.mnrow td{border-top:2px dashed #1976d2;border-bottom:2px dashed #1976d2}" in tpl
    assert "tr.dayrow td{padding:6px 8px;background:var(--line);color:var(--muted);font-weight:600;border:none;text-align:left}" in tpl
    assert "const dayMx={},dayMn={};" in tpl
    assert "const day=t.slice(0,10);" in tpl
    assert "if(!(day in dayMx)||mx>dayMx[day][1])dayMx[day]=[i,mx];" in tpl
    assert "if(!(day in dayMn)||mn<dayMn[day][1])dayMn[day]=[i,mn];" in tpl
    assert "'<tr class=\"dayrow\"><td colspan=\"'+(3+codes.length)+'\">'" in tpl
    assert "prevDay=day" in tpl
    assert "let drow='';" in tpl
    assert "if(day!==prevDay){" in tpl
    assert "&&(prevDay=day," not in tpl
    assert "const inMx=dayMx[day]&&dayMx[day][0]===i;" in tpl
    assert "const inMn=dayMn[day]&&dayMn[day][0]===i;" in tpl
    assert "mxrow':''}${inMn?' mnrow':''}" in tpl


def test_compare_tab_named_chasy():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert '<button data-tab="compare">Часы</button>' in tpl
    assert "<h2>Часы</h2>" in tpl


def test_update_radar_frame_uses_location_coords():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    html = meteo.render(tpl, _payload())
    assert "D.location.lat" in html
    assert "D.location.lon" in html
    assert "radar.html?lat=" in html


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
    assert "rainradar.ru/tiles?z={z}&x={x}&y={y}" in radar
    assert "tms:true" in radar
    assert "basemaps.cartocdn.com" not in radar
    assert "tile.openstreetmap.org" not in radar
    assert "#map{position:absolute;inset:0;background:#acacac}" in radar
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


def test_radar_frame_is_lazy_loaded_on_tab_activation():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "f.dataset.radarSrc=url" in tpl
    assert "tab.classList.contains('active')" in tpl
    assert "b.dataset.tab==='radar'" in tpl
    assert "f.dataset.radarSrc!==f.dataset.loadedSrc" in tpl


def test_radar_legend_matches_original():
    with open(os.path.join(HERE, "radar_template.html"), encoding="utf-8") as f:
        tpl = f.read()
    for label in ("Облачность", "Осадки", "Гроза", "Град"):
        assert label in tpl
    assert "слабо" not in tpl
    assert "сильно" not in tpl
    assert "8889bd" in tpl and "b80db2" in tpl


def test_radar_has_lightning_layer():
    with open(os.path.join(HERE, "radar_template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "images.lightningmaps.org" in tpl
    assert "blitzortung" in tpl
    assert "lightning-0" in tpl and "lightning-1" in tpl
    assert "createPane('lightning-0')" in tpl
    assert "type=" in tpl
    assert "tileSize:1024" in tpl and "zoomOffset:-2" in tpl
    assert 'id="ltoggle"' in tpl
    assert "brightness(1.1)" in tpl and "brightness(1.3)" in tpl
    assert "hue-rotate(155deg)" in tpl and "hue-rotate(160deg)" in tpl


def test_weather_now_parameter_table_with_sun_and_rain():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert '<table class="wnowtbl">' in tpl
    assert "lab:'Температура'" in tpl
    assert "lab:'Осадки'" in tpl
    assert "lab:'Ветер'" in tpl
    assert "lab:'Солнце'" in tpl
    assert "lab:'Влажность'" not in tpl
    assert "lab:'Давление'" not in tpl
    assert tpl.index("lab:'Температура'") < tpl.index("lab:'Осадки'") < tpl.index("lab:'Ветер'") < tpl.index("lab:'Солнце'")
    assert "['CAPE'," not in tpl
    assert "['Восход / закат'," not in tpl
    assert "'↑ '" in tpl and "'↓ '" in tpl
    assert "rngUp(iMx['wind_speed_10m'],'wind_speed_10m')" in tpl
    assert "rngUp(iMx['wind_speed_10m'],'wind_speed_10m','м/с')" not in tpl
    assert "'↑ '+fmt(w.precipitation[pMx])+' в '" in tpl
    assert "'↑ '+fmt(w.precipitation[pMx])+' мм в '" not in tpl
    assert "D.time[i].slice(11,13)+'ч'" in tpl
    assert "D.time[iMx['temperature_2m']].slice(11,13)+'ч'" in tpl
    assert "D.time[pMx].slice(11,13)+'ч'" in tpl
    assert "const aptMean=apn?temp(apt/apn):'';" in tpl
    assert "aptMean?' ('+aptMean+')':''" in tpl


def test_accuracy_tables_sorted_by_mean_mae():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "mrows.sort((a,b)=>(meanOf(ver[a],vnames)??1e9)-(meanOf(ver[b],vnames)??1e9))" in tpl


def test_hour_ribbon_rain_bar():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert ".hour{flex:none;width:64px;text-align:center;font-size:12px;padding:4px 2px;border-right:1px solid var(--line);position:relative;overflow:hidden}" in tpl
    assert ".hour .hprc{position:absolute;left:0;right:0;bottom:0;background:linear-gradient(#4fc3f7,#0288d1);opacity:.75;pointer-events:none}" in tpl
    assert ".hour .ht,.hour .he,.hour .htemp,.hour .hwnd,.hour .hpp{position:relative}" in tpl
    assert "class=\"hprc\"" in tpl
    assert "Math.min(100,Math.round(pr/5*100))" in tpl


def test_radar_has_rainradar_base_above_precipitation():
    with open(os.path.join(HERE, "radar_template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "#map{position:absolute;inset:0;background:#acacac}" in tpl
    assert "rainradar.ru/tiles?z={z}&x={x}&y={y}" in tpl
    assert "tms:true" in tpl
    assert "zIndex:998" in tpl
    assert "basemaps.cartocdn.com" not in tpl
    assert "tile.openstreetmap.org" not in tpl


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


def test_radar_has_labels_layer():
    with open(os.path.join(HERE, "radar_template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "LabelsLayer" in tpl
    assert "map.createPane('labels')" in tpl
    assert "rainradar.ru/labels?z=" in tpl
    assert ".leaflet-labels-pane{z-index:900}" in tpl
    assert ".label.l0>span" in tpl and ".label.l3>span" in tpl
    assert "text-shadow:-1px 0 1px" in tpl
    assert "pointer-events:none" in tpl
    assert "updateWhenZooming:false" in tpl
    assert "minZoom:5" in tpl
    assert "tile.style.width='256px'" in tpl
    assert "tile.style.height='256px'" in tpl
    with open(os.path.join(HERE, "radar.html"), encoding="utf-8") as f:
        radar = f.read()
    assert "LabelsLayer" in radar
    assert "rainradar.ru/labels?z=" in radar
    assert ".leaflet-labels-pane{z-index:900}" in radar
    assert ".label.l3>span" in radar
    assert "tile.style.width='256px'" in radar
    assert "tile.style.height='256px'" in radar


def test_radar_labels_have_city_dots_like_rainradar():
    with open(os.path.join(HERE, "radar_template.html"), encoding="utf-8") as f:
        tpl = f.read()
    # точка = ::before у .label: круг с чёрной обводкой, заливка #eee
    assert ".label::before{content:\" \";" in tpl
    assert "border:1px solid #000" in tpl
    assert "border-radius:50%" in tpl
    assert "background-color:#eee" in tpl
    assert "width:6px;height:6px" in tpl
    # размеры точек по классам: l0=6px, l1/l2=4px, l3/l4=2px
    assert ".label.l1::before,.label.l2::before{left:-2px;bottom:-2px;width:4px;height:4px}" in tpl
    assert ".label.l3::before,.label.l4::before{left:-1px;bottom:-1px;width:2px;height:2px}" in tpl
    # span absolute: текст сдвинут вправо-вверх от точки (как на rainradar)
    assert "position:absolute;left:-9px;bottom:5px" in tpl
    assert ".label.l3 span,.label.l4 span{left:-7px}" in tpl
    assert ".label.l4>span{font-size:10px}" in tpl
    with open(os.path.join(HERE, "radar.html"), encoding="utf-8") as f:
        radar = f.read()
    assert ".label::before{content:\" \";" in radar
    assert "background-color:#eee" in radar
    assert "width:6px;height:6px" in radar
    assert "position:absolute;left:-9px;bottom:5px" in radar
    assert ".label.l4>span{font-size:10px}" in radar
