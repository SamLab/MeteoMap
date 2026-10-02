import json
import os

import pytest

import meteo
from meteo import SENSOR_LOCATIONS, load_sensor_model


def test_locations_have_unique_slugs():
    slugs = [loc["slug"] for loc in meteo.LOCATIONS]
    assert len(slugs) == len(set(slugs))
    assert "yaroslavl" in slugs
    assert meteo.LOCATIONS[0]["name"] == "Ярославль"


def test_moscow_external_disabled():
    m = next(loc for loc in meteo.LOCATIONS if loc["slug"] == "moscow")
    assert m["name"] == "Москва"
    assert m.get("external") is False


def test_batumi_timezone():
    b = next(loc for loc in meteo.LOCATIONS if loc["slug"] == "batumi")
    assert b["name"] == "Батуми (Грузия)"
    assert b["tz"] == "Asia/Tbilisi"
    assert b["tz_offset"] == 4
    assert "balakirevo" not in [loc["slug"] for loc in meteo.LOCATIONS]


def test_fetch_model_batch_splits_by_city(monkeypatch):
    calls = {}

    def fake_request(url, params, timeout):
        calls["params"] = params
        return [
            {"latitude": 57.75, "hourly": {"time": ["t"], "temperature_2m": [1.0]}},
            {"latitude": 56.5, "hourly": {"time": ["t"], "temperature_2m": [5.0]}},
        ]

    monkeypatch.setattr(meteo, "request_with_retry", fake_request)
    res = meteo.fetch_model(
        "m", "forecast", ["temperature_2m"],
        days=2, lats="57.63,56.507", lons="39.87,38.846",
    )
    assert len(res) == 2
    assert res[0]["hourly"]["temperature_2m"] == [1.0]
    assert res[1]["hourly"]["temperature_2m"] == [5.0]
    assert calls["params"]["latitude"] == "57.63,56.507"
    assert calls["params"]["longitude"] == "39.87,38.846"


def test_fetch_model_wraps_single_response(monkeypatch):
    monkeypatch.setattr(
        meteo, "request_with_retry",
        lambda *a, **k: {"latitude": 57.75, "hourly": {}},
    )
    res = meteo.fetch_model("m", "forecast", ["temperature_2m"], lats="57.63", lons="39.87")
    assert isinstance(res, list) and len(res) == 1


def test_fetch_model_ensemble_has_longer_timeout(monkeypatch):
    seen = {}

    def fake(url, params, timeout):
        seen["timeout"] = timeout
        return {"hourly": {"time": ["t"], "temperature_2m": [1.0]}}

    monkeypatch.setattr(meteo, "request_with_retry", fake)
    meteo.fetch_model("n", "ensemble", ["temperature_2m"], lats="57.63", lons="39.87")
    assert seen["timeout"] == 30


def test_fetch_historical_model_wraps_single_response(monkeypatch):
    monkeypatch.setattr(
        meteo, "request_with_retry",
        lambda *a, **k: {"hourly": {"time": ["t"], "temperature_2m": [1.0]}},
    )
    res = meteo.fetch_historical_model("m", "2026-07-30", "2026-08-05", ["temperature_2m"])
    assert isinstance(res, list) and len(res) == 1


def test_fetch_archive_wraps_single_response(monkeypatch):
    monkeypatch.setattr(
        meteo, "request_with_retry",
        lambda *a, **k: {"hourly": {"time": ["t"], "temperature_2m": [1.0]}},
    )
    res = meteo.fetch_archive("2026-07-30", "2026-08-05", ["temperature_2m"])
    assert isinstance(res, list) and len(res) == 1


def test_build_payload_uses_location():
    hourly = {"a": {"time": ["h0"], "data": {"temperature_2m": [1.0]}}}
    consensus = {
        "time": ["h0"], "weighted": {"temperature_2m": [1.0]},
        "mean": {"temperature_2m": [1.0]}, "median": {"temperature_2m": [1.0]},
    }
    loc = {"name": "Батуми (Грузия)", "slug": "batumi", "lat": 41.6461, "lon": 41.6356}
    p = meteo.build_payload(["a"], {"a": "A"}, hourly, {}, consensus, {},
                            "2026-08-06T12:00:00+03:00", loc)
    assert p["location"] == loc


