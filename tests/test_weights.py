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
