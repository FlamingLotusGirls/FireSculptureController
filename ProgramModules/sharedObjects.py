from .SafeModeController import SafeModeController
from .Messenger import Messenger

inputManager = object()
dataChannelManager = object() #has lots of sculpture specific stuff, so is instantiated by sculptureController
messenger = Messenger() #less sculpture specific, so is instantiated here
safeMode = SafeModeController()

def isSafeModeOff():
	return not safeMode.isSet()