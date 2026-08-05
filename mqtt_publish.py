import json
import math
from datetime import datetime, timedelta, timezone

SITE_URL = "https://samlab.github.io/MeteoMap/index.html"
MQTT_HOST = "yar.gorod76.ru"
MQTT_PORT = 1883
MQTT_TOPIC_PREFIX = "city/out/pogoda"

NEEDLE = '<script id="data" type="application/json">'

MOSCOW = timezone(timedelta(hours=3))

RAIN_CODES = [51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82]
STORM_CODES = [95, 96, 99]
HAIL_CODES = [96, 99]

COMPASS = ["С", "СВ", "В", "ЮВ", "Ю", "ЮЗ", "З", "СЗ"]

WCODE = {
    0: "Ясно", 1: "В основном ясно", 2: "Переменная облачность", 3: "Пасмурно",
    45: "Туман", 48: "Изморозь",
    51: "Небольшая морось", 53: "Морось", 55: "Сильная морось",
    56: "Ледяная морось", 57: "Ледяная морось",
    61: "Небольшой дождь", 63: "Дождь", 65: "Сильный дождь",
    66: "Ледяной дождь", 67: "Ледяной дождь",
    71: "Небольшой снег", 73: "Снег", 75: "Сильный снег", 77: "Снежные зерна",
    80: "Небольшой ливень", 81: "Ливень", 82: "Сильный ливень",
    85: "Снегопад", 86: "Снегопад",
    95: "Гроза", 96: "Гроза с градом", 99: "Гроза с градом",
}


def fmt(x):
    if x is None:
        return None
    return math.floor(x * 10 + 0.5) / 10


def num(x):
    if x is None:
        return None
    return int(math.floor(x + 0.5))


def weather_text(code):
    return WCODE.get(code, "—")


def rumb_short(deg):
    if deg is None:
        return "—"
    return COMPASS[int(math.floor(deg / 45 + 0.5)) % 8]


def parse_payload(html):
    start = html.find(NEEDLE)
    if start < 0:
        return None
    start += len(NEEDLE)
    end = html.find("</script>", start)
    if end < 0:
        return None
    try:
        return json.loads(html[start:end])
    except ValueError:
        return None


def cur_idx(data, now_hour=None):
    if now_hour is None:
        now_hour = datetime.now(MOSCOW).strftime("%Y-%m-%dT%H:00")
    for i, t in enumerate(data.get("time") or []):
        if str(t) >= now_hour:
            return i
    return 0


def iso_time(t):
    s = str(t)
    return s if s.endswith("+03:00") else s + "+03:00"


def _w(data, var, i):
    arr = (data.get("weighted") or {}).get(var) or []
    return arr[i] if i < len(arr) else None


def _model_codes(data):
    return data.get("model_codes") or []


def _model_wc(data, code, i):
    m = (data.get("models") or {}).get(code) or {}
    arr = m.get("weather_code") or []
    return arr[i] if i < len(arr) else None


def _source_list(data, i, codes):
    return [c for c in _model_codes(data) if _model_wc(data, c, i) in codes]


def _source_names(data, i, codes):
    names = data.get("model_names") or {}
    return [names.get(c, c) for c in _source_list(data, i, codes)]


def find_rain_by_consensus(data, frm):
    for i in range(frm, len(data.get("time") or [])):
        if _w(data, "weather_code", i) in RAIN_CODES:
            return i
    return -1


def find_nearest_source(data, frm, codes):
    for i in range(frm, len(data.get("time") or [])):
        if _source_list(data, i, codes):
            return i
    return -1


def build_now(data, idx, updated_at):
    return {
        "temperature": fmt(_w(data, "temperature_2m", idx)),
        "feels_like": fmt(_w(data, "apparent_temperature", idx)),
        "weather": weather_text(_w(data, "weather_code", idx)),
        "wind_speed": fmt(_w(data, "wind_speed_10m", idx)),
        "wind_dir": rumb_short(_w(data, "wind_direction_10m", idx)),
        "pressure": num(_w(data, "pressure_msl", idx)),
        "humidity": num(_w(data, "relative_humidity_2m", idx)),
        "updated_at": updated_at,
    }


