import pytest
from tools import nowcast

CAP = (
    '<WMT_MS_Capabilities>'
    '<Service><Name><![CDATA[WMS]]></Name></Service>'
    '<Capability><Layer><Title>R</Title>'
    '<Layer queryable="1"><Dimension name="time" units="ISO8601" current="1"/>'
    '<Extent name="time" default="2026-09-03T09:30:00.000Z">'
    '2026-09-03T09:30:00.000Z,2026-09-03T09:40:00.000Z,2026-09-03T09:50:00.000Z'
    '</Extent><Layer queryable="1"><Name>1</Name></Layer></Layer></Layer>'
    '</Capability></WMT_MS_Capabilities>'
)


def test_parse_capabilities_times_extracts_ordered_utc():
    times = nowcast.parse_capabilities_times(CAP)
    assert times == [
        "2026-09-03T09:30:00.000Z",
        "2026-09-03T09:40:00.000Z",
        "2026-09-03T09:50:00.000Z",
    ]


def test_parse_capabilities_times_empty_when_no_extent():
    assert nowcast.parse_capabilities_times("<WMT_MS_Capabilities></WMT_MS_Capabilities>") == []


def test_tile_path_concatenates_z0x0y():
    assert nowcast.tile_path(6, 39, 19) == "6039019"
    assert nowcast.tile_path(9, 312, 155) == "903120155"


def test_tile_url_builds_known_good():
    url = nowcast.tile_url(6, 39, 19, "2026-09-03T10:00:00.000Z")
    assert url == (
        "https://meteoinfo.ru/res/nowcast/6039019/ncgi.php"
        "?tnz=6&tnx=39&tny=19&inidt=2026-09-03T10%3A00%3A00.000Z"
    )


def test_gibs_constants():
    assert "earthdata.nasa.gov" in nowcast.GIBS_BASE
    assert nowcast.GIBS_PRODUCT == "MODIS_Terra_CorrectedReflectance_TrueColor"
    assert nowcast.GIBS_MATRIX == "GoogleMapsCompatible_Level9"


def test_gibs_tile_url_builds_known_good():
    url = nowcast.gibs_tile_url(35, 22, "2026-09-03")
    assert url == (
        "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/"
        "MODIS_Terra_CorrectedReflectance_TrueColor/default/2026-09-03/"
        "GoogleMapsCompatible_Level9/9/22/35.jpg"
    )
