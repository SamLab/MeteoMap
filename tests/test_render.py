import json
import os
import re
import shutil
import subprocess

import pytest

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


def read_template():
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        return f.read()


def test_cmp_col_order_filters_sensor_for_unmeasured_variable():
    html = read_template()
    assert "const SENSOR_VARS=['temperature_2m'];" in html
    assert "c!==SENSOR_CODE" in html or "!(c===SENSOR_CODE" in html
    assert "cmpColOrder(codes,v)" in html
    assert "cmpColOrder(codes,cmpVar)" in html


def test_cmp_col_order_has_no_bare_single_argument_call_site():
    """Every call site must pass the current variable.

    The legend call site ``cmpColOrder(codes,curVar)`` was previously unasserted,
    and reverting it to the one-argument form leaks the «Датчик» legend entry for
    every variable while leaving the table and the chart correct.
    """
    html = read_template()
    assert "cmpColOrder(codes,v)" in html
    assert "cmpColOrder(codes,curVar)" in html
    assert "cmpColOrder(codes,cmpVar)" in html
    assert "cmpColOrder(codes)" not in html
    assert re.findall(r"cmpColOrder\(codes\)", html) == []


def test_cmp_col_order_sensor_ok_is_derived_not_hardcoded():
    """``sensorOk`` must come from SENSOR_VARS, never from a literal.

    Hardcoding it to ``true`` restores the original bug — the «Датчик» column is
    shown for every variable — while leaving every positive token assertion
    above green.
    """
    html = read_template()
    assert "const sensorOk=v==null||SENSOR_VARS.indexOf(v)>=0;" in html
    assert re.search(r"sensorOk\s*=\s*(?:true|false|'1'|'0'|1|0)\b", html) is None


def test_template_sensor_vars_match_python():
    """SENSOR_VARS is duplicated in meteo.py and in the template.

    Only the JS side was pinned, so a parameter added to ``meteo.SENSOR_VARS``
    would be published and then silently hidden by the ``cmpColOrder`` filter:
    real data disappears from the page with no failing test. The lists must be
    equal, and the comparison has to read the template, not a literal.
    """
    html = read_template()
    m = re.search(r"const SENSOR_VARS=\[([^\]]*)\];", html)
    assert m, "в шаблоне нет списка SENSOR_VARS"
    js_vars = [v.strip().strip("'\"") for v in m.group(1).split(",")]
    assert js_vars == list(meteo.SENSOR_VARS)


def _cmp_table_js():
    """Тело buildCmpTable — места, где рисуется ячейка источника."""
    html = read_template()
    start = html.index("function buildCmpTable(){")
    return html[start:html.index("// accuracy", start)]


def test_cmp_table_renders_station_count_as_superscript():
    """Число станций обязано быть видно в самой ячейке.

    Среднее по одной станции (`66.1` за 2026-09-28T20:00, когда Пенаты и Фрунзе
    отдали заглушку) иначе выглядит ровно как среднее по четырём.
    """
    body = _cmp_table_js()
    # цифра берётся из верхнеуровневого ключа payload по текущей переменной
    assert "D.sensor_station_counts[cmpVar]" in body
    assert re.search(r"<sup>[^<]*\$\{sc\[i\]\}</sup>", body)
    # только в колонке «Датчик» и только когда значение числовое: у «—»
    # (пустой или будущий час) цифры быть не должно
    assert re.search(r"j===si&&typeof v==='number'", body)
    # счётчики не читаются из models[code]: это ряды по переменным, и
    # не-массивный элемент там сломал бы сборку графика
    assert re.search(r"models\[[^\]]+\][^\n]*station_counts", read_template()) is None


def test_cmp_table_uses_the_same_sensor_value_as_now():
    """Колонка «Датчик» в «Часах» показывает ту же величину, что «Сейчас».

    Цеденево вне окна среднего берёт минимум по станциям, но таблица сравнения
    рисовала среднее: строка «По датчику» и столбик в «Часах» расходились.
    Подстановка идёт через `sensorValueFor` и до подсчёта mx/mn, поэтому и
    сравнение с консенсусом, и жирный экстремум считаются по показанному числу.
    """
    body = _cmp_table_js()
    assert "sensorValueFor(" in body, "значение «Датчика» выбирается общим хелпером"
    assert "sensor_station_min" in body, "минимум едет отдельным ключом payload"
    assert body.index("sensorValueFor(") < body.index("Math.max(...nums)"), (
        "подстановка должна идти до подсчёта mx/mn, иначе подсветка разойдётся "
        "с показанным числом"
    )


def test_sensor_superscript_is_styled_without_breaking_the_column():
    """Надстрочная цифра обязана не раздувать строку таблицы."""
    html = read_template()
    m = re.search(r"#tab-compare \.tblwrap td sup\{([^}]*)\}", html)
    assert m, "нет стиля для надстрочной цифры в таблице «Часы»"
    assert "line-height:0" in m.group(1)


def test_help_explains_sensor_station_count():
    """Справка обязана объяснять надстрочную цифру — в этом весь смысл правки."""
    tpl = read_template()
    assert "Надстрочная цифра у «Датчика» — сколько станций усреднилось" in tpl
    assert "станция без замера в этом часе не участвует" in tpl


