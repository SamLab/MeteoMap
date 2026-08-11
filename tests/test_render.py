import os

import meteo

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_tabs_forecast_after_compare():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    tabs = [t.split('data-tab="')[1].split('"')[0]
            for t in tpl.split('class="tabs"')[1].split('</div>')[0].split('\n')
            if 'data-tab="' in t]
    assert tabs.index("forecast") > tabs.index("compare")
    assert tabs.index("radar") < tabs.index("compare")


def _payload():
    hourly = {
        "a": {"time": ["h0"], "data": {"temperature_2m": [1.0]}},
        "b": {"time": ["h0"], "data": {"temperature_2m": [3.0]}},
    }
    consensus = meteo.assemble_consensus(
        hourly, ["temperature_2m"],
        {"temperature_2m": {"a": 0.5, "b": 0.5}}, min_sources=2
    )
    daily = {
        "a": {"time": ["d0"], "temperature_2m_max": [5.0],
              "precipitation_probability_max": [10.0],
              "sunrise": ["2026-08-03T04:19:00"],
              "sunset": ["2026-08-03T20:33:00"],
              "cloud_cover_mean": [40.0],
              "relative_humidity_2m_mean": [70.0]},
        "b": {"time": ["d0"], "temperature_2m_max": [7.0],
              "precipitation_probability_max": [30.0],
              "sunrise": ["2026-08-03T04:20:00"],
              "sunset": ["2026-08-03T20:34:00"],
              "cloud_cover_mean": [50.0],
              "relative_humidity_2m_mean": [80.0]},
    }
    verification = {
        "7d": {"a": {"temperature_2m": 1.0}, "b": {"temperature_2m": 2.0}},
        "30d": {},
    }
    return meteo.build_payload(
        ["a", "b"], {"a": "Model A", "b": "Model B"},
        hourly, daily, consensus, verification, "2026-08-03T12:00:00+03:00",
        meteo.LOCATIONS[0],
    )


def test_payload_contains_key_sections():
    p = _payload()
    assert p["location"]["name"] == "Ярославль"
    assert p["generated_at"].startswith("2026-08-03")
    assert p["model_names"]["a"] == "Model A"
    assert p["time"] == ["h0"]
    assert p["weighted"]["temperature_2m"] == [2.0]
    assert p["mean"]["temperature_2m"] == [2.0]
    assert p["median"]["temperature_2m"] == [2.0]
    assert p["models"]["a"]["temperature_2m"] == [1.0]
    assert p["daily"]["temperature_2m_max"] == [6.0]
    assert p["verification"]["7d"]["a"]["temperature_2m"] == 1.0


def test_render_replaces_placeholders_and_keeps_attribution():
    template = (
        "<title>__CITY__</title><span id='generated'>__GENERATED_AT__</span>"
        "<script id='data' type='application/json'>__DATA__</script>"
    )
    html = meteo.render(template, _payload())
    assert "Ярославль" in html
    assert "2026-08-03T12:00:00+03:00" in html
    assert '"temperature_2m"' in html
    assert "</script>" not in html.replace(
        "<script id='data' type='application/json'>", ""
    ).split("</script>")[0]


def test_render_attribution_link(tmp_path):
    template = (
        "<script id='data' type='application/json'>__DATA__</script>"
        "__ATTRIBUTION__"
    )
    # render() adds attribution; verify it appears
    html = meteo.render(template, _payload())
    assert "open-meteo.com" in html


def test_moscow_now_iso_has_utc3_offset():
    import re

    value = meteo.moscow_now_iso()
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+03:00", value)


def test_daily_contains_new_variables():
    p = _payload()
    assert p["daily"]["precipitation_probability_max"] == [20.0]
    assert p["daily"]["sunrise"] == ["2026-08-03T04:19:00"]
    assert p["daily"]["sunset"] == ["2026-08-03T20:33:00"]


def test_daily_cloud_cover_mean_is_averaged():
    p = _payload()
    assert p["daily"]["cloud_cover_mean"] == [45.0]


def test_daily_relative_humidity_mean_is_averaged():
    p = _payload()
    assert p["daily"]["relative_humidity_2m_mean"] == [75.0]


def test_daily_string_fields_take_first_model():
    p = _payload()
    # строки берутся из первой модели с данными, а не усредняются
    assert p["daily"]["sunrise"][0] == "2026-08-03T04:19:00"
    assert isinstance(p["daily"]["sunrise"][0], str)


def test_daily_time_passthrough():
    hourly = {"a": {"time": ["h0"], "data": {"temperature_2m": [1.0]}}}
    consensus = {
        "time": ["h0"],
        "weighted": {"temperature_2m": [1.0]},
        "mean": {"temperature_2m": [1.0]},
        "median": {"temperature_2m": [1.0]},
    }
    daily = {"a": {"time": ["2026-08-03", "2026-08-04"], "temperature_2m_max": [5.0, 6.0]}}
    p = meteo.build_payload(
        ["a"], {"a": "A"}, hourly, daily, consensus, {},
        "2026-08-03T12:00:00+03:00", meteo.LOCATIONS[0],
    )
    assert p["daily_time"] == ["2026-08-03", "2026-08-04"]
    assert p["daily"]["temperature_2m_max"] == [5.0, 6.0]


def test_payload_hides_models_without_data():
    hourly = {
        "a": {"time": ["h0"], "data": {"temperature_2m": [1.0]}},
        "b": {"time": ["h0"], "data": {"temperature_2m": [None]}},
        "c": {"time": ["h0"], "data": {"temperature_2m": [None], "wind_speed_10m": [5.0]}},
    }
    consensus = {
        "time": ["h0"],
        "weighted": {"temperature_2m": [1.0]},
        "mean": {"temperature_2m": [1.0]},
        "median": {"temperature_2m": [1.0]},
    }
    p = meteo.build_payload(
        ["a", "b", "c"], {"a": "A", "b": "B", "c": "C"},
        hourly, {}, consensus, {}, "2026-08-03T12:00:00+03:00", meteo.LOCATIONS[0],
    )
    assert p["model_codes"] == ["a", "c"]
    assert p["model_names"] == {"a": "A", "c": "C"}
    assert "b" not in p["models"]


def test_payload_keeps_original_codes_when_all_empty():
    hourly = {
        "a": {"time": ["h0"], "data": {"temperature_2m": [None]}},
    }
    consensus = {
        "time": ["h0"],
        "weighted": {"temperature_2m": [None]},
        "mean": {"temperature_2m": [None]},
        "median": {"temperature_2m": [None]},
    }
    p = meteo.build_payload(
        ["a"], {"a": "A"}, hourly, {}, consensus, {}, "2026-08-03T12:00:00+03:00",
        meteo.LOCATIONS[0],
    )
    assert p["model_codes"] == ["a"]
