#!/usr/bin/env python3
"""Собирает снимок показаний метеостанций с MQTT-брокера yar.gorod76.ru.

Ключевой принцип: retained-сообщения НЕ считаются данными. Скрипт подписывается
на топики станций и слушает живой эфир заданное окно; в снимок попадает только
то, что реально пришло, с меткой «сколько секунд назад». Не услышанное станцией
за окно помечается offline, поэтому протухшие значения не выдаются за живые.
"""

import json
import math
import os
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_CONFIG = os.path.join(HERE, 'stations.json')

# Параметры, которые реально измеряет сеть. Ключи совпадают с именами
# переменных meteo.py, поэтому подстановка в таблицу Часов не требует
# преобразований. Всё остальное (ветер, осадки, CAPE) датчики не меряют.
#
# Влажность и давление убраны осознанно: влажность деградировала в заглушку
# 99.99 у Пенатов и ул. Фрунзе, а давление есть только у двух станций и
# разбросалось на 4 гПа. Подробности в
# docs/superpowers/specs/2026-09-28-sensors-temperature-only-design.md.
# Убрать параметр отсюда - значит запретить его и в stations.json: load_stations
# отвергает всё, чего нет в этой таблице, поэтому вернуть влажность молча
# не получится.
SENSOR_PARAMS = {
    'temperature_2m': (-50.0, 50.0),
}

# Ключ бакета истории — локальный московский час, тот же формат, что у time[]
# в meteo.py. Москва не переводит часы с 2014 года, поэтому фиксированный
# UTC+3 равнозначен зоне; он же используется, если в системе нет базы часовых
# поясов (Windows без пакета tzdata).
HISTORY_DEFAULT_DAYS = 30

# Транспорт станции. Поле source в stations.json: отсутствует - значит mqtt,
# потому что так записаны все станции брокера. Явный "http" означает, что в
# sensors лежит URL, а не топик, и станция опрашивается, а не слушается.
# "metar" - тот же опрос, но ответом идёт JSON-сводка аэропорта.
VALID_SOURCES = ('mqtt', 'http', 'metar')

# Порог свежести HTTP-замера. Сам yartemp обновляет данные раз в 5 минут и не
# гарантирует круглосуточной доступности, поэтому 15 минут - это запас на три
# пропущенных обновления подряд. Протухшее значение не попадает в словари
# вообще, поэтому станция честно молчит, а не портит среднее вчерашним числом.
HTTP_MAX_AGE_S = 900

# Таймаут HTTP-источника. Прогон живёт ~6 минут, но источник не должен этим
# пользоваться: сетевой сбой внешнего сайта обязан кончаться, а не висеть.
HTTP_TIMEOUT_S = 20

# Источник не документирован и не требует авторизации. Единственное, что мы
# шлём, - тот же Referer, что шлёт сам сайт, и cache-busting query, без
# которого ответы могут кэшироваться посередине.
YARTEMP_REFERER = 'https://yartemp.com/'

# Идентификация, которую NOAA требует от автоматических запросов. Без неё
# ответ может прийти 403. Referer не шлём: источник его не требует и он
# ничего не значит для API.
NOAA_USER_AGENT = 'meteomap-yaroslavl/1.0 (github.com/meteomap)'

# Адрес METAR-сводки по коду аэропорта. hours=1 - суточная сводка NOAA
# обновляется раз в полчаса, поэтому часа достаточно; ids= вместо отдельного
# запроса на каждую станцию оставляет возможность опросить несколько кодов.
METAR_ENDPOINT = ('https://aviationweather.gov/api/data/metar'
                  '?format=json&ids=%s&hours=1')

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


def http_stations(stations):
    """Станции, которые опрашиваются по сети, а не слушаются по MQTT.

    Их два вида: http разбирает ответ веб-страницы, metar - сводку аэропорта
    из JSON API. Оба опрашиваются, поэтому и живут в одной выборке; чем
    разбирать ответ, решает collect_http по полю source. Отсутствие поля
    означает mqtt, поэтому существующие станции в stations.json не меняются
    и не обязаны знать про этот выбор.
    """
    return [st for st in stations if st.get('source', 'mqtt') in ('http', 'metar')]


