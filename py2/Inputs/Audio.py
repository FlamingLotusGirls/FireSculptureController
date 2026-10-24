''' Grabbed from Angel Audiopoof. Could probably be made less janky.
''' 
from InputBase import InputBase

from threading import Thread, Event
import time
import sys
import struct


inputTypes = {
	'audio pulse' : {
		'longDescription' : 'Audio responsive pulse input',
		'shortDescription' : 'Audio Pulse',
		'inParams' : [{'type' : 'value', 'description' : 'Threshold', 'default' : 1000, 'min' : 1000, 'max' : 10000}],
		'outParams' : [{'type' : 'pulse', 'sendMessageOnChange' : True}],
		'hasOwnClass' : True
	}
}

	
try:
	import pyaudio
	import numpy 
except:
	inputTypes['audio pulse']['unavailable'] = True

class AudioPulseInput(InputBase):
	class AudioInputThread(Thread):
		def __init__(self, parent, stopEvent, callBackFunction, configParams = {'chunk' : 1024, 'channels' : 1, 'rate' : 22500, 'recordSeconds' : 5}):
			Thread.__init__(self)
			configParams['format'] = pyaudio.paInt16
			self.configParams = configParams
			self.callBackFunction = callBackFunction
			self.p=pyaudio.PyAudio()
			self.stopEvent = stopEvent
			self.stream = self.p.open(
				format = configParams['format'],
				channels = configParams['channels'], 
				rate = configParams['rate'], 
				input = True,
				output = True
			)
			csum = []
			spectlen = configParams['rate'] / configParams['chunk'] * configParams['recordSeconds']
			self.makebands(configParams['chunk']/2)
			self.bmax=0
			self.gain = 1.0
			self.skip =8            # skip this many windows

		def setgain(self,intgain):
				self.gain = 2*intgain/100.0

		def makebands(self,max):
				"make a set of power-of-two bands. Max must be power of 2"
				self.bands = []
				self.scale = []
				while max > 2:
						self.bands.append(range(max/2, max))
						self.scale.append(max)
						max = max/2
				self.bands[-1] = range(0,4)
				self.bands.reverse()
				self.scale.reverse()

		def run(self):
			i = 0
			while not self.stopEvent.isSet():
				i += 1
				try:
					data = self.stream.read(self.configParams['chunk'])
				except Exception as e: # HO HUM!
					data = False
					time.sleep(0.01)
				if i>2 and data:
					i = 0
					buff = numpy.array(struct.unpack_from('1024h',data))
					bdata = range(len(self.bands))    
					self.callBackFunction(bands=bdata, value = buff.std())
					time.sleep(0.01)

		def stop(self):
			sys.stdout.flush()
			self.stopEvent.set()
			self.stream.stop_stream()
			self.stream.close()
			self.p.terminate()

	def __init__(self, *args):
		InputBase.__init__(self, *args)
		self.audioThread = AudioPulseInput.AudioInputThread(self, Event(), self.handleAudioUpdate)
		self.audioThread.start()
		
	def stop(self):
		self.audioThread.stop()
		InputBase.stop(self)

	def handleAudioUpdate(self, bands, value):
		if (value > self.inParams[0].getValue()):
			self.outParams[0].setValue(True)
	

