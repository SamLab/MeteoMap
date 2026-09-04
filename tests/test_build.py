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


def test_nowcast_template_has_tile_retry():
    with open(NOWCAST_TEMPLATE, encoding="utf-8") as f:
        s = f.read()
    assert "MAX_TILE_ATTEMPTS" in s
    assert "TILE_RETRY_MS" in s
    assert "img.onerror" in s
    assert "loadRaw(url,cb,attempt+1)" in s


def test_builder_produces_nowcast_html():
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    from tools import build_radar

    build_radar.build("nowcast")
    assert os.path.isfile(NOWCAST_OUTPUT), "nowcast.html not written"
    with open(NOWCAST_OUTPUT, encoding="utf-8") as f:
        html = f.read()
    assert "function parseTimes" in html
    assert "ncgi.php" in html
    assert "/res/nowcast/" in html
    for marker in ("/*__LEAFLET__*/", "/*__LEAFLET_CSS__*/", "/*__PALETTE__*/"):
        assert marker not in html, f"leftover placeholder {marker} in nowcast.html"


def test_nowcast_template_has_gibs_cloud_layer():
    with open(NOWCAST_TEMPLATE, encoding="utf-8") as f:
        s = f.read()
    assert 'id="ctoggle"' in s
    assert "gibsLayer" in s
    assert "earthdata.nasa.gov" in s
    assert "maxNativeZoom" in s


def test_nowcast_template_has_cloud_timelabel():
    with open(NOWCAST_TEMPLATE, encoding="utf-8") as f:
        s = f.read()
    assert 'id="ctime"' in s
    assert "mskLabel" in s
    assert "MSK · den (Terra)" in s
