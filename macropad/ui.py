"""Everything the user sees and navigates: OLED drawing, key pages and
their actions, the settings menu, the screen test, and sleep mode."""

import time

import displayio

from adafruit_hid.consumer_control_code import ConsumerControlCode
from adafruit_hid.keycode import Keycode

import config
import proto
import shared
from shared import (GREEN, RED, clean, grid_l, clock_l, title_l,
                    link_connected, macropad, pc_connected, state)

WMO = {0: "clear", 1: "clear-ish", 2: "cloudy", 3: "overcast", 45: "fog",
       48: "fog", 51: "drizzle", 53: "drizzle", 55: "drizzle", 61: "rain",
       63: "rain", 65: "rain+", 66: "frz rain", 67: "frz rain", 71: "snow",
       73: "snow", 75: "snow+", 77: "snow", 80: "showers", 81: "showers",
       82: "showers+", 95: "storm", 96: "storm", 99: "storm"}

WEATHER_URL = ("https://api.open-meteo.com/v1/forecast"
               "?latitude={}&longitude={}"
               "&current=temperature_2m,wind_speed_10m,weather_code"
               ).format(config.LAT, config.LON)
WEATHER_PICK = ["current.temperature_2m", "current.wind_speed_10m",
                "current.weather_code"]

view = {"mode": "idle", "cur": 0, "top": 0, "edit": 0}
KEYMAP = {}
page_i = 0

# ------------------------------ drawing -----------------------------------

def show(l1, l2=""):
    grid_l[0].text = clean(l1)
    grid_l[1].text = clean(l2)
    grid_l[2].text = ""
    grid_l[3].text = ""


def fail(key, l1, l2=""):
    show(l1, l2)
    flash(key, RED)


def flash(key, color):
    if key is None or key < 0:
        return
    macropad.pixels[key] = color
    shared.flashes[key] = time.monotonic() + 0.4


def base_color(n):
    """Idle LED encodes the key type: blue=net, amber=hid,
    purple=media (cc), off=unmapped."""
    kind = KEYMAP.get(n, (None,))[0]
    if kind == "net":
        return (0, 30, 80)
    if kind == "hid":
        return (70, 35, 0)
    if kind == "cc":
        return (50, 0, 60)
    return (0, 0, 0)


def draw_title():
    """Title row: temperature top-left, page name CENTERED, link
    glyphs top-RIGHT ('P' = PC link via USB or Bluetooth, 'W' = net
    link via the proxy; '-' = that link is down)."""
    pc = "P" if pc_connected() else "-"
    net = "W" if (link_connected() and state["wifi"] is not False) else "-"
    name = PAGES[page_i][0] if PAGES else "MacroPad"
    row = [" "] * 21
    if state["temp"] is not None and link_connected():
        for i, ch in enumerate(clean("%.0fC" % state["temp"])[:5]):
            row[i] = ch
    start = (21 - len(name)) // 2
    for i, ch in enumerate(clean(name)):
        if 0 <= start + i < 19:
            row[start + i] = ch
    row[19] = pc
    row[20] = net
    title_l.text = "".join(row)


def draw_status():
    """Bottom edge: full date+time, centered, ticking every second."""
    if view["mode"] != "idle" or not state["awake"]:
        return  # the menu or sleep mode owns the display
    if not link_connected():
        clk = "proxy offline"
    elif state["time_ok"]:
        t = time.localtime()
        clk = "%04d/%02d/%02d %02d:%02d:%02d" % (
            t.tm_year, t.tm_mon, t.tm_mday, t.tm_hour, t.tm_min, t.tm_sec)
    else:
        clk = "syncing..."
    clock_l.text = clean(clk)  # label is anchored bottom-center

# ------------------------------ actions -----------------------------------
# Each action composes its own request(s), formats its own output and
# gives its own LED feedback. The proxy knows nothing about any of this.

def fetch_weather(on_done):
    proto.http("GET", WEATHER_URL, on_done, pick=WEATHER_PICK)


