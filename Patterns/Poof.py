from Patterns.PatternBase import PatternBase
from ProgramModules.Timers import Timer
import json
class Chase(PatternBase):
	def __init__(self, *args):
		self.inputParams = {
			'multiVal' : {
				'descriptionInPattern' : 'Parameters',
				'type' : 'multi',
				'subType' : 'basic',
				'number' : 3,
				'basicInputType' : 'IntValueInput',
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
			'reverse' : {
				'descriptionInPattern' : 'Reverse direction',
				'type' : 'pulse',
				'subType' : 'onOff',
				'default' : False
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
		PatternBase.__init__(self, *args)
		self.patternName = 'Poofer Chase'

		self.position = 0
		self.sequenceTriggered = True

	def triggerStep(self, *args):
		if self.inputs.triggerStep and self.sequenceTriggered:
			self.updateTriggerFunction()
			self.position += self.inputs.stepping
			if self.position > self.gridSize[1]:
				if self.inputs.numberPulses > 1:
					self.position -= self.gridSize[1]
				else:
					self.position = 0
				self.sequenceTriggered = self.inputs.triggerSequence
				if not self.sequenceTriggered:
					self.updateTriggerFunction()

		
	def triggerSequence(self, *args):
		if self.inputs.triggerSequence:
			self.inputs.doCommand(['triggerStep', 'refresh'])
			self.position = 0
			self.sequenceTriggered = True
			
	def getState(self, row, col):
		result = False
		if self.inputs.reverse:
			col = self.gridSize[1] - (col + 1)
		if self.sequenceTriggered:
			spacing = self.gridSize[1] / self.inputs.numberPulses
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
		
class AllPoof(PatternBase):
	def __init__(self, *args):
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
	def poofButton(self, *args):
		if self.inputs.poofButton:
			self.timer.changeInterval(self.inputs.stayOnTime)
			self.timer.refresh()
			self.poofState = True
			self.updateTriggerFunction()
	
	def turnOff(self):
		self.poofState = False
		self.updateTriggerFunction()

	def getState(self, row, col):
		return self.poofState
		
	def stop(self):
		self.timer.stop()
		PatternBase.stop(self)
		
class RandomPoof(PatternBase):
	def __init__(self, inputManager, gridSize, *args):
		self.inputParams = {
			'randomGenerator' : {
				'descriptionInPattern' : 'Random generator',
				'type' : 'multi',
				'subType' : 'randomPulse',
				'bindToFunction' : 'randomGenerator',
				'number' : gridSize[0] * gridSize[1]
			},
		}
		PatternBase.__init__(self, inputManager, gridSize, *args)
		self.patternName = 'Random Poof'
		self.poofStates = [[False for i in range(self.gridSize[1])] for i in range(self.gridSize[0])]

	def randomGenerator(self, input, index):
		self.poofStates[index // self.gridSize[1]][index % self.gridSize[1]] = self.inputs.randomGenerator(index)
		self.updateTriggerFunction()

	def getState(self, row, col):
		return self.poofStates[row][col]
