''' Protocols take data from the program and convert it into a specific language for talking to the sculpture, then sends it over an adaptor. They are constructed with
an adaptor instance, so each one has all the "stuff" for talking to the sculpture. Protocols to be added: Soma, OpenPixel, Tympani LED, Serpent LED, Helyx maybe, motor contollers
To send data, each takes a command like [ (address, data), (address2, data2), ...].
'''
from __future__ import annotations
from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING, cast
from .Interfaces import Adaptor, ProtocolEncoder
from .Types import (
	AddressKey, GridAddress, HardwareAddress, LogicalAddress, OutputCommands,
	OutputValue, ProtocolConfig,
)


import logging

import ProgramModules.sharedObjects as app

logger = logging.getLogger(__name__)


class ProtocolBase():
	translateAddr: Callable[[LogicalAddress], HardwareAddress]

	def __init__(self, adaptorObj: Adaptor | None, configParams: ProtocolConfig) -> None:
		self.adaptorObj = adaptorObj
		self.configParams = configParams
		self.dataCache = b""
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
	def transmitData(self) -> bool:
		# This helper is synchronous; the manager owns queued delivery and retries.
		data = self.dataCache
		self.dataCache = b""
		# Only the synchronous path has an adaptor; the manager uses this as an encoder.
		return cast(Adaptor, self.adaptorObj).transmitData(data)

	def send(self, data: OutputCommands) -> bool:
		with app.safeMode.lock:
			self.dataCache = self.formatCommands(data)
			if self.dataCache:
				return self.transmitData()
			return True

	def formatCommands(self, data: OutputCommands) -> bytes:
		# Concrete protocols supply formatData; the base has no runtime fallback method.
		encoder = cast(ProtocolEncoder, self)
		return b"".join(encoder.formatData(self.translateAddr(address), value) for address, value in data)

	def addresses(self) -> Iterator[AddressKey]:
		"""Yield logical addresses in the same order used by the sculpture module."""
		mapping = self.configParams['mapping']
		if isinstance(mapping, dict):
			yield from mapping
		elif isinstance(mapping[0][0], list):
			for row, entries in enumerate(mapping):
				for col in range(len(entries)):
					yield (row, col)
		else:
			yield from range(len(mapping))

	def allOff(self) -> bytes:
		return self.formatCommands((address, False) for address in self.addresses())

	def translateDictAddr(self, addr: LogicalAddress) -> HardwareAddress:
		mapping = cast(dict[str, HardwareAddress], self.configParams['mapping'])
		return mapping[cast(str, addr)]

	def translateOneDimensionalListAddr(self, addr: LogicalAddress) -> HardwareAddress:
		mapping = cast(list[HardwareAddress], self.configParams['mapping'])
		return mapping[cast(int, addr)]

	def translateTwoDimensionalListAddr(self, addr: LogicalAddress) -> HardwareAddress:
		mapping = cast(list[list[HardwareAddress]], self.configParams['mapping'])
		position = cast(GridAddress, addr)
		return mapping[position[0]][position[1]]


class FlgRelayProtocol(ProtocolBase): #Poofer relay boards used on Serpent, Angel, Tympani, Mutopia
	def formatData(self, addr: HardwareAddress, data: OutputValue) -> bytes:
		if (data in [True, '1', 1]) and ((not app.safeMode.isSet()) or self.ignoreSafeMode):
			cmd = '1'
		else:
			cmd = '0'
		return ("!%02X%s%s." %(addr[0], addr[1], cmd)).encode("ascii")

class TympaniLedProtocol(ProtocolBase): #Tympani Mobius Leds
	def formatData(self, addr: HardwareAddress, data: OutputValue) -> bytes:
		# Tympani consumes scalar controls; RGB values belong to the Serpent LED path.
		return ("!%02X%02X%02X." %(addr[0], addr[1], int(cast(int | float | str, data)))).encode("ascii")


class SerpentMotherLedProtocol(ProtocolBase):
	"""Protocol for the Serpent Mother LEDs."""

	def formatData(self, addr: HardwareAddress, data: OutputValue) -> bytes:
		logger.debug('sending %s to %s', data, addr)
		# TODO: implement format. Currently only a mock.
		return b""


if TYPE_CHECKING:
	_protocolClasses: tuple[type[ProtocolEncoder], ...] = (
		FlgRelayProtocol, TympaniLedProtocol, SerpentMotherLedProtocol,
	)
