"""Tunables for the esp_proxy. Per-install values come from settings.toml
(see settings.toml.example); the rest are protocol/product constants."""

import os

# protocol / HTTP limits (match host/bridge.py behaviour)
HTTP_TIMEOUT = 8
# Bounded so a wedged radio can't block the loop forever; kept under the
# pad's 12 s link timeout so retries don't read as a dead proxy.
WIFI_CONNECT_TIMEOUT = 8
LINE_MAX = 6000           # absolute serialized-line cap
NET_PERIOD = 5            # s - WiFi/BLE/link maintenance cadence
ALLOWED_SCHEMES = ("http://", "https://")   # https verified working (TLS+BLE ok)

# time
NTP_PERIOD = 6 * 3600     # re-sync the RTC this often (s)

# recovery: hardware watchdog resets the chip if the main loop stalls this
# long. Must exceed the worst legitimate block (WiFi connect + NTP + HTTP,
# ~26 s back-to-back). "0" disables it (needed for REPL work).
WATCHDOG_S = int(os.getenv("WATCHDOG_S") or "30")

# link / UI
PAD_TIMEOUT = 5           # s without a frame => pad considered offline
ROTATION = 180            # display orientation (owner preference)
SLEEP_S = int(os.getenv("SLEEP_S") or "30")   # idle screen-off; 0 = never
# Mirror the pad's USB identity so the PC sees the same device fields
# whether keys arrive over USB or through this proxy.
BLE_NAME = "Macropad RP2040"
BLE_MANUFACTURER = "Adafruit Industries LLC"
