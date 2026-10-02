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


def _build_city_body():
    with open(os.path.join(HERE, "meteo.py"), encoding="utf-8") as f:
        src = f.read()
    return src.split("def build_city_payload(")[1]


def test_build_city_payload_injects_sensors_before_consensus():
    body = _build_city_body()
    inject = body.index("load_sensor_model(grid)")
    assert inject < body.index("assemble_consensus("), (
        "датчик обязан попасть в hourly_by_model до консенсуса, "
        "иначе он не получит вес и не попадёт в models"
    )
    assert 'if loc["slug"] in SENSOR_LOCATIONS:' in body


def test_sensors_not_added_to_verification():
    body = _build_city_body()
    verify = body.split("verification")[1]
    assert "SENSOR_CODE" not in verify


# --- сквозной тест: датчик реально доезжает до weighted_consensus ---


def _sensor_history_file(tmp_path, grid, value):
    import json
    hist = {"hours": {grid[1]: {
        "samples": 2,
        "stations": {"penaty": {"temperature_2m": [value]},
                     "bereg": {"temperature_2m": [value]}},
    }}}
    p = tmp_path / "sensors_history.json"
    p.write_text(json.dumps(hist), encoding="utf-8")
    return str(p)


def _stub_verification(monkeypatch):
    mae = {code: {v: 1.0 for v in meteo.VERIFICATION_VARIABLES}
           for code, _n, _e in meteo.FORECAST_MODELS}
    monkeypatch.setattr(
        meteo, "verify_windows",
        lambda *a, **k: {"7d": mae, "30d": mae},
    )


def _raw_everywhere(grid, temps):
    """build_city_payload берёт ответы по индексу LOCATIONS, а не по слагу.

    Две модели нужно, чтобы консенсус вообще собрался: у него
    min_sources=2. Одна модель плюс датчик — тоже два источника, но только
    в тестах, где датчик как раз и должен появиться.
    """
    resp = _fake_resp(grid, temp_arr=temps)
    return {
        "ecmwf_ifs025": [resp for _ in LOCATIONS],
        "ncep_gfs_seamless": [resp for _ in LOCATIONS],
    }


def test_sensor_weight_2x_reaches_weighted_consensus_end_to_end(monkeypatch, tmp_path):
    """Вес датчика 2.0 доезжает до weighted_consensus через настоящие
    build_city_payload -> apply_sensor_weights -> assemble_consensus.

    Две модели дают 0.0, у каждой make_weights даёт 1/12 (MAE=1.0 у всех 12
    моделей из FORECAST_MODELS), датчик 20.0 получает 2*1/12 = 1/6. Веса
    [1/12, 1/12, 1/6] в сумме 1/3, ответ (20*1/6)/(1/3) = 10.0.
    При 1.0*среднее датчик получил бы 1/12, сумма весов 1/4, и ответ
    (20*1/12)/(3/12) = 20/3 = 6.667 — расхождение в 3.33 градуса,
    тест не проходит вхолостую.
    """
    grid = _hour_grid(datetime(2026, 9, 28, 9, 0), 3)
    monkeypatch.setattr(meteo, "SENSOR_HISTORY",
                        _sensor_history_file(tmp_path, grid, 20.0))
    _stub_verification(monkeypatch)

    loc = next(l for l in LOCATIONS if l["slug"] == "yaroslavl")
    p = meteo.build_city_payload(
        loc, _raw_everywhere(grid, [0.0, 0.0, 0.0]), {},
        "2026-09-28T12:00:00+03:00", False,
    )

    assert meteo.SENSOR_CODE in p["model_codes"]
    assert p["model_names"][meteo.SENSOR_CODE] == meteo.SENSOR_NAME
    assert p["models"][meteo.SENSOR_CODE]["temperature_2m"] == [None, 20.0, None]
    got = p["weighted"]["temperature_2m"][1]
    assert abs(got - 10.0) < 1e-6, got
    # при 1.0 вместо 2.0 получилось бы 20/3 = 6.667
    assert abs(got - 20.0 / 3.0) > 1.0
    # датчик не выдумывает остальные часы: моделей две, датчика там нет
    assert p["weighted"]["temperature_2m"][0] == 0.0
    assert p["weighted"]["temperature_2m"][2] == 0.0
    # и умышленно не участвует в верификации
    assert meteo.SENSOR_CODE not in p["verification"]["7d"]
    assert meteo.SENSOR_CODE not in p["verification"]["30d"]


def test_sensor_absent_for_other_cities_end_to_end(monkeypatch, tmp_path):
    grid = _hour_grid(datetime(2026, 9, 28, 9, 0), 3)
    monkeypatch.setattr(meteo, "SENSOR_HISTORY",
                        _sensor_history_file(tmp_path, grid, 20.0))
    _stub_verification(monkeypatch)

    for slug in ("batumi", "rybinsk", "moscow"):
        loc = next(l for l in LOCATIONS if l["slug"] == slug)
        p = meteo.build_city_payload(
            loc, _raw_everywhere(grid, [1.0, 1.0, 1.0]), {},
            "2026-09-28T12:00:00+03:00", False,
        )
        assert meteo.SENSOR_CODE not in p["model_codes"], slug
        assert meteo.SENSOR_CODE not in p["models"], slug


