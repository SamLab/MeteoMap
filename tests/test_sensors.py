import json
from datetime import datetime, timedelta, timezone

import pytest

from tools import collect_sensors as cs
from tools.collect_sensors import (
    HTTP_MAX_AGE_S,
    average_stations,
    fetch_metar,
    fetch_yartemp,
    history_hour_value,
    http_stations,
    load_history,
    load_stations,
    moscow_hour_key,
    moscow_now_ts,
    record_history,
    station_max_age_s,
    trim_history,
    validate,
)

PENATY_T = 'city/out/zavolga/penaty/temp/ws01'
EAST_H = 'city/out/east/hum'
EAST_T = 'city/out/east/temp/ds'


def test_parse_json_status_object_yields_value():
    assert cs.parse_payload('{"status":"20.4"}') == pytest.approx(20.4)


def test_parse_bare_number_yields_value():
    assert cs.parse_payload('13.62') == pytest.approx(13.62)


def test_parse_integer_yields_value():
    assert cs.parse_payload('9') == pytest.approx(9.0)


@pytest.mark.parametrize('raw', ['on', 'off', 'offline', 'up', '', 'null', 'STOP'])
def test_parse_non_numeric_status_yields_none(raw):
    assert cs.parse_payload(raw) is None


def test_parse_nested_json_yields_none():
    assert cs.parse_payload('{"date":"23.05.25, 08:48","so2":"0","h2s":"0.0009"}') is None


def test_parse_garbage_yields_none():
    assert cs.parse_payload('###') is None


def test_validate_accepts_temperature_in_range():
    assert cs.validate('temperature_2m', 20.4) is None


def test_validate_rejects_humidity_not_measured_anymore():
    # Влажность убрана из измерений сети. Правдоподобное значение всё равно
    # не проходит, потому что relative_humidity_2m больше нет в allowlist:
    # это делает stations.json строгим - вернуть влажность молча нельзя.
    reason = cs.validate('relative_humidity_2m', 71.6)
    assert reason is not None
    assert 'unknown parameter' in reason


def test_validate_rejects_pressure_not_measured_anymore():
    # Давление убрано по той же причине: заглушек не было, но станций было
    # всего две, разброс 4 гПа - сигнала меньше, чем шума от лишней колонки.
    reason = cs.validate('pressure_msl', 765.5)
    assert reason is not None
    assert 'unknown parameter' in reason


def test_validate_rejects_temperature_below_range():
    assert cs.validate('temperature_2m', -60.0) is not None


def test_validate_rejects_unknown_parameter():
    assert 'unknown parameter' in (cs.validate('ph', 7.0) or '')


def test_validate_rejects_wind_not_measured_by_network():
    # Ветер сеть нигде не меряет: правдоподобное значение всё равно не
    # проходит, потому что wind_speed_10m нет в allowlist.
    reason = cs.validate('wind_speed_10m', 0.0)
    assert reason is not None
    assert 'wind_speed_10m' in reason


def test_validate_rejects_nan():
    assert cs.validate('temperature_2m', float('nan')) is not None


def test_validate_rejects_pm25_not_measured_by_network():
    # PM2.5 тоже вне allowlist: канал frunze/pm2_5 исключён из конфига.
    reason = cs.validate('pm25', 2.8)
    assert reason is not None
    assert 'pm25' in reason


STATIONS = [
    {'id': 'penaty', 'name': 'Пенаты', 'lat': 57.6304, 'lon': 39.91527,
     'sensors': {'temperature_2m': PENATY_T}},
    {'id': 'east', 'name': 'Восток', 'lat': 57.62, 'lon': 39.92,
     'sensors': {'temperature_2m': EAST_T}},
]


def test_snapshot_marks_station_online_when_live_message_arrived():
    snap = cs.build_snapshot(STATIONS, {PENATY_T: '20.4'},
                             window_s=240, now=1000.0)
    st = {s['id']: s for s in snap['stations']}['penaty']
    assert st['online'] is True
    assert st['values']['temperature_2m'] == pytest.approx(20.4)


def test_snapshot_marks_station_offline_without_live_messages():
    snap = cs.build_snapshot(STATIONS, {}, window_s=240, now=1000.0)
    st = {s['id']: s for s in snap['stations']}['penaty']
    assert st['online'] is False
    assert st['age_s'] is None
    assert st['values'] == {}


def test_snapshot_records_rejected_value_with_reason():
    # Температура вне диапазона -50..50 отбрасывается с внятной причиной,
    # и станция остаётся offline: лучше пусто, чем правдоподобная дичь.
    snap = cs.build_snapshot(STATIONS, {EAST_T: '99.99'},
                             window_s=240, now=1000.0)
    st = {s['id']: s for s in snap['stations']}['east']
    assert st['online'] is False
    assert st['rejected']
    assert 'out of range' in st['rejected'][0]['reason']
    assert st['rejected'][0]['param'] == 'temperature_2m'


def test_snapshot_age_reflects_window_end():
    snap = cs.build_snapshot(STATIONS, {PENATY_T: '20.4'},
                             window_s=240, now=1000.0, seen={PENATY_T: 940.0})
    st = {s['id']: s for s in snap['stations']}['penaty']
    assert st['age_s'] == pytest.approx(60.0)


def test_snapshot_uses_latest_message_for_same_topic():
    seen = {PENATY_T: 900.0}
    snap = cs.build_snapshot(
        STATIONS,
        {PENATY_T: '18.0'},
        window_s=240, now=1000.0, seen=seen)
    st = {s['id']: s for s in snap['stations']}['penaty']
    # 18.0 пришёл позже 20.4 и перекрывает его
    assert st['values']['temperature_2m'] == pytest.approx(18.0)


def test_snapshot_carries_station_coordinates():
    snap = cs.build_snapshot(STATIONS, {}, window_s=240, now=1000.0)
    for s in snap['stations']:
        assert 'lat' in s and 'lon' in s and 'name' in s


def test_snapshot_records_generation_metadata():
    snap = cs.build_snapshot(STATIONS, {}, window_s=240, now=1000.0)
    assert snap['window_s'] == 240
    assert snap['generated_at']


def test_load_stations_reads_json(tmp_path):
    p = tmp_path / 'st.json'
    p.write_text(json.dumps({'stations': STATIONS}), encoding='utf-8')
    assert len(cs.load_stations(p)) == 2


def test_load_stations_rejects_duplicate_ids(tmp_path):
    dup = [dict(STATIONS[0]), dict(STATIONS[0])]
    p = tmp_path / 'st.json'
    p.write_text(json.dumps({'stations': dup}), encoding='utf-8')
    with pytest.raises(ValueError, match='duplicate'):
        cs.load_stations(p)


def test_load_stations_rejects_latitude_out_of_range(tmp_path):
    bad = [dict(STATIONS[0], lat=95.0)]
    p = tmp_path / 'st.json'
    p.write_text(json.dumps({'stations': bad}), encoding='utf-8')
    with pytest.raises(ValueError, match='lat'):
        cs.load_stations(p)


def test_load_stations_rejects_longitude_out_of_range(tmp_path):
    bad = [dict(STATIONS[0], lon=200.0)]
    p = tmp_path / 'st.json'
    p.write_text(json.dumps({'stations': bad}), encoding='utf-8')
    with pytest.raises(ValueError, match='lon'):
        cs.load_stations(p)


def test_load_stations_rejects_empty_topic(tmp_path):
    bad = [{'id': 'a', 'name': 'A', 'lat': 57.0, 'lon': 39.0,
            'sensors': {'temperature_2m': ''}}]
    p = tmp_path / 'st.json'
    p.write_text(json.dumps({'stations': bad}), encoding='utf-8')
    with pytest.raises(ValueError, match='topic'):
        cs.load_stations(p)


def test_load_stations_unknown_parameter_error_lists_allowlist(tmp_path):
    bad = [{'id': 'a', 'name': 'A', 'lat': 57.0, 'lon': 39.0,
            'sensors': {'wind_speed_10m': 'city/out/a'}}]
    p = tmp_path / 'st.json'
    p.write_text(json.dumps({'stations': bad}), encoding='utf-8')
    with pytest.raises(ValueError) as e:
        cs.load_stations(p)
    msg = str(e.value)
    assert 'wind_speed_10m' in msg
    for allowed in cs.SENSOR_PARAMS:
        assert allowed in msg


def test_load_stations_rejects_non_string_topic(tmp_path):
    bad = [{'id': 'a', 'name': 'A', 'lat': 57.0, 'lon': 39.0,
            'sensors': {'temperature_2m': 42}}]
    p = tmp_path / 'st.json'
    p.write_text(json.dumps({'stations': bad}), encoding='utf-8')
    with pytest.raises(ValueError, match='topic'):
        cs.load_stations(p)


def test_repository_stations_config_is_valid():
    stations = cs.load_stations(cs.DEFAULT_CONFIG)
    assert stations, 'stations.json must not be empty'
    assert len({s['id'] for s in stations}) == len(stations)
    # Сеть меряет только температуру. Влажность и давление убраты из
    # stations.json и из allowlist коллектора, поэтому load_stations не даст
    # вернуть их молча - проверка ниже это отдельно закрепляет.
    for st in stations:
        assert set(st['sensors']) == {'temperature_2m'}, st['id']


def test_repository_stations_config_window_covers_the_slowest_station():
    with open(cs.DEFAULT_CONFIG, encoding='utf-8') as f:
        settings = json.load(f)
    # Живой замер 700 с подписки (broker narodmon-mqtt public, tools/stations.json):
    # bereg публикует раз в 30 с, east раз в 60 с, а frunze и penaty — раз в
    # 300 с. Период был принят за ~2.5 мин, и на этом держалось обоснование
    # окна в 600 с. Окно должно быть не меньше периода самой медленной станки:
    # в любом интервале длиной >= периода гарантированно есть хотя бы одна
    # публикация, поэтому «молчание» в окне значит «станция молчит», а не
    # «мимо окна». 350 с — 50 с запаса сверх 300 с.
    assert settings['window_s'] >= 300, (
        "окно короче 300 с: frunze и penaty публикуют раз в 5 минут, и такие "
        "станции начнут выпадать из замеров"
    )


def test_repository_stations_config_subscribes_only_four_topics():
    with open(cs.DEFAULT_CONFIG, encoding='utf-8') as f:
        settings = json.load(f)
    # Считаются только mqtt-станции: у http-станции в sensors лежит URL, а не
    # топик, и в подписку он не попадает.
    mqtt = [st for st in settings['stations']
            if st.get('source', 'mqtt') == 'mqtt']
    topics = [t for st in mqtt for t in st['sensors'].values()]
    # Температуру отдают все четыре станции брокера, поэтому отказ от
    # влажности и давления не обесценил ни одну: 4 топика вместо 9.
    assert len(mqtt) == 4
    assert len(topics) == 4
    assert len(set(topics)) == 4


def test_load_stations_rejects_humidity_now_unmeasured(tmp_path):
    """Вернуть влажность в конфиг нельзя молча.

    SENSOR_PARAMS в коллекторе - единственный allowlist. Убрать из него
    параметр значит запретить его и в stations.json, так что возврат
    влажности падает на загрузке, а не всплывает на сайте.
    """
    bad = [{'id': 'a', 'name': 'A', 'lat': 57.0, 'lon': 39.0,
            'sensors': {'relative_humidity_2m': 'city/out/a/hum'}}]
    p = tmp_path / 'st.json'
    p.write_text(json.dumps({'stations': bad}), encoding='utf-8')
    with pytest.raises(ValueError, match='not measured by the network'):
        cs.load_stations(p)


class _FakeClient:
    """Минимальная замена paho: пишет сообщения в обработчик."""

    def __init__(self, script, connected=True):
        self.script = script
        self.connected = connected
        self.subs = []
        self.running = False
        self.on_connect = None
        self.on_message = None
        self.connect_calls = []

    def connect(self, *a, **kw):
        self.connect_calls.append((a, kw))
        if not self.connected:
            raise OSError('refused')

    def loop_start(self):
        self.running = True
        if self.connected:
            self.on_connect(self, None, {}, 0)
            for topic, payload, retain in self.script:
                self.on_message(self, None, _Msg(topic, payload, retain))
            self.running = False

    def loop_stop(self):
        self.running = False

    def subscribe(self, topic, qos=0):
        self.subs.append(topic)

    def disconnect(self):
        pass


