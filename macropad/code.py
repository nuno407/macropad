"""MacroPad RP2040 (pad-centric).

ALL application logic lives on the pad: key map, actions, URL
composition, response handling, OLED formatting. The proxy it talks to
(esp_proxy/ on the T-QT, or host/bridge.py on a PC) is generic and
logic-free.

Modules:  config.py tunables/prefs · shared.py hardware+state ·
proto.py wire protocol+HID routing · ui.py display/actions/menu.
This file owns the boot sequence and the main loop.

Requires:
  - boot.py from this folder (enables usb_cdc.data), then a hard reset
  - adafruit_macropad + deps in /lib  ->  `circup install adafruit_macropad`
  - optional: settings.toml on CIRCUITPY (see settings.toml.example)

Wire protocol v1 (transport-agnostic, minimal):
  pad -> proxy: {"t":"hello"}
                {"t":"ping"}                             liveness probe, every
                  LINK_KEEPALIVE s on UART (the proxy answers pong)
                {"t":"pong"}                             reply to a proxy ping
                  (the PC daemon probes ports with ping during discovery)
                {"t":"time"}                             clock request (on
                  connect + hourly); answered once the proxy has NTP
                {"t":"http","id":7,"m":"GET","url":"...",
                 "pick":["current.temperature_2m"]}      pick optional
                {"t":"hid","k":[...],"cc":233}           deliver keys to the
                  PC over the proxy's Bluetooth HID link (hold chord k,
                  tap consumer code cc, release)
                {"t":"enc","d":1}                        one confirmed
                  encoder detent (+/-1); the proxy treats it as user
                  activity (wakes its screen)
  proxy -> pad: {"t":"ping"}                             USB discovery probe
                {"t":"pong"}                             reply to a pad ping;
                  any inbound line marks the link alive
                {"t":"time","epoch":1781612345}          UTC epoch from the
                  proxy's NTP-synced clock
                {"t":"res","id":7,"st":200,"v":[...]}    v only when pick
                {"t":"res","id":7,"err":"Timeout"}       transport error
                {"t":"link","pc":true,"net":true}        proxy's Bluetooth
                  HID link to the PC ("pc") and WiFi state ("net")
  Both devices compute the Lisbon offset locally (same EU DST rule);
  the UTC epoch itself comes from NTP on the proxy and is mirrored to
  the pad via "time".
"""

import time

from adafruit_hid.consumer_control_code import ConsumerControlCode

import config
import proto
import shared
import ui
from shared import link_connected, macropad, pc_connected, state

# usb link needs boot.py's data channel; without it there is no proxy.
if shared.ser is None:
    ui.show("usb_cdc.data is OFF", "copy boot.py, then")
    shared.grid_l[2].text = "unplug and replug"
    while True:
        time.sleep(1)

proto.on_link = ui.draw_title   # repaint glyphs when the proxy reports


def on_connect():
    proto.send({"t": "hello"})
    proto.sync_clock()
    state["wx_due"] = 0.0
    ui.draw_title()
    ui.draw_status()


ui.set_page(0)

was_connected = link_connected()
was_pc = pc_connected()
ui.draw_title()
if was_connected:
    on_connect()
else:
    ui.draw_status()

last_pos = macropad.encoder
enc_pos = 0       # gross clockwise counts inside the vote window
enc_neg = 0       # gross counter-clockwise counts inside the window
enc_dir = 0       # established twirl direction (+1/-1, 0 = none)
enc_rev = 0       # consecutive windows that voted against enc_dir
enc_ts = 0.0      # when the encoder last moved
enc_win_end = 0.0  # when the current vote window closes (0 = no window)
sw_down = 0.0     # when the encoder switch went down (0 = not held)
sw_long = False   # long-press already fired for this hold
last_act = time.monotonic()  # last user input, for sleep mode
keys_down = set()  # currently held key numbers
chord_pend = {}   # bottom-row key -> deadline to fire its own action
chord_used = set()  # bottom-row keys consumed by a chord
chord2_pend = None  # (deadline, +1/-1): 2-key chord waiting briefly in
                    # case the third key joins to form the menu chord