def test_build_city_payload_survives_corrupt_sensor_history(monkeypatch, tmp_path):
    """Битая sensors_history.json не должна ронять сборку города."""
    grid = _hour_grid(datetime(2026, 9, 28, 9, 0), 3)
    p_history = tmp_path / "sensors_history.json"
    p_history.write_text("{oops", encoding="utf-8")
    monkeypatch.setattr(meteo, "SENSOR_HISTORY", str(p_history))
    _stub_verification(monkeypatch)

    loc = next(l for l in LOCATIONS if l["slug"] == "yaroslavl")
    p = meteo.build_city_payload(
        loc, _raw_everywhere(grid, [1.0, 1.0, 1.0]), {},
        "2026-09-28T12:00:00+03:00", False,
    )
    assert meteo.SENSOR_CODE not in p["model_codes"]
    assert p["weighted"]["temperature_2m"] == [1.0, 1.0, 1.0]


def test_build_city_payload_survives_hand_edited_sensor_history(monkeypatch, tmp_path):
    """Руками правленый JSON: плохие часы, читаемые выживают."""
    import json
    grid = _hour_grid(datetime(2026, 9, 28, 9, 0), 3)
    hist = {"hours": {
        grid[0]: "not a bucket",
        grid[1]: {"samples": 1, "stations": {
            "a": {"temperature_2m": [None, "oops"]},
            "b": {"temperature_2m": [20.0]},
        }},
        grid[2]: {"samples": 1, "stations": {"a": "broken"}},
    }}
    p_history = tmp_path / "sensors_history.json"
    p_history.write_text(json.dumps(hist), encoding="utf-8")
    monkeypatch.setattr(meteo, "SENSOR_HISTORY", str(p_history))
    _stub_verification(monkeypatch)

    loc = next(l for l in LOCATIONS if l["slug"] == "yaroslavl")
    p = meteo.build_city_payload(
        loc, _raw_everywhere(grid, [0.0, 0.0, 0.0]), {},
        "2026-09-28T12:00:00+03:00", False,
    )
    assert p["models"][meteo.SENSOR_CODE]["temperature_2m"] == [None, 20.0, None]
    assert p["weighted"]["temperature_2m"][1] == 10.0


def test_build_city_payload_skips_sensor_without_history(monkeypatch, tmp_path):
    grid = _hour_grid(datetime(2026, 9, 28, 9, 0), 3)
    monkeypatch.setattr(meteo, "SENSOR_HISTORY", str(tmp_path / "missing.json"))
    _stub_verification(monkeypatch)

    loc = next(l for l in LOCATIONS if l["slug"] == "tsedenevo")
    p = meteo.build_city_payload(
        loc, _raw_everywhere(grid, [1.0, 1.0, 1.0]), {},
        "2026-09-28T12:00:00+03:00", False,
    )
    assert meteo.SENSOR_CODE not in p["model_codes"]
    assert p["weighted"]["temperature_2m"] == [1.0, 1.0, 1.0]


def test_sensor_values_stay_aligned_to_the_grid(tmp_path):
    """Псевдо-модель датчика обязана лежать на той же сетке часов."""
    grid = ["2026-09-28T09:00", "2026-09-28T10:00", "2026-09-28T11:00"]
    model = meteo.load_sensor_model(grid, _sensor_history_file(tmp_path, grid, 20.0))
    assert model["time"] == grid
    for values in model["data"].values():
        assert len(values) == len(grid)


def test_sensor_model_carries_max_across_stations(tmp_path):
    """Минимум и максимум считаются по одному списку станций, а не по замерам.

    Ячейка «Датчики» показывает среднее (1+5+9)/3 = 5, минимум 1 и максимум 9
    в одном и том же часе; второй час без наблюдений остаётся None во всех
    трёх рядах.
    """
    import json
    grid = ["2026-09-28T09:00", "2026-09-28T10:00"]
    hist = {"hours": {grid[0]: {"samples": 3, "stations": {
        "a": {"temperature_2m": [1.0]},
        "b": {"temperature_2m": [5.0]},
        "c": {"temperature_2m": [9.0]},
    }}}}
    path = tmp_path / "sensors_history.json"
    path.write_text(json.dumps(hist), encoding="utf-8")

    model = meteo.load_sensor_model(grid, str(path))
    assert model["data"]["temperature_2m"] == [5.0, None]
    assert model["station_min"]["temperature_2m"] == [1.0, None]
    assert model["station_max"]["temperature_2m"] == [9.0, None]
