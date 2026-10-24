from __future__ import annotations

from .InputBase import InputBase
from threading import Event, Thread, current_thread
from time import time
from ProgramModules import utils
from ProgramModules.Runtime import runCallback

inputTypes = {
	'osc multi' : {
		'longDescription' : 'OpenSoundControl server', 
		'shortDescription' : 'OSC server', 
		'host' : '0.0.0.0',
		'port' : 8000, 
		'setupParamsNeeded' : [['text', 'Host', 'host'], ['int', 'Port', 'port'], ['text', 'Button addresses(separated by space)', 'pulseAddressString'], ['text', 'Toggle addresses(separated by space)', 'toggleAddressString'], ['text', 'Value addresses(separated by space)', 'valueAddressString']],
		'callbackAddresses' : {'pulse' : ['/1/button1', '/1/button2', '/1/button3'], 'toggle' : [], 'value' : ['/1/value1', '/1/value2', '/1/value3']},
		'hasOwnClass' : True
	}
}

try:
	from pythonosc.dispatcher import Dispatcher
	from pythonosc.osc_server import BlockingOSCUDPServer
	from pythonosc.osc_packet import OscPacket, ParseError
except ImportError:
	inputTypes['osc multi']['unavailable'] = True


if 'unavailable' not in inputTypes['osc multi']:
	class CancellableDispatcher(Dispatcher):
		"""Keep bundle timetags, but cancel their wait when the input stops."""
		def __init__(self) -> None:
			super().__init__()
			self.stopEvent = Event()

		def call_handlers_for_packet(self, data: bytes, client_address: tuple[str, int]):
			try:
				packet = OscPacket(data)
			except ParseError:
				return []
			results = []
			for message in packet.messages:
				if self.stopEvent.wait(max(0, message.time - time())):
					break
				for handler in self.handlers_for_address(message.message.address):
					result = runCallback(self.stopEvent, handler.invoke, client_address, message.message)
					if result is not None:
						results.append(result)
			return results


class OscMultiInput(InputBase):
	class OscServerThread(Thread):
		def __init__(self, host: tuple[str, int], dispatcher: CancellableDispatcher) -> None:
			Thread.__init__(self, name='osc-%s:%s' % host)
			self.server = BlockingOSCUDPServer(host, dispatcher)
			self.stopEvent = dispatcher.stopEvent
			self.shutdownThread: Thread | None = None

		def run(self) -> None:
			try:
				self.server.serve_forever(poll_interval=0.05)
			finally:
				self.server.server_close()

		def stop(self) -> None:
			self.stopEvent.set()
			# shutdown() must run outside the serving thread, or it deadlocks.
			if current_thread() is self:
				if self.shutdownThread is None:
					self.shutdownThread = Thread(target=self.server.shutdown, name='osc-stop')
					self.shutdownThread.start()
				return
			self.server.shutdown()
			self.join()
			if self.shutdownThread is not None:
				self.shutdownThread.join()

	def __init__(self, params, *args) -> None:
		params = utils.extendSettings(inputTypes['osc multi'], params)
		params['port'] = int(params['port'])
		self.outputTypes = ['pulse', 'toggle', 'value']
		callbackAddresses: dict[str, list[str]] = {}
		callbacksInStringForm = False
		for outputType in self.outputTypes:
			callbackAddresses[outputType] = []
			key = outputType + 'AddressString'
			if key in params.keys():
				callbackAddresses[outputType] = params[key].split()
				callbacksInStringForm = True
				del params[key]
		if callbacksInStringForm:
			params['callbackAddresses'] = callbackAddresses
		params['outParams'] = []
		for outputType in self.outputTypes:
			for address in params['callbackAddresses'][outputType]:
				params['outParams'].append({'type' : outputType, 'description' : outputType[0].upper() + outputType[1:] + ' ' + address, 'sendMessageOnChange' : True})
			
		InputBase.__init__(self, params, *args)
		dispatcher = CancellableDispatcher()
		self.registerCallbacks(dispatcher)
		self.server = OscMultiInput.OscServerThread((self.configParams['host'], self.configParams['port']), dispatcher)
		try:
			self.server.start()
		except Exception:
			self.server.server.server_close()
			InputBase.stop(self)
			raise
		self.persistant = True


	def registerCallbacks(self, dispatcher: CancellableDispatcher) -> None:
		# Match the output order used above: pulses, then toggles, then values.
		outputIndex = 0
		for callbackType in self.outputTypes:
			function = getattr(self, utils.makeCamelCase(['do', callbackType, 'callback']))
			for address in self.configParams['callbackAddresses'][callbackType]:
				# python-osc passes registered arguments to the callback as a list.
				dispatcher.map(address, function, outputIndex)
				outputIndex += 1

	def stop(self) -> None:
		# Finish incoming callbacks before stopping their output parameters/timers.
		self.server.stop()
		InputBase.stop(self)

	def doPulseCallback(self, path: str, fixedArgs: list[int], *values) -> None:
		if values:
			outputIndex = fixedArgs[0]
			self.outParams[outputIndex].setValue(values[0] in ['1', 1, 'true', 'True'])

	def doToggleCallback(self, path: str, fixedArgs: list[int], *values) -> None:
		if values:
			outputIndex = fixedArgs[0]
			self.outParams[outputIndex].setValue(values[0])

	def doValueCallback(self, path: str, fixedArgs: list[int], *values) -> None:
		if values:
			outputIndex = fixedArgs[0]
			self.outParams[outputIndex].setValue(values[0])

