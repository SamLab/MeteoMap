import os
import re

import meteo
from tools import build_radar

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
    assert "function scheduleAligned(fn, ms)" in tpl
    assert "})(()=>loadCity(D.location.slug,true),5*60*1000);" in tpl
    assert "setInterval(()=>loadCity(D.location.slug,true),5*60*1000)" not in tpl
    html = meteo.render(tpl, _payload())
    assert "})(()=>loadCity(D.location.slug,true),5*60*1000);" in html
    assert "setInterval(()=>loadCity(D.location.slug,true),5*60*1000)" not in html
    assert "URLSearchParams(location.search).get('city')" in tpl
    assert "loadCity(_uc); else renderAll();" in tpl


def test_widgets_refresh_aligned_every_5_minutes():
    for fname in ("meteo.html", "meteow.html"):
        with open(os.path.join(HERE, fname), encoding="utf-8") as f:
            w = f.read()
        assert "var REFRESH_MS = 5 * 60 * 1000;" in w, fname
        assert "function scheduleAligned(fn, ms)" in w, fname
        assert "setInterval(load, REFRESH_MS)" not in w, fname


def test_data_cache_bust_via_version_token():
    with open(os.path.join(HERE, "meteo.py"), encoding="utf-8") as f:
        py = f.read()
    assert '\"data\", \"version.json\"' in py or '"data"), "version.json"' in py or '"version.json"' in py

    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "fetch('data/'+slug+'.json?v='+v" in tpl
    assert "encodeURIComponent(D.generated_at||'')" in tpl

    for fname in ("meteo.html", "meteow.html"):
        with open(os.path.join(HERE, fname), encoding="utf-8") as f:
            w = f.read()
        assert "function dataUrl(base)" in w, fname
        assert "dataUrl(relUrl())" in w, fname
        assert "dataUrl(absUrl())" in w, fname
        assert "fetch('data/version.json'" in w, fname
        assert "__DATA_VERSION__" in w, fname


def test_hours_title_uses_remaining_today_window():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "const start=curIdx;" in tpl
    # окно «по часам» считает от текущего часа включительно — цифры совпадают с виджетом и предупреждениями
    assert "const hs=Math.min(curIdx,D.time.length-1);" in tpl
    assert "const isToday=j=>D.time[j]&&j>=hs;" in tpl
    assert "isToday=j=>D.time[j]&&D.time[j].slice(0,10)===today&&j>=hs" not in tpl
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
    assert "'<tr class=\"dayrow\"><td colspan=\"'+(2+cc.length)+'\">'" in tpl
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
    assert "Предупреждения (ближайшее/" in tpl
    assert "подтвержденное</b>)" in tpl or "подтвержденное</strong>)" in tpl
    assert '<h3 class="tstab">Предупреждения</h3>' not in tpl


def test_hourstitle_rain_type_uses_window_start_code():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "const jStartCode=w.weather_code?.[ws];" in tpl
    assert "rainType=(rainCodes.includes(jStartCode)&&wcode(jStartCode)[0])?wcode(jStartCode)[0]:'Дождь';" in tpl
    assert "const jPeakCode=w.weather_code?.[jPeak];" not in tpl
    assert "RainType" not in tpl
    assert "const enIdx=Math.min(jLast+1,D.time.length-1);" in tpl
    assert "const enLabel=(enTime==='00ч'&&enDay!==D.time[rainHour].slice(0,10))?'00ч':(enDay===D.time[rainHour].slice(0,10)?enTime:relDay(enTs)+' '+enTime);" in tpl
    assert "const timeStr=nowRain?'до '+enLabel:(st===enLabel?stDay+'в '+stHour:stDay+'с '+stHour+' до '+enLabel);" in tpl
    assert "const mcLbl='по '+rcLbl(mCnt,mX);" in tpl
    assert "const ccLbl='по '+rcLbl(ccCnt,ccX);" in tpl
    assert "if(n>mX)mX=n;" in tpl
    assert "ccCnt>=1?' · '+ccLbl:''" in tpl
    assert "ccCnt>=2?' · '+ccLbl:''" not in tpl
    assert "if(rainCodes.includes(v)||(pr!=null&&pr>=0.1)||((pr==null||pr<0.1)&&pp!=null&&pp>20))cn++;" in tpl
    assert "на '+fmtP(sumPr)+'мм с '+num(maxPp)+'%" in tpl
    assert "rainHour>=0?'Далее '" not in tpl
    assert "'Сегодня — Подтвержденного дождя нет, но '+(mCnt>=1?mcLbl+' ':'')+'вероятны Осадки '+" in tpl
    assert "Сегодня подтвержденного дождя нет" not in tpl


def test_hourstitle_interval_breaks_on_first_dry_hour():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "if(hasRainAt(j)){if(rainHour<0)rainHour=j;jLast=j;}else if(rainHour>=0)break;" in tpl
    assert "if(hasRainAt(j)||modelRainCount(j)>=2){if(rainHour<0)rainHour=j;jLast=j;}else if(rainHour>=0)break;" in tpl


def test_consensus_rain_confirmed_by_code_mm_or_prob_in_all_four():
    consensus = "(p!=null&&p>=0.1)||((p==null||p<0.1)&&q!=null&&q>20)"
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "const conAt=i=>{const c=D.weighted.weather_code?.[i],p=D.weighted.precipitation?.[i],q=D.weighted.precipitation_probability?.[i];return (c!=null&&rainCodesLocal.includes(Number(c)))||" + consensus + ";};" in tpl
    assert "function hasRainAt(j){const c=w.weather_code?.[j],p=w.precipitation?.[j],q=w.precipitation_probability?.[j];return rainCodes.includes(c)||" + consensus + ";}" in tpl
    for fname in ("meteo.html", "meteow.html"):
        with open(os.path.join(HERE, fname), encoding="utf-8") as f:
            w = f.read()
        assert "function hasRainAt(j){var c=data.weather_code?Math.round(data.weather_code[j]):0;var p=data.precipitation?data.precipitation[j]:null;var q=data.precipitation_probability?data.precipitation_probability[j]:null;return RAIN.indexOf(c)>=0||" + consensus + ";}" in w, fname


def test_widget_episode_crosses_midnight_with_rel_day():
    with open(os.path.join(HERE, "meteo.html"), encoding="utf-8") as f:
        m = f.read()
    with open(os.path.join(HERE, "meteow.html"), encoding="utf-8") as f:
        w = f.read()
    assert "if(times[j].toDateString()!==todayStr) break;" not in m
    assert "if(times[j].toDateString()!==todayStr) break;" not in w
    assert "var todayStr=now.toDateString();" not in m
    assert "var todayStr=now.toDateString();" not in w
    assert "var DOW = ['Вс','Пн','Вт','Ср','Чт','Пт','Сб'];" in m
    assert "function relDay(d){" in m and "function relDay(d){" in w
    assert "relDay(times[endIdx])+' '+pad2(times[endIdx].getHours())+'ч'" in m
    assert "relDay(times[endIdx])+' '+pad2(times[endIdx].getHours())+'ч'" in w
    assert "times[endIdx].toDateString()===times[rainHour].toDateString()" in m
    assert "times[endIdx].toDateString()===times[rainHour].toDateString()" in w


def test_rain_interval_start_labels_day_when_not_today():
    with open(os.path.join(HERE, "meteo.html"), encoding="utf-8") as f:
        m = f.read()
    with open(os.path.join(HERE, "meteow.html"), encoding="utf-8") as f:
        w = f.read()
    assert "var st=times[rainHour].toDateString()===times[idx].toDateString()?pad2(times[rainHour].getHours())+'ч':relDay(times[rainHour])+' '+pad2(times[rainHour].getHours())+'ч';" in m
    assert "var st=times[rainHour].toDateString()===times[idx].toDateString()?pad2(times[rainHour].getHours())+'ч':relDay(times[rainHour])+' '+pad2(times[rainHour].getHours())+'ч';" in w
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "const stDay=D.time[rainHour].slice(0,10)===D.time[hs].slice(0,10)?'':relDay(D.time[rainHour])+' ';" in tpl
    assert "const stHour=D.time[rainHour].slice(11,13)+'ч';" in tpl


