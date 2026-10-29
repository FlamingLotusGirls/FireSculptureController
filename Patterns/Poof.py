from __future__ import annotations

from Patterns.PatternBase import PatternBase
from ProgramModules.Timers import Timer
import json
import random
class Chase(PatternBase):
	def __init__(self, gridSize: list[int], *args) -> None:
		self.inputParams = {
			'multiVal' : {
				'descriptionInPattern' : 'Parameters',
				'type' : 'multi',
				'subType' : 'basic',
				'number' : 3,
				'basicInputType' : 'int value',
				'min' : [1, 1, 1],
				'max' : [5, 5, 3],
				'default' : [2, 1, 1],
				'description' : ['Poofers', 'Jump', 'Pulses'],
				'channels' : ['numberOn', 'stepping', 'numberPulses']
			},
			'triggerStep' : {
				'descriptionInPattern' : 'Trigger next step in sequence',
				'type' : 'pulse',
				'subType' : 'timer',
				'bindToFunction' : 'triggerStep',
				'min' : 50,
				'max' : 3000, 
				'default' : 100
			},
			'triggerSequence' : {
				'descriptionInPattern' : 'Trigger chase',
				'type' : 'pulse',
				'subType' : 'onOff',
				'bindToFunction' : 'triggerSequence'
			},
			'stayOnTime' : {
				'descriptionInPattern' : 'On duration',
				'type' : 'value',
				'subType' : 'int',
				'min' : 0,
				'max' : 3000,
				'default' : 0
			},
			'reverse' : {
				'descriptionInPattern' : 'Reverse direction',
				'type' : 'pulse',
				'subType' : 'onOff',
				'default' : False
			},
			'chaseRange' : {
				'descriptionInPattern' : 'Chase range (0 = ignore)',
				'type' : 'multi',
				'subType' : 'basic',
				'number' : 2,
				'basicInputType' : 'int value',
				'min' : [0, 0],
				'max' : [gridSize[1], gridSize[1]],
				'default' : [0, 0],
				'description' : ['Start', 'Stop'],
				'sendMessageOnChange' : True,
				'channels' : ['startPoofer', 'stopPoofer']
			},
			'startPoofer' : {
				'descriptionInPattern' : 'Start poofer',
				'type' : 'value',
				'bindToFunction' : 'rangeChanged'
			},
			'stopPoofer' : {
				'descriptionInPattern' : 'Stop poofer',
				'type' : 'value',
				'bindToFunction' : 'rangeChanged'
			},
			'numberOn' : {
				'descriptionInPattern' : 'Number of poofers on',
				'type' : 'value',
			},
			'stepping' : {
				'descriptionInPattern' : 'Number of poofers to jump',
				'type' : 'value',
			},
			'numberPulses' : {
				'descriptionInPattern' : 'Number of pulses',
				'type' : 'value',
			}
		}
		PatternBase.__init__(self, gridSize, *args)
		self.patternName = 'Poofer Chase'

		self.position = 0
		self.sequenceTriggered = True
		self.timedPoofers: set[int] = set()
		self.offTimers: dict[int, Timer] = {}

	def triggerStep(self, *args) -> None:
		if self.inputs.triggerStep and self.sequenceTriggered:
			if self.inputs.stayOnTime > 0:
				self.startTimedPoofers()
			self.requestUpdate()
			self.position += self.inputs.stepping
			start, stop = self.getChaseRange()
			length = stop - start
			if self.inputs.startPoofer or self.inputs.stopPoofer:
				# Explicit ranges wrap immediately, without an empty step at either end.
				if length > 0 and self.position < length:
					return
				self.position = self.position % length if length > 0 else 0
				self.sequenceTriggered = self.inputs.triggerSequence
				if not self.sequenceTriggered:
					self.requestUpdate()
			elif self.position > self.gridSize[1]:
				if self.inputs.numberPulses > 1:
					self.position -= self.gridSize[1]
				else:
					self.position = 0
				self.sequenceTriggered = self.inputs.triggerSequence
				if not self.sequenceTriggered:
					self.requestUpdate()

		
	def triggerSequence(self, *args) -> None:
		if self.inputs.triggerSequence:
			self.inputs.doCommand(['triggerStep', 'refresh'])
			self.position = 0
			self.sequenceTriggered = True
			
	def startTimedPoofers(self) -> None:
		# Each selected poofer gets its own OFF deadline, independent of step timing.
		for col in range(self.gridSize[1]):
			if self.isPooferInStep(col):
				if col not in self.offTimers:
					self.offTimers[col] = Timer(False, self.inputs.stayOnTime, self.turnOffPoofer, (col,))
				self.timedPoofers.add(col)
				self.offTimers[col].changeInterval(self.inputs.stayOnTime)
				self.offTimers[col].refresh()

	def turnOffPoofer(self, col: int) -> None:
		self.timedPoofers.discard(col)
		self.requestUpdate()

	def stop(self) -> None:
		for timer in self.offTimers.values():
			timer.stop()
		PatternBase.stop(self)

	def getChaseRange(self) -> tuple[int, int]:
		# Controls use inclusive, one-based poofer numbers; code uses [start, stop).
		start = max(0, min(self.inputs.startPoofer - 1, self.gridSize[1] - 1))
		stop = max(0, min(self.inputs.stopPoofer or self.gridSize[1], self.gridSize[1]))
		return start, stop

	def rangeChanged(self, *args) -> None:
		self.position = 0
		self.timedPoofers.clear()
		self.requestUpdate()

	def getState(self, row: int, col: int) -> bool:
		start, stop = self.getChaseRange()
		if not start <= col < stop:
			return False
		if self.inputs.stayOnTime > 0:
			return col in self.timedPoofers
		return self.isPooferInStep(col)

	def isPooferInStep(self, col: int) -> bool:
		start, stop = self.getChaseRange()
		if not start <= col < stop:
			return False
		col -= start
		length = stop - start
		result = False
		if self.inputs.reverse:
			col = length - (col + 1)
		if self.sequenceTriggered:
			spacing = length // self.inputs.numberPulses
			intervalCount = 0
			while intervalCount < self.inputs.numberPulses and not result:
				lowerLimit = self.position + intervalCount * spacing
				upperLimit = lowerLimit + self.inputs.numberOn
				if col >= lowerLimit and col < upperLimit:
					result = True
				if self.inputs.numberPulses > 1:
					lowerLimit = self.position - intervalCount * spacing
					upperLimit = lowerLimit + self.inputs.numberOn
					if col >= lowerLimit and col < upperLimit:
						result = True
				intervalCount += 1
		return result
		
