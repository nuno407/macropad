"""Tunables for the esp_proxy. Per-install values come from settings.toml
(see settings.toml.example); the rest are protocol/product constants."""

import os

# protocol / HTTP limits (match host/bridge.py behaviour)
HTTP_TIMEOUT = 8
LINE_MAX = 6000           # absolute serialized-line cap
NET_PERIOD = 5            # s - WiFi/BLE/link maintenance cadence
ALLOWED_SCHEMES = ("http://", "https://")   # https verified working (TLS+BLE ok)

# time
NTP_PERIOD = 6 * 3600     # re-sync the RTC this often (s)

# link / UI
PAD_TIMEOUT = 5           # s without a frame => pad considered offline
ROTATION = 180            # display orientation (owner preference)
SLEEP_S = int(os.getenv("SLEEP_S") or "30")   # idle screen-off; 0 = never
BLE_NAME = "MacroPad Bridge"
