#!/usr/bin/env python3
"""Собирает снимок показаний метеостанций с MQTT-брокера yar.gorod76.ru.

Ключевой принцип: retained-сообщения НЕ считаются данными. Скрипт подписывается
на топики станций и слушает живой эфир заданное окно; в снимок попадает только
то, что реально пришло, с меткой «сколько секунд назад». Не услышанное станцией
за окно помечается offline, поэтому протухшие значения не выдаются за живые.
"""

import json
import os
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_CONFIG = os.path.join(HERE, 'stations.json')

# Диапазоны допустимых значений. Значения вне диапазона — заглушки или поломки:
# в сети встречаются hum=99.99 и press=748.9 (тот же сломанный канал повторяется
# в diesel/petrol/kerosene/turpentine/white_spirit).
KIND_RANGES = {
    'temp': (-50.0, 50.0),
    'hum': (0.0, 100.0),
    'press': (600.0, 820.0),
    'illuminance': (0.0, 200000.0),
    'wind': (0.0, 60.0),
    'pm': (0.0, 1000.0),
}

# Влажность 99.5+ — заведомо заглушка, а не измерение.
HUM_SENTINEL = 99.5


def parse_payload(raw):
    """Достаёт число из payload. Возвращает float или None.

    Поддерживает два формата сети: JSON-обёртку {"status":"20.4"}
    (станции /bereg, /dbereg_2, /yarbatut) и голое число (city/out/*).
    """
    if raw is None:
        return None
    text = raw.strip() if isinstance(raw, str) else str(raw).strip()
    if not text:
        return None

    if text.startswith('{'):
        try:
            obj = json.loads(text)
        except ValueError:
            return None
        if not isinstance(obj, dict):
            return None
        status = obj.get('status')
        if status is None:
            return None
        text = str(status).strip()
        if not text:
            return None

    try:
        return float(text)
    except ValueError:
        return None


def validate(kind, value):
    """Проверяет значение против диапазона. None — значение допустимо,
    иначе строка с причиной отброса."""
    bounds = KIND_RANGES.get(kind)
    if bounds is None:
        return 'unknown kind %r' % (kind,)
    if value is None:
        return 'no value'
    if value != value:  # NaN
        return 'not a number'

    low, high = bounds
    if not (low <= value <= high):
        return 'out of range [%g, %g]' % (low, high)
    if kind == 'hum' and value >= HUM_SENTINEL:
        return 'humidity sentinel'
    return None


def build_snapshot(stations, received, window_s, now, seen=None):
    """Собирает снимок из конфига станций и пришедших за окно сообщений.

    received: топик -> сырой payload
    seen:     топик -> время прихода (unix). Отсутствует — сообщение считается
             пришедшим в момент начала окна.
    Станция online только если пришло хотя бы одно валидное значение.
    """
    seen = seen or {}
    out_stations = []

    for st in stations:
        values = {}
        rejected = []
        last_ts = None

        for key, (kind, topic) in st['sensors'].items():
            if topic not in received:
                continue
            value = parse_payload(received[topic])
            reason = validate(kind, value)
            if reason is not None:
                rejected.append({'key': key, 'topic': topic, 'raw': received[topic],
                                 'reason': reason})
                continue
            values[key] = round(value, 2)
            ts = seen.get(topic)
            if ts is not None and (last_ts is None or ts > last_ts):
                last_ts = ts

        age = None
        if values:
            ref = last_ts if last_ts is not None else now - window_s
            age = round(now - ref, 1)

        out_stations.append({
            'id': st['id'],
            'name': st['name'],
            'lat': st['lat'],
            'lon': st['lon'],
            'online': bool(values),
            'age_s': age,
            'values': values,
            'rejected': rejected,
        })

    return {
        'generated_at': datetime.fromtimestamp(now, timezone.utc).strftime(
            '%Y-%m-%dT%H:%M:%SZ'),
        'window_s': window_s,
        'stations': out_stations,
    }


