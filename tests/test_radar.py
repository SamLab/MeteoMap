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
    assert "window.L=e" in radar
    assert "tilecache.rainviewer.com" in radar
    assert "basemaps.cartocdn.com" in radar
    assert "api.rainviewer.com/public/weather-maps.json" in radar
    assert "/256/{z}/{x}/{y}/2/1_1.png" in radar