def build_horizon(data, idx, horizon_h, updated_at):
    j = idx + horizon_h
    doc = {"horizon_h": horizon_h}
    times = data.get("time") or []
    if j >= len(times):
        return doc
    doc.update({
        "time": iso_time(times[j]),
        "temperature": fmt(_w(data, "temperature_2m", j)),
        "weather": weather_text(_w(data, "weather_code", j)),
        "precip_mm": fmt(_w(data, "precipitation", j)),
        "precip_prob": num(_w(data, "precipitation_probability", j)),
        "wind_speed": fmt(_w(data, "wind_speed_10m", j)),
        "wind_dir": rumb_short(_w(data, "wind_direction_10m", j)),
        "updated_at": updated_at,
    })
    return doc


def build_rain(data, frm):
    times = data.get("time") or []
    doc = {"rain": None, "thunder": None, "hail": None}
    ri = find_rain_by_consensus(data, frm)
    if ri >= 0:
        doc["rain"] = {
            "time": iso_time(times[ri]),
            "precip_mm": fmt(_w(data, "precipitation", ri)),
            "probability": num(_w(data, "precipitation_probability", ri)),
            "models": len(_source_list(data, ri, RAIN_CODES)),
        }
    ti = find_nearest_source(data, frm, STORM_CODES)
    if ti >= 0:
        doc["thunder"] = {
            "time": iso_time(times[ti]),
            "precip_mm": fmt(_w(data, "precipitation", ti)),
            "probability": num(_w(data, "precipitation_probability", ti)),
            "sources": _source_names(data, ti, STORM_CODES),
        }
    hi = find_nearest_source(data, frm, HAIL_CODES)
    if hi >= 0:
        doc["hail"] = {
            "time": iso_time(times[hi]),
            "precip_mm": fmt(_w(data, "precipitation", hi)),
            "probability": num(_w(data, "precipitation_probability", hi)),
            "sources": _source_names(data, hi, HAIL_CODES),
        }
    return doc


def build_all(data, now_hour=None, updated_at=None):
    if updated_at is None:
        updated_at = datetime.now(MOSCOW).isoformat(timespec="seconds")
    idx = cur_idx(data, now_hour)
    return {
        "now": build_now(data, idx, updated_at),
        "3": build_horizon(data, idx, 3, updated_at),
        "6": build_horizon(data, idx, 6, updated_at),
        "12": build_horizon(data, idx, 12, updated_at),
        "rain": build_rain(data, idx),
    }


def topic_for(prefix, name):
    return "{}/{}".format(prefix, name)


def publish_docs(host, port, prefix, docs, client=None):
    import time
    own = False
    if client is None:
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            raise SystemExit("paho-mqtt is not installed (pip install paho-mqtt)")
        if hasattr(mqtt, "CallbackAPIVersion"):
            client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION1)
        else:
            client = mqtt.Client()
        client.connect(host, port, keepalive=30)
        client.loop_start()
        own = True
    infos = []
    try:
        for name, payload in docs.items():
            infos.append(client.publish(
                topic_for(prefix, name),
                json.dumps(payload, ensure_ascii=False),
                retain=True,
            ))
        deadline = time.time() + 10
        while time.time() < deadline and not all(i.is_published() for i in infos):
            time.sleep(0.1)
        if not all(i.is_published() for i in infos):
            raise RuntimeError("MQTT publish timeout")
    finally:
        if own:
            client.loop_stop()
            client.disconnect()
    return len(infos)


def fetch_html(url):
    import urllib.request
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read().decode("utf-8")


def main():
    import os
    host = os.environ.get("MQTT_HOST", MQTT_HOST)
    port = int(os.environ.get("MQTT_PORT", MQTT_PORT))
    prefix = os.environ.get("MQTT_TOPIC_PREFIX", MQTT_TOPIC_PREFIX)
    url = os.environ.get("SITE_URL", SITE_URL)
    html = fetch_html(url)
    data = parse_payload(html)
    if data is None:
        raise SystemExit("Failed to parse payload from " + url)
    docs = build_all(data)
    n = publish_docs(host, port, prefix, docs)
    print("published {} topics to {}:{} prefix={}".format(n, host, port, prefix))


if __name__ == "__main__":
    main()