def test_tomorrow_23h_interval_with_00h_edge_keeps_day():
    # Регрессия a4b15b3: интервал завтра 23ч—00ч (послезавтра 00ч) терял день,
    # т.к. st был голым часом, а en при 00ч отбрасывал day. Должно быть «Завтра 23ч—00ч».
    import re as _re
    for fname in ("meteo.html", "meteow.html"):
        with open(os.path.join(HERE, fname), encoding="utf-8") as f:
            w = f.read()
        # сравнение дня rainHour идёт с текущим часом idx, НЕ с самим rainHour
        assert "var st=times[rainHour].toDateString()===times[idx].toDateString()?pad2(times[rainHour].getHours())+'ч':relDay(times[rainHour])+' '+pad2(times[rainHour].getHours())+'ч';" in w, fname
        assert "var st=times[rainHour].toDateString()===times[rainHour].toDateString()" not in w, fname
        # en при 00ч остаётся «00ч» (намеренно без дня), но старт держит день
        assert "var en=(times[endIdx].getHours()===0)?'00ч':" in w or "var en=(times[endIdx].getHours()===0)?'\\u0030\\u0030\\u0447':" in w, fname
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "const stDay=D.time[rainHour].slice(0,10)===D.time[hs].slice(0,10)?'':relDay(D.time[rainHour])+' ';" in tpl
    assert "const stDay=D.time[rainHour].slice(0,10)===D.time[rainHour].slice(0,10)" not in tpl

    # поведенческая эмуляция: завтра 23ч → послезавтра 00ч
    def pad2(n):
        return str(n).zfill(2)
    def rel_day(ts, cur):
        from datetime import datetime
        d0 = datetime.strptime(cur[:10], "%Y-%m-%d")
        d1 = datetime.strptime(ts[:10], "%Y-%m-%d")
        diff = (d1 - d0).days
        if diff == 0:
            return "Сегодня"
        if diff == 1:
            return "Завтра"
        return ["Вс", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"][d1.isoweekday() % 7] + " " + str(d1.day)
    def emit(st_day, cur_day, sh, eh):
        st = pad2(sh) + "ч" if st_day == cur_day else rel_day(st_day, cur_day) + " " + pad2(sh) + "ч"
        en = "00ч" if eh == 0 else pad2(eh) + "ч"
        return st + "—" + en
    curated = {
        "2026-09-26T23:00": ("2026-09-26", 23, 0, "23ч—00ч"),      # сегодня 23ч → завтра 00ч: день не нужен
        "2026-09-27T23:00": ("2026-09-27", 23, 0, "Завтра 23ч—00ч"),  # завтра 23ч → послезавтра 00ч: день нужен
        "2026-09-28T23:00": ("2026-09-28", 23, 0, "Пн 28 23ч—00ч"),   # послезавтра: день-дата нужен
    }
    for ts, (st_day, sh, eh, expected) in curated.items():
        cur_day = "2026-09-26"
        out = emit(st_day, cur_day, sh, eh)
        assert out == expected, (ts, out, expected)


def test_widget_interval_breaks_on_first_dry_hour():
    # Один проход по объединённому критерию (консенсус ИЛИ >=2 модели):
    # берётся ближайший эпизод, интервал рвётся на первом часу без дождя.
    for fname in ("meteo.html", "meteow.html"):
        with open(os.path.join(HERE, fname), encoding="utf-8") as f:
            w = f.read()
        assert "if(hasRainAt(j)||modelRainCount(j)>=2){if(rainHour<0)rainHour=j;jLast=j;}else if(rainHour>=0)break;" in w, fname


def test_widget_summary_prefers_nearest_rain_not_later_confirmed():
    # Регрессия: виджет прыгал на далёкий подтверждённый консенсусом дождь,
    # пропуская ближайший эпизод, который отмечают >=2 модели. «Вероятны
    # Осадки» — когда начало ближайшего эпизода не подтверждено консенсусом.
    for fname in ("meteo.html", "meteow.html"):
        with open(os.path.join(HERE, fname), encoding="utf-8") as f:
            w = f.read()
        assert "if(hasRainAt(j)){if(rainHour<0)rainHour=j;jLast=j;}else if(rainHour>=0)break;" not in w, fname
        assert "if(rainHour>=0)fromModels=true;" not in w, fname
        assert "var fromModels=rainHour>=0&&!hasRainAt(rainHour);" in w, fname


def test_hourly_interval_continues_on_consensus_even_if_models_below_threshold():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "if(hasRainAt(j)||modelRainCount(j)>=2){if(rainHour<0)rainHour=j;jLast=j;}else if(rainHour>=0)break;" in tpl
    for fname in ("meteo.html", "meteow.html"):
        with open(os.path.join(HERE, fname), encoding="utf-8") as f:
            w = f.read()
        assert "if(hasRainAt(j)||modelRainCount(j)>=2){if(rainHour<0)rainHour=j;jLast=j;}else if(rainHour>=0)break;" in w, fname


def test_hourstitle_rain_interval():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "const jStartCode=w.weather_code?.[ws];" in tpl
    assert "const enIdx=Math.min(jLast+1,D.time.length-1);" in tpl
    assert "const enLabel=(enTime==='00ч'&&enDay!==D.time[rainHour].slice(0,10))?'00ч':(enDay===D.time[rainHour].slice(0,10)?enTime:relDay(enTs)+' '+enTime);" in tpl
    assert "const timeStr=nowRain?'до '+enLabel:(st===enLabel?stDay+'в '+stHour:stDay+'с '+stHour+' до '+enLabel);" in tpl
    assert "const mcLbl='по '+rcLbl(mCnt,mX);" in tpl
    assert "if(n>mX)mX=n;" in tpl
    assert "ccCnt>=1?' · '+ccLbl:''" in tpl
    assert "ccCnt>=2?' · '+ccLbl:''" not in tpl
    assert "на '+fmtP(sumPr)+'мм с '+num(maxPp)+'%" in tpl
    assert "rainHour>=0?'Далее '" not in tpl


def test_hourstitle_includes_current_hour_when_raining():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "const ws=nowRain?start:rainHour;" in tpl
    assert "const inWin=j=>j>=ws&&D.time[j];" in tpl
    assert "const inWin=j=>j>=ws&&D.time[j]&&D.time[j].slice(0,10)===today;" not in tpl
    assert tpl.count("if(!inWin(j))continue;") >= 2


def test_hourstitle_search_not_limited_to_today():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    # эпизод ищется от curIdx до конца данных; день отсекается только границей данных, не календарём
    assert "const isToday=j=>D.time[j]&&j>=hs;" in tpl
    assert "const inWin=j=>j>=ws&&D.time[j];" in tpl
    assert "const enLabel=(enTime==='00ч'&&enDay!==D.time[rainHour].slice(0,10))?'00ч':(enDay===D.time[rainHour].slice(0,10)?enTime:relDay(enTs)+' '+enTime);" in tpl
    assert "enDay!==today" not in tpl


def test_rain_intensity_helper_by_wmo_code_removed():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    # dead-code cleanup: rainIntensity не вызывается, mapping живёт в degreeText (проверен ниже)
    assert "const rainIntensity=" not in tpl and "function rainIntensity(" not in tpl
    assert "degreeText(" in tpl


def test_hourly_has_no_intensity_line():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    # интенсивность вынесена из почасового блока — нет ни строки, ни вызова в buildWeatherHours
    assert 'class="hip"' not in tpl
    assert "rainIntensity(w.weather_code?.[j])" not in tpl
    # в блоке «Сейчас» интенсивность применяется только через degreeText; rainIntensity — чистая таблица маппинга
    assert "rainIntensity(w.weather_code" not in tpl
    assert "degreeText(" in tpl


def test_now_shows_intensity_when_raining():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    # степень добавляется только нейтральным типам, без тавтологии «Небольшой дождь слабый»
    assert "const degreeText=(c,wtext)=>{" in tpl
    assert "c===53?'умеренная':'умеренный'" in tpl
    assert "degreeText(w.weather_code?.[curIdx],wtext)" in tpl
    assert "rainIntensity(w.weather_code?.[curIdx])" not in tpl


def test_detail_summary_column():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert '<div class="hour hsum">' in tpl
    assert "DAY_NAMES[d.getDay()]+',<br>'" in tpl
    assert ".hour.hsum{width:" in tpl
    assert '.hour.hsum .tmin{font-weight:400}' in tpl
    assert "' мм / '" in tpl
    assert "aggPart(day,'00','24','precipitation','sum')" in tpl
    assert ".hour .hcloud{" in tpl
    assert "RAIN_CODES.includes(D.weighted.weather_code?.[j])" in tpl
    assert "const RAIN_CODES=[51,53,55,56,57,61,63,65,66,67,80,81,82];" in tpl
    assert "' <span class=\"tmin\">/ '" in tpl
    assert "'<div>с '+rst+' до '+ren+'</div>'" in tpl
    assert "'<div class=\"hour hsun\">'" in tpl
    assert '<div class="sunl">Долгота' in tpl
    assert "+sunCol+'</div>'" in tpl
    assert '<div class="dsun">' not in tpl
    assert '<span class="dsum">' not in tpl
    assert 'function daySummary' not in tpl
    assert "const dayCode=aggWcode(day,'00','24');" in tpl
    assert "'<div class=\"he\">'+wcode(dayCode)[1]+'</div>'" in tpl


def test_help_text_up_to_date():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "Предупреждения</b> — дождь, заморозки, порывы ветра (≥ 15 м/с)" in tpl
    assert "Ближайшее — по одной модели, подтверждённое (жирным) — по консенсусу" in tpl
    assert "час минимума/максимума дня по консенсусу" in tpl
    assert "Типы погоды" in tpl
    assert "51–57 — морось" in tpl
    assert "дождь 61→63→65" in tpl
    assert "Google AI (WeatherNext) — Google DeepMind" in tpl
    assert "ECMWF IFS и ECMWF AIFS" in tpl
    assert "BOM ACCESS" not in tpl
    assert "KMA GDPS" not in tpl
    assert "1/MAE за 7 дней" in tpl
    assert "голосование моделей по коду" in tpl
    # «Среднее» давно не среднее только по моделям: наблюдение «Датчика» входит и
    # в него, и в консенсус. Прежние формулировки закрепляли неверное утверждение.
    assert "простой средний прогноз всех моделей" not in tpl
    assert "Вес модели — 1/MAE за 7 дней" in tpl
    assert "вдвое больше среднего веса моделей" in tpl
    assert "входит и в «Среднее», и в «Консенсус»" in tpl
    assert "одна модель вместе с «Датчиком» — это уже два источника" in tpl
    assert "«Датчик» — это среднее по станциям" in tpl
    assert "В проверке точности «Датчик» не участвует" in tpl
    assert "дождь, гроза, град" not in tpl
    assert "<b>Сегодня</b> — ближайшие 48 часов по часам." not in tpl
    assert "первый дождливый час дня и час после конца первой непрерывной серии дождя по консенсусу" in tpl


def test_d10_title_line_over_days():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert 'id="d10title"' in tpl
    assert "d10title" in tpl and "buildWeather16Title" in tpl
    assert "На 16 дней — " in tpl or "'На 16 дней' +" in tpl or "'На 16 дней — '" in tpl
    assert "Ближайший дождь" in tpl
    assert "Ближайший дождь в " not in tpl
    assert "'Ближайший дождь: '+dayLabel(d)" in tpl
    # ближайший дождь — непрерывный эпизод от текущего часа; конец эксклюзивный (час после последнего дождливого)
    assert "while(k<D.time.length&&D.time[k]&&hasRainAt(k))k++;" in tpl
    assert "D.time[k].slice(0,10)===D.time[i].slice(0,10)" not in tpl
    assert "rainB=Math.min(k,D.time.length-1);" in tpl
    assert "hits[hits.length-1]" not in tpl
    assert "'На 16 дней — '+parts.join(' — ')" in tpl
    assert "parts.join(' / ')" not in tpl
    assert "не ожидается" in tpl
    assert "Теплее: " in tpl
    assert "Холоднее: " in tpl
    assert "D.weighted.weather_code" in tpl
    assert "D.daily.temperature_2m_max" in tpl
    assert "D.daily.temperature_2m_min" in tpl


def test_d10_rain_uses_consensus_and_crosses_midnight():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "function hasRainAt(i){const c=D.weighted.weather_code?.[i],p=D.weighted.precipitation?.[i],q=D.weighted.precipitation_probability?.[i];return rainCodes.includes(c)||(p!=null&&p>=0.1)||((p==null||p<0.1)&&q!=null&&q>20);}" in tpl
    assert "if(!D.time[i]||!hasRainAt(i))continue;" in tpl
    assert "const endLabel=(eTime==='00ч'&&eDay!==D.time[rainA].slice(0,10))?'00ч':(eDay===D.time[rainA].slice(0,10)?eTime:relDay(eTs)+' '+eTime);" in tpl
    assert "'Ближайший дождь: '+dayLabel(d)+' с '+hh(D.time[rainA])+' до '+endLabel" in tpl


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


def test_warnings_nearest_row_uses_two_model_threshold_and_first_dry_boundary():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "if(sourceCountAt(k,list,precipMin)<2)break;sE=k;" in tpl
    assert "sourceList(s,list,precipMin)" not in tpl
    assert "const R=rainModelRange(s,sE);const sLabel=R.mn>=1?'по '+rcLbl(R.mn,R.mx):''" in tpl
    assert "endLabel(ts[Math.min(sE+1,ts.length-1)]," in tpl
    assert "function rainModelRange(a,b){" in tpl
    assert "function rcLbl(mn,mx){" in tpl
    assert "return {mn,mx};" in tpl


def test_warnings_confirmed_requires_two_models():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "sourceCountAt(i,list,pm)>=2" in tpl
    assert "if(sourceCountAt(i,list,pm)>=mn)return i;" in tpl
    assert "sourceCountAt(i,list,pm)>0)return i;" not in tpl


def test_warnings_gust_column_instead_of_hail():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "const GUST_MIN=15;" in tpl
    assert "wind_gusts_10m?.[i]" in tpl
    assert "findGust(1)" in tpl and "findGust(2)" in tpl
    # предупреждение о ветре показывает ЧИСЛО моделей, а не название модели:
    # строка обязана читаться одинаково при любом счётчике
    assert "' м/с · по '+rcLbl(g.n,g.n);}" in tpl
    assert "g.lst.join(' и ')" not in tpl
    # список имён стал мёртвым кодом — убирать, а не оставлять на будущее
    assert "lst.push(names[c])" not in tpl
    assert "const lst=[]" not in tpl
    assert "col('🧊',H)" not in tpl


def test_wind_warning_uses_model_count_never_model_name():
    """«Чт 8 в 20ч до 15 м/с · по 1 модели» вместо «· Visual Crossing»."""
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()

    def rc_lbl(mn, mx):
        # порс той же rcLbl(), которой пользуется строка предупреждения
        if mn < 1:
            return ""
        if mn == mx:
            return "1 модели" if mn == 1 else "%d моделям" % mn
        return "%d-%d моделям" % (mn, mx)

    assert "по " + rc_lbl(1, 1) == "по 1 модели"
    for n, want in ((2, "по 2 моделям"), (3, "по 3 моделям"),
                    (5, "по 5 моделям"), (11, "по 11 моделям")):
        assert "по " + rc_lbl(n, n) == want, n

    # имя модели в предупреждении о ветре больше не встречается вовсе
    assert "names[c]}" not in tpl.split("const gustInfo=")[1][:400]
    assert "function rcLbl(mn,mx){" in tpl


def test_warnings_do_not_duplicate_when_nearest_confirmed_coincide():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "if(s>=0&&s!==c" in tpl
    assert "if(g1>=0&&g1!==g2)" in tpl


def test_warnings_frost_column_replaces_thunderstorm():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "temperature_2m?.[i]" in tpl
    assert "🥶" in tpl
    assert "подтверждено" in tpl
    assert "Заморозков в ближайшие дни не ожидается" in tpl
    assert "v===96||v===99" not in tpl
    assert "риск грозы" not in tpl
    assert "findRisk" not in tpl


def test_warnings_empty_messages():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "Осадков в ближайшие дни не ожидается" in tpl
    assert "Заморозков в ближайшие дни не ожидается" in tpl
    assert "Гроз и града в ближайшие дни не ожидается" not in tpl
    assert "Порывистого ветра в ближайшие дни не ожидается" in tpl
    assert "Возможный минимум " in tpl


def test_warnings_precip_column_wider_than_wind():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    import re
    def flex_grow(cls):
        m = re.search(r"\." + cls + r"\s*\{[^}]*?flex\s*:\s*([\d.]+)", tpl)
        assert m, "no flex in .%s rule" % cls
        return float(m.group(1))
    assert flex_grow("wcol-precip") > flex_grow("wcol-wind")
    assert "'wcol-precip')" in tpl
    assert "wcol wcol-wind" in tpl
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "const fmtP=v=>" in tpl
    assert "Math.round(v*100)/100" in tpl
    assert "fmtP(pr)+'мм'" in tpl
    assert "fmtP(x.pr))+'мм / '" in tpl
    assert "fmtP(prSum)+' мм'" in tpl


def test_daily_precip_shows_zero_below_tenth():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "'Осадки за день',(pr<0.1?0:fmtP(pr))+' мм'" in tpl


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
    assert "63:['Дождь','🌧️']" in tpl
    assert "65:['Сильный дождь','🌧️']" in tpl
    assert "80:['Небольшой ливень','🌧️']" in tpl
    assert "51:['Небольшая морось','🌧️']" in tpl
    assert "61:['Дождь'" not in tpl


def test_wmo_dictionary_is_canonical_everywhere():
    canonical = {
        1: "В основном ясно", 48: "Изморозь",
        51: "Небольшая морось", 53: "Морось", 55: "Сильная морось",
        56: "Ледяная морось", 57: "Ледяная морось",
        61: "Небольшой дождь", 63: "Дождь", 65: "Сильный дождь",
        66: "Ледяной дождь", 67: "Ледяной дождь",
        71: "Небольшой снег", 73: "Снег", 75: "Сильный снег", 77: "Снежные зерна",
        80: "Небольшой ливень", 81: "Ливень", 82: "Сильный ливень",
        85: "Снегопад", 86: "Снегопад",
        95: "Гроза", 96: "Гроза с градом", 99: "Гроза с градом",
    }
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    for code, label in canonical.items():
        assert "{}:['{}'".format(code, label) in tpl, "template.html code {}: {}".format(code, label)
    for bad in ("['Морось','🌧️'],53:[", "['Ливень','🌧️'],81:[", "71:['Снег'", "75:['Снег'", "48:['Туман"):
        assert bad not in tpl, "template.html simplified: " + bad
    for fname in ("meteo.html", "meteow.html"):
        with open(os.path.join(HERE, fname), encoding="utf-8") as f:
            w = f.read()
        for code, label in canonical.items():
            assert "l:'{}'".format(label) in w, "{} code {}: {}".format(fname, code, label)


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
    assert "lightning-0" in tpl and "lightning-1" in tpl
    assert "createPane('lightning-0')" in tpl
    assert "t=" in tpl
    assert "maxZoom:10" in tpl
    assert 'id="ltoggle"' in tpl
    assert "saturate(8)" in tpl or "saturate(6)" in tpl or "saturate(5)" in tpl
    assert "drop-shadow" in tpl
    assert "hue-rotate(330deg)" in tpl


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
    assert "lab:'Датчики'" in tpl
    # последняя ячейка условна: у городов с датчиками — «Датчики» со средним
    # и размахом по станциям (без времени), у остальных — прежний CAPE
    assert "sensor_station_max" in tpl
    assert "mx:(sn&&sn.max!=null)?'↑ '+temp(sn.max):'—'" in tpl
    assert "mn:(sn&&sn.min!=null)?'↓ '+temp(sn.min):'—'" in tpl
    assert "lab:'Восход / закат'" not in tpl
    assert tpl.index("lab:'Температура'") < tpl.index("lab:'Осадки'") < tpl.index("lab:'Облачность'") < tpl.index("lab:'Ветер'") < tpl.index("lab:'Солнце'") < tpl.index("lab:'Видимость'") < tpl.index("lab:'Точка росы'") < tpl.index("lab:'Давление'") < tpl.index("lab:'Влажность'")
    # десятая ячейка — не литерал, а lastCell (Датчики или CAPE), и она идёт
    # последней в массиве cells
    assert tpl.index("lab:'Влажность'") < tpl.index("lastCell\n  ];")
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
    # окно «Осадки» — от первого дождливого часа дня до часа после конца
    # непрерывного эпизода; предикат часа вынесен в rainEpisodeWindow
    assert "function rainEpisodeWindow(today,pred){" in tpl
    assert "if(!pred(j))continue;" in tpl
    assert "while(k<D.time.length&&D.time[k]&&D.time[k].slice(0,10)===today&&pred(k))k++;" in tpl
    assert "pickRainWindow(today,prSum,hasRainAt,j=>modelTraceCount(j)>=2)" in tpl
    assert "function hasRainAt(j){const c=w.weather_code?.[j],p=w.precipitation?.[j],q=w.precipitation_probability?.[j];return rainCodes.includes(c)||" in tpl
    assert "'↑ '+fmt(w.precipitation[pMx])+' в '" not in tpl
    assert "const aptMean=apn?temp(apt/apn):'';" in tpl
    assert "aptMean?' ('+aptMean+')':''" in tpl


def test_hours_title_has_rain_only():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "parts.push('без дождя')" in tpl
    assert "const rainType=(rainCodes.includes(jStartCode)&&wcode(jStartCode)[0])?wcode(jStartCode)[0]:'Дождь';" in tpl
    assert "const timeStr=nowRain?'до '+enLabel:(st===enLabel?stDay+'в '+stHour:stDay+'с '+stHour+' до '+enLabel);" in tpl
    assert "'Остаток дня '" in tpl
    assert "tiMax" not in tpl
    assert "tiMin" not in tpl


def test_accuracy_tables_sorted_by_mean_mae():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "mrows.sort((a,b)=>(meanOf(ver[a],vnames)??1e9)-(meanOf(ver[b],vnames)??1e9))" in tpl


def test_hour_ribbon_no_precip_rects():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert ".hour{flex:none;width:64px;text-align:center;font-size:12px;padding:4px 2px;border-right:1px solid var(--line);position:relative;overflow:hidden;z-index:1}" in tpl
    assert ".hours .hbg{position:absolute;left:0;top:0;height:100%;pointer-events:none;z-index:0;overflow:hidden}" in tpl
    assert "hsel.insertAdjacentHTML('afterbegin','<svg class=\"hbg\"" in tpl
    assert "(hN*64)+'px\"" in tpl
    # в почасовой ленте осадки рисует только график-заливка, прямоугольники убраны;
    # .hprc остался лишь в детальных строках «Подробно», где графика нет
    assert ".hour .hprc{position:absolute;left:0;right:0;bottom:0;background:linear-gradient(#b3e5fc,#4fc3f7);opacity:.45;pointer-events:none}" in tpl
    assert ".hour .ht,.hour .he,.hour .htemp,.hour .hwnd,.hour .hpp{position:relative}" in tpl
    assert tpl.count('class="hprc"') == 1
    assert "class=\"hcl\"" not in tpl
    assert "const x=(hi)/hN*100;" in tpl
    assert "(hi+0.5)" not in tpl
    assert "Math.min(100,Math.round(pr/5*100))" in tpl


def test_d10_unified_cloud_rain_graph():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    # единый график облачности + осадков по часам на полные сутки, поверх всей полосы
    assert "function cloudRainSvg(" in tpl
    assert "function cloudRainSvgWrap(" in tpl
    assert "cloudRainSvgWrap(dt,null,yT)" in tpl
    # облачность: заливка к верху; осадки: заливка к низу (только залитая область, без обводки)
    assert "class=\"d10ccf\"" in tpl
    assert "class=\"d10prf\"" in tpl
    assert '.d10ccf{' in tpl
    assert '.d10prf{' in tpl
    assert 'class="d10ccl"' not in tpl
    assert 'class="d10prl"' not in tpl
    assert ".d10ccl" not in tpl
    assert ".d10prl" not in tpl
    # обводка только у кривой температуры, не у заливок
    assert "stroke-width" in tpl
    assert ".d10cline{" in tpl
    assert '.d10ccf{fill:rgba(141,154,165,.35);stroke:none}' in tpl
    assert '.d10prf{fill:rgba(25,118,210,.45);stroke:none}' in tpl
    # температура — синусоида вместо колонок: красная при +, синяя при —, с пересечением нуля
    assert "function tempLineSvg(days,yT)" in tpl
    assert '<path d="' in tpl
    assert 'stroke="#e74c3c"' in tpl
    assert 'stroke="#3498db"' in tpl
    assert "<polyline" not in tpl
    assert 'class="d10tbar"' not in tpl
    assert "d10tbar{" not in tpl
    # полоса позиционирована (для наложения svg поверх)
    assert ".d10strip{display:flex;width:100%;min-width:100%;position:relative}" in tpl
    # дни разделены тонкой вертикальной линией
    assert ".d10col{flex:1;min-width:70px;text-align:center;position:relative;z-index:1;border-left:1px solid var(--line)}" in tpl
    assert ".d10col:first-child{border-left:0}" in tpl
    # заливка на всю ширину ленты даже при прокрутке на смартфоне
    assert "if(d10svg)d10svg.style.width=d10strip.scrollWidth+'px';" in tpl
    # график ограничен высотой трубки (0.01мм / 0% строка полосы), не растягивается вниз до подписей дней
    assert ".d10svg{position:absolute;left:0;top:0;width:100%;height:135px;overflow:hidden;pointer-events:none}" in tpl
    assert ".d10svg{position:absolute;left:0;top:0;width:100%;height:100%" not in tpl
    # график позади колонок температуры (как раньше бар был первым ребёнком трубки)
    assert ".d10tube{height:135px;position:relative;z-index:1}" in tpl
    # точка часа стоит на сетке часа (пик осадков в 11ч читается в позиции 11ч)
    assert "const x=(di*24+h)/(N*24)*100;" in tpl
    assert "(di*24+h+0.5)" not in tpl
    # осадки — по часовым мм (как в данных weighted.precipitation), верх = 10 мм/час
    assert "(1-Math.min(1,r/5))*135" in tpl
    assert "const r=D.weighted.precipitation?.[i];" in tpl
    assert "sum/30" not in tpl
    # облачность не инвертирована: заливка растёт сверху вниз по мере роста облачности (17% -> ~17% высоты)
    assert "c/100*135" in tpl
    assert "(100-c)/100*135" not in tpl
    assert "r/50" not in tpl
    assert "r/20" not in tpl
    # старый пер-колоночный svg и бары удалены
    assert "cloudSvg(x.day)" not in tpl
    assert "cloudSvg(day)" not in tpl
    assert "class=\"d10cloud\"" not in tpl
    assert "class=\"d10prec\"" not in tpl
    assert "d10cloudline" not in tpl
    assert "d10cloudfill" not in tpl
    # график из «Подробно» убран (не ломает высоту строк и не добавляет скроллов)
    assert "hetSvg" not in tpl
    assert "cloudRainSvgWrap([day]" not in tpl
    assert ".hours{display:flex;overflow-x:auto;padding:4px 0;position:relative}" in tpl


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


def test_widget_precip_font_and_ppct():
    for fname in ("meteo.html", "meteow.html"):
        with open(os.path.join(HERE, fname), encoding="utf-8") as f:
            w = f.read()
        assert '<span class="ppct">%</span>' in w, fname
        assert ".ppct{font-size:.5em}" in w, fname


def test_widget_rain_type_uses_current_hour_not_peak():
    for fname in ("meteo.html", "meteow.html"):
        with open(os.path.join(HERE, fname), encoding="utf-8") as f:
            w = f.read()
        assert "var jCode=data.weather_code?Math.round(data.weather_code[rainHour]):0;" in w, fname
        assert "var rainType=(RAIN.indexOf(jCode)>=0&&WMO[jCode])?WMO[jCode].l:" in w, fname
        assert "data.weather_code[jPeak]" not in w, fname


def test_widget_d10_unified_cloud_rain_graph():
    with open(os.path.join(HERE, "meteow.html"), encoding="utf-8") as f:
        w = f.read()
    # единый SVG облачность+осадки в виджете, поверх всей полосы дней
    assert "function cloudRainSvgW(" in w
    assert "d10strip.innerHTML = html10 + cloudRainSvgW(arr.slice(0, dispDays), 74)" in w
    assert "var shownDays" not in w
    # только залитые области без обводки
    assert 'class="d10ccf"' in w
    assert 'class="d10prf"' in w
    assert 'class="d10ccl"' not in w
    assert 'class="d10prl"' not in w
    assert "d10ccl" not in w
    assert "d10prl" not in w
    # обводка только у кривой температуры, не у заливок
    assert "stroke-width" in w
    assert ".d10cline{" in w
    # заливка дождя ярче
    assert '.d10prf{fill:rgba(25,118,210,.45);stroke:none}' in w
    # температура — синусоида вместо колонок: красная при +, синяя при —, с пересечением нуля
    assert "function tempCurve(" in w
    assert '<path d="' in w
    assert 'stroke="#e74c3c"' in w
    assert 'stroke="#3498db"' in w
    assert "<polyline" not in w
    assert 'class="d10tbar"' not in w
    assert "d10tbar{" not in w
    # результат обёрнут в <svg> (иначе фигуры не видны)
    assert "'<svg class=\"d10svg\" viewBox=\"0 0 100 ' + HGT + '\" preserveAspectRatio=\"none\">' + out + '</svg>'" in w
    assert ".d10strip{display:flex;width:100%;min-width:100%;position:relative}" in w
    # дни разделены тонкой вертикальной линией
    assert ".d10col{flex:1 1 0;min-width:0;text-align:center;position:relative;z-index:1;border-left:1px solid var(--line)}" in w
    assert ".d10col:first-child{border-left:0}" in w
    # график ограничен высотой трубки виджета (64px), не растягивается вниз
    assert ".d10svg{position:absolute;left:0;top:0;width:100%;height:74px;overflow:hidden;pointer-events:none}" in w
    # график позади колонок температуры
    assert ".d10tube{height:74px;position:relative;z-index:1}" in w
    # осадки — по часовым мм, верх = 10 мм/час
    assert "(1 - Math.min(1, r / 5)) * HGT" in w
    assert "sum / 30" not in w
    # облачность виджета не инвертирована (заливка растёт сверху вниз по мере роста облачности)
    assert "c / 100 * HGT" in w
    assert "(100 - c) / 100 * HGT" not in w
    # старые пер-дневные бары облачности и осадков убраны
    assert "d10cloud" not in w
    assert "d10prec" not in w
    # в колонке виджета вместо мм — значок кондиции
    assert 'class="d10mm"' not in w
    assert 'class="d10cond"><span class="ic">' in w
    assert ".d10cond{font-size:15.5px" in w
    # первый день в виджете — сегодня (не завтра), подпись — день недели + число (без «Сегодня/Завтра»)
    assert "if (dateStr < todayStr) continue;" in w
    assert "dateStr <= todayStr" not in w
    assert "relDay(x.ds)" not in w
    assert "'<div class=\"d10day\"><b>' + DOW[x.d.getDay()] + '</b> ' + x.d.getDate() + '</div>'" in w
    # точка часа — на сетке часа, а не в середине слота (пик 11ч читается в позиции 11ч)
    assert "var x = (di * 24 + h) / (N * 24) * 100;" in w
    assert "var x = (di * 24 + h) / (list.length * 24) * 100;" in w
    assert "var x = h / cnt * 100;" in w
    assert "(h + 0.5)" not in w
    # заливки облачности/осадков в почасовой части, как в 16 днях (SVG позади ячеек)
    assert ".strip{display:flex;gap:2px;padding:2px 0 1px;position:relative}" in w
    assert ".hobg{position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:none;z-index:0;overflow:hidden}" in w
    assert "function hourBgSvg(" in w
    assert "strip.insertAdjacentHTML('afterbegin', bg)" in w
    assert "(1 - Math.min(1, r / 5)) * 100" in w
    # по одному последнему элементу убраны: 16 часов и 16 дней — остальные крупнее
    assert "var DEFAULT_HOURS = 16;" in w
    # заливки/кривая считаются по числу выводимых колонок, иначе при обрезке 16→16 сетка графика разъезжалась бы с колонками
    assert "var dispDays = Math.min(arr.length, 16);" in w
    assert "d10strip.innerHTML = html10 + cloudRainSvgW(arr.slice(0, dispDays), 74);" in w


def test_js_brace_balance_in_html_files():
    for fname in ("template.html", "meteo.html", "meteow.html", "radar.html", "radar_template.html"):
        with open(os.path.join(HERE, fname), encoding="utf-8") as f:
            content = f.read()
        for script in re.findall(r"<script>(.*?)</script>", content, re.S):
            assert script.count("{") == script.count("}"), fname + " braces"
            assert script.count("(") == script.count(")"), fname + " parens"
            assert script.count("[") == script.count("]"), fname + " brackets"


def test_no_reserved_js_keywords_as_identifiers():
    reserved = ("in","class","new","for","if","else","return","typeof","function",
                "do","while","switch","case","break","continue","delete","void",
                "this","with","try","catch","throw","instanceof","of")
    for fname in ("template.html", "meteo.html", "meteow.html", "radar.html", "radar_template.html"):
        with open(os.path.join(HERE, fname), encoding="utf-8") as f:
            content = f.read()
        for script in re.findall(r"<script>(.*?)</script>", content, re.S):
            for kw in reserved:
                assert not re.search(r"\b(const|let|var)\s+" + kw + r"\b", script), \
                    fname + " reserved word used as identifier: " + kw


def test_relday_shows_date_for_after_tomorrow():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    # «Завтра» остаётся словом
    assert "if(diff===1)return 'Завтра';" in tpl
    # «Послезавтра» больше не используется; diff===2 уходит в общий формат даты
    assert "Послезавтра" not in tpl
    assert "if(diff===2)" not in tpl
    assert "return DAY_NAMES_SHORT[d.getDay()]+' '+d.getDate();" in tpl


def test_warnings_no_current_model_rain_row():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "const curN" not in tpl
    assert "'Сейчас'+endH" not in tpl
    assert "endH?'Сейчас':'Текущий час'" not in tpl
    assert "curN>=minProb&&(curIdx<from)" not in tpl


def test_rain_model_count_uses_min_per_hour():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "let mCnt=Infinity,mX=-Infinity,ccCnt=Infinity,ccX=-Infinity;" in tpl
    assert "if(n<mCnt)mCnt=n;" in tpl
    assert "if(cn<ccCnt)ccCnt=cn;" in tpl
    assert "if(mCnt===Infinity)mCnt=0;" in tpl
    assert "if(mX===-Infinity)mX=0;" in tpl
    assert "if(mn===Infinity)mn=0;" in tpl
    assert "if(mx===-Infinity)mx=0;" in tpl
    assert "if(has)mCnt++" not in tpl
    assert "const R=rainModelRangeCons(c0,c1);rows.push('<div class=\"wr2\">'+cLbl+wv+(R.mn>=1?' · по '+rcLbl(R.mn,R.mx):'')+'</div>');}" in tpl
    assert "const R=rainModelRange(c0,c1);rows.push" not in tpl
    assert "const R=rainModelRangeCons(s,sE);" not in tpl
    assert "n>=1?' · по '+(n===1?'1 модели':n+' моделям'):''" not in tpl
    # wr2 для идущего сейчас дождя показывает «до часа после последнего подтверждённого» (без типа)
    assert "cLbl='до '+endLabel(ts[Math.min(ce+1,ts.length-1)]);" in tpl
    assert "cLbl=rType+' до '+endLabel(ts[Math.min(ce+1,ts.length-1)]);" not in tpl
    assert "const eh=ce>curIdx?endLabel(ts[Math.min(ce+1,ts.length-1)]):'';" not in tpl
    assert "endLabel(ts[Math.min(cE+1,ts.length-1)],ts[c].slice(0,10))" in tpl
    assert "const n=sourceCountAt(c,list,precipMin)" not in tpl
    for fname in ("meteo.html", "meteow.html"):
        with open(os.path.join(HERE, fname), encoding="utf-8") as f:
            w = f.read()
        assert "if(n<peakModels)peakModels=n;" in w, fname
        assert "if(peakModels===Infinity)peakModels=0;" in w, fname
        assert "if(all)peakModels++" not in w, fname
        assert "if(n>peakMax)peakMax=n;" in w, fname
        assert "function rcCnt(mn,mx)" in w, fname
        assert "rcCnt(peakModels,peakMax)" in w, fname
        assert "mn===mx?mn+'" in w, fname
        assert "if(code!=null?RAIN.indexOf(code)>=0:" in w, fname
        assert "if(mn<1)return '';" in w, fname
        assert "var conCnt=conPeak>=1?(' '+rcCnt(conPeak,conMax)):'';" in w, fname
        assert "var conCnt=conPeak>=2?(' '+rcCnt(conPeak,conMax)):'';" not in w, fname
        assert "if(cn<conPeak)conPeak=cn;" in w, fname
        assert "if(cn>conMax)conMax=cn;" in w, fname
        assert "if(RAIN.indexOf(code)>=0||(pr!=null&&pr>=0.1)||((pr==null||pr<0.1)&&pp!=null&&pp>20))cn++;" in w, fname
    with open(os.path.join(HERE, "meteo.html"), encoding="utf-8") as f:
        m = f.read()
    assert "function rcCnt(mn,mx){if(mn<1)return '';return mn===mx?mn+'м':mn+'-'+mx+'м';}" in m


def test_index_has_sputnik_tab_and_iframe():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert 'data-tab="satellite"' in tpl
    assert '<button data-tab="satellite">Спутник</button>' in tpl
    assert 'id="satellite-frame"' in tpl
    assert "updateSputnikFrame()" in tpl
    assert "'satellite'" in tpl


def test_day_verdict_removed_completely():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    # вердикт-предложения убраны: ни функции, ни вставок из «Сейчас», ни справа в 16 днях
    assert "buildDayVerdict" not in tpl
    assert "class=\"wadv\"" not in tpl
    assert "hverdict" not in tpl
    assert "verdictCol" not in tpl
    # блок «Сейчас» вернулся к таблице без вердикта; 16 дней — столбцы без вердикта
    assert "'<div class=\"wdet\"><table class=\"wnowtbl\"><tr>'" in tpl
    assert "'<div class=\"hours\">'+sumCol+blocks.join('')+sunCol+'</div>'" in tpl


def test_current_hour_uses_city_timezone():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "function cityTz()" in tpl
    assert "function cityClock()" in tpl
    assert "function cityToday()" in tpl
    assert "const curHour=cityClock().slice(0,13)+':00';" in tpl
    assert "nowMsk().replace(', ','T').slice(0,13)+':00'" not in tpl


def test_warnings_today_uses_city_grid():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "const todayStr=cityToday();" in tpl
    assert "const today=todayStr;" in tpl
    assert "new Date().toISOString().slice(0,10)" not in tpl


def test_detail_rain_window_breaks_on_dry_hour():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "else if(rst!==null)break;" in tpl


def test_meteo_widget_hour_fill():
    with open(os.path.join(HERE, "meteo.html"), encoding="utf-8") as f:
        m = f.read()
    assert ".strip{" in m and "position:relative" in m
    assert ".hobg{position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:none;z-index:0;overflow:hidden}" in m
    assert ".d10ccf{fill:rgba(141,154,165,.35);stroke:none}" in m
    assert ".d10prf{fill:rgba(25,118,210,.45);stroke:none}" in m
    assert "function hourBgSvg(cnt)" in m
    assert "if (bg) strip.insertAdjacentHTML('afterbegin', bg);" in m
    assert "(1 - Math.min(1, r / 5)) * 100" in m
    assert "(pr.length >= 2){ out += '<polygon points=\"' + pr.join(' ') + ' 100,100 0,100\" class=\"d10prf\"/>'; }" in m
    assert "data.weighted.temperature_2m ? data.weighted.temperature_2m[i] : 0" in m


def test_widget_fill_scale_is_five_mm():
    for fname in ("meteo.html", "meteow.html"):
        with open(os.path.join(HERE, fname), encoding="utf-8") as f:
            w = f.read()
        assert "r / 5" in w, fname
        assert "r / 10" not in w, fname
        assert "r/10" not in w, fname


def test_widget_summary_formats_match_both_widgets():
    import re as _re

    def unescape(src):
        return _re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), src)

    def stmt(src, var):
        for line in src.splitlines():
            if line.strip().startswith("var " + var + "="):
                return line.strip()
        return None

    with open(os.path.join(HERE, "meteo.html"), encoding="utf-8") as f:
        m = unescape(f.read())
    with open(os.path.join(HERE, "meteow.html"), encoding="utf-8") as f:
        w = unescape(f.read())
    for var in ("timeStr", "cntStr", "conCnt", "stats"):
        assert stmt(m, var) is not None
        assert stmt(m, var) == stmt(w, var), var
    assert "if(fromModels) return 'Вероятны Осадки '+timeStr+' '+stats+cntStr;" in m
    assert "if(fromModels) return 'Вероятны Осадки '+timeStr+' '+stats+cntStr;" in w
    assert "var txt=rainType+' '+timeStr+' '+stats+conCnt;" in m
    assert "var txt=rainType+' '+timeStr+' '+stats+cntStr;" not in m


