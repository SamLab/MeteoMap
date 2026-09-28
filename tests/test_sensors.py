import json
from datetime import datetime, timedelta, timezone

import pytest

from tools import collect_sensors as cs
from tools.collect_sensors import (
    average_stations,
    history_hour_value,
    load_history,
    load_stations,
    moscow_hour_key,
    moscow_now_ts,
    record_history,
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


def test_repository_stations_config_window_is_ten_minutes():
    with open(cs.DEFAULT_CONFIG, encoding='utf-8') as f:
        settings = json.load(f)
    # Окно 10 минут: запас в четыре периода публикации самой медленной
    # станции (~2.5 мин) вместо полутора при 240 с, из-за которого
    # «2/4 online» означало «эти двое не заговорили в мою минуту эфира».
    assert settings['window_s'] == 600


def test_repository_stations_config_subscribes_only_four_topics():
    with open(cs.DEFAULT_CONFIG, encoding='utf-8') as f:
        settings = json.load(f)
    topics = [t for st in settings['stations'] for t in st['sensors'].values()]
    # Температуру отдают все четыре станции, поэтому отказ от влажности и
    # давления не обесценил ни одну: 4 топика вместо 9.
    assert len(settings['stations']) == 4
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
