"""Closed-loop generation test: runs the real meteo.py pipeline (fetch-mocked)
from template.html to a written index.html and sanity-checks rendered blocks.

This catches real-pipeline bugs (missing braces, missing variables, value
mismatches) that substring-only assertions cannot, without hitting the network.
"""

import os
import re
import tempfile
from datetime import datetime, timedelta

import meteo
from meteo import HOURLY_VARIABLES, LOCATIONS, FORECAST_DAYS

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TZ = meteo.timezone(meteo.timedelta(hours=3))


def _hour_grid(start, hours):
    out = []
    t = start
    for _ in range(hours):
        out.append(t.strftime("%Y-%m-%dT%H:00"))
        t += meteo.timedelta(hours=1)
    return out


def _series(hours, start=5.0, step=0.1):
    return [start + i * step for i in range(hours)]


def _fake_resp(time_arr, temp_arr=None, **extra):
    n = len(time_arr)
    hourly = {
        "time": time_arr,
        "temperature_2m": temp_arr or _series(n),
        "temperature_2m_max": _series(n),
        "temperature_2m_min": _series(n),
        "precipitation_sum": [0.0] * n,
    }
    for v in HOURLY_VARIABLES:
        hourly.setdefault(v, [0.0] * n)
    return {"hourly": hourly, "daily": {
        "time": time_arr[:FORECAST_DAYS],
        "temperature_2m_max": _series(FORECAST_DAYS, 15.0, 1.0),
        "temperature_2m_min": _series(FORECAST_DAYS, 5.0, 0.5),
    }}


def _make_payload():
    grid = _hour_grid(datetime(2026, 9, 9, 0, 0), FORECAST_DAYS * 24)
    raw = {}
    for code, _name, _endpoint in meteo.FORECAST_MODELS:
        raw[code] = [_fake_resp(grid)]
    gen = "2026-09-09T07:00:00+03:00"
    hist_grid = _hour_grid(datetime(2026, 8, 10, 0, 0), 30 * 24)
    hist_resp = _fake_resp(hist_grid)

    orig_hist, orig_arch = meteo._city_hist, meteo._city_arch

    def fake_hist(loc):
        def f(code, start, end, variables):
            return hist_resp
        return f

    def fake_arch(loc):
        def f(start, end, variables):
            return hist_resp
        return f

    meteo._city_hist, meteo._city_arch = fake_hist, fake_arch
    try:
        payload = meteo.build_city_payload(
            LOCATIONS[0], raw, {}, gen, external_enabled=False,
        )
    finally:
        meteo._city_hist, meteo._city_arch = orig_hist, orig_arch
    if payload is None:
        raise AssertionError("build_city_payload returned None")
    return payload


def _render_to_file(payload):
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        template = f.read()
    html = meteo.render(template, payload)
    tmp = tempfile.NamedTemporaryFile("w", suffix=".html", delete=False,
                                      encoding="utf-8")
    try:
        tmp.write(html)
    finally:
        tmp.close()
    return tmp.name, html


def test_generation_index_render_and_sanity():
    payload = _make_payload()
    path, html = _render_to_file(payload)

    # инлайн-данные проставлены
    assert "__DATA__" not in html
    assert payload["generated_at"] in html

    # ключевые блоки страницы на месте
    for needle in ("weather-hours", "hourstitle", "Предупреждения",
                   "Осадков в ближайшие дни не ожидается",
                   "Заморозков в ближайшие дни не ожидается"):
        assert needle in html, needle

    # сгенерированный HTML не должен содержать незакрытых скобок в JS
    m = re.search(r"<script>(.*?)</script>", html, re.S)
    assert m, "no inline script found"
    body = m.group(1)
    assert body.count("{") == body.count("}"), "unbalanced braces in JS"
    assert body.count("(") == body.count(")"), "unbalanced parens in JS"

    os.unlink(path)


def test_generation_files_written():
    payload = _make_payload()
    path, _html = _render_to_file(payload)
    outdir = tempfile.mkdtemp()
    tmp_index = os.path.join(outdir, "index.html")
    try:
        for slug, p in {LOCATIONS[0]["slug"]: payload}.items():
            with open(os.path.join(outdir, f"{slug}.json"), "w",
                      encoding="utf-8") as f:
                import json
                f.write(meteo.json.dumps(p, ensure_ascii=False))
        meteo.write_index(_html, tmp_index)
        assert os.path.exists(tmp_index)
        with open(tmp_index, encoding="utf-8") as f:
            again = f.read()
        assert payload["generated_at"] in again
    finally:
        import shutil
        shutil.rmtree(outdir, ignore_errors=True)
        os.unlink(path)