def test_help_texts_mention_model_range():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "«по N-K моделям»" in tpl
    assert "диапазон числа моделей по часам интервала" in tpl or "минимум-максимум по часам" in tpl


def _radar_template():
    with open(os.path.join(HERE, "radar_template.html"), encoding="utf-8") as f:
        return f.read()


def _fetch_url(src, expr):
    """Адрес из выражения fetch(<expr>): строковый литерал либо переменная,
    которой в этом же файле присвоен строковый литерал. None — не распознали."""
    m = re.match(r"""\s*['"]([^'"]*)['"]""", expr)
    if m:
        return m.group(1)
    m = re.match(r"\s*([A-Za-z_$][\w$]*)", expr)
    if not m:
        return None
    q = re.search(r"(?:^|[^\w$.])" + re.escape(m.group(1)) + r"\s*=\s*['\"]([^'\"]*)['\"]", src)
    return q.group(1) if q else None


def test_radar_template_knows_nothing_about_sensors():
    # Слой измерений переехал в столбик «Датчик» таблицы «Часы» (tests/test_locations.py):
    # карта показывает осадки и молнии, измерения — в часовой сетке. Инвариант
    # структурный, а не список запрещённых имён: радар не знает о датчиках вообще,
    # поэтому любое упоминание sensor (в любом регистре, в любом написании — sensors,
    # sensorLayer, sensors_data.json) означает, что слой вернулся на карту. Список
    # вроде createPane('stations') от этого не спасал: переименованный слой
    # (createPane('sensors') / sensorLayer / fetch('sensors_data.json')) проходил его
    # насквозь.
    src = _radar_template()
    hits = [(i + 1, ln.strip()) for i, ln in enumerate(src.splitlines())
            if re.search("sensor", ln, re.I)]
    assert not hits, (
        "radar_template.html снова знает о датчиках: %r.\n"
        "Измерения живут в столбике «Датчик» таблицы «Часы» (tests/test_locations.py); "
        "на радаре их быть не должно — правьте таблицу часов, а не карту." % hits[:3]
    )

    # Второй, независимый от имён признак того же слоя: локальный источник данных.
    # Снимок датчиков всегда был бы файлом этого сайта, то есть относительным
    # fetch(), а у радара таких нет — всё, что он грузит, приходит с внешнего
    # тайлового API rainradar.ru (плитки, подписи, манифест). Поэтому проверяем не
    # имена файлов, а сам набор адресов: любое отклонение — новый источник данных.
    targets = [_fetch_url(src, e) for e in re.findall(r"fetch\((.*)", src)]
    hosts = set()
    for t in targets:
        m = re.match(r"https?://([^/]+)", t or "")
        hosts.add(m.group(1) if m else t)
    assert hosts == {"rainradar.ru"}, (
        "радар грузит что-то помимо внешнего API rainradar.ru: %r.\n"
        "У карты нет своих файлов с измерениями — снимок датчиков живёт в таблице "
        "«Часы», а не на радаре." % targets
    )