class _Msg:
    def __init__(self, topic, payload, retain):
        self.topic = topic
        self.payload = payload.encode('utf-8')
        self.retain = retain


def test_collect_records_live_message():
    stations = [{'id': 'a', 'name': 'A', 'lat': 57.0, 'lon': 39.0,
                 'sensors': {'temperature_2m': 'city/out/a'}}]
    fake = _FakeClient([('city/out/a', '20.4', False)])

    got, seen = cs.collect(fake, stations, window_s=0)

    assert got['city/out/a'] == '20.4'
    assert 'city/out/a' in seen


def test_collect_ignores_retained_message():
    stations = [{'id': 'a', 'name': 'A', 'lat': 57.0, 'lon': 39.0,
                 'sensors': {'temperature_2m': 'city/out/a'}}]
    fake = _FakeClient([('city/out/a', '20.4', True)])

    got, _seen = cs.collect(fake, stations, window_s=0)

    assert got == {}, 'retained must not be treated as data'


def test_collect_subscribes_only_to_configured_topics():
    stations = [{'id': 'a', 'name': 'A', 'lat': 57.0, 'lon': 39.0,
                 'sensors': {'temperature_2m': 'city/out/a'}}]
    fake = _FakeClient([])

    cs.collect(fake, stations, window_s=0)

    assert fake.subs == ['city/out/a']


def test_collect_keeps_latest_value_per_topic():
    stations = [{'id': 'a', 'name': 'A', 'lat': 57.0, 'lon': 39.0,
                 'sensors': {'temperature_2m': 'city/out/a'}}]
    fake = _FakeClient([('city/out/a', '18.0', False),
                        ('city/out/a', '21.0', False)])

    got, _seen = cs.collect(fake, stations, window_s=0)

    assert got['city/out/a'] == '21.0'


def test_collect_disconnects_client():
    stations = [{'id': 'a', 'name': 'A', 'lat': 57.0, 'lon': 39.0,
                 'sensors': {'temperature_2m': 'city/out/a'}}]
    fake = _FakeClient([])

    cs.collect(fake, stations, window_s=0)

    assert fake.running is False


def test_run_writes_snapshot_file(tmp_path, monkeypatch):
    stations = [{'id': 'a', 'name': 'A', 'lat': 57.0, 'lon': 39.0,
                 'sensors': {'temperature_2m': 'city/out/a'}}]
    cfg = tmp_path / 'st.json'
    cfg.write_text(json.dumps({'stations': stations}), encoding='utf-8')
    out = tmp_path / 'sensors.json'
    fake = _FakeClient([('city/out/a', '20.4', False)])

    cs.run(client_factory=lambda *a, **kw: fake, config=cfg, out=out, window_s=0,
           history=str(tmp_path / 'h.json'))

    data = json.loads(out.read_text(encoding='utf-8'))
    assert data['stations'][0]['values']['temperature_2m'] == pytest.approx(20.4)


def test_run_returns_exit_code_zero(tmp_path):
    stations = [{'id': 'a', 'name': 'A', 'lat': 57.0, 'lon': 39.0,
                 'sensors': {'temperature_2m': 'city/out/a'}}]
    cfg = tmp_path / 'st.json'
    cfg.write_text(json.dumps({'stations': stations}), encoding='utf-8')

    code = cs.run(client_factory=lambda *a, **kw: _FakeClient([]),
                  config=cfg, out=tmp_path / 's.json', window_s=0,
                  history=str(tmp_path / 'h.json'))

    assert code == 0


def test_run_connects_to_broker_from_config(tmp_path):
    stations = [{'id': 'a', 'name': 'A', 'lat': 57.0, 'lon': 39.0,
                 'sensors': {'temperature_2m': 'city/out/a'}}]
    cfg = tmp_path / 'st.json'
    cfg.write_text(json.dumps({'broker': 'test.host', 'port': 8883,
                               'stations': stations}), encoding='utf-8')
    fake = _FakeClient([])

    cs.run(client_factory=lambda *a, **kw: fake, config=cfg,
           out=tmp_path / 's.json', window_s=0,
           history=str(tmp_path / 'h.json'))

    args, _kw = fake.connect_calls[0]
    assert args[0] == 'test.host'
    assert args[1] == 8883


# --- строгая схема конфига и усреднение по станциям ---


def test_config_rejects_two_topics_for_one_parameter(tmp_path):
    cfg = {
        "broker": "b", "port": 1883, "window_s": 10, "history_days": 30,
        "stations": [{
            "id": "s1", "name": "S1", "lat": 57.0, "lon": 39.0,
            "sensors": {"temperature_2m": ["a", "b"]},
        }],
    }
    p = tmp_path / "st.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    with pytest.raises(ValueError) as e:
        load_stations(str(p))
    assert "topic" in str(e.value).lower() or "строка" in str(e.value).lower()


def test_config_rejects_parameter_outside_allowlist(tmp_path):
    cfg = {
        "broker": "b", "port": 1883, "window_s": 10, "history_days": 30,
        "stations": [{
            "id": "s1", "name": "S1", "lat": 57.0, "lon": 39.0,
            "sensors": {"wind_speed_10m": "some/topic"},
        }],
    }
    p = tmp_path / "st.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    with pytest.raises(ValueError) as e:
        load_stations(str(p))
    assert "wind_speed_10m" in str(e.value)


def test_config_accepts_topic_string(tmp_path):
    cfg = {
        "broker": "b", "port": 1883, "window_s": 10, "history_days": 30,
        "stations": [{
            "id": "s1", "name": "S1", "lat": 57.0, "lon": 39.0,
            "sensors": {"temperature_2m": "some/topic"},
        }],
    }
    p = tmp_path / "st.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    got = load_stations(str(p))
    assert got[0]["sensors"]["temperature_2m"] == "some/topic"


def test_average_excludes_stations_without_live_value():
    per_station = [
        {"id": "a", "values": {"temperature_2m": 10.0}},
        {"id": "b", "values": {"temperature_2m": 20.0}},
        {"id": "c", "values": {}},
    ]
    got = average_stations(per_station)
    assert got["temperature_2m"]["value"] == 15.0
    assert got["temperature_2m"]["n"] == 2
    assert got["temperature_2m"]["stations"] == ["a", "b"]


def test_average_missing_parameter_is_absent_not_zero():
    got = average_stations([{"id": "a", "values": {"temperature_2m": 10.0}}])
    assert "pressure_msl" not in got


# --- накопление истории по часам ---


def test_record_history_merges_same_hour():
    hours = {"hours": {}}
    ok = record_history(hours, "2026-09-28T12:00",
                        [{"id": "a", "values": {"temperature_2m": 10.0}}])
    assert ok is True
    ok = record_history(hours, "2026-09-28T12:00",
                        [{"id": "a", "values": {"temperature_2m": 12.0}}])
    assert ok is True
    assert hours["hours"]["2026-09-28T12:00"]["samples"] == 2
    assert hours["hours"]["2026-09-28T12:00"]["stations"]["a"]["temperature_2m"] == [10.0, 12.0]


def test_record_history_new_hour_creates_bucket():
    hours = {"hours": {}}
    record_history(hours, "2026-09-28T13:00",
                   [{"id": "a", "values": {"temperature_2m": 10.0}}])
    assert list(hours["hours"]) == ["2026-09-28T13:00"]


# --- граница часа: замер раскладывается по часу прихода, а не старта прогона ---


def test_record_history_uses_hour_of_arrival_not_run_start():
    """Замер кладётся в бакет часа, который шёл в момент его прихода.

    Окно в 10 минут пересекает границу часа, и прогон, стартовавший в 22:55,
    честно добирает замеры часа 23:00. Класть их в 22:00 - тихая ошибка:
    на сайте час сдвинут на пять минут данных, и заметить это нельзя.
    """
    hours = {"hours": {}}
    late = cs.moscow_hour_key(cs.moscow_now_ts("2026-09-28T23:04"))
    assert late == "2026-09-28T23:00"
    record_history(hours, "2026-09-28T22:00", [
        {"id": "a", "values": {"temperature_2m": 10.0},
         "value_hours": {"temperature_2m": late}}])
    assert list(hours["hours"]) == ["2026-09-28T23:00"]
    assert hours["hours"]["2026-09-28T23:00"]["stations"]["a"]["temperature_2m"] == [10.0]


def test_record_history_keeps_early_sample_in_run_hour():
    """Замер до границы остаётся в часе старта прогона."""
    hours = {"hours": {}}
    early = cs.moscow_hour_key(cs.moscow_now_ts("2026-09-28T22:57"))
    assert early == "2026-09-28T22:00"
    record_history(hours, "2026-09-28T22:00", [
        {"id": "a", "values": {"temperature_2m": 10.0},
         "value_hours": {"temperature_2m": early}}])
    assert list(hours["hours"]) == ["2026-09-28T22:00"]


def test_record_history_splits_one_station_across_two_buckets():
    """Граница часа прошла между двумя прогонами.

    У станции по одному замеру в каждом бакете, и часовые значения не должны
    слиться в один - иначе на часовом графике появится ступенька там, где
    её не было.
    """
    hours = {"hours": {}}
    record_history(hours, "2026-09-28T22:00", [
        {"id": "a", "values": {"temperature_2m": 10.0},
         "value_hours": {"temperature_2m": "2026-09-28T22:00"}}])
    record_history(hours, "2026-09-28T22:00", [
        {"id": "a", "values": {"temperature_2m": 12.0},
         "value_hours": {"temperature_2m": "2026-09-28T23:00"}}])
    early = hours["hours"]["2026-09-28T22:00"]["stations"]["a"]["temperature_2m"]
    late = hours["hours"]["2026-09-28T23:00"]["stations"]["a"]["temperature_2m"]
    assert early == [10.0]
    assert late == [12.0]
    assert history_hour_value(hours["hours"]["2026-09-28T22:00"],
                              "temperature_2m")["value"] == 10.0
    assert history_hour_value(hours["hours"]["2026-09-28T23:00"],
                              "temperature_2m")["value"] == 12.0


def test_record_history_falls_back_to_run_hour_without_arrival_hours():
    """Прогон без времени прихода - прежнее поведение, час берётся у прогона.

    Так работают юнит-тесты и любой вызов без seen; молча разложить не по
    чему значило бы потерять замеры, а не получить более точные.
    """
    hours = {"hours": {}}
    record_history(hours, "2026-09-28T22:00", [
        {"id": "a", "values": {"temperature_2m": 10.0}}])
    assert list(hours["hours"]) == ["2026-09-28T22:00"]


def test_record_history_counts_station_contributions_not_runs():
    """samples описывает содержимое бакета: три станции - это три вклада.

    Старая арифметика "+1 за прогон" перестала бы описывать бакет, в который
    одна станция попала из трёх прогонов.
    """
    hours = {"hours": {}}
    record_history(hours, "2026-09-28T12:00", [
        {"id": "a", "values": {"temperature_2m": 10.0}},
        {"id": "b", "values": {"temperature_2m": 20.0}},
        {"id": "c", "values": {"temperature_2m": 30.0}}])
    assert hours["hours"]["2026-09-28T12:00"]["samples"] == 3


def test_snapshot_records_hour_of_arrival_per_param():
    """Снимок помнит час прихода по каждому параметру.

    Без этого record_history не сможет разложить замеры по бакетам: у него
    на руках только снимок станций, а не топики.
    """
    snap = cs.build_snapshot(
        STATIONS, {PENATY_T: "20.4"}, window_s=600, now=1000.0,
        seen={PENATY_T: cs.moscow_now_ts("2026-09-28T23:04")})
    st = {s["id"]: s for s in snap["stations"]}["penaty"]
    assert st["value_hours"]["temperature_2m"] == "2026-09-28T23:00"


def test_record_history_skips_empty_run():
    hours = {"hours": {}}
    assert record_history(hours, "2026-09-28T12:00", []) is False
    assert hours["hours"] == {}


def test_record_history_skips_run_where_no_station_reported():
    # Станция присутствует, но ни одного живого значения не принесла.
    hours = {"hours": {}}
    assert record_history(hours, "2026-09-28T12:00",
                          [{"id": "a", "values": {}}]) is False
    assert hours["hours"] == {}


