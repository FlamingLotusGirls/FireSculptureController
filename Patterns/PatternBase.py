
from __future__ import annotations
from collections.abc import Callable
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
	from ProgramModules.InputManager import InputCollection

import ProgramModules.sharedObjects as app


class PatternBase():
	inputParams: dict

	def __init__(self, gridSize: list[int], instanceId: str) -> None:
		self.gridSize = gridSize
		# Callbacks and inputs are installed before use; retain False when absent or stopped.
		self.requestUpdate = cast(Callable[[], None], False)
		self.patternName = ''
		self.instanceId = instanceId
		try:
			self.inputParams
		except:
			self.inputs = cast('InputCollection', False)
		else:
			self.inputs = app.inputManager.buildInputCollection(self, self.inputParams)

	def reassignInput(self, *args) -> None:
		self.inputs.reassignInput(*args)


	def stop(self) -> None:
		self.inputs.stop()
		self.requestUpdate = cast(Callable[[], None], False)
		self.inputs = cast('InputCollection', False)


	def getCurrentStateData(self):
		return({'name' : self.patternName, 'inputs' : self.inputs.getCurrentStateData()})

	def getPersistentState(self) -> dict:
		return {}

	def restorePersistentState(self, state: dict) -> None:
		pass
	

	def setUpdateFunction(self, function: Callable[[], None]) -> None:
		self.requestUpdate = function


	def getId(self) -> str:
		return self.instanceId
