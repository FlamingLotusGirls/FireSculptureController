'''Timer object that calls a function after specified time. Can be repeating or single. Single timers
stick around and can be reset by default, but can also be set to stop their timer thread after the 
time is up.
''' 

from threading import Thread, Event
class Timer():
	class TimerThread(Thread):
		def __init__(self, parent):
			Thread.__init__(self)
			self.parent = parent
		def run(self):
			while not self.parent.stopEvent.is_set():
				self.parent.waitEvent.wait(self.parent.interval / 1000.)
				self.parent.doFunction()
		
	def __init__(self, repeating, interval, function, args = False, stopWhenDone = False):
		self.__dict__.update(locals())
		del self.self
		self.stopEvent = Event()
		self.waitEvent = Event()
		self.thread = Timer.TimerThread(self)
		self.functionQueue = 1
		self.thread.start()

	def stop(self):
		self.functionQueue = -1
		self.repeating = False
		self.waitEvent.set()
		self.stopEvent.set()
	
	
	def refresh(self):
		self.functionQueue = 1
		self.waitEvent.set()
		self.waitEvent.clear()
		
	def changeInterval(self, interval):
		self.interval = interval
		
	def doFunction(self):
		if self.functionQueue == 0 or (self.repeating and self.functionQueue < 1):
			if self.args:
				self.function(*self.args)
			else:
				self.function()
			if self.stopWhenDone:
				self.stop()
		if self.functionQueue > -1:
			self.functionQueue -= 1