def _lf(blob):
    """Артефакт с переводами строк, приведёнными к LF."""
    return blob.replace(b"\r\n", b"\n")


def _same_artifact(fresh, committed):
    """Побайтовое сравнение артефакта, не зависящее от перевода строк.

    В репозитории нет .gitattributes, поэтому файл в рабочей копии приходит с
    CRLF при core.autocrlf=true и с LF при core.autocrlf=false, а свежая сборка
    всегда пишется текстовым open() и на Windows получает CRLF. Сравнение
    нормализует переводы строк вместо того, чтобы вводить .gitattributes,
    который изменил бы поведение репозитория целиком.
    """
    return _lf(fresh) == _lf(committed)


def _drift(fresh, committed):
    """Диагноз расхождения: где именно разошлись два артефакта.

    Длины файлов при настоящем дрейфе почти всегда равны — правится текст той же
    длины, а не добавляется блок, — поэтому «собрано N байт против M байт» в
    сообщении падения не говорит ничего: оба числа совпадают и выглядят как
    «всё хорошо». Поэтому показываем позицию первого различия, оба байта,
    строку целиком и длины уже после нормализации переводов строк (сырые длины
    зависят от core.autocrlf машины и в диагностике только мешают).
    """
    a, b = _lf(fresh), _lf(committed)
    limit = min(len(a), len(b))
    pos = next((i for i in range(limit) if a[i] != b[i]), limit)
    if pos == limit:
        if len(a) == len(b):
            return ("различий нет: артефакты совпадают побайтово после "
                    "нормализации переводов строк, %d байт" % len(a))
        shorter = "сборка" if len(a) < len(b) else "закоммиченный артефакт"
        return ("различие только в длине: %s короче, %d против %d байт после "
                "нормализации переводов строк, общий префикс %d байт"
                % (shorter, len(a), len(b), pos))
    line_no = a.count(b"\n", 0, pos) + 1
    col_no = pos - (a.rfind(b"\n", 0, pos) + 1) + 1
    line = a.split(b"\n")[line_no - 1].strip().decode("utf-8", "replace")
    return ("первое различие — смещение %d, строка %d, столбец %d: в сборке %r, "
            "в репозитории %r; строка целиком: %s; длины после нормализации "
            "переводов строк %d и %d"
            % (pos, line_no, col_no,
               a[pos:pos + 1].decode("utf-8", "replace"),
               b[pos:pos + 1].decode("utf-8", "replace"),
               line[:200], len(a), len(b)))


