import meteo


def _series(a, b, c, var="temperature_2m"):
    data = {}
    for code, vals in (("a", a), ("b", b), ("c", c)):
        data[code] = {"time": ["h0", "h1"], "data": {var: vals}}
    return data


def test_assemble_weighted_and_mean():
    hb = _series([0.0, 10.0], [10.0, 0.0], [5.0, 5.0])
    weights = {"temperature_2m": {"a": 0.5, "b": 0.5, "c": 0.0}}
    out = meteo.assemble_consensus(
        hb, ["temperature_2m"], weights, min_sources=2
    )
    assert out["time"] == ["h0", "h1"]
    assert abs(out["weighted"]["temperature_2m"][0] - 5.0) < 1e-6
    assert abs(out["mean"]["temperature_2m"][0] - 5.0) < 1e-6
    assert abs(out["median"]["temperature_2m"][0] - 5.0) < 1e-6
    assert out["models"]["a"]["temperature_2m"] == [0.0, 10.0]


def test_assemble_default_min_sources_is_two():
    hb = _series([10.0], [20.0], [None], var="temperature_2m")
    out = meteo.assemble_consensus(
        hb, ["temperature_2m"], {"temperature_2m": {}}
    )
    assert out["weighted"]["temperature_2m"][0] == 15.0


def test_assemble_unweighted_model_gets_min_weight_not_one():
    hb = _series([0.0], [20.0], [20.0], var="temperature_2m")
    weights = {"temperature_2m": {"a": 0.8, "b": 0.2}}
    out = meteo.assemble_consensus(hb, ["temperature_2m"], weights, min_sources=2)
    got = out["weighted"]["temperature_2m"][0]
    expected = (0.0 + 0.2 * 20 + 0.2 * 20) / (0.8 + 0.2 + 0.2)
    assert abs(got - expected) < 1e-6
    assert abs(got - 12.0) > 0.1


def test_assemble_min_sources_threshold():
    hb = _series([1.0], [None], [None], var="temperature_2m")
    out = meteo.assemble_consensus(
        hb, ["temperature_2m"], {"temperature_2m": {}}, min_sources=3
    )
    assert out["weighted"]["temperature_2m"][0] is None
    assert out["mean"]["temperature_2m"][0] is None


def test_assemble_wind_direction_uses_circular_median():
    hb = {
        "a": {"time": ["h0"], "data": {"wind_direction_10m": [350.0]}},
        "b": {"time": ["h0"], "data": {"wind_direction_10m": [10.0]}},
        "c": {"time": ["h0"], "data": {"wind_direction_10m": [0.0]}},
    }
    out = meteo.assemble_consensus(
        hb, ["wind_direction_10m"],
        {"wind_direction_10m": {}}, min_sources=2
    )
    m = out["median"]["wind_direction_10m"][0]
    assert m is not None and (abs(m - 0.0) < 1e-6 or abs(m - 360.0) < 1e-6)


def test_assemble_weather_code_by_majority():
    hb = _series([61, 0], [61, 0], [80, 0], var="weather_code")
    out = meteo.assemble_consensus(
        hb, ["weather_code"], {"weather_code": {}}, min_sources=2
    )
    assert out["weighted"]["weather_code"][0] == 61
    assert out["weighted"]["weather_code"][1] == 0


def test_assemble_precipitation_floored_to_tenths():
    hb = {
        "a": {"time": ["h0"], "data": {"precipitation": [0.2]}},
        "b": {"time": ["h0"], "data": {"precipitation": [0.2]}},
        "c": {"time": ["h0"], "data": {"precipitation": [0.1]}},
        "d": {"time": ["h0"], "data": {"precipitation": [0.1]}},
        "e": {"time": ["h0"], "data": {"precipitation": [0.2]}},
    }
    out = meteo.assemble_consensus(
        hb, ["precipitation"], {"precipitation": {}}, min_sources=2
    )
    assert out["weighted"]["precipitation"][0] == 0.1  # 0.16, не 0.2
    assert out["mean"]["precipitation"][0] == 0.1
    assert out["median"]["precipitation"][0] == 0.2


def test_assemble_precipitation_below_tenth_floors_to_zero():
    hb = {
        "a": {"time": ["h0"], "data": {"precipitation": [0.1]}},
        "b": {"time": ["h0"], "data": {"precipitation": [0.0]}},
        "c": {"time": ["h0"], "data": {"precipitation": [0.0]}},
    }
    out = meteo.assemble_consensus(
        hb, ["precipitation"], {"precipitation": {}}, min_sources=2
    )
    assert out["weighted"]["precipitation"][0] == 0.0  # 0.033, а не 0.04
    assert out["mean"]["precipitation"][0] == 0.0
    assert out["median"]["precipitation"][0] == 0.0


def test_assemble_cape_consensus():
    hb = _series([0.0, 1500.0], [10.0, 1800.0], [5.0, 1200.0], var="cape")
    out = meteo.assemble_consensus(
        hb, ["cape"], {"cape": {}}, min_sources=2
    )
    assert out["weighted"]["cape"][0] == 5.0
    assert out["mean"]["cape"][0] == 5.0
    assert out["median"]["cape"][0] == 5.0


def test_assemble_cape_respects_min_sources():
    hb = _series([1200.0], [None], [None], var="cape")
    out = meteo.assemble_consensus(
        hb, ["cape"], {"cape": {}}, min_sources=3
    )
    assert out["weighted"]["cape"][0] is None
