"""Encode module updates and deliver them through one blocking writer per serial bus.

Normal traffic preserves command order. Recovery replaces queued history with the most
recent state, so a failed OFF cannot be forgotten and old pulses are not replayed.
"""
from __future__ import annotations
from .Interfaces import Adaptor, ProtocolEncoder
from .Types import (
	AddressKey, AdaptorConfig, AdaptorUpdate, OutputCommands, SafeModeBinding,
	SculptureConfig, StateData,
)
from typing import cast

import logging
from dataclasses import dataclass
from queue import Empty, Full, Queue
from threading import Event, Thread
from time import monotonic

from . import Adaptors, Protocols
import ProgramModules.sharedObjects as app

logger = logging.getLogger(__name__)


@dataclass
class PendingWrite:
	moduleId: str
	generation: int
	safeGeneration: int
	data: bytes
	created: float


class ChannelState:
	def __init__(self, protocol: ProtocolEncoder) -> None:
		self.protocol = protocol
		self.protected = isinstance(protocol, Protocols.FlgRelayProtocol) and not protocol.ignoreSafeMode
		self.generation = 0
		self.values: dict[AddressKey, bytes] = {}
		if self.protected:
			self.setOff()

	def setOff(self) -> None:
		self.values = {
			address: self.protocol.formatData(self.protocol.translateAddr(address), False)
			for address in self.protocol.addresses()
		}

	def snapshot(self) -> bytes:
		return b"".join(self.values.values())


class AdaptorThread(Thread):
	QUEUE_LIMIT = 128
	MAX_QUEUE_AGE = 0.25
	RETRY_INTERVAL = 0.25

	def __init__(self, adaptor: Adaptor) -> None:
		super().__init__(name='serial-' + adaptor.configData['adaptorId'])
		self.adaptor = adaptor
		self.channels: dict[str, ChannelState] = {}
		self.queue: Queue[PendingWrite | None] = Queue(maxsize=self.QUEUE_LIMIT)
		self.offPending: dict[str, bytes] = {}
		self.needsResync = False
		self.needsConnect = False
		self.accepting = True
		self.stopEvent = Event()
		self.idleEvent = Event()
		self.idleEvent.set()
		self.lastError: str | None = None
		# Lock order is safe-mode lock, then adaptor lock. The writer never calls engine callbacks.
		self.lock = app.safeMode.lock

	def registerChannel(self, moduleId: str, protocol: ProtocolEncoder) -> None:
		self.channels[moduleId] = ChannelState(protocol)

	def send(self, moduleId: str, commands: OutputCommands) -> bool:
		with self.lock:
			if not self.accepting:
				return False
			channel = self.channels[moduleId]
			parts = []
			for address, value in commands:
				key = tuple(address) if isinstance(address, list) else address
				data = channel.protocol.formatData(channel.protocol.translateAddr(address), value)
				if not isinstance(data, bytes):
					raise TypeError('Protocols must produce bytes')
				channel.values[key] = data
				parts.append(data)
			payload = b"".join(parts)
			if not payload:
				return True
			self.idleEvent.clear()
			if self.needsResync:
				# The recovery pass reads the latest values; there is no history to enqueue.
				return True
			packet = PendingWrite(moduleId, channel.generation, app.safeMode.generation, payload, monotonic())
			try:
				self.queue.put_nowait(packet)
			except Full:
				self._requestResync('Serial queue full; replacing history with current state')
			return True  # Accepted, not acknowledged by the hardware.

	def allOff(self) -> None:
		with self.lock:
			if not self.accepting:
				return
			for moduleId, channel in self.channels.items():
				if channel.protected:
					channel.generation += 1
					channel.setOff()
					self.offPending[moduleId] = channel.snapshot()
			if self.offPending:
				self.idleEvent.clear()
				self._wake()

	def _wake(self) -> None:
		try:
			self.queue.put_nowait(None)
		except Full:
			pass  # An existing item already makes the reader runnable.

	def _requestResync(self, reason: str, reconnect: bool = False) -> None:
		self.lastError = reason
		logger.warning('%s: %s', self.name, reason)
		self.needsResync = True
		self.needsConnect = self.needsConnect or reconnect
		self.idleEvent.clear()
		for channel in self.channels.values():
			channel.generation += 1
		while True:
			try:
				self.queue.get_nowait()
				self.queue.task_done()
			except Empty:
				break
		self._wake()

	def _write(self, data: bytes) -> bool:
		if not data:
			return True
		if self.adaptor.transmitData(data):
			return True
		self._requestResync('Serial delivery failed; current state pending reconnect', reconnect=True)
		return False

	def _restoreLatestState(self) -> bool:
		if self.needsConnect:
			if not self.adaptor.connect():
				return False
			self.needsConnect = False
		# Restore governed relays first; exempt controls and LEDs keep their own state.
		channels = sorted(self.channels.values(), key=lambda channel: not channel.protected)
		for channel in channels:
			if channel.protected and app.safeMode.isSet():
				channel.setOff()
			if not self._write(channel.snapshot()):
				return False
		self.offPending.clear()
		self.needsResync = False
		self.lastError = None
		return True

	def _writePendingOff(self) -> bool:
		for moduleId, data in list(self.offPending.items()):
			if not self._write(data):
				return False
			del self.offPending[moduleId]
		return True

	def _updateIdle(self) -> None:
		if self.queue.empty() and not self.offPending and not self.needsResync:
			self.idleEvent.set()

	def run(self) -> None:
		try:
			while not self.stopEvent.is_set():
				with self.lock:
					if self.needsResync:
						self._restoreLatestState()
					retry = self.needsResync
					self._updateIdle()
				if retry:
					self.stopEvent.wait(self.RETRY_INTERVAL)
					continue
				packet = self.queue.get()
				try:
					with self.lock:
						if self.stopEvent.is_set():
							break
						if not self._writePendingOff():
							continue
						if packet is not None and not self.needsResync:
							channel = self.channels[packet.moduleId]
							cancelled = channel.protected and packet.safeGeneration != app.safeMode.generation
							if packet.generation == channel.generation and not cancelled:
								if monotonic() - packet.created > self.MAX_QUEUE_AGE:
									self._requestResync('Serial backlog expired; replacing history with current state')
								else:
									self._write(packet.data)
						self._updateIdle()
				finally:
					self.queue.task_done()
		except Exception:
			self.lastError = 'Serial writer stopped unexpectedly'
			self.accepting = False
			logger.exception('%s stopped unexpectedly', self.name)
		finally:
			self.adaptor.stop()

	def flush(self, timeout: float = 2.0) -> bool:
		"""Wait for accepted writes/recovery, not a hardware acknowledgement."""
		return self.idleEvent.wait(timeout)

	def stop(self, timeout: float = 2.0) -> bool:
		with self.lock:
			self.accepting = False
		completed = self.flush(timeout)
		if not completed:
			logger.error('%s stopped with undelivered state', self.name)
		self.stopEvent.set()
		self._wake()
		self.join(timeout=1.0)
		if self.is_alive():
			raise RuntimeError('Serial writer did not stop: ' + self.name)
		return completed

	def updateSerialConnection(self, data: AdaptorUpdate) -> bool:
		with self.lock:
			if not self.accepting:
				return False
			connected = self.adaptor.updateSerialConnection(data)
			self._requestResync('Serial configuration changed; restoring current state', reconnect=not connected)
			return connected

	def getCurrentStateData(self) -> StateData:
		with self.lock:
			data = self.adaptor.getCurrentStateData()
			data['deliveryPending'] = not self.idleEvent.is_set()
			data['writerError'] = self.lastError
			return data


