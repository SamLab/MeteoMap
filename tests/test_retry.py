import requests

import meteo


class _Resp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def test_retry_returns_json_on_first_ok():
    calls = []

    def get(url, params, timeout):
        calls.append(1)
        return _Resp(200, {"ok": True})

    out = meteo.request_with_retry("http://x", {}, 5, get=get)
    assert out == {"ok": True}
    assert len(calls) == 1


def test_retry_recovers_from_429():
    calls = []

    def get(url, params, timeout):
        calls.append(1)
        if len(calls) < 3:
            return _Resp(429)
        return _Resp(200, {"ok": True})

    out = meteo.request_with_retry(
        "http://x", {}, 5, get=get, max_retries=3, base_delay=0
    )
    assert out == {"ok": True}
    assert len(calls) == 3


def test_retry_raises_after_max_retries():
    calls = []

    def get(url, params, timeout):
        calls.append(1)
        return _Resp(429)

    try:
        meteo.request_with_retry(
            "http://x", {}, 5, get=get, max_retries=2, base_delay=0
        )
        assert False, "expected HTTPError"
    except requests.exceptions.HTTPError:
        pass
    assert len(calls) == 3


def test_retry_on_timeout():
    calls = []

    def get(url, params, timeout):
        calls.append(1)
        if len(calls) < 2:
            raise requests.exceptions.Timeout("t")
        return _Resp(200, {"ok": True})

    out = meteo.request_with_retry(
        "http://x", {}, 5, get=get, max_retries=2, base_delay=0
    )
    assert out == {"ok": True}
    assert len(calls) == 2


def test_no_retry_on_400():
    calls = []

    def get(url, params, timeout):
        calls.append(1)
        return _Resp(400)

    try:
        meteo.request_with_retry(
            "http://x", {}, 5, get=get, max_retries=2, base_delay=0
        )
        assert False, "expected HTTPError"
    except requests.exceptions.HTTPError:
        pass
    assert len(calls) == 1
