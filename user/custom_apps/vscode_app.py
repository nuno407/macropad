from utils.apps.key import Key, KeyApp
from utils.commands import (
    Keycode,
    Press,
    Text,
)
from utils.constants import COLOR_8, COLOR_NUMPAD, COLOR_WARNING
from user.custom_apps.base_app import BaseApp

class VSCodeApp(BaseApp):
    name = "Numpad"

    # First row
    key_0 = Key("Comment", COLOR_NUMPAD, Press(Keycode.LEFT_CONTROL, Keycode.FORWARD_SLASH))
    key_1 = Key("Format", COLOR_NUMPAD, Press(Keycode.LEFT_SHIFT, Keycode.LEFT_ALT, Keycode.F))
    key_2 = Key("Term", COLOR_NUMPAD, Press(Keycode.LEFT_CONTROL, Keycode.LEFT_SHIFT, Keycode.GRAVE_ACCENT))

    # Second row
    key_3 = Key("Cmd", COLOR_NUMPAD, Press(Keycode.LEFT_CONTROL, Keycode.LEFT_SHIFT, Keycode.P))
    key_4 = Key("MulLine", COLOR_NUMPAD, Press(Keycode.LEFT_CONTROL, Keycode.LEFT_ALT))
    key_5 = Key("6", COLOR_NUMPAD, Text("6"), double_tap_command=Text("-"))

    # Third row
    key_6 = Key("InDef", COLOR_NUMPAD, Press(Keycode.LEFT_ALT, Keycode.F12))
    key_7 = Key("SideDef", COLOR_NUMPAD,  Press(Keycode.LEFT_CONTROL, Keycode.LEFT_ALT))
    key_8 = Key("BackDef", COLOR_NUMPAD, Press(Keycode.LEFT_ALT, Keycode.LEFT_ARROW))

    # Fourth row
    key_9 = Key("CTRL", COLOR_NUMPAD, Press(Keycode.LEFT_CONTROL))
    key_10 = Key()
    key_11 = Key("ESC", COLOR_WARNING, Press(Keycode.ESCAPE))
