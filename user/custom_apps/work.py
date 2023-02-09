import os
from utils.apps.key import Key
from utils.commands import Press, Text, Keycode
from utils.constants import COLOR_NUMPAD
from user.custom_apps.base_app import BaseApp

class WorkApp(BaseApp):
    name = "Work"

    def on_focus(self):
        super().on_focus()
        self.macropad.start_tone(18000)
        def previous_app():
            # switch to main menu
            self.encoder_button.execute(self)
            self.app_pad.delete_timer("go_out")
        self.app_pad.add_timer(
            "auto_go_out_work",
            10,
            previous_app,
        )

    # First row
    key_0 = Key("EPT", COLOR_NUMPAD, Text(os.getenv("EPT", "")))
    key_1 = Key("ENT", COLOR_NUMPAD, Text(os.getenv("ENT", "")))
    key_2 = Key("NT", COLOR_NUMPAD, Text(os.getenv("NT", "")))

    # Second row
    key_3 = Key("LOG", COLOR_NUMPAD, Text(os.getenv("LOG", "")))
    key_4 = None
    key_5 = None

    # Third row
    key_6 = None
    key_7 = None
    key_8 = None

    # Fourth row
    key_9 = None
    key_10 = None
    key_11 = Key("Enter", COLOR_NUMPAD, Press(Keycode.KEYPAD_ENTER))
