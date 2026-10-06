import pytest

from tools.collect_narodmon import (
    build_stations,
    collect_narodmon,
    haversine_km,
    parse_map_response,
    parse_temperature,
    station_id,
    within_radius,
)

# Реальные строки из ответа narodmon.ru/map (снимок 2026-09-29).
# Формат: готовый текст для балуна на карте, датчики перечислены
# через запятую, у каждого своя единица измерения.
MAP_SAMPLES = [
    '+12°, 1m/s, 82%',
    '+12°, 767mmHg',
    '+11°',
    '+10°, ON, 97%',
    '+9°, 94%, 766mmHg',
    '+9°, 99%, 772mmHg',
    '+10°, 863Lx',
    '+13°, 765mmHg, 100%',
]


@pytest.mark.parametrize('text', MAP_SAMPLES)
def test_parse_temperature_reads_degree_value(text):
    # Температура - единственное значение с градусом, поэтому знак градуса
    # и есть надёжный якорь: давление, влажность, люкс, ветер и цифровой
    # выход градуса не имеют и не должны быть приняты за температуру.
    assert isinstance(parse_temperature(text), float)


def test_parse_temperature_handles_negative_sign():
    assert parse_temperature('-7°') == pytest.approx(-7.0)


def test_parse_temperature_handles_unicode_minus():
    # U+2212 вместо ASCII-минуса встречается в разных источниках.
    assert parse_temperature('\u22125°') == pytest.approx(-5.0)


def test_parse_temperature_handles_fractional_value():
    assert parse_temperature('-13.54°') == pytest.approx(-13.54)


@pytest.mark.parametrize('text', [
    '49%, 762mmHg',
    '764mmHg',
    '67%, 767mmHg',
    '1013mmHg',
    '55%',
    '863Lx',
    '1m/s',
    'ON',
    '',
])
def test_parse_temperature_yields_none_without_degree(text):
    # Приборы без температуры не пропускаем: температура не найдена, а не ноль.
    assert parse_temperature(text) is None


def test_parse_temperature_yields_none_for_garbage():
    assert parse_temperature('###') is None


def test_station_id_is_namespaced():
    # id narodmon не должен совпадать с id из stations.json (penaty, frunze...),
    # иначе станции склеятся в один бакет истории.
    assert station_id(8528) == 'nm-8528'


def test_station_id_is_stable():
    assert station_id(8528) == station_id(8528)


def test_station_id_rejects_non_integer():
    with pytest.raises(ValueError):
        station_id('BME280HABA')


# Ответ narodmon.ru/map - это не JSON, а литерал массива, который страница
# передаёт в eval(). Первый элемент всегда пустой, дальше идут приборы:
# [id, тип, lat*1e6, lon*1e6, unixtime, имя, показания, имя, ""]
# Координаты приходят целыми, умноженными на 1e6, поэтому в тесте - сырые
# целые, как в ответе, а не готовые десятичные.
RAW_MAP = (
    '[[],'
    '[8528,255,57612112,39887462,1790673000,"BME280HABA","+9°, 99%, 772mmHg",'
    '"BME280HABA",""],'
    '[9730,255,57661062,40065337,1790673000,"Пестрецово","+11°","D9730",""],'
    '[101491,255,57561000,40157000,1790673000,"Yaroslav/Tunoshna Arpt IAR",'
    '"+12°, 1m/s, 82%","Yaroslav/Tunoshna Arpt IAR",""],'
    '[1343,255,57725800,39757000,1790673000,"ESP8266+BME280","+13°, 765mmHg, 100%",'
    '"ESP8266+BME280",""],'
    '[726,255,57582953,39840247,1790673000,"gorod76.ru","49%, 762mmHg",'
    '"gorod76.ru",""]]'
)

CITY_LAT = 57.62
CITY_LON = 39.90
CITY_RADIUS_KM = 12.0


def test_parse_map_response_reads_devices():
    devices = parse_map_response(RAW_MAP)
    assert len(devices) == 5


def test_parse_map_response_skips_leading_empty_marker():
    # Пустой первый элемент - служебный маркер, не прибор: без фильтра он
    # превратился бы в станцию без координат.
    devices = parse_map_response(RAW_MAP)
    assert all(d['id'] is not None for d in devices)


def test_parse_map_response_scales_coordinates():
    device = next(d for d in parse_map_response(RAW_MAP) if d['id'] == 8528)
    assert device['lat'] == pytest.approx(57.612112)
    assert device['lon'] == pytest.approx(39.887462)


def test_parse_map_response_keeps_name_and_time():
    device = next(d for d in parse_map_response(RAW_MAP) if d['id'] == 9730)
    assert device['name'] == 'Пестрецово'
    assert device['time'] == 1790673000


def test_parse_map_response_reads_temperature():
    device = next(d for d in parse_map_response(RAW_MAP) if d['id'] == 8528)
    assert device['temperature'] == pytest.approx(9.0)


def test_parse_map_response_yields_none_temperature_when_absent():
    # gorod76.ru отдаёт только влажность и давление - температуры нет.
    device = next(d for d in parse_map_response(RAW_MAP) if d['id'] == 726)
    assert device['temperature'] is None


def test_parse_map_response_yields_none_on_empty_body():
    assert parse_map_response('') == []


def test_parse_map_response_yields_none_on_error_marker():
    # При недоступности сервиса страница получает STOP вместо данных.
    assert parse_map_response('STOP') == []


def test_haversine_matches_known_distance():
    # Пестрецово - около 10.9 км от центра, радиус 12 км обязан его вмещать.
    km = haversine_km(CITY_LAT, CITY_LON, 57.661062, 40.065337)
    assert 10.0 < km < 11.5


