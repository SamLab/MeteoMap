import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _tpl():
    with open(os.path.join(HERE, "radar_template.html"), encoding="utf-8") as f:
        return f.read()


def test_radar_has_station_toggle_button():
    tpl = _tpl()
    assert 'id="stoggle"' in tpl
    assert "Датчики" in tpl
    assert "#stoggle" in tpl
    assert "#stoggle.on" in tpl


def test_station_layer_uses_own_pane_above_precipitation():
    tpl = _tpl()
    assert "createPane('stations')" in tpl
    # base tiles carry zIndex:998, labels 900; stations must sit above them
    assert ".leaflet-stations-pane{z-index:1005}" in tpl.replace(" ", "")
    assert "pane:'stations'" in tpl


def test_station_pane_css_comes_after_leaflet_css():
    # Leaflet ships `.leaflet-pane{z-index:400}` at the same specificity, so a
    # station rule placed before the injection would silently lose.
    tpl = _tpl()
    assert tpl.index("/*__LEAFLET_CSS__*/") < tpl.index(".leaflet-stations-pane")


def test_station_markers_are_circle_markers():
    tpl = _tpl()
    assert "L.circleMarker" in tpl


def test_station_layer_fetches_snapshot_with_cache_busting():
    tpl = _tpl()
    assert "sensors.json" in tpl
    assert "Date.now()" in tpl
    assert "fetch(" in tpl


def test_station_layer_refreshes_every_15_minutes():
    tpl = _tpl()
    assert "15*60*1000" in tpl


def test_station_markers_show_online_and_offline_colours():
    tpl = _tpl()
    assert "#36b343" in tpl
    assert "#9a9a9a" in tpl


def test_station_popup_shows_age_and_values():
    tpl = _tpl()
    assert "bindPopup" in tpl
    assert "обновлено" in tpl
    assert "нет данных" in tpl


def test_station_layer_fails_silently_when_snapshot_missing():
    tpl = _tpl()
    assert ".catch(function(){})" in tpl or ".catch(function(){})" in tpl.replace(" ", "")


def test_station_marker_radius_scales_with_zoom():
    tpl = _tpl()
    assert "getZoom()" in tpl
    assert "radius:" in tpl


def test_station_temperature_label_has_shadow():
    tpl = _tpl()
    assert ".stlabel" in tpl
    assert "text-shadow" in tpl


def test_numbered_sensors_get_distinct_labels():
    # Several stations report t1/t2/t3; showing three rows all captioned "T"
    # makes them indistinguishable in the popup.
    tpl = _tpl()
    assert "t1:'T1'" in tpl
    assert "t2:'T2'" in tpl
    assert "t3:'T3'" in tpl


def test_indoor_and_outdoor_sensors_get_distinct_labels():
    tpl = _tpl()
    assert "t_in:'T внутри'" in tpl
    assert "t_out:'T снаружи'" in tpl


def _deploy_yml():
    with open(os.path.join(HERE, ".github", "workflows", "deploy.yml"),
              encoding="utf-8") as f:
        return f.read()


def test_deploy_copies_snapshot_into_site():
    # deploy.yml copies an explicit file list into _site/; anything missing
    # there never reaches GitHub Pages.
    yml = _deploy_yml()
    assert "sensors.json _site/" in yml


def test_deploy_tolerates_absent_snapshot():
    yml = _deploy_yml()
    assert "-f sensors.json" in yml
    assert "||" in yml, 'missing snapshot must not fail the deploy'
