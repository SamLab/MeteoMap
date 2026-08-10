#!/usr/bin/env python3
"""Собирает radar.html: инлайнит Leaflet 1.6.0 из tools/leaflet.js."""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LEAFLET = os.path.join(ROOT, "tools", "leaflet.js")
TEMPLATE = os.path.join(ROOT, "radar_template.html")
OUT = os.path.join(ROOT, "radar.html")


def build():
    if not os.path.isfile(LEAFLET):
        sys.exit(f"error: leaflet not found: {LEAFLET}")
    with open(LEAFLET, encoding="utf-8", errors="replace") as f:
        leaflet = f.read()
    with open(TEMPLATE, encoding="utf-8") as f:
        template = f.read()
    assert "/*__LEAFLET__*/" in template, "placeholder missing in template"
    html = template.replace("/*__LEAFLET__*/", leaflet)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[ok] radar.html written ({os.path.getsize(OUT)} bytes)")


if __name__ == "__main__":
    build()
