"""Wire protocol + HID routing: JSON lines to the proxy, async http with
pick extraction, the pad's clock sync, and key delivery to the PC.

Inbound "link" updates repaint the title through the `on_link` hook
(set by code.py) so this module never imports the UI."""

import json
import time

import rtc
import supervisor

from adafruit_hid.keycode import Keycode

import config
import shared

next_id = 0
rx = b""
on_link = None   # callable, set by code.py: repaint after a link update


def send(obj):
    """Best-effort write; never let a missing proxy crash the pad."""
    try:
        shared.ser.write(json.dumps(obj).encode() + b"\n")
    except Exception:
        pass


def http(method, url, on_done, pick=None, timeout=config.REQ_TIMEOUT):
    """Fire an async request through the proxy. on_done(msg_or_None)."""
    global next_id
    next_id += 1
    msg = {"t": "http", "id": next_id, "m": method, "url": url}
    if pick is not None:
        msg["pick"] = pick
    shared.pending[next_id] = (on_done, time.monotonic() + timeout)
    send(msg)
    return next_id


def values(res, n):
    """Return n picked values from a response, or None on any failure."""
    if not res or res.get("st") != 200:
        return None
    v = res.get("v")
    if not isinstance(v, list) or len(v) < n:
        return None
    return v


def _last_sunday_0100(year, month):
    """Epoch of 01:00 UTC on the last Sunday of a 31-day month."""
    e31 = time.mktime((year, month, 31, 1, 0, 0, 0, 0, -1))
    wd = time.localtime(e31).tm_wday          # Monday=0 ... Sunday=6
    return e31 - ((wd + 1) % 7) * 86400


def lisbon_offset(epoch_utc):
    """Europe/Lisbon offset by the fixed EU DST rule: WEST (UTC+1)
    from the last Sunday of March 01:00 UTC to the last Sunday of
    October 01:00 UTC, WET (UTC+0) otherwise. Same rule as the proxy;
    no network needed."""
    year = time.localtime(epoch_utc).tm_year
    if _last_sunday_0100(year, 3) <= epoch_utc < _last_sunday_0100(year, 10):
        return 3600
    return 0


def set_clock(epoch_utc):
    """Set the RTC to Lisbon wall time from a UTC epoch (the proxy's
    NTP-synced clock, mirrored over the protocol - the pad has no radio
    of its own); the offset is local math."""
    epoch_utc = int(epoch_utc)
    rtc.RTC().datetime = time.localtime(epoch_utc + lisbon_offset(epoch_utc))
    shared.state["time_ok"] = True
    shared.state["last_min"] = -1


def sync_clock():
    """Ask the proxy for its NTP-synced UTC epoch. It only answers once
    its own clock is set, so the pad shows "syncing..." until then."""
    shared.state["time_due"] = time.monotonic() + config.TIME_PERIOD
    send({"t": "time"})


def handle(msg):
    t = msg.get("t")
    if t == "ping":
        send({"t": "pong"})
    elif t == "time":
        if "epoch" in msg:
            set_clock(msg["epoch"])
    elif t == "res":
        item = shared.pending.pop(msg.get("id"), None)
        if item:
            item[0](msg)
    elif t == "link":
        # the proxy reports its Bluetooth HID link to the PC and/or its
        # WiFi state; both fields optional. The USB daemon never sends it.
        if "pc" in msg:
            shared.state["bt_pc"] = bool(msg["pc"])
        if "net" in msg:
            shared.state["wifi"] = bool(msg["net"])
        if on_link:
            on_link()


def poll_serial():
    global rx
    try:
        n = shared.ser.in_waiting
    except Exception:
        return
    if not n:
        return
    chunk = shared.ser.read(n)
    if not chunk:           # UART.read may return None even when waiting
        return
    rx += chunk
    while True:
        i = rx.find(b"\n")
        if i < 0:
            return
        raw, rx = rx[:i], rx[i + 1:]
        if not raw:
            continue
        try:
            msg = json.loads(raw)
        except ValueError:
            continue
        shared.state["last_rx"] = time.monotonic()  # valid line = link alive
        handle(msg)


def deliver_keys(codes, cc=None):
    """Route HID to the PC. USB when enumerated (lowest latency);
    otherwise forward to the proxy as {"t":"hid","k":[...],"cc":n} for
    Bluetooth delivery (uart proxy; inert with the USB-only proxy).
    `codes` are held while the optional consumer code `cc` fires, then
    released - that one shape covers chords and fine volume alike."""
    if supervisor.runtime.usb_connected:
        try:
            if cc is None:
                shared.macropad.keyboard.send(*codes)
            else:
                if codes:
                    shared.macropad.keyboard.press(*codes)
                shared.macropad.consumer_control.send(cc)
            return True
        except Exception:
            return False
        finally:
            if cc is not None and codes:
                try:
                    shared.macropad.keyboard.release(*codes)
                except Exception:
                    pass
    if shared.state["bt_pc"]:
        msg = {"t": "hid", "k": list(codes)}
        if cc is not None:
            msg["cc"] = int(cc)
        send(msg)
        return True
    return False


def send_volume(code):
    """One volume event; with FINE_VOL, Shift+Option makes macOS move
    in quarter-steps so each detent is a small nudge, not a jump."""
    deliver_keys([Keycode.SHIFT, Keycode.ALT] if config.FINE_VOL else [],
                 cc=code)
