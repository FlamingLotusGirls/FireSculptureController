"""Safe-mode state and callbacks, serialized with command formatting and serial writes."""
import logging
from threading import RLock
from .Runtime import synchronized

logger = logging.getLogger(__name__)


class SafeModeController:
	def __init__(self):
		self.safeMode = True
		self.generation = 0
		self.bindings = []
		self.lock = RLock()

	def isSet(self):
		with self.lock:
			return self.safeMode

	@synchronized
	def set(self, value):
		with self.lock:
			self.safeMode = bool(value)
			if self.safeMode:
				self.generation += 1
				firstError = None
				for function, args in list(self.bindings):
					try:
						if args:
							function(*args)
						else:
							function()
					except Exception as error:
						# An engine callback must not prevent the transport's all-OFF callback.
						logger.exception('Safe-mode callback failed')
						if firstError is None:
							firstError = error
				if firstError is not None:
					raise firstError

	def addBinding(self, function, args=False):
		with self.lock:
			binding = [function, args]
			self.bindings.append(binding)
			return binding

	def removeBinding(self, binding):
		with self.lock:
			if binding in self.bindings:
				self.bindings.remove(binding)

	def clearBindings(self):
		with self.lock:
			self.bindings.clear()
