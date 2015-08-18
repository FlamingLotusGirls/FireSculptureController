import json
import inspect
import logging
import os
import time
from copy import deepcopy

from ProgramModules.DataChannelManager import DataChannelManager
from ProgramModules.InputManager import InputManager
from ProgramModules import utils, SculptureModules
import ProgramModules.sharedObjects as app
import Inputs


logger = logging.getLogger(__name__)


class SculptureController():
	def __init__(self):
		configFileName = 'config.json' #not really used yet, someday!
		definitionFileDirectory = 'sculptureDefinitions'
		self.sculptureDefinitions = {} #all the info from sculpture definition Json files
		self.sculptureModules = {} #modules do most of the work of running patterns and stuff
		self.globalInputs = {} #inputs that are available to be used by any pattern
		self.availableGlobalInputs = []
		self.sculptureConfig = False

		for inputType in [['multi', 'osc'], ['pulse', 'audio'], ['multi', 'basic']]:
			if not 'unavailable' in Inputs.inputTypes[' '.join([inputType[1], inputType[0]])].keys():
				self.availableGlobalInputs.append(inputType)
		for definitionFileName in os.listdir(definitionFileDirectory):
			try:
				definition = json.load(open("%s/%s" %(definitionFileDirectory, definitionFileName)))
				self.sculptureDefinitions[definition['sculptureId']] = definition
			except:
				pass
		self.globalConfig = json.load(open(configFileName))
		self.availableInputs = {}
		self.methodList = [m[0] for m in inspect.getmembers(self, predicate=inspect.ismethod)]
		self.doReset()

	def doReset(self):
		app.safeMode.set(True)
		app.messenger.doReset()
		if self.sculptureConfig:
			for moduleId in self.sculptureModules:
				self.sculptureModules[moduleId].stop()
			for inputInstanceId in self.globalInputs:
				self.globalInputs[inputInstanceId].stop()
			app.inputManager.unRegisterInputs('main')
			app.dataChannelManager.stop()
			time.sleep(0.5)
		self.sculptureConfig = False
		self.sculptureModules = {}
		self.globalInputs = {}
		app.messenger.doReset()

	def loadSculpture(self, sculptureId):
		self.doReset()
		self.sculptureConfig = deepcopy(self.sculptureDefinitions[sculptureId])
		app.dataChannelManager = DataChannelManager(self.sculptureConfig)
		app.inputManager = InputManager()
		self.currentSculptureId = sculptureId
		for moduleId in self.sculptureConfig['modules']:
			moduleConfig = self.sculptureConfig['modules'][moduleId]
			moduleConfig['moduleId'] = moduleId
			sculptureModuleClass = getattr(SculptureModules, moduleConfig['moduleType'] + 'Module')
			self.sculptureModules[moduleId] = sculptureModuleClass(moduleConfig)

	def setInputValue(self, inputInstanceId, *args):
		inputObj = app.inputManager.getInputObj(inputInstanceId)
		inputObj.setInputValue(*args)

	def doCommand(self, command):
		logger.debug('doCommand(%s)', command)
		functionName = command[0]
		if functionName in self.methodList:
			command.pop(0)
			function = getattr(self, functionName)
			return function(*command)
		else:
			moduleId = command.pop(1)
			return self.sculptureModules[moduleId].doCommand(command)

	def getCurrentStateData(self):
		if self.sculptureConfig:
			data = self.sculptureConfig.copy()
			data['safeMode'] = app.safeMode.isSet()
			for moduleId in self.sculptureConfig['modules']:
				data['modules'][moduleId] = dict(self.sculptureConfig['modules'][moduleId], **self.sculptureModules[moduleId].getCurrentStateData())
			data = dict(data, **app.inputManager.getCurrentStateData())
			data['messenger'] = app.messenger.getCurrentStateData()
			data['adaptors'] = app.dataChannelManager.getCurrentStateData()
		else:
			data = {'sculptures' : {}}
			for sculptureId in self.sculptureDefinitions:
				data['sculptures'][sculptureId] = self.sculptureDefinitions[sculptureId]
		data['globalInputs'] = self.globalInputs.keys()
		data['availableGlobalInputs'] = self.availableGlobalInputs
		return data

	def addGlobalInput(self, inputParams):
		newInputId = app.inputManager.createNewInput(inputParams)
		self.globalInputs[newInputId] = app.inputManager.registerAndGetInput('main', newInputId)

	def removeGlobalInput(self, inputInstanceId):
		app.inputManager.unRegisterInputs('main', inputInstanceId)
		del self.globalInputs[inputInstanceId]

	def setSafeMode(self, value):
		app.safeMode.set(value)

	def updateSerialConnection(self, *args):
		return app.dataChannelManager.updateSerialConnection(*args)
