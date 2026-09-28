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
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_CONFIG = os.path.join(HERE, 'stations.json')

# Параметры, которые реально измеряет сеть. Ключи совпадают с именами
# переменных meteo.py, поэтому подстановка в таблицу Часов не требует
# преобразований. Всё остальное (ветер, осадки, CAPE) датчики не меряют.
SENSOR_PARAMS = {
    'temperature_2m': (-50.0, 50.0),
    'relative_humidity_2m': (0.0, 100.0),
    'pressure_msl': (600.0, 820.0),
}

# Влажность 99.5+ — заведомо заглушка, а не измерение.
HUM_SENTINEL = 99.5

# Ключ бакета истории — локальный московский час, тот же формат, что у time[]
# в meteo.py. Москва не переводит часы с 2014 года, поэтому фиксированный
# UTC+3 равнозначен зоне; он же используется, если в системе нет базы часовых
# поясов (Windows без пакета tzdata).
HISTORY_DEFAULT_DAYS = 30
try:
    HISTORY_TZ = ZoneInfo('Europe/Moscow')
except ZoneInfoNotFoundError:
    HISTORY_TZ = timezone(timedelta(hours=3))


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


def validate(param, value):
    """Проверяет значение против диапазона. None — значение допустимо,
    иначе строка с причиной отброса."""
    bounds = SENSOR_PARAMS.get(param)
    if bounds is None:
        return 'unknown parameter %r' % (param,)
    if value is None:
        return 'no value'
    if value != value:  # NaN
        return 'not a number'

    low, high = bounds
    if not (low <= value <= high):
        return 'out of range [%g, %g]' % (low, high)
    if param == 'relative_humidity_2m' and value >= HUM_SENTINEL:
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

        for param, topic in st['sensors'].items():
            if topic not in received:
                continue
            value = parse_payload(received[topic])
            reason = validate(param, value)
            if reason is not None:
                rejected.append({'param': param, 'topic': topic,
                                 'raw': received[topic], 'reason': reason})
                continue
            values[param] = round(value, 2)
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


def average_stations(per_station):
    """Среднее по станциям для каждого параметра.

    Станция без живого значения параметра исключается из среднего, а не
    считается нулём. Возвращает {param: {"value", "n", "stations"}}.
    """
    out = {}
    for station in per_station:
        for param, value in (station.get('values') or {}).items():
            if param not in SENSOR_PARAMS:
                continue
            entry = out.setdefault(param, {'value': 0.0, 'n': 0, 'stations': []})
            entry['value'] += value
            entry['n'] += 1
            entry['stations'].append(station['id'])
    for entry in out.values():
        entry['value'] = round(entry['value'] / entry['n'], 2)
        entry['stations'].sort()
    return out


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
        for param, topic in sensors.items():
            if param not in SENSOR_PARAMS:
                raise ValueError(
                    'station %r: parameter %r is not measured by the network; '
                    'allowed: %s' % (sid, param, ', '.join(sorted(SENSOR_PARAMS))))
            if not isinstance(topic, str) or not topic.strip():
                raise ValueError('station %r: sensors[%r] must be a topic string'
                                 % (sid, param))

    return raw


def moscow_hour_key(now_ts):
    """Ключ бакета истории: локальный московский час в формате time[]."""
    return datetime.fromtimestamp(now_ts, HISTORY_TZ).strftime('%Y-%m-%dT%H:00')


def moscow_now_ts(hour_key):
    """Обратное преобразование ключа в unix-время, для отсечения старого."""
    return datetime.strptime(hour_key, '%Y-%m-%dT%H:%M').replace(
        tzinfo=HISTORY_TZ).timestamp()