class DataChannelManager:
	def __init__(self, sculptureConfigData: SculptureConfig) -> None:
		self.adaptors: dict[str, AdaptorThread] = {}
		self.dataChannels: dict[str, ProtocolEncoder] = {}
		self.moduleAdaptors: dict[str, AdaptorThread] = {}
		self.stopped = False
		self.safeModeBinding: SafeModeBinding | None = None
		self.shutdownComplete = False
		try:
			for adaptorId, settings in sculptureConfigData['adaptors'].items():
				adaptorConfig = cast(AdaptorConfig, dict(settings, adaptorId=adaptorId))
				className = adaptorConfig['type'][0].upper() + adaptorConfig['type'][1:] + 'Adaptor'
				adaptor: Adaptor = getattr(Adaptors, className)(adaptorConfig)
				self.adaptors[adaptorId] = AdaptorThread(adaptor)
			for moduleId, config in sculptureConfigData['modules'].items():
				kind = config['protocol']['type']
				protocolClass = getattr(Protocols, kind[0].upper() + kind[1:] + 'Protocol')
				# The manager uses the protocol as an encoder and owns asynchronous delivery.
				protocol: ProtocolEncoder = protocolClass(None, config['protocol'])
				self.dataChannels[moduleId] = protocol
				writer = self.adaptors[config['adaptor']]
				writer.registerChannel(moduleId, protocol)
				self.moduleAdaptors[moduleId] = writer
			self.safeModeBinding = app.safeMode.addBinding(self.allOff)
			if app.safeMode.isSet():
				self.allOff()
			for writer in self.adaptors.values():
				writer.start()
		except Exception:
			if self.safeModeBinding is not None:
				app.safeMode.removeBinding(self.safeModeBinding)
			for writer in self.adaptors.values():
				try:
					if writer.ident is None:
						writer.adaptor.stop()
					else:
						writer.stop()
				except Exception:
					logger.exception('Failed to close partially initialized serial writer')
			raise

	def send(self, moduleId: str, commands: OutputCommands) -> bool:
		return self.moduleAdaptors[moduleId].send(moduleId, commands)

	def allOff(self) -> None:
		for writer in self.adaptors.values():
			writer.allOff()

	def flush(self, timeout: float = 2.0) -> bool:
		deadline = monotonic() + timeout
		return all(writer.flush(max(0, deadline - monotonic())) for writer in self.adaptors.values())

	def stop(self) -> bool:
		if self.stopped:
			return self.shutdownComplete
		with app.safeMode.lock:
			self.stopped = True
			self.allOff()
			for writer in self.adaptors.values():
				writer.accepting = False
			app.safeMode.removeBinding(self.safeModeBinding)
		# Do not hold the safe-mode lock while waiting for the writers to drain.
		completed = []
		errors = []
		for writer in self.adaptors.values():
			try:
				completed.append(writer.stop())
			except Exception as error:
				logger.exception('Failed to stop %s', writer.name)
				errors.append(error)
		if errors:
			self.stopped = False
			raise RuntimeError('Serial shutdown failed') from errors[0]
		self.shutdownComplete = all(completed)
		return self.shutdownComplete

	def updateSerialConnection(self, adaptorId: str, data: AdaptorUpdate) -> bool:
		return self.adaptors[adaptorId].updateSerialConnection(data)

	def getCurrentStateData(self) -> dict[str, StateData]:
		return {name: writer.getCurrentStateData() for name, writer in self.adaptors.items()}
