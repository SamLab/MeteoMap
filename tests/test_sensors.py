import json

import pytest

from tools import collect_sensors as cs
from tools.collect_sensors import average_stations, load_stations, validate

PENATY_T = 'city/out/zavolga/penaty/temp/ws01'
EAST_H = 'city/out/east/hum'


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


def test_validate_rejects_humidity_above_range():
    assert cs.validate('relative_humidity_2m', 120.0) is not None


def test_validate_accepts_plausible_pressure_around_749():
    # 748.9 — нормальное давление для сети; сломанные каналы diesel/petrol
    # исключаются тем, что их топики не внесены в конфиг, а не диапазоном.
    assert cs.validate('pressure_msl', 748.93) is None


def test_validate_rejects_pressure_wildly_out_of_range():
    assert cs.validate('pressure_msl', 48.0) is not None


def test_validate_rejects_gps_speed_sentinel_as_humidity():
    # city/gps/*/speed держит ~99.9 — если такой топик ошибочно отобразить
    # на влажность, заглушка должна быть отброшена
    assert cs.validate('relative_humidity_2m', 99.9709625244141) is not None


def test_validate_accepts_pressure_in_range():
    assert cs.validate('pressure_msl', 765.5) is None


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
     'sensors': {'relative_humidity_2m': EAST_H}},
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
    snap = cs.build_snapshot(STATIONS, {EAST_H: '99.99'},
                             window_s=240, now=1000.0)
    st = {s['id']: s for s in snap['stations']}['east']
    assert st['online'] is False
    assert st['rejected']
    assert 'humidity sentinel' in st['rejected'][0]['reason']
    assert st['rejected'][0]['param'] == 'relative_humidity_2m'


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

    cs.run(client_factory=lambda *a, **kw: fake, config=cfg, out=out, window_s=0)

    data = json.loads(out.read_text(encoding='utf-8'))
    assert data['stations'][0]['values']['temperature_2m'] == pytest.approx(20.4)


def test_run_returns_exit_code_zero(tmp_path):
    stations = [{'id': 'a', 'name': 'A', 'lat': 57.0, 'lon': 39.0,
                 'sensors': {'temperature_2m': 'city/out/a'}}]
    cfg = tmp_path / 'st.json'
    cfg.write_text(json.dumps({'stations': stations}), encoding='utf-8')

    code = cs.run(client_factory=lambda *a, **kw: _FakeClient([]),
                  config=cfg, out=tmp_path / 's.json', window_s=0)

    assert code == 0


def test_run_connects_to_broker_from_config(tmp_path):
    stations = [{'id': 'a', 'name': 'A', 'lat': 57.0, 'lon': 39.0,
                 'sensors': {'temperature_2m': 'city/out/a'}}]
    cfg = tmp_path / 'st.json'
    cfg.write_text(json.dumps({'broker': 'test.host', 'port': 8883,
                               'stations': stations}), encoding='utf-8')
    fake = _FakeClient([])

    cs.run(client_factory=lambda *a, **kw: fake, config=cfg,
           out=tmp_path / 's.json', window_s=0)

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


def test_validate_rejects_humidity_sentinel():
    assert validate("relative_humidity_2m", 99.99) is not None
    assert validate("relative_humidity_2m", 71.6) is None
