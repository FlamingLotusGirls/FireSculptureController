''' Creates instances of adaptor and protocol objects and passes data to them
One instance of this in the program seems to make more sense than one instance per module for now,
due to adaptors needing to serve multiple data channels in some cases
'''
from threading import Thread, Event
import Protocols
import Adaptors


class DataChannelManager():
	class AdaptorThread(Thread):
		def __init__(self, adaptor):
			Thread.__init__(self)
			self.adaptor = adaptor
			self.data = ''
			self.stopEvent = Event()
		
		def run(self):
			while not self.stopEvent.isSet():
				if not self.data == '':
					self.adaptor.transmitData(self.data)
					self.data = ''
		
		def transmitData(self, data):
			self.data += data
			return True
		
		def __getattr__(self, attr):
			return getattr(self.adaptor, attr)

		def stop(self):
			self.adaptor.stop()
			self.stopEvent.set()
		
	def __init__(self, sculptureConfigData):
		self.adaptors = {}
		self.dataChannels = {}
		for adaptorId in sculptureConfigData['adaptors']:
			adaptorConfig = sculptureConfigData['adaptors'][adaptorId]
			adaptorConfig['adaptorId'] = adaptorId
			adaptorClassName = adaptorConfig['type'][0].upper() + adaptorConfig['type'][1:] + 'Adaptor'
			adaptorClass = getattr(Adaptors, adaptorClassName)
			self.adaptors[adaptorId] = DataChannelManager.AdaptorThread(adaptorClass(adaptorConfig))
			self.adaptors[adaptorId].start()
		for moduleId in sculptureConfigData['modules']:
			moduleConfig = sculptureConfigData['modules'][moduleId]
			protocolClassName = moduleConfig['protocol']['type'][0].upper() + moduleConfig['protocol']['type'][1:] + 'Protocol'
			protocolClass = getattr(Protocols, protocolClassName)
			self.dataChannels[moduleId] = protocolClass(self.adaptors[moduleConfig['adaptor']], moduleConfig['protocol'])
	def send(self, moduleId, *args):
		return self.dataChannels[moduleId].send(*args)
		
	def stop(self):
		for adaptorId in self.adaptors:
			self.adaptors[adaptorId].stop()
			
	def updateSerialConnection(self, adaptorId, data):
		return self.adaptors[adaptorId].updateSerialConnection(data)


	def getCurrentStateData(self):
		return {adaptorId : self.adaptors[adaptorId].getCurrentStateData() for adaptorId in self.adaptors}
			
	