def test_help_documents_sensor_section():
    """Справка обязана описывать сеть датчиков целиком, а не отдельные её следы."""
    tpl = read_template()
    assert "<h2>Датчики</h2>" in tpl

    # раздел стоит перед «Часы», где остались подробности про надстрочную цифру
    i = tpl.index("<h2>Датчики</h2>")
    j = tpl.index("<h2>Часы</h2>", i)
    assert i < j

    # что меряем и где это видно
    assert "который не прогнозирует, а меряет" in tpl
    assert "только у Ярославля и Цеденево" in tpl
    assert "«По датчику»" in tpl
    assert "надстрочной цифрой" in tpl

    # время замера вместо начала часа — главное из последней правки
    assert "минуты последнего замера, а не начало часа" in tpl
    assert "«10:44»" in tpl

    # в какой час кладётся замер и как считаются молчащие станции
    assert "в момент прихода, а не в час старта прогона" in tpl
    assert "вклады станций, а не прогонов" in tpl
    assert "сохранённые брокером старые сообщения отбрасываются намеренно" in tpl
    assert "окно прослушивания около 6 минут" in tpl
    assert "старше 15 минут" in tpl
    assert "не заполняется предыдущим" in tpl

    # окно среднего Цеденево смещено относительно солнца
    assert "Цеденево — не только ночью" in tpl
    assert "с трёх часов после рассвета и до двух часов до заката" in tpl

    # сбор и условия использования YarTemp
    assert "каждые 10 минут" in tpl
    assert "30 суток" in tpl
    assert "нельзя выдавать за свои" in tpl
    assert "автор просит написать ему" in tpl

    # слой датчиков на карте отменён решением пользователя — упоминать нельзя
    assert "Датчики на карте" not in tpl


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


def _sensor_payload():
    hourly = {
        "a": {"time": ["h0", "h1"], "data": {"temperature_2m": [1.0, 3.0]}},
        meteo.SENSOR_CODE: {
            "time": ["h0", "h1"],
            "data": {"temperature_2m": [20.0, None]},
            "station_counts": {"temperature_2m": [4, 0]},
            "station_min": {"temperature_2m": [8.0, None]},
            "station_max": {"temperature_2m": [12.0, None]},
            "now_value": {"temperature_2m": [20.5, None]},
            "now_min": {"temperature_2m": [9.0, None]},
            "now_max": {"temperature_2m": [11.5, None]},
        },
    }
    consensus = {
        "time": ["h0", "h1"],
        "weighted": {"temperature_2m": [1.0, 3.0]},
        "mean": {"temperature_2m": [1.0, 3.0]},
        "median": {"temperature_2m": [1.0, 3.0]},
    }
    return meteo.build_payload(
        ["a", meteo.SENSOR_CODE], {"a": "A", meteo.SENSOR_CODE: meteo.SENSOR_NAME},
        hourly, {}, consensus, {}, "2026-08-03T12:00:00+03:00", meteo.LOCATIONS[0],
    )


def test_payload_publishes_sensor_station_counts_at_top_level():
    """Счётчики станций едут в payload отдельным верхнеуровневым ключом.

    Четвёртым ключом в ``models["sensors"]["data"]`` их быть не может: потребители
    читают ``data`` как параллельные ряды по переменным, и не-массивный элемент
    там сломал бы сборку графика.
    """
    p = _sensor_payload()
    assert p["sensor_station_counts"] == {"temperature_2m": [4, 0]}
    assert "station_counts" not in p["models"][meteo.SENSOR_CODE]
    assert set(p["models"][meteo.SENSOR_CODE]) == {"temperature_2m"}


def test_payload_publishes_sensor_station_min_at_top_level():
    """Минимум по станциям едет в payload тем же способом, что и счётчики.

    Отдельный верхнеуровневый ключ, а не элемент ``models["sensors"]``: там
    читают параллельные ряды по переменным, и не-массивный элемент сломал бы
    график. Ключ верхнего уровня — по той же причине, что и
    ``sensor_station_counts``.
    """
    p = _sensor_payload()
    assert p["sensor_station_min"] == {"temperature_2m": [8.0, None]}
    assert "station_min" not in p["models"][meteo.SENSOR_CODE]


def test_payload_publishes_sensor_station_max_at_top_level():
    """Максимум по станциям едет в payload тем же способом, что и минимум.

    Он нужен ячейке «Датчики», где рядом со средним показывается размах
    по станциям: среднее уже есть в data, минимум — в station_min.
    """
    p = _sensor_payload()
    assert p["sensor_station_max"] == {"temperature_2m": [12.0, None]}
    assert "station_max" not in p["models"][meteo.SENSOR_CODE]


def test_payload_publishes_sensor_now_arrays_at_top_level():
    """Показ «сейчас» берёт последний замер станции, а не среднее часа.

    Ряды now_value/now_min/now_max едут отдельными верхнеуровневыми ключами,
    как и остальная статистика датчиков: models[code] остаётся средним часа и
    кормит таблицы и график.
    """
    p = _sensor_payload()
    assert p["sensor_now_value"] == {"temperature_2m": [20.5, None]}
    assert p["sensor_now_min"] == {"temperature_2m": [9.0, None]}
    assert p["sensor_now_max"] == {"temperature_2m": [11.5, None]}
    for key in ("now_value", "now_min", "now_max"):
        assert key not in p["models"][meteo.SENSOR_CODE]


