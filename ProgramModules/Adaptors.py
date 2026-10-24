''' Adaptors specify the interface to the hardware such as a serial bus, ethernet, or a dummy interface. They 
take the params needed to open the connection, send the already processed data over the connection,
(eventually) recieve data, and make sure it stays connected. '''
import logging
import serial
from . import utils

import ProgramModules.sharedObjects as app

logger = logging.getLogger(__name__)


class SerialAdaptor():
	def __init__ (self, configData):
		self.configData = configData
		self.connection = False
		self.connect()

	def transmitData(self, data):
		success = True
		logger.debug('Sending serial data: %r', data)
		try:
			self.connection.write(data)
		except:
			self.connect()
			try:
				self.connection.write(data)
			except:
				app.messenger.putMessage('log', '%s failure sending data' %(self.configData['adaptorId']))
				success = False
		return success
	def connect(self):
		if self.connection:
			self.connection.close()
			self.connection = False
		portIndex = 0
		while (not self.connection) and portIndex < len(self.configData['ports']):
			try:
				self.connection = serial.Serial(self.configData['ports'][portIndex], self.configData['baudrate'], timeout=0.1)
				app.messenger.putMessage('log', '%s connected on %s at baudrate %s' %(self.configData['adaptorId'], self.configData['ports'][portIndex], self.configData['baudrate']))
			except Exception as e:
				app.messenger.putMessage('log', '%s failed to connect on %s at baudrate %s' %(self.configData['adaptorId'], self.configData['ports'][portIndex], self.configData['baudrate']))
				app.messenger.putMessage('log', str(e))
				portIndex += 1
				
	def updateSerialConnection(self, data):
		self.configData = utils.extendSettings(self.configData, data)
		self.connect()
		
	def stop(self):
		if self.connection:
			self.connection.close()
		self.connection = False
		
	def getCurrentStateData(self):
		data = self.configData.copy()
		if self.connection:
			data['connected'] = True
		else:
			data['connected'] = False
		return data
			