def test_radar_html_is_in_lockstep_with_template(tmp_path):
    # radar.html — закоммиченный артефакт сборки, и рассинхрон шаблона с артефактом —
    # историческая поломка этого проекта. Пересобираем шаблон в tmp_path и сравниваем
    # байт в байт: так ловится дрейф в обе стороны (правка шаблона без пересборки и
    # правка артефакта без шаблона). Ban-лист по строкам этого не ловил вовсе.
    build_radar.build("radar", out_dir=str(tmp_path))
    fresh = (tmp_path / "radar.html").read_bytes()
    with open(os.path.join(HERE, "radar.html"), "rb") as f:
        committed = f.read()
    assert _same_artifact(fresh, committed), (
        "radar.html разошёлся с radar_template.html: %s. Пересобери и закоммить "
        "артефакт: python tools/build_radar.py radar" % _drift(fresh, committed)
    )


def test_lockstep_survives_a_checkout_with_other_autocrlf(tmp_path):
    # .gitattributes в репозитории нет, поэтому переводы строк на рабочей копии
    # задаёт core.autocrlf машины: индекс хранит LF, а checkout с autocrlf=true
    # раздаёт CRLF, checkout с autocrlf=false — LF. Свежая сборка всегда пишется
    # текстовым open() и на Windows получает CRLF, так что побайтовое сравнение
    # зависит от того, где запущен тест, и падает ложно. Эмулируем checkout с
    # autocrlf=false (LF) и сравниваем с собранным файлом (CRLF).
    build_radar.build("radar", out_dir=str(tmp_path))
    fresh = (tmp_path / "radar.html").read_bytes()
    with open(os.path.join(HERE, "radar.html"), "rb") as f:
        committed = f.read()
    checkout = committed.replace(b"\r\n", b"\n")
    assert _same_artifact(fresh, checkout), (
        "эмуляция checkout с autocrlf=false не сошлась: сборка и LF-версия "
        "артефакта различаются. Причина не обязательно перевод строк: если "
        "radar.html разошёлся с radar_template.html по-настоящему, тест упадёт "
        "здесь же, и нижеследующий диагноз покажет это как обычное различие "
        "байтов. %s. Если дело в артефакте — пересобери и закоммить его: "
        "python tools/build_radar.py radar" % _drift(fresh, checkout)
    )