def test_record_history_keeps_stations_equal_weight():
    hours = {"hours": {}}
    # Одна станция с одним замером не должна получать вес шести станций.
    record_history(hours, "2026-09-28T12:00", [
        {"id": "a", "values": {"temperature_2m": 10.0}},
        {"id": "b", "values": {"temperature_2m": 20.0}},
        {"id": "c", "values": {"temperature_2m": 30.0}},
        {"id": "d", "values": {"temperature_2m": 40.0}},
        {"id": "e", "values": {"temperature_2m": 50.0}},
        {"id": "f", "values": {"temperature_2m": 60.0}},
    ])
    record_history(hours, "2026-09-28T12:00",
                   [{"id": "a", "values": {"temperature_2m": 100.0}}])
    got = history_hour_value(hours["hours"]["2026-09-28T12:00"], "temperature_2m")
    # a: (10+100)/2 = 55, остальные 20..60 -> (55+20+30+40+50+60)/6 = 42.5
    assert got["value"] == 42.5
    assert got["n"] == 6


def test_trim_history_drops_old_buckets():
    hours = {"hours": {
        "2026-08-01T10:00": {"samples": 1, "stations": {}},
        "2026-09-28T10:00": {"samples": 1, "stations": {}},
    }}
    now = moscow_now_ts("2026-09-28T12:00")
    got = trim_history(hours, 30, now)
    assert list(got["hours"]) == ["2026-09-28T10:00"]


def test_load_history_missing_file_is_empty(tmp_path):
    got = load_history(str(tmp_path / "nope.json"))
    assert got == {"hours": {}}


def test_load_history_corrupt_file_is_empty(tmp_path):
    p = tmp_path / "h.json"
    p.write_text("{not json", encoding="utf-8")
    assert load_history(str(p)) == {"hours": {}}


def test_load_history_list_top_level_is_empty(tmp_path):
    # Файл руками отредактирован в чужую форму: сборка сайта получает пустую
    # историю, а не исключение на генерации.
    p = tmp_path / "h.json"
    p.write_text(json.dumps([{"hours": {"2026-09-28T12:00": {}}}]), encoding="utf-8")
    assert load_history(str(p)) == {"hours": {}}


def test_load_history_non_dict_hours_is_empty(tmp_path):
    p = tmp_path / "h.json"
    p.write_text(json.dumps({"hours": []}), encoding="utf-8")
    assert load_history(str(p)) == {"hours": {}}


def test_history_hour_value_is_none_when_no_station_reports_param():
    bucket = {"samples": 1, "stations": {"a": {"temperature_2m": [10.0]}}}
    assert history_hour_value(bucket, "pressure_msl") is None


def test_trim_history_keeps_bucket_at_exact_cutoff():
    # Граница включительная: бакет ровно в 30 дней назад остаётся, на час старше
    # отбрасывается. Знак сравнения «>=» вместо «>» — вот что здесь ловится.
    hours = {"hours": {
        "2026-08-29T11:00": {"samples": 1, "stations": {}},
        "2026-08-29T12:00": {"samples": 1, "stations": {}},
    }}
    now = moscow_now_ts("2026-09-28T12:00")
    got = trim_history(hours, 30, now)
    assert list(got["hours"]) == ["2026-08-29T12:00"]


# --- ключ бакета: московский час, а не локальный ---


WINTER_TS = datetime(2026, 1, 15, 21, 37, tzinfo=timezone.utc).timestamp()
SUMMER_TS = datetime(2026, 7, 15, 21, 37, tzinfo=timezone.utc).timestamp()


def test_moscow_hour_key_is_utc_plus_3_in_winter_and_summer():
    # Москва не переводит часы с 2014 года. Пара зима/лето — это и есть
    # разрешение использовать фиксированный UTC+3 вместо Europe/Moscow:
    # если бы в зоне оставался DST, эти два ключа разошлись бы.
    assert moscow_hour_key(WINTER_TS) == "2026-01-16T00:00"
    assert moscow_hour_key(SUMMER_TS) == "2026-07-16T00:00"


def test_history_tz_offset_is_utc_plus_3():
    # HISTORY_TZ — фиксированный UTC+3 и в системе без базы часовых поясов
    # (Windows без tzdata), и при её наличии: ключ обязан быть тем же.
    january = datetime(2026, 1, 15, 12, 0)
    july = datetime(2026, 7, 15, 12, 0)
    assert cs.HISTORY_TZ.utcoffset(january) == timedelta(hours=3)
    assert cs.HISTORY_TZ.utcoffset(july) == timedelta(hours=3)


@pytest.mark.parametrize("ts", [WINTER_TS, SUMMER_TS])
def test_moscow_hour_key_equals_fixed_utc_plus_3_key(ts):
    # ZoneInfo на этой машине не импортируется, поэтому эквивалентность
    # fallback проверяем явно посчитанным ключом UTC+3, а не через зону.
    expected = datetime.fromtimestamp(
        ts, timezone(timedelta(hours=3))).strftime("%Y-%m-%dT%H:00")
    assert moscow_hour_key(ts) == expected


def test_moscow_hour_key_is_not_machine_local():
    # 21:37 UTC — это 00:37 следующего дня по Москве, тот же самый момент.
    # Ключ обязан быть московским, а не тем, что видит машина.
    utc_key = datetime.fromtimestamp(
        SUMMER_TS, timezone.utc).strftime("%Y-%m-%dT%H:00")
    assert utc_key == "2026-07-15T21:00"
    assert moscow_hour_key(SUMMER_TS) != utc_key
    assert moscow_hour_key(SUMMER_TS) == "2026-07-16T00:00"


def test_load_history_drops_malformed_hour_bucket(tmp_path):
    # Бакет не той формы отбрасывается здесь же, а не упал бы в meteo.py на
    # values.get(param) при генерации сайта.
    p = tmp_path / "h.json"
    p.write_text(json.dumps({"hours": {
        "2026-09-28T12:00": {"samples": 1},
        "2026-09-28T13:00": ["not", "a", "bucket"],
        "2026-09-28T14:00": {"samples": 1, "stations": {"a": {"temperature_2m": [10.0]}}},
    }}), encoding="utf-8")
    got = load_history(str(p))
    assert list(got["hours"]) == ["2026-09-28T14:00"]


def test_history_hour_value_ignores_broken_station_in_good_bucket():
    # Сломанная станция внутри годного бакета: её данные теряются, но бакет и
    # данные соседних станций остаются — выкидывать весь час из-за одной
    # кривой записи в чужом файле незачем.
    bucket = {"samples": 1, "stations": {
        "a": "oops",
        "b": {"temperature_2m": [20.0]},
    }}
    assert history_hour_value(bucket, "temperature_2m") == {"value": 20.0, "n": 1}


def test_history_hour_value_skips_samples_that_are_not_a_list():
    # Та же гарантия на уровне чтения: чужое значение в samples — это «нет
    # данных», а не TypeError внутри sum().
    bucket = {"samples": 1, "stations": {
        "a": {"temperature_2m": "oops"},
        "b": {"pressure_msl": [1.0]},
        "c": {"temperature_2m": [20.0]},
    }}
    assert history_hour_value(bucket, "temperature_2m") == {"value": 20.0, "n": 1}


def test_history_hour_value_is_none_for_foreign_stations_shape():
    assert history_hour_value({"samples": 1, "stations": ["a"]},
                              "temperature_2m") is None
    assert history_hour_value({"samples": 1}, "temperature_2m") is None


@pytest.mark.parametrize("bad", [
    [None], ["hot"], [True, False], [{}], [[]], [None, 1.0], [1.0, "2.0"],
])
def test_history_hour_value_skips_samples_holding_non_numbers(bad):
    # Список-контейнер проверен, а его содержимое — нет: sum() внутри mean()
    # роняет прогон сборщика на TypeError, а meteo.py:_sensor_hour_value на том
    # же файле молча отдаёт «нет данных». Смысл обоих читателей обязан совпадать,
    # иначе один из них врёт сайту, а другой — отчёту.
    bucket = {"samples": 1, "stations": {"a": {"temperature_2m": bad}}}
    assert history_hour_value(bucket, "temperature_2m") is None


def test_history_hour_value_keeps_good_station_next_to_non_numbers():
    # Отбрасывается станция с чужими samples, а не весь час: кривая запись в
    # чужом файле не должна обнулять соседние станции.
    bucket = {"samples": 1, "stations": {
        "a": {"temperature_2m": [None]},
        "b": {"temperature_2m": [20.0]},
    }}
    assert history_hour_value(bucket, "temperature_2m") == {"value": 20.0, "n": 1}


# --- атомарная запись истории ---


def test_run_keeps_previous_history_when_write_is_interrupted(tmp_path, monkeypatch):
    # Прогон, убитый в середине записи, не должен обнулять накопленное:
    # битый файл load_history читает как пустую историю, и следующий прогон
    # записал бы в него один свежий бакет вместо тридцати дней.
    stations = [{"id": "a", "name": "A", "lat": 57.0, "lon": 39.0,
                 "sensors": {"temperature_2m": "city/out/a"}}]
    cfg = tmp_path / "st.json"
    cfg.write_text(json.dumps({"stations": stations}), encoding="utf-8")
    hist = tmp_path / "h.json"
    kept = '{"hours": {"2026-09-28T12:00": {"samples": 3, "stations": {}}}}'
    hist.write_text(kept, encoding="utf-8")

    real_dump = cs.json.dump

    def failing_dump(obj, fp, **kw):
        # Временный файл лежит рядом с целью, поэтому сверяем по началу пути.
        if str(getattr(fp, "name", "")).startswith(str(hist)):
            raise OSError("диск кончился в середине записи")
        return real_dump(obj, fp, **kw)

    monkeypatch.setattr(cs.json, "dump", failing_dump)

    with pytest.raises(OSError):
        cs.run(client_factory=lambda *a, **kw: _FakeClient([("city/out/a", "20.4", False)]),
               config=cfg, out=tmp_path / "s.json", window_s=0, history=str(hist))

    assert hist.read_text(encoding="utf-8") == kept


def test_run_leaves_no_temp_file_next_to_history(tmp_path):
    # history приходит и строкой, и Path — временный файл строится из того же
    # пути, что и цель, и не остаётся рядом с ней после записи.
    stations = [{"id": "a", "name": "A", "lat": 57.0, "lon": 39.0,
                 "sensors": {"temperature_2m": "city/out/a"}}]
    cfg = tmp_path / "st.json"
    cfg.write_text(json.dumps({"stations": stations}), encoding="utf-8")

    cs.run(client_factory=lambda *a, **kw: _FakeClient([("city/out/a", "20.4", False)]),
           config=cfg, out=tmp_path / "s.json", window_s=0,
           history=tmp_path / "h.json")

    assert sorted(p.name for p in tmp_path.iterdir()) == ["h.json", "s.json", "st.json"]


@pytest.mark.parametrize("bad", ["месяц", None, -5, 0])
def test_run_survives_garbage_history_days(tmp_path, bad):
    # history_days не должен ронять прогон уже после записи sensors.json и не
    # должен отсекать только что записанный бакет.
    stations = [{"id": "a", "name": "A", "lat": 57.0, "lon": 39.0,
                 "sensors": {"temperature_2m": "city/out/a"}}]
    cfg = tmp_path / "st.json"
    cfg.write_text(json.dumps({"history_days": bad, "stations": stations}),
                   encoding="utf-8")
    hist = tmp_path / "h.json"

    code = cs.run(client_factory=lambda *a, **kw: _FakeClient([("city/out/a", "20.4", False)]),
                  config=cfg, out=tmp_path / "s.json", window_s=0, history=str(hist))

    assert code == 0
    assert len(json.loads(hist.read_text(encoding="utf-8"))["hours"]) == 1


# --- yartemp.com: пятая станция, только температура -----------------------
# Формат ответа: одна строка, поля через ";". Поле [0] - температура,
# поле [1] - unix-время САМОГО ЗАМЕРА (не время отдачи страницы).

