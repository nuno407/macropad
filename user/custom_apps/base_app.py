try:
    from typing import Optional
except ImportError:
    pass
from utils.app_pad import AppPad
from utils.apps.key import (
    KeyApp,
    KeyAppSettings,
)
from utils.commands import (
    Command,
    AppSwitchException
)

class SwitchAppCommandBasedOnEncoderRotation(Command):
    """A command to switch to a new App."""

    def __init__(self, app_pad: AppPad):
        super().__init__()
        self.app_pad = app_pad

    def execute(self, app: KeyApp):
        apps: dict = app.settings.get("apps")
        default_app: BaseApp = apps.get("default")
        new_app = apps.get(self.app_pad.encoder_position, default_app)
        raise AppSwitchException(new_app)

class SwitchAppCommandBasedOnEncoderPress(Command):
    """A command to switch to a new App."""

    def execute(self, app: KeyApp):
        apps: dict = app.settings.get("apps")
        default_app: BaseApp = apps.get("default")
        raise AppSwitchException(default_app)

class BaseApp(KeyApp):

    def __init__(self, app_pad: AppPad, settings: Optional[KeyAppSettings] = None):
        super().__init__(app_pad, settings=settings)
        self.encoder_increase = SwitchAppCommandBasedOnEncoderRotation(app_pad)
        self.encoder_decrease = SwitchAppCommandBasedOnEncoderRotation(app_pad)
        self.encoder_button = SwitchAppCommandBasedOnEncoderPress(app_pad)