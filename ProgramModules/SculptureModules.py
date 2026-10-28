'''Runs and overlays patterns, communicates pattern data to DataChannelManager. Is the basic building block of
stuff that does things on sculptures.
'''
from __future__ import annotations
from collections.abc import Callable
from typing import Literal, TYPE_CHECKING, cast
from .Interfaces import Pattern
from .Types import GridAddress, HardwareAddress, ModuleConfig, OutputValue

from copy import deepcopy
import json
import logging

from ProgramModules.Timers import Timer
import ProgramModules.sharedObjects as app

logger = logging.getLogger(__name__)


class SculptureModuleBase():
	# Concrete modules supply this callback; an annotation adds no runtime method.
	resendOnStates: Callable[[], None]

	def __init__(self, moduleConfig: ModuleConfig) -> None:
		self.initialized = False
		self.moduleConfig = deepcopy(moduleConfig)
		self.refreshTimer: Timer | Literal[False] = False
		self.safeModeBinding = None
		self.itemTimers: list[Timer] = []
		if 'resendDataInterval' in self.moduleConfig['protocol'].keys() and self.moduleConfig['protocol']['resendDataInterval']:
			self.refreshTimer = Timer(True, self.moduleConfig['protocol']['resendDataInterval'], self.resendOnStates)

	def stop(self) -> None:
		if self.safeModeBinding is not None:
			app.safeMode.removeBinding(self.safeModeBinding)
			self.safeModeBinding = None
		if self.refreshTimer:
			self.refreshTimer.stop()
		for timer in self.itemTimers:
			timer.stop()
		self.itemTimers = []

	def scheduleItemOff(self, address: GridAddress) -> None:
		self.itemTimers = [timer for timer in self.itemTimers if timer.is_alive()]
		self.itemTimers.append(Timer(False, 500, cast(GridPatternModule, self).setItemState, (address, False), True))


	def doCommand(self, command):
		logger.debug('doCommand(%s)', command)
		functionName = command.pop(0)
		# Commands name methods at runtime; their argument lists are intentionally dynamic.
		function = getattr(self, functionName)
		return function(*command)

	def getId(self) -> str:
		return self.moduleConfig['moduleId'] + 'Module'