def station_max_age_s(station):
    """Порог свежести станции в секундах.

    Общий HTTP_MAX_AGE_S описывает yartemp, который обновляется раз в 5 минут.
    Источник с другим ритмом требует другого допуска: METAR выходит раз в 30
    минут, и при общем пороге в 15 минут он протухал бы в каждом прогоне,
    то есть не дал бы ни одного числа. Поле необязательное, поэтому станции
    без него сохраняют прежнее поведение.
    """
    return station.get('max_age_s', HTTP_MAX_AGE_S)


def fetch_yartemp(url, timeout_s=HTTP_TIMEOUT_S, now=None, session=None):
    """Опрашивает HTTP-источник. Возвращает (payload, reading_ts) или (None, None).

    Ответ - одна строка, поля разделены ";". Берутся ровно два: [0] температура
    и [1] unix-время САМОГО ЗАМЕРА. Оно, а не время нашего запроса, становится
    меткой прихода, поэтому age_s на сайте показывает свежесть показания.

    Не бросает исключений ни при каком ответе. Публикация sensors_history.json
    не должна зависеть от чужого сайта: сеть отвалилась, сайт отдал HTML вместо
    данных, автор сменил формат - всё это «нет данных», а не падение прогона.
    Худший исход при смене формата - станция молча перестаёт давать значение.
    """
    now = time.time() if now is None else now
    if session is None:
        import requests

        session = requests.Session()
    # Cache-busting: без него ответ может прийти из кэша, и мы запишем в бакет
    # показание, которого никто не измерял.
    query = urlencode({'_': int(now * 1000)})
    try:
        response = session.get('%s?%s' % (url, query),
                               timeout=timeout_s,
                               headers={'Referer': YARTEMP_REFERER})
        response.raise_for_status()
        text = response.text
    except Exception:
        return None, None

    if not text:
        return None, None
    fields = text.strip().split(';')
    if len(fields) < 2:
        return None, None
    try:
        reading_ts = float(fields[1])
    except (TypeError, ValueError):
        return None, None
    if reading_ts != reading_ts or reading_ts <= 0:
        return None, None
    value = fields[0].strip()
    if not value:
        return None, None
    # Значение проверяется здесь, а не в validate(), потому что validate()
    # живёт в общем для обоих транспортов снимке и не знает, откуда пришли
    # данные. Мусор вместо числа не должен доходить до словарей: иначе он
    # попал бы в бакет истории и тихо испортил среднее.
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None, None
    if number != number:
        return None, None
    return value, reading_ts


def parse_metar_report_time(text):
    """Разбирает reportTime NOAA в unix-время. None - если разобрать нельзя.

    Строка приходит с миллисекундами и суффиксом 'Z'
    ('2026-09-30T09:30:00.000Z'); с 3.11 datetime.fromisoformat ест и то, и
    другое, поэтому строка разбирается как есть. Ничего отбрасывать нельзя:
    хвост с миллисекундами отделяется точкой, но точка же может стоять перед
    смещением ('09:30:00.000+03:00'), и отрезанное '+03:00' уехало бы на
    три часа по времени наблюдения. Метка нужна и для бакета часа, и для
    проверки свежести, поэтому неразобранное время означает отказ от показания.
    """
    if not isinstance(text, str) or not text.strip():
        return None
    try:
        moment = datetime.fromisoformat(text.strip())
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.timestamp()


