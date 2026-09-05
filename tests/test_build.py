import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(HERE, "tools")
BUILD = os.path.join(TOOLS, "build_radar.py")
NOWCAST_TEMPLATE = os.path.join(HERE, "nowcast_template.html")
NOWCAST_OUTPUT = os.path.join(HERE, "nowcast.html")


def test_nowcast_template_has_required_placeholders():
    with open(NOWCAST_TEMPLATE, encoding="utf-8") as f:
        s = f.read()
    for m in ("/*__LEAFLET__*/", "/*__LEAFLET_CSS__*/", "/*__PALETTE__*/"):
        assert m in s


def test_build_script_defines_nowcast_output():
    with open(BUILD, encoding="utf-8") as f:
        s = f.read()
    assert "nowcast_template.html" in s
    assert "nowcast.html" in s


def test_builder_produces_nowcast_html():
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    from tools import build_radar

    build_radar.build("nowcast")
    assert os.path.isfile(NOWCAST_OUTPUT), "nowcast.html not written"
    with open(NOWCAST_OUTPUT, encoding="utf-8") as f:
        html = f.read()
    assert "satellite-europe" in html
    assert "imn-rust-lb.infoplaza.io" in html
    for marker in ("/*__LEAFLET__*/", "/*__LEAFLET_CSS__*/", "/*__PALETTE__*/"):
        assert marker not in html, f"leftover placeholder {marker} in nowcast.html"


def test_nowcast_template_has_gibs_cloud_layer():
    with open(NOWCAST_TEMPLATE, encoding="utf-8") as f:
        s = f.read()
    assert "gibsLayer" in s
    assert "earthdata.nasa.gov" in s
    assert "maxNativeZoom" in s


def test_nowcast_template_cloud_shown_in_msk():
    with open(NOWCAST_TEMPLATE, encoding="utf-8") as f:
        s = f.read()
    assert "sat24Label" in s
    assert 'id="sattime"' in s
    assert "elSatTime" in s


def test_nowcast_template_has_default_zoom():
    with open(NOWCAST_TEMPLATE, encoding="utf-8") as f:
        s = f.read()
    assert "zoom||'3'" in s or "zoom||3" in s or "parseInt(params.get('zoom')||'3'" in s


def test_nowcast_template_has_no_nowcast():
    with open(NOWCAST_TEMPLATE, encoding="utf-8") as f:
        s = f.read()
    # Наукастинг ГМЦ и радарная полоса/легенда/кнопка удалены
    for m in ("ncgi.php", "/res/nowcast/", "parseTimes", "CAP_URL", "tileURL",
              'id="segs"', 'id="play"', 'id="legend"', 'id="ctoggle"',
              "renderSegs", "showFrame", "NowcastLayer", "MAX_TILE_ATTEMPTS"):
        assert m not in s, f"запрещённый маркер присутствует: {m}"


def test_nowcast_template_cloud_always_shown():
    with open(NOWCAST_TEMPLATE, encoding="utf-8") as f:
        s = f.read()
    # Облачность включается сразу и без кнопки-переключателя
    assert "loadCloud()" in s
    assert "sat24Layer" in s
    assert 'id="sattimeline"' in s
    assert 'id="ctoggle"' not in s
    assert "cloudOn" not in s


def test_nowcast_template_has_sat24_cloud_layer():
    with open(NOWCAST_TEMPLATE, encoding="utf-8") as f:
        s = f.read()
    # Живой слой облачности Sat24 (Infoplaza tile CDN, кадры раз в 15 мин)
    assert "satellite-europe" in s
    assert "imn-rust-lb.infoplaza.io" in s
    assert "SAT24_BASE" in s
    assert "SAT24_ZOOM=4" in s
    assert "sat24Layer" in s
    assert "L.imageOverlay" in s
    # Автоподбор свежего timestamp (перебор 15-мин шагов)
    assert "pickSat24Time" in s
    # Фолбэк на NASA GIBS при недоступности Sat24
    assert "sat24Fallback" in s


def test_builder_produces_sat24_cloud_in_output():
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    from tools import build_radar

    build_radar.build("nowcast")
    with open(NOWCAST_OUTPUT, encoding="utf-8") as f:
        html = f.read()
    assert "satellite-europe" in html
    assert "imn-rust-lb.infoplaza.io" in html
    assert "sat24Layer" in html
    # В собранном файле тоже нет наукастинга/кнопки/полосы радара
    for m in ("ncgi.php", "parseTimes", 'id="ctoggle"', "renderSegs", "showFrame"):
        assert m not in html, f"запрещённый маркер в output: {m}"


def test_nowcast_template_has_sat24_rewind():
    with open(NOWCAST_TEMPLATE, encoding="utf-8") as f:
        s = f.read()
    # Полоса перемотки спутника (история ~6 ч, слайдер + play)
    assert 'id="sattimeline"' in s
    assert 'id="satplay"' in s
    assert 'id="satsegs"' in s
    assert 'id="sattime"' in s
    assert "SAT24_MINUTES_BACK" in s
    assert "buildSatHistory" in s
    assert "renderSatSegs" in s
    assert "showSatFrame" in s
    assert "toggleSatPlay" in s
    assert "satFrames" in s


def test_builder_produces_sat24_rewind_in_output():
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    from tools import build_radar

    build_radar.build("nowcast")
    with open(NOWCAST_OUTPUT, encoding="utf-8") as f:
        html = f.read()
    assert 'id="sattimeline"' in html
    assert 'id="satplay"' in html
    assert 'id="satsegs"' in html
    assert "buildSatHistory" in html
    assert "renderSatSegs" in html
    assert "showSatFrame" in html
    assert "toggleSatPlay" in html