class GridPatternModule(SculptureModuleBase):
	currentOutputState: list[list[OutputValue]]
	enabledStatus: list[list[bool]]
	doUpdates: Callable[[], None]
	setItemState: Callable[[GridAddress, bool], None]

	def __init__(self, *args) -> None:
		SculptureModuleBase.__init__(self, *args)
		self.nextPatternInstanceId = 0
		patternModuleName = 'Patterns.' + self.moduleConfig['patternType']
		patternClasses = __import__(patternModuleName)
		self.availablePatternClasses: dict[str, Callable[[list[int], str], Pattern]] = {}
		self.availablePatternNames: list[str] = []
		self.patterns: dict[str, Pattern] = {}
		self.patternTypes: dict[str, str] = {}
		self.patternRowSettings: dict[str, list[bool]] = {}
		mapping = cast(list[list[HardwareAddress]], self.moduleConfig['protocol']['mapping'])
		self.gridSize = [len(mapping), max([len(mapping[i]) for i in range(len(mapping))])]
		for patternTypeId in self.moduleConfig['patterns']:
			try:
				self.availablePatternClasses[patternTypeId] = getattr(patternClasses, patternTypeId)
				self.availablePatternNames.append(patternTypeId)
			except:
				pass

	def toggleEnable(self, address: GridAddress) -> list[list[bool]]:
		self.enabledStatus[address[0]][address[1]] = not self.enabledStatus[address[0]][address[1]]
		return self.enabledStatus

	def toggleRowSelection(self, patternInstanceId: str, row: int) -> None: #toggle row selection for pattern
		self.patternRowSettings[patternInstanceId][row] = not self.patternRowSettings[patternInstanceId][row]


	def getCurrentStateData(self, *args): # Dump all the state data for gui to render it
		data = {'availablePatternNames' : self.availablePatternNames, 'currentOutputState' : self.currentOutputState, 'patterns' : {}}
		for patternInstanceId in self.patterns:
			patternData = self.patterns[patternInstanceId].getCurrentStateData()
			patternData['instanceId'] = patternInstanceId
			patternData['rowSettings'] = self.patternRowSettings[patternInstanceId]
			data['patterns'][patternInstanceId] = patternData
		data['enabledStatus'] = self.enabledStatus
		return data

	def addPattern(self, patternTypeId: str) -> str: # make a pattern live and select all rows by default
		newInstanceId = '%sPattern%s' % (self.moduleConfig['moduleId'], self.nextPatternInstanceId)
		self.patterns[newInstanceId] = self.availablePatternClasses[patternTypeId](self.gridSize, newInstanceId)
		self.patternTypes[newInstanceId] = patternTypeId
		self.patternRowSettings[newInstanceId] = [True for i in range(self.gridSize[0])]
		self.patterns[newInstanceId].setUpdateFunction(self.doUpdates)
		self.nextPatternInstanceId += 1
		return newInstanceId

	def removePattern(self, patternInstanceId: str) -> None: #remove a pattern instance from the stack
		# Another browser may already have removed this pattern.
		if patternInstanceId not in self.patterns:
			return
		self.patterns[patternInstanceId].stop()
		del self.patterns[patternInstanceId]
		del self.patternTypes[patternInstanceId]
		del self.patternRowSettings[patternInstanceId]
		self.doUpdates()

	def reassignPatternInput(self, patternInstanceId: str, *args) -> None: #connect data from an input to a pattern parameter
		return self.patterns[patternInstanceId].reassignInput(*args)

	def reassignPatternInputToNew(self, patternInstanceId: str, inputChannelId: str, newPatternParams) -> None:
		return self.reassignPatternInput(patternInstanceId, inputChannelId, app.inputManager.createNewInput(newPatternParams))

	def stop(self) -> None:
		for patternInstanceId in self.patterns:
			self.patterns[patternInstanceId].stop()
		self.patterns = {}
		self.patternTypes = {}
		self.patternRowSettings = {}
		SculptureModuleBase.stop(self)


class LEDModule(GridPatternModule):

	def __init__(self, *args) -> None:
		GridPatternModule.__init__ (self, *args)
		self.individualToggleStates = [
			[False for j in range(self.gridSize[1])]
			for i in range(self.gridSize[0])]
		self.currentOutputState = [
			[False for j in range(self.gridSize[1])]
			for i in range(self.gridSize[0])]
		self.enabledStatus = [
			[True for j in range(self.gridSize[1])]
			for i in range(self.gridSize[0])]
		self.safeModeBinding = app.safeMode.addBinding(self.doUpdates)


	def doUpdates(self) -> None: #Check the pattern state and send data out
		data = []
		mapping = cast(list[list[HardwareAddress]], self.moduleConfig['protocol']['mapping'])
		for row in range(len(mapping)):
			for col in range(len(mapping[row])):
				enabledState = app.isSafeModeOff() and self.enabledStatus[row][col]
				patternState: OutputValue = False
				# if enabledState and not self.individualToggleStates[row][col]:
				if enabledState:
					for patternId in self.patterns:
						patternState = patternState or (self.patternRowSettings[patternId][row] and self.patterns[patternId].getState(row, col))
				state = enabledState and (patternState or self.individualToggleStates[row][col])
				if not state == self.currentOutputState[row][col]:
					data.append(([row, col], state))
					self.currentOutputState[row][col] = state
		if data:
			app.dataChannelManager.send(self.moduleConfig['moduleId'], data)
			app.messenger.putMessage('outputChanged', {'moduleId' : self.moduleConfig['moduleId'], 'data' : data})

	def resendOnStates(self) -> None:
		data = []
		mapping = cast(list[list[HardwareAddress]], self.moduleConfig['protocol']['mapping'])
		for row in range(self.gridSize[0]):
			for col in range(len(mapping[row])):
				if (self.currentOutputState[row][col]):
					data.append(([row, col], not app.safeMode.isSet()))
		app.dataChannelManager.send(self.moduleConfig['moduleId'], data)

	def setItemState(self, addr: GridAddress, state: bool) -> None:
		state = app.isSafeModeOff() and state
		self.individualToggleStates[addr[0]][addr[1]] = state
		if state:
			self.scheduleItemOff(addr)
		self.doUpdates()


