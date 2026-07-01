#!/usr/bin/env python3
"""MacroPad bridge proxy - wire protocol v1. Generic by design.

This proxy knows NOTHING about keys, actions, or the OLED. It only:
  - answers pings with a pong (port discovery + link liveness)
  - answers time requests with the PC clock's UTC epoch
  - executes HTTP requests the pad asks for, optionally extracting
    JSON paths ("pick") so the pad never parses large bodies

All application logic lives on the pad (macropad/). Add features
there, not here. Keep this file boring - esp_proxy/ implements the same
role on the T-QT.

Usage:  .venv/bin/python bridge.py [--port /dev/cu.usbmodemXXXX] [--verbose]
Deps:   uv pip install -p .venv/bin/python -r requirements.txt
"""

import argparse
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

import requests
import serial
from serial.tools import list_ports

ADAFRUIT_VID = 0x239A
HTTP_TIMEOUT = 10
LINE_MAX = 6000       # absolute serialized-line cap
ALLOWED_SCHEMES = ("http://", "https://")

# Optional generic guard (policy, not application logic): comma-separated
# hostnames the proxy may contact. Empty/unset = allow all.
ALLOW_HOSTS = frozenset(
    h.strip().lower()
    for h in os.environ.get("MACROPAD_ALLOW_HOSTS", "").split(",")
    if h.strip())


def pick_path(data, path):
    """Resolve a dot path like 'current.temperature_2m' or '0.title'."""
    cur = data
    for seg in path.split("."):
        if isinstance(cur, list):
            try:
                cur = cur[int(seg)]
            except (ValueError, IndexError):
                return None
        elif isinstance(cur, dict):
            if seg not in cur:
                return None
            cur = cur[seg]
        else:
            return None
    return cur


class Proxy:
    def __init__(self, ser, verbose=False):
        self.ser = ser
        self.verbose = verbose
        self.lock = threading.Lock()
        self.pool = ThreadPoolExecutor(max_workers=4)

    # ------------------------- transport -------------------------
    def send(self, obj):
        line = json.dumps(obj)
        if len(line) > LINE_MAX and obj.get("t") == "res":
            obj = {"t": "res", "id": obj.get("id"),
                   "st": obj.get("st"), "err": "too_big"}
            line = json.dumps(obj)
        if self.verbose:
            print(f"tx: {line}")
        with self.lock:
            self.ser.write(line.encode() + b"\n")

    def reader_loop(self, initial=b""):
        """Blocks forever; raises SerialException when the pad goes away.

        `initial`: bytes discovery read while waiting for the pong - the
        pad sends hello/time as soon as the port opens, so they may sit
        in front of (or behind) the pong and must not be dropped.
        """
        self.ser.timeout = 0.2
        buf = initial
        while True:
            while b"\n" in buf:
                raw, buf = buf.split(b"\n", 1)
                self.handle(raw.strip())
            buf += self.ser.read(256)

    # ------------------------- protocol --------------------------
    def handle(self, raw):
        if not raw:
            return
        if self.verbose:
            print(f"rx: {raw.decode(errors='replace')}")
        try:
            msg = json.loads(raw)
        except ValueError:
            return
        t = msg.get("t")
        if t == "hello":
            print("pad connected")
        elif t == "ping":
            self.send({"t": "pong"})   # discovery + pad-side liveness
        elif t == "time":
            self.send({"t": "time", "epoch": int(time.time())})
        elif t == "http":
            self.pool.submit(self.do_http, msg)
        # "pong" only matters during discovery; anything else is ignored.
        # That includes "hid"/"enc": key forwarding and encoder events
        # are the ESP32 proxy's job - over USB the pad delivers keys
        # itself as a HID device.

    def do_http(self, msg):
        rid = msg.get("id")
        method = str(msg.get("m", "GET")).upper()
        url = str(msg.get("url", ""))
        if not url.startswith(ALLOWED_SCHEMES):
            return self.send({"t": "res", "id": rid, "err": "scheme"})
        if ALLOW_HOSTS:
            host = (urlsplit(url).hostname or "").lower()
            if host not in ALLOW_HOSTS:
                return self.send({"t": "res", "id": rid, "err": "host"})

        kwargs = {"timeout": HTTP_TIMEOUT}
        try:
            r = requests.request(method, url, **kwargs)
        except Exception as exc:
            return self.send({"t": "res", "id": rid,
                              "err": exc.__class__.__name__[:24]})

        # Minimal response: status always; extracted values only when the
        # pad asked via "pick". Raw bodies are never returned.
        res = {"t": "res", "id": rid, "st": r.status_code}
        pick = msg.get("pick")
        if pick:
            try:
                data = r.json()
            except ValueError:
                res["err"] = "json"
            else:
                res["v"] = [pick_path(data, str(p)) for p in pick]
        if self.verbose:
            print(f"{method} {url} -> {r.status_code}")
        self.send(res)


# ------------------------- port discovery ------------------------
def candidate_ports(explicit):
    if explicit:
        return [explicit]
    return [p.device for p in list_ports.comports() if p.vid == ADAFRUIT_VID]


def open_pad(explicit):
    """Ping each candidate port; the pad's DATA channel answers with pong.

    Returns (ser, leftover). `leftover` is everything read while waiting
    for the pong; the pad's hello/time lines often arrive first and the
    caller must feed them to the reader (the pong line itself is ignored
    by Proxy.handle).
    """
    for dev in candidate_ports(explicit):
        try:
            ser = serial.Serial(dev, 115200, timeout=0.2)
        except (OSError, serial.SerialException):
            continue
        try:
            ser.reset_input_buffer()
            ser.write(b'{"t":"ping"}\n')
            deadline = time.time() + 1.5
            buf = b""
            while time.time() < deadline:
                buf += ser.read(256)
                if b'"pong"' in buf:
                    print(f"MacroPad data port: {dev}")
                    return ser, buf
        except (OSError, serial.SerialException):
            pass
        ser.close()
    return None, b""


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", help="serial device of the pad's DATA port")
    ap.add_argument("--verbose", action="store_true",
                    help="log every rx/tx protocol line")
    args = ap.parse_args()

    while True:
        ser, leftover = open_pad(args.port)
        if ser is None:
            print("searching for MacroPad... "
                  "(boot.py installed? hard reset done?)")
            time.sleep(2)
            continue
        proxy = Proxy(ser, verbose=args.verbose)
        try:
            proxy.reader_loop(initial=leftover)
        except (OSError, serial.SerialException):
            print("pad disconnected, retrying...")
        finally:
            proxy.pool.shutdown(wait=False)
            try:
                ser.close()
            except Exception:
                pass
        time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nbye")
