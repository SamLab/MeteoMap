import re
from urllib.parse import quote

CAP_URL = "https://meteoinfo.ru/hmc-output/nowcast3/nowcast.php"
TILE_BASE = "https://meteoinfo.ru/res/nowcast/"

_EXTENT_RE = re.compile(r'<Extent name="time"[^>]*>(.*?)</Extent>', re.S)


def parse_capabilities_times(xml):
    """Извлекает список времён кадров (ISO8601 UTC) из WMS-capabilities ГМЦ."""
    m = _EXTENT_RE.search(xml or "")
    if not m:
        return []
    raw = m.group(1).strip()
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]


def tile_path(z, x, y):
    """Путь сегмента тайла: `{z}0{x}0{y}` (конкатенация)."""
    return "{}0{}0{}".format(z, x, y)


def tile_url(z, x, y, inidt):
    """Полный URL тайла. inidt — ISO без URL-кодирования на входе."""
    path = tile_path(z, x, y)
    q = (
        "tnz={}&tnx={}&tny={}&inidt={}".format(z, x, y, quote(inidt, safe=""))
    )
    return TILE_BASE + path + "/ncgi.php?" + q