class Twister(PatternBase):
	def __init__(self, *args) -> None:
		self.inputParams = {
			'triggerSequence': {
				'descriptionInPattern': 'Run twister',
				'type': 'pulse', 'subType': 'onOff', 'default': False,
				'bindToFunction': 'reset'
			},
			'triggerStep': {
				'descriptionInPattern': 'Trigger next step in sequence',
				'type': 'pulse', 'subType': 'timer',
				'min': 50, 'max': 3000, 'default': 1000,
				'bindToFunction': 'triggerStep'
			},
			'stayOnTime': {
				'descriptionInPattern': 'On duration',
				'type': 'value', 'subType': 'int',
				'min': 0, 'max': 3000, 'default': 0
			},
			'continueChance': {
				'descriptionInPattern': 'Continue chance',
				'description': '%, 50 = even odds',
				'type': 'value', 'subType': 'int',
				'min': 0, 'max': 100, 'default': 60
			},
			'startAtEnd': {
				'descriptionInPattern': 'Start at far end',
				'type': 'pulse', 'subType': 'onOff', 'default': False,
				'bindToFunction': 'reset'
			}
		}
		PatternBase.__init__(self, *args)
		self.patternName = 'Twister'
		self.position: int | None = None
		self.direction = 1
		self.timedPoofers: set[int] = set()
		self.offTimers: dict[int, Timer] = {}

	def reset(self, *args) -> None:
		self.position = None
		self.timedPoofers.clear()
		self.inputs.doCommand(['triggerStep', 'refresh'])
		self.requestUpdate()

	def triggerStep(self, *args) -> None:
		if not self.inputs.triggerStep or not self.inputs.triggerSequence:
			return
		last = self.gridSize[1] - 1
		if self.position is None:
			self.position = last if self.inputs.startAtEnd else 0
			self.direction = -1 if self.inputs.startAtEnd else 1
		elif last > 0:
			if self.position == 0:
				self.direction = 1
			elif self.position == last:
				self.direction = -1
			elif random.random() >= self.inputs.continueChance / 100.0:
				self.direction *= -1
			self.position += self.direction

		if self.inputs.stayOnTime > 0:
			col = self.position
			if col not in self.offTimers:
				self.offTimers[col] = Timer(False, self.inputs.stayOnTime, self.turnOffPoofer, (col,))
			self.timedPoofers.add(col)
			self.offTimers[col].changeInterval(self.inputs.stayOnTime)
			self.offTimers[col].refresh()
		self.requestUpdate()

	def turnOffPoofer(self, col: int) -> None:
		self.timedPoofers.discard(col)
		self.requestUpdate()

	def getState(self, row: int, col: int) -> bool:
		if not self.inputs.triggerSequence:
			return False
		if self.inputs.stayOnTime > 0:
			return col in self.timedPoofers
		return col == self.position

	def stop(self) -> None:
		for timer in self.offTimers.values():
			timer.stop()
		PatternBase.stop(self)


