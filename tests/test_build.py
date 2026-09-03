import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(HERE, "tools")
BUILD = os.path.join(TOOLS, "build_radar.py")
NOWCAST_TEMPLATE = os.path.join(HERE, "nowcast_template.html")


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
