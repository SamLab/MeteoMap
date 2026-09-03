#!/usr/bin/env python3
"""Собирает radar.html и nowcast.html: инлайнит Leaflet 1.6.0, CSS и палитру
из tools/ в HTML-шаблоны (radar_template.html, nowcast_template.html)."""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LEAFLET = os.path.join(ROOT, "tools", "leaflet.js")
LEAFLET_CSS = os.path.join(ROOT, "tools", "leaflet.css")
PALETTE = os.path.join(ROOT, "tools", "palette.js")

TARGETS = {
    "radar": (os.path.join(ROOT, "radar_template.html"),
              os.path.join(ROOT, "radar.html")),
    "nowcast": (os.path.join(ROOT, "nowcast_template.html"),
                os.path.join(ROOT, "nowcast.html")),
}

MARKERS = ("/*__LEAFLET__*/", "/*__LEAFLET_CSS__*/", "/*__PALETTE__*/")


def _read(p):
    with open(p, encoding="utf-8", errors="replace") as f:
        return f.read()


def _read_strict(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def build(name=None):
    if name is not None and name not in TARGETS:
        sys.exit(f"error: unknown target: {name} (choose from {', '.join(TARGETS)})")
    for p in (LEAFLET, LEAFLET_CSS, PALETTE):
        if not os.path.isfile(p):
            sys.exit(f"error: missing {p}")
    assets = {
        "/*__LEAFLET__*/": _read(LEAFLET),
        "/*__LEAFLET_CSS__*/": _read(LEAFLET_CSS),
        "/*__PALETTE__*/": _read(PALETTE),
    }
    targets = {name: TARGETS[name]} if name else TARGETS
    for n, (tpl, out) in targets.items():
        if not os.path.isfile(tpl):
            sys.exit(f"error: template not found: {tpl}")
        template = _read_strict(tpl)
        for marker in MARKERS:
            assert marker in template, f"placeholder missing in {tpl}: {marker}"
        html = template
        for marker, content in assets.items():
            html = html.replace(marker, content)
        with open(out, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[ok] {out} written ({os.path.getsize(out)} bytes)")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        build(sys.argv[1])
    else:
        build()
