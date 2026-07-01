"""Hardware-free tests for the PC-daemon proxy (run with: pytest -q).

A FakeSerial with in-memory buffers stands in for the pad; HTTP is
stubbed at the requests boundary. No application logic is asserted
here because the proxy must not contain any.
"""

import json
import time

import pytest
import serial

import bridge
from bridge import Proxy, pick_path


class FakeSerial:
    """In-memory serial.Serial stand-in.

    Reads pop from a chunk queue; an exhausted queue raises
    SerialException exactly like a vanished USB device, which is what
    terminates Proxy.reader_loop in real life.
    """

    timeout = 0.2

    def __init__(self, chunks=()):
        self.chunks = list(chunks)
        self.tx = b""

    def read(self, size=256):
        if not self.chunks:
            raise serial.SerialException("pad gone")
        return self.chunks.pop(0)

    def write(self, data):
        self.tx += data
        return len(data)

    def sent(self):
        return [json.loads(l) for l in self.tx.splitlines() if l.strip()]


class FakeResponse:
    def __init__(self, text="", status_code=200, data=None):
        self.text = text
        self.status_code = status_code
        self._data = data

    def json(self):
        if self._data is None:
            raise ValueError("not json")
        return self._data


def stub_http(monkeypatch, response):
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return response

    monkeypatch.setattr(bridge.requests, "request", fake_request)
    return calls


# ---------------------------------------------------------------- pick_path

def test_pick_path_nested_dicts():
    data = {"current": {"temperature_2m": 18.4, "wind_speed_10m": 7.9}}
    assert pick_path(data, "current.temperature_2m") == 18.4


def test_pick_path_list_indices():
    assert pick_path([42, 43], "0") == 42
    assert pick_path({"a": [{"title": "hi"}]}, "a.0.title") == "hi"


def test_pick_path_missing_keys():
    assert pick_path({"a": {"b": 1}}, "a.c") is None
    assert pick_path({"a": [1]}, "a.5") is None


def test_pick_path_type_mismatches():
    assert pick_path({"a": [1, 2]}, "a.x") is None      # non-int on a list
    assert pick_path({"a": 1}, "a.b") is None           # descend into scalar
    assert pick_path("scalar", "a") is None


# ----------------------------------------------------------- scheme / hosts

def test_scheme_rejection():
    p = Proxy(FakeSerial())
    p.do_http({"id": 1, "m": "GET", "url": "file:///etc/passwd"})
    p.do_http({"id": 2, "m": "GET", "url": "ftp://example.com/x"})
    assert p.ser.sent() == [
        {"t": "res", "id": 1, "err": "scheme"},
        {"t": "res", "id": 2, "err": "scheme"},
    ]


def test_allow_hosts_guard(monkeypatch):
    monkeypatch.setattr(bridge, "ALLOW_HOSTS", frozenset({"api.allowed.com"}))
    stub = stub_http(monkeypatch, FakeResponse(text="ok"))
    p = Proxy(FakeSerial())
    p.do_http({"id": 1, "m": "GET", "url": "https://evil.com/x"})
    p.do_http({"id": 2, "m": "GET", "url": "https://API.Allowed.com/x"})
    msgs = p.ser.sent()
    assert msgs[0] == {"t": "res", "id": 1, "err": "host"}
    assert msgs[1]["st"] == 200
    assert [u for _, u, _ in stub] == ["https://API.Allowed.com/x"]


# ------------------------------------------------------ minimal responses

def test_no_pick_returns_status_only(monkeypatch):
    # raw bodies are never returned - the pad only ever reads st/v/err
    stub_http(monkeypatch, FakeResponse(text="x" * 5000, status_code=204))
    p = Proxy(FakeSerial())
    p.do_http({"id": 1, "m": "POST", "url": "https://e.com/hook"})
    (res,) = p.ser.sent()
    assert res == {"t": "res", "id": 1, "st": 204}


def test_oversized_line_collapses_to_too_big(monkeypatch):
    # a huge picked value can still blow the line cap
    stub_http(monkeypatch,
              FakeResponse(text="j", data={"a": "x" * (bridge.LINE_MAX + 100)}))
    p = Proxy(FakeSerial())
    p.do_http({"id": 1, "m": "GET", "url": "https://e.com/huge",
               "pick": ["a"]})
    (res,) = p.ser.sent()
    assert res["err"] == "too_big"
    assert "v" not in res


def test_pick_on_non_json_reports_err(monkeypatch):
    stub_http(monkeypatch, FakeResponse(text="<html>"))
    p = Proxy(FakeSerial())
    p.do_http({"id": 1, "m": "GET", "url": "https://e.com/x", "pick": ["a"]})
    (res,) = p.ser.sent()
    assert res["err"] == "json"


def test_transport_error_reports_class_name(monkeypatch):
    def boom(method, url, **kwargs):
        raise bridge.requests.exceptions.ConnectTimeout("nope")

    monkeypatch.setattr(bridge.requests, "request", boom)
    p = Proxy(FakeSerial())
    p.do_http({"id": 1, "m": "GET", "url": "https://e.com/x"})
    (res,) = p.ser.sent()
    assert res == {"t": "res", "id": 1, "err": "ConnectTimeout"}


# ----------------------------------------------------------- line framing

def test_framing_across_split_reads():
    # messages split across reads must still be assembled and handled
    fake = FakeSerial([b'{"t":"pi', b'ng"}\n{"t":', b'"ping"}\n'])
    p = Proxy(fake)
    with pytest.raises(serial.SerialException):
        p.reader_loop()
    assert [m["t"] for m in fake.sent()] == ["pong", "pong"]


def test_reader_consumes_discovery_leftover():
    # hello/ping read by open_pad while waiting for the pong must be
    # handled, and the pong line itself ignored
    leftover = b'{"t":"hello"}\n{"t":"pong"}\n{"t":"ping"}\n'
    fake = FakeSerial()
    p = Proxy(fake)
    with pytest.raises(serial.SerialException):
        p.reader_loop(initial=leftover)
    replies = fake.sent()
    assert len(replies) == 1 and replies[0]["t"] == "pong"


# ----------------------------------------------------------------- ping

def test_ping_answered_with_pong():
    p = Proxy(FakeSerial())
    p.handle(b'{"t":"ping"}')
    assert p.ser.sent() == [{"t": "pong"}]


def test_time_reply_is_utc_epoch():
    p = Proxy(FakeSerial())
    before = int(time.time())
    p.handle(b'{"t":"time"}')
    after = int(time.time())
    (msg,) = p.ser.sent()
    assert msg["t"] == "time"
    assert before <= msg["epoch"] <= after
    assert "off" not in msg   # zone offsets are local math on the pad
