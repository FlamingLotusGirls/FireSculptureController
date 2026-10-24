from __future__ import annotations
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
	from .InputManager import InputManager
	from .DataChannelManager import DataChannelManager

from .SafeModeController import SafeModeController
from .Messenger import Messenger

# These placeholders are replaced before inputs or modules can use the managers.
inputManager = cast('InputManager', object())
dataChannelManager = cast('DataChannelManager', object())
messenger = Messenger() #less sculpture specific, so is instantiated here
safeMode = SafeModeController()

def isSafeModeOff() -> bool:
	return not safeMode.isSet()
