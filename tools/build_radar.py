#!/usr/bin/env python3
"""Собирает radar.html: инлайнит Leaflet 1.6.0 из tools/leaflet.js."""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LEAFLET = os.path.join(ROOT, "tools", "leaflet.js")
PALETTE = os.path.join(ROOT, "tools", "palette.js")
TEMPLATE = os.path.join(ROOT, "radar_template.html")
OUT = os.path.join(ROOT, "radar.html")


def build():
    for name, path, marker in (
        ("leaflet", LEAFLET, "/*__LEAFLET__*/"),
        ("palette", PALETTE, "/*__PALETTE__*/"),
    ):
        if not os.path.isfile(path):
            sys.exit(f"error: {name} not found: {path}")
    with open(LEAFLET, encoding="utf-8", errors="replace") as f:
        leaflet = f.read()
    with open(PALETTE, encoding="utf-8", errors="replace") as f:
        palette = f.read()
    with open(TEMPLATE, encoding="utf-8") as f:
        template = f.read()
    for marker in ("/*__LEAFLET__*/", "/*__PALETTE__*/"):
        assert marker in template, f"placeholder missing in template: {marker}"
    html = template.replace("/*__LEAFLET__*/", leaflet)
    html = html.replace("/*__PALETTE__*/", palette)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[ok] radar.html written ({os.path.getsize(OUT)} bytes)")


if __name__ == "__main__":
    build()
