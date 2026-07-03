"""BLE HID keyboard into the PC (the proxy's "type for the pad" role)."""

from adafruit_ble import BLERadio
from adafruit_ble.advertising import Advertisement
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
from adafruit_hid.consumer_control import ConsumerControl
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.mouse import Mouse
from adafruit_ble.services.standard.hid import HIDService
from adafruit_ble.services.standard.device_info import DeviceInfoService

import config

_hid = HIDService()
# Same identity fields as the pad's own USB descriptors present.
_device_info = DeviceInfoService(manufacturer=config.BLE_MANUFACTURER,
                                 model_number=config.BLE_NAME)
_ble = BLERadio()
_ble.name = config.BLE_NAME
_adv = ProvideServicesAdvertisement(_hid)
_adv.appearance = 961  # BLE "keyboard" - macOS hides HID without it
_scan_resp = Advertisement()
_scan_resp.complete_name = config.BLE_NAME
_kbd = Keyboard(_hid.devices)
_consumer = ConsumerControl(_hid.devices)
_mouse = Mouse(_hid.devices)   # the standard HID descriptor includes a mouse


def connected():
    return _ble.connected


def ensure_advertising():
    if _ble.connected or _ble.advertising:
        return
    try:
        _ble.start_advertising(_adv, _scan_resp)
    except Exception as exc:
        print("ble:", exc)


def do_hid(msg):
    """Hold chord k, tap the consumer code cc OR left-click (mc),
    release. Plain chords are sent atomically."""
    if not _ble.connected:
        return
    codes = msg.get("k") or []
    cc = msg.get("cc")
    mc = msg.get("mc")
    try:
        if mc:
            if codes:
                _kbd.press(*codes)
            _mouse.click(Mouse.LEFT_BUTTON)
        elif cc is None:
            _kbd.send(*codes)
        else:
            if codes:
                _kbd.press(*codes)
            _consumer.send(int(cc))
    except Exception as exc:
        print("hid:", exc)
    finally:
        if (mc or cc is not None) and codes:
            try:
                _kbd.release(*codes)
            except Exception:
                pass
