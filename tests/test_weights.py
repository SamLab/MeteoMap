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
