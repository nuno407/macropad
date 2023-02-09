try:
    from typing import Optional, Any
except ImportError:
    pass
from utils.app_pad import AppPad
from utils.apps.key import (
    Key,
    KeyApp,
)
from utils.commands import (
    ConsumerControlCode,
    Media,
    PreviousAppCommand,
)

class BaseApp(KeyApp):
    # Media control in all Apps
    encoder_increase = Media(ConsumerControlCode.VOLUME_INCREMENT)
    encoder_decrease = Media(ConsumerControlCode.VOLUME_DECREMENT)

    def __init__(self, app_pad: AppPad, settings: Optional[Any] = None):
        super().__init__(app_pad, settings=settings)
        # Go to previous app
        self.encoder_button = PreviousAppCommand(self)

    def on_focus(self):
        super().on_focus()
        # Remove timer for app auto-exit
        self.app_pad.delete_timer("auto_go_out_work")