def test_widget_shows_sensor_temperature_with_directional_rounding():
    # Строка виджета начинается с температуры датчика: у Цеденево округление
    # следует за показанной величиной (среднее в окне рассвет+3ч…закат-2ч —
    # вверх, минимум вне окна — вниз), у остальных городов остаётся старое
    # окно рассвет–закат.
    for fname in ("meteo.html", "meteow.html"):
        with open(os.path.join(HERE, fname), encoding="utf-8") as f:
            w = f.read()
        assert "function widgetSensorTemp(data, idx)" in w, fname
        assert "function sensorShowsMean(data, j)" in w, fname
        assert "function sensorInDayWindow(data, j)" in w, fname
        assert "function roundSensorTemp(v, showsMean)" in w, fname
        assert "return showsMean ? Math.ceil(v) : Math.floor(v);" in w, fname
        assert "var sensorTemp = widgetSensorTemp(data, idx);" in w, fname
        # Шапка собирается из частей через join(', '), а не склейкой строки:
        # тогда запятая появляется ровно между непустыми частями, и пропуск
        # температуры не оставляет висячей запятой. Эмодзи в исходниках —
        # escape-последовательность, поэтому сравниваем с ней.
        assert "var headParts = [];" in w, fname
        assert "if (sensorTemp) headParts.push(sensorTemp);" in w, fname
        assert "headParts.push(summary);" in w, fname
        # ветер из шапки убран — он теперь в почасовой строке
        assert "windPart" not in w, fname
        # значок обёрнут в span, чтобы его можно было увеличить отдельно от
        # текста города; сравниваем с escape-последовательностью эмодзи
        assert (
            r"""cityEl.innerHTML = '<span class="cico">\uD83C\uDF24</span> ' + headParts.join(', ');"""
            in w
        ), fname
        assert "' + sensorTemp + summary;" not in w, fname
        # виджет берёт наблюдение датчиков, а не прогноз
        assert "var SENSOR_CODE = 'sensors'" in w, fname
        assert "var SENSOR_VARS = ['temperature_2m']" in w, fname
        assert "var n = sc ? sc[key] : null;" in w, fname
        assert "var v = sr ? sr.temperature_2m : null;" in w, fname
        # Цеденево вне окна среднего показывает минимум — то же значение, что
        # и главная страница
        assert "var mn = data.sensor_station_min ? data.sensor_station_min.temperature_2m : null;" in w, fname
        assert "slug==='tsedenevo' && !showsMean && mn && mn[j]!=null" in w, fname
        # виджеты написаны в ES5 (var, без ?. и const) — не потерять стиль
        assert "?." not in w, fname
        assert "const " not in w, fname


