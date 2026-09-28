import json

import pytest

from tools import collect_sensors as cs


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
    assert cs.validate('temp', 20.4) is None


def test_validate_rejects_humidity_sentinel():
    assert cs.validate('hum', 99.99) is not None


def test_validate_rejects_humidity_above_range():
    assert cs.validate('hum', 120.0) is not None


def test_validate_accepts_plausible_pressure_around_749():
    # 748.9 — нормальное давление для сети; сломанные каналы diesel/petrol
    # исключаются тем, что их топики не внесены в конфиг, а не диапазоном.
    assert cs.validate('press', 748.93) is None


def test_validate_rejects_pressure_wildly_out_of_range():
    assert cs.validate('press', 48.0) is not None


def test_validate_rejects_gps_speed_sentinel_as_humidity():
    # city/gps/*/speed держит ~99.9 — если такой топик ошибочно отобратить
    # на влажность, заглушка должна быть отброшена
    assert cs.validate('hum', 99.9709625244141) is not None


def test_validate_accepts_pressure_in_range():
    assert cs.validate('press', 765.5) is None


def test_validate_rejects_temperature_below_range():
    assert cs.validate('temp', -60.0) is not None


def test_validate_rejects_unknown_kind():
    assert cs.validate('ph', 7.0) is not None


def test_validate_accepts_zero_wind():
    assert cs.validate('wind', 0.0) is None


def test_validate_rejects_nan():
    assert cs.validate('temp', float('nan')) is not None


def test_validate_accepts_pm25_in_range():
    assert cs.validate('pm', 2.8) is None


def test_validate_rejects_pm25_absurd():
    assert cs.validate('pm', 5000.0) is not None


STATIONS = [
    {'id': 'yarbatut', 'name': 'Ярбатут', 'lat': 57.64033, 'lon': 39.88513,
     'sensors': {'t1': ('temp', '/yarbatut/2054001-1458270/dstmp4_0/status')}},
    {'id': 'east', 'name': 'Восток', 'lat': 57.62, 'lon': 39.92,
     'sensors': {'h': ('hum', 'city/out/east/hum')}},
]


def test_snapshot_marks_station_online_when_live_message_arrived():
    snap = cs.build_snapshot(STATIONS, {'/yarbatut/2054001-1458270/dstmp4_0/status': '20.4'},
                             window_s=240, now=1000.0)
    st = {s['id']: s for s in snap['stations']}['yarbatut']
    assert st['online'] is True
    assert st['values']['t1'] == pytest.approx(20.4)


def test_snapshot_marks_station_offline_without_live_messages():
    snap = cs.build_snapshot(STATIONS, {}, window_s=240, now=1000.0)
    st = {s['id']: s for s in snap['stations']}['yarbatut']
    assert st['online'] is False
    assert st['age_s'] is None
    assert st['values'] == {}


def test_snapshot_records_rejected_value_with_reason():
    snap = cs.build_snapshot(STATIONS, {'city/out/east/hum': '99.99'},
                             window_s=240, now=1000.0)
    st = {s['id']: s for s in snap['stations']}['east']
    assert st['online'] is False
    assert st['rejected']
    assert 'humidity sentinel' in st['rejected'][0]['reason']


def test_snapshot_age_reflects_window_end():
    snap = cs.build_snapshot(STATIONS, {'/yarbatut/2054001-1458270/dstmp4_0/status': '20.4'},
                             window_s=240, now=1000.0, seen={'/yarbatut/2054001-1458270/dstmp4_0/status': 940.0})
    st = {s['id']: s for s in snap['stations']}['yarbatut']
    assert st['age_s'] == pytest.approx(60.0)


def test_snapshot_uses_latest_message_for_same_topic():
    seen = {'/yarbatut/2054001-1458270/dstmp4_0/status': 900.0}
    snap = cs.build_snapshot(
        STATIONS,
        {'/yarbatut/2054001-1458270/dstmp4_0/status': '18.0'},
        window_s=240, now=1000.0, seen=seen)
    st = {s['id']: s for s in snap['stations']}['yarbatut']
    # 18.0 пришёл позже 20.4 и перекрывает его
    assert st['values']['t1'] == pytest.approx(18.0)


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
            'sensors': {'t': ('temp', '')}}]
    p = tmp_path / 'st.json'
    p.write_text(json.dumps({'stations': bad}), encoding='utf-8')
    with pytest.raises(ValueError, match='topic'):
        cs.load_stations(p)