def load_history(path):
    """Читает историю. Отсутствующий или битый файл — пустая история,
    а не ошибка: сборка сайта не должна зависеть от накопленного.

    Бакет не той формы отбрасывается здесь же, чтобы history_hour_value и
    meteo.py получали только то, что читается без try/except.
    """
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {'hours': {}}
    if not isinstance(data, dict) or not isinstance(data.get('hours'), dict):
        return {'hours': {}}
    data['hours'] = {k: v for k, v in data['hours'].items()
                     if isinstance(v, dict) and isinstance(v.get('stations'), dict)}
    return data


def record_history(hours, hour_key, per_station):
    """Дописывает значения станций в бакет часа. Пустой прогон не пишется."""
    live = [s for s in per_station if s.get('values')]
    if not live:
        return False
    bucket = hours['hours'].setdefault(hour_key, {'samples': 0, 'stations': {}})
    for station in live:
        entry = bucket['stations'].setdefault(station['id'], {})
        for param, value in station['values'].items():
            entry.setdefault(param, []).append(value)
    bucket['samples'] += 1
    return True


def mean(values):
    values = list(values)
    return sum(values) / len(values) if values else None


def history_hour_value(bucket, param):
    """Значение часа: среднее по станциям от средних по замерам станции.

    Станции равноправны независимо от того, сколько прогонов их видели.
    Чужой бакет, чужие stations или samples не из чисел — это «нет данных»,
    а не ошибка. Набор проверок повторяет meteo.py:_sensor_hour_value: файл
    один на двоих, и расхождение читателей опаснее дублирования кода.
    """
    stations = bucket.get('stations') if isinstance(bucket, dict) else None
    if not isinstance(stations, dict):
        return None
    per_station = []
    for values in stations.values():
        samples = values.get(param) if isinstance(values, dict) else None
        if not isinstance(samples, list) or not samples:
            continue
        # bool — подкласс int, но JSON-true замером температуры не является
        if not all(isinstance(x, (int, float)) and not isinstance(x, bool)
                   for x in samples):
            continue
        per_station.append(mean(samples))
    if not per_station:
        return None
    return {'value': round(sum(per_station) / len(per_station), 2),
            'n': len(per_station)}


def trim_history(hours, history_days, now):
    """Удаляет бакеты старше history_days."""
    cutoff = moscow_hour_key(now - history_days * 86400)
    hours['hours'] = {k: v for k, v in hours['hours'].items() if k >= cutoff}
    return hours


def history_days(settings):
    """Сколько дней хранить. Мусор в конфиге не должен ронять прогон уже
    после записи sensors.json, а отрицательное значение — задвигать отсечку
    в будущее и стирать только что записанный бакет."""
    try:
        days = int(settings.get('history_days', HISTORY_DEFAULT_DAYS))
    except (TypeError, ValueError):
        return HISTORY_DEFAULT_DAYS
    return max(1, days)


def write_json_atomic(path, payload):
    """Пишет JSON через временный файл рядом с целью.

    Иначе убитый на середине записи прогон оставляет обрезанный
    sensors_history.json, который следующая загрузка прочитала бы как пустую
    историю — и тридцать дней накопления пропали бы молча.
    """
    target = os.fspath(path)
    tmp = target + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write('\n')
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def collect(client, stations, window_s):
    """Слушает живой эфир window_s секунд. Возвращает (payloads, seen_times).

    Retained-сообщения намеренно отбрасываются: они не несут времени публикации
    и могут хранить значения, опубликованные месяцы назад.
    """
    received = {}
    seen = {}
    wanted = set()
    for st in stations:
        for topic in st['sensors'].values():
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
DEFAULT_HISTORY = os.path.join(ROOT, 'sensors_history.json')


def run(config=DEFAULT_CONFIG, out=DEFAULT_OUT, window_s=None, client_factory=None,
        history=DEFAULT_HISTORY):
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
    now = time.time()
    snapshot = build_snapshot(stations, received, window_s, now, seen)

    accumulated = load_history(history)
    record_history(accumulated, moscow_hour_key(now), snapshot['stations'])
    trim_history(accumulated, history_days(settings), now)
    write_json_atomic(history, accumulated)

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
