"""Safe-mode state and callbacks, serialized with command formatting and serial writes."""
from __future__ import annotations
from .Types import Callback

import logging
from threading import RLock
from .Runtime import synchronized

logger = logging.getLogger(__name__)


class SafeModeController:
	def __init__(self) -> None:
		self.safeMode = True
		self.generation = 0
		self.bindings: list = []
		self.lock = RLock()

	def isSet(self) -> bool:
		with self.lock:
			return self.safeMode

	@synchronized
	def set(self, value: object) -> None:
		with self.lock:
			self.safeMode = bool(value)
			if self.safeMode:
				self.generation += 1
				firstError: Exception | None = None
				for function, args in list(self.bindings):
					try:
						if args:
							function(*args)
						else:
							function()
					except Exception as error:
						# An engine callback must not prevent cancellation of pending output.
						logger.exception('Safe-mode callback failed')
						if firstError is None:
							firstError = error
				if firstError is not None:
					raise firstError

	def addBinding(self, function: Callback, args = False):
		with self.lock:
			binding = [function, args]
			self.bindings.append(binding)
			return binding

	def removeBinding(self, binding) -> None:
		with self.lock:
			if binding in self.bindings:
				self.bindings.remove(binding)

	def clearBindings(self) -> None:
		with self.lock:
			self.bindings.clear()
