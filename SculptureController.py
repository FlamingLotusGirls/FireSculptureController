from __future__ import annotations
from collections.abc import Callable
from typing import Literal, cast
from ProgramModules.Interfaces import Input, SculptureModule
from ProgramModules.Types import ModuleConfig, SculptureConfig

import inspect
import json
import logging
from copy import deepcopy
from pathlib import Path

from ProgramModules.DataChannelManager import DataChannelManager
from ProgramModules.InputManager import InputManager
from ProgramModules import SculptureModules
from ProgramModules.Runtime import callbackContext, synchronized
from ProgramModules.Timers import Timer
import ProgramModules.sharedObjects as app
import Inputs

logger = logging.getLogger(__name__)


class ControllerStopped(RuntimeError):
	pass


class SculptureController:
	@synchronized
	def __init__(self) -> None:
		root = Path(__file__).resolve().parent
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
		self._reset()
		self.sculptureConfig = config
		try:
			self.dataChannelManager = DataChannelManager(config)
			app.dataChannelManager = self.dataChannelManager
			self.inputManager = InputManager()
			app.inputManager = self.inputManager
			self.currentSculptureId = sculptureId
			for moduleId, moduleConfig in config['modules'].items():
				moduleConfig = cast(ModuleConfig, dict(moduleConfig, moduleId=moduleId))
				moduleClass = getattr(SculptureModules, moduleConfig['moduleType'] + 'Module')
				self.sculptureModules[moduleId] = moduleClass(moduleConfig)
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
			return getattr(self, functionName)(*command[1:])
		moduleId = command.pop(1)
		return self.sculptureModules[moduleId].doCommand(command)

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
		# JSON encoding happens after releasing the lock; return an independent snapshot.
		return deepcopy(data)

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
