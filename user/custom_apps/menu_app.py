try:
    from typing import Optional, Any
except ImportError:
    pass
from utils.app_pad import AppPad
from utils.apps.key import (
    Key,
)
from utils.commands import (
    SwitchAppCommand,
    Media,
    ConsumerControlCode
)
from utils.constants import (
    COLOR_APPS,
)
from user.custom_apps.base_app import BaseApp
from user.custom_apps.home_app import HomeApp
from user.custom_apps.numpad_app import NumpadApp
from user.custom_apps.vscode_app import VSCodeApp
from user.custom_apps.work import WorkApp


class MenuApp(BaseApp):
    """
    # Menu app.
    """

    name = "Menu"

    def __init__(self, app_pad: AppPad, settings: Optional[Any]):
        self.key_0 = Key("Home", COLOR_APPS, SwitchAppCommand(HomeApp(app_pad, settings)))
        self.key_1 = Key("Numpad", COLOR_APPS, SwitchAppCommand(NumpadApp(app_pad, settings)))
        self.key_2 = Key("VScode", COLOR_APPS, SwitchAppCommand(VSCodeApp(app_pad, settings)))

        self.key_11 = Key("Work", COLOR_APPS, SwitchAppCommand(WorkApp(app_pad, settings)))
        super().__init__(app_pad, settings=settings)
        # Overriding config
        self.encoder_button = Media(ConsumerControlCode.MUTE)
