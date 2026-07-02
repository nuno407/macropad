# boot.py - runs once at power-up, before code.py.
#
# 1. Hides the CIRCUITPY drive unless KEY12 is held while plugging in -
#    the on-device settings.toml holds credentials, so the filesystem
#    stays invisible to whatever computer the pad is connected to. With
#    the drive hidden the filesystem is remounted WRITABLE for the
#    firmware, so prefs (macropad_prefs.json) persist; while KEY12-
#    mounted the computer owns it and prefs are session-only.
# 2. Enables a SECOND USB CDC serial channel ("data") next to the REPL
#    console; the bridge protocol runs on "data" so the REPL stays free.
# 3. Enables the keyboard/mouse/consumer-control HID devices.
#
# boot.py changes need a hard reset (unplug/replug) to take effect.

import usb_cdc
import usb_hid
import storage
import board, digitalio

# Only activate usb if KEY12 is pressed during boot
# On the Macropad, pressing a key grounds it. You need to set a pull-up.
# If not pressed, the key will be at +V (due to the pull-up).
button = digitalio.DigitalInOut(board.KEY12)
button.pull = digitalio.Pull.UP
# Disable devices only if button is not pressed.
if button.value:
   storage.disable_usb_drive()
   # Hiding the drive is NOT enough: the FS stays read-only to the
   # firmware until it is remounted. Without this, saving any pref
   # (page, brightness, link...) silently fails.
   storage.remount("/", readonly=False)

# Enable console and data
usb_cdc.enable(console=True, data=True)

# Enable multiple usb_hid devices
usb_hid.enable((usb_hid.Device.KEYBOARD, usb_hid.Device.MOUSE, usb_hid.Device.CONSUMER_CONTROL))
