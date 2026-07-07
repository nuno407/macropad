# CLAUDE.md — agent orientation

Two CircuitPython devices form the product: an **Adafruit MacroPad RP2040**
(`macropad/`) wired over a STEMMA QT cable to a **LilyGo T-QT Pro / ESP32-S3**
(`esp_proxy/`) that gives it WiFi and acts as a BLE keyboard to the PC.
Both run **CircuitPython 10.2.1**. `host/bridge.py` is an alternative proxy
(PC daemon over USB) and holds the hardware-free pytest suite.

## Architecture rules (do not break)

1. **The pad is the brain; the proxy is logic-free.** All features (key
   maps, URLs, formatting, display) live in `macropad/`. The proxy only:
   runs HTTP requests, answers liveness pings, serves its NTP-synced UTC
   epoch, types HID events, reports link state. If a change seems to need
   proxy smarts, make it generic or put it on the pad.
2. **Wire protocol v1 is minimal by policy.** Newline-delimited JSON over
   UART/USB-CDC; message table in `README.md`. Keep it carrying only what
   the product uses — optimizing/pruning is encouraged. Any protocol
   change MUST update all three parties together: `macropad/`,
   `esp_proxy/` and `host/bridge.py` (+ its tests). Unknown message types
   are ignored by both sides, which is what makes staged deploys safe.
3. **HTTPS must work.** TLS+BLE is verified fine on this board; plain
   http is allowed, but never break the https path (the pad's real
   actions all use it).
4. **No secrets in the repo, ever.** Live creds exist only in
   `settings.toml` on each device's CIRCUITPY drive. The repo tracks
   only the `settings.toml.example` templates (placeholders).
5. **Keep everything consistent after every change.** Docs (`README.md`,
   this file), code, docstrings and comments must all describe the same
   system — when you change behavior, sweep the rest in the same pass
   (protocol table, repo-layout block, quick-start commands, module
   docstrings, `.example` templates). Stale docs are treated as bugs.

## Working on it

- **Deploy = copy files.** `cp esp_proxy/*.py /Volumes/CIRCUITPY/` or
  `cp macropad/*.py /Volumes/CIRCUITPY/` — CircuitPython auto-reloads; no
  build step anywhere. Both firmwares are split into modules that live at
  the drive root next to code.py: proxy = code/config/net/blehid/ui, pad
  = code/config/shared/proto/ui (+ boot.py).
- **The pad's drive is hidden by design**: hold **KEY12 while plugging in**
  to mount it (`macropad/boot.py`). Its on-device `settings.toml` contains
  unrelated personal credentials — never overwrite, copy, or commit it.
- **Which device is `/Volumes/CIRCUITPY`?** Check `boot_out.txt` on the
  drive before copying — pad and proxy mount under the same name.
- **Serial debugging**: read `/dev/cu.usbmodem*` at 115200 with pyserial
  (`uvx --with pyserial python ...`). Ctrl-C then Ctrl-D over serial
  soft-reboots CircuitPython and replays boot output.
- **Python tooling is uv only**: `uv venv`, `uv pip -p .venv/bin/python`,
  `uvx` for one-offs (circup, esptool). Never bare pip. Venv: `host/.venv`.
- **Firmware flashing**: pad = UF2 (double-tap reset → RPI-RP2 drive, drag
  `adafruit_macropad_rp2040` build). T-QT = `.bin` for board id
  `lilygo_tqt_pro_psram` via esptool at `0x0`. `/lib` `.mpy` files must
  come from the bundle matching the CircuitPython **major** version.
- Git: work directly on `main`; commit messages are short descriptive
  sentences (see `git log`). Commit only when asked.

## Hardware facts (verified the hard way — trust these)

- **UART link**: pad `busio.UART(tx=board.SDA, rx=board.SCL)` ↔ proxy
  `busio.UART(tx=board.SCL, rx=board.SDA)`, 115200, straight-through
  STEMMA cable. Pad sends a `{"t":"ping"}` liveness probe every 4 s and
  the proxy answers `pong`; 12 s of silence = link down on the pad,
  5 s = "Pad: --" on the proxy.
- **T-QT Pro**: `board.DISPLAY` (128×128 GC9107) is auto-initialised;
  `display.rotation = 180` is the owner's preferred orientation. Backlight
  `board.LCD_BCKL` is **active-low**. Buttons `board.BUTTON0`/`BUTTON1`
  are active-low (BUTTON0 doubles as BOOT).
  When in doubt about this board, check LilyGo's repo
  (github.com/Xinyuan-LilyGO/T-QT) — don't guess pins/polarity.
- **ESP32-S3 + PSRAM runs WiFi + BLE + TLS simultaneously** under
  CircuitPython (~2 MB heap free, steady) — radios and TLS can be brought
  up in any order.
- **Pad encoder is worn**: it emits noisy reverse bursts. `macropad/code.py`
  majority-votes counts in 150 ms windows with sticky direction — don't
  "simplify" that logic.
- **Pad OLED burns in**: that's why sleep mode and the screen test exist.

## Conventions

- Screen-sleep, the proxy's hang-reset watchdog and creds are configured
  via `settings.toml`, not constants — see the `.example` files. Both
  devices show Europe/Lisbon time with no time-API dependency: the proxy
  syncs UTC via NTP and mirrors it to the pad (`time` message); both
  apply the identical local EU-DST-rule offset.
- Comments explain *why* (hardware quirks, protocol invariants), not what.
- The proxy dashboard only marks the pad "linked" from real protocol
  frames; user *activity* (for screen-wake) counts only `hid`/`enc`
  messages and button presses — deliberately not the keepalive.
