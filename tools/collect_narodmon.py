#!/usr/bin/env python3
"""Собирает температуру с публичных приборов narodmon.ru.

Источник - тот же список, что рисует карта проекта: ответ /map отдаёт
приборы в заданном прямоугольнике, а показание - готовой строкой для
балуна ("+9°, 94%, 766mmHg"). Это не документированный контракт, а
внутренний эндпоинт интерфейса, поэтому коллектор обязан деградировать
тихо: обрыв narodmon уменьшает число станций, но не роняет сбор.

Температура опознаётся по знаку градуса: в строке остаются и влажность,
и давление, и ветер, и цифровые выходы, но градус есть только у
температуры. Приборы без градуса пропускаются, а не читаются как ноль.
"""

import json
import math
import re

DEGREE = '\u00b0'
# Минус в трёх видах: ASCII, U+2212 (типографский) и «тире» U+2013.
MINUS_CHARS = '\u2212\u2013'

# Знак, число, необязательный пробел, знак градуса. Якорь справа обязателен:
# без него "+10°, ON, 97%" дал бы 10, но и "767mmHg" разобрался бы как 767.
_TEMP_RE = re.compile(
    r'([+%s-]?\d+(?:\.\d+)?)\s*%s' % (re.escape(MINUS_CHARS), DEGREE))

STATION_PREFIX = 'nm-'

# Базовый адрес и параметры запроса повторяют то, что делает сама страница.
# sens=1 обязателен: без него сервер отвечает пустым списком, даже если
# границы верные. Границы в градусах, lat/lon - в порядке ответа сервера.
BASE_URL = 'https://narodmon.ru'
MAP_PATH = '/map'
USER_AGENT = 'MeteoMap/1.0 (samlab.github.io/MeteoMap)'


def _map_url(lat, lon, radius_km):
    """Собирает URL выборки. Отбор идёт прямоугольником, а радиусом мы
    режем уже разобранный ответ - сервер не знает про наш радиус."""
    dlat = float(radius_km) / 111.32
    # Косинус широты: километр по долготе короче, чем по широте.
    dlon = dlat / max(0.01, abs(math.cos(math.radians(float(lat)))))
    bounds = (float(lat) - dlat, float(lon) - dlon,
              float(lat) + dlat, float(lon) + dlon)
    query = ('ajax=1&types=0&sens=1&cw=1280&tz=3&bounds='
             + ','.join('%.6f' % v for v in bounds))
    return '%s%s?%s' % (BASE_URL, MAP_PATH, query)


def _http_map_fetch(url):
    """GET с cookie-сессией. Ответ или None.

    Главная страница выдаёт сессионную cookie, и /map без неё отвечает 403
    даже с браузерным User-Agent. Логин не нужен: сессия анонимная, но
    без неё эндпоинт не отдаёт данных, поэтому шаг с главной обязателен.
    """
    import urllib.error
    import urllib.request
    from http.cookiejar import CookieJar

    jar = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    headers = {'User-Agent': USER_AGENT, 'Referer': BASE_URL + '/',
               'X-Requested-With': 'XMLHttpRequest'}
    opener.open(urllib.request.Request(BASE_URL + '/', headers=headers),
                timeout=20).read()
    try:
        with opener.open(urllib.request.Request(url, headers=headers),
                         timeout=20) as response:
            return response.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError:
        return None


def parse_temperature(text):
    """Достаёт температуру из строки показаний. None - градуса нет.

    Единица измерения в строке может быть любой, поэтому отсеиваем всё
    остальное якорем, а не знаком: знак есть и у отрицательной температуры,
    но давление, влажность и освещённость со знаком не выводятся.
    """
    if not isinstance(text, str):
        return None
    match = _TEMP_RE.search(text)
    if match is None:
        return None
    raw = match.group(1)
    for ch in MINUS_CHARS:
        raw = raw.replace(ch, '-')
    try:
        return float(raw)
    except ValueError:
        return None


