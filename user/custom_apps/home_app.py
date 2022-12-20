from utils.apps.key import (
    Key,
)
from utils.commands import (
    ConsumerControlCode,
    Keycode,
    Media,
    Press,
)
from utils.constants import (
    COLOR_ALERT,
    COLOR_SPOTIFY,
    COLOR_MEDIA,
    COLOR_NAV,
)
from user.custom_apps.base_app import BaseApp


class HomeApp(BaseApp):
    """
    Main menu app.
    """

    name = "Home"

    # Meeting Controls. Uses PowerToys windows app
    key_1 = Key("Cam", COLOR_MEDIA, Press(Keycode.CONTROL, Keycode.SHIFT, Keycode.O))
    key_2 = Key("Mic", COLOR_MEDIA, Press(Keycode.CONTROL, Keycode.SHIFT, Keycode.A))

    # Music
    key_3 = Key("<<", COLOR_SPOTIFY, Media(ConsumerControlCode.SCAN_PREVIOUS_TRACK))
    key_4 = Key(">||", COLOR_SPOTIFY, Media(ConsumerControlCode.PLAY_PAUSE))
    key_5 = Key(">>", COLOR_SPOTIFY, Media(ConsumerControlCode.SCAN_NEXT_TRACK))

    # Delete and Basckspace key
    key_8 = Key("Del", COLOR_ALERT, Press(Keycode.DELETE))
    key_6 = Key("Backs", COLOR_ALERT, Press(Keycode.BACKSPACE))
    
    # Arrows
    key_7 = Key("/\\", COLOR_NAV, Press(Keycode.UP_ARROW))
    key_9 = Key("<-", COLOR_NAV, Press(Keycode.LEFT_ARROW))
    key_10= Key("\\/", COLOR_NAV, Press(Keycode.DOWN_ARROW))
    key_11 = Key("->", COLOR_NAV, Press(Keycode.RIGHT_ARROW))
