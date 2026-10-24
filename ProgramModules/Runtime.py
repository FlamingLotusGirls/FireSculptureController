"""Serialize controller work without trapping stopped workers behind its lock."""
from functools import wraps
import logging
from threading import Event, RLock, local

logger = logging.getLogger(__name__)
engineLock = RLock()
failureEvent = Event()
callbackContext = local()


def synchronized(function):
	"""Use the same reentrant lock for HTTP commands, state reads, and callbacks."""
	@wraps(function)
	def locked(*args, **kwargs):
		with engineLock:
			return function(*args, **kwargs)
	return locked


def runCallback(stopEvent, function, *args):
	# A controller may hold engineLock while stopping this worker. Check cancellation
	# while waiting, so joining the worker cannot deadlock on that lock.
	while not stopEvent.is_set():
		if not engineLock.acquire(timeout=0.05):
			continue
		try:
			if not stopEvent.is_set():
				previous = getattr(callbackContext, 'active', False)
				callbackContext.active = True
				try:
					return function(*args)
				finally:
					callbackContext.active = previous
		except Exception:
			logger.exception('Controller callback failed; requesting shutdown')
			failureEvent.set()
			raise
		finally:
			engineLock.release()
