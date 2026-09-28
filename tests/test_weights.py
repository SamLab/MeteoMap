import meteo


def test_make_weights_inverse_mae():
    mae = {"a": {"temperature_2m": 1.0}, "b": {"temperature_2m": 3.0}}
    w = meteo.make_weights(mae, "temperature_2m")
    assert abs(w["a"] - 0.75) < 1e-6
    assert abs(w["b"] - 0.25) < 1e-6


def test_make_weights_missing_gets_lowest():
    mae = {
        "a": {"temperature_2m": 1.0},
        "b": {"temperature_2m": 2.0},
        "c": {},  # no data → gets lowest inverse weight
    }
    w = meteo.make_weights(mae, "temperature_2m")
    assert abs(sum(w.values()) - 1.0) < 1e-6
    inv = [1.0, 0.5]
    lowest = min(inv)
    total = sum(inv) + lowest
    assert abs(w["c"] - lowest / total) < 1e-6
    assert w["c"] == w["b"]


def test_make_weights_all_missing_equal():
    mae = {"a": {}, "b": {}}
    w = meteo.make_weights(mae, "temperature_2m")
    assert abs(w["a"] - 0.5) < 1e-6
    assert abs(w["b"] - 0.5) < 1e-6


def test_weighted_consensus_basic():
    assert abs(meteo.weighted_consensus([0.0, 10.0], [0.25, 0.75]) - 7.5) < 1e-6


def test_weighted_consensus_skips_none_and_renormalizes():
    # weights 0.25/0.75, second value None → uses only first, normalized to 1.0
    assert meteo.weighted_consensus([5.0, None], [0.25, 0.75]) == 5.0


def test_weighted_consensus_all_none():
    assert meteo.weighted_consensus([None, None], [0.5, 0.5]) is None


def test_weighted_consensus_zero_weight_total():
    assert meteo.weighted_consensus([1.0, 2.0], [0.0, 0.0]) is None


def test_force_min_weight_sets_lowest():
    w = {"a": 0.5, "b": 0.3, "c": 0.2}
    out = meteo.force_min_weight(dict(w), "a")
    assert out["a"] == 0.2
    assert out["b"] == 0.3


def test_force_min_weight_keeps_equal_minimum():
    # их минимальные совпадают — вес не меняется
    w = {"a": 0.2, "b": 0.3}
    out = meteo.force_min_weight(dict(w), "a")
    assert out["a"] == 0.2


def test_force_min_weight_missing_code_noop():
    w = {"a": 0.5, "b": 0.5}
    assert meteo.force_min_weight(dict(w), "zz") == w


def test_build_precip_weights_wwo_minimal_in_both():
    base = {
        "temperature_2m": {"a": 0.6, "b": 0.4, "wwo": 0.3},
        "precipitation": {"a": 0.7, "b": 0.2, "wwo": 0.9},
    }
    out = meteo.build_precip_weights(base)
    # вероятность берёт веса количества, WWO занижен до минимума
    assert out["precipitation_probability"]["wwo"] == 0.2
    assert out["precipitation_probability"]["a"] == 0.7
    assert out["precipitation_probability"]["b"] == 0.2
    # количество тоже форсируется
    assert out["precipitation"]["wwo"] == 0.2
    # остальные переменные не тронуты
    assert out["temperature_2m"] == base["temperature_2m"]


def test_build_precip_weights_no_precip_key():
    base = {"temperature_2m": {"a": 0.5, "b": 0.5}}
    out = meteo.build_precip_weights(base)
    assert "precipitation" not in out
    assert "precipitation_probability" not in out


def test_sensor_weight_is_double_average_model():
    wbv = {"temperature_2m": {"a": 0.05, "b": 0.05, "c": 0.05}}
    meteo.apply_sensor_weights(wbv, ["a", "b", "c"])
    assert abs(wbv["temperature_2m"]["sensors"] - 2 * 0.05) < 1e-6


def test_sensor_weight_uses_mean_not_min_or_max():
    # Неравномерные веса: 2*среднее=1.0, 2*минимум=0.4, 2*максимум=1.6.
    # При равномерных весах (остальные тесты) среднее совпадает с обоими
    # краями, поэтому подмена average→min/max прошла бы незаметно.
    wbv = {"temperature_2m": {"a": 0.2, "b": 0.8}}
    meteo.apply_sensor_weights(wbv, ["a", "b"])
    assert abs(wbv["temperature_2m"]["sensors"] - 1.0) < 1e-6


def test_sensor_weight_added_for_variable_without_weights():
    # Ветка fallback: переменной нет в weights_by_var, и код подставляет всем
    # моделям 1.0, а датчику - вдвое больше. apply_sensor_weights обходит
    # SENSOR_VARS, поэтому проверяется на температуре - единственном
    # измеряемом параметре.
    wbv = {}
    meteo.apply_sensor_weights(wbv, ["a", "b"])
    assert wbv["temperature_2m"] == {"a": 1.0, "b": 1.0, "sensors": 2.0}


def test_sensor_weight_leaves_model_weights_untouched():
    before = {"a": 0.3, "b": 0.7}
    wbv = {"temperature_2m": dict(before)}
    meteo.apply_sensor_weights(wbv, ["a", "b"])
    assert wbv["temperature_2m"]["a"] == before["a"]
    assert wbv["temperature_2m"]["b"] == before["b"]


def test_sensor_weight_is_idempotent_for_both_call_shapes():
    # (a) повторный вызов не удваивает вес датчика
    once = {"temperature_2m": {"a": 0.4, "b": 0.6}}
    meteo.apply_sensor_weights(once, ["a", "b"])
    twice = {k: dict(v) for k, v in once.items()}
    meteo.apply_sensor_weights(twice, ["a", "b"])
    meteo.apply_sensor_weights(twice, ["a", "b"])
    assert twice == once
    assert abs(twice["temperature_2m"]["sensors"] - 1.0) < 1e-6
    # (b) вызов с уже добавленным в model_codes SENSOR_CODE (город дописывает
    # его в city_codes до вызова) даёт тот же результат, что и без него
    with_sensor = {"temperature_2m": {"a": 0.4, "b": 0.6}}
    meteo.apply_sensor_weights(with_sensor, ["a", "b", "sensors"])
    assert with_sensor == once


def test_sensor_weight_untouched_variables_absent():
    wbv = {"precipitation": {"a": 0.5, "b": 0.5}}
    meteo.apply_sensor_weights(wbv, ["a", "b"])
    assert wbv["precipitation"] == {"a": 0.5, "b": 0.5}
    # ровно исходная переменная плюс SENSOR_VARS — лишних записей не появилось
    assert set(wbv) == {"precipitation", *meteo.SENSOR_VARS}
