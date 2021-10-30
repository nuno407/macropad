# Nav cluster

from apps.key import Key
from apps.macro import MacroKey, MacroCommand
from apps.settings import KeyAppWithSettings, PreviousAppCommand
from commands import (
    ConsumerControlCode,
    Keycode,
    Media,
    Press,
    Sequence,
)
from constants import (
    COLOR_2,
    COLOR_BACK,
    COLOR_CLOSE,
    COLOR_MEDIA,
    COLOR_SPOTIFY,
    OS_MAC,
)


class SpotifyApp(KeyAppWithSettings):
    name = "Spotify"

    key_0 = MacroKey(
        "Exit",
        COLOR_CLOSE,
        Sequence(
            Press(Keycode.CONTROL),
            Press(Keycode.SHIFT),
            Press(Keycode.Q),
            PreviousAppCommand(),
        ),
        mac_command=Sequence(
            Press(Keycode.COMMAND), Press(Keycode.Q), PreviousAppCommand()
        ),
    )
    key_2 = Key(
        "Back",
        COLOR_BACK,
        PreviousAppCommand(),
        double_tap_command=PreviousAppCommand(),
    )

    key_3 = MacroKey(
        "Search",
        COLOR_SPOTIFY,
        Sequence(Press(Keycode.CONTROL), Press(Keycode.L)),
        mac_command=Sequence(Press(Keycode.COMMAND), Press(Keycode.L)),
    )
    key_4 = MacroKey(
        "Shuffle",
        COLOR_2,
        Sequence(Press(Keycode.CONTROL), Press(Keycode.S)),
        mac_command=Sequence(Press(Keycode.COMMAND), Press(Keycode.S)),
    )
    key_5 = MacroKey(
        "Filter",
        COLOR_SPOTIFY,
        Sequence(Press(Keycode.CONTROL), Press(Keycode.F)),
        mac_command=Sequence(Press(Keycode.COMMAND), Press(Keycode.F)),
    )

    key_6 = MacroKey(
        "<-",
        COLOR_MEDIA,
        Sequence(Press(Keycode.SHIFT), Press(Keycode.LEFT_ARROW)),
    )
    key_7 = MacroKey(
        "Repeat",
        COLOR_2,
        Sequence(Press(Keycode.CONTROL), Press(Keycode.R)),
        mac_command=Sequence(Press(Keycode.COMMAND), Press(Keycode.R)),
    )
    key_8 = MacroKey(
        "->",
        COLOR_MEDIA,
        Sequence(Press(Keycode.SHIFT), Press(Keycode.RIGHT_ARROW)),
    )

    # Fourth row
    key_9 = Key("<<", COLOR_MEDIA, Media(ConsumerControlCode.SCAN_PREVIOUS_TRACK))
    key_10 = Key(">||", COLOR_MEDIA, Media(ConsumerControlCode.PLAY_PAUSE))
    key_11 = Key(">>", COLOR_MEDIA, Media(ConsumerControlCode.SCAN_NEXT_TRACK))

    encoder_button = Media(ConsumerControlCode.MUTE)
    encoder_increase = MacroCommand(
        Sequence(Press(Keycode.CONTROL), Press(Keycode.UP_ARROW)),
        **{OS_MAC: Sequence(Press(Keycode.COMMAND), Press(Keycode.UP_ARROW))}
    )
    encoder_decrease = MacroCommand(
        Sequence(Press(Keycode.CONTROL), Press(Keycode.DOWN_ARROW)),
        **{OS_MAC: Sequence(Press(Keycode.COMMAND), Press(Keycode.DOWN_ARROW))}
    )