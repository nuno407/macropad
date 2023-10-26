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

# Enable console and data
usb_cdc.enable(console=True, data=True)

# Enable multiple usb_hid devices
usb_hid.enable((usb_hid.Device.KEYBOARD, usb_hid.Device.MOUSE, usb_hid.Device.CONSUMER_CONTROL))
