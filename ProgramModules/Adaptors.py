"""Physical serial connections. The writer owns reconnects and delivery recovery."""
from __future__ import annotations
from typing import TYPE_CHECKING, cast
from serial.serialutil import SerialBase
from .Types import AdaptorConfig, AdaptorUpdate
from .SerialPorts import resolveSerialIdentity, settingsForPort

import logging
from threading import RLock

import serial
from . import utils

logger = logging.getLogger(__name__)


class SerialAdaptor:
	WRITE_TIMEOUT = 0.25

	def __init__(self, configData: AdaptorConfig) -> None:
		self.configData = cast(AdaptorConfig, dict(configData))
		self.configData['baudrate'] = int(self.configData['baudrate'])
		self.connection: SerialBase | None = None
		self.lastError: str | None = None
		self.lock = RLock()
		self.stopped = False
		self.connect()

	def transmitData(self, data: bytes) -> bool:
		if not isinstance(data, bytes):
			raise TypeError('Serial data must be bytes')
		with self.lock:
			if self.stopped or self.connection is None:
				return False
			try:
				logger.debug('Sending serial data: %r', data)
				if self.connection.write(data) != len(data):
					raise serial.SerialTimeoutException('Incomplete serial write')
			except (serial.SerialException, OSError) as error:
				self.lastError = str(error)
				logger.error('%s write failed: %s', self.configData['adaptorId'], error)
				self._closeConnection()
				return False
			self.lastError = None
			return True

	def connect(self) -> bool:
		with self.lock:
			if self.stopped:
				return False
			self._closeConnection()
			ports = self.configData['ports']
			if self.configData.get('identity'):
				try:
					ports = [resolveSerialIdentity(cast(dict, self.configData['identity']))]
				except OSError as error:
					self.lastError = str(error)
					return False
			for port in ports:
				try:
					self.connection = serial.serial_for_url(
						port, cast(int, self.configData['baudrate']), timeout=0.1,
						write_timeout=self.WRITE_TIMEOUT)
				except (serial.SerialException, OSError) as error:
					self.lastError = str(error)
					logger.warning('%s cannot connect to %s: %s', self.configData['adaptorId'], port, error)
				else:
					self.configData['ports'] = [port] if self.configData.get('identity') else self.configData['ports']
					self.lastError = None
					logger.info('%s connected to %s at %s baud', self.configData['adaptorId'], port, self.configData['baudrate'])
					return True
			return False

	def updateSerialConnection(self, data: AdaptorUpdate) -> bool:
		with self.lock:
			data = cast(AdaptorUpdate, dict(data))
			if 'ports' in data:
				# Derive hardware identity on the controller, not in the browser.
				data['identity'] = None
				if len(data['ports']) == 1:
					try:
						data.update(settingsForPort(data['ports'][0]))
					except OSError:
						pass  # Explicit paths still work if enumeration is unavailable.
			config = utils.extendSettings(self.configData, data)
			config['baudrate'] = int(config['baudrate'])
			self.configData = config
			return self.connect()

	def _closeConnection(self) -> None:
		if self.connection is not None:
			try:
				self.connection.close()
			except (serial.SerialException, OSError) as error:
				logger.warning('%s close failed: %s', self.configData['adaptorId'], error)
			finally:
				self.connection = None

	def stop(self) -> None:
		with self.lock:
			self.stopped = True
			self._closeConnection()

	def getCurrentStateData(self):
		with self.lock:
			data = dict(self.configData)
			data['connected'] = self.connection is not None and self.connection.is_open
			data['lastError'] = self.lastError
			return data


if TYPE_CHECKING:
	from .Interfaces import Adaptor
	_adaptorClass: type[Adaptor] = SerialAdaptor
