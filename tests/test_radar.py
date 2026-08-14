import os
import re

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
    assert "URLSearchParams(location.search).get('city')" in tpl
    assert "loadCity(_uc); else renderAll();" in tpl


def test_hours_title_uses_remaining_today_window():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "const start=curIdx;" in tpl
    assert "const hs=Math.min(curIdx+1,D.time.length-1);" in tpl
    assert "isToday=j=>D.time[j]&&D.time[j].slice(0,10)===today&&j>=hs" in tpl
    assert "const th=document.getElementById('hourstitle')" in tpl
    assert "th.textContent=(rainHour>=0?'':'Остаток дня ')+parts.join(', ')" in tpl


def test_compare_rows_highlight_day_max_min():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "tr.mxrow td{border-top:2px dashed #d32f2f;border-bottom:2px dashed #d32f2f}" in tpl
    assert "tr.mnrow td{border-top:2px dashed #1976d2;border-bottom:2px dashed #1976d2}" in tpl
    assert "tr.dayrow td{padding:6px 8px;background:var(--line);color:var(--muted);font-weight:600;border:none;text-align:left}" in tpl
    assert "const dayMx={},dayMn={};" in tpl
    assert "const day=t.slice(0,10);" in tpl
    assert "if(!(day in dayMx)||w>dayMx[day][1])dayMx[day]=[i,w];" in tpl
    assert "if(!(day in dayMn)||w<dayMn[day][1])dayMn[day]=[i,w];" in tpl
    assert "Math.max(...nums),mn=Math.min(...nums)" not in tpl
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


def test_warnings_title_lists_nearest_confirmed():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "Предупреждения (ближайшее/подтвержденное)" in tpl
    assert '<h3 class="tstab">Предупреждения</h3>' not in tpl


def test_hourstitle_rain_interval():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "const rainType=wcode(w.weather_code?.[jPeak])[0]||'Дождь';" in tpl
    assert "rainType+' с '+D.time[rainHour].slice(11,16)+' до '+D.time[jLast].slice(11,16)" in tpl
    assert "· по '+(mCnt===1?'1 модели':mCnt+' моделям')" in tpl
    assert "на '+fmtP(sumPr)+'мм с '+num(maxPp)+'%" in tpl
    assert "rainHour>=0?'Далее '" not in tpl


def test_help_text_up_to_date():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "Предупреждения</b> — дождь, гроза, порывы ветра (≥ 15 м/с)" in tpl
    assert "Ближайшее — по одной модели, подтверждённое — по двум и более" in tpl
    assert "час минимума/максимума дня по консенсусу" in tpl
    assert "Типы погоды" in tpl
    assert "51–57 — морось" in tpl
    assert "дождь 61→63→65" in tpl
    assert "Google AI (WeatherNext) — Google DeepMind" in tpl
    assert "ECMWF IFS и ECMWF AIFS" in tpl
    assert "KMA GDPS — Южная Корея" in tpl
    assert "1/MAE за 7 дней" in tpl
    assert "голосование моделей по коду" in tpl
    assert "дождь, гроза, град" not in tpl
    assert "<b>Сегодня</b> — ближайшие 48 часов по часам." not in tpl


def test_d10_wind_like_hourly():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "const ws=D.daily.wind_speed_10m_max?.[di];" in tpl
    assert "const wd=D.daily.wind_direction_10m_dominant?.[di];" in tpl
    assert "'<div class=\"d10wind\">'" in tpl
    assert tpl.rfind("d10cond") < tpl.rfind("d10wind") < tpl.rfind("d10day")
    assert ".d10wind{font-size:10.5px" in tpl


def test_cmp_table_shows_all_available_hours():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "const rows=D.time.map((t,i)=>" in tpl
    assert "endI" not in tpl


def test_cmp_row_highlight_uses_consensus_not_model_extreme():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "const w=D.weighted[cmpVar]?.[i];" in tpl
    assert "w>dayMx[day][1]" in tpl
    assert "w<dayMn[day][1]" in tpl
    assert "Math.max(...nums),mn=Math.min(...nums)" not in tpl


def test_warnings_confirmed_requires_two_models():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "sourceCountAt(i,list)>=2" in tpl
    assert "sourceCountAt(i,list)>0)return i;" in tpl


def test_warnings_gust_column_instead_of_hail():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "const GUST_MIN=15;" in tpl
    assert "wind_gusts_10m?.[i]" in tpl
    assert "findGust(1)" in tpl and "findGust(2)" in tpl
    assert "g.lst.join(' и ')" in tpl
    assert "lst.push(names[c])" in tpl
    assert "col('🧊',H)" not in tpl


def test_precip_shows_hundredths_for_small_values():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "const fmtP=v=>" in tpl
    assert "Math.round(v*100)/100" in tpl
    assert "fmtP(pr)+'мм'" in tpl
    assert "fmtP(x.pr))+'мм / '" in tpl
    assert "fmtP(prSum)+' мм'" in tpl


def test_hourly_rain_fill_less_bright():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    m = re.search(r"\.hour \.hprc\{[^}]+\}", tpl)
    assert m and "opacity:.45" in m.group(0)
    assert ".hprc{position:absolute;left:0;right:0;bottom:0;background:linear-gradient(#b3e5fc,#4fc3f7);" in tpl


