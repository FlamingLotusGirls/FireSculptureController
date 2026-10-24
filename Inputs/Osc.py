from .InputBase import InputBase
from threading import Thread, Event
from ProgramModules import utils

inputTypes = {
	'osc multi' : {
		'longDescription' : 'OpenSoundControl server', 
		'shortDescription' : 'OSC server', 
		'host' : '127.0.0.2', 
		'port' : 8000, 
		'setupParamsNeeded' : [['text', 'Host', 'host'], ['int', 'Port', 'port'], ['text', 'Button addresses(separated by space)', 'pulseAddressString'], ['text', 'Toggle addresses(separated by space)', 'toggleAddressString'], ['text', 'Value addresses(separated by space)', 'valueAddressString']],
		'callbackAddresses' : {'pulse' : ['/1/button1', '/1/button2', '/1/button3'], 'toggle' : [], 'value' : ['/1/value1', '/1/value2', '/1/value3']},
		'hasOwnClass' : True
	}
}

try:
	from OSC import OSCServer,OSCClient, OSCMessage
except:
	inputTypes['osc multi']['unavailable'] = True


class OscMultiInput(InputBase):
	class OscServerThread(Thread):
		def __init__(self, host, stopEvent):
			Thread.__init__(self)
			self.server = OSCServer(host)
			self.stopEvent = stopEvent
		def setCallBacks(self, callBacks):
			for callBack in callBacks:
				self.server.addMsgHandler(callBack[0], callBack[1])
		def run(self):
			while not self.stopEvent.is_set():
				self.server.handle_request()
			self.server.close()

	def __init__(self, params, *args):
		self.outputTypes = ['pulse', 'toggle', 'value']
		callbackAddresses = {}
		callbacksInStringForm = False
		for outputType in self.outputTypes:
			callbackAddresses[outputType] = []
			key = outputType + 'AddressString'
			if key in params.keys():
				callbackAddresses[outputType] = params[key].split()
				if len(callbackAddresses[outputType]) > 0:
					callbacksInStringForm = True
				del params[key]
		if callbacksInStringForm:
			params['callbackAddresses'] = callbackAddresses
		params['outParams'] = []
		for outputType in self.outputTypes:
			for address in params['callbackAddresses'][outputType]:
				params['outParams'].append({'type' : outputType, 'description' : outputType[0].upper() + outputType[1:] + ' ' + address, 'sendMessageOnChange' : True})
			
		InputBase.__init__(self, params, *args)
		self.callbackLinkList = []
		self.stopEvent = Event()
		self.server = OscMultiInput.OscServerThread((self.configParams['host'], self.configParams['port']), self.stopEvent)
		self.buildCallbackLinkList()
		self.server.setCallBacks(self.callbackLinkList)
		self.server.start()
		self.persistant = True


	def buildCallbackLinkList(self):
		for callbackType in self.outputTypes:
			if callbackType in self.configParams['callbackAddresses'].keys():
				function = getattr(self, utils.makeCamelCase(['do', callbackType, 'callback']))
				for callbackAddress in self.configParams['callbackAddresses'][callbackType]:
					self.callbackLinkList.append([callbackAddress, function])

	def stop(self):
		self.stopEvent.set()
		InputBase.stop(self)

	def doPulseCallback(self, path, tags, args, source):
		outputIndex = self.getOutputIndexFromAddress(path, 'pulse')
		self.outParams[outputIndex].setValue(args[0] in ['1', 1, 'true', 'True'])

	def doToggleCallback(self, path, tags, args, source):
		outputIndex = self.getOutputIndexFromAddress(path, 'toggle')
		self.outParams[outputIndex].setValue(args[0])

	def doValueCallback(self, path, tags, args, source):
		outputIndex = self.getOutputIndexFromAddress(path, 'value')
		self.outParams[outputIndex].setValue(args[0])


	def getOutputIndexFromAddress(self, path, callbackType):
		if path[:-2].isdigit():
			addrNum = int(path[:-2])
		elif path[:-1].isdigit():
			addrNum = int(path[:-1])
		else:
			return False
		index = addrNum-1
		done = False
		for outputType in outputTypes:
			if callbackType == outputType:
				done = True
			if not done:
				index += len(self.configParams[outputType])
		return index

