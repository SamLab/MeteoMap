import os
import re

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


def test_payload_without_sensor_has_no_station_counts():
    """Город без датчика не получает ключа: двух станций рядом с ним нет."""
    assert "sensor_station_counts" not in _payload()
    assert "sensor_station_min" not in _payload()


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
    # опциональная цепочка допустима: массив time может оказаться короче ряда
    assert re.search(r"D\.time\[j\]\??\.slice\(11,16\)", body)


# --- ночной минимум для Цеденево


def _sensor_daynight_js():
    """Помощники выбора значения: день/ночь и что именно показать."""
    html = read_template()
    start = html.index("function sensorIsDayAt(")
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
    """День — это sunrise <= час < sunset: рассвет включительно, закат нет.

    Проверяется структура сравнения, а не наличие подстрок: перевёрнутое
    условие даёт ночь днём на тех же данных, и любой тест на вхождение слова
    «sunrise» при этом проходит. Регулярка требует один и тот же левый
    операнд в обеих границах — иначе «день» вёл бы себя как «час не раньше
    рассвета ИЛИ час раньше заката», то есть почти всегда был бы днём.
    """
    body = _sensor_daynight_js()
    m = re.search(r"(\w+)>=(\w+)\.slice\(11,16\)&&\1<(\w+)\.slice\(11,16\)", body)
    assert m, (
        "ожидалось сравнение вида hh>=sr.slice(11,16)&&hh<ss.slice(11,16), с одним "
        "и тем же часом в обеих границах"
    )
    assert m.group(2) != m.group(3), "нижняя и верхняя границы не должны совпадать"


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
    """Цеденево переключается на минимум ночью, Ярославль — никогда."""
    body = _sensor_pick_js()
    assert "tsedenevo" in body
    assert "sensor_station_min" in _sensor_now_js() or "min" in body
    # Ярославль не упоминается в ветке выбора: там только slug Цеденево,
    # всё остальное — среднее по умолчанию
    assert "yaroslavl" not in body, (
        "у Ярославля ночного минимума нет, упоминать его в выборе незачем"
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


# --- атрибуция yartemp.com -------------------------------------------------
# FAQ yartemp: при использовании данных на другом сайте нужно ставить ссылку
# на оригинал, а выдавать их за свои без договорённости автор не разрешает.
# Ссылка появляется только там, где yartemp реально попал в данные: у города
# без датчиков упоминать чужой источник незачем.

YARTEMP_URL = "https://yartemp.com/"


def test_render_credits_yartemp_when_it_contributed():
    p = _payload()
    p["sensor_station_ids"] = [["penaty", "yartemp"], ["yartemp"], []]
    html = meteo.render("__ATTRIBUTION__", p)
    assert YARTEMP_URL in html
    assert "yartemp.com" in html


def test_render_omits_yartemp_when_it_did_not_contribute():
    p = _payload()
    p["sensor_station_ids"] = [["penaty"], ["penaty"], []]
    html = meteo.render("__ATTRIBUTION__", p)
    assert "yartemp.com" not in html


def test_render_omits_yartemp_for_cities_without_sensors():
    """Город без датчиков не должен упоминать источник датчиков."""
    html = meteo.render("__ATTRIBUTION__", _payload())
    assert "yartemp.com" not in html


def test_sensor_station_ids_reports_contributing_stations():
    """Клиенту нужно знать, какие станции попали в значение, чтобы показать источник."""
    from meteo import _sensor_station_ids

    bucket = {"stations": {"penaty": {"temperature_2m": [1.0, 3.0]},
                            "yartemp": {"temperature_2m": [2.0]},
                            "broken": {"temperature_2m": "nope"}}}
    ids = _sensor_station_ids(bucket, "temperature_2m")
    assert ids == ["penaty", "yartemp"]


def test_sensor_station_ids_matches_stations_used_by_hour_value():
    """Атрибуция и счётчик обязаны считать один и тот же список станций."""
    from meteo import _sensor_hour_value, _sensor_station_ids

    bucket = {"stations": {"penaty": {"temperature_2m": [1.0]},
                            "yartemp": {"temperature_2m": [2.0, 4.0]},
                            "broken": {"temperature_2m": "nope"}}}
    _, _, n = _sensor_hour_value(bucket, "temperature_2m")
    assert n == len(_sensor_station_ids(bucket, "temperature_2m"))
