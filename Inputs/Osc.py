from .InputBase import InputBase
from threading import Thread, current_thread
from ProgramModules import utils

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
except ImportError:
	inputTypes['osc multi']['unavailable'] = True


class OscMultiInput(InputBase):
	class OscServerThread(Thread):
		def __init__(self, host, dispatcher):
			Thread.__init__(self, name='osc-%s:%s' % host)
			self.server = BlockingOSCUDPServer(host, dispatcher)

		def run(self):
			try:
				self.server.serve_forever(poll_interval=0.05)
			finally:
				self.server.server_close()

		def stop(self):
			# shutdown() must run outside the serving thread, or it deadlocks.
			if current_thread() is self:
				raise RuntimeError('Stop the OSC input from outside its callback thread')
			self.server.shutdown()
			self.join()

	def __init__(self, params, *args):
		params = utils.extendSettings(inputTypes['osc multi'], params)
		params['port'] = int(params['port'])
		self.outputTypes = ['pulse', 'toggle', 'value']
		callbackAddresses = {}
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
		dispatcher = Dispatcher()
		self.registerCallbacks(dispatcher)
		self.server = OscMultiInput.OscServerThread((self.configParams['host'], self.configParams['port']), dispatcher)
		self.server.start()
		self.persistant = True


	def registerCallbacks(self, dispatcher):
		# Match the output order used above: pulses, then toggles, then values.
		outputIndex = 0
		for callbackType in self.outputTypes:
			function = getattr(self, utils.makeCamelCase(['do', callbackType, 'callback']))
			for address in self.configParams['callbackAddresses'][callbackType]:
				# python-osc passes registered arguments to the callback as a list.
				dispatcher.map(address, function, outputIndex)
				outputIndex += 1

	def stop(self):
		# Finish incoming callbacks before stopping their output parameters/timers.
		self.server.stop()
		InputBase.stop(self)

	def doPulseCallback(self, path, fixedArgs, *values):
		if values:
			outputIndex = fixedArgs[0]
			self.outParams[outputIndex].setValue(values[0] in ['1', 1, 'true', 'True'])

	def doToggleCallback(self, path, fixedArgs, *values):
		if values:
			outputIndex = fixedArgs[0]
			self.outParams[outputIndex].setValue(values[0])

	def doValueCallback(self, path, fixedArgs, *values):
		if values:
			outputIndex = fixedArgs[0]
			self.outParams[outputIndex].setValue(values[0])

