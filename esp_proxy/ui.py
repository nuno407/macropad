"""Display dashboard, buttons, backlight and screen sleep.

code.py owns nothing visual: it calls note_activity() when real user
input arrives (hid/enc frames) and tick(now, pad_linked) every loop.
"""

import os
import time

import board
import digitalio
import displayio
import terminalio
# bitmap_label.Label scrolls with the same API; scrolling_label is deprecated
from adafruit_display_text.bitmap_label import Label as ScrollLabel
from adafruit_display_text.label import Label

import blehid
import config
import net

display = board.DISPLAY
display.rotation = config.ROTATION

# Backlight for screen sleep. Prefer manual control of LCD_BCKL (active-low
# on this board); if the board build already owns that pin, fall back to
# the display's brightness control.
try:
    _bl = digitalio.DigitalInOut(board.LCD_BCKL)
    _bl.direction = digitalio.Direction.OUTPUT

    def set_backlight(on):
        _bl.value = not on            # active-low: low = on
except ValueError:
    def set_backlight(on):
        display.brightness = 1.0 if on else 0.0

# Two side buttons (active-low). Used to wake the screen.
_btns = []
for _pin in (board.BUTTON0, board.BUTTON1):
    _b = digitalio.DigitalInOut(_pin)
    _b.direction = digitalio.Direction.INPUT
    _b.pull = digitalio.Pull.UP
    _btns.append(_b)
_btn_prev = [b.value for b in _btns]


def _buttons_pressed():
    """True if any button went down since the last call (edge, debounced
    by the ~10ms loop)."""
    hit = False
    for i, b in enumerate(_btns):
        v = b.value
        if _btn_prev[i] and not v:    # high->low = press
            hit = True
        _btn_prev[i] = v
    return hit


# ---- dashboard widgets ----------------------------------------------------

_root = displayio.Group()
_bg = displayio.Bitmap(display.width, display.height, 1)
_pal = displayio.Palette(1)
_pal[0] = 0x000000
_root.append(displayio.TileGrid(_bg, pixel_shader=_pal))

_title = Label(terminalio.FONT, text="MacroPad Bridge", color=0x00FFFF, x=6, y=8)
_l_wifi_pre = Label(terminalio.FONT, text="WiFi:", color=0xFFFFFF, x=4, y=32)
# Only the SSID scrolls (marquee) when it's too long for the remaining width.
_l_wifi = ScrollLabel(terminalio.FONT, max_characters=14, text="...",
                      animate_time=0.25, color=0xFFFFFF, x=40, y=32)
# Same pattern as the WiFi row: white prefix, coloured status value.
_l_pad_pre = Label(terminalio.FONT, text="MacroPad:", color=0xFFFFFF, x=4, y=52)
_l_pad = Label(terminalio.FONT, text="...", color=0xFFFFFF, x=64, y=52)
_l_ble_pre = Label(terminalio.FONT, text="BLE:", color=0xFFFFFF, x=4, y=72)
_l_ble = Label(terminalio.FONT, text="...", color=0xFFFFFF, x=34, y=72)
_l_clock = Label(terminalio.FONT, text="--:--:--", color=0xFFFFFF, scale=2, x=16, y=100)
_l_tz = Label(terminalio.FONT, text="", color=0x808080, x=48, y=118)
for _o in (_title, _l_wifi_pre, _l_wifi, _l_pad_pre, _l_pad,
           _l_ble_pre, _l_ble, _l_clock, _l_tz):
    _root.append(_o)
display.root_group = _root

_wifi_txt = None
_last_activity = time.monotonic()
_awake = True
_refresh_due = 0.0

set_backlight(True)


def _dashboard_update(pad_linked):
    global _wifi_txt
    if net.connected():
        txt = os.getenv("WIFI_SSID") or "?"
        _l_wifi.color = 0x00FF00
    else:
        txt = "off"
        _l_wifi.color = 0xFF4040
    if txt != _wifi_txt:   # only reassign on change, else the scroll resets
        _wifi_txt = txt
        _l_wifi.text = txt
    _l_pad.text = "linked" if pad_linked else "--"
    _l_pad.color = 0x00FF00 if pad_linked else 0xFF4040
    ble_up = blehid.connected()
    # advertising is a waiting state, not a fault - orange, not red
    _l_ble.text = "connected" if ble_up else "waiting for PC"
    _l_ble.color = 0x00FF00 if ble_up else 0xFFA000
    if net.clock_ok:
        lt = time.localtime(time.time() + net.tz_off)
        _l_clock.text = "%02d:%02d:%02d" % (lt.tm_hour, lt.tm_min, lt.tm_sec)
        _l_tz.text = net.tz_abbr or "Lisbon"
    else:
        _l_clock.text = "--:--:--"
        _l_tz.text = ""


def note_activity():
    """Real user input (pad hid/enc frames). Buttons are handled in tick()."""
    global _last_activity
    _last_activity = time.monotonic()


def tick(now, pad_linked):
    """Call every main-loop pass: buttons, screen sleep, dashboard refresh."""
    global _last_activity, _awake, _refresh_due

    if _buttons_pressed():
        _last_activity = now

    # sleep: backlight off after SLEEP_S idle; any activity wakes it. The
    # pad's 4s keepalive is deliberately NOT activity (else it never sleeps).
    if config.SLEEP_S:
        idle = now - _last_activity
        if _awake and idle > config.SLEEP_S:
            set_backlight(False)
            _awake = False
        elif not _awake and idle < 0.2:
            set_backlight(True)
            _awake = True

    if _awake:
        _l_wifi.update()   # marquee-scroll long SSIDs (self-throttled)
        if now >= _refresh_due:
            _refresh_due = now + 1
            _dashboard_update(pad_linked)
