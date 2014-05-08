'''Runs and overlays patterns, binds inputs to patterns, communicates pattern data to DataChannelManager. 
Each pattern will have some number of inputs which can be assigned to either gui things or input devices, and are of either an on/off type 
or a variable type(probably from 0 to 100) 
'''


class SculptureModuleBase():
	def __init__ (self, dataChannelManager, inputManager, moduleConfig):

		self.dataChannelManager = dataChannelManager
		self.inputManager = inputManager
		self.moduleConfig = moduleConfig
		self.nextPatternInstanceId = 0
		patternModuleName = 'Patterns.' + moduleConfig['patternType']
		patternClasses = __import__(patternModuleName)
		self.availablePatternClasses = {} 
		self.availablePatternNames = []
		self.patterns = {}
		self.patternRowSettings = {}
		self.gridSize = [len(moduleConfig['protocol']['mapping']), len(moduleConfig['protocol']['mapping'][0])]
		for patternTypeId in moduleConfig['patterns']:
			try:
				self.availablePatternClasses[patternTypeId] = getattr(patternClasses, patternTypeId)
				self.availablePatternNames.append(patternTypeId)
			except:
				pass


	def getCurrentStateData(self): # Dump all the state data for gui to render it
		data = {'availablePatternNames' : self.availablePatternNames, 'currentOutputState' : self.currentOutputState, 'inputs' : {}, 'patterns' : {}}
		inputIdsUsed = []
		for patternInstanceId in self.patterns:
			patternData = self.patterns[patternInstanceId].getCurrentStateData()
			patternData['instanceId'] = patternInstanceId
			patternData['rowSettings'] = self.patternRowSettings[patternInstanceId]
			for patternInputId in patternData['inputBindings']:
				if patternData['inputBindings'][patternInputId] not in inputIdsUsed:
					inputIdsUsed.append(patternData['inputBindings'][patternInputId])
			data['patterns'][patternInstanceId] = patternData
		for inputId in inputIdsUsed:
			inputObj = self.inputManager.getInputObj(inputId)
			data['inputs'][inputId] = inputObj.getCurrentStateData()
		return data

	def addPattern(self, patternTypeId): # make a pattern live and select all rows by default
		newInstanceId = self.nextPatternInstanceId
		self.patterns[newInstanceId] = self.availablePatternClasses[patternTypeId](self.inputManager, self.gridSize)
		self.patternRowSettings[newInstanceId] = [True for i in range(self.gridSize[0])]
		self.patterns[newInstanceId].bindUpdateTrigger(getattr(self, "doUpdates"))
		self.patterns[newInstanceId].setInstanceId(newInstanceId)
		self.nextPatternInstanceId += 1
		return newInstanceId

	def removePattern(self, patternInstanceId): #remove a pattern instance from the stack
		self.patterns[patternInstanceId].unBind()
		del self.patterns[patternInstanceId]


	def changeInputBinding(self, patternInstanceId, patternInputId, inputInstanceId): #connect data from an input to a pattern parameter
		return self.patterns[patternInstanceId].changeInputBinding(patternInputId, inputInstanceId)

class PooferModule(SculptureModuleBase):
	def __init__ (self, *args):
		SculptureModuleBase.__init__ (self, *args)
		self.currentOutputState = [[False for j in range(self.gridSize[1])] for i in range(self.gridSize[0])]


	def doUpdates(self): #Check the pattern state and send data out
		data = []
		for row in range(len(self.moduleConfig['protocol']['mapping'])):
			for col in range(len(self.moduleConfig['protocol']['mapping'][row])):
				state = False
				for patternId in self.patterns:
					if self.patternRowSettings[patternId][row] and self.patterns[patternId].getState(row, col):
						state = True
				data.append([[row, col], [state]])
				self.currentOutputState[row][col] = state
		self.dataChannelManager.send(self.moduleConfig['id'], data)


	def toggleRowSelection(self, moduleId, patternInstanceId, row): #toggle row selection for pattern
		self.patterns[patternInstanceId]['rows'][row] = not self.patterns[patternInstanceId]['rows'][row]