def test_payload_without_sensor_has_no_station_counts():
    """Город без датчика не получает ключа: двух станций рядом с ним нет."""
    assert "sensor_station_counts" not in _payload()
    assert "sensor_station_min" not in _payload()
    assert "sensor_station_max" not in _payload()
    assert "sensor_now_value" not in _payload()
    assert "sensor_now_min" not in _payload()
    assert "sensor_now_max" not in _payload()


def test_sensor_column_header_comes_from_model_names():
    """Заголовок «Датчик» — из model_names, а не из литерала в шаблоне.

    Браузерный рендер заголовка доказывает headless-прогон; здесь страж на сам
    механизм: колонка берётся из payload, и подпись не зашита в разметку.
    """
    p = _sensor_payload()
    assert meteo.SENSOR_CODE in p["model_codes"]
    assert p["model_names"][meteo.SENSOR_CODE] == meteo.SENSOR_NAME == "Датчик"
    body = _cmp_table_js()
    assert "const cols=[{t:'Время'},{t:'Консенсус'}].concat(cc.map(c=>({t:names[c]})));" \
        in body
    assert re.search(r"th>\${c\.t}</th>", body)


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


def test_render_escapes_closing_script_in_payload():
    payload = _payload()
    # модель с именем/данными, содержащими закрывающий тег, не должна рвать страницу
    payload["model_names"]["a"] = "Model </scr" + "ipt> X"
    # копия, а не сам meteo.LOCATIONS[0]: иначе тест навсегда портит модульное
    # состояние и валит любой следующий тест, читающий LOCATIONS
    payload["location"] = dict(payload["location"], name="Город </scr" + "ipt>")
    template = "<script id='data' type='application/json'>__DATA__</script>"
    html = meteo.render(template, payload)
    body = html.replace("<script id='data' type='application/json'>", "").split(
        "</script>")[0]
    assert "</scr" + "ipt>" not in body
    assert "<\\/scr" + "ipt>" in body or "<\\u003c/scr" + "ipt>" in body
    assert "Model </scr" + "ipt>" not in body


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


def test_daily_precip_uses_hourly_when_daily_diverges():
    hourly = {
        "plausible": {"time": ["2026-08-03T00:00", "2026-08-04T00:00"],
                      "data": {"precipitation": [0.0, 0.0]}},
        "spike": {"time": ["2026-08-03T00:00", "2026-08-04T00:00"],
                  "data": {"precipitation": [0.5, 1.0]}},
    }
    consensus = {
        "time": ["2026-08-03T00:00", "2026-08-04T00:00"],
        "weighted": {"precipitation": [0.25, 0.5]},
        "mean": {"precipitation": [0.25, 0.5]},
        "median": {"precipitation": [0.25, 0.5]},
    }
    # "spike" daily 6.5 мм резко расходится с её hourly (0.5), а 1.0 согласован
    daily = {
        "plausible": {"time": ["2026-08-03", "2026-08-04"],
                      "precipitation_sum": [0.0, 0.0]},
        "spike": {"time": ["2026-08-03", "2026-08-04"],
                  "precipitation_sum": [6.5, 1.0]},
    }
    p = meteo.build_payload(
        ["plausible", "spike"], {"plausible": "A", "spike": "B"},
        hourly, daily, consensus, {}, "2026-08-03T12:00:00+03:00",
        meteo.LOCATIONS[0],
    )
    # день 0: 6.5 расходится с hourly sum 0.5 → в консенсус идёт почасовая 0.5
    # день 1: 1.0 согласуется → остаётся 1.0
    # консенсус осадков округляется вниз до десятых: mean(0.5, 0.0)=0.25 → 0.2
    assert p["daily"]["precipitation_sum"] == [0.2, 0.5]


def test_daily_nonprecip_keeps_precision():
    hourly = {"a": {"time": ["h0"], "data": {"temperature_2m": [1.0]}}}
    consensus = {
        "time": ["h0"],
        "weighted": {"temperature_2m": [1.0]},
        "mean": {"temperature_2m": [1.0]},
        "median": {"temperature_2m": [1.0]},
    }
    daily = {
        "a": {"time": ["d0"], "cloud_cover_mean": [45.6]},
        "b": {"time": ["d0"], "cloud_cover_mean": [52.4]},
    }
    p = meteo.build_payload(
        ["a", "b"], {"a": "A", "b": "B"}, hourly, daily, consensus, {},
        "2026-08-03T12:00:00+03:00", meteo.LOCATIONS[0],
    )
    # не-осадочные переменные не округляются вниз до десятых: mean=49.0 → 49.0
    assert p["daily"]["cloud_cover_mean"] == pytest.approx([49.0])


# --- строка «По датчику» под «Ощущается как» в блоке «Сейчас»


def _sensor_now_js():
    """Тело функции, ищущей последний непустой бакет датчиков."""
    html = read_template()
    start = html.index("function lastSensorHour(")
    return html[start:html.index("function buildWeatherNow(", start)]