def test_render_replaces_cities_placeholder():
    template = "<script id='cities'>__CITIES__</script>"
    payload = {"location": {"name": "Ярославль"}, "generated_at": "2026-08-06T12:00:00+03:00"}
    html = meteo.render(template, payload)
    assert "__CITIES__" not in html
    assert '"slug": "yaroslavl"' in html
    assert 'Батуми (Грузия)' in html
    assert '"slug": "batumi"' in html


def _write_history(tmp_path, obj, name="sensors_history.json"):
    p = tmp_path / name
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return str(p)


def test_sensor_model_fills_past_hours_and_nulls_the_rest(tmp_path):
    hist = {"hours": {"2026-09-28T10:00": {
        "samples": 2, "stations": {
            "a": {"temperature_2m": [10.0, 12.0]},
            "b": {"temperature_2m": [20.0, 20.0]},
        }},
        "2026-09-28T11:00": {
        "samples": 1, "stations": {
            "a": {"pressure_msl": [760.0]}}}}}
    p = tmp_path / "sensors_history.json"
    p.write_text(json.dumps(hist), encoding="utf-8")
    grid = ["2026-09-28T09:00", "2026-09-28T10:00", "2026-09-28T11:00",
            "2026-09-28T12:00"]
    model = load_sensor_model(grid, str(p))
    assert model["time"] == grid
    # станция a: mean(10,12)=11, станция b: mean(20,20)=20, среднее 15.5
    assert model["data"]["temperature_2m"] == [None, 15.5, None, None]
    # Влажность и давление убраны из измерений, поэтому старые бакеты с ними
    # в модель не попадают вообще - в том числе из уже накопленной истории,
    # которую мы намеренно не вычищали.
    assert "pressure_msl" not in model["data"]
    assert "relative_humidity_2m" not in model["data"]


def test_sensor_hour_value_is_mean_of_station_means(tmp_path):
    """Станции равноправны: среднее по замерам, потом среднее по станциям.

    Одна станция с двумя замерами не должна весить как две станции по одному.
    """
    hist = {"hours": {"2026-09-28T10:00": {"samples": 2, "stations": {
        "busy": {"temperature_2m": [0.0, 0.0, 30.0]},
        "quiet": {"temperature_2m": [20.0]},
    }}}}
    path = _write_history(tmp_path, hist)
    model = load_sensor_model(["2026-09-28T10:00"], path)
    # busy -> 10.0, quiet -> 20.0, среднее 15.0 (а не mean всех четырёх = 12.5)
    assert model["data"]["temperature_2m"] == [15.0]


def test_sensor_model_missing_history_is_none(tmp_path):
    assert load_sensor_model(["2026-09-28T10:00"], str(tmp_path / "nope.json")) is None


def test_sensor_model_corrupt_history_is_none(tmp_path):
    p = tmp_path / "h.json"
    p.write_text("{oops", encoding="utf-8")
    assert load_sensor_model(["2026-09-28T10:00"], str(p)) is None


def test_sensors_absent_for_other_cities():
    assert SENSOR_LOCATIONS == {"yaroslavl", "tsedenevo"}
    for slug in ["rybinsk", "rostov", "petropavlovka", "moscow", "loo",
                 "borok", "batumi"]:
        assert slug not in SENSOR_LOCATIONS


# --- битая sensors_history.json: meteo.py читает файл при сборке сайта, и
# руками правленый JSON не должен ронять сборку. Семантика повторяет
# load_history/history_hour_value в tools/collect_sensors.py. ---


def test_sensor_model_top_level_not_dict_is_none(tmp_path):
    path = _write_history(tmp_path, [{"hours": {"2026-09-28T10:00": {}}}])
    assert load_sensor_model(["2026-09-28T10:00"], path) is None


