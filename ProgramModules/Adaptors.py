''' Adaptors specify the interface to the hardware such as a serial bus, ethernet, or a dummy interface. They 
take the params needed to open the connection, send the already processed data over the connection,
(eventually) recieve data, and make sure it stays connected. '''

from random import randint
import utils
class SerialAdaptor():
	import serial
	def __init__ (self, configData):
		self.configData = configData
		self.connect()
	def transmitData(self, data):
		success = True
		try:
			self.connection.write(data)
		except:
			self.connect()
			try:
				self.connection.write(data)
			except:
				appMessenger.putMessage('log', '%s failure sending data' %(self.configData['adaptorId']))
				print data
				# print 'ser' + str(randint(0, 20))
				#success = False
		return success
	def connect(self):
		self.connection = False
		portIndex = 0
		while (not self.connection) and portIndex < len(self.configData['ports']):
			try:
				self.connection = serial.Serial(self.configData['ports'][portIndex], self.configData['baudrate'], timeout=0.1)
				appMessenger.putMessage('log', '%s connected on %s at baudrate %s' %(self.configData['adaptorId'], self.configData['ports'][portIndex], self.configData['baudrate']))
			except:
				appMessenger.putMessage('log', '%s failed to connect on %s at baudrate %s' %(self.configData['adaptorId'], self.configData['ports'][portIndex], self.configData['baudrate']))
				portIndex += 1
				
	def updateSerialConnection(self, data):
		self.configData = utils.extendSettings(self.configData, data)
		self.connect()
		
	def stop(self):
		self.connection = False
			
