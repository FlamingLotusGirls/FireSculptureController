from __future__ import annotations
from collections.abc import Callable
from typing import Literal, cast
from ProgramModules.Interfaces import Input, SculptureModule
from ProgramModules.Types import SculptureConfig

import inspect
import json
import logging
import os
from copy import deepcopy
from pathlib import Path

from ProgramModules.DataChannelManager import DataChannelManager
from ProgramModules.InputManager import InputManager
from ProgramModules import SculptureModules
from ProgramModules.Runtime import callbackContext, synchronized
from ProgramModules.Timers import Timer
from ProgramModules.SettingsStore import SettingsStore
from ProgramModules.SerialPorts import discoverSerialPorts
import ProgramModules.sharedObjects as app
import Inputs

logger = logging.getLogger(__name__)


class ControllerStopped(RuntimeError):
	pass


class SculptureController:
	@synchronized
	def __init__(self) -> None:
		root = Path(__file__).resolve().parent
		self.settingsStore = SettingsStore(Path(os.environ.get('FIRESCULPTURE_STATE_DIR', str(root / 'state'))))
		self.settingsError: str | None = None
		self.sculptureDefinitions: dict[str, SculptureConfig] = {}
		self.sculptureModules: dict[str, SculptureModule] = {}
		self.globalInputs: dict[int, Input] = {}
		self.availableGlobalInputs = []
		self.sculptureConfig: SculptureConfig | Literal[False] = False
		self.inputManager: InputManager | None = None
		self.dataChannelManager: DataChannelManager | None = None
		self.stopped = False
		self.shutdownComplete = True
		for inputType in [['multi', 'osc'], ['multi', 'basic']]:
			if 'unavailable' not in Inputs.inputTypes[' '.join([inputType[1], inputType[0]])]:
				self.availableGlobalInputs.append(inputType)
		for path in sorted((root / 'sculptureDefinitions').glob('*.json')):
			with path.open(encoding='utf-8') as source:
				definition: SculptureConfig = json.load(source)
			self.sculptureDefinitions[definition['sculptureId']] = definition
		with (root / 'config.json').open(encoding='utf-8') as source:
			self.globalConfig = json.load(source)
		self.availableInputs: dict = {}
		self.methodList = [name for name, method in inspect.getmembers(self, predicate=inspect.ismethod)
			if not name.startswith('_')]
		self.doReset()

	def _reset(self) -> bool:
		if getattr(callbackContext, 'active', False):
			raise RuntimeError('Reset or reload the controller outside a timer/OSC callback')
		# engineLock has stopped new commands/callbacks. Keep it held through cleanup;
		# cancelled workers can leave their lock wait and be joined safely.
		errors = []
		def cleanup(function: Callable[[], object]) -> object:
			try:
				return function()
			except Exception as error:
				logger.exception('Cleanup failed in %s', function.__name__)
				errors.append(error)
				return None

		cleanup(lambda: app.safeMode.set(True))
		for module in list(self.sculptureModules.values()):
			cleanup(module.stop)
		if self.inputManager is not None:
			cleanup(self.inputManager.stop)
		cleanup(Timer.stopAll)
		delivered = True
		if self.dataChannelManager is not None:
			delivered = cleanup(self.dataChannelManager.stop) is not False
		if errors:
			# Do not replace managers when cleanup failed; another stop may retry it.
			raise RuntimeError('Controller cleanup failed') from errors[0]
		app.safeMode.clearBindings()
		app.messenger.doReset()
		self.sculptureConfig = False
		self.sculptureModules = {}
		self.globalInputs = {}
		self.inputManager = None
		self.dataChannelManager = None
		return delivered

	@synchronized
	def doReset(self) -> bool:
		return self._reset()

	@synchronized
	def stop(self) -> bool:
		if self.stopped:
			return self.shutdownComplete
		self.stopped = True
		self.shutdownComplete = False
		try:
			self.shutdownComplete = self._reset()
		except Exception:
			self.stopped = False  # Allow another cleanup attempt.
			raise
		return self.shutdownComplete

	@synchronized
	def loadSculpture(self, sculptureId: str) -> None:
		if self.stopped:
			raise ControllerStopped('Controller has stopped')
		config = deepcopy(self.sculptureDefinitions[sculptureId])
		self.settingsError = None
		try:
			settings = self.settingsStore.load(sculptureId)
		except (OSError, ValueError) as error:
			settings = None
			self.settingsError = 'Could not load saved settings: ' + str(error)
			logger.error(self.settingsError)
		if settings:
			for adaptorId, saved in settings['adaptors'].items():
				if adaptorId in config['adaptors']:
					config['adaptors'][adaptorId].update(saved)
		self._reset()
		self.sculptureConfig = config

		def buildModules():
			self.dataChannelManager = DataChannelManager(config)
			app.dataChannelManager = self.dataChannelManager
			self.inputManager = InputManager()
			app.inputManager = self.inputManager
			self.currentSculptureId = sculptureId
			for moduleId, moduleConfig in config['modules'].items():
				# The GUI needs this ID in the loaded configuration returned by getData.
				moduleConfig['moduleId'] = moduleId
				moduleClass = getattr(SculptureModules, moduleConfig['moduleType'] + 'Module')
				self.sculptureModules[moduleId] = moduleClass(moduleConfig)

		try:
			buildModules()
			if settings:
				try:
					self._restoreSettings(settings)
				except (KeyError, ValueError, TypeError, IndexError, AttributeError) as error:
					# A removed pattern/input type must not leave a half-restored engine.
					self.settingsError = 'Could not restore saved patterns/inputs: ' + str(error)
					logger.error(self.settingsError)
					self._reset()
					self.sculptureConfig = config
					buildModules()
		except Exception:
			self._reset()
			raise

	@synchronized
	def setInputValue(self, inputInstanceId: int, *args) -> None:
		# Input and serial commands require a loaded sculpture; keep that existing contract.
		cast(InputManager, self.inputManager).getInputObj(inputInstanceId).setInputValue(*args)

	@synchronized
	def doCommand(self, command):
		if self.stopped:
			raise ControllerStopped('Controller has stopped')
		if not isinstance(command, list) or not command or not isinstance(command[0], str):
			raise ValueError('Expected a non-empty command list')
		command = list(command)
		logger.debug('doCommand(%s)', command)
		functionName = command[0]
		if functionName in self.methodList:
			# Method names and argument lists come from GUI commands.
			result = getattr(self, functionName)(*command[1:])
		else:
			moduleId = command.pop(1)
			result = self.sculptureModules[moduleId].doCommand(command)
		if functionName in {'updateSerialConnection', 'addPattern', 'removePattern',
			'toggleRowSelection', 'toggleEnable', 'reassignPatternInput',
			'reassignPatternInputToNew', 'reassignModuleInput', 'reassignModuleInputToNew',
			'addGlobalInput', 'removeGlobalInput', 'setInputValue'}:
			self._saveSettings()
		return result

	def _saveSettings(self) -> None:
		if not self.sculptureConfig:
			return
		manager = cast(InputManager, self.inputManager)
		settings: dict = {'version': 1, 'adaptors': {}, 'modules': {}, 'inputs': {},
			'globalInputs': list(self.globalInputs)}
		for adaptorId, adaptor in cast(DataChannelManager, self.dataChannelManager).getCurrentStateData().items():
			settings['adaptors'][adaptorId] = {key: deepcopy(adaptor[key])
				for key in ('ports', 'baudrate', 'identity') if key in adaptor}
		for inputId, inputObj in manager.inputInstances.items():
			settings['inputs'][inputId] = {'params': manager.inputDefinitions[inputId],
				'values': [param['currentValue'] if param['type'] != 'pulse' else None
					for param in inputObj.getCurrentStateData()['inParams']]}
		for moduleId, module in self.sculptureModules.items():
			if isinstance(module, SculptureModules.GridPatternModule):
				settings['modules'][moduleId] = {'enabledStatus': module.enabledStatus, 'patterns': [
					{'type': module.patternTypes[patternId], 'rowSettings': module.patternRowSettings[patternId],
					 'inputs': pattern.getCurrentStateData()['inputs'], 'state': pattern.getPersistentState()}
					for patternId, pattern in module.patterns.items()]}
			elif isinstance(module, SculptureModules.InputOnlyModule):
				settings['modules'][moduleId] = {'inputs': module.inputs.getCurrentStateData()}
		try:
			self.settingsStore.save(self.currentSculptureId, settings)
		except OSError as error:
			self.settingsError = 'Changes are active but could not be saved: ' + str(error)
			logger.error(self.settingsError)
		else:
			self.settingsError = None

	def _restoreSettings(self, settings: dict) -> None:
		manager = cast(InputManager, self.inputManager)
		inputIds = {}
		for savedId, saved in settings['inputs'].items():
			inputId = manager.createNewInput(saved['params'])
			if inputId is False:
				raise ValueError('Saved input type is unavailable')
			inputIds[str(savedId)] = inputId
			# Restore switches after installing bindings, so their change callbacks run.
			inputObj = manager.getInputObj(inputId)
			for index, param in enumerate(inputObj.getCurrentStateData()['inParams']):
				if param['type'] == 'toggle':
					inputObj.setInputValue(False, index)
		for savedId in settings['globalInputs']:
			inputId = inputIds[str(savedId)]
			self.globalInputs[inputId] = manager.registerAndGetInput('main', inputId)

		def rebind(collection, assignments):
			for channel, assignment in assignments.items():
				collection.reassignInput(channel, inputIds[str(assignment['inputInstanceId'])], assignment['outParamIndex'])

		for moduleId, saved in settings['modules'].items():
			module = self.sculptureModules.get(moduleId)
			if isinstance(module, SculptureModules.GridPatternModule):
				if 'enabledStatus' in saved and [len(row) for row in saved['enabledStatus']] == [len(row) for row in module.enabledStatus]:
					module.enabledStatus = deepcopy(saved['enabledStatus'])
				for patternSettings in saved.get('patterns', []):
					patternId = module.addPattern(patternSettings['type'])
					pattern = module.patterns[patternId]
					if len(patternSettings['rowSettings']) == module.gridSize[0]:
						module.patternRowSettings[patternId] = list(patternSettings['rowSettings'])
					rebind(pattern.inputs, patternSettings['inputs'])
					pattern.restorePersistentState(patternSettings.get('state', {}))
			elif isinstance(module, SculptureModules.InputOnlyModule):
				rebind(module.inputs, saved['inputs'])
		for savedId, saved in settings['inputs'].items():
			inputObj = manager.getInputObj(inputIds[str(savedId)])
			for index, value in enumerate(saved['values']):
				if value is not None:
					inputObj.setInputValue(value, index)

	@synchronized
	def getCurrentStateData(self):
		if self.sculptureConfig:
			data = deepcopy(self.sculptureConfig)
			data['safeMode'] = app.safeMode.isSet()
			for moduleId, module in self.sculptureModules.items():
				data['modules'][moduleId].update(module.getCurrentStateData())
			data.update(cast(InputManager, self.inputManager).getCurrentStateData())
			data['messenger'] = app.messenger.getCurrentStateData()
			data['adaptors'] = cast(DataChannelManager, self.dataChannelManager).getCurrentStateData()
		else:
			data = {'sculptures': self.sculptureDefinitions}
		data['globalInputs'] = list(self.globalInputs)
		data['availableGlobalInputs'] = self.availableGlobalInputs
		data['settingsError'] = self.settingsError
		# JSON encoding happens after releasing the lock; return an independent snapshot.
		return deepcopy(data)

	@synchronized
	def getSerialPorts(self):
		try:
			return {'ports': discoverSerialPorts(), 'error': None}
		except OSError as error:
			return {'ports': [], 'error': 'Could not list serial ports: ' + str(error)}

	@synchronized
	def getConnectionStatus(self):
		connections = []
		if self.sculptureConfig and self.dataChannelManager:
			for adaptorId, adaptor in self.dataChannelManager.getCurrentStateData().items():
				modules = [module['name'] for module in self.sculptureConfig['modules'].values()
					if module['adaptor'] == adaptorId]
				connections.append(dict(adaptor, adaptorId=adaptorId, modules=modules))
		return {'connections': connections, 'safeMode': app.safeMode.isSet(),
			'settingsError': self.settingsError}

	@synchronized
	def addGlobalInput(self, inputParams) -> None:
		manager = cast(InputManager, self.inputManager)
		newInputId = manager.createNewInput(inputParams)
		self.globalInputs[newInputId] = manager.registerAndGetInput('main', newInputId)

	@synchronized
	def removeGlobalInput(self, inputInstanceId: int) -> None:
		cast(InputManager, self.inputManager).unRegisterInputs('main', inputInstanceId)
		del self.globalInputs[inputInstanceId]

	@synchronized
	def setSafeMode(self, value: object) -> None:
		app.safeMode.set(value)

	@synchronized
	def updateSerialConnection(self, *args) -> bool:
		return cast(DataChannelManager, self.dataChannelManager).updateSerialConnection(*args)