def test_haversine_is_zero_for_same_point():
    assert haversine_km(CITY_LAT, CITY_LON, CITY_LAT, CITY_LON) == pytest.approx(0.0)


def test_within_radius_keeps_pestrecovo():
    # Требование заказчика: Пестрецово (10.9 км) обязано попасть в выборку.
    kept = {d['id'] for d in within_radius(parse_map_response(RAW_MAP),
                                          CITY_LAT, CITY_LON, CITY_RADIUS_KM)}
    assert 9730 in kept


def test_within_radius_drops_airport():
    # Аэропорт Тунoshna в 16.7 км и самый тёплый показатель в выборке (+12°):
    # он тянул бы среднее по городу вверх.
    kept = {d['id'] for d in within_radius(parse_map_response(RAW_MAP),
                                          CITY_LAT, CITY_LON, CITY_RADIUS_KM)}
    assert 101491 not in kept


def test_within_radius_drops_far_suburb():
    # 14.5 км, тоже за радиусом.
    kept = {d['id'] for d in within_radius(parse_map_response(RAW_MAP),
                                          CITY_LAT, CITY_LON, CITY_RADIUS_KM)}
    assert 1343 not in kept


def test_within_radius_keeps_nearby_city_sensor():
    kept = {d['id'] for d in within_radius(parse_map_response(RAW_MAP),
                                          CITY_LAT, CITY_LON, CITY_RADIUS_KM)}
    assert 8528 in kept


def test_within_radius_keeps_device_without_temperature():
    # Прибор внутри радиуса остаётся в списке даже без температуры: решение
    # «пропустить» принимает отборка значений, а не география.
    kept = {d['id'] for d in within_radius(parse_map_response(RAW_MAP),
                                          CITY_LAT, CITY_LON, CITY_RADIUS_KM)}
    assert 726 in kept


def _fetcher(body, status=200, calls=None):
    """Подмена сети: возвращает тело ответа и пишет себя в calls."""
    def fetch(url):
        if calls is not None:
            calls.append(url)
        if status != 200:
            return None
        return body
    return fetch


def test_collect_narodmon_returns_station_shaped_dicts():
    # Форма повторяет stations.json, поэтому build_snapshot принимает её
    # без отдельной ветки: ключ sensors - тот же temperature_2m.
    stations = collect_narodmon(CITY_LAT, CITY_LON, CITY_RADIUS_KM,
                                fetch=_fetcher(RAW_MAP))
    assert stations
    for st in stations:
        assert set(st) == {'id', 'name', 'lat', 'lon', 'sensors', 'time'}
        assert list(st['sensors']) == ['temperature_2m']


def test_collect_narodmon_namespaces_ids():
    stations = collect_narodmon(CITY_LAT, CITY_LON, CITY_RADIUS_KM,
                                fetch=_fetcher(RAW_MAP))
    assert all(st['id'].startswith('nm-') for st in stations)


def test_collect_narodmon_keeps_device_name():
    stations = collect_narodmon(CITY_LAT, CITY_LON, CITY_RADIUS_KM,
                                fetch=_fetcher(RAW_MAP))
    assert any(st['name'] == 'Пестрецово' for st in stations)


def test_collect_narodmon_rounds_to_one_decimal():
    # На входе отображаются целые градусы, поэтому хранить больше одного
    # знака - значит показывать точность, которой нет.
    stations = collect_narodmon(CITY_LAT, CITY_LON, CITY_RADIUS_KM,
                                fetch=_fetcher(RAW_MAP))
    for st in stations:
        assert round(st['sensors']['temperature_2m'], 1) == st['sensors']['temperature_2m']


def test_collect_narodmon_skips_device_without_temperature():
    stations = collect_narodmon(CITY_LAT, CITY_LON, CITY_RADIUS_KM,
                                fetch=_fetcher(RAW_MAP))
    assert 'nm-726' not in {st['id'] for st in stations}


def test_collect_narodmon_respects_radius():
    kept = {st['id'] for st in collect_narodmon(
        CITY_LAT, CITY_LON, CITY_RADIUS_KM, fetch=_fetcher(RAW_MAP))}
    assert 'nm-101491' not in kept
    assert 'nm-9730' in kept


def test_collect_narodmon_degrades_to_empty_on_http_failure():
    # Ключевое требование: обрыв narodmon уменьшает число станций,
    # но не роняет сбор - MQTT-станции должны уехать в тот же снимок.
    assert collect_narodmon(CITY_LAT, CITY_LON, CITY_RADIUS_KM,
                            fetch=_fetcher('', status=403)) == []


def test_collect_narodmon_degrades_to_empty_on_error_marker():
    assert collect_narodmon(CITY_LAT, CITY_LON, CITY_RADIUS_KM,
                            fetch=_fetcher('STOP')) == []


def test_collect_narodmon_returns_empty_on_empty_body():
    assert collect_narodmon(CITY_LAT, CITY_LON, CITY_RADIUS_KM,
                            fetch=_fetcher('')) == []


def test_build_stations_falls_back_to_id_when_name_missing():
    # Прибор без названия не должен попасть в снимок с name=None:
    # таблица Часов печатает имя, и пустое имя - это визуальный баг.
    stations = build_stations([{'id': 4242, 'name': None, 'lat': 57.6,
                                'lon': 39.9, 'time': 1790673000,
                                'temperature': 5.0}])
    assert stations[0]['name'] == 'nm-4242'


def test_build_stations_keeps_reporting_time():
    # Час показания нужен, чтобы замер лёг в бакет того часа, в который
    # прибор реально отчитался, а не в час запуска прогона.
    stations = build_stations([{'id': 4242, 'name': 'x', 'lat': 57.6,
                                'lon': 39.9, 'time': 1790673000,
                                'temperature': 5.0}])
    assert stations[0]['time'] == 1790673000
