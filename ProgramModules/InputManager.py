''' Builds collections of input objects based on defaults. Manages uses: Inputs 
can be used by multiple things, so this keeps track of who's using what and deletes unused inputs'''


class InputManager():
	def __init__ (self, dataChannelManager):
		self.dataChannelManager = dataChannelManager
		self.inputModules = __import__('ProgramModules.Inputs')
		self.nextInputInstanceId = 0
		self.inputInstances = {}
		self.inputInstanceUses = {}


	def buildInputCollection(self, inputParams, userId):
		inputDict = {}
		for userSubId in inputParams:
			newInputInstanceId = self.createNewInput(inputParams[userSubId])
			inputDict[userSubId] = self.inputInstances[newInputInstanceId]
			self.registerUsage(userId, newInputInstanceId, userSubId)
		InputCollectionWrapper = getattr(self.inputModules, "InputCollectionWrapper")
		return InputCollectionWrapper(inputDict)

	def createNewInput(self, params):
		typeName = params['type']
		subTypeName = params['subType']
		newInputInstanceId = self.nextInputInstanceId
		self.nextInputInstanceId += 1
		inputClassName = subTypeName[0].upper() + subTypeName[1:] + typeName[0].upper() + typeName[1:] + 'Input'
		inputClass = getattr(self.inputModules, inputClassName)
		if typeName == 'multi':
			self.inputInstances[newInputInstanceId] = inputClass(self, params)
		else:
			self.inputInstances[newInputInstanceId] = inputClass(params)
		self.inputInstances[newInputInstanceId].setInstanceId(newInputInstanceId)
		return newInputInstanceId

	def registerUsage(self, userId, inputInstanceId, userSubId = False):
		if not inputInstanceId in self.inputInstanceUses.keys():
			self.inputInstanceUses[inputInstanceId] = []
		self.inputInstanceUses[inputInstanceId].append([userId, userSubId])
		return self.getInputObj(inputInstanceId)


	def unRegisterUsage(self, userId, inputInstanceId = False, userSubId = False):
		def checkItem(l, userId, userSubId):
			return userId == l[0] and (not userSubId or userSubId == l[1])
		def unRegisterForInput(userId, inputInstanceId, userSubId):
			self.inputInstanceUses[inputInstanceId][:] = [l for l in self.inputInstanceUses[inputInstanceId] if not checkItem(l, userId, userSubId)]
			if len(self.inputInstanceUses[inputInstanceId]) == 0 and not self.inputInstances[inputInstanceId].isPersistant():
				self.inputInstances[inputInstanceId].stop()
				del self.inputInstances[inputInstanceId]

		if not inputInstanceId:
			for inputInstanceId in self.inputInstanceUses:
				unRegisterForInput(userId, inputInstanceId, userSubId)
		else:
			unRegisterForInput(userId, inputInstanceId, userSubId)



	def getInputObj(self, inputInstanceId):
		return self.inputInstances[inputInstanceId]