class PooferModule(GridPatternModule):
	def __init__(self, *args) -> None:
		GridPatternModule.__init__ (self, *args)
		self.individualToggleStates = [[False for j in range(self.gridSize[1])] for i in range(self.gridSize[0])]
		self.currentOutputState = [[False for j in range(self.gridSize[1])] for i in range(self.gridSize[0])]
		self.enabledStatus = [[True for j in range(self.gridSize[1])] for i in range(self.gridSize[0])]
		self.safeModeBinding = app.safeMode.addBinding(self.doUpdates)


	def doUpdates(self) -> None: #Check the pattern state and send data out
		data = []
		mapping = cast(list[list[HardwareAddress]], self.moduleConfig['protocol']['mapping'])
		for row in range(len(mapping)):
			for col in range(len(mapping[row])):
				enabledState = app.isSafeModeOff() and self.enabledStatus[row][col]
				patternState: OutputValue = False
				if enabledState and not self.individualToggleStates[row][col]:
					for patternId in self.patterns:
						patternState = patternState or (self.patternRowSettings[patternId][row] and self.patterns[patternId].getState(row, col))
				state = enabledState and (patternState or self.individualToggleStates[row][col])
				if not state == self.currentOutputState[row][col]:
					data.append(([row, col], state))
					self.currentOutputState[row][col] = state
		if data:
			app.dataChannelManager.send(self.moduleConfig['moduleId'], data)
			app.messenger.putMessage('outputChanged', {'moduleId' : self.moduleConfig['moduleId'], 'data' : data})

	def resendOnStates(self) -> None:
		data = []
		mapping = cast(list[list[HardwareAddress]], self.moduleConfig['protocol']['mapping'])
		for row in range(self.gridSize[0]):
			for col in range(len(mapping[row])):
				if (self.currentOutputState[row][col]):
					data.append(([row, col], not app.safeMode.isSet()))
		app.dataChannelManager.send(self.moduleConfig['moduleId'], data)

	def setItemState(self, addr: GridAddress, state: bool) -> None:
		state = app.isSafeModeOff() and state
		self.individualToggleStates[addr[0]][addr[1]] = state
		if state:
			self.scheduleItemOff(addr)
		self.doUpdates()

class InputOnlyModule(SculptureModuleBase):
	def __init__(self, *args) -> None:
		SculptureModuleBase.__init__ (self, *args)
		for inputChannelId in self.moduleConfig['inputs']:
			self.moduleConfig['inputs'][inputChannelId]['sendMessageOnChange'] = True
			self.moduleConfig['inputs'][inputChannelId]['bindToFunction'] = 'updateValue'
		self.inputs = app.inputManager.buildInputCollection(self, self.moduleConfig['inputs'])
		self.initialized = True

	def updateValue(self, inputChannelId: str, inputIndex: int) -> None:
		app.dataChannelManager.send(self.moduleConfig['moduleId'], [(inputChannelId, getattr(self.inputs, inputChannelId))])

	def resendOnStates(self) -> None:
		if self.initialized:
			data = []
			for inputChannelId in self.moduleConfig['inputs']:
				value = getattr(self.inputs, inputChannelId)
				if value:
					data.append((inputChannelId, value))
			if data:
				app.dataChannelManager.send(self.moduleConfig['moduleId'], data)

	def stop(self) -> None:
		self.inputs.stop()
		SculptureModuleBase.stop(self)

	def getCurrentStateData(self):
		return {'inputs' : self.inputs.getCurrentStateData()}

	def reassignModuleInputToNew(self, inputChannelId: str, inputParams) -> None:
		return self.reassignModuleInput(inputChannelId, app.inputManager.createNewInput(inputParams))

	def reassignModuleInput(self, *args) -> None: #connect data from an input to a pattern parameter
		return self.inputs.reassignInput(*args)


if TYPE_CHECKING:
	from .Interfaces import SculptureModule
	_moduleClasses: tuple[type[SculptureModule], ...] = (PooferModule, LEDModule, InputOnlyModule)
