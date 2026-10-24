'''
Messenger is an interface for all objects in the program to communicate with each other.
It can have an arbitrary number of "channels". Any object can put a message on any channel,
and other objects can either check the channel for messages on their own, or bind a function that
will be called when a message appears on the channel.
'''
from __future__ import annotations
from collections.abc import Sequence
from typing import Literal, TypedDict
from .Types import Callback


import logging
from .Runtime import synchronized

logger = logging.getLogger(__name__)


class MessageBinding(TypedDict):
	function: Callback
	data: Sequence | Literal[False]


class MessageChannel(TypedDict):
	messages: list
	bindings: dict[int, MessageBinding]
	queueMessages: bool


class Messenger():
	def __init__(self) -> None:
		self.channels: dict[str, MessageChannel] = {}
		self.nextBindingId = 1


	@synchronized
	def putMessage(self, channelId: str, message) -> None:
		logger.debug('putMessage(%s, %s)', channelId, message)
		self.checkForChannel(channelId)
		if self.channels[channelId]['queueMessages']:
			self.channels[channelId]['messages'].append(message)
		else:
			self.channels[channelId]['messages'] = [message]
		for bindingId, binding in list(self.channels[channelId]['bindings'].items()):
			if bindingId not in self.channels[channelId]['bindings']:
				continue
			function = binding['function']
			data = binding['data']
			logger.debug('calling %s with %s', function, data)
			if data:
				function(*data)
			else:
				function()


	@synchronized
	def getMessages(self, channelId: str):
		self.checkForChannel(channelId)
		data = self.channels[channelId]['messages']
		self.channels[channelId]['messages'] = []
		return data


	@synchronized
	def addBinding(self, channelId: str, function: Callback, data = False) -> int:
		self.checkForChannel(channelId)
		newBindingId = self.nextBindingId
		binding: MessageBinding = {'function' : function, 'data' : data}
		self.channels[channelId]['bindings'][newBindingId] = binding
		self.nextBindingId += 1
		return newBindingId


	@synchronized
	def removeBinding(self, bindingId: int) -> None:
		for channelId in self.channels:
			if bindingId in self.channels[channelId]['bindings']:
				del self.channels[channelId]['bindings'][bindingId]


	@synchronized
	def checkForChannel(self, channelId: str) -> None:
		if not channelId in self.channels.keys():
			self.channels[channelId] = {'messages' : [], 'bindings' : {}, 'queueMessages' : True}

	@synchronized
	def setQueuing(self, channelId: str, value: bool) -> None:
		self.checkForChannel(channelId)
		self.channels[channelId]['queueMessages'] = value

	@synchronized
	def doReset(self) -> None:
		self.channels = {}
		self.nextBindingId = 1
	@synchronized
	def getCurrentStateData(self) -> dict[str, list[int]]:
		data = {}
		for channelId in self.channels:
			data[channelId] = list(self.channels[channelId]['bindings'].keys())
		return data