def fetch_metar(url, timeout_s=HTTP_TIMEOUT_S, now=None, session=None):
    """Опрашивает METAR-сводку аэропорта. Возвращает (payload, reading_ts).

    Ответ - JSON-массив, свежая сводка первая. Берутся ровно два поля: temp
    как значение и reportTime как метка наблюдения. Время отдачи ответа не
    годится: между сводками проходит полчаса, и подставь мы его вместо
    reportTime, прогон объявил бы получасовую давность свежим замером.

    Не бросает исключений ни при каком ответе - публикация sensors_history.json
    не должна зависеть от чужого сервиса. Смена формата, HTML вместо JSON,
    обрыв сети - всё это «нет данных», станция просто молчит.

    Параметр now остаётся, хотя внутри не используется: collect_http зовёт
    адаптеры одним и тем же вызовом, и сигнатуры у них обязаны совпадать.
    """
    if session is None:
        import requests

        session = requests.Session()
    try:
        response = session.get(url, timeout=timeout_s,
                               headers={'User-Agent': NOAA_USER_AGENT})
        response.raise_for_status()
        text = response.text
    except Exception:
        return None, None

    if not text:
        return None, None
    try:
        report = json.loads(text)
    except ValueError:
        return None, None
    if not isinstance(report, list) or not report:
        return None, None
    newest = report[0]
    if not isinstance(newest, dict):
        return None, None

    reading_ts = parse_metar_report_time(newest.get('reportTime'))
    if reading_ts is None:
        return None, None

    # Температура проверяется здесь, а не в validate(): validate() живёт в
    # общем снимке и не знает, откуда пришли данные. Мусор или физически
    # невозможное число не должны попасть в бакет истории.
    temp = newest.get('temp')
    if temp is None or isinstance(temp, bool):
        return None, None
    try:
        number = float(temp)
    except (TypeError, ValueError, OverflowError):
        # OverflowError — это целое JSON-число длиннее ~309 цифр: float(temp)
        # падает, хотя TypeError/ValueError здесь не срабатывают. У fetch_yartemp
        # такой ветки нет, он всегда преобразует строку.
        return None, None
    low, high = SENSOR_PARAMS['temperature_2m']
    if not (low <= number <= high):
        return None, None
    # Значение возвращается строкой, как у fetch_yartemp, чтобы build_snapshot
    # не различал транспорты.
    return str(number), reading_ts


def metar_fetcher(icao, timeout_s=HTTP_TIMEOUT_S, now=None, session=None):
    """Разворачивает код аэропорта из конфига в адрес METAR-API.

    В конфиге лежит короткий код аэропорта - 'UUDL'. Он же служит ключом
    словаря полученных значений, и сравнивать его с URL не пришлось бы. Но
    сам по себе это относительный путь, а не адрес: requests на нём падает с
    MissingSchema, fetch_metar глотает исключение, и станция молчала бы при
    каждом прогоне, нигде не оставив следов. Поэтому адрес собирается здесь,
    на границе конфига и транспорта, а адаптеру достаётся готовый URL.
    """
    return fetch_metar(METAR_ENDPOINT % icao, timeout_s=timeout_s,
                       now=now, session=session)


def station_fetcher(station):
    """Адаптер разбора ответа для сетевой станции.

    Транспорт один - HTTP, но формат ответа разный: yartemp отдаёт строку с
    полями через ';', аэропорт отдаёт JSON-сводку. Разбор выбирается здесь,
    чтобы collect_http не ветвился по source на каждую станцию.
    """
    if station.get('source') == 'metar':
        return metar_fetcher
    return fetch_yartemp


def collect_http(received, seen, stations, now, timeout_s=HTTP_TIMEOUT_S):
    """Опрашивает сетевые станции и кладёт ответы в те же словари, что и MQTT.

    Ключом служит URL из sensors - ровно то, что лежит в конфиге, поэтому
    build_snapshot не различает транспорты и не меняется. Протухший или
    непригодный ответ в словари не попадает: станция станет offline сама.
    """
    for st in http_stations(stations):
        fetcher = station_fetcher(st)
        for param, url in st['sensors'].items():
            payload, reading_ts = fetcher(url, now=now, timeout_s=timeout_s)
            if payload is None:
                continue
            # Часы источника могут спешить на несколько секунд. Метка из
            # будущего прошла бы проверку свежести и выглядела бы свежее
            # прогона, поэтому она прижимается к времени опроса.
            if reading_ts > now:
                reading_ts = now
            max_age_s = station_max_age_s(st)
            if now - reading_ts > max_age_s:
                continue
            received[url] = payload
            seen[url] = reading_ts
            break


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
        value_hours = {}
        value_ts = {}
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
            if ts is not None:
                # Час прихода, а не час старта прогона: окно в 10 минут может
                # пересечь границу часа, и без этого замеры следующего часа
                # молча уезжали бы в предыдущий бакет. Без seen (юнит-тесты,
                # --dry) часа нет, и record_history возьмёт час прогона.
                value_hours[param] = moscow_hour_key(ts)
                # Сам момент прихода. Из него на сайте получается подпись
                # «обновлено в 10:53», а из ключа бакета - только «10:00»,
                # что читается как время обновления и вводит в заблуждение.
                value_ts[param] = ts
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
            'value_hours': value_hours,
            'value_ts': value_ts,
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
        source = st.get('source', 'mqtt')
        if source not in VALID_SOURCES:
            raise ValueError('station %r: unknown source %r; allowed: %s'
                             % (sid, source, ', '.join(VALID_SOURCES)))
        # Порог свежести проверяется здесь, а не в collect_http: station_max_age_s
        # отдаёт поле как есть, поэтому мусор в конфиге уронил бы прогон
        # TypeError уже после прослушки эфира. Проверка bool обязательна и
        # идёт первой: bool - подкласс int, и JSON-true в пороге прошёл бы
        # числовую проверку как 1 секунда, то есть станция молчала бы в каждом
        # прогоне, а виноват выглядел бы источник.
        if 'max_age_s' in st:
            raw_age = st['max_age_s']
            if isinstance(raw_age, bool) or not isinstance(raw_age, (int, float)):
                raise ValueError('station %r: max_age_s must be a number: %r'
                                 % (sid, raw_age))
            # json.load берёт литералы NaN и Infinity без кавычек, а json.dump
            # пишет их без кавычек же, поэтому такое значение может прийти в
            # конфиг из любого скрипта, который правит stations.json. Оба
            # проходят проверку типа, а проверка знака их не видит: nan <= 0
            # ложно, и inf > 0 истинно. Дальше порог не превышается никогда,
            # станция не протухает никогда, и в среднее сайта попадают замеры
            # любой давности - то есть порог свежести выключен молча.
            if not math.isfinite(raw_age) or raw_age <= 0:
                raise ValueError('station %r: max_age_s must be a positive '
                                 'finite number: %s' % (sid, raw_age))
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


