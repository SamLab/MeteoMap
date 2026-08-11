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


def test_radar_frame_is_lazy_loaded_on_tab_activation():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    assert "f.dataset.radarSrc=url" in tpl
    assert "tab.classList.contains('active')" in tpl
    assert "b.dataset.tab==='radar'" in tpl
    assert "f.dataset.radarSrc!==f.dataset.loadedSrc" in tpl


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
