"""Hardware + shared state: the MacroPad object, the OLED layout, the
proxy serial link, and the state dicts every other module reads."""

import time

import board
import busio
import displayio
import supervisor
import terminalio
import usb_cdc
from adafruit_display_text import label
from adafruit_macropad import MacroPad

import config

GREEN = (0, 255, 0)
RED = (255, 0, 0)
PRESS = (120, 120, 120)

macropad = MacroPad()
macropad.pixels.brightness = config.BRIGHT_PCT / 100

# Custom layout (display_text can't bottom-align): title row pinned to
# the top, a 4x3 grid mirroring the physical keys in the middle, and
# the clock anchored to the BOTTOM edge of the panel.
screen = displayio.Group()


def _mk_label(y, anchor=(0, 0), x=0):
    lab = label.Label(terminalio.FONT, text="", color=0xFFFFFF,
                      anchor_point=anchor, anchored_position=(x, y))
    screen.append(lab)
    return lab


title_l = _mk_label(0)
grid_l = [_mk_label(12 + 10 * i) for i in range(4)]
clock_l = _mk_label(64, anchor=(0.5, 1.0), x=64)  # bottom-center
macropad.display.root_group = screen
SLEEP_SCREEN = displayio.Group()  # empty group = every OLED pixel off

title_l.text = "     MacroPad v2"
grid_l[0].text = "starting..."

if config.LINK_MODE == "uart":
    # uart mode: the proxy lives on the T-QT across the STEMMA QT UART.
    # SDA = pad TX -> proxy RX, SCL = pad RX <- proxy TX, shared GND.
    ser = busio.UART(tx=board.SDA, rx=board.SCL, baudrate=115200,
                     timeout=0, receiver_buffer_size=512)
else:
    ser = usb_cdc.data  # None when boot.py isn't active - code.py handles it
    if ser is not None:
        ser.timeout = 0
        try:
            ser.write_timeout = 0
        except Exception:
            pass

state = {"time_ok": False, "temp": None, "wx_busy": False,
         "wx_due": 0.0, "time_due": 0.0, "tick_due": 0.0, "last_min": -1,
         "bt_pc": False,  # proxy-reported Bluetooth link to the PC
         "wifi": None,    # proxy-reported WiFi state (None = not reported)
         "awake": True,   # False = screen/LEDs blanked by sleep mode
         "last_rx": -999.0,  # monotonic time of last inbound line (UART)
         "ka_due": 0.0}   # next UART liveness ping
pending = {}   # request id -> (callback, deadline)
flashes = {}   # key number -> restore deadline


def clean(s):
    """ASCII-only, 21 chars max - the OLED font renders nothing else."""
    return "".join(c if " " <= c <= "~" else "?" for c in str(s))[:21]


def link_connected():
    """Is the proxy reachable? USB has a carrier line; UART does not,
    so liveness is inferred from recent inbound traffic (the pad
    pings every LINK_KEEPALIVE s and the proxy answers pong)."""
    if config.LINK_MODE == "uart":
        return (time.monotonic() - state["last_rx"]) < config.LINK_TIMEOUT
    return ser.connected


def pc_connected():
    """True when key events can reach the PC: enumerated as USB HID,
    or the proxy reports a Bluetooth HID link to the PC ({"t":"link"}).
    uart mode: the proxy runs WiFi (HTTP) and BLE HID to the PC at
    the same time, so either path may carry the keys."""
    return supervisor.runtime.usb_connected or state["bt_pc"]
