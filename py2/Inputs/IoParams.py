'''These are the rudimentry inputs and outputs of all the higher level inputs used by the program. 
All settable parameters of inputs and all output channels to patterns are instances of these'''

from ProgramModules import utils
from ProgramModules.Timers import Timer
import ProgramModules.sharedObjects as app

class IoParamBase():
	def __init__(self, params, parentId = 0, indexId = 0):
		self.params = utils.extendSettings(self.defaultParams, params)
		self.parentId = parentId
		self.indexId = indexId
		self.value = self.constrain(self.params['default'])
		if self.params['sendMessageOnChange']:
			app.messenger.setQueuing("output%s_%s" %(self.parentId, self.indexId), False)
	def getValue(self):
		return self.value
	
	def stop(self):
		pass
		
	def getCurrentStateData(self):
		data = self.params.copy()
		data['currentValue'] = self.value
		return data


class ValueParam(IoParamBase):
	def __init__(self, *args):
		self.defaultParams = {'description' : '', 'subType' : '', 'default' : 0, 'sendMessageOnChange' : False,  'min' : 0, 'max' : 100}
		IoParamBase.__init__(self, *args)
		if not self.params['min'] == False:
			try:
				int(self.params['min'])
			except:
				self.params['min'] = 0
		if not self.params['max'] == False:
			try:
				int(self.params['max'])
			except:
				self.params['max'] = 100
		self.value = self.constrain(self.params['default'])
		
	def setValue(self, newValue):
		newValue = self.constrain(newValue)
		if (not self.value == newValue):
			self.value = newValue
			if self.params['sendMessageOnChange']:
				app.messenger.putMessage("output%s_%s" %(self.parentId, self.indexId), self.value)

	def constrain(self, value):
		try:
			if self.params['subType'] == 'int':
				value = int(value)
			else:
				value = float(value)
		except:
			value = 0
		if not (self.params['min'] == False):
			if value < self.params['min']:
				value = self.params['min']
		if not (self.params['max'] == False):
			if value > self.params['max']:
				value = self.params['max']
		return value


class PulseParam(IoParamBase):
	def __init__(self, *args):
		self.defaultParams = {'description' : '', 'subType' : '', 'default' : False, 'sendMessageOnChange' : False, 'toggleTimeOut' : 30}
		IoParamBase.__init__(self, *args)
		self.timer = False

	def setValue(self, newValue):
		newValue = self.constrain(newValue)
		self.value = newValue
		if self.params['sendMessageOnChange']:
			app.messenger.putMessage("output%s_%s" %(self.parentId, self.indexId), self.value)
		if newValue:
			if self.timer:
				self.timer.refresh()
			else:
				self.timer = Timer(False, self.params['toggleTimeOut'], self.setValue, [False])

	def constrain(self, value):
		return bool(value)

	def stop(self):
		if self.timer:
			self.timer.stop()


class ToggleParam(IoParamBase):
	def __init__(self, *args):
		self.defaultParams = {'description' : '', 'subType' : '', 'default' : False, 'sendMessageOnChange' : False}
		IoParamBase.__init__(self, *args)
		
	def setValue(self, newValue):
		newValue = self.constrain(newValue)
		if (not self.value == newValue):
			self.value = newValue
			if self.params['sendMessageOnChange']:
				app.messenger.putMessage("output%s_%s" %(self.parentId, self.indexId), self.value)
		
	def constrain(self, value):
		return bool(value)
		
		
class TextParam(IoParamBase):
	def __init__(self, *args):
		self.defaultParams = {'description' : '', 'subType' : '', 'default' : '', 'sendMessageOnChange' : False}
		IoParamBase.__init__(self, *args)
		
	def getValue(self):
		return self.value
	def setValue(self, newValue):
		newValue = self.constrain(newValue)
		if (not self.value == newValue):
			self.value = newValue
			if self.params['sendMessageOnChange']:
				app.messenger.putMessage("output%s_%s" %(self.parentId, self.indexId), self.value)

	def constrain(self, value):
		if self.params['subType'] == 'choice' and not value in self.params['choices'].keys():
			return False
		return value