def moscow_iso(ts):
    """Unix-время в локальный московский ISO с явным смещением.

    Формат тот же, что у ключей бакетов, но с минутами и часовым поясом:
    такой stamp сортируется как строка, поэтому в record_history достаточно
    сравнения '>', а разбор часовых поясов на стороне сайта не нужен.
    """
    return datetime.fromtimestamp(ts, HISTORY_TZ).replace(
        second=0, microsecond=0).isoformat(timespec='seconds')


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
    """Дописывает значения станций в бакеты часов. Пустой прогон не пишется.

    Замер кладётся в бакет часа, который шёл в момент его прихода
    (build_snapshot пишет value_hours), а не в час старта прогона: с окном
    в 10 минут прогон, начавшийся в 22:55, честно набирает замеры часа 23:00,
    и класть их в 22:00 — тихая ошибка на сайте. hour_key (час старта
    прогона) остаётся запасным вариантом для прогонов без времени прихода.

    samples считает вклады станций, а не прогоны: в один бакет попадает станция
    из нескольких прогонов, и старая арифметика "+1 за прогон" перестала бы
    описывать содержимое. Читатель meteo.py:_sensor_hour_value поле samples
    не читает - он считает по stations, поэтому смена смысла безопасна.
    """
    wrote = False
    for station in per_station:
        values = station.get('values')
        if not values:
            continue
        hours_by_param = station.get('value_hours')
        if not isinstance(hours_by_param, dict):
            hours_by_param = {}
        ts_by_param = station.get('value_ts')
        if not isinstance(ts_by_param, dict):
            ts_by_param = {}
        for param, value in values.items():
            key = hours_by_param.get(param, hour_key)
            bucket = hours['hours'].setdefault(key, {'samples': 0, 'stations': {}})
            entry = bucket['stations'].setdefault(station['id'], {})
            entry.setdefault(param, []).append(value)
            bucket['samples'] += 1
            # Метка последнего обновления бакета - время самого позднего
            # пришедшего замера, а не ключ часа: именно её показывает сайт.
            # max(), а не присваивание, потому что в бакет попадают замеры
            # нескольких прогонов и поздний прогон не должен откатывать
            # метку на часы, если после него пришёл более ранний замер часа.
            ts = ts_by_param.get(param)
            stamp = moscow_iso(ts) if ts is not None else key
            if bucket.get('updated_at') is None or stamp > bucket['updated_at']:
                bucket['updated_at'] = stamp
            wrote = True
    return wrote


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
        # Только mqtt-станции: у http-станции в sensors лежит URL, и подписка
        # на него была бы молчаливым мусором в брокере.
        if st.get('source', 'mqtt') != 'mqtt':
            continue
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
    # HTTP-станции опрашиваются после прослушки, но до снимка: и MQTT, и HTTP
    # должны описывать один и тот же момент времени, иначе age_s у разных
    # станций означал бы разное.
    collect_http(received, seen, stations, time.time())
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
