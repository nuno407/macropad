"""WiFi, the clock (NTP + local DST rule) and logic-free HTTP proxying.

Module-level state other modules read: tz_off/tz_abbr/clock_ok (ui) and
ntp_due (code.py's scheduler). do_http() RETURNS the response dict so the
transport stays in code.py.
"""

import os
import ssl
import time

import rtc
import socketpool
import wifi

import adafruit_ntp
import adafruit_requests

import config

session = None
tz_off = 0                # set by sync_clock (local EU DST rule)
tz_abbr = ""              # "WEST"/"WET", set alongside tz_off
ntp_due = 0.0
clock_ok = False          # RTC has been NTP-synced at least once


def log(*args):
    print(*args)


def up():
    """Connect (or reconnect) WiFi; True when associated."""
    global session
    if wifi.radio.connected:
        return True
    ssid = os.getenv("WIFI_SSID")
    if not ssid:
        return False
    try:
        wifi.radio.power_management = wifi.PowerManagement.NONE
    except (AttributeError, NotImplementedError):
        pass
    try:
        log("wifi: connecting to", ssid)
        wifi.radio.connect(ssid, os.getenv("WIFI_PASSWORD") or "")
    except Exception as exc:
        log("wifi:", exc)
        return False
    pool = socketpool.SocketPool(wifi.radio)
    session = adafruit_requests.Session(pool, ssl.create_default_context())
    log("wifi: up,", wifi.radio.ipv4_address)
    return True


def connected():
    return wifi.radio.connected


def sync_clock():
    """NTP -> local RTC (UTC), plus the Lisbon UTC offset + abbreviation."""
    global tz_off, tz_abbr, ntp_due, clock_ok
    if not wifi.radio.connected:
        return
    try:
        pool = socketpool.SocketPool(wifi.radio)
        rtc.RTC().datetime = adafruit_ntp.NTP(pool, tz_offset=0).datetime
        ntp_due = time.monotonic() + config.NTP_PERIOD
        clock_ok = True
        log("ntp: clock set")
    except Exception as exc:
        log("ntp:", exc)
        ntp_due = time.monotonic() + 60
        return
    tz_off, tz_abbr = lisbon_offset(time.time())
    log("tz:", tz_abbr, tz_off)


def _last_sunday_0100(year, month):
    """Epoch of 01:00 UTC on the last Sunday of a 31-day month."""
    e31 = time.mktime((year, month, 31, 1, 0, 0, 0, 0, -1))
    wd = time.localtime(e31).tm_wday          # Monday=0 ... Sunday=6
    return e31 - ((wd + 1) % 7) * 86400


def lisbon_offset(epoch_utc):
    """Europe/Lisbon offset by the fixed EU DST rule: WEST (UTC+1)
    from the last Sunday of March 01:00 UTC to the last Sunday of
    October 01:00 UTC, WET (UTC+0) otherwise. No network needed."""
    year = time.localtime(epoch_utc).tm_year
    if _last_sunday_0100(year, 3) <= epoch_utc < _last_sunday_0100(year, 10):
        return 3600, "WEST"
    return 0, "WET"


def _pick_path(data, path):
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


def do_http(msg):
    """Run one protocol "http" request; returns the "res" dict to send."""
    rid = msg.get("id")
    method = str(msg.get("m", "GET")).upper()
    url = str(msg.get("url", ""))
    if not url.startswith(config.ALLOWED_SCHEMES):
        return {"t": "res", "id": rid, "err": "scheme"}
    if session is None or not wifi.radio.connected:
        return {"t": "res", "id": rid, "err": "NoWifi"}

    kwargs = {"timeout": config.HTTP_TIMEOUT}
    try:
        r = session.request(method, url, **kwargs)
    except Exception as exc:
        return {"t": "res", "id": rid, "err": exc.__class__.__name__[:24]}

    # Minimal response: status always; extracted values only when the pad
    # asked for them via "pick". Raw bodies are never returned (nothing
    # consumes them - the pad's small heap shouldn't parse big payloads).
    res = {"t": "res", "id": rid, "st": r.status_code}
    pick = msg.get("pick")
    try:
        if pick:
            try:
                data = r.json()
            except ValueError:
                res["err"] = "json"
            else:
                res["v"] = [_pick_path(data, str(p)) for p in pick]
    finally:
        r.close()
    return res