def bg_weather():
    """Silent refresh of the cached temperature for the status line."""
    if state["wx_busy"]:
        return
    state["wx_busy"] = True

    def done(res):
        state["wx_busy"] = False
        vals = proto.values(res, 3)
        if vals is None:
            state["wx_due"] = time.monotonic() + 60  # retry soon
            return
        state["wx_due"] = time.monotonic() + config.WEATHER_PERIOD
        state["temp"] = vals[0]
        draw_title()  # temperature lives on the title row

    fetch_weather(done)


def act_weather(key):
    def done(res):
        vals = proto.values(res, 3)
        if vals is None:
            return fail(key, "weather failed")
        temp, wind, code = vals
        state["temp"] = temp
        draw_title()  # temperature lives on the title row
        show("{} {:.1f}C {}".format(config.LOC_NAME, temp,
                                    WMO.get(int(code), "?")),
             "wind {:.0f} km/h".format(wind))
        flash(key, GREEN)
    fetch_weather(done)


def act_hn(key):
    def got_item(res):
        vals = proto.values(res, 2)
        if vals is None:
            return fail(key, "hn failed")
        title = vals[0] or "?"
        show(title[:21], title[21:42] or "{} points".format(vals[1] or 0))
        flash(key, GREEN)

    def got_ids(res):
        vals = proto.values(res, 1)
        if vals is None or vals[0] is None:
            return fail(key, "hn failed")
        proto.http("GET",
                   "https://hacker-news.firebaseio.com/v0/item/{}.json"
                   .format(vals[0]),
                   got_item, pick=["title", "score"])

    proto.http("GET", "https://hacker-news.firebaseio.com/v0/topstories.json",
               got_ids, pick=["0"])


# ------------------------ pages, menu, settings ---------------------------
# ("net", function)   -> runs an action defined above
# ("hid", [keycodes]) -> chord delivered to the PC
# ("cc", code)        -> consumer-control tap (media keys)
PAGE_MAIN = {
    0: ("net", act_weather),
    1: ("net", act_hn),
    9: ("hid", [config.MOD, Keycode.C]),
    10: ("hid", [config.MOD, Keycode.V]),
    11: ("hid", [config.MOD, Keycode.SHIFT, Keycode.M]),  # Teams mute
}
PAGE_MEDIA = {
    0: ("cc", ConsumerControlCode.SCAN_PREVIOUS_TRACK),
    1: ("cc", ConsumerControlCode.PLAY_PAUSE),
    2: ("cc", ConsumerControlCode.SCAN_NEXT_TRACK),
    3: ("cc", ConsumerControlCode.MUTE),
}
PAGE_NUMPAD = {  # laid out like a numpad: 789 / 456 / 123 / 0.Enter
    0: ("hid", [Keycode.SEVEN]), 1: ("hid", [Keycode.EIGHT]),
    2: ("hid", [Keycode.NINE]), 3: ("hid", [Keycode.FOUR]),
    4: ("hid", [Keycode.FIVE]), 5: ("hid", [Keycode.SIX]),
    6: ("hid", [Keycode.ONE]), 7: ("hid", [Keycode.TWO]),
    8: ("hid", [Keycode.THREE]), 9: ("hid", [Keycode.ZERO]),
    10: ("hid", [Keycode.PERIOD]), 11: ("hid", [Keycode.RETURN]),
}
PAGES = (  # name, keymap, per-key labels for the on-screen grid
    ("Main", PAGE_MAIN,
     {0: "wthr", 1: "hn",
      9: "copy", 10: "paste", 11: "mute"}),
    ("Media", PAGE_MEDIA,
     {0: "prev", 1: "play", 2: "next", 3: "mute"}),
    ("Numpad", PAGE_NUMPAD,
     {0: "7", 1: "8", 2: "9", 3: "4", 4: "5", 5: "6",
      6: "1", 7: "2", 8: "3", 9: "0", 10: ".", 11: "enter"}),
)

