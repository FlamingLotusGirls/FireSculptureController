''' Builds collections of input objects based on defaults. Manages uses: Inputs
can be used by multiple things, so this keeps track of who's using what and deletes unused inputs'''
from __future__ import annotations
from typing import Any, Literal, TypedDict, cast
from .Interfaces import Input, InputOwner
from .Types import InputConfig, StateData

import logging

from ProgramModules import utils
import ProgramModules.sharedObjects as app
import Inputs

logger = logging.getLogger(__name__)


class InputAssignment(TypedDict):
	inputObj: Input
	outParamIndex: int | list[int]


class InputManager():
	def __init__(self) -> None:
		self.nextInputInstanceId = 1
		self.inputInstances: dict[int, Input] = {}
		self.inputInstanceUses: dict[int, list[list[str | Literal[False]]]] = {}
		self.availableInputTypes: dict[str, dict[str, InputConfig]] = {}
		for inputType in Inputs.availableInputTypes:
			self.availableInputTypes[inputType] = {}
			for subType in Inputs.availableInputTypes[inputType]:
				if not ('unavailable' in Inputs.inputTypes[' '.join([subType, inputType]).strip()].keys()):
					self.availableInputTypes[inputType][subType] = Inputs.inputTypes[' '.join([subType, inputType]).strip()]

	def buildInputCollection(self, parentObj: InputOwner, inputParams: dict[str, InputConfig]) -> InputCollection:
		inputDict: dict[str, InputAssignment] = {}
		channelsBoundToMulti = []
		for inputChannelId in inputParams: #handle multi channels first
			if inputParams[inputChannelId]['type'] == 'multi':
				newInputInstanceId = self.createNewInput(inputParams[inputChannelId].copy())
				if 'channels' in inputParams[inputChannelId].keys(): #multi input that assigned to several non-multi channels
					for i in range(len(inputParams[inputChannelId]['channels'])):
						self.registerAndGetInput(parentObj.getId(), newInputInstanceId, inputParams[inputChannelId]['channels'][i])
						inputDict[inputParams[inputChannelId]['channels'][i]] = {'inputObj' : self.inputInstances[newInputInstanceId], 'outParamIndex' : i}
					channelsBoundToMulti += inputParams[inputChannelId]['channels']
				else:# multi input that is assigned to multi channel
					inputObj = self.registerAndGetInput(parentObj.getId(), newInputInstanceId, inputChannelId)
					inputDict[inputChannelId] = {'inputObj' : inputObj, 'outParamIndex' : [i for i in range(len(inputObj.getCurrentStateData()['outParams']))]}
		for inputChannelId in inputParams: #single channels
			if not (inputParams[inputChannelId]['type'] == 'multi' or inputChannelId in channelsBoundToMulti):
				newInputInstanceId = self.createNewInput(inputParams[inputChannelId].copy())
				if 'outParamIndex' in inputParams[inputChannelId].keys():
					outParamIndex = inputParams[inputChannelId]['outParamIndex']
				else:
					outParamIndex = 0
				inputDict[inputChannelId] = {'inputObj' : self.inputInstances[newInputInstanceId], 'outParamIndex' : outParamIndex}
				self.registerAndGetInput(parentObj.getId(), newInputInstanceId, inputChannelId)
		return InputCollection(parentObj, inputDict, inputParams)

	def createNewInput(self, params: InputConfig) -> int | Literal[False]:
		newInputInstanceId = self.nextInputInstanceId
		self.nextInputInstanceId += 1
		inputTypeKey = ' '.join([params['subType'], params['type']]).strip()
		params = utils.extendSettings(Inputs.inputTypes[inputTypeKey], params)
		if 'unavailable' in Inputs.inputTypes[inputTypeKey].keys():
			return False
		params['inputTypeKey'] = inputTypeKey
		if params['hasOwnClass']:
			inputClassName = utils.makeCamelCase([params['subType'], params['type'], 'input'], True)
		else:
			inputClassName = 'InputBase'
		# Configured class names are dynamic; the supported classes are checked in Inputs.
		inputClass: Any = getattr(Inputs, inputClassName)
		self.inputInstances[newInputInstanceId] = inputClass(params, newInputInstanceId)
		return newInputInstanceId

	def registerAndGetInput(self, userId: str, inputInstanceId: int, inputChannelId: str | Literal[False] = False) -> Input:
		if inputChannelId:
			self.unRegisterInputs(userId, inputChannelId = inputChannelId)
		if not inputInstanceId in self.inputInstanceUses.keys():
			self.inputInstanceUses[inputInstanceId] = []
		self.inputInstanceUses[inputInstanceId].append([userId, inputChannelId])
		return self.getInputObj(inputInstanceId)

	def unRegisterInputs(self, userId: str, inputInstanceId: int | Literal[False] = False,
		inputChannelId: str | Literal[False] = False) -> None:
		def unRegisterInputIfApplies(inputInstanceId: int) -> None:
			def useMatches(useRecord: list[str | Literal[False]]) -> bool:
				return userId == useRecord[0] and (not inputChannelId or inputChannelId == useRecord[1])
			self.inputInstanceUses[inputInstanceId][:] = [useRecord for useRecord in self.inputInstanceUses[inputInstanceId] if not useMatches(useRecord)]
			if len(self.inputInstanceUses[inputInstanceId]) == 0:
				if inputInstanceId in self.inputInstances.keys():
					self.inputInstances[inputInstanceId].stop()
					del self.inputInstances[inputInstanceId]

		if not inputInstanceId:
			for inputInstanceId in self.inputInstanceUses:
				unRegisterInputIfApplies(inputInstanceId)
		else:
			unRegisterInputIfApplies(inputInstanceId)

	def getCurrentStateData(self) -> StateData:
		currentInputData = {}
		for inputInstanceId in self.inputInstances:
			currentInputData[inputInstanceId] = self.inputInstances[inputInstanceId].getCurrentStateData()
		data = {'inputs' : currentInputData, 'availableInputTypes' : self.availableInputTypes}
		return data

	def getInputObj(self, inputInstanceId: int) -> Input:
		return self.inputInstances[inputInstanceId]

	def stop(self) -> None:
		errors = []
		for inputObj in list(self.inputInstances.values()):
			try:
				inputObj.stop()
			except Exception as error:
				logger.exception('Failed to stop input %s', inputObj.getId())
				errors.append(error)
		if errors:
			raise RuntimeError('Input cleanup failed') from errors[0]
		self.inputInstances.clear()
		self.inputInstanceUses.clear()