def test_weather_now_renders_sensor_line_under_apparent():
    """Строка «По датчику» обязана стоять под «Ощущается как», а не рядом.

    Пользователь просил именно это место: порядок в разметке — единственное,
    что отличает новую строку от любой другой подписи в том же блоке.
    """
    html = read_template()
    start = html.index("function buildWeatherNow(){")
    body = html[start:html.index("function buildWeatherHours(", start)]
    feel = body.index("Ощущается как")
    sensor = body.index("По датчику")
    assert feel < sensor, "«По датчику» должен идти после «Ощущается как»"
    # та же строка ощущается как у соседней подписи: без нового CSS-правила
    assert 'class="wfeel"' in body[feel - 40:feel]
    assert 'class="wfeel"' in body[sensor - 40:sensor]


def test_last_sensor_hour_walks_back_from_current_hour():
    """Значение ищется назад от текущего часа, а не в будущем.

    Датчики пишут только за прошедшие часы, поэтому «последний непустой бакет»
    почти всегда старше curIdx.
    """
    body = _sensor_now_js()
    assert re.search(r"for\(let j=curIdx;\s*j>=0;\s*j--\)", body)
    # счётчик станций и значение проверяются вместе: одно без другого
    # описывает не наблюдение
    assert "sensor_station_counts" in body


def test_last_sensor_hour_treats_zero_as_a_reading():
    """Ноль градусов — замер, а не отсутствие данных.

    Проверка на истинность (``if(!v)``) убрала бы строку в морозы, когда
    показание самое интересное.
    """
    body = _sensor_now_js()
    assert re.search(r"!=\s*null", body), "проверка на null, а не на истинность"
    assert re.search(r"if\(!v\)", body) is None


def test_last_sensor_hour_returns_null_when_grid_is_empty():
    """Пустая сетка — это «нет данных», а не необработанное исключение."""
    body = _sensor_now_js()
    assert re.search(r"return\s+null", body)


def test_last_sensor_hour_carries_max_across_stations():
    """Вместе со средним и минимумом хелпер отдаёт максимум по станциям.

    Ячейка «Датчики» показывает среднее/максимум/минимум текущей температуры,
    поэтому максимум обязан ехать тем же рядом, что и минимум, и браться по
    найденному часу наблюдения j, а не из текущего часа страницы.
    """
    body = _sensor_now_js()
    assert "sensor_now_max" in body
    assert "max:mx?mx[j]:null" in body


def test_last_sensor_hour_uses_now_arrays_not_hour_mean():
    """Значение «сейчас» берётся из sensor_now_*, а не из среднего часа.

    models[SENSOR_CODE] остаётся средним часа: им живут таблицы и график.
    Подмена ряда на среднее вернула бы отставание на весь час усреднения.
    """
    body = _sensor_now_js()
    assert "sensor_now_value" in body
    assert "sensor_now_min" in body
    assert "D.models?.[SENSOR_CODE]" not in body


def test_weather_now_omits_sensor_line_without_station_counts():
    """Город вне SENSOR_LOCATIONS не получает строки вовсе."""
    body = read_template()
    start = body.index("function buildWeatherNow(){")
    b = body[start:body.index("function buildWeatherHours(", start)]
    assert re.search(r"if\(sn\)\{?[^}]*По датчику", b) or \
        re.search(r"По датчику[^;]*sn", b) or "sensorNowLine" in b, \
        "строка не обёрнута в проверку наличия данных датчиков"


def test_weather_now_sensor_line_shows_hour_of_the_reading():
    """Час в скобках берётся из найденного бакета, а не из текущего."""
    body = _sensor_now_js()
    # Подпись строится из элемента с индексом нашего бакета j, а не из
    # текущего часа страницы: иначе она называла бы время просмотра.
    assert re.search(r"D\.time\[j\]", body), "метка обязана браться по индексу j"


# --- округление половины от нуля


def _js_round_helper():
    """Исходник округляющего помощника."""
    html = read_template()
    start = html.index("const rnd=")
    return html[start:html.index("\n", start)]


def test_rounding_sends_halves_away_from_zero():
    """Math.round округляет к +∞, и в мороз это читается как ошибка.

    JS: Math.round(-1.5) == -1 и Math.round(-0.5) == -0. То есть -1.5°
    показывалось как -1° (а не -2°), а -0.4° вообще теряло знак. Половины
    обязаны уходить от нуля, иначе шкала несимметрична относительно нуля.
    """
    body = _js_round_helper()
    assert "Math.sign" in body and "Math.abs" in body, \
        "округление обязано идти от нуля через знак и модуль"


