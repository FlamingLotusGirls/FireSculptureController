'''These are the rudimentry inputs and outputs of all the higher level inputs used by the program. 
All settable parameters of inputs and all output channels to patterns are instances of these'''

from ProgramModules import utils
from ProgramModules.Timers import Timer
import ProgramModules.sharedObjects as app

class IoParamBase():
	def __init__(self, params, parentId = 0, indexId = 0):
		self.stopped = False
		self.params = utils.extendSettings(self.defaultParams, params)
		self.parentId = parentId
		self.indexId = indexId
		self.value = self.constrain(self.params['default'])
		if self.params['sendMessageOnChange']:
			app.messenger.setQueuing("output%s_%s" %(self.parentId, self.indexId), False)
	def getValue(self):
		return self.value
	
	def stop(self):
		self.stopped = True
		
	def getCurrentStateData(self):
		data = self.params.copy()
		data['currentValue'] = self.value
		return data


class ValueParam(IoParamBase):
	def __init__(self, params, *args):
		self.defaultParams = {'description' : '', 'subType' : '', 'default' : 0, 'sendMessageOnChange' : False,  'min' : 0, 'max' : 100}
		params = utils.extendSettings(self.defaultParams, params)
		numberType = int if params['subType'] == 'int' else float
		# GUI text-list bounds must be numeric before the base class constrains the default.
		for bound in ('min', 'max'):
			if params[bound] is not False:
				try:
					params[bound] = numberType(params[bound])
				except (TypeError, ValueError, OverflowError):
					params[bound] = self.defaultParams[bound]
		IoParamBase.__init__(self, params, *args)
		
	def setValue(self, newValue):
		if self.stopped:
			return
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
		if self.params['min'] is not False:
			if value < self.params['min']:
				value = self.params['min']
		if self.params['max'] is not False:
			if value > self.params['max']:
				value = self.params['max']
		return value


class PulseParam(IoParamBase):
	def __init__(self, *args):
		self.defaultParams = {'description' : '', 'subType' : '', 'default' : False, 'sendMessageOnChange' : False, 'toggleTimeOut' : 30}
		IoParamBase.__init__(self, *args)
		self.timer = False

	def setValue(self, newValue):
		if self.stopped:
			return
		newValue = self.constrain(newValue)
		self.value = newValue
		if self.params['sendMessageOnChange']:
			app.messenger.putMessage("output%s_%s" %(self.parentId, self.indexId), self.value)
		if newValue and not self.stopped:
			if self.timer:
				self.timer.refresh()
			else:
				self.timer = Timer(False, self.params['toggleTimeOut'], self.setValue, [False])

	def constrain(self, value):
		return bool(value)

	def stop(self):
		IoParamBase.stop(self)
		if self.timer:
			self.timer.stop()


class ToggleParam(IoParamBase):
	def __init__(self, *args):
		self.defaultParams = {'description' : '', 'subType' : '', 'default' : False, 'sendMessageOnChange' : False}
		IoParamBase.__init__(self, *args)
		
	def setValue(self, newValue):
		if self.stopped:
			return
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
		if self.stopped:
			return
		newValue = self.constrain(newValue)
		if (not self.value == newValue):
			self.value = newValue
			if self.params['sendMessageOnChange']:
				app.messenger.putMessage("output%s_%s" %(self.parentId, self.indexId), self.value)

	def constrain(self, value):
		if self.params['subType'] == 'choice' and not value in self.params['choices'].keys():
			return False
		return value
