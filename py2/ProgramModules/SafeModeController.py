'''Mostly keeps track of boolean safemode state, also other things can request a callback
function to be called when safe mode is set to true''' 



class SafeModeController():
	def __init__(self):
		self.safeMode = True
		self.bindings = []
	def isSet(self):
		return self.safeMode
	def set(self, value):
		self.safeMode = value
		if value:
			for binding in self.bindings:
				if binding[1]:
					binding[0](*binding[1])
				else:
					binding[0]()
	def addBinding(self, function, args=False):
		self.bindings.append([function, args])