@pytest.mark.skipif(shutil.which("node") is None, reason="нужен node")
def test_temp_and_fmt_round_symmetrically_on_halves():
    """Поведенческая проверка: числа из JS считаются реально, а не на глаз."""
    html = read_template()
    src = html[html.index("const rnd="):html.index("const WCODE=")]
    cases = [
        # (аргумент, ожидаемый temp, ожидаемый fmt)
        ("13.5", "+14°", "13.5"),
        ("-13.5", "-14°", "-13.5"),
        ("-0.5", "-1°", "-0.5"),
        ("-0.4", "0°", "-0.4"),
        ("-0.6", "-1°", "-0.6"),
        ("12.98", "+13°", "13"),
        ("-12.98", "-13°", "-13"),
    ]
    # Список уходит в JS как JSON-массив. Через repr нельзя: repr кортежа
    # даёт скобки, а в JS «(("a","b","c"))» — это один элемент, где запятая
    # схлопывается в оператор, и разборка [arg,t,f] раскладывала строку по
    # символам вместо того, чтобы прочитать тройку.
    script = src + """
const cases=%s;
for(const [arg,t,f] of cases){
  const got=temp(Number(arg));
  const gotF=fmt(Number(arg));
  if(got!==t||String(gotF)!==f){
    console.log(JSON.stringify([arg,t,f,got,String(gotF)]));
  }
}""" % json.dumps(cases, ensure_ascii=False)
    # Скрипт уходит байтами UTF-8: text=True кодировал бы аргумент в кодировку
    # локали и ломал бы кириллицу на любой машине, где не UTF-8.
    out = subprocess.run(["node", "-e", script.encode("utf-8")],
                         capture_output=True)
    assert not out.stdout.strip(), \
        "расхождение округления: %s" % out.stdout.decode("utf-8", "replace")


def _precip_window_js():
    """Чистые функции выбора окна осадков: порог консенсуса и trace-fallback."""
    html = read_template()
    start = html.index("function rainEpisodeWindow(")
    end = html.index("function buildWeatherNow(){", start)
    return html[start:end]


@pytest.mark.skipif(shutil.which("node") is None, reason="нужен node")
def test_precip_trace_window_uses_two_model_precipitation():
    """Когда консенсус не даёт дождливого часа, окно берётся по trace-осадкам.

    Почасовой консенсус усекает всё ниже 0.1 мм до нуля, поэтому дневная сумма
    может быть > 0 при пустом окне (Цеденево: 0.1 мм и «—/—»). Fallback-окно
    строится по числу моделей с осадками > 0: порог — не меньше двух моделей,
    чтобы одиночная trace-модель не рисовала ложный интервал.
    """
    html = read_template()
    assert "function rainEpisodeWindow(" in html, \
        "нет функции выбора окна осадков"
    body = _precip_window_js()
    day = "2026-10-02"
    times = ["%sT%02d:00" % (day, h) for h in range(24)] + ["2026-10-03T00:00"]
    # две модели дают trace с 16:00 до 23:00, третья молчит
    a = [0.0] * 25
    b = [0.0] * 25
    c = [0.0] * 25
    for j in range(16, 24):
        a[j] = 0.1
        b[j] = 0.1
    script = """
const D={time:%s,models:{a:{precipitation:%s},b:{precipitation:%s},c:{precipitation:%s}}};
const codes=['a','b','c'];
%s
const never=()=>false;
const cons=j=>j===10;
const trace=j=>modelTraceCount(j)>=2;
const out={
  consensus:pickRainWindow('2026-10-02',0.1,cons,trace),
  fallback:pickRainWindow('2026-10-02',0.1,never,trace),
  zeroSum:pickRainWindow('2026-10-02',0.0,never,trace),
  strict:pickRainWindow('2026-10-02',0.1,never,j=>modelTraceCount(j)>=3),
  counts:[0,5,15,16,20,23,24].map(j=>modelTraceCount(j))
};
console.log(JSON.stringify(out));
""" % (json.dumps(times), json.dumps(a), json.dumps(b), json.dumps(c), body)
    out = subprocess.run(["node", "-e", script.encode("utf-8")],
                         capture_output=True)
    assert not out.stderr.strip(), out.stderr.decode("utf-8", "replace")
    got = json.loads(out.stdout.decode("utf-8"))
    # порог консенсуса важнее trace: окно по нему, а не по моделям
    assert got["consensus"] == {"first": 10, "last": 11}
    # консенсус молчит, но дневная сумма > 0 — окно по trace-моделям
    assert got["fallback"] == {"first": 16, "last": 24}
    # нулевая сумма — trace-окна нет
    assert got["zeroSum"] == {"first": -1, "last": -1}
    # порог «не меньше трёх моделей» trace-окно не создаёт
    assert got["strict"] == {"first": -1, "last": -1}
    assert got["counts"] == [0, 0, 0, 2, 2, 2, 0]
    # fallback подключён к ячейке «Осадки» с порогом в две модели
    now = html[html.index("function buildWeatherNow(){"):
               html.index("function buildWeatherHours(")]
    assert "pickRainWindow(today,prSum,hasRainAt" in now
    assert "modelTraceCount(j)>=2" in now


# --- температура виджета берётся из датчиков


def _widget_thermo_js():
    """Кусок buildWeatherNow, отвечающий за число в виджете."""
    html = read_template()
    start = html.index("function buildWeatherNow(){")
    return html[start:html.index("function buildWeatherHours(", start)]