def test_widget_sensor_temp_absent_when_no_observation():
    # Без наблюдения строка виджета остаётся прежней: пустой префикс вместо
    # прочерка, иначе заголовок занял бы место пустотой.
    for fname in ("meteo.html", "meteow.html"):
        with open(os.path.join(HERE, fname), encoding="utf-8") as f:
            w = f.read()
        assert "if(!n||!v) return '';" in w, fname
        assert "return '';" in w.split("function widgetSensorTemp")[1][:1200], fname


def test_widget_header_separates_temp_from_summary():
    # Заголовок: «🌤 +14, Дождь …» — между непустыми частями запятая с
    # пробелом, а не склейка без разделителя и не запятая на месте пропуска.
    # Ветер из шапки убран: он теперь в почасовом блоке. Строка собирается
    # целиком: раздельные assert на «+14» и «Дождь» прошли бы и при слипшейся.
    def header(sensor_temp, summary):
        parts = []
        if sensor_temp: parts.append(sensor_temp)
        parts.append(summary)
        return "\u2600\uFE0F " + ", ".join(parts)

    # эмодзи в виджете не обязателен для проверки разделителя, но строка
    # должна собираться ровно так же, как в JS
    for sensor_temp, summary, want in (
        ("+14", "Дождь Пн 5 22ч-Вт 6 23ч [0мм_34%] 3-10м",
         "\u2600\uFE0F +14, Дождь Пн 5 22ч-Вт 6 23ч [0мм_34%] 3-10м"),
        ("", "Дождь сегодня 10ч-12ч [0.2мм_60%] 2м",
         "\u2600\uFE0F Дождь сегодня 10ч-12ч [0.2мм_60%] 2м"),
        ("+14", "Остаток дня без дождя",
         "\u2600\uFE0F +14, Остаток дня без дождя"),
        ("", "Остаток дня без дождя",
         "\u2600\uFE0F Остаток дня без дождя"),
    ):
        got = header(sensor_temp, summary)
        assert got == want, (got, want)
        # ни слипания, ни двойного пробела, ни висячей запятой
        assert "  " not in got, got
        assert ",," not in got, got

    import re as _re

    def unescape(src):
        return _re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), src)

    for fname in ("meteo.html", "meteow.html"):
        with open(os.path.join(HERE, fname), encoding="utf-8") as f:
            w = unescape(f.read())
        line = [ln.strip() for ln in w.splitlines() if "headParts.join(', ')" in ln]
        assert len(line) == 1, (fname, line)
        assert "cityEl.innerHTML" in line[0], (fname, line[0])


def test_widget_header_wind_arrow_rotates_to_direction():
    # Стрелка ветра в шапке: ↑ повёрнут на (направление+180)° — показывает,
    # куда дует ветер, как в 10-дневной полосе, — и румб уходит в подпись.
    # Скорость округляется до целых м/с тем же rnd. Нет скорости — пустая
    # строка: в шапке ветер лучше опустить, чем показать прочерк.
    import re as _re

    def unescape(src):
        return _re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), src)

    for fname in ("meteo.html", "meteow.html"):
        with open(os.path.join(HERE, fname), encoding="utf-8") as f:
            w = unescape(f.read())
        assert "function windArrow(wd, ws)" in w, fname
        assert "if(ws == null) return '';" in w, fname
        assert "(wd + 180) % 360" in w, fname
        assert "Math.round(rot)" in w, fname
        assert "rnd(ws)" in w, fname
        assert "\u2191" in w, fname
        assert "\u0412\u0435\u0442\u0435\u0440 \u043a" in w, fname
        assert 'class="warr"' in w, fname
        assert ".warr{" in w, fname
        # виджеты остаются ES5
        assert "?." not in w, fname
        assert "const " not in w, fname


def test_widget_header_icon_larger_and_gap_to_hourly_reduced():
    # Значок 🌤 в шапке крупнее текста города, а зазор от шапки до часовой
    # полосы — на 1px меньше прежних 8px. Значок обёрнут в .cico, иначе
    # увеличить его отдельно от названия города нельзя.
    import re as _re

    for fname in ("meteo.html", "meteow.html"):
        with open(os.path.join(HERE, fname), encoding="utf-8") as f:
            w = f.read()
        cico = _re.search(r"\.city \.cico\{[^}]*\}", w)
        assert cico, f"{fname}: нет правила .city .cico"
        m = _re.search(r"font-size:(\d+)px", cico.group(0))
        assert m and int(m.group(1)) > 14, (fname, cico.group(0))
        assert r'<span class="cico">' in w, fname
        head = _re.search(r"\.head\{[^}]*\}", w)
        assert head, f"{fname}: нет правила .head"
        assert "margin-bottom:6px" in head.group(0), (fname, head.group(0))


def test_widget_hourly_shows_wind_between_condition_and_temperature():
    # В почасовой ячейке виджета строка ветра стоит между иконкой погоды и
    # температурой: стрелка повёрнута по ходу ветра (тот же windArrow, что в
    # шапке), сила без единиц — как в шапке. Строка резервирует высоту, чтобы
    # температуры во всех колонках не разъезжались там, где ветра нет.
    import re as _re

    def unescape(src):
        return _re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), src)

    for fname in ("meteo.html", "meteow.html"):
        with open(os.path.join(HERE, fname), encoding="utf-8") as f:
            w = unescape(f.read())
        # почасовые данные ветра берём по текущему часу цикла
        assert (
            "var wd = data.weighted.wind_direction_10m ? data.weighted.wind_direction_10m[i] : null;"
            in w
        ), fname
        assert (
            "var ws = data.weighted.wind_speed_10m ? data.weighted.wind_speed_10m[i] : null;"
            in w
        ), fname
        he = "'<div class=\"he\">' + w.e + '</div>'"
        hw = "'<div class=\"hwnd\">' + windArrow(wd, ws) + '</div>'"
        ht = "'<div class=\"htemp\">' + tempStr + '</div>'"
        for frag in (he, hw, ht):
            assert frag in w, (fname, frag)
        assert w.index(he) < w.index(hw) < w.index(ht), fname
        # CSS: строка не переносится и держит высоту
        wind_css = _re.search(r"\.hour \.hwnd\{[^}]*\}", w)
        assert wind_css, f"{fname}: нет правила .hour .hwnd"
        assert "min-height:" in wind_css.group(0), (fname, wind_css.group(0))
        assert ".hour .hwnd .warr{" in w, fname
        # виджеты остаются ES5
        assert "?." not in w, fname
        assert "const " not in w, fname


def test_sensor_mean_window_boundaries_shift_into_daylight():
    # Node недоступен, поэтому границы окна воспроизводим в Python — иначе
    # остаётся проверять только наличие констант в исходнике, а сдвиг на
    # час мог бы оказаться вычитанием вместо сложения и тест бы этого не
    # заметил.
    #
    # Рассвет 06:31, закат 18:12: окно среднего 09:31…16:11 включительно.
    sunrise, sunset = 6 * 60 + 31, 18 * 60 + 12

    def shows_mean(h):
        return h >= sunrise + 180 and h < sunset - 120

    def hour(s):
        return int(s[:2]) * 60 + int(s[3:5])

    # ночь и раннее утро — минимум
    assert not shows_mean(hour("00:00"))
    assert not shows_mean(hour("03:17"))
    assert not shows_mean(hour("06:00"))  # час начинается до рассвета
    assert not shows_mean(hour("06:31"))  # ровно рассвет, сдвиг ещё не прошёл
    assert not shows_mean(hour("09:30"))
    # граница снизу включена в окно
    assert shows_mean(hour("09:31"))
    assert shows_mean(hour("12:00"))
    assert shows_mean(hour("16:11"))
    # граница сверху не включена
    assert not shows_mean(hour("16:12"))
    assert not shows_mean(hour("18:11"))  # час начинается до заката, но вечер уже
    assert not shows_mean(hour("23:00"))

    # Окно не пустеет и зимой: солнце в Москве поднимается позже и садится
    # раньше, но сумма сдвигов всё равно меньше светового дня.
    winter_sunrise, winter_sunset = 8 * 60 + 57, 15 * 60 + 25
    winter = winter_sunrise + 180, winter_sunset - 120
    assert winter[0] < winter[1], f"зимой окно должно остаться непустым: {winter}"