def station_id(device_id):
    """Идентификатор прибора для sensors.json и истории.

    Префикс nm- отделяет приборы narodmon от станций MQTT-сети: id вида
    'penaty' из stations.json не должен пересекаться с числовым кодом
    проекта, иначе два разных прибора склеятся в один бакет истории.
    """
    if isinstance(device_id, bool):
        raise ValueError('device id must be an integer, got %r' % (device_id,))
    if isinstance(device_id, str):
        text = device_id.strip()
        if not text.isdigit():
            raise ValueError('device id must be an integer, got %r' % (device_id,))
        return STATION_PREFIX + str(int(text))
    if isinstance(device_id, int):
        return STATION_PREFIX + str(device_id)
    if isinstance(device_id, float) and device_id.is_integer():
        return STATION_PREFIX + str(int(device_id))
    raise ValueError('device id must be an integer, got %r' % (device_id,))


def haversine_km(lat1, lon1, lat2, lon2):
    """Расстояние между точками на сфере, км.

    Радиус земли - средний, 6371 км. Для отбора станций в пределах города
    разница с эллипсоидом WGS84 меньше погрешности самих показаний.
    """
    radius_km = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
    return 2 * radius_km * math.asin(math.sqrt(min(1.0, a)))


def parse_map_response(raw):
    """Разбирает ответ /map в список приборов. Мусор - пустой список.

    Ответ - литерал массива, который страница отдаёт в eval(), но по
    синтаксису это обычный JSON, поэтому парсится без eval: строка из
    внешнего источника не должна попадать в исполняемый код.
    """
    if not isinstance(raw, str):
        return []
    text = raw.strip()
    if not text.startswith('['):
        # 'STOP' и прочие маркеры недоступности сюда попадают.
        return []
    try:
        data = json.loads(text)
    except ValueError:
        return []
    if not isinstance(data, list):
        return []

    out = []
    for entry in data:
        if not isinstance(entry, list) or len(entry) < 7:
            # Пустой служебный маркер в начале ответа - не прибор.
            continue
        device_id = entry[0]
        if isinstance(device_id, bool) or not isinstance(device_id, int):
            continue
        try:
            lat = float(entry[2]) / 1e6
            lon = float(entry[3]) / 1e6
        except (TypeError, ValueError):
            continue
        name = entry[5] if isinstance(entry[5], str) else ''
        out.append({
            'id': device_id,
            'name': name.strip() or None,
            'lat': lat,
            'lon': lon,
            'time': entry[4],
            'raw': entry[6],
            'temperature': parse_temperature(entry[6]),
        })
    return out


def within_radius(devices, lat, lon, radius_km):
    """Оставляет приборы не дальше radius_km от точки. Расстояние
    добавляется в запись, чтобы прогон мог показать, кто и насколько далеко."""
    limit = float(radius_km)
    out = []
    for device in devices:
        distance = haversine_km(lat, lon, device['lat'], device['lon'])
        if distance > limit:
            continue
        entry = dict(device)
        entry['distance_km'] = round(distance, 2)
        out.append(entry)
    return out


def build_stations(devices):
    """Приборы с температурой -> записи формы stations.json.

    Прибор без градуса пропускается целиком: частично заполненная станция
    участвовала бы в среднем как «есть значение», а на сайте читалась бы
    как работающая, и молчала бы там, где данных нет.

    Значение округляется до одного знака: источник отдаёт целые градусы,
    и хранить два знака - значит выдавать точность, которой нет.
    """
    out = []
    for device in devices:
        temperature = device.get('temperature')
        if temperature is None:
            continue
        sid = station_id(device['id'])
        out.append({
            'id': sid,
            # Название прибора может отсутствовать, а таблица Часов печатает
            # имя: пустое имя - это визуальный баг, а не «нет данных».
            'name': device.get('name') or sid,
            'lat': round(float(device['lat']), 5),
            'lon': round(float(device['lon']), 5),
            'sensors': {'temperature_2m': round(float(temperature), 1)},
            'time': device.get('time'),
        })
    return out


def collect_narodmon(lat, lon, radius_km, fetch=None):
    """Опрашивает карту narodmon.ru и возвращает станции в форме конфига.

    Любая неудача - пустой список, а не исключение: источник внешний и не
    документированный, его обрыв не должен ронять общий сбор, в котором
    параллельно живут станции MQTT-сети.
    """
    if fetch is None:
        fetch = _http_map_fetch
    try:
        body = fetch(_map_url(lat, lon, radius_km))
    except Exception:
        # Сеть, TLS, редирект - внешние причины, коллектор обязан продолжить.
        return []
    if not body:
        return []
    devices = within_radius(parse_map_response(body), lat, lon, radius_km)
    return build_stations(devices)