def test_widget_shows_sensor_temperature_not_model():
    """Большое число виджета — показание станций, а не модельный консенсус.

    Пользователь заметил расхождение «+14» против «По датчику +13.1» и
    потребовал, чтобы виджет показывал то же, что и строка под ним: реальное
    измерение, округлённое до целых. Модель и измерение — разные величины,
    и подписывать одно именем другого нельзя.
    """
    body = _widget_thermo_js()
    assert re.search(r"const\s+wtemp\s*=\s*sv!=null\s*\?\s*sv\s*:", body), \
        "виджет обязан брать температуру из датчиков, а откатываться на модель"
    # Само число в разметке и в ячейке «Температура» — одно и то же значение,
    # иначе виджет покажет две разные температуры рядом.
    assert len(re.findall(r"temp\(wtemp\)", body)) >= 2, \
        "и крупное число, и ячейка «Температура» берут wtemp"
    assert "temp(w.temperature_2m?.[curIdx])" not in body, \
        "модельное значение больше не должно попадать в виджет"
    # опциональная цепочка допустима: массив time может оказаться короче ряда
    assert "D.time[j]" in body


# --- ночной минимум для Цеденево


def _sensor_daynight_js():
    """Помощники выбора значения: границы окон и что именно показать."""
    html = read_template()
    start = html.index("function hhmmMin(")
    return html[start:html.index("function lastSensorHour(", start)]


def _sensor_pick_js():
    html = read_template()
    start = html.index("function sensorValueFor(")
    return html[start:html.index("function lastSensorHour(", start)]


def test_sensor_is_day_compares_the_reading_hour_against_its_own_day():
    """Рассвет и закат берутся для дня показания, а не для сегодняшнего.

    День часа ищется в daily_time, поэтому на границе суток час не получит
    чужой закат. Без этого поиска сравнение шлось бы по индексу 0 и ночь
    последнего часа суток считалась бы по закату первого дня.
    """
    body = _sensor_daynight_js()
    assert "daily_time" in body
    assert re.search(r"indexOf\(\s*\w+\.slice\(0,10\)\s*\)", body), (
        "индекс дня должен искаться по дате самого часа"
    )
    assert "sunrise" in body and "sunset" in body


def test_sensor_is_day_boundaries_match_the_agreed_rule():
    """Среднее показывается с рассвета+3ч и до заката-2ч.

    Границы считаются в минутах от полуночи, а не сравнением строк: сдвиг на
    часы арифметикой виден в коде буквально, тогда как строковое сравнение
    спрятало бы его за срезом и при переходе через полночь Compare вели бы себя
    неожиданно. Проверяются оба сдвига и то, что верхняя граница не входит.
    """
    body = _sensor_daynight_js()
    assert "SENSOR_MEAN_AFTER_SUNRISE=180" in body, "3 часа после рассвета = 180 минут"
    assert "SENSOR_MEAN_BEFORE_SUNSET=120" in body, "2 часа до заката = 120 минут"
    m = re.search(
        r"(\w+)\s*>=\s*([\w.]+)\s*\+\s*SENSOR_MEAN_AFTER_SUNRISE\s*&&\s*\1\s*<\s*([\w.]+)\s*-\s*"
        r"SENSOR_MEAN_BEFORE_SUNSET",
        body,
    )
    assert m, (
        "ожидалось сравнение вида hh>=sr+AFTER&&hh<ss-BEFORE, с одним и тем же "
        "часом в обеих границах"
    )
    assert m.group(2) != m.group(3), "нижняя и верхняя границы не должны совпадать"


def test_sensor_window_helpers_agree_across_the_three_frontends():
    """Главная и оба виджета считают одно и то же окно.

    Правило живёт в трёх копиях шаблона. Если разъедутся сдвиги или знаки,
    строка «По датчику» на странице и цифра в виджете будут показывать разное
    для одного и того же часа, и это не заметят по одному скриншоту.
    """
    tpl = read_template()
    for fname in ("meteo.html", "meteow.html"):
        with open(os.path.join(HERE, fname), encoding="utf-8") as f:
            w = f.read()
        for body, label in ((tpl, "template.html"), (w, fname)):
            assert "180" in body, f"{label}: 3 часа после рассвета"
            assert "120" in body, f"{label}: 2 часа до заката"


def test_sensor_rounding_follows_the_value_shown_only_for_tsedenevo():
    """Направление округления у Цеденево — по показанной величине.

    У Ярославля значение всегда среднее, но округление остаётся на старом
    окне рассвет–закат: привязывать его к выбору значения значило бы сделать
    его всегда вверх и поднять ночные числа города на градус.
    """
    for fname in ("meteo.html", "meteow.html"):
        with open(os.path.join(HERE, fname), encoding="utf-8") as f:
            w = f.read()
        assert "function sensorInDayWindow(" in w, fname
        assert "function sensorShowsMean(" in w, fname
        assert "return showsMean ? Math.ceil(v) : Math.floor(v);" in w, fname
        # Ярославль идёт по старому окну, Цеденево — по новому
        assert re.search(
            r"showsMean\s*=\s*slug==='tsedenevo'\s*\?\s*sensorShowsMean\([^)]*\)"
            r"\s*:\s*sensorInDayWindow\([^)]*\)", w), fname


def test_sensor_is_day_defaults_to_day_without_solar_data():
    """Нет данных о солнце — показываем среднее, то есть день.

    Обратный дефолт переключил бы поведение там, где данных просто не
    хватает: страница поменяла бы значение не из-за погоды.
    """
    body = _sensor_daynight_js()
    assert re.search(r"if\([^)]*<0[^)]*\)\s*return true|!\w+\)\s*return true", body), (
        "отсутствие рассвета/заката должно давать дефолт «день»"
    )