YARTEMP_URL = 'https://yartemp.com/webdata/'
YARTEMP_BODY = '8.090;1790708310;-0.146;3.193;9.819;-1;-1;-0.864;21.825;06:19;18:02;11:43;-29.172;0.883;18.096;5;3;766.8;0;-1;730.0;770.0;0.1'


class _FakeResponse:
    def __init__(self, text, status=200):
        self.text = text
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError('HTTP %d' % self.status_code)


class _FakeSession:
    """Записывает запросы и отдаёт заготовленный ответ."""

    def __init__(self, text='8.090;1790708310', status=200, raises=None):
        self.text = text
        self.status = status
        self.raises = raises
        self.calls = []

    def get(self, url, **kw):
        self.calls.append((url, kw))
        if self.raises is not None:
            raise self.raises
        return _FakeResponse(self.text, self.status)


def test_fetch_yartemp_takes_temperature_and_reading_time():
    """Берутся только поле [0] как значение и поле [1] как метка замера."""
    payload, reading_ts = fetch_yartemp(
        YARTEMP_URL, now=1790708310.0, session=_FakeSession(YARTEMP_BODY))
    assert payload == '8.090'
    assert reading_ts == 1790708310.0


def test_fetch_yartemp_sends_cache_busting_query_and_referer():
    """Сайт сам так ходит: query с меняющимся числом и Referer на главную."""
    session = _FakeSession(YARTEMP_BODY)
    fetch_yartemp(YARTEMP_URL, now=1790708310.0, session=session)
    url, kw = session.calls[0]
    assert url.startswith(YARTEMP_URL + '?')
    assert kw['headers']['Referer'] == 'https://yartemp.com/'


def test_fetch_yartemp_returns_none_for_garbage():
    """Мусор вместо числа - это «нет данных», а не исключение."""
    assert fetch_yartemp(YARTEMP_URL, now=1.0,
                         session=_FakeSession('nope;123')) == (None, None)


def test_fetch_yartemp_returns_none_when_body_has_no_timestamp():
    """Без поля [1] свежесть неизвестна, поэтому значение не принимается."""
    assert fetch_yartemp(YARTEMP_URL, now=1.0,
                         session=_FakeSession('8.090')) == (None, None)


def test_fetch_yartemp_returns_none_on_empty_body():
    assert fetch_yartemp(YARTEMP_URL, now=1.0,
                         session=_FakeSession('')) == (None, None)


def test_fetch_yartemp_survives_network_error():
    """Чужой сайт не должен ронять публикацию sensors_history.json."""
    assert fetch_yartemp(
        YARTEMP_URL, now=1.0,
        session=_FakeSession(raises=OSError('connection reset'))) == (None, None)


def test_fetch_yartemp_survives_http_error():
    assert fetch_yartemp(
        YARTEMP_URL, now=1.0,
        session=_FakeSession('oops', status=503)) == (None, None)


def test_fetch_yartemp_survives_html_instead_of_data():
    """Если вместо данных придёт HTML (смена формата) - тихо None."""
    assert fetch_yartemp(
        YARTEMP_URL, now=1.0,
        session=_FakeSession('<html><body>404</body></html>')) == (None, None)


def test_http_stations_selects_only_explicit_http_sources():
    stations = [
        {'id': 'a', 'sensors': {'temperature_2m': 'city/out/a'}},
        {'id': 'b', 'source': 'http',
         'sensors': {'temperature_2m': YARTEMP_URL}},
        {'id': 'c', 'source': 'mqtt', 'sensors': {'temperature_2m': 'x/y'}},
    ]
    assert [st['id'] for st in http_stations(stations)] == ['b']


def test_stale_yartemp_reading_is_not_injected(tmp_path, monkeypatch):
    """Замер старше порога не попадает в среднее: станция молчит."""
    now = 1790708310.0
    stale = now - HTTP_MAX_AGE_S - 1
    stations = [{'id': 'yt', 'name': 'Y', 'lat': 57.6, 'lon': 39.9,
                 'source': 'http', 'sensors': {'temperature_2m': YARTEMP_URL}}]
    cfg = tmp_path / 'st.json'
    cfg.write_text(json.dumps({'stations': stations}), encoding='utf-8')
    out = tmp_path / 'sensors.json'

    monkeypatch.setattr(cs.time, 'time', lambda: now)
    monkeypatch.setattr(cs, 'fetch_yartemp', lambda url, **kw: ('8.090', stale))

    cs.run(client_factory=lambda *a, **kw: _FakeClient([]), config=cfg, out=out,
           window_s=0, history=str(tmp_path / 'h.json'))

    data = json.loads(out.read_text(encoding='utf-8'))
    assert data['stations'][0]['online'] is False
    assert data['stations'][0]['values'] == {}


def test_fresh_yartemp_reading_is_counted_like_an_mqtt_station(tmp_path, monkeypatch):
    """Свежий HTTP-чтение проходит ровно тем же путём, что и MQTT."""
    now = 1790708310.0
    stations = [{'id': 'yt', 'name': 'Y', 'lat': 57.6, 'lon': 39.9,
                 'source': 'http', 'sensors': {'temperature_2m': YARTEMP_URL}}]
    cfg = tmp_path / 'st.json'
    cfg.write_text(json.dumps({'stations': stations}), encoding='utf-8')
    out = tmp_path / 'sensors.json'
    hist = tmp_path / 'h.json'

    monkeypatch.setattr(cs.time, 'time', lambda: now)
    monkeypatch.setattr(cs, 'fetch_yartemp',
                        lambda url, **kw: ('8.09', now - 60))

    cs.run(client_factory=lambda *a, **kw: _FakeClient([]), config=cfg, out=out,
           window_s=0, history=str(hist))

    data = json.loads(out.read_text(encoding='utf-8'))
    st = data['stations'][0]
    assert st['online'] is True
    assert st['values']['temperature_2m'] == pytest.approx(8.09)
    # age считается от метки ЗАМЕРА, а не от времени нашего запроса
    assert st['age_s'] == pytest.approx(60.0, abs=1)
    # и значение попало в историю
    hours = json.loads(hist.read_text(encoding='utf-8'))['hours']
    assert hours


def test_failing_yartemp_does_not_break_mqtt_stations(tmp_path, monkeypatch):
    """Падение одного источника не должно обнулить остальные станции."""
    now = 1790708310.0
    stations = [
        {'id': 'a', 'name': 'A', 'lat': 57.0, 'lon': 39.0,
         'sensors': {'temperature_2m': 'city/out/a'}},
        {'id': 'yt', 'name': 'Y', 'lat': 57.6, 'lon': 39.9,
         'source': 'http', 'sensors': {'temperature_2m': YARTEMP_URL}},
    ]
    cfg = tmp_path / 'st.json'
    cfg.write_text(json.dumps({'stations': stations}), encoding='utf-8')
    out = tmp_path / 'sensors.json'
    fake = _FakeClient([('city/out/a', '20.4', False)])

    monkeypatch.setattr(cs.time, 'time', lambda: now)
    monkeypatch.setattr(cs, 'fetch_yartemp', lambda url, **kw: (None, None))

    cs.run(client_factory=lambda *a, **kw: fake, config=cfg, out=out, window_s=0,
           history=str(tmp_path / 'h.json'))

    data = json.loads(out.read_text(encoding='utf-8'))
    assert data['stations'][0]['values']['temperature_2m'] == pytest.approx(20.4)
    assert data['stations'][1]['online'] is False


def test_http_station_is_never_subscribed_over_mqtt():
    """URL не должен попадать в подписку: collect берёт только mqtt-станции."""
    stations = [
        {'id': 'a', 'sensors': {'temperature_2m': 'city/out/a'}},
        {'id': 'yt', 'source': 'http', 'sensors': {'temperature_2m': YARTEMP_URL}},
    ]
    client = _FakeClient([('city/out/a', '20.4', False)])
    cs.collect(client, stations, 0)
    assert client.subs == ['city/out/a']


def test_repository_config_has_eight_stations_with_three_network_sources():
    with open(cs.DEFAULT_CONFIG, encoding='utf-8') as f:
        settings = json.load(f)
    stations = settings['stations']
    assert len(stations) == 8
    http = [st for st in stations if st.get('source') == 'http']
    metar = [st for st in stations if st.get('source') == 'metar']
    wu = [st for st in stations if st.get('source') == 'wu']
    assert len(http) == 1
    assert http[0]['id'] == 'yartemp'
    assert len(metar) == 1
    assert metar[0]['id'] == 'uudl'
    assert len(wu) == 2
    assert {st['id'] for st in wu} == {'wu-ananyino', 'wu-zavolzhskoe'}
    # у всех станций только температура, как и у MQTT-станций
    for st in stations:
        assert list(st['sensors']) == ['temperature_2m']


def test_metar_station_in_config_points_at_uudl_with_its_own_threshold():
    """Код аэропорта и его собственный порог закреплены конфигом.

    UUDL - аэропорт Ярославля; ULLK в каталоге NOAA не существует, и первая
    попытка работы с ним молча дала ложный вывод, что станция не отдаёт METAR.

    Порог 2400 с обязателен и не избыточен: общий порог 900 с короче
    получасовой периодичности сводок, и без собственного станция не отдала бы
    ни одного значения - молча, без ошибок.
    """
    with open(cs.DEFAULT_CONFIG, encoding='utf-8') as f:
        settings = json.load(f)
    metar = [st for st in settings['stations'] if st.get('source') == 'metar'][0]
    assert metar['sensors']['temperature_2m'] == 'UUDL'
    # 30-минутная периодичность источника плюс запас
    assert metar['max_age_s'] == 2400
    # координаты аэропорта из каталога NOAA, а не координаты соседней станции
    assert (metar['lat'], metar['lon']) == (57.561, 40.157)


def test_fetch_metar_rejects_a_report_for_another_airport():
    """Сводка чужого аэропорта не должна выдаваться за нашу станцию.

    NOAA на несуществующий код отвечает 204 с пустым телом, и без сверки
    icaoId опечатка в конфиге выглядела бы как «аэропорт не отвечает» - молча,
    при каждом прогоне. С несуществующим ULLK так уже случилось однажды.
    """
    session = _FakeSession(_metar_body())
    fetcher = cs.station_fetcher({'source': 'metar'})
    payload, reading_ts = fetcher('UUDL', now=1.0, session=_FakeSession(
        json.dumps([{'icaoId': 'UUDR', 'temp': 14,
                     'reportTime': METAR_REPORT_ISO}])))
    assert (payload, reading_ts) == (None, None)

    # а свой код проходит - сверка не должна отвергать всё подряд
    ok_payload, ok_ts = fetcher('UUDL', now=1.0, session=session)
    assert ok_payload == '16.0'
    assert ok_ts == pytest.approx(
        datetime(2026, 9, 30, 9, 30, tzinfo=timezone.utc).timestamp(), abs=1)


def test_repository_metar_station_survives_validation_and_network_selection():
    """Шестая станция проходит проверки конфига и попадает в сетевой опрос.

    Тест работает с настоящим tools/stations.json, а не с рукописной копией:
    копия разъехалась бы с файлом незаметно, и расхождение никто бы не увидел.
    """
    stations = cs.load_stations(cs.DEFAULT_CONFIG)
    uudl = [st for st in stations if st['id'] == 'uudl'][0]
    assert uudl['source'] == 'metar'
    assert cs.station_max_age_s(uudl) == 2400
    # сетевой опрос её берёт, а подписка по MQTT - нет
    assert 'uudl' in [st['id'] for st in cs.http_stations(stations)]
    mqtt_ids = [st['id'] for st in stations if st.get('source', 'mqtt') == 'mqtt']
    assert 'uudl' not in mqtt_ids


def test_repository_metar_station_reaches_a_real_url_through_the_real_dispatch():
    """Токен из боевого конфига доезжает до запроса как настоящий адрес.

    Здесь нет подмены адаптера: берётся запись из stations.json, прогоняется
    через station_fetcher, и единственное подменённое - сессия. Именно так
    станция молчала бы в бою, если бы токен ушёл в get() как есть.
    """
    with open(cs.DEFAULT_CONFIG, encoding='utf-8') as f:
        settings = json.load(f)
    uudl = [st for st in settings['stations'] if st.get('source') == 'metar'][0]
    token = uudl['sensors']['temperature_2m']

    session = _FakeSession(_metar_body())
    fetcher = cs.station_fetcher(uudl)
    payload, reading_ts = fetcher(token, now=1.0, session=session)

    assert session.calls[0][0] == METAR_URL
    assert payload == '16.0'
    assert reading_ts is not None