@pytest.mark.parametrize("hours", [[], "2026-09-28T10:00", None, 7, True])
def test_sensor_model_hours_not_dict_is_none(tmp_path, hours):
    path = _write_history(tmp_path, {"hours": hours})
    assert load_sensor_model(["2026-09-28T10:00"], path) is None


def test_sensor_model_empty_hours_is_none(tmp_path):
    path = _write_history(tmp_path, {"hours": {}})
    assert load_sensor_model(["2026-09-28T10:00"], path) is None


def test_sensor_model_foreign_hour_buckets_dropped(tmp_path):
    """Бакет не той формы отбрасывается, читаемые часы рядом выживают."""
    hist = {
        "hours": {
            "2026-09-28T09:00": "2026-09-28T09:00",
            "2026-09-28T10:00": [1, 2, 3],
            "2026-09-28T11:00": None,
            "2026-09-28T12:00": {"samples": 1, "stations": None},
            "2026-09-28T13:00": {"samples": 1, "stations": []},
            "2026-09-28T14:00": {"samples": 1, "stations": {
                "a": {"temperature_2m": [5.0]}}},
        }
    }
    path = _write_history(tmp_path, hist)
    grid = [f"2026-09-28T{h:02d}:00" for h in range(9, 15)]
    model = load_sensor_model(grid, path)
    assert model["data"]["temperature_2m"] == [None] * 5 + [5.0]


def test_sensor_model_foreign_station_entries_skipped(tmp_path):
    hist = {"hours": {"2026-09-28T10:00": {"samples": 2, "stations": {
        "a": "broken",
        "b": None,
        "c": ["broken"],
        "d": {"temperature_2m": [10.0, 30.0]},
        "e": {"temperature_2m": 20.0},
        "f": {"temperature_2m": []},
        "g": {"temperature_2m": None},
    }}}}
    path = _write_history(tmp_path, hist)
    model = load_sensor_model(["2026-09-28T10:00"], path)
    # выжил только d: остальные записи либо не словари, либо не списки
    assert model["data"]["temperature_2m"] == [20.0]


@pytest.mark.parametrize("samples", [[None], ["x"], [None, 1.0], ["1.0"],
                                     [1.0, "2.0"], [1.0, None], [{}], [[]],
                                     [True, False]])
def test_sensor_model_non_numeric_samples_give_none_not_crash(tmp_path, samples):
    """Список замеров с не-числом — это «нет данных», а не исключение."""
    hist = {"hours": {"2026-09-28T10:00": {"samples": 1, "stations": {
        "a": {"temperature_2m": samples}}}}}
    path = _write_history(tmp_path, hist)
    model = load_sensor_model(["2026-09-28T10:00"], path)
    assert model is None


def test_sensor_model_usable_values_survive_a_broken_neighbour(tmp_path):
    """Битая запись одной станции не обнуляет читаемую вторую."""
    hist = {"hours": {"2026-09-28T10:00": {"samples": 2, "stations": {
        "a": {"temperature_2m": [None, "oops"]},
        "b": {"temperature_2m": [8.0, 12.0]},
    }}}}
    path = _write_history(tmp_path, hist)
    model = load_sensor_model(["2026-09-28T10:00"], path)
    assert model["data"]["temperature_2m"] == [10.0]


def test_sensor_model_hour_with_no_stations_yields_none_column(tmp_path):
    """Чистый файл без единого значения — источника нет, а не нули."""
    path = _write_history(tmp_path, {"hours": {
        "2026-09-28T10:00": {"samples": 0, "stations": {}},
    }})
    assert load_sensor_model(["2026-09-28T10:00"], path) is None