def load_stations(path):
    """Читает и проверяет конфиг станций. Бросает ValueError с причиной."""
    with open(path, encoding='utf-8') as f:
        data = json.load(f)

    raw = data.get('stations')
    if not isinstance(raw, list) or not raw:
        raise ValueError('stations must be a non-empty list')

    seen_ids = set()
    for st in raw:
        for field in ('id', 'name', 'lat', 'lon', 'sensors'):
            if field not in st:
                raise ValueError('station missing %r' % field)

        sid = st['id']
        if sid in seen_ids:
            raise ValueError('duplicate id %r' % sid)
        seen_ids.add(sid)

        try:
            lat = float(st['lat'])
            lon = float(st['lon'])
        except (TypeError, ValueError):
            raise ValueError('station %r: non-numeric lat/lon' % sid)
        if not -90.0 <= lat <= 90.0:
            raise ValueError('station %r: lat out of range: %s' % (sid, lat))
        if not -180.0 <= lon <= 180.0:
            raise ValueError('station %r: lon out of range: %s' % (sid, lon))

        sensors = st['sensors']
        if not isinstance(sensors, dict) or not sensors:
            raise ValueError('station %r: sensors must be a non-empty object' % sid)
        for key, spec in sensors.items():
            if not isinstance(spec, (list, tuple)) or len(spec) != 2:
                raise ValueError('station %r: sensors[%r] must be [kind, topic]'
                                 % (sid, key))
            kind, topic = spec
            if kind not in KIND_RANGES:
                raise ValueError('station %r: sensors[%r] unknown kind %r'
                                 % (sid, key, kind))
            if not isinstance(topic, str) or not topic.strip():
                raise ValueError('station %r: sensors[%r] empty topic' % (sid, key))

    return raw


def collect(client, stations, window_s):
    """Слушает живой эфир window_s секунд. Возвращает (payloads, seen_times).

    Retained-сообщения намеренно отбрасываются: они не несут времени публикации
    и могут хранить значения, опубликованные месяцы назад.
    """
    received = {}
    seen = {}
    wanted = set()
    for st in stations:
        for _kind, topic in st['sensors'].values():
            wanted.add(topic)

    def on_connect(_c, _u, _f, _rc):
        for topic in sorted(wanted):
            client.subscribe(topic, qos=0)

    def on_message(_c, _u, msg):
        if msg.retain:
            return
        try:
            payload = msg.payload.decode('utf-8')
        except UnicodeDecodeError:
            return
        received[msg.topic] = payload
        seen[msg.topic] = time.time()

    client.on_connect = on_connect
    client.on_message = on_message
    client.loop_start()
    if window_s > 0:
        time.sleep(window_s)
    client.loop_stop()
    client.disconnect()
    return received, seen


DEFAULT_OUT = os.path.join(ROOT, 'sensors.json')


def run(config=DEFAULT_CONFIG, out=DEFAULT_OUT, window_s=None, client_factory=None):
    """Собирает снимок и записывает его в out. Возвращает код выхода."""
    with open(config, encoding='utf-8') as f:
        settings = json.load(f)
    stations = load_stations(config)

    if window_s is None:
        window_s = int(settings.get('window_s', 240))

    if client_factory is None:
        import paho.mqtt.client as mqtt

        def client_factory(host, port, keepalive):
            return mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)

    client = client_factory(settings.get('broker', 'yar.gorod76.ru'),
                            int(settings.get('port', 1883)), 30)
    client.connect(settings.get('broker', 'yar.gorod76.ru'),
                   int(settings.get('port', 1883)), 30)
    received, seen = collect(client, stations, window_s)
    snapshot = build_snapshot(stations, received, window_s, time.time(), seen)

    with open(out, 'w', encoding='utf-8') as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
        f.write('\n')

    online = sum(1 for s in snapshot['stations'] if s['online'])
    print('[ok] %s: %d/%d stations online' % (out, online, len(snapshot['stations'])))
    for st in snapshot['stations']:
        if st['online']:
            print('     %-10s %s  age=%ss' % (st['id'], st['values'], st['age_s']))
        elif st['rejected']:
            print('     %-10s rejected: %s' % (
                st['id'], ', '.join(r['reason'] for r in st['rejected'])))
        else:
            print('     %-10s no live data' % st['id'])
    return 0


def main():
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--config', default=DEFAULT_CONFIG)
    ap.add_argument('--out', default=DEFAULT_OUT)
    ap.add_argument('--window', type=int, default=None,
                    help='seconds to listen for live messages')
    args = ap.parse_args()
    return run(config=args.config, out=args.out, window_s=args.window)


if __name__ == '__main__':
    raise SystemExit(main())
