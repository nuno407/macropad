"""Tunables for the pad. Per-install values come from settings.toml (see
settings.toml.example); menu-tweakable prefs persist in macropad_prefs.json
on the drive (writable only while the USB drive is hidden, i.e. normal use).
"""

import json
import os

from adafruit_hid.keycode import Keycode

# ----------------- settings.toml (user-owned) -----------------------------
LAT = float(os.getenv("MACROPAD_LAT") or "38.722")
LON = float(os.getenv("MACROPAD_LON") or "-9.139")
LOC_NAME = os.getenv("MACROPAD_LOC_NAME") or "Lisbon"
MOD = {"CTRL": Keycode.CONTROL, "CMD": Keycode.COMMAND}.get(
    (os.getenv("MACROPAD_MOD") or "CMD").upper(), Keycode.COMMAND)

# ----------------- product constants ---------------------------------------
REQ_TIMEOUT = 10       # seconds before an in-flight request fails
WEATHER_PERIOD = 600   # background weather refresh for the status line
TIME_PERIOD = 3600     # clock re-sync interval (proxy's NTP via "time")
ENC_WINDOW = 0.15      # s - encoder counts are majority-voted per window
                       # because this encoder emits noisy reverse bursts
ENC_REV_WINDOWS = 2    # opposing windows in a row to reverse mid-twirl
                       # (a pause >0.5s resets direction instantly)
LONG_PRESS = 0.8       # s - hold the encoder to open the menu / go back
CHORD_KEYS = (9, 10, 11)  # bottom row: chords control the menu
CHORD_WAIT = 0.25      # s - bottom-row keys fire on release or after
                       # this hold, so chords can't trigger them
LINK_KEEPALIVE = 4     # s - UART has no carrier line, so the pad pings
LINK_TIMEOUT = 12      # s - ... and treats silence past this as offline

# ----------------- menu-tweakable prefs (macropad_prefs.json) --------------
PREFS_FILE = "/macropad_prefs.json"
ENC_DIV = max(1, int(os.getenv("MACROPAD_ENC_DIV") or "1"))
                       # encoder detents per volume step (higher = gentler)
# macOS adjusts volume in quarter-steps when Shift+Option is held with
# the volume key. Default: on when the modifier is CMD (= macOS host);
# force with MACROPAD_FINE_VOL = 1 or 0 in settings.toml.
_fv = os.getenv("MACROPAD_FINE_VOL")
FINE_VOL = (MOD == Keycode.COMMAND) if _fv is None else str(_fv) == "1"
BRIGHT_PCT = 20
SLEEP_MIN = 5          # screen/LEDs off after this many idle minutes (0=never)
# Which physical link carries the proxy protocol:
#   "usb"  -> usb_cdc.data (bridge daemon on this PC)
#   "uart" -> busio.UART on the STEMMA QT pins (the T-QT proxy)
# Changing it takes effect after a reload (Ctrl-D / save / replug).
LINK_MODE = "usb"
PAGE = 0               # active key page, remembered across reboots

try:
    with open(PREFS_FILE) as _f:
        _p = json.load(_f)
    ENC_DIV = max(1, int(_p.get("enc_div", ENC_DIV)))
    FINE_VOL = bool(_p.get("fine_vol", FINE_VOL))
    BRIGHT_PCT = int(_p.get("brightness", BRIGHT_PCT))
    SLEEP_MIN = int(_p.get("sleep", SLEEP_MIN))
    LINK_MODE = "uart" if _p.get("link") == "uart" else "usb"
    PAGE = int(_p.get("page", PAGE))
except Exception:
    pass


def save_prefs():
    """Persist the tweakables; False if the FS is read-only (drive
    mounted via KEY12) - values still apply for this session."""
    try:
        with open(PREFS_FILE, "w") as f:
            json.dump({"enc_div": ENC_DIV,
                       "fine_vol": 1 if FINE_VOL else 0,
                       "brightness": BRIGHT_PCT,
                       "sleep": SLEEP_MIN,
                       "link": LINK_MODE,
                       "page": PAGE}, f)
    except OSError:
        return False
    return True