def test_load_stations_accepts_source_field(tmp_path):
    """Явный source=http валиден; отсутствие поля означает mqtt."""
    stations = [
        {'id': 'a', 'name': 'A', 'lat': 57.0, 'lon': 39.0,
         'sensors': {'temperature_2m': 'city/out/a'}},
        {'id': 'yt', 'name': 'Y', 'lat': 57.6, 'lon': 39.9, 'source': 'http',
         'sensors': {'temperature_2m': YARTEMP_URL}},
    ]
    cfg = tmp_path / 'st.json'
    cfg.write_text(json.dumps({'stations': stations}), encoding='utf-8')
    loaded = load_stations(cfg)
    assert loaded[0].get('source', 'mqtt') == 'mqtt'
    assert loaded[1]['source'] == 'http'


def test_load_stations_rejects_unknown_source(tmp_path):
    stations = [{'id': 'a', 'name': 'A', 'lat': 57.0, 'lon': 39.0,
                 'source': 'carrier-pigeon',
                 'sensors': {'temperature_2m': 'city/out/a'}}]
    cfg = tmp_path / 'st.json'
    cfg.write_text(json.dumps({'stations': stations}), encoding='utf-8')
    with pytest.raises(ValueError, match='source'):
        load_stations(cfg)


def test_future_timestamp_is_clamped_to_poll_time(tmp_path, monkeypatch):
    """Часы источника спешат: метка из будущего не должна выглядеть свежее прогона."""
    now = 1790708310.0
    stations = [{'id': 'yt', 'name': 'Y', 'lat': 57.6, 'lon': 39.9,
                 'source': 'http', 'sensors': {'temperature_2m': YARTEMP_URL}}]
    cfg = tmp_path / 'st.json'
    cfg.write_text(json.dumps({'stations': stations}), encoding='utf-8')
    out = tmp_path / 'sensors.json'

    monkeypatch.setattr(cs.time, 'time', lambda: now)
    # источник на 5 секунд впереди нас
    monkeypatch.setattr(cs, 'fetch_yartemp',
                        lambda url, **kw: ('8.09', now + 5))

    cs.run(client_factory=lambda *a, **kw: _FakeClient([]), config=cfg, out=out,
           window_s=0, history=str(tmp_path / 'h.json'))

    data = json.loads(out.read_text(encoding='utf-8'))
    st = data['stations'][0]
    assert st['online'] is True
    assert st['age_s'] >= 0


# --- время последнего обновления вместо начала часа ----------------------
# Раньше строка показывала D.time[j] - ключ бакета, то есть начало часа.
# Пользователь читает это как "данные обновились в 10:00", что неправда:
# показание могло прийти в 10:53.

def test_snapshot_records_arrival_timestamp_per_param():
    """Время прихода замера не должно теряться: из него делается метка часа."""
    st = {"id": "a", "name": "A", "lat": 57.0, "lon": 39.0,
          "sensors": {"temperature_2m": "city/out/a"}}
    ts = 1790708310.0
    snap = cs.build_snapshot([st], {"city/out/a": "20.4"}, 350, ts,
                             {"city/out/a": ts})
    assert snap["stations"][0]["value_ts"]["temperature_2m"] == ts


def test_record_history_stores_latest_reading_time_in_bucket():
    """В бакет пишется ISO-время последнего пришедшего замера."""
    hours = {"hours": {}}
    # 10:53 МСК = 07:53 UTC
    ts = datetime(2026, 9, 28, 7, 53, tzinfo=timezone.utc).timestamp()
    per_station = [{"id": "a", "values": {"temperature_2m": 20.4},
                    "value_hours": {"temperature_2m": "2026-09-28T10:00"},
                    "value_ts": {"temperature_2m": ts}}]
    cs.record_history(hours, "2026-09-28T10:00", per_station)
    assert hours["hours"]["2026-09-28T10:00"]["updated_at"].startswith(
        "2026-09-28T10:53")


def test_record_history_keeps_the_newest_of_two_runs():
    """Поздний прогон дописывает замер и двигает метку, ранний - не откатывает."""
    hours = {"hours": {}}
    early = datetime(2026, 9, 28, 7, 5, tzinfo=timezone.utc).timestamp()
    late = datetime(2026, 9, 28, 7, 53, tzinfo=timezone.utc).timestamp()
    for ts in (late, early):
        cs.record_history(hours, "2026-09-28T10:00", [
            {"id": "a", "values": {"temperature_2m": 20.4},
             "value_hours": {"temperature_2m": "2026-09-28T10:00"},
             "value_ts": {"temperature_2m": ts}}])
    bucket = hours["hours"]["2026-09-28T10:00"]
    assert bucket["updated_at"].startswith("2026-09-28T10:53")
    assert len(bucket["stations"]["a"]["temperature_2m"]) == 2


def test_record_history_falls_back_to_bucket_hour_without_arrival_time():
    """Прогон без времени прихода (юнит-тесты, --dry) даёт начало часа."""
    hours = {"hours": {}}
    cs.record_history(hours, "2026-09-28T10:00", [
        {"id": "a", "values": {"temperature_2m": 20.4},
         "value_hours": {"temperature_2m": "2026-09-28T10:00"}}])
    assert hours["hours"]["2026-09-28T10:00"]["updated_at"].startswith(
        "2026-09-28T10:00")


def test_record_history_uses_max_across_stations():
    """Метка бакета - время самого позднего замера из всех станций."""
    hours = {"hours": {}}
    fast = datetime(2026, 9, 28, 7, 10, tzinfo=timezone.utc).timestamp()
    slow = datetime(2026, 9, 28, 7, 40, tzinfo=timezone.utc).timestamp()
    cs.record_history(hours, "2026-09-28T10:00", [
        {"id": "a", "values": {"temperature_2m": 20.4},
         "value_hours": {"temperature_2m": "2026-09-28T10:00"},
         "value_ts": {"temperature_2m": fast}},
        {"id": "b", "values": {"temperature_2m": 19.0},
         "value_hours": {"temperature_2m": "2026-09-28T10:00"},
         "value_ts": {"temperature_2m": slow}}])
    assert hours["hours"]["2026-09-28T10:00"]["updated_at"].startswith(
        "2026-09-28T10:40")


# --- порог свежести у каждой станции свой -------------------------------
# METAR обновляется раз в 30 минут, поэтому общий порог в 15 минут убил бы
# его полностью: станция молчала бы в каждом прогоне. Порог становится
# свойством станции, а не свойством транспорта.


def test_station_max_age_s_defaults_to_the_shared_constant():
    assert station_max_age_s({'id': 'a'}) == HTTP_MAX_AGE_S


def test_station_max_age_s_is_taken_from_the_station():
    assert station_max_age_s({'id': 'a', 'max_age_s': 2400}) == 2400


def test_station_without_max_age_s_keeps_the_old_freshness_behaviour(tmp_path, monkeypatch):
    """Станция без нового поля ведёт себя ровно как раньше: 15 минут."""
    now = 1790708310.0
    stations = [{'id': 'yt', 'name': 'Y', 'lat': 57.6, 'lon': 39.9,
                 'source': 'http', 'sensors': {'temperature_2m': YARTEMP_URL}}]
    cfg = tmp_path / 'st.json'
    cfg.write_text(json.dumps({'stations': stations}), encoding='utf-8')
    out = tmp_path / 'sensors.json'

    monkeypatch.setattr(cs.time, 'time', lambda: now)
    # чуть старше общей границы: станция обязана промолчать, как раньше
    monkeypatch.setattr(cs, 'fetch_yartemp',
                        lambda url, **kw: ('8.09', now - HTTP_MAX_AGE_S - 60))

    cs.run(client_factory=lambda *a, **kw: _FakeClient([]), config=cfg, out=out,
           window_s=0, history=str(tmp_path / 'h.json'))

    data = json.loads(out.read_text(encoding='utf-8'))
    assert data['stations'][0]['online'] is False


def test_station_with_own_max_age_s_keeps_a_reading_older_than_the_shared_one(tmp_path, monkeypatch):
    """Собственный порог реально применяется, а не просто хранится в конфиге.

    Замер на 20 минут старше для yartemp протух бы, а METAR выходит раз в
    30 минут: без собственного порога такая станция молчала бы в каждом прогоне
    и не дала бы ни одного числа.
    """
    now = 1790708310.0
    stations = [{'id': 'metar', 'name': 'M', 'lat': 57.6, 'lon': 39.9,
                 'source': 'http', 'max_age_s': 2400,
                 'sensors': {'temperature_2m': YARTEMP_URL}}]
    cfg = tmp_path / 'st.json'
    cfg.write_text(json.dumps({'stations': stations}), encoding='utf-8')
    out = tmp_path / 'sensors.json'

    monkeypatch.setattr(cs.time, 'time', lambda: now)
    monkeypatch.setattr(cs, 'fetch_yartemp',
                        lambda url, **kw: ('8.09', now - HTTP_MAX_AGE_S - 300))

    cs.run(client_factory=lambda *a, **kw: _FakeClient([]), config=cfg, out=out,
           window_s=0, history=str(tmp_path / 'h.json'))

    data = json.loads(out.read_text(encoding='utf-8'))
    st = data['stations'][0]
    assert st['online'] is True
    assert st['values']['temperature_2m'] == pytest.approx(8.09)


# --- третий транспорт: metar --------------------------------------------

METAR_URL = 'https://aviationweather.gov/api/data/metar?format=json&ids=UUDL&hours=1'


def test_metar_is_a_valid_source(tmp_path):
    stations = [{'id': 'uudl', 'name': 'A', 'lat': 57.561, 'lon': 40.157,
                 'source': 'metar', 'sensors': {'temperature_2m': 'UUDL'}}]
    cfg = tmp_path / 'st.json'
    cfg.write_text(json.dumps({'stations': stations}), encoding='utf-8')
    assert load_stations(cfg)[0]['source'] == 'metar'


def test_load_stations_rejects_non_positive_max_age(tmp_path):
    """Ноль или минус означали бы «отбрасывать всё», поэтому это ошибка конфига."""
    for bad in (0, -1):
        stations = [{'id': 'yt', 'name': 'Y', 'lat': 57.6, 'lon': 39.9,
                     'source': 'http', 'max_age_s': bad,
                     'sensors': {'temperature_2m': YARTEMP_URL}}]
        cfg = tmp_path / 'st.json'
        cfg.write_text(json.dumps({'stations': stations}), encoding='utf-8')
        with pytest.raises(ValueError, match='max_age_s'):
            load_stations(cfg)


def test_load_stations_rejects_non_numeric_max_age(tmp_path):
    stations = [{'id': 'yt', 'name': 'Y', 'lat': 57.6, 'lon': 39.9,
                 'source': 'http', 'max_age_s': 'half an hour',
                 'sensors': {'temperature_2m': YARTEMP_URL}}]
    cfg = tmp_path / 'st.json'
    cfg.write_text(json.dumps({'stations': stations}), encoding='utf-8')
    with pytest.raises(ValueError, match='max_age_s'):
        load_stations(cfg)


def test_load_stations_rejects_null_max_age(tmp_path):
    """Явный null - это не «поля нет», а запрещённое значение.

    station_max_age_s отдаёт поле как есть, поэтому None доехал бы до
    сравнения now - reading_ts > None и уронил прогон TypeError уже после
    того, как эфир прослушан. Ошибка конфига обязана звучать на загрузке,
    где её ещё можно исправить руками.
    """
    stations = [{'id': 'yt', 'name': 'Y', 'lat': 57.6, 'lon': 39.9,
                 'source': 'http', 'max_age_s': None,
                 'sensors': {'temperature_2m': YARTEMP_URL}}]
    cfg = tmp_path / 'st.json'
    cfg.write_text(json.dumps({'stations': stations}), encoding='utf-8')
    with pytest.raises(ValueError, match='max_age_s'):
        load_stations(cfg)