def test_sensor_hour_value_returns_mean_min_and_station_count():
    """Четвёрка (среднее, минимум, максимум, n).

    Все три статистики берутся из одного и того же списка пер-станционных
    средних: если считать их раздельно, ночной минимум может оказаться по
    двум станциям, а среднее — по четырём, и строка станет несопоставимой
    сама с собой.
    """
    bucket = {"stations": {
        "a": {"temperature_2m": [10.0, 20.0]},   # среднее станции 15
        "b": {"temperature_2m": [40.0]},          # среднее станции 40
        "c": {"relative_humidity_2m": [55.0]},    # к температуре отношения не имеет
    }}
    # минимум 15 — это среднее станции «a», а не 10: сырые замеры внутри часа
    # за минимум не принимаются, иначе станция с двумя замерами перевесила бы
    # станцию с одним и «минимум» зависел бы от числа прогонов, а не от погоды
    assert meteo._sensor_hour_value(bucket, "temperature_2m") == (27.5, 15.0, 40.0, 2)
    # станция без замеров по этому параметру в счётчик не идёт
    assert meteo._sensor_hour_value(bucket, "pressure_msl") == (None, None, None, 0)


def test_sensor_model_publishes_station_counts_per_hour(tmp_path):
    """Счётчики едут из истории вместе со значениями, по той же оси grid."""
    hist = {"hours": {
        "2026-09-28T10:00": {"samples": 3, "stations": {
            "a": {"temperature_2m": [10.0]},
            "b": {"temperature_2m": [20.0]},
            "c": {"relative_humidity_2m": [50.0]}}},
        "2026-09-28T11:00": {"samples": 2, "stations": {
            "a": {"temperature_2m": [7.0, 8.0]}}},
    }}
    grid = ["2026-09-28T09:00", "2026-09-28T10:00",
            "2026-09-28T11:00", "2026-09-28T12:00"]
    model = load_sensor_model(grid, _write_history(tmp_path, hist))
    assert model["data"]["temperature_2m"] == [None, 15.0, 7.5, None]
    # n считается по станциям: «a» с двумя замерами — это одна станция, а не две
    assert model["station_counts"]["temperature_2m"] == [0, 2, 1, 0]
    # часы без наблюдений дают 0, а не None: ноль станций — факт, а не пробел
    assert set(model["station_counts"]) == set(meteo.SENSOR_VARS)
    # Станция «c» осталась в старом бакете с влажностью - она не превращается
    # ни во что, потому что влажность больше не измеряется.
    assert meteo.SENSOR_VARS == ("temperature_2m",)


def test_sensor_model_publishes_station_minimum_per_hour(tmp_path):
    """Минимум едет из истории по той же оси grid, что и среднее."""
    hist = {"hours": {
        "2026-09-28T10:00": {"samples": 3, "stations": {
            "a": {"temperature_2m": [10.0]},
            "b": {"temperature_2m": [20.0]},
            "c": {"relative_humidity_2m": [50.0]}}},
        "2026-09-28T11:00": {"samples": 2, "stations": {
            "a": {"temperature_2m": [7.0, 8.0]}}},
    }}
    grid = ["2026-09-28T09:00", "2026-09-28T10:00",
            "2026-09-28T11:00", "2026-09-28T12:00"]
    model = load_sensor_model(grid, _write_history(tmp_path, hist))
    # тот же ряд, что station_counts: 0 станций там, где и минимума нет
    assert model["station_min"]["temperature_2m"] == [None, 10.0, 7.5, None]
    assert set(model["station_min"]) == set(meteo.SENSOR_VARS)
    # среднее и минимум не пересекаются: 15.0 строго между 7.5 и 10.0 не
    # появится, среднее по «a» и «b» — ровно посередине их значений
    assert model["data"]["temperature_2m"] == [None, 15.0, 7.5, None]


def test_sensor_hour_value_foreign_bucket_is_none():
    assert meteo._sensor_hour_value("2026-09-28T10:00", "temperature_2m") == (None, None, None, 0)
    assert meteo._sensor_hour_value(None, "temperature_2m") == (None, None, None, 0)
    assert meteo._sensor_hour_value({"stations": 5}, "temperature_2m") == (None, None, None, 0)