while True:
    proto.poll_serial()
    now = time.monotonic()

    event = macropad.keys.events.get()
    while event:
        last_act = now
        if not state["awake"]:
            ui.wake_up()
        if ui.view["mode"] == "screentest":
            if event.pressed:  # any key leaves the screen test
                ui.stop_screentest()
            event = macropad.keys.events.get()
            continue
        n = event.key_number
        macropad.pixels[n] = shared.PRESS if event.pressed else ui.base_color(n)
        if event.pressed:
            keys_down.add(n)
            if n in config.CHORD_KEYS:
                # defer this key's own action; first check for chords
                chord_pend[n] = now + config.CHORD_WAIT
                if all(k in keys_down for k in config.CHORD_KEYS):
                    chord2_pend = None  # superseded by the menu chord
                    for k in config.CHORD_KEYS:  # K9+K10+K11: toggle menu
                        chord_used.add(k)
                        chord_pend.pop(k, None)
                    if ui.view["mode"] == "idle":
                        ui.ui_open()
                    else:
                        ui.ui_close()
                elif 10 in keys_down and (9 in keys_down or 11 in keys_down):
                    # K9+K10 = previous, K10+K11 = next. Consume the keys
                    # NOW so their own actions (copy/paste/...) can never
                    # fire from a chord; act after a short grace in case
                    # the third key joins to form the menu chord.
                    d = -1 if 9 in keys_down else 1
                    chord_used.update((10, 9 if d < 0 else 11))
                    chord_pend.pop(10, None)
                    chord_pend.pop(9 if d < 0 else 11, None)
                    chord2_pend = (now + 0.08, d)
            else:
                ui.run_key(n)
        else:
            keys_down.discard(n)
            if n in config.CHORD_KEYS:
                if n in chord_used:
                    chord_used.discard(n)  # chord handled it
                    chord_pend.pop(n, None)
                elif chord_pend.pop(n, None) is not None:
                    ui.key_action(n)  # quick solo tap: act on release
        event = macropad.keys.events.get()

    pos = macropad.encoder
    if pos != last_pos:
        last_act = now
        if not state["awake"]:
            ui.wake_up()
        if now - enc_ts > 0.5:  # idle gap: new twirl, forget direction
            enc_dir = 0
            enc_rev = 0
            enc_pos = 0
            enc_neg = 0
        enc_ts = now
        d = pos - last_pos
        if d > 0:
            enc_pos += d
        else:
            enc_neg -= d
        last_pos = pos
        if not enc_win_end:  # first movement opens a vote window
            enc_win_end = now + config.ENC_WINDOW

    # This encoder intermittently decodes whole stretches of rotation
    # backwards (worn contacts), so counts are majority-voted per
    # window AND the twirl direction is sticky: one quarter-step per
    # agreeing window, while opposing windows are ignored until
    # ENC_REV_WINDOWS of them arrive in a row. Wrong-direction
    # stretches become a brief pause instead of a backward jump; a
    # short pause resets the direction so deliberate reversals after
    # letting go stay instant.
    if enc_win_end and now >= enc_win_end:
        pos_c, neg_c = enc_pos, enc_neg
        enc_pos = 0
        enc_neg = 0
        enc_win_end = 0.0
        # Majority vote decides direction; the magnitude is the GROSS
        # movement in the winning direction, so the encoder's fake
        # opposing counts can't slow the volume down - they only vote.
        want = 1 if pos_c >= neg_c else -1
        mag = pos_c if want > 0 else neg_c
        if mag >= (config.ENC_DIV if ui.view["mode"] == "idle" else 1):
            if enc_dir in (0, want) or enc_rev + 1 >= config.ENC_REV_WINDOWS:
                enc_dir = want
                enc_rev = 0
                # Mirror each confirmed detent to the proxy: it treats
                # them as user activity (wakes its screen).
                proto.send({"t": "enc", "d": want})
                if ui.view["mode"] == "idle":
                    # speed scales with rotation: 1 quarter-step per
                    # ENC_DIV detents in the window, capped for smoothness
                    n_ev = min(max(mag // config.ENC_DIV, 1), 6)
                    for _ in range(n_ev):
                        proto.send_volume(
                            ConsumerControlCode.VOLUME_INCREMENT
                            if want > 0
                            else ConsumerControlCode.VOLUME_DECREMENT)
                elif ui.view["mode"] != "screentest":
                    ui.ui_nav(want)  # menu open: the knob moves the cursor
            else:
                enc_rev += 1

    macropad.encoder_switch_debounced.update()
    if macropad.encoder_switch_debounced.pressed:
        last_act = now
        if not state["awake"]:
            ui.wake_up()
        if ui.view["mode"] == "screentest":
            ui.stop_screentest()
        else:
            sw_down = now
            sw_long = False
    if (sw_down and not sw_long and macropad.encoder_switch
            and now - sw_down >= config.LONG_PRESS):
        sw_long = True  # fires while still held
        if ui.view["mode"] == "idle":
            ui.ui_open()
        else:
            ui.ui_back()
    if macropad.encoder_switch_debounced.released:
        if sw_down and not sw_long:
            if ui.view["mode"] == "idle":
                proto.sync_clock()     # re-sync clock
                state["wx_due"] = 0.0  # refresh weather on next pass
            else:
                ui.ui_select()
        sw_down = 0.0
        sw_long = False

    if pc_connected() != was_pc:
        was_pc = pc_connected()
        ui.draw_title()

    # UART has no carrier line: ping so the proxy's pong keeps the
    # link marked alive (any inbound line updates last_rx).
    if config.LINK_MODE == "uart" and now >= state["ka_due"]:
        state["ka_due"] = now + config.LINK_KEEPALIVE
        proto.send({"t": "ping"})

    if link_connected() != was_connected:
        was_connected = link_connected()
        if was_connected:
            on_connect()
        else:
            for cb, _ in shared.pending.values():
                cb(None)
            shared.pending.clear()
            state["bt_pc"] = False  # both ride on the proxy channel
            state["wifi"] = None
            ui.draw_title()
            ui.draw_status()

    # schedulers ----------------------------------------------------------
    if (state["awake"] and config.SLEEP_MIN and ui.view["mode"] == "idle"
            and now - last_act >= config.SLEEP_MIN * 60):
        ui.go_sleep()

    if ui.view["mode"] == "screentest":
        ui.screentest_tick(now)

    if chord2_pend and now >= chord2_pend[0]:
        d = chord2_pend[1]
        chord2_pend = None
        if ui.view["mode"] == "idle":  # menu closed: step through pages
            ui.set_page((ui.page_i + d) % len(ui.PAGES))
        else:  # menu open: move the highlight
            ui.ui_nav(d)

    if chord_pend:  # bottom-row key held alone past the chord window
        for k in [k for k, dl in chord_pend.items() if now >= dl]:
            chord_pend.pop(k)
            if k not in chord_used:
                ui.key_action(k)

    if shared.pending:
        for rid in [r for r, (_, dl) in shared.pending.items() if now > dl]:
            shared.pending.pop(rid)[0](None)

    if shared.flashes:
        for k in [k for k, dl in shared.flashes.items() if now > dl]:
            shared.flashes.pop(k)
            macropad.pixels[k] = ui.base_color(k)

    if was_connected and now >= state["wx_due"]:
        state["wx_due"] = now + config.REQ_TIMEOUT  # back off in flight
        ui.bg_weather()

    if was_connected and now >= state["time_due"]:
        proto.sync_clock()

    if now >= state["tick_due"]:
        state["tick_due"] = now + 0.25  # catch second flips promptly
        cur = time.localtime().tm_sec if state["time_ok"] else -2
        if cur != state["last_min"]:
            state["last_min"] = cur
            ui.draw_status()

    time.sleep(0.005)