def test_load_stations_rejects_boolean_max_age(tmp_path):
    """bool - подкласс int, поэтому наивная числовая проверка его протащила бы.

    JSON-true в пороге означал бы одну секунду свежести: станция молчала бы в
    каждом прогоне, и виноват выглядел бы не конфиг, а сам источник.
    """
    stations = [{'id': 'yt', 'name': 'Y', 'lat': 57.6, 'lon': 39.9,
                 'source': 'http', 'max_age_s': True,
                 'sensors': {'temperature_2m': YARTEMP_URL}}]
    cfg = tmp_path / 'st.json'
    cfg.write_text(json.dumps({'stations': stations}), encoding='utf-8')
    with pytest.raises(ValueError, match='max_age_s') as err:
        load_stations(cfg)
    # Причина обязана называть то, что оператор написал в конфиге: строка
    # про «не число» без значения сама по себе ни о чём не говорит.
    assert 'True' in str(err.value)


def test_load_stations_rejects_nan_max_age(tmp_path):
    """NaN проходит и проверку типа, и проверку знака, а порог не работает.

    json.load по умолчанию берёт литерал NaN, а json.dump пишет его без
    кавычек, поэтому такое значение может появиться в конфиге из любого
    скрипта, который правит stations.json. Дальше `now - reading_ts > nan`
    всегда False: станция не протухает никогда, и в среднее копятся замеры
    любой давности - ровно то, ради чего порог и существует.
    """
    stations = [{'id': 'yt', 'name': 'Y', 'lat': 57.6, 'lon': 39.9,
                 'source': 'http', 'max_age_s': float('nan'),
                 'sensors': {'temperature_2m': YARTEMP_URL}}]
    cfg = tmp_path / 'st.json'
    cfg.write_text(json.dumps({'stations': stations}), encoding='utf-8')
    with pytest.raises(ValueError, match='max_age_s') as err:
        load_stations(cfg)
    assert 'nan' in str(err.value)


def test_load_stations_rejects_infinite_max_age(tmp_path):
    """Бесконечность ломает порог так же, как NaN, но иначе проходит.

    `nan <= 0` ложно, так что знака тут не хватает; зато `inf > 0` истинно,
    и бесконечность отсекает только проверка конечности.
    """
    stations = [{'id': 'yt', 'name': 'Y', 'lat': 57.6, 'lon': 39.9,
                 'source': 'http', 'max_age_s': float('inf'),
                 'sensors': {'temperature_2m': YARTEMP_URL}}]
    cfg = tmp_path / 'st.json'
    cfg.write_text(json.dumps({'stations': stations}), encoding='utf-8')
    with pytest.raises(ValueError, match='max_age_s') as err:
        load_stations(cfg)
    assert 'inf' in str(err.value)


def test_metar_station_is_polled_over_the_network_not_mqtt():
    """Обе сетевые станции попадают в http_stations, mqtt-станции - нет."""
    stations = [
        {'id': 'a', 'sensors': {'temperature_2m': 'city/out/a'}},
        {'id': 'yt', 'source': 'http',
         'sensors': {'temperature_2m': YARTEMP_URL}},
        {'id': 'uudl', 'source': 'metar',
         'sensors': {'temperature_2m': 'UUDL'}},
    ]
    assert [st['id'] for st in http_stations(stations)] == ['yt', 'uudl']


def test_metar_station_is_never_subscribed_over_mqtt():
    """Токен UUDL - это не топик брокера: в подписку он попасть не должен."""
    stations = [
        {'id': 'a', 'sensors': {'temperature_2m': 'city/out/a'}},
        {'id': 'uudl', 'source': 'metar',
         'sensors': {'temperature_2m': 'UUDL'}},
    ]
    client = _FakeClient([('city/out/a', '20.4', False)])
    cs.collect(client, stations, 0)
    assert client.subs == ['city/out/a']


# --- METAR аэропорта: NOAA, JSON, раз в 30 минут --------------------------
# Ответ - JSON-массив сводок, свежая первая. Берётся temp как значение и
# reportTime как метка наблюдения: время отдачи ответа не годится, оно
# ничего не говорит о свежести показания.

# 2026-09-30T09:30:00Z = 12:30 МСК
METAR_REPORT_ISO = '2026-09-30T09:30:00.000Z'


def _metar_body(temp='16.0', report_time=METAR_REPORT_ISO):
    return json.dumps([{'icaoId': 'UUDL',
                        'temp': temp,
                        'reportTime': report_time,
                        'rawOb': 'UUDL 093000Z 09004MPS 060V110 9999 FEW045 16/09 Q1011'}])


def test_fetch_metar_takes_temperature_and_observation_time():
    """temp - значение, reportTime - метка наблюдения в unix-времени."""
    want_ts = datetime(2026, 9, 30, 9, 30, tzinfo=timezone.utc).timestamp()
    payload, reading_ts = fetch_metar(
        METAR_URL, now=want_ts, session=_FakeSession(_metar_body()))
    assert payload == '16.0'
    assert reading_ts == pytest.approx(want_ts, abs=1)


def test_fetch_metar_marks_observation_time_not_poll_time():
    """Метка - это момент наблюдения, а не момент нашего запроса.

    Между сводками проходит полчаса, поэтому now отличается от reportTime на
    минуты. Подставь fetch_metar вместо reportTime время запроса, прогон
    объявил бы получасовую давность свежим замером, и age_s на сайте считал бы
    давность запроса вместо давности показания.
    """
    want_ts = datetime(2026, 9, 30, 9, 30, tzinfo=timezone.utc).timestamp()
    payload, reading_ts = fetch_metar(
        METAR_URL, now=want_ts + 1500, session=_FakeSession(_metar_body()))
    assert payload == '16.0'
    assert reading_ts == pytest.approx(want_ts, abs=1)


def test_fetch_metar_takes_numeric_temperature_as_it_comes():
    """Живой NOAA присылает temp числом JSON, а не строкой.

    Значение всё равно возвращается строкой: build_snapshot разбирает payload
    через parse_payload, и оба транспорта обязаны отдавать одно и то же.
    """
    want_ts = datetime(2026, 9, 30, 9, 30, tzinfo=timezone.utc).timestamp()
    payload, reading_ts = fetch_metar(
        METAR_URL, now=want_ts, session=_FakeSession(_metar_body(temp=14)))
    assert isinstance(payload, str), 'payload must be a string, like fetch_yartemp'
    assert payload == '14.0'
    assert reading_ts == pytest.approx(want_ts, abs=1)
    # round trip через build_snapshot: разбор строки даёт то же число
    assert cs.parse_payload(payload) == pytest.approx(14.0)


def test_fetch_metar_takes_the_newest_report_of_the_list():
    """NOAA отдаёт сводки новыми первыми, поэтому берётся report[0].

    report[-1] - это сводка получасовой давности: значение вышло бы верное на
    вид, а в бакет истории легло бы в старый час.
    """
    want_ts = datetime(2026, 9, 30, 9, 30, tzinfo=timezone.utc).timestamp()
    body = json.dumps([
        {'icaoId': 'UUDL', 'temp': 14, 'reportTime': METAR_REPORT_ISO},
        {'icaoId': 'UUDL', 'temp': 11,
         'reportTime': '2026-09-30T09:00:00.000Z',
         'rawOb': 'UUDL 090000Z 09004MPS 060V110 9999 FEW045 11/09 Q1011'},
    ])
    payload, reading_ts = fetch_metar(
        METAR_URL, now=want_ts + 1500, session=_FakeSession(body))
    assert payload == '14.0'
    assert reading_ts == pytest.approx(want_ts, abs=1)


def test_fetch_metar_sends_a_user_agent():
    """NOAA требует представиться; Referer не нужен и не шлётся."""
    session = _FakeSession(_metar_body())
    fetch_metar(METAR_URL, now=1.0, session=session)
    url, kw = session.calls[0]
    assert url == METAR_URL
    assert 'User-Agent' in kw['headers']
    assert 'Referer' not in kw['headers']


def test_fetch_metar_returns_none_on_empty_list():
    assert fetch_metar(METAR_URL, now=1.0,
                       session=_FakeSession('[]')) == (None, None)


def test_fetch_metar_returns_none_on_missing_temperature():
    body = json.dumps([{'icaoId': 'UUDL', 'reportTime': METAR_REPORT_ISO}])
    assert fetch_metar(METAR_URL, now=1.0,
                       session=_FakeSession(body)) == (None, None)


def test_fetch_metar_returns_none_on_missing_report_time():
    body = json.dumps([{'icaoId': 'UUDL', 'temp': '16.0'}])
    assert fetch_metar(METAR_URL, now=1.0,
                       session=_FakeSession(body)) == (None, None)


def test_fetch_metar_returns_none_on_unparsable_report_time():
    assert fetch_metar(
        METAR_URL, now=1.0,
        session=_FakeSession(_metar_body(report_time='вчера'))) == (None, None)


def test_fetch_metar_rejects_temperature_out_of_range():
    """За пределами физики значение не должно доходить до словарей."""
    assert fetch_metar(
        METAR_URL, now=1.0,
        session=_FakeSession(_metar_body(temp='99.0'))) == (None, None)


def test_fetch_metar_survives_html_instead_of_json():
    """Смена формата на сайте - тишина, а не падение публикации."""
    assert fetch_metar(
        METAR_URL, now=1.0,
        session=_FakeSession('<html>maintenance</html>')) == (None, None)


def test_fetch_metar_survives_integer_too_large_for_float():
    """Огромное целое из JSON не должно вылетать из fetch_metar.

    float() на строке к такому не готовит, а целое длиннее ~309 цифр
    превращается в OverflowError, который не ловится TypeError/ValueError.
    Ветка нужна именно здесь: fetch_yartemp всегда преобразует строку и
    OverflowError не возникает, а collect_http вызывает адаптеры без
    собственной защиты.
    """
    assert fetch_metar(
        METAR_URL, now=1.0,
        session=_FakeSession(_metar_body(temp=10 ** 400))) == (None, None)


def test_fetch_metar_survives_network_error():
    assert fetch_metar(
        METAR_URL, now=1.0,
        session=_FakeSession(raises=OSError('connection reset'))) == (None, None)


def test_fetch_metar_survives_http_error():
    """Сводка за 503 - это «нет данных», даже если тело разбирается.

    Тело здесь заведомо валидная сводка: иначе тест прошёл бы и с выкинутой
    проверкой статуса, потому что json.loads всё равно не справился бы.
    """
    assert fetch_metar(
        METAR_URL, now=1.0,
        session=_FakeSession(_metar_body(), status=503)) == (None, None)


def test_fetch_metar_returns_none_on_empty_body():
    assert fetch_metar(METAR_URL, now=1.0,
                       session=_FakeSession('')) == (None, None)


def test_fetch_metar_returns_none_when_json_is_not_a_list():
    """Словарь вместо массива - тоже смена формата, а не повод падать."""
    body = json.dumps({'error': 'no data for UUDL'})
    assert fetch_metar(METAR_URL, now=1.0,
                       session=_FakeSession(body)) == (None, None)


def test_fetch_metar_returns_none_when_first_report_is_not_an_object():
    """Строка или число вместо сводки: полями от неё не пахнет."""
    assert fetch_metar(METAR_URL, now=1.0,
                       session=_FakeSession('["16.0"]')) == (None, None)


def test_fetch_metar_returns_none_on_boolean_temperature():
    """bool - подкласс int, поэтому float(true) дал бы тихие 1.0 градуса.

    JSON-true на месте temp означал бы правдоподобное число в бакет истории,
    и виноват выглядел бы аэропорт, а не разбор ответа.
    """
    assert fetch_metar(
        METAR_URL, now=1.0,
        session=_FakeSession(_metar_body(temp=True))) == (None, None)


@pytest.mark.parametrize('temp', ['M02', 'NaN', '', 'Infinity'])
def test_fetch_metar_returns_none_on_non_numeric_temperature(temp):
    """Мусор вместо числа не должен ни падать, ни попасть в историю."""
    assert fetch_metar(
        METAR_URL, now=1.0,
        session=_FakeSession(_metar_body(temp=temp))) == (None, None)


