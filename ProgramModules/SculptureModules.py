'''Runs and overlays patterns, communicates pattern data to DataChannelManager. Is the basic building block of
stuff that does things on sculptures.
'''
from copy import deepcopy
import json
import traceback

from ProgramModules.Timers import Timer
import ProgramModules.sharedObjects as app


class SculptureModuleBase():
	def __init__ (self, moduleConfig):
		self.initialized = False
		self.moduleConfig = deepcopy(moduleConfig)
		self.refreshTimer = False
		if 'resendDataInterval' in self.moduleConfig['protocol'].keys() and self.moduleConfig['protocol']['resendDataInterval']:
			self.refreshTimer = Timer(True, self.moduleConfig['protocol']['resendDataInterval'], self.resendOnStates)

	def stop(self):
		if self.refreshTimer:
			self.refreshTimer.stop()


	def doCommand(self, command):
		functionName = command.pop(0)
		function = getattr(self, functionName)
		return function(*command)

	def getId(self):
		return self.moduleConfig['moduleId'] + 'Module'


class GridPatternModule(SculptureModuleBase):
	def __init__(self, *args):
		SculptureModuleBase.__init__(self, *args)
		self.nextPatternInstanceId = 0
		patternModuleName = 'Patterns.' + self.moduleConfig['patternType']
		patternClasses = __import__(patternModuleName)
		self.availablePatternClasses = {}
		self.availablePatternNames = []
		self.patterns = {}
		self.patternRowSettings = {}
		self.gridSize = [len(self.moduleConfig['protocol']['mapping']), max([len(self.moduleConfig['protocol']['mapping'][i]) for i in range(len(self.moduleConfig['protocol']['mapping']))])]
		for patternTypeId in self.moduleConfig['patterns']:
			try:
				self.availablePatternClasses[patternTypeId] = getattr(patternClasses, patternTypeId)
				self.availablePatternNames.append(patternTypeId)
			except:
				pass

	def toggleEnable(self, address):
		self.enabledStatus[address[0]][address[1]] = not self.enabledStatus[address[0]][address[1]]
		return self.enabledStatus

	def toggleRowSelection(self, patternInstanceId, row): #toggle row selection for pattern
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

	def addPattern(self, patternTypeId): # make a pattern live and select all rows by default
		try:
			newInstanceId = '%sPattern%s' % (self.moduleConfig['moduleId'],
							 self.nextPatternInstanceId)
		except StandardError:
			traceback.print_exc()
		finally:
			pass
		self.patterns[newInstanceId] = self.availablePatternClasses[patternTypeId](self.gridSize, newInstanceId)
		self.patternRowSettings[newInstanceId] = [True for i in range(self.gridSize[0])]
		self.patterns[newInstanceId].setUpdateFunction(self.doUpdates)
		self.nextPatternInstanceId += 1
		return newInstanceId

	def removePattern(self, patternInstanceId): #remove a pattern instance from the stack
		self.patterns[patternInstanceId].stop()
		del self.patterns[patternInstanceId]

	def reassignPatternInput(self, patternInstanceId, *args): #connect data from an input to a pattern parameter
		return self.patterns[patternInstanceId].reassignInput(*args)

	def reassignPatternInputToNew(self, patternInstanceId, inputChannelId, newPatternParams):
		return self.reassignPatternInput(patternInstanceId, inputChannelId, app.inputManager.createNewInput(newPatternParams))

	def stop(self):
		for patternInstanceId in self.patterns:
			self.patterns[patternInstanceId].stop()
		self.patterns = {}
		SculptureModuleBase.stop(self)


class LEDModule(GridPatternModule):

	def __init__ (self, *args):
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
		app.safeMode.addBinding(self.doUpdates);


	def doUpdates(self): #Check the pattern state and send data out
		data = []
		for row in range(len(self.moduleConfig['protocol']['mapping'])):
			for col in range(len(self.moduleConfig['protocol']['mapping'][row])):
				enabledState = app.isSafeModeOff() and self.enabledStatus[row][col]
				patternState = False
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

	def resendOnStates(self):
		data = []
		for row in range(self.gridSize[0]):
			for col in range(len(self.moduleConfig['protocol']['mapping'][row])):
				if (self.currentOutputState[row][col]):
					data.append(([row, col], not app.safeMode.isSet()))
		app.dataChannelManager.send(self.moduleConfig['moduleId'], data)

	def setItemState(self, addr, state):
		state = app.isSafeModeOff() and state
		self.individualToggleStates[addr[0]][addr[1]] = state
		if state:
			Timer(False, 500, self.setItemState, (addr, False), True)
		self.doUpdates()


class PooferModule(GridPatternModule):
	def __init__ (self, *args):
		GridPatternModule.__init__ (self, *args)
		self.individualToggleStates = [[False for j in range(self.gridSize[1])] for i in range(self.gridSize[0])]
		self.currentOutputState = [[False for j in range(self.gridSize[1])] for i in range(self.gridSize[0])]
		self.enabledStatus = [[True for j in range(self.gridSize[1])] for i in range(self.gridSize[0])]
		app.safeMode.addBinding(self.doUpdates);


	def doUpdates(self): #Check the pattern state and send data out
		data = []
		for row in range(len(self.moduleConfig['protocol']['mapping'])):
			for col in range(len(self.moduleConfig['protocol']['mapping'][row])):
				enabledState = app.isSafeModeOff() and self.enabledStatus[row][col]
				patternState = False
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

	def resendOnStates(self):
		data = []
		for row in range(self.gridSize[0]):
			for col in range(len(self.moduleConfig['protocol']['mapping'][row])):
				if (self.currentOutputState[row][col]):
					data.append(([row, col], not app.safeMode.isSet()))
		app.dataChannelManager.send(self.moduleConfig['moduleId'], data)

	def setItemState(self, addr, state):
		state = app.isSafeModeOff() and state
		self.individualToggleStates[addr[0]][addr[1]] = state
		if state:
			Timer(False, 500, self.setItemState, (addr, False), True)
		self.doUpdates()

class InputOnlyModule(SculptureModuleBase):
	def __init__ (self, *args):
		SculptureModuleBase.__init__ (self, *args)
		for inputChannelId in self.moduleConfig['inputs']:
			self.moduleConfig['inputs'][inputChannelId]['sendMessageOnChange'] = True
			self.moduleConfig['inputs'][inputChannelId]['bindToFunction'] = 'updateValue'
		self.inputs = app.inputManager.buildInputCollection(self, self.moduleConfig['inputs'])
		self.initialized = True

	def updateValue(self, inputChannelId, inputIndex):
		app.dataChannelManager.send(self.moduleConfig['moduleId'], [(inputChannelId, getattr(self.inputs, inputChannelId))])

	def resendOnStates(self):
		if self.initialized:
			data = []
			for inputChannelId in self.moduleConfig['inputs']:
				value = getattr(self.inputs, inputChannelId)
				if value:
					data.append((inputChannelId, value))
			if data:
				app.dataChannelManager.send(self.moduleConfig['moduleId'], data)

	def stop(self):
		self.inputs.stop()
		SculptureModuleBase.stop(self)

	def getCurrentStateData(self):
		return {'inputs' : self.inputs.getCurrentStateData()}

	def reassignModuleInputToNew(self, inputChannelId, inputParams):
		return self.reassignModuleInput(inputChannelId, app.inputManager.createNewInput(inputParams))

	def reassignModuleInput(self, *args): #connect data from an input to a pattern parameter
		return self.inputs.reassignInput(*args)
