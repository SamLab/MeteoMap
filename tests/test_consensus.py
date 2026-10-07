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


def test_sensor_source_flows_through_assemble_consensus():
    hb = {
        "a": {"time": ["h0", "h1"], "data": {"temperature_2m": [0.0, 10.0]}},
        "b": {"time": ["h0", "h1"], "data": {"temperature_2m": [10.0, 0.0]}},
        "sensors": {"time": ["h0", "h1"],
                    "data": {"temperature_2m": [20.0, None]}},
    }
    weights = {"temperature_2m": {"a": 0.5, "b": 0.5, "sensors": 0.5}}
    out = meteo.assemble_consensus(
        hb, ["temperature_2m"], weights, min_sources=2
    )
    # Прошедший час: равные веса 0.5 у троих, сумма 1.5, среднее 0/10/20 = 10.0.
    assert abs(out["weighted"]["temperature_2m"][0] - 10.0) < 1e-6
    # Будущий час: у датчика None, consensus его отбросил, остались две модели.
    assert abs(out["weighted"]["temperature_2m"][1] - 5.0) < 1e-6
    assert out["models"]["sensors"]["temperature_2m"] == [20.0, None]


def test_sensor_doubles_its_weight_over_the_model_mean():
    """Контракт apply_sensor_weights: вдвое больше среднего веса модели.

    Функция обходит SENSOR_VARS, поэтому контракт проверяется ровно на том
    множестве, которое реально измеряет сеть, - иначе тест врал бы, проверяя
    переменные, до которых код не доходит.
    """
    for var in meteo.SENSOR_VARS:
        wbv = {var: {"a": 0.2, "b": 0.8}}
        meteo.apply_sensor_weights(wbv, ["a", "b"])
        mean = 0.5
        assert wbv[var]["sensors"] == 2.0 * mean


def test_sensor_doubled_weight_reaches_weighted_consensus():
    """Вес 2.0 доезжает до weighted_consensus, а не остаётся в словаре.

    Три источника: модель 0.0, внешний 0.0, датчик 20.0, веса моделей по 1.0.
    Датчик получает 2.0, сумма весов 4.0, ответ 40/4 = 10.0. При весе 1.0
    сумма была бы 3.0 и ответ 20/3 = 6.67 — расхождение заметно, поэтому
    тест не проходит вхолостую.
    """
    hb = {
        "model": {"time": ["h0"], "data": {"temperature_2m": [0.0]}},
        "ext": {"time": ["h0"], "data": {"temperature_2m": [0.0]}},
    }
    weights = {"temperature_2m": {"model": 1.0, "ext": 1.0}}
    meteo.apply_sensor_weights(weights, ["model", "ext", meteo.SENSOR_CODE])
    hb[meteo.SENSOR_CODE] = {
        "time": ["h0"], "data": {"temperature_2m": [20.0]},
    }
    out = meteo.assemble_consensus(hb, ["temperature_2m"], weights, min_sources=2)
    assert out["models"][meteo.SENSOR_CODE]["temperature_2m"] == [20.0]
    assert abs(out["weighted"]["temperature_2m"][0] - 10.0) < 1e-9
    # при 1.0 вместо 2.0 среднее было бы 20/3
    assert abs(out["weighted"]["temperature_2m"][0] - 20.0 / 3.0) > 1.0


def test_sensor_none_past_hours_do_not_fabricate_forecast():
    """Датчик не заполняет будущие часы: consensus там остаётся как был."""
    hb = {
        "a": {"time": ["h0", "h1"], "data": {"temperature_2m": [10.0, 10.0]}},
        "b": {"time": ["h0", "h1"], "data": {"temperature_2m": [12.0, 12.0]}},
    }
    plain = meteo.assemble_consensus(hb, ["temperature_2m"], {})
    hb[meteo.SENSOR_CODE] = {
        "time": ["h0", "h1"], "data": {"temperature_2m": [5.0, None]},
    }
    with_sensor = meteo.assemble_consensus(hb, ["temperature_2m"], {})
    assert plain["weighted"]["temperature_2m"][1] == with_sensor["weighted"]["temperature_2m"][1]
    assert with_sensor["weighted"]["temperature_2m"][1] == 11.0


def test_wwo_neither_votes_nor_weighs_but_still_adds_mm(monkeypatch):
    """WWO в консенсусе: код и вероятность молчат, миллиметры идут.

    Строка берётся через настоящий fetch_wwo, а не руками: правка живёт
    именно в источнике. Дождевой код 302 и вероятность 90% от wwo обязаны
    быть отброшены, а 0.6 мм — дойти до weighted.precipitation.

    min_sources=1, потому что код погоды у wwo намеренно None: без него
    сухая модель «а» осталась бы единственным голосующим, и консенсус
    кода вообще не собрался бы.
    """
    from datetime import datetime, timezone

    class _Resp:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            pass

        def json(self):
            return self._payload

    payload = {"data": {"weather": [
        {"date": "2026-08-28", "hourly": [
            {"time": "500", "tempC": "18", "FeelsLikeC": "17",
             "humidity": "70", "precipMM": "0.6", "chanceofrain": "90",
             "weatherCode": "302", "pressure": "1013",
             "cloudcover": "60", "windspeedKmph": "10",
             "WindGustKmph": "20", "winddirDegree": "180",
             "visibility": "10"},
        ]},
    ]}}
    monkeypatch.setattr(
        meteo, "_request_get",
        lambda url, params=None, timeout=None: _Resp(payload),
    )
    wwo_rows = meteo.fetch_wwo(57.63, 39.87, api_key="test")

    hour = datetime(2026, 8, 28, 5, tzinfo=timezone.utc)
    grid = ["2026-08-28T05:00"]
    dry = [{"utc": hour, "precipitation": 0.0,
            "precipitation_probability": 10.0, "weather_code": 0}]
    other = [{"utc": hour, "precipitation": 0.0,
              "precipitation_probability": 20.0, "weather_code": None}]
    hourly = {
        "a": meteo.align_to_grid(dry, grid, timezone.utc),
        "b": meteo.align_to_grid(other, grid, timezone.utc),
        meteo.WWO_CODE: meteo.align_to_grid(wwo_rows, grid, timezone.utc),
    }
    weights = {
        "precipitation": {"a": 1.0, "b": 1.0, meteo.WWO_CODE: 1.0},
        "precipitation_probability": {"a": 1.0, "b": 1.0,
                                      meteo.WWO_CODE: 1.0},
    }
    out = meteo.assemble_consensus(
        hourly,
        ["weather_code", "precipitation", "precipitation_probability"],
        weights, min_sources=1,
    )

    # 302 = дождь: с ним ничья 0/61 перетянула бы консенсус в дождь
    assert out["weighted"]["weather_code"][0] == 0
    # 90% от wwo подняли бы среднее с 15 до 40
    assert out["weighted"]["precipitation_probability"][0] == 15.0
    # 0.6 мм от wwo доходят: (0+0+0.6)/3, floor до десятых
    assert abs(out["weighted"]["precipitation"][0] - 0.2) < 1e-9