def test_fetch_metar_honours_offset_in_report_time():
    """Смещение в reportTime читается как смещение, а не отбрасывается.

    Отбрасывать нельзя ни миллисекунды, ни знак: '09:30+03:00' и '06:30Z' -
    один и тот же момент, и разница трёх часов решила бы, в какой бакет часа
    попадёт показание. Смещение в сводке NOAA сегодня не встречается, но
    разбор не должен зависеть от этого.
    """
    with_offset = datetime(2026, 9, 30, 9, 30,
                           tzinfo=timezone(timedelta(hours=3))).timestamp()
    _payload, shifted = fetch_metar(
        METAR_URL, now=1.0,
        session=_FakeSession(_metar_body(report_time='2026-09-30T09:30:00.000+03:00')))
    _payload, as_utc = fetch_metar(
        METAR_URL, now=1.0,
        session=_FakeSession(_metar_body(report_time='2026-09-30T06:30:00.000Z')))
    assert shifted == pytest.approx(as_utc, abs=1)
    assert shifted == pytest.approx(with_offset, abs=1)


def test_fetch_metar_reads_naive_report_time_as_utc():
    """Метка reportTime без смещения читается как UTC.

    Сводка приходит в UTC, поэтому метка без часового пояса читается как UTC:
    иначе показание уезжало бы на три часа в бакет истории.
    """
    want_ts = datetime(2026, 9, 30, 9, 30, tzinfo=timezone.utc).timestamp()
    body = _metar_body(report_time='2026-09-30T09:30:00')
    payload, reading_ts = fetch_metar(METAR_URL, now=want_ts,
                                      session=_FakeSession(body))
    assert payload == '16.0'
    assert reading_ts == pytest.approx(want_ts, abs=1)


# --- collect_http разводит станции по адаптерам ----------------------------
# Сетевой транспорт один, а формат ответа разный: yartemp отдаёт строку с
# полями через ';', аэропорт - JSON-сводку. Слой опроса не должен ветвиться по
# source на каждую станцию, поэтому выбор адаптера вынесен в station_fetcher.


def test_collect_http_picks_the_adapter_matching_the_source(tmp_path, monkeypatch):
    """Каждая сетевая станция получает свой разбор ответа, не чужой."""
    now = 1790708310.0
    stations = [
        {'id': 'yt', 'name': 'Y', 'lat': 57.6, 'lon': 39.9, 'source': 'http',
         'sensors': {'temperature_2m': YARTEMP_URL}},
        {'id': 'uudl', 'name': 'A', 'lat': 57.561, 'lon': 40.157,
         'source': 'metar', 'max_age_s': 2400,
         'sensors': {'temperature_2m': 'UUDL'}},
    ]
    cfg = tmp_path / 'st.json'
    cfg.write_text(json.dumps({'stations': stations}), encoding='utf-8')
    out = tmp_path / 'sensors.json'
    metar_ts = now - 600

    seen_by = {}

    def fake_yartemp(url, **kw):
        seen_by['yartemp'] = url
        return '8.090', now - 60

    def fake_metar(url, **kw):
        seen_by['metar'] = url
        return '16.0', metar_ts

    monkeypatch.setattr(cs.time, 'time', lambda: now)
    monkeypatch.setattr(cs, 'fetch_yartemp', fake_yartemp)
    monkeypatch.setattr(cs, 'fetch_metar', fake_metar)

    cs.run(client_factory=lambda *a, **kw: _FakeClient([]), config=cfg, out=out,
           window_s=0, history=str(tmp_path / 'h.json'))

    # Каждый адаптер вызван только для своей станции. METAR получает не токен
    # из конфига, а развёрнутый из него адрес API: сам токен - относительный
    # URL, и requests на нём падает, а fetch_metar это молча проглатывает.
    assert seen_by == {'yartemp': YARTEMP_URL, 'metar': METAR_URL}
    data = json.loads(out.read_text(encoding='utf-8'))
    by_id = {st['id']: st for st in data['stations']}
    assert by_id['uudl']['values']['temperature_2m'] == pytest.approx(16.0)
    assert by_id['yt']['values']['temperature_2m'] == pytest.approx(8.09)


def test_icao_token_from_config_becomes_a_requestable_metar_url():
    """Токен из конфига - это ключ словаря, а не адрес, по нему не ходят.

    Здесь настоящий fetch_metar с поддельной сессией: если бы station_fetcher
    отдал адаптер напрямую, в get() ушло бы 'UUDL', requests поднял бы
    MissingSchema, except Exception проглотил бы её, и станция молчала бы
    каждый прогон - без единой ошибки в логе.
    """
    session = _FakeSession(_metar_body())

    fetcher = cs.station_fetcher({'source': 'metar'})
    payload, reading_ts = fetcher('UUDL', now=1.0, session=session)

    assert session.calls[0][0] == METAR_URL
    assert payload == '16.0'
    assert reading_ts == pytest.approx(
        datetime(2026, 9, 30, 9, 30, tzinfo=timezone.utc).timestamp(), abs=1)


def test_fresh_metar_reading_lands_in_the_hour_of_the_observation(tmp_path, monkeypatch):
    """Бакет берётся от reportTime, а не от часа прогона.

    Прогон в 13:05 МСК, а сам замер сделан в 12:30. Замер обязан лечь в бакет
    12:00, иначе подпись на сайте сказала бы «обновилось в 13:00» про
    показание получасовой давности.

    fetch_yartemp подменён тоже: при неверном выборе адаптера станция ушла бы
    в настоящий HTTP-запрос по не-URL и «прошла бы» на отказе сети, а не на
    нужной метке бакета.
    """
    run_ts = datetime(2026, 9, 30, 10, 5, tzinfo=timezone.utc).timestamp()  # 13:05 МСК
    obs_ts = datetime(2026, 9, 30, 9, 30, tzinfo=timezone.utc).timestamp()  # 12:30 МСК
    stations = [{'id': 'uudl', 'name': 'A', 'lat': 57.561, 'lon': 40.157,
                 'source': 'metar', 'max_age_s': 2400,
                 'sensors': {'temperature_2m': 'UUDL'}}]
    cfg = tmp_path / 'st.json'
    cfg.write_text(json.dumps({'stations': stations}), encoding='utf-8')
    out = tmp_path / 'sensors.json'
    hist = tmp_path / 'h.json'

    monkeypatch.setattr(cs.time, 'time', lambda: run_ts)
    monkeypatch.setattr(cs, 'fetch_yartemp',
                        lambda url, **kw: ('8.090', run_ts - 60))
    monkeypatch.setattr(cs, 'fetch_metar', lambda url, **kw: ('16.0', obs_ts))

    cs.run(client_factory=lambda *a, **kw: _FakeClient([]), config=cfg, out=out,
           window_s=0, history=str(hist))

    hours = json.loads(hist.read_text(encoding='utf-8'))['hours']
    assert list(hours) == ['2026-09-30T12:00']


def test_stale_metar_reading_is_not_injected(tmp_path, monkeypatch):
    """Сводка старше собственного порога станции не попадает в среднее."""
    now = 1790708310.0
    stations = [{'id': 'uudl', 'name': 'A', 'lat': 57.561, 'lon': 40.157,
                 'source': 'metar', 'max_age_s': 2400,
                 'sensors': {'temperature_2m': 'UUDL'}}]
    cfg = tmp_path / 'st.json'
    cfg.write_text(json.dumps({'stations': stations}), encoding='utf-8')
    out = tmp_path / 'sensors.json'

    monkeypatch.setattr(cs.time, 'time', lambda: now)
    # Замер yartemp здесь свежий, поэтому с ошибочным выбором адаптера станция
    # наполнилась бы чужим значением и тест прошёл бы не по той причине.
    monkeypatch.setattr(cs, 'fetch_yartemp',
                        lambda url, **kw: ('8.090', now - 60))
    monkeypatch.setattr(cs, 'fetch_metar',
                        lambda url, **kw: ('16.0', now - 2400 - 60))

    cs.run(client_factory=lambda *a, **kw: _FakeClient([]), config=cfg, out=out,
           window_s=0, history=str(tmp_path / 'h.json'))

    data = json.loads(out.read_text(encoding='utf-8'))
    assert data['stations'][0]['online'] is False
    assert data['stations'][0]['values'] == {}


def test_metar_freshness_uses_its_own_threshold_not_the_shared_one(tmp_path, monkeypatch):
    """Полчаса - протухло для yartemp, но в пределах допуска METAR."""
    now = 1790708310.0
    stations = [
        {'id': 'yt', 'name': 'Y', 'lat': 57.6, 'lon': 39.9, 'source': 'http',
         'sensors': {'temperature_2m': YARTEMP_URL}},
        {'id': 'uudl', 'name': 'A', 'lat': 57.561, 'lon': 40.157,
         'source': 'metar', 'max_age_s': 2400,
         'sensors': {'temperature_2m': 'UUDL'}},
    ]
    cfg = tmp_path / 'st.json'
    cfg.write_text(json.dumps({'stations': stations}), encoding='utf-8')
    out = tmp_path / 'sensors.json'
    aged = now - 2000

    monkeypatch.setattr(cs.time, 'time', lambda: now)
    monkeypatch.setattr(cs, 'fetch_yartemp', lambda url, **kw: ('8.090', aged))
    monkeypatch.setattr(cs, 'fetch_metar', lambda url, **kw: ('16.0', aged))

    cs.run(client_factory=lambda *a, **kw: _FakeClient([]), config=cfg, out=out,
           window_s=0, history=str(tmp_path / 'h.json'))

    data = json.loads(out.read_text(encoding='utf-8'))
    by_id = {st['id']: st for st in data['stations']}
    assert by_id['yt']['online'] is False
    assert by_id['uudl']['online'] is True


def test_failing_metar_does_not_break_other_stations(tmp_path, monkeypatch):
    """Отвал аэропорта не должен обнулять ни MQTT, ни yartemp."""
    now = 1790708310.0
    stations = [
        {'id': 'a', 'name': 'A', 'lat': 57.0, 'lon': 39.0,
         'sensors': {'temperature_2m': 'city/out/a'}},
        {'id': 'yt', 'name': 'Y', 'lat': 57.6, 'lon': 39.9, 'source': 'http',
         'sensors': {'temperature_2m': YARTEMP_URL}},
        {'id': 'uudl', 'name': 'Air', 'lat': 57.561, 'lon': 40.157,
         'source': 'metar', 'max_age_s': 2400,
         'sensors': {'temperature_2m': 'UUDL'}},
    ]
    cfg = tmp_path / 'st.json'
    cfg.write_text(json.dumps({'stations': stations}), encoding='utf-8')
    out = tmp_path / 'sensors.json'
    fake = _FakeClient([('city/out/a', '20.4', False)])

    monkeypatch.setattr(cs.time, 'time', lambda: now)
    monkeypatch.setattr(cs, 'fetch_yartemp', lambda url, **kw: ('8.090', now - 60))
    monkeypatch.setattr(cs, 'fetch_metar', lambda url, **kw: (None, None))

    cs.run(client_factory=lambda *a, **kw: fake, config=cfg, out=out, window_s=0,
           history=str(tmp_path / 'h.json'))

    data = json.loads(out.read_text(encoding='utf-8'))
    by_id = {st['id']: st for st in data['stations']}
    assert by_id['a']['values']['temperature_2m'] == pytest.approx(20.4)
    assert by_id['yt']['online'] is True
    assert by_id['uudl']['online'] is False


# --- таймаут доходит до обоих адаптеров -----------------------------------
# collect_http гонит оба разбора одним и тем же вызовом, поэтому забытый
# таймаут сломал бы оба источника разом, а заметить это можно было бы только
# по прогону, который висит дольше любой разумной публикации.


def test_fetch_yartemp_passes_the_timeout_through():
    """Таймаут уходит в запрос, а не теряется по дороге к session.get."""
    session = _FakeSession(YARTEMP_BODY)
    fetch_yartemp(YARTEMP_URL, now=1790708310.0, session=session, timeout_s=7)

    _url, kw = session.calls[0]
    assert kw['timeout'] == 7


def test_fetch_metar_passes_the_timeout_through():
    """То же для аэропорта: у обоих адаптеров сигнатуры обязаны совпадать."""
    session = _FakeSession(_metar_body())
    fetch_metar(METAR_URL, now=1.0, session=session, timeout_s=7)

    _url, kw = session.calls[0]
    assert kw['timeout'] == 7