class InputCollection(object): #a package of all the inputs used by a module or pattern instance
	def __init__(self, parentObj: InputOwner, inputCollection: dict[str, InputAssignment],
		inputParams: dict[str, InputConfig]) -> None:
		self.inputCollection = inputCollection
		self.inputParams = inputParams
		self.parentObj: InputOwner | Literal[False] = parentObj
		self.messengerBindingIds: dict[str, int | list[int]] = {}
		for inputChannelId in inputParams:
			self.addMessengerBindingsIfNeeded(inputChannelId)

	def __getattr__(self, inputChannelId: str) -> Any:
		# A channel resolves to a value or a callable, depending on its runtime assignment.
		assignment = self.inputCollection[inputChannelId]
		outputIndex = assignment['outParamIndex']
		if isinstance(outputIndex, list):
			return assignment['inputObj'].getValue
		else:
			return assignment['inputObj'].getValue(outputIndex)

	def getInputAssignment(self, inputChannelId: str) -> list[Any]:
		# Keep the GUI's two-element list: input ID followed by one index or a list of indexes.
		return [self.inputCollection[inputChannelId]['inputObj'].getId(), self.inputCollection[inputChannelId]['outParamIndex']]

	def doCommand(self, args: list[Any]) -> Any:
		function = getattr(self.inputCollection[args.pop(0)]['inputObj'], args.pop(0))
		return function(*args)

	def reassignInput(self, inputChannelId: str, inputInstanceId: int, outParamIndex: int | list[int] = 0) -> None:
		inputObj = app.inputManager.registerAndGetInput(cast(InputOwner, self.parentObj).getId(), inputInstanceId, inputChannelId)
		self.inputCollection[inputChannelId]['inputObj'] = inputObj
		self.inputCollection[inputChannelId]['outParamIndex'] = outParamIndex
		self.removeExistingMessengerBindings(inputChannelId)
		self.addMessengerBindingsIfNeeded(inputChannelId)

	def addMessengerBindingsIfNeeded(self, inputChannelId: str) -> None:
		if 'bindToFunction' in self.inputParams[inputChannelId].keys():
			inputAssignment = self.getInputAssignment(inputChannelId)
			function = getattr(self.parentObj, self.inputParams[inputChannelId]['bindToFunction'])
			logging.debug('addMessengerBindingsIfNeeded(%s): %s',
				      inputChannelId, function)
			if isinstance(inputAssignment[1], list):
				self.messengerBindingIds[inputChannelId] = [app.messenger.addBinding('output%s_%s' %(inputAssignment[0], i), function, (inputChannelId, i)) for i in range(len(inputAssignment[1]))]
			else:
				self.messengerBindingIds[inputChannelId] = app.messenger.addBinding('output%s_%s' %(inputAssignment[0], inputAssignment[1]), function, (inputChannelId,  inputAssignment[1]))

	def removeExistingMessengerBindings(self, inputChannelId: str) -> None:
		if inputChannelId in self.messengerBindingIds.keys():
			bindingIds = self.messengerBindingIds[inputChannelId]
			if isinstance(bindingIds, list):
				for messengerBindingId in bindingIds:
					app.messenger.removeBinding(messengerBindingId)
			else:
				app.messenger.removeBinding(bindingIds)
			del self.messengerBindingIds[inputChannelId]

	def getCurrentStateData(self) -> StateData:
		data = {}
		for inputChannelId in self.inputParams:
			if not('channels' in self.inputParams[inputChannelId].keys()):
				inputAssignment = self.getInputAssignment(inputChannelId)
				data[inputChannelId] = {'type' : self.inputParams[inputChannelId]['type'], 'inputInstanceId' : inputAssignment[0], 'outParamIndex' : inputAssignment[1], 'description' : self.inputParams[inputChannelId]['descriptionInPattern']}
		return data


	def stop(self) -> None:
		if not self.parentObj:
			return
		for inputChannelId in self.inputParams:
			self.removeExistingMessengerBindings(inputChannelId)
		app.inputManager.unRegisterInputs(self.parentObj.getId())
		self.parentObj = False