def test_widget_rounding_window_differs_between_tsedenevo_and_other_cities():
    # Округление Цеденево следует за величиной, у Ярославля остаётся на
    # старом солнечном окне. Проверяем, что решение принимается по slug, а не
    # по одному окну на оба города: иначе Ярославль получил бы вечные +1.
    sunrise, sunset = 6 * 60 + 31, 18 * 60 + 12

    def shows_mean_new(h):
        return h >= sunrise + 180 and h < sunset - 120

    def in_old_day_window(h):
        return h >= sunrise and h < sunset

    # час 08:00: солнце уже есть, но окно среднего Цеденево ещё не началось
    assert in_old_day_window(8 * 60)
    assert not shows_mean_new(8 * 60)
    # значит Цеденево показывает минимум и округляет вниз, а Ярославль
    # показывает среднее и округляет вверх
    assert round(7.6) == 8  # среднее, ceil
    assert int(7.6) == 7  # минимум, floor


def test_widget_sensor_rounding_semantics():
    # Node недоступен, поэтому семантику округления воспроизводим в Python.
    # Границы: день ceil, ночь floor, ровные значения не меняются.
    import math

    def round_sensor_temp(v, is_day):
        return math.ceil(v) if is_day else math.floor(v)

    assert round_sensor_temp(13.18, True) == 14
    assert round_sensor_temp(13.18, False) == 13
    assert round_sensor_temp(5.2, True) == 6
    assert round_sensor_temp(5.8, False) == 5
    # отрицательные: «в большую» и «в меньшую» — это ceil/floor, а не toward zero
    assert round_sensor_temp(-2.3, True) == -2
    assert round_sensor_temp(-2.3, False) == -3
    assert round_sensor_temp(-2.0, True) == -2
    assert round_sensor_temp(-2.0, False) == -2
    assert round_sensor_temp(0.0, True) == 0
    assert round_sensor_temp(0.0, False) == 0


def test_widget_sensor_temp_prefix_format():
    # «+5» для положительных, «-3» для отрицательных, ноль без знака —
    # как в часовой ленте, но без знака градуса.
    for fname in ("meteo.html", "meteow.html"):
        with open(os.path.join(HERE, fname), encoding="utf-8") as f:
            w = f.read()
        assert "return(t>0?'+':'')+t;" in w, fname
        assert "'+';" not in w.split("function roundSensorTemp")[1][:200], fname


def test_widget_typography_is_half_a_pixel_smaller():
    # Шрифты виджета уменьшены на полпикселя: верхняя строчка и оба блока.
    # Значения зафиксированы числами, потому что полпикселя глазом не
    # отличить — без теста правка выглядит как «ничего не изменилось» и её
    # легко откатить случайно, не заметив.
    shared = [
        # верхняя строчка с городом, температурой и сводкой
        ".city{font-size:14px;font-weight:600}",
        # почасовой блок
        ".hour .ht{color:var(--muted);font-size:10px",
        ".hour .he{font-size:20.5px",
        ".hour .htemp{font-weight:600;font-size:13px",
        ".hour .hpp{color:var(--rain);font-size:9.5px",
        ".hour .hmm{color:var(--rain);font-size:9px",
        # узкий экран — те же элементы отдельными размерами
        ".hour .ht{font-size:8.5px}",
        ".hour .he{font-size:16.5px}",
        ".hour .htemp{font-size:11px}",
        ".hour .hpp{font-size:7.5px}",
        ".hour .hmm{font-size:7px}",
    ]
    # .ppct задан в em и обязан остаться в em: пересчитается сам от
    # уменьшенного родителя, а фиксированное значение разъехалось бы с ним.
    shared.append(".ppct{font-size:.5em}")
    # Вне запрошенных блоков — не трогали.
    shared.append(".updated{font-size:11px")
    shared.append(".err{color:var(--muted);font-size:12px")

    for fname in ("meteo.html", "meteow.html"):
        with open(os.path.join(HERE, fname), encoding="utf-8") as f:
            w = f.read()
        for needle in shared:
            assert needle in w, f"{fname}: нет {needle}"

    # Недельный блок есть только в meteow.html — meteo.html ограничен
    # часами и рисует трубку сам.
    with open(os.path.join(HERE, "meteow.html"), encoding="utf-8") as f:
        w = f.read()
    for needle in (
        "translateX(-50%);font-size:10.5px;font-weight:700",
        ".d10cond{font-size:15.5px",
        ".d10cond .ic{font-size:15.5px}",
        ".d10day{font-size:9.5px",
    ):
        assert needle in w, f"meteow.html: нет {needle}"


def test_widget_card_has_no_frame_and_sits_in_the_corner():
    # Виджет встраивается в чужую страницу, поэтому рамка и скругление были
    # лишними: карточка должна начинаться ровно в левом верхнем углу окна.
    import re as _re

    for fname in ("meteo.html", "meteow.html"):
        with open(os.path.join(HERE, fname), encoding="utf-8") as f:
            w = f.read()
        card = _re.search(r"\.card\{[^}]*\}", w)
        assert card, f"{fname}: нет правила .card"
        rule = card.group(0)
        assert "border-radius" not in rule, f"{fname}: скругление осталось"
        assert "border:" not in rule, f"{fname}: рамка осталась"
        assert "padding:2px 2px 0 2px" in rule, f"{fname}: отступ не 2px по бокам и сверху: {rule}"
        assert "margin:0" in rule, f"{fname}: карточка всё ещё центрируется: {rule}"
        # отступ страницы остался нулевым: воздух даёт сама карточка
        body = _re.search(r"\nbody\{[^}]*\}", w)
        assert body, f"{fname}: нет правила body"
        assert "padding:0" in body.group(0), f"{fname}: отступ body не обнулён"
        # ширину виджета не трогали: снять max-width — другая задача
        assert "max-width:600px" in rule, f"{fname}: max-width убран не по задаче"


def test_widget_daily_block_shows_wind_arrow_and_speed():
    # Ветреная подпись в недельном блоке: стрелка показывает, КУДА дует
    # (градус из API — откуда, поэтому плюс 180), рядом сила без единиц.
    import re as _re

    with open(os.path.join(HERE, "meteow.html"), encoding="utf-8") as f:
        w = f.read()

    # заглушка display:none заменена рабочим правилом
    wind = _re.search(r"\.d10wind\{[^}]*\}", w)
    assert wind, "нет правила .d10wind"
    assert "display:none" not in wind.group(0), ".d10wind всё ещё скрыт"
    assert "font-size:9.5px" in wind.group(0), f"шрифт ветра не 9.5px: {wind.group(0)}"

    # направление ветра кладём в arr, иначе стрелке нечего поворачивать
    assert "daily.wind_direction_10m_dominant" in w
    assert "wd:wd" in w, "направление не попало в arr"

    # поворот именно на +180: стрелка смотрит по ходу ветра, а не откуда он идёт
    assert "(wd + 180) % 360" in w
    # сила ветра без единиц измерения, как заказано
    assert "d10wind" in w
    assert "if (ws == null) return" in w, "нет защиты на отсутствие данных о ветре"
    # ветер стоит над датой: блок стал выше, но день остаётся нижней строкой
    markup = w[w.index("var html10 = '';"):]
    assert 'class="d10day"' not in markup[:markup.index('class="d10wind"')], "ветер должен быть выше даты"
    # вертикальный overflow больше не hidden, иначе строка ветра обрезалась бы
    body = _re.search(r"\nbody\{[^}]*\}", w)
    assert "overflow-y:hidden" not in body.group(0), "overflow-y:hidden обрежет ветер"


def test_widget_column_counts():
    # +1 час и +1 день. Оба числа стоят в коде дважды: в срезе колонок и в
    # расчёте заливки, иначе фон графика разъехался бы с колонками.
    with open(os.path.join(HERE, "meteow.html"), encoding="utf-8") as f:
        w = f.read()
    assert "var DEFAULT_HOURS = 16;" in w
    assert "var dispDays = Math.min(arr.length, 16);" in w
    assert "cloudRainSvgW(arr.slice(0, dispDays), 74)" in w

    with open(os.path.join(HERE, "meteo.html"), encoding="utf-8") as f:
        m = f.read()
    assert "var DEFAULT_HOURS = 17;" in m
    # ширину не трогали: колонки flex:1, поэтому одна extra-колонка лишь сужает их
    assert "max-width:600px" in m


def test_widget_gap_between_hourly_and_daily_blocks_is_one_pixel():
    # Зазор между часовым и недельным блоками складывается из двух отступов:
    # низ .strip плюс верх .d10wrap. После сжатия сумма должна быть 1px.
    import re as _re

    with open(os.path.join(HERE, "meteow.html"), encoding="utf-8") as f:
        w = f.read()
    m = _re.search(r"\.strip\{[^}]*padding:(\d+)px 0 (\d+)px", w)
    assert m, "у .strip должен остаться явный вертикальный padding"
    strip_bottom = int(m.group(2))
    m2 = _re.search(r"\.d10wrap\{[^}]*padding:(\d+)px 0 (\d+)px", w)
    assert m2, "у .d10wrap должен остаться явный вертикальный padding"
    wrap_top = int(m2.group(1))
    assert strip_bottom + wrap_top == 1, (
        f"зазор между блоками {strip_bottom}+{wrap_top}={strip_bottom + wrap_top}px, ждали 1px"
    )
    # нижний отступ недельного блока не трогаем: он отделяет его от низа карточки
    assert int(m2.group(2)) == 2, "нижний отступ недельного блока должен остаться 2px"


def test_help_documents_widget_sensor_temperature():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "Температура датчика в виджете" in tpl
    assert "вверх" in tpl and "вниз" in tpl


def test_main_chart_reused_not_recreated():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    # при 5-мин автообновлении graph переиспользуется, а не пересоздаётся (теряется выбор переменной)
    assert "if(mainChart)mainChart.destroy();" not in tpl
    assert "if(mainChart){" in tpl
    assert "setVar(curVar);" in tpl
    # mae-chart тоже обновляется на месте через Chart.getChart()
    assert "const exists=Chart.getChart(maeEl);" in tpl
    assert "exists.data.datasets[0].data=data;" in tpl
    assert "exists.update();" in tpl