def test_collect_http_forwards_its_timeout_to_both_adapters(monkeypatch):
    """Свой таймаут collect_http доезжает до обоих разборов ответа.

    Разбор выбирается по source, а вызов у них общий: забыть параметр можно
    один раз, но цена - HTTP-запрос без предела ожидания на обоих источниках.
    """
    calls = []

    def record(name):
        # Подпись повторяет настоящий контракт адаптеров, session включительно:
        # разбор выбора адаптера подставляет его в вызов сам, и заглушка с
        # урезанной подписью ловила бы не ошибку таймаута, а TypeError.
        def fetcher(url, now=None, timeout_s=None, session=None, **kw):
            calls.append((name, url, timeout_s))
            return None, None
        return fetcher

    monkeypatch.setattr(cs, 'fetch_yartemp', record('yartemp'))
    monkeypatch.setattr(cs, 'fetch_metar', record('metar'))
    stations = [
        {'id': 'yt', 'source': 'http',
         'sensors': {'temperature_2m': YARTEMP_URL}},
        {'id': 'uudl', 'source': 'metar', 'max_age_s': 2400,
         'sensors': {'temperature_2m': 'UUDL'}},
    ]

    cs.collect_http({}, {}, stations, now=1790708310.0, timeout_s=7)

    assert calls == [('yartemp', YARTEMP_URL, 7), ('metar', METAR_URL, 7)]


# --- четвёртый транспорт: wu ----------------------------------------------
# Weather Underground PWS. Ответ - JSON-объект с полем observations (не массив
# верхнего уровня, как у METAR). Значение - metric.temp, метка наблюдения -
# obsTimeUtc. Формат зафиксирован с живого запроса 2026-10-01.

WU_KEY = '6532d6454b8aa370768e63d6ba5a832e'
WU_URL = ('https://api.weather.com/v2/pws/observations/current'
          '?stationId=IZAVOLZH3&format=json&units=m&apiKey=' + WU_KEY)
# 2026-10-01T20:44:12Z = 23:44 МСК
WU_OBS_ISO = '2026-10-01T20:44:12Z'


def _wu_ts():
    return datetime(2026, 10, 1, 20, 44, 12, tzinfo=timezone.utc).timestamp()


def _wu_body(temp=4, obs_time=WU_OBS_ISO, station='IZAVOLZH3', metric=True):
    obs = {'stationID': station, 'obsTimeUtc': obs_time, 'humidity': 91,
           'qcStatus': -1}
    if metric:
        obs['metric'] = {'temp': temp, 'windSpeed': 0, 'pressure': 1016.26}
    return json.dumps({'observations': [obs]})


def test_fetch_wu_takes_temperature_and_observation_time():
    """metric.temp - значение, obsTimeUtc - метка наблюдения в unix-времени."""
    payload, reading_ts = cs.fetch_wu(
        WU_URL, now=_wu_ts(), session=_FakeSession(_wu_body()))
    assert payload == '4.0'
    assert reading_ts == pytest.approx(_wu_ts(), abs=1)


def test_fetch_wu_marks_observation_time_not_poll_time():
    """Метка - момент наблюдения, а не момент нашего запроса.

    WU отдаёт готовое число, но обновляется раз в ~5 минут, поэтому now и
    obsTimeUtc расходятся. Подставь время запроса - age_s на сайте считал бы
    давность запроса, а не давность показания.
    """
    payload, reading_ts = cs.fetch_wu(
        WU_URL, now=_wu_ts() + 60, session=_FakeSession(_wu_body()))
    assert payload == '4.0'
    assert reading_ts == pytest.approx(_wu_ts(), abs=1)


def test_fetch_wu_sends_a_user_agent():
    session = _FakeSession(_wu_body())
    cs.fetch_wu(WU_URL, now=1.0, session=session)
    url, kw = session.calls[0]
    assert url == WU_URL
    assert 'User-Agent' in kw['headers']
    assert 'Referer' not in kw['headers']


def test_fetch_wu_returns_none_on_empty_observations():
    assert cs.fetch_wu(WU_URL, now=1.0,
                       session=_FakeSession('{"observations": []}')) == (None, None)


def test_fetch_wu_returns_none_when_json_is_not_an_object():
    """Массив вместо объекта - смена формата (METAR отдаёт массив, WU нет)."""
    assert cs.fetch_wu(WU_URL, now=1.0,
                       session=_FakeSession('[]')) == (None, None)


def test_fetch_wu_returns_none_on_missing_metric():
    assert cs.fetch_wu(WU_URL, now=1.0,
                       session=_FakeSession(_wu_body(metric=False))) == (None, None)


def test_fetch_wu_returns_none_on_missing_temperature():
    body = json.dumps({'observations': [{'stationID': 'IZAVOLZH3',
                                         'obsTimeUtc': WU_OBS_ISO,
                                         'metric': {'windSpeed': 0}}]})
    assert cs.fetch_wu(WU_URL, now=1.0,
                       session=_FakeSession(body)) == (None, None)


def test_fetch_wu_returns_none_on_null_temperature():
    """null на месте temp - «нет данных», а не ноль градусов.

    У проверенных станций поле присутствует, но PWS легко отдают null, когда
    датчик отвалился. Прочитай его как 0 - в бакет истории легло бы ложное
    показание.
    """
    assert cs.fetch_wu(WU_URL, now=1.0,
                       session=_FakeSession(_wu_body(temp=None))) == (None, None)


def test_fetch_wu_returns_none_on_boolean_temperature():
    """bool - подкласс int, поэтому float(true) дал бы тихий 1.0 градус."""
    assert cs.fetch_wu(WU_URL, now=1.0,
                       session=_FakeSession(_wu_body(temp=True))) == (None, None)


def test_fetch_wu_rejects_temperature_out_of_range():
    assert cs.fetch_wu(WU_URL, now=1.0,
                       session=_FakeSession(_wu_body(temp=99))) == (None, None)


def test_fetch_wu_returns_none_on_missing_observation_time():
    body = json.dumps({'observations': [{'stationID': 'IZAVOLZH3',
                                         'metric': {'temp': 4}}]})
    assert cs.fetch_wu(WU_URL, now=1.0,
                       session=_FakeSession(body)) == (None, None)


def test_fetch_wu_returns_none_on_unparsable_observation_time():
    assert cs.fetch_wu(
        WU_URL, now=1.0,
        session=_FakeSession(_wu_body(obs_time='вчера'))) == (None, None)


def test_fetch_wu_survives_html_instead_of_json():
    assert cs.fetch_wu(
        WU_URL, now=1.0,
        session=_FakeSession('<html>maintenance</html>')) == (None, None)


def test_fetch_wu_survives_network_error():
    assert cs.fetch_wu(
        WU_URL, now=1.0,
        session=_FakeSession(raises=OSError('connection reset'))) == (None, None)


def test_fetch_wu_survives_http_error():
    """503 - «нет данных», даже если тело разбирается.

    Тело здесь валидная сводка: иначе тест прошёл бы и с выкинутой проверкой
    статуса, потому что json.loads всё равно бы не справился.
    """
    assert cs.fetch_wu(
        WU_URL, now=1.0,
        session=_FakeSession(_wu_body(), status=503)) == (None, None)


def test_fetch_wu_returns_none_on_empty_body():
    assert cs.fetch_wu(WU_URL, now=1.0,
                       session=_FakeSession('')) == (None, None)


def test_fetch_wu_rejects_a_report_for_another_station():
    """Станция чужого id не должна выдаваться за нашу.

    WU на несуществующий id отвечает пустым observations, но сверка ловит и
    случай, когда сервис вернул данные другой станции. Без неё опечатка в
    конфиге молчала бы, а выглядело бы как «станция не отвечает».
    """
    body = _wu_body(station='I90583615')
    assert cs.fetch_wu(WU_URL, now=1.0, expect_station='IZAVOLZH3',
                       session=_FakeSession(body)) == (None, None)


def test_fetch_wu_accepts_its_own_station_id():
    payload, reading_ts = cs.fetch_wu(
        WU_URL, now=_wu_ts(), expect_station='IZAVOLZH3',
        session=_FakeSession(_wu_body()))
    assert payload == '4.0'
    assert reading_ts == pytest.approx(_wu_ts(), abs=1)


def test_fetch_wu_passes_the_timeout_through():
    session = _FakeSession(_wu_body())
    cs.fetch_wu(WU_URL, now=1.0, session=session, timeout_s=7)
    _url, kw = session.calls[0]
    assert kw['timeout'] == 7


def test_wu_fetcher_builds_the_request_url_from_the_station_id():
    """Токен из конфига - ключ словаря, а не адрес: по нему не ходят.

    wu_fetcher разворачивает stationId в настоящий URL, как metar_fetcher
    разворачивает код аэропорта. Иначе requests упал бы с MissingSchema,
    адаптер проглотил бы исключение, и станция молчала бы каждый прогон.
    """
    session = _FakeSession(_wu_body())
    payload, reading_ts = cs.wu_fetcher('IZAVOLZH3', now=_wu_ts(), session=session)
    assert session.calls[0][0] == WU_URL
    assert payload == '4.0'
    assert reading_ts is not None


def test_station_fetcher_picks_wu_adapter():
    assert cs.station_fetcher({'source': 'wu'}) is cs.wu_fetcher


def test_wu_is_a_valid_source(tmp_path):
    stations = [{'id': 'wu', 'name': 'W', 'lat': 57.5, 'lon': 39.9,
                 'source': 'wu', 'sensors': {'temperature_2m': 'IZAVOLZH3'}}]
    cfg = tmp_path / 'st.json'
    cfg.write_text(json.dumps({'stations': stations}), encoding='utf-8')
    assert load_stations(cfg)[0]['source'] == 'wu'


def test_wu_station_is_polled_over_the_network_not_mqtt():
    stations = [
        {'id': 'a', 'sensors': {'temperature_2m': 'city/out/a'}},
        {'id': 'wu', 'source': 'wu',
         'sensors': {'temperature_2m': 'IZAVOLZH3'}},
    ]
    assert [st['id'] for st in http_stations(stations)] == ['wu']
    client = _FakeClient([('city/out/a', '20.4', False)])
    cs.collect(client, stations, 0)
    assert client.subs == ['city/out/a']


def test_repository_wu_stations_point_at_expected_ids_with_own_threshold():
    """id станций, порог и координаты закреплены боевым конфигом.

    Порог 1800 с - 3 периода обновления WU (~5 минут): короче общего 900 с он
    не должен становиться, иначе станция протухала бы между циклами.
    """
    with open(cs.DEFAULT_CONFIG, encoding='utf-8') as f:
        settings = json.load(f)
    wu = {st['id']: st for st in settings['stations'] if st.get('source') == 'wu'}
    assert set(wu) == {'wu-ananyino', 'wu-zavolzhskoe'}
    assert wu['wu-ananyino']['sensors']['temperature_2m'] == 'I90583615'
    assert wu['wu-zavolzhskoe']['sensors']['temperature_2m'] == 'IZAVOLZH3'
    for st in wu.values():
        assert st['max_age_s'] == 1800
    assert (wu['wu-ananyino']['lat'], wu['wu-ananyino']['lon']) == (57.48765, 39.94122)
    assert (wu['wu-zavolzhskoe']['lat'], wu['wu-zavolzhskoe']['lon']) == (57.81076, 40.06904)


def test_repository_wu_station_reaches_a_real_url_through_the_real_dispatch():
    """Токен из боевого конфига доезжает до запроса как настоящий адрес.

    Единственное подменённое - сессия: так станция молчала бы в бою, если бы
    в get() ушёл голый stationId.
    """
    with open(cs.DEFAULT_CONFIG, encoding='utf-8') as f:
        settings = json.load(f)
    wu = [st for st in settings['stations'] if st.get('source') == 'wu'][0]
    token = wu['sensors']['temperature_2m']

    session = _FakeSession(_wu_body(station=token))
    fetcher = cs.station_fetcher(wu)
    payload, reading_ts = fetcher(token, now=_wu_ts(), session=session)

    assert token in session.calls[0][0]
    assert 'stationId=' + token in session.calls[0][0]
    assert payload == '4.0'
    assert reading_ts is not None
