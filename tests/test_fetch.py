import meteo


def test_fetch_all_forecasts_returns_all_models(monkeypatch):
    calls = []

    def fake_fetch_model(code, endpoint, variables, days=None, timezone=None):
        calls.append((code, endpoint))
        return [{"model": code}]

    monkeypatch.setattr(meteo, "fetch_model", fake_fetch_model)
    models = [("a", "A", "forecast"), ("b", "B", "ensemble")]
    res = meteo.fetch_all_forecasts(models, ["temperature_2m"], 2, "UTC", max_workers=2)
    assert set(res) == {"a", "b"}
    assert res["a"] == [{"model": "a"}]
    assert res["b"] == [{"model": "b"}]
    assert set(calls) == {("a", "forecast"), ("b", "ensemble")}


def test_fetch_all_forecasts_skips_failures(monkeypatch):
    def fake_fetch_model(code, endpoint, variables, days=None, timezone=None):
        if code == "bad":
            raise RuntimeError("boom")
        return [{"model": code}]

    monkeypatch.setattr(meteo, "fetch_model", fake_fetch_model)
    models = [("good", "G", "forecast"), ("bad", "B", "forecast")]
    res = meteo.fetch_all_forecasts(models, ["t"], 2, "UTC", max_workers=2)
    assert "good" in res
    assert "bad" not in res
