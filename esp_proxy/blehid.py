"""BLE HID keyboard into the PC (the proxy's "type for the pad" role)."""

from adafruit_ble import BLERadio
from adafruit_ble.advertising import Advertisement
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
from adafruit_hid.consumer_control import ConsumerControl
from adafruit_hid.keyboard import Keyboard
from adafruit_ble.services.standard.hid import HIDService

import config

_hid = HIDService()
_ble = BLERadio()
_ble.name = config.BLE_NAME
_adv = ProvideServicesAdvertisement(_hid)
_adv.appearance = 961  # BLE "keyboard" - macOS hides HID without it
_scan_resp = Advertisement()
_scan_resp.complete_name = config.BLE_NAME
_kbd = Keyboard(_hid.devices)
_consumer = ConsumerControl(_hid.devices)


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
    """Hold chord k, tap optional consumer code cc, release."""
    if not _ble.connected:
        return
    codes = msg.get("k") or []
    cc = msg.get("cc")
    try:
        if cc is None:
            _kbd.send(*codes)
        else:
            if codes:
                _kbd.press(*codes)
            _consumer.send(int(cc))
    except Exception as exc:
        print("hid:", exc)
    finally:
        if cc is not None and codes:
            try:
                _kbd.release(*codes)
            except Exception:
                pass