def test_load_stations_rejects_unknown_sensor_kind(tmp_path):
    bad = [{'id': 'a', 'name': 'A', 'lat': 57.0, 'lon': 39.0,
            'sensors': {'t': ('ph', 'city/out/a')}}]
    p = tmp_path / 'st.json'
    p.write_text(json.dumps({'stations': bad}), encoding='utf-8')
    with pytest.raises(ValueError, match='kind'):
        cs.load_stations(p)


def test_load_stations_rejects_malformed_sensor_entry(tmp_path):
    bad = [{'id': 'a', 'name': 'A', 'lat': 57.0, 'lon': 39.0,
            'sensors': {'t': ['temp']}}]
    p = tmp_path / 'st.json'
    p.write_text(json.dumps({'stations': bad}), encoding='utf-8')
    with pytest.raises(ValueError, match='sensors'):
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


def _topics(stations):
    return [spec[1] for st in stations for spec in st['sensors'].values()]


def test_collect_records_live_message():
    stations = [{'id': 'a', 'name': 'A', 'lat': 57.0, 'lon': 39.0,
                 'sensors': {'t': ('temp', 'city/out/a')}}]
    fake = _FakeClient([('city/out/a', '20.4', False)])

    got, seen = cs.collect(fake, stations, window_s=0)

    assert got['city/out/a'] == '20.4'
    assert 'city/out/a' in seen


def test_collect_ignores_retained_message():
    stations = [{'id': 'a', 'name': 'A', 'lat': 57.0, 'lon': 39.0,
                 'sensors': {'t': ('temp', 'city/out/a')}}]
    fake = _FakeClient([('city/out/a', '20.4', True)])

    got, _seen = cs.collect(fake, stations, window_s=0)

    assert got == {}, 'retained must not be treated as data'


def test_collect_subscribes_only_to_configured_topics():
    stations = [{'id': 'a', 'name': 'A', 'lat': 57.0, 'lon': 39.0,
                 'sensors': {'t': ('temp', 'city/out/a')}}]
    fake = _FakeClient([])

    cs.collect(fake, stations, window_s=0)

    assert fake.subs == ['city/out/a']


def test_collect_keeps_latest_value_per_topic():
    stations = [{'id': 'a', 'name': 'A', 'lat': 57.0, 'lon': 39.0,
                 'sensors': {'t': ('temp', 'city/out/a')}}]
    fake = _FakeClient([('city/out/a', '18.0', False),
                        ('city/out/a', '21.0', False)])

    got, _seen = cs.collect(fake, stations, window_s=0)

    assert got['city/out/a'] == '21.0'


def test_collect_disconnects_client():
    stations = [{'id': 'a', 'name': 'A', 'lat': 57.0, 'lon': 39.0,
                 'sensors': {'t': ('temp', 'city/out/a')}}]
    fake = _FakeClient([])

    cs.collect(fake, stations, window_s=0)

    assert fake.running is False


def test_run_writes_snapshot_file(tmp_path, monkeypatch):
    stations = [{'id': 'a', 'name': 'A', 'lat': 57.0, 'lon': 39.0,
                 'sensors': {'t': ('temp', 'city/out/a')}}]
    cfg = tmp_path / 'st.json'
    cfg.write_text(json.dumps({'stations': stations}), encoding='utf-8')
    out = tmp_path / 'sensors.json'
    fake = _FakeClient([('city/out/a', '20.4', False)])

    cs.run(client_factory=lambda *a, **kw: fake, config=cfg, out=out, window_s=0)

    data = json.loads(out.read_text(encoding='utf-8'))
    assert data['stations'][0]['values']['t'] == pytest.approx(20.4)


def test_run_returns_exit_code_zero(tmp_path):
    stations = [{'id': 'a', 'name': 'A', 'lat': 57.0, 'lon': 39.0,
                 'sensors': {'t': ('temp', 'city/out/a')}}]
    cfg = tmp_path / 'st.json'
    cfg.write_text(json.dumps({'stations': stations}), encoding='utf-8')

    code = cs.run(client_factory=lambda *a, **kw: _FakeClient([]),
                  config=cfg, out=tmp_path / 's.json', window_s=0)

    assert code == 0


def test_run_connects_to_broker_from_config(tmp_path):
    stations = [{'id': 'a', 'name': 'A', 'lat': 57.0, 'lon': 39.0,
                 'sensors': {'t': ('temp', 'city/out/a')}}]
    cfg = tmp_path / 'st.json'
    cfg.write_text(json.dumps({'broker': 'test.host', 'port': 8883,
                               'stations': stations}), encoding='utf-8')
    fake = _FakeClient([])

    cs.run(client_factory=lambda *a, **kw: fake, config=cfg,
           out=tmp_path / 's.json', window_s=0)

    args, _kw = fake.connect_calls[0]
    assert args[0] == 'test.host'
    assert args[1] == 8883
