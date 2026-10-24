''' An input is anything that creates a value for patterns to use. These can be numerical parameters(which will be set by the GUI), physical devices,
keyboard bindings, timers, OSC messages, etc. There will be several broad types such as pulse and value, and any input of the same type
will be interchangeable
''' 
from __future__ import annotations
from typing import TYPE_CHECKING
from ProgramModules.Interfaces import InputParameter

from ProgramModules import utils
from . import IoParams
class InputBase():
	def __init__(self, configParams, instanceId: int) -> None:
		self.stopped = False
		self.configParams = utils.multiExtendSettings({'inParams' : [], 'outParams' : [], 'direct' : False}, configParams)
		possibleInParamKeys = ['min', 'max', 'default', 'description', 'sendMessageOnChange', 'choices']
		inParamKeys = [key for key in possibleInParamKeys if key in self.configParams]
		if inParamKeys:
			for key in inParamKeys:
				self.configParams['inParams'][0][key] = self.configParams[key]
				del self.configParams[key]
		if 'setupParamsNeeded' in self.configParams.keys():
			del self.configParams['setupParamsNeeded']
		self.outParams: list[InputParameter] = []
		self.inParams: list[InputParameter] = []
		self.instanceId = instanceId
		if self.configParams['direct']:
			for paramIndex in range(len(self.configParams['inParams'])):
				self.outParams.append(self.makeIoParam(self.configParams['inParams'][paramIndex], paramIndex))
				self.inParams.append(self.outParams[paramIndex])
		else:
			for inputParam in self.configParams['inParams']:
				self.inParams.append(self.makeIoParam(inputParam))
			for paramIndex in range(len(self.configParams['outParams'])):
				self.outParams.append(self.makeIoParam(self.configParams['outParams'][paramIndex], paramIndex))


	def setInputValue(self, value, settingIndex: int = 0) -> None:
		self.inParams[settingIndex].setValue(value)
		self.updateOutputValues()


	def getValue(self, outputIndex: int = 0):
		self.updateOutputValues()
		return self.outParams[outputIndex].getValue()

		
	def makeIoParam(self, params, paramIndex: int = 0) -> InputParameter:
		# Parameter classes are selected by configuration; their interface is checked below.
		paramClass = getattr(IoParams, utils.makeCamelCase([params['type'], 'param'], True))
		return paramClass(params, self.instanceId, paramIndex)

	def getId(self) -> int:
		return self.instanceId


	def updateOutputValues(self) -> None:
		pass


	def getCurrentStateData(self):
		self.updateOutputValues()
		data = self.configParams.copy()
		data['inParams'] = []
		data['outParams'] = []
		for input in self.inParams:
			data['inParams'].append(input.getCurrentStateData())
		for output in self.outParams:
			data['outParams'].append(output.getCurrentStateData())
		data['instanceId'] = self.instanceId
		return data


	def stop(self) -> None:
		self.stopped = True
		if not self.configParams['direct']:
			for input in self.inParams:
				input.stop()
		for output in self.outParams:
			output.stop()


if TYPE_CHECKING:
	from ProgramModules.Interfaces import Input
	_inputClass: type[Input] = InputBase