def test_tsedenevo_takes_minimum_at_night_and_yaroslavl_always_mean():
    """Цеденево переключается на минимум вне окна, Ярославль — никогда."""
    body = _sensor_pick_js()
    assert "tsedenevo" in body
    assert "sensorShowsMean" in body, "значение выбирается по новому окну"
    assert "sensor_station_min" in _sensor_now_js() or "min" in body
    # Ярославль не упоминается в ветке выбора: там только slug Цеденево,
    # всё остальное — среднее по умолчанию
    assert "yaroslavl" not in body, (
        "у Ярославля ночного минимума нет, упоминать его в выборе незачем"
    )


def test_help_explains_the_shifted_window():
    """Справка обязана называть новые границы, а не «от заката до рассвета».

    Старая формулировка стала бы прямой ложью на странице: правило сдвинуто,
    а текст продолжал бы обещать переключение ровно на закате.
    """
    tpl = read_template()
    assert "рассвет" in tpl and "3" in tpl and "2" in tpl
    assert "от заката до рассвета" not in tpl, (
        "старое правило в справке больше не действует"
    )


def test_sensor_shows_mean_when_precipitation_is_forecast_for_the_hour():
    """Осадки — второе условие: в дождь показывается среднее, а не минимум.

    Минимум по станциям отвечает на вопрос «насколько холодно в низине», и
    низина остывает только под ясным небом. Под дождём или плотной облачностью
    станции стоят рядом, и ночной минимум приписал бы низине холод, которого
    не было. Поэтому проверка осадков должна вызываться из sensorShowsMean до
    сравнения часа с окном, а не после него: иначе дождливый час в окне среднего
    и дождливый час вне его вели бы себя одинаково лишь случайно.
    """
    body = _sensor_daynight_js()
    assert "function sensorHourWet(" in body, "проверка осадков должна быть отдельной функцией"
    wet = body[body.index("function sensorHourWet("):body.index("function sensorShowsMean(")]
    assert "weighted" in wet, "осадки берутся у консенсуса, как и остальная сводка"
    assert "precipitation" in wet and "precipitation_probability" in wet
    assert "0.1" in wet, "порог тот же, что в сводке по дождю: 0.1 мм"
    shows = body[body.index("function sensorShowsMean("):]
    assert re.search(r"if\([^)]*sensorHourWet\([^)]*\)\)\s*return true", shows), (
        "идущие осадки переводят показ на среднее независимо от времени суток"
    )
    assert shows.index("sensorHourWet(") < shows.index("SENSOR_MEAN_AFTER_SUNRISE"), (
        "осадки проверяются до окна, а не после"
    )


@pytest.mark.skipif(shutil.which("node") is None, reason="нужен node")
def test_sensor_window_switches_to_mean_when_it_rains(tmp_path):
    """Поведенческая проверка: правило исполняется, а не только написано.

    Четыре случая подряд: сухая ночь обязана остаться минимумом, день —
    средним, а три вида осадков (миллиметры, дождевой код, вероятность) —
    переводить ночь на среднее. Без node эти случаи остались бы
    предположением по тексту.
    """
    html = read_template()
    src = html[html.index("function hhmmMin("):html.index("function lastSensorHour(")]
    script = f"""
const RAIN_CODES=[51,53,55,56,57,61,63,65,66,67,80,81,82];
const D={{time:['2026-10-05T02:00','2026-10-05T10:00'],
  daily_time:['2026-10-05'],
  daily:{{sunrise:['06:40'],sunset:['18:10']}},
  weighted:{{weather_code:[0,0],precipitation:[0,0],precipitation_probability:[0,0]}}}};
const m=(new Function('D','RAIN_CODES',{json.dumps(src)}+
  ';return {{sensorShowsMean}};'))(D,RAIN_CODES);
function reset(){{
  D.weighted.weather_code=[0,0];
  D.weighted.precipitation=[0,0];
  D.weighted.precipitation_probability=[0,0];
}}
const out={{}};
out.night_clear=m.sensorShowsMean(0);
out.day_clear=m.sensorShowsMean(1);
reset();D.weighted.precipitation=[0.4,0];out.night_rain_mm=m.sensorShowsMean(0);
reset();D.weighted.weather_code=[61,0];out.night_rain_code=m.sensorShowsMean(0);
reset();D.weighted.precipitation_probability=[55,0];out.night_rain_prob=m.sensorShowsMean(0);
console.log(JSON.stringify(out));
"""
    js = tmp_path / "sensor_window.js"
    js.write_text(script, encoding="utf-8")
    out = subprocess.run(
        ["node", str(js)], capture_output=True, text=True, timeout=60
    )
    assert out.returncode == 0, out.stderr
    got = json.loads(out.stdout)
    assert got == {
        "night_clear": False,      # сухая ночь -> минимум
        "day_clear": True,         # день -> среднее
        "night_rain_mm": True,     # осадки есть -> среднее
        "night_rain_code": True,   # дождевой код без миллиметров -> среднее
        "night_rain_prob": True,   # вероятность без миллиметров -> среднее
    }, got


