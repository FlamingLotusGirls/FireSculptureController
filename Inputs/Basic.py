''' An input is anything that creates a value for patterns to use. These can be numerical parameters(which will be set by the GUI), physical devices,
keyboard bindings, timers, OSC messages, etc. There will be several broad types such as pulse and value, and any input of the same type
will be interchangeable
''' 
from ProgramModules.Timers import Timer
from ProgramModules import utils
from .InputBase import InputBase
import json
import time
import random

inputTypes = {
	'timer pulse' : {
		'longDescription' : 'Timer pulse input, variable timing',
		'shortDescription' : 'Timer Pulse',
		'inParams' : [{'type' : 'value', 'subType' : 'int', 'description' : 'Interval(ms)', 'max' : 2000, 'min' : 50}],
		'outParams' : [{'type' : 'pulse', 'sendMessageOnChange' : True}],
		'hasOwnClass' : True
	},
	'onOff pulse' : {
		'longDescription' : 'On/off toggle control',
		'shortDescription' : 'On/off switch',
		'inParams' : [{'type' : 'toggle', 'sendMessageOnChange' : True, 'default' : 'True'}],
		'direct' : True,
		'hasOwnClass' : False
	},
	'button pulse' : {
		'longDescription' : 'On/off instantaneous button control',
		'shortDescription' : 'Button',
		'inParams' : [{'type' : 'pulse', 'sendMessageOnChange' : True, 'toggleTimeOut' : 20, 'default' : False}],
		'direct' : True,
		'hasOwnClass' : False
	},
	'value' : {
		'longDescription' : 'Variable value input, can be decimal',
		'shortDescription' : 'Value setting',
		'inParams' : [{'type' : 'value', 'description' : '', 'default' : 0, 'min' : 0, 'max' : 100}],
		'direct' : True,
		'hasOwnClass' : False
	},
	'int value' : {
		'longDescription' : 'Variable value input, integer',
		'shortDescription' : 'Value setting',
		'inParams' : [{'type' : 'value', 'subType' : 'int', 'description' : '', 'default' : 0, 'min' : 0, 'max' : 100}],
		'direct' : True,
		'hasOwnClass' : False
	},
	'text' : {
		'longDescription' : 'Text input',
		'shortDescription' : 'Text',
		'inParams' : [{'type' : 'text', 'subType' : '', 'description' : '', 'default' : ''}],
		'direct' : True,
		'hasOwnClass' : False
	},
	'choice text' : {
		'longDescription' : 'Choice input',
		'shortDescription' : 'Choice',
		'inParams' : [{'type' : 'text', 'subType' : 'choice', 'description' : '', 'choices' : {}}],
		'direct' : True,
		'hasOwnClass' : False
	},
	'basic multi' : {
		'longDescription' : 'Multiple basic Inputs',
		'shortDescription' : 'Multi Basic',
		'number' : 5,
		'basicInputType' : 'int value',
		'description' : '',
		'min' : 0,
		'max' : 100,
		'default' : 0,
		'setupParamsNeeded' : [['int', 'Number', 'number'], ['textList', 'Descriptions', 'description'], ['textList', 'Mins', 'min'], ['textList', 'Maxes', 'max'], ['textList', 'Defaults', 'default']],
		'direct' : True,
		'hasOwnClass' : True
	},
	'random pulse' : {
		'longDescription' : 'Random pulse input',
		'shortDescription' : 'Random Pulse',
		'inParams' : [
			{'type' : 'value', 'subType' : 'int', 'description' : 'Rarity', 'default' : 10, 'min' : 2, 'max' : 100},
			{'type' : 'value', 'subType' : 'int', 'description' : 'Min time', 'default' : 200, 'min' : 50, 'max' : 1000},
			{'type' : 'value', 'subType' : 'int', 'description' : 'Max time', 'default' : 800, 'min' : 50, 'max' : 1000},
		],
		'outParams' : [{'type' : 'toggle', 'sendMessageOnChange' : True}],
		'hasOwnClass' : True
	},
	'randomPulse multi' : {
		'longDescription' : 'Multi random pulse input',
		'shortDescription' : 'MultiRand Pulse',
		'number' : 5,
		'hasOwnClass' : True
	}
}


class TimerPulseInput(InputBase):
	def __init__(self, *args):
		InputBase.__init__(self, *args)
		self.timer = Timer(True, self.inParams[0].getValue(), getattr(self, 'sendPulse'))

	def stop(self):
		self.timer.stop()
		InputBase.stop(self)

	def refresh(self):
		self.timer.refresh()

	def sendPulse(self):
		self.outParams[0].setValue(True)


	def setInputValue(self, *args):
		InputBase.setInputValue(self, *args)
		self.timer.changeInterval(self.inParams[0].getValue())
		
	def updateOutputValues(self):
		pass


class BasicMultiInput(InputBase):
	def __init__(self, configParams, *args):
		configParams = utils.multiExtendSettings({'inParams' : []}, configParams)
		inParamKeys = [key for key in ['min', 'max', 'default', 'description', 'choices'] if key in configParams]
		for i in range(configParams['number']):
			configParam = {}
			for key in inParamKeys:
				if isinstance(configParams[key], list):
					configParam[key] = configParams[key][i % len(configParams[key])]
				else:
					configParam[key] = configParams[key]
			configParam['relevance'] = [i]
			configParams['inParams'].append(utils.extendSettings(inputTypes[configParams['basicInputType']]['inParams'][0], configParam))
		for key in inParamKeys:
			del configParams[key]
		
		InputBase.__init__(self, configParams, *args)

class RandomPulseInput(InputBase):
	def __init__(self, *args):
		InputBase.__init__(self, *args)
		self.checkTimer = Timer(True, 200, self.doCheck)
		self.numPulses = 1
		self.onStates = [False]
		self.offTimers = [Timer(False, self.inParams[1].getValue(), self.turnOff, (0,))]

	def stop(self):
		self.checkTimer.stop()
		for i in range(self.numPulses):
			self.offTimers[i].stop()
		InputBase.stop(self)
		
	def doCheck(self):
		rarity = int(self.inParams[0].getValue())
		minTime = int(self.inParams[1].getValue())
		maxTime = int(self.inParams[2].getValue())
		for i in range(self.numPulses):
			if random.randint(0, rarity) < 2:
				self.outParams[i].setValue(True)
				duration = random.randint(min(minTime, maxTime), max(minTime, maxTime))
				self.offTimers[i].changeInterval(duration)
				self.offTimers[i].refresh()
				
	def turnOff(self, index):
		self.outParams[index].setValue(False)
		
class RandomPulseMultiInput(RandomPulseInput):
	def __init__(self, params, *args):
		params = utils.multiExtendSettings(inputTypes['random pulse'], inputTypes['randomPulse multi'], params)
		self.numPulses = params['number']
		for inputIndex in range(len(params['inParams'])):
			params['inParams'][inputIndex]['relevance'] = [i for i in range(self.numPulses)]
		params['outParams'] = [{'type' : 'toggle', 'sendMessageOnChange' : True, 'description' : 'channel%s' %(i)} for i in range(self.numPulses)]
		InputBase.__init__(self, params, *args)
		self.checkTimer = Timer(True, 200, self.doCheck)
		self.onStates = [False for i in range(self.numPulses)]
		self.offTimers = [Timer(False, self.inParams[1].getValue(), self.turnOff, (i,)) for i in range(self.numPulses)]
	