def test_sensor_hour_value_last_takes_the_latest_sample_per_station():
    """Режим last=True берёт последний замер станции, а не среднее часа.

    Им живёт показ «сейчас»: пользователь хотел видеть последний опрос, а не
    среднее по прошедшим часа. Минимум и максимум выходят из тех же последних
    значений, поэтому «Датчики» и ночной минимум Цеденево остаются
    сопоставимыми.
    """
    bucket = {"stations": {
        "a": {"temperature_2m": [10.0, 20.0]},   # последний 20
        "b": {"temperature_2m": [40.0, 5.0]},    # последний 5
        "c": {"relative_humidity_2m": [55.0]},   # к температуре отношения не имеет
    }}
    assert meteo._sensor_hour_value(bucket, "temperature_2m", last=True) == (
        12.5, 5.0, 20.0, 2)
    assert meteo._sensor_hour_value(bucket, "pressure_msl", last=True) == (
        None, None, None, 0)
    # средний режим не поехал: a=15, b=22.5, среднее 18.75
    assert meteo._sensor_hour_value(bucket, "temperature_2m") == (
        18.75, 15.0, 22.5, 2)


def test_sensor_model_publishes_now_arrays_per_hour(tmp_path):
    """Ряды последних замеров едут рядом со средним, по той же оси grid."""
    hist = {"hours": {
        "2026-09-28T10:00": {"samples": 4, "stations": {
            "a": {"temperature_2m": [10.0, 14.0]},
            "b": {"temperature_2m": [20.0, 18.0]}}},
        "2026-09-28T11:00": {"samples": 2, "stations": {
            "a": {"temperature_2m": [7.0, 8.0]}}},
    }}
    grid = ["2026-09-28T09:00", "2026-09-28T10:00",
            "2026-09-28T11:00", "2026-09-28T12:00"]
    model = load_sensor_model(grid, _write_history(tmp_path, hist))
    # среднее часа: a=12, b=19 -> 15.5; a=7.5
    assert model["data"]["temperature_2m"] == [None, 15.5, 7.5, None]
    # последние замеры: a=14, b=18 -> 16.0; a=8
    assert model["now_value"]["temperature_2m"] == [None, 16.0, 8.0, None]
    assert model["now_min"]["temperature_2m"] == [None, 14.0, 8.0, None]
    assert model["now_max"]["temperature_2m"] == [None, 18.0, 8.0, None]
    assert set(model["now_value"]) == set(meteo.SENSOR_VARS)
    assert set(model["now_min"]) == set(meteo.SENSOR_VARS)
    assert set(model["now_max"]) == set(meteo.SENSOR_VARS)



def test_sensor_model_history_path_defaults_next_to_meteo_py():
    # Проверяем не формулу, а куда файл попадает: рядом с meteo.py, в корне
    # репозитория, а не под data/ — data/ в .gitignore, и накопленная история
    # обнулялась бы на каждом CI-прогоне. Переписывание os.path.join должно
    # ломать этот тест, а не только менять его текст.
    path = os.path.abspath(meteo.SENSOR_HISTORY)
    root = os.path.dirname(os.path.abspath(meteo.__file__))

    assert os.path.basename(path) == "sensors_history.json"
    assert os.path.dirname(path) == root, "история обязана лежать рядом с meteo.py"
    assert "data" not in os.path.relpath(path, root).split(os.sep)
    # корень репозитория, а не произвольная папка рядом с ним
    assert os.path.isfile(os.path.join(root, "pytest.ini"))


def test_sensor_model_publishes_last_reading_time_per_hour(tmp_path):
    """Клиенту нужно время последнего замера, а не ключ бакета."""
    hist = {"hours": {
        "2026-09-28T10:00": {"samples": 1, "updated_at": "2026-09-28T10:53:00+03:00",
                             "stations": {"a": {"temperature_2m": [10.0]}}},
        "2026-09-28T11:00": {"samples": 1, "stations": {"a": {"temperature_2m": [7.0]}}},
    }}
    grid = ["2026-09-28T10:00", "2026-09-28T11:00"]
    model = load_sensor_model(grid, _write_history(tmp_path, hist))
    # старый бакет без updated_at остаётся None, чтобы клиент откатился на час
    assert model["updated_at"]["temperature_2m"] == ["2026-09-28T10:53:00+03:00", None]
    assert set(model["updated_at"]) == set(meteo.SENSOR_VARS)