SETTINGS = (  # label, prefs key, choices; key None = action entry
    ("knob speed", "enc_div", (1, 2, 3, 4)),
    ("fine volume", "fine_vol", (1, 0)),
    ("brightness", "brightness", (10, 20, 30, 50, 75, 100)),
    ("sleep min", "sleep", (5, 1, 2, 10, 30, 0)),  # 0 = never
    ("net proxy", "link", ("usb", "uart")),  # usb=PC daemon, uart=T-QT
    ("screen test", None, None),
)


def set_page(i):
    global page_i, KEYMAP
    page_i = i
    KEYMAP = PAGES[i][1]
    for k in range(12):
        macropad.pixels[k] = base_color(k)
    draw_title()
    show_legend()


def show_legend():
    """4x3 grid mirroring the physical keys of the active page."""
    labels = PAGES[page_i][2]
    for r in range(4):
        cells = [clean(labels.get(r * 3 + c, "."))[:6] for c in range(3)]
        grid_l[r].text = "%-7s%-7s%s" % (cells[0], cells[1], cells[2])


def run_key(n):
    """Execute key n's single-key action from the active page."""
    kind, arg = KEYMAP.get(n, (None, None))
    if kind == "hid":
        if not proto.deliver_keys(arg):
            flash(n, RED)  # no PC link (USB or BT) right now
    elif kind == "cc":
        if not proto.deliver_keys([], cc=arg):
            flash(n, RED)
    elif kind == "net":
        arg(n)


def key_action(n):
    """A solo bottom-row tap: page action when idle; in the menu,
    K11 = enter/select and K9 = exit/back (K10 is the chord pivot)."""
    if view["mode"] == "idle":
        run_key(n)
    elif n == 11:
        ui_select()
    elif n == 9:
        ui_back()


def setting_value(key):
    if key == "enc_div":
        return config.ENC_DIV
    if key == "fine_vol":
        return 1 if config.FINE_VOL else 0
    if key == "sleep":
        return config.SLEEP_MIN
    if key == "link":
        return config.LINK_MODE
    return config.BRIGHT_PCT


def apply_setting(key, val):
    """Apply live and persist; False if the FS is read-only (drive
    mounted via KEY12) - the value still applies for this session.
    Changing the net proxy re-opens the transport, so once it is saved
    the pad soft-reloads to bring the new link up cleanly."""
    if key == "enc_div":
        config.ENC_DIV = val
    elif key == "fine_vol":
        config.FINE_VOL = bool(val)
    elif key == "sleep":
        config.SLEEP_MIN = val
    elif key == "link":
        config.LINK_MODE = val
    elif key == "brightness":
        config.BRIGHT_PCT = val
        macropad.pixels.brightness = val / 100
    ok = config.save_prefs()
    if ok and key == "link":
        import supervisor
        supervisor.reload()  # restart so ser re-opens on the new transport
    return ok


def ui_items():
    if view["mode"] == "menu":
        return [p[0] for p in PAGES] + ["Settings..."]
    out = []
    for i, (name, key, choices) in enumerate(SETTINGS):
        if key is None:
            out.append(name)
        elif view["mode"] == "edit" and i == view["cur"]:
            out.append("%s <%s>" % (name, choices[view["edit"]]))
        else:
            out.append("%s %s" % (name, setting_value(key)))
    return out


def draw_ui():
    items = ui_items()
    if view["cur"] < view["top"]:
        view["top"] = view["cur"]
    if view["cur"] > view["top"] + 3:
        view["top"] = view["cur"] - 3
    for r in range(4):
        i = view["top"] + r
        text = ""
        if i < len(items):
            text = ("> " if i == view["cur"] else "  ") + str(items[i])
        grid_l[r].text = clean(text)


def ui_open():
    view["mode"] = "menu"
    view["cur"] = page_i
    view["top"] = 0
    draw_ui()


def ui_close():
    view["mode"] = "idle"
    state["last_min"] = -1  # let the next tick refresh the clock too
    show_legend()
    draw_status()