def test_wcode_rain_icons_have_no_sun():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "🌦️" not in tpl
    assert "61:['Небольшой дождь','🌧️']" in tpl
    assert "80:['Небольшой ливень','🌧️']" in tpl
    assert "51:['Небольшая морось','🌧️']" in tpl


def test_radar_play_runs_single_loop_to_current_hour():
    with open(os.path.join(HERE, "radar_template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "showFrame(idx+1<frames.length?idx+1:0)" not in tpl
    assert "if(idx>=frames.length-1)showFrame(0);" in tpl
    assert "else{playing=false;elPlay.textContent='▶';elPlay.classList.remove('playing');clearInterval(timer);timer=null;}" in tpl


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
    assert "lab:'Точка росы'" in tpl
    assert "lab:'Осадки'" in tpl
    assert "lab:'Влажность'" in tpl
    assert "lab:'CAPE'" in tpl
    assert "lab:'Ветер'" in tpl
    assert "lab:'Облачность'" in tpl
    assert "lab:'Давление'" in tpl
    assert "lab:'Видимость'" in tpl
    assert "lab:'Солнце'" in tpl
    assert "lab:'Восход / закат'" not in tpl
    assert tpl.index("lab:'Температура'") < tpl.index("lab:'Осадки'") < tpl.index("lab:'Облачность'") < tpl.index("lab:'Ветер'") < tpl.index("lab:'Солнце'") < tpl.index("lab:'Видимость'") < tpl.index("lab:'Точка росы'") < tpl.index("lab:'Давление'") < tpl.index("lab:'Влажность'") < tpl.index("lab:'CAPE'")
    assert "const meanDay=f=>" in tpl
    assert "['temperature_2m','wind_speed_10m','dew_point_2m','relative_humidity_2m','pressure_msl','cloud_cover','visibility','cape']" in tpl
    assert "@media (max-width:700px){.wnowtbl td.wcol3,.wnowtbl td.wcol5,.wnowtbl td.wcol6,.wnowtbl td.wcol7,.wnowtbl td.wcol8,.wnowtbl td.wcol9{display:none}}" in tpl
    assert "cells.map((c,i)=>'<td class=\"wcol'+i+'\">'" in tpl
    assert "['CAPE'," not in tpl
    assert "['Восход / закат'," not in tpl
    assert "'↑ '" in tpl and "'↓ '" in tpl
    assert "rngUp(iMx['wind_speed_10m'],'wind_speed_10m')" in tpl
    assert "rngUp(iMx['wind_speed_10m'],'wind_speed_10m','м/с')" not in tpl
    assert "' в '+D.time[i].slice(11,16)" in tpl
    assert "D.time[i].slice(11,13)+'ч'" not in tpl
    assert "D.time[iMx['temperature_2m']].slice(11,16)" in tpl
    assert "'с '+D.time[pFirst].slice(11,16)" in tpl
    assert "'до '+D.time[pLast].slice(11,16)" in tpl
    assert "if(!rainCodes.includes(w.weather_code?.[j]))continue;" in tpl
    assert "'↑ '+fmt(w.precipitation[pMx])+' в '" not in tpl
    assert "const aptMean=apn?temp(apt/apn):'';" in tpl
    assert "aptMean?' ('+aptMean+')':''" in tpl


def test_hours_title_has_rain_only():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "parts.push('без дождя')" in tpl
    assert "const rainType=wcode(w.weather_code?.[jPeak])[0]||'Дождь';" in tpl
    assert "rainType+' с '+D.time[rainHour].slice(11,16)+' до '+D.time[jLast].slice(11,16)" in tpl
    assert "'Остаток дня '" in tpl
    assert "tiMax" not in tpl
    assert "tiMin" not in tpl


def test_accuracy_tables_sorted_by_mean_mae():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "mrows.sort((a,b)=>(meanOf(ver[a],vnames)??1e9)-(meanOf(ver[b],vnames)??1e9))" in tpl


def test_hour_ribbon_rain_bar():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert ".hour{flex:none;width:64px;text-align:center;font-size:12px;padding:4px 2px;border-right:1px solid var(--line);position:relative;overflow:hidden}" in tpl
    assert ".hour .hprc{position:absolute;left:0;right:0;bottom:0;background:linear-gradient(#b3e5fc,#4fc3f7);opacity:.45;pointer-events:none}" in tpl
    assert ".hour .ht,.hour .he,.hour .htemp,.hour .hwnd,.hour .hpp{position:relative}" in tpl
    assert "class=\"hprc\"" in tpl
    assert "class=\"hcl\"" not in tpl
    assert "Math.min(100,Math.round(pr/5*100))" in tpl


def test_d10_cloud_fill_top_to_bottom():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert ".d10cloud{position:absolute;left:0;right:0;top:0;background:linear-gradient(#eceff1,#b0bec5);opacity:.75}" in tpl
    assert ".d10prec{position:absolute;left:0;right:0;bottom:0;background:linear-gradient(#4fc3f7,#0288d1);opacity:.75}" in tpl
    assert "class=\"d10cloud\"" in tpl
    assert "class=\"d10prec\"" in tpl
    assert tpl.index('<div class="d10cloud"') < tpl.index('<div class="d10prec"')
    assert "Math.max(0,Math.min(100,Math.round(x.cl||0)))" in tpl
    assert "Math.max(0,Math.round(x.pr/50*100))" in tpl


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
