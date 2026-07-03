"""LilyGo T-QT Pro bridge proxy (CircuitPython).

The generic, LOGIC-FREE proxy role (same as host/bridge.py and what the
pad's code.py expects): UART to the pad, WiFi for HTTP(S), NTP for time,
a BLE HID keyboard into the PC, and a status dashboard on the screen.

Modules:  config.py tunables · net.py WiFi/time/HTTP · blehid.py BLE
keyboard · ui.py display/buttons/sleep.  This file owns the UART
transport, protocol dispatch and the main loop.

Wiring (T-QT <-> MacroPad, STEMMA QT cable):  SDA = pad TX -> T-QT RX,
  SCL = pad RX <- T-QT TX  (so busio.UART(tx=board.SCL, rx=board.SDA))
settings.toml (see settings.toml.example): WIFI_SSID, WIFI_PASSWORD,
  SLEEP_S (idle screen-off seconds, 0=never)
Libraries (/lib, bundle major must match CircuitPython major):
  adafruit_ble adafruit_hid adafruit_requests adafruit_connection_manager
  adafruit_ntp adafruit_display_text adafruit_ticks

Wire protocol v1 (minimal; a change must update macropad/, esp_proxy/ AND host/):
  pad -> proxy: hello / ping (liveness) / time (clock request)
                http{id,m,url,pick?} / hid{k,cc?,mc?} / enc{d}
  proxy -> pad: pong / time{epoch} (UTC; answered once NTP has synced)
                res{id,st,v?}|{id,err} / link{pc,net}
Unknown message types are ignored by both sides. Both devices compute
the Lisbon offset locally; the pad mirrors this proxy's NTP clock.
"""

import json
import time

import board
import busio

import blehid
import config
import net
import ui

# STEMMA QT cable to the pad: TX on SCL, RX on SDA (pad uses SDA=TX/SCL=RX).
uart = busio.UART(board.SCL, board.SDA, baudrate=115200, timeout=0,
                  receiver_buffer_size=4096)


def send(obj):
    line = json.dumps(obj)
    if len(line) > config.LINE_MAX and obj.get("t") == "res":
        obj = {"t": "res", "id": obj.get("id"), "st": obj.get("st"),
               "err": "too_big"}
        line = json.dumps(obj)
    uart.write(line.encode() + b"\n")


# ------------------------------- protocol ---------------------------------

link_pc = None
link_net = None
last_pad = -999.0   # far past: "linked" only after a real frame arrives


def send_link(force=False):
    global link_pc, link_net
    pc = blehid.connected()
    net_up = net.connected()
    if force or pc != link_pc or net_up != link_net:
        link_pc, link_net = pc, net_up
        send({"t": "link", "pc": pc, "net": net_up})


def handle(msg):
    global last_pad
    last_pad = time.monotonic()
    t = msg.get("t")
    if t == "hello":
        send_link(force=True)
    elif t == "ping":
        send({"t": "pong"})   # liveness: the pad infers the link from this
    elif t == "time":
        if net.clock_ok:      # only answer with a real (NTP-synced) epoch
            send({"t": "time", "epoch": int(time.time())})
    elif t == "http":
        send(net.do_http(msg))
    elif t == "hid":
        ui.note_activity()    # real user input wakes/keeps the screen on
        blehid.do_hid(msg)
    elif t == "enc":
        ui.note_activity()    # encoder detents count as user activity
    # unknown types are ignored - that's what keeps additions safe


# ------------------------------- main loop --------------------------------

blehid.ensure_advertising()
net.up()
net.sync_clock()
print("bridge proxy ready")

buf = b""
net_due = 0.0

while True:
    now = time.monotonic()

    data = uart.read(256)
    if data:
        buf += data
        while b"\n" in buf:
            raw, buf = buf.split(b"\n", 1)
            raw = raw.strip()
            if not raw:
                continue
            try:
                handle(json.loads(raw))
            except ValueError:
                pass

    if now >= net_due:
        net_due = now + config.NET_PERIOD
        net.up()
        blehid.ensure_advertising()
        send_link()   # only transmits on a state change

    if net.ntp_due and now >= net.ntp_due:
        net.sync_clock()

    ui.tick(now, now - last_pad < config.PAD_TIMEOUT)

    time.sleep(0.01)
