import json

import mqtt_publish as m


def _make_data():
    from datetime import datetime, timedelta

    start = datetime(2026, 8, 5, 0, 0)
    n = 48
    times = [(start + timedelta(hours=i)).strftime("%Y-%m-%dT%H:00") for i in range(n)]

    temps = [20.0 + (i % 24) * 0.5 for i in range(n)]
    temps[11] = 23.4
    temps[15] = 24.0
    temps[23] = 17.0
    apparent = [t - 0.3 for t in temps]
    apparent[11] = 23.1

    precip = [0.0] * n
    precip[14] = 0.1
    precip[34] = 0.4
    precip[38] = 1.1

    prob = [0] * n
    prob[14] = 32
    prob[34] = 11
    prob[38] = 59

    wc = [0] * n
    wc[14] = 61

    wind = [3.0] * n
    wind[11] = 3.2
    wdir = [270.0] * n
    wdir[11] = 315.0
    pres = [750.0] * n
    pres[11] = 753.0
    hum = [60] * n
    hum[11] = 45

    uk = [0] * n
    uk[14] = 61
    uk[34] = 95
    dwd = [0] * n
    dwd[14] = 61
    dwd[38] = 96

    return {
        "model_codes": ["uk", "dwd"],
        "model_names": {"uk": "UKMO Global", "dwd": "DWD ICON"},
        "time": times,
        "weighted": {
            "temperature_2m": temps,
            "apparent_temperature": apparent,
            "precipitation": precip,
            "precipitation_probability": prob,
            "weather_code": wc,
            "wind_speed_10m": wind,
            "wind_direction_10m": wdir,
            "pressure_msl": pres,
            "relative_humidity_2m": hum,
        },
        "models": {
            "uk": {"weather_code": uk},
            "dwd": {"weather_code": dwd},
        },
    }


def test_fmt():
    assert m.fmt(23.5) == 23.5
    assert m.fmt(23.44) == 23.4
    assert m.fmt(0.05) == 0.1
    assert m.fmt(None) is None


def test_num():
    assert m.num(45.6) == 46
    assert m.num(753.0) == 753
    assert m.num(None) is None


def test_weather_text():
    assert m.weather_text(0) == "Ясно"
    assert m.weather_text(61) == "Небольшой дождь"
    assert m.weather_text(96) == "Гроза с градом"
    assert m.weather_text(999) == "—"


def test_rumb_short():
    assert m.rumb_short(315) == "СЗ"
    assert m.rumb_short(None) == "—"


def test_parse_payload():
    html = '<html><script id="data" type="application/json">{"time":["2026-08-05T12:00"]}</script></html>'
    assert m.parse_payload(html) == {"time": ["2026-08-05T12:00"]}


def test_parse_payload_bad_html():
    assert m.parse_payload("<html>no data</html>") is None
    assert m.parse_payload('<script id="data" type="application/json">not json</script>') is None


def test_cur_idx():
    d = _make_data()
    assert m.cur_idx(d, "2026-08-05T11:00") == 11
    assert m.cur_idx(d, "2099-01-01T00:00") == 0


def test_build_now():
    d = _make_data()
    doc = m.build_now(d, 11, "2026-08-05T12:34:04+03:00")
    assert doc == {
        "temperature": 23.4,
        "feels_like": 23.1,
        "weather": "Ясно",
        "wind_speed": 3.2,
        "wind_dir": "СЗ",
        "pressure": 753,
        "humidity": 45,
        "updated_at": "2026-08-05T12:34:04+03:00",
    }


def test_build_horizon():
    d = _make_data()
    doc = m.build_horizon(d, 11, 3, "2026-08-05T12:34:04+03:00")
    assert doc["horizon_h"] == 3
    assert doc["time"] == "2026-08-05T14:00+03:00"
    assert doc["temperature"] == 27.0
    assert doc["weather"] == "Небольшой дождь"
    assert doc["precip_mm"] == 0.1
    assert doc["precip_prob"] == 32


def test_build_horizon_out_of_range():
    d = _make_data()
    small = {"time": d["time"][:20]}
    assert m.build_horizon(small, 11, 12, "x") == {"horizon_h": 12}


def test_build_rain():
    d = _make_data()
    doc = m.build_rain(d, 11)
    assert doc["rain"] == {
        "time": "2026-08-05T14:00+03:00",
        "precip_mm": 0.1,
        "probability": 32,
        "models": 2,
    }
    assert doc["thunder"] == {
        "time": "2026-08-06T10:00+03:00",
        "precip_mm": 0.4,
        "probability": 11,
        "sources": ["UKMO Global"],
    }
    assert doc["hail"] == {
        "time": "2026-08-06T14:00+03:00",
        "precip_mm": 1.1,
        "probability": 59,
        "sources": ["DWD ICON"],
    }


def test_build_rain_none():
    d = _make_data()
    d["weighted"]["weather_code"] = [0] * len(d["time"])
    for c in ("uk", "dwd"):
        d["models"][c]["weather_code"] = [0] * len(d["time"])
    doc = m.build_rain(d, 11)
    assert doc == {"rain": None, "thunder": None, "hail": None}


def test_build_all_uses_cur_idx():
    d = _make_data()
    docs = m.build_all(d, now_hour="2026-08-05T11:00", updated_at="2026-08-05T12:34:04+03:00")
    assert list(docs) == ["now", "3", "6", "12", "rain"]
    assert docs["now"]["temperature"] == 23.4
    assert docs["3"]["horizon_h"] == 3
    assert docs["6"]["horizon_h"] == 6
    assert docs["12"]["horizon_h"] == 12
    assert docs["rain"]["rain"]["models"] == 2


def test_topic_for():
    assert m.topic_for("city/out/pogoda", "now") == "city/out/pogoda/now"
    assert m.topic_for("city/out/pogoda", "3") == "city/out/pogoda/3"
