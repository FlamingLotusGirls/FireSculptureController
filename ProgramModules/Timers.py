"""Refreshable single/repeating timers, with cancellation and joined shutdown.

Keep the original countdown behavior: a new timer skips its first interval;
refresh wakes that skipped step immediately, then waits one full interval.
Changing the interval affects the next wait, without restarting the current wait.
"""
from __future__ import annotations
from typing import ClassVar
from .Types import Callback

from threading import Event, Lock, Thread, current_thread

from .Runtime import runCallback, synchronized


class Timer:
	activeTimers: ClassVar[set[Timer]] = set()
	registryLock = Lock()

	class TimerThread(Thread):
		def __init__(self, parent: Timer) -> None:
			Thread.__init__(self, name='timer-' + parent.function.__name__)
			self.parent = parent

		def run(self) -> None:
			try:
				while not self.parent.stopEvent.is_set():
					self.parent.waitEvent.wait(self.parent.interval / 1000.0)
					runCallback(self.parent.stopEvent, self.parent.doFunction)
			finally:
				with Timer.registryLock:
					Timer.activeTimers.discard(self.parent)

	def __init__(self, repeating: bool, interval: float, function: Callback,
		args = False, stopWhenDone: bool = False) -> None:
		self.repeating = repeating
		self.interval = interval
		self.function = function
		self.args = args
		self.stopWhenDone = stopWhenDone
		self.stopEvent = Event()
		self.waitEvent = Event()
		self.functionQueue = 1
		self.thread = Timer.TimerThread(self)
		with Timer.registryLock:
			Timer.activeTimers.add(self)
		try:
			self.thread.start()
		except Exception:
			with Timer.registryLock:
				Timer.activeTimers.discard(self)
			raise

	def requestStop(self) -> None:
		self.stopEvent.set()
		self.waitEvent.set()

	def stop(self) -> None:
		self.requestStop()
		if current_thread() is not self.thread:
			self.thread.join()

	def is_alive(self) -> bool:
		return self.thread.is_alive()

	@classmethod
	def stopAll(cls) -> None:
		# Also catches timers created by an object whose construction failed.
		with cls.registryLock:
			timers = list(cls.activeTimers)
		for timer in timers:
			timer.requestStop()
		for timer in timers:
			timer.stop()

	@synchronized
	def refresh(self) -> None:
		if not self.stopEvent.is_set():
			self.functionQueue = 1
			self.waitEvent.set()

	@synchronized
	def changeInterval(self, interval: float) -> None:
		self.interval = interval

	def doFunction(self) -> None:
		# Called under engineLock. Consume refresh notifications here, so a refresh
		# while waiting for that lock cannot cause an immediate extra callback.
		self.waitEvent.clear()
		if self.stopEvent.is_set():
			return
		if self.functionQueue == 0 or (self.repeating and self.functionQueue < 1):
			if self.args:
				self.function(*self.args)
			else:
				self.function()
			if self.stopWhenDone:
				self.stop()
		if self.functionQueue > -1:
			self.functionQueue -= 1