class AllPoof(PatternBase):
	def __init__(self, *args) -> None:
		self.inputParams = {
			'poofButton' : {
				'descriptionInPattern' : 'Poof!',
				'type' : 'pulse',
				'subType' : 'button',
				'bindToFunction' : 'poofButton'
			},
			'stayOnTime' : {
				'descriptionInPattern' : 'Time to stay on for(ms)',
				'type' : 'value',
				'subType' : 'int',
				'min' : 100,
				'max' : 1000,
				'default' : 200
			},
		}
		PatternBase.__init__(self, *args)
		self.patternName = 'Allpoof'
		self.timer = Timer(False, self.inputs.stayOnTime, self.turnOff)
		self.poofState = False

	def poofButton(self, *args) -> None:
		if self.inputs.poofButton:
			self.timer.changeInterval(self.inputs.stayOnTime)
			self.timer.refresh()
			self.poofState = True
			self.requestUpdate()
	
	def turnOff(self) -> None:
		self.poofState = False
		self.requestUpdate()

	def getState(self, row: int, col: int) -> bool:
		return self.poofState
		
	def stop(self) -> None:
		self.timer.stop()
		PatternBase.stop(self)
		
class RandomPoof(PatternBase):
	def __init__(self, gridSize: list[int], *args) -> None:
		self.inputParams = {
			'randomGenerator' : {
				'descriptionInPattern' : 'Random generator',
				'type' : 'multi',
				'subType' : 'randomPulse',
				'bindToFunction' : 'changePooferState',
				'number' : gridSize[0] * gridSize[1]
			},
		}
		PatternBase.__init__(self, gridSize, *args)
		self.patternName = 'Random Poof'
		self.poofStates = [[False for i in range(self.gridSize[1])] for i in range(self.gridSize[0])]

	def changePooferState(self, input: str, index: int) -> None:
		self.poofStates[index // self.gridSize[1]][index % self.gridSize[1]] = self.inputs.randomGenerator(index)
		self.requestUpdate()

	def getState(self, row: int, col: int) -> bool:
		return self.poofStates[row][col]