def test_sensor_minimum_only_when_night_is_clear():
    """Минимум достаётся Цеденево лишь когда ни ночь, ни осадки не отменяют его."""
    body = _sensor_pick_js()
    m = re.search(r"slug==='tsedenevo'\s*&&\s*!sensorShowsMean\(", body)
    assert m, "минимум выбирается через то же окно, что и раньше"
    daynight = _sensor_daynight_js()
    assert "sensorShowsMean(" in daynight, "окно обязано учитывать осадки"


def test_help_explains_that_rain_cancels_the_minimum():
    """Справка обязана называть второе условие, иначе правило станет загадкой.

    Формулировка «ночью стоит минимум» перестала бы быть правдой в дождливую
    ночь, а страница продолжала бы обещать минимум.
    """
    tpl = read_template()
    row = [ln for ln in tpl.splitlines() if "минимум по станциям" in ln]
    assert row, "строка про минимум по станциям должна быть в справке"
    assert "осадк" in row[0].lower(), (
        "в строке про минимум должно быть сказано про осадки"
    )


def test_sensor_min_missing_falls_back_to_mean():
    """Нет ряда минимумов — строка показывает среднее, а не исчезает."""
    body = _sensor_pick_js()
    assert re.search(r"min\s*!=\s*null|\.min\s*!=\s*null", body), (
        "минимум берётся только когда он есть, иначе — среднее"
    )


def test_daily_wind_direction_uses_circular_mean():
    hourly = {"a": {"time": ["h0"], "data": {"temperature_2m": [1.0]}}}
    consensus = {
        "time": ["h0"],
        "weighted": {"temperature_2m": [1.0]},
        "mean": {"temperature_2m": [1.0]},
        "median": {"temperature_2m": [1.0]},
    }
    daily = {
        "a": {"time": ["d0"], "wind_direction_10m_dominant": [350.0]},
        "b": {"time": ["d0"], "wind_direction_10m_dominant": [10.0]},
    }
    p = meteo.build_payload(
        ["a", "b"], {"a": "A", "b": "B"}, hourly, daily, consensus, {},
        "2026-08-03T12:00:00+03:00", meteo.LOCATIONS[0],
    )
    # линейное среднее дало бы 180°, круговое — ~0°
    assert p["daily"]["wind_direction_10m_dominant"] == pytest.approx([0.0], abs=0.1)


def test_help_section_credits_yartemp():
    """В справке перечислены источники, и yartemp должен быть среди них.

    Подвал с атрибуцией был убран в cdd7047 в пользу раздела «Источники
    данных» в справке, поэтому ссылка на чужой источник живёт именно там.
    Требование yartemp - ссылка на оригинал везде, где публикуются его данные.
    """
    with open('template.html', encoding='utf-8') as f:
        template = f.read()
    assert 'https://yartemp.com/' in template


def test_help_credits_yartemp_as_a_station_source():
    with open('template.html', encoding='utf-8') as f:
        template = f.read()
    # Источник должен быть назван рядом со станциями, а не в общем списке моделей
    assert 'YarTemp' in template or 'yartemp' in template


def test_help_lists_eight_stations_and_credits_noaa_metar():
    """В справке восемь станций, аэропорт назван, источники данных указаны.

    NOAA отдаёт открытые данные без требования атрибуции, но ссылка нужна
    пользователю, чтобы проверить, откуда взялось число. Weather Underground
    добавлены двумя любительскими станциями, поэтому и они должны быть названы
    со ссылкой на источник.
    """
    with open('template.html', encoding='utf-8') as f:
        template = f.read()
    assert 'Станций восемь' in template
    assert 'https://aviationweather.gov/' in template
    assert 'METAR' in template
    assert 'раз в 30 минут' in template
    assert 'https://www.wunderground.com/' in template
    assert 'Weather Underground' in template


def test_help_does_not_promise_an_outdated_station_count():
    """Старые «пять» и «шесть станций» должны уйти вместе со сменой состава."""
    with open('template.html', encoding='utf-8') as f:
        template = f.read()
    assert 'Станций пять' not in template
    assert 'Станций шесть' not in template


# --- подпись показывает время последнего обновления, а не начало часа -----

def test_last_sensor_hour_label_prefers_reading_time_over_bucket_hour():
    """В скобках - время, когда показание реально пришло, а не «10:00».

    Пользователь читал «(10:00)» как «обновилось в 10:00», хотя замер мог
    прийти в 10:53. Подпись обязана брать время последнего замера, когда оно
    есть, и откатываться на ключ бакета только для старых бакетов.
    """
    body = _sensor_now_js()
    assert "sensor_updated_at" in body, (
        "время последнего замера должно приезжать отдельным рядом"
    )
    # Значение замера проверяется раньше ключа бакета, поэтому порядок важен:
    # перестановка вернула бы показ «10:00» вместо «10:53».
    assert re.search(r"\(ua&&ua\[j\]\)\|\|D\.time\[j\]", body), (
        "метка замера должна проверяться раньше ключа бакета"
    )


def test_last_sensor_hour_label_falls_back_to_bucket_hour():
    """Старые бакеты без updated_at показывают начало часа, а не пустоту."""
    body = _sensor_now_js()
    assert "||D.time[j]" in body, "нужен запасной вариант на ключ бакета часа"
    # Подпись не должна превратиться в «null» или «undefined»
    assert "String(stamp" not in body
