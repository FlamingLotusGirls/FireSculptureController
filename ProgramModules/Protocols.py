''' Protocols take data from the program and convert it into a specific language for talking to the sculpture, then sends it over an adaptor. They are constructed with
an adaptor instance, so each one has all the "stuff" for talking to the sculpture. Protocols to be added: Soma, OpenPixel, Tympani LED, Serpent LED, Helyx maybe, motor contollers
To send data, each takes a command like [ (address, data), (address2, data2), ...].
'''

import logging

import ProgramModules.sharedObjects as app

logger = logging.getLogger(__name__)


class ProtocolBase():
	def __init__(self, adaptorObj, configParams):
		self.adaptorObj = adaptorObj
		self.configParams = configParams
		self.dataCache = ''
		self.ignoreSafeMode = False
		if 'ignoreSafeMode' in self.configParams.keys() and self.configParams['ignoreSafeMode']:
			self.ignoreSafeMode = True
		if isinstance(self.configParams['mapping'], dict):
			self.translateAddr = self.translateDictAddr
		elif isinstance(self.configParams['mapping'], list):
			if isinstance(self.configParams['mapping'][0][0], list):
				self.translateAddr = self.translateTwoDimensionalListAddr
			else:
				self.translateAddr = self.translateOneDimensionalListAddr
	def transmitData(self):
		if self.adaptorObj.transmitData(self.dataCache):
			self.dataCache = ''
	def send(self, data):
		for command in data:
			self.dataCache += self.formatData(self.translateAddr(command[0]), command[1])
		if self.dataCache:
			self.transmitData()

	def translateDictAddr(self, addr):
		return self.configParams['mapping'][addr]

	def translateOneDimensionalListAddr(self, addr):
		return self.configParams['mapping'][addr]

	def translateTwoDimensionalListAddr(self, addr):
		return self.configParams['mapping'][addr[0]][addr[1]]


class FlgRelayProtocol(ProtocolBase): #Poofer relay boards used on Serpent, Angel, Tympani, Mutopia
	def formatData(self, addr, data):
		if (data in [True, '1', 1]) and ((not app.safeMode.isSet()) or self.ignoreSafeMode):
			cmd = '1'
		else:
			cmd = '0'
		return "!%02X%s%s." %(addr[0], addr[1], cmd)

class TympaniLedProtocol(ProtocolBase): #Tympani Mobius Leds
	def formatData(self, addr, data):
		return "!%02X%02X%02X." %(addr[0], addr[1], int(data))


class SerpentMotherLedProtocol(ProtocolBase):
	"""Protocol for the Serpent Mother LEDs."""

	def formatData(self, addr, data):
		logger.debug('sending %s to %s', data, addr)
		# TODO: implement format. Currently only a mock.
		return ""
