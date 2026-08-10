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
    assert "window.L=e" in radar
    assert "var LUT=" in radar
    assert "var RV=" in radar
    assert "var RR=" in radar
    assert "tilecache.rainviewer.com" in radar
    assert "basemaps.cartocdn.com" in radar
    assert "api.rainviewer.com/public/weather-maps.json" in radar
    assert "maxNativeZoom:7" in radar
    assert "while(c>0&&frames[c].future){c--;}" in radar


def test_radar_uses_light_rainradar_theme():
    with open(os.path.join(HERE, "radar.html"), encoding="utf-8") as f:
        radar = f.read()
    assert "light_all" in radar
    assert "dark_all" not in radar
    assert "#acacac" in radar
    assert "grayscale(1) brightness(0.72)" in radar
    assert "#415fad" in radar
    assert "linear-gradient(to right,#8889bd,#595a95,#454696,#36b343,#81c81e,#c2d11e,#ffd000,#f29b17,#e1782e,#d23a4b,#b3107c,#b80db2)" in radar
    assert "RecolorLayer" in radar


def test_radar_palette_has_12_rainradar_colors():
    with open(os.path.join(HERE, "tools", "palette.js"), encoding="utf-8") as f:
        pal = f.read()
    assert "var LUT=" in pal
    assert "var RV=" in pal
    assert "var RR=" in pal
    rr = pal.split("var RR=")[1].split(";")[0]
    assert rr.count("[") == rr.count("]")
    assert rr.count("],") == 11
    assert "184,13,178" in rr