def ui_nav(d):
    if view["mode"] == "edit":
        choices = SETTINGS[view["cur"]][2]
        view["edit"] = (view["edit"] + d) % len(choices)
    else:
        view["cur"] = max(0, min(len(ui_items()) - 1, view["cur"] + d))
    draw_ui()


def ui_select():
    if view["mode"] == "menu":
        if view["cur"] < len(PAGES):
            set_page(view["cur"])
            ui_close()
        else:
            view["mode"] = "settings"
            view["cur"] = 0
            view["top"] = 0
            draw_ui()
    elif view["mode"] == "settings":
        key, choices = SETTINGS[view["cur"]][1:]
        if key is None:
            start_screentest()
            return
        cur = setting_value(key)
        view["edit"] = choices.index(cur) if cur in choices else 0
        view["mode"] = "edit"
        draw_ui()
    elif view["mode"] == "edit":
        key, choices = SETTINGS[view["cur"]][1:]
        if not apply_setting(key, choices[view["edit"]]):
            macropad.play_tone(220, 0.1)  # applied, but no persistence
        view["mode"] = "settings"
        draw_ui()


def ui_back():
    if view["mode"] == "edit":
        view["mode"] = "settings"
        draw_ui()
    elif view["mode"] == "settings":
        view["mode"] = "menu"
        view["cur"] = len(PAGES)  # land back on the Settings row
        draw_ui()
    else:
        ui_close()

# ------------------------------ screen test -------------------------------
# Cycles full-screen patterns (all-on / all-off / two checkerboards) and
# sweeps the LEDs - reveals OLED burn-in (uneven patches on full white)
# and exercises every pixel. Any key or the encoder exits.
test = {"step": -1, "due": 0.0, "group": None, "tiles": None}
TEST_LEDS = ((90, 0, 0), (0, 90, 0), (0, 0, 90), (90, 90, 90))


def _test_tiles():
    pal = displayio.Palette(2)
    pal[0] = 0x000000
    pal[1] = 0xFFFFFF
    tiles = []
    for v in (1, 0):  # all pixels on, all off
        b = displayio.Bitmap(1, 1, 2)
        b[0, 0] = v
        tiles.append(displayio.TileGrid(
            b, pixel_shader=pal, width=128, height=64,
            tile_width=1, tile_height=1))
    for phase in (0, 1):  # checkerboards hit alternating pixels
        b = displayio.Bitmap(2, 2, 2)
        for y in range(2):
            for x in range(2):
                b[x, y] = (x + y + phase) & 1
        tiles.append(displayio.TileGrid(
            b, pixel_shader=pal, width=64, height=32,
            tile_width=2, tile_height=2))
    return tiles


def start_screentest():
    if test["tiles"] is None:
        test["tiles"] = _test_tiles()
        test["group"] = displayio.Group()
        test["group"].append(test["tiles"][0])
    test["step"] = -1
    test["due"] = 0.0
    macropad.display.root_group = test["group"]
    view["mode"] = "screentest"


def screentest_tick(now):
    if now < test["due"]:
        return
    test["due"] = now + 1.2
    test["step"] = (test["step"] + 1) % 4
    test["group"].pop()
    test["group"].append(test["tiles"][test["step"]])
    macropad.pixels.fill(TEST_LEDS[test["step"]])


def stop_screentest():
    view["mode"] = "settings"
    macropad.display.root_group = shared.screen  # hand back the text layout
    set_page(page_i)  # restore the page's LED colors and title/legend
    draw_ui()

# -------------------------------- sleep -----------------------------------

def go_sleep():
    """Blank the OLED and LEDs after inactivity - burn-in protection."""
    state["awake"] = False
    macropad.display.root_group = shared.SLEEP_SCREEN
    macropad.pixels.fill((0, 0, 0))


def wake_up():
    state["awake"] = True
    macropad.display.root_group = shared.screen
    for k in range(12):
        macropad.pixels[k] = base_color(k)
    state["last_min"] = -1  # redraw the clock promptly
