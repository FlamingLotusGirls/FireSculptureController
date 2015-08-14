import json
import logging

from Patterns.PatternBase import PatternBase
from ProgramModules.Timers import Timer

logger = logging.getLogger(__name__)


class LED(object):
	"""A representation of an LED to capture position and light values."""

	def __init__(self, color_triple=None):
		"""Initialize.

		Args:
		  color_triple: A tuple of 3 color values for RGB.
		"""
		if not color_triple:
			self.color_triple = (255, 0, 0)
		else:
			self.color_triple = color_triple
		self._brightness = 0

	@property
	def color_triple(self):
		return self._color_triple

	@color_triple.setter
	def color_triple(self, color_triple):
		self._color_triple = color_triple

	def getColorWithBrightness(self):
		"""Get the color value with applied brightness as a hex string.

		For example, if the color value would be (255,255,0), the hex
		string would be "#FFFF00".
		"""
		brightness_triple = list(self.color_triple)
		brightness_triple[0] = int(brightness_triple[0]*self.brightness)
		brightness_triple[1] = int(brightness_triple[1]*self.brightness)
		brightness_triple[2] = int(brightness_triple[2]*self.brightness)
		return tuple(brightness_triple)

	@property
	def brightness(self):
		return self._brightness

	@brightness.setter
	def brightness(self, brightness):
		"""Set brightness as a value 0 <= x <= 1."""
		if brightness < 0:
			raise ValueError("'brigthness must not be smaller than 0'")
		elif brightness > 1:
			raise ValueError("'brigthness must not be larger than 1'")
		self._brightness = brightness


class LEDGrid(object):
	"""A two-dimensional grid of LEDs."""

	def __init__(self, row_count, col_count):
		"""Initialize.

		Args:
		  row_count: The number of rows.
		  col_count: The number of columns.
		"""
		self._row_count = row_count
		self._col_count = col_count
		self._leds = []
		self._leds = [[LED() for col in range(col_count)]
			      for row in range(row_count)]

	@property
	def row_count(self):
		return self._row_count

	@property
	def col_count(self):
		return self._col_count

	def getLED(self, row, col):
		"""Returns the LED at (row,column)."""
		return self._leds[row][col]

	@staticmethod
	def getDistance(left, right):
		"""Computes the distance of one LED to another LED.

		Args:
		  left: First LED position (row, col).
		  right: Second LED position (row, col).

		Returns:
		  A (row distance, column distance) tuple.
		"""
		col_distance = 0
		row_distance = 0
		if left[1] > right[1]:
			col_distance = left[1] - right[1]
		else:
			col_distance = right[1] - left[1]
		if left[0] > right[0]:
			row_distance = left[0] - right[0]
		else:
			row_distance = right[0] - left[0]
		return (row_distance, col_distance)



class HeartBeat(PatternBase):
	"""An LED pattern emulating a heart beat."""

	# DEFAULT_BRIGHTNESS = 0.4

	# Difference in brightness per step (either increasing of decreasing).
	BRIGHTNESS_DIFF = 0.1

	# Differences in brightness in relation to the distance to the point
	# (the further away, the darker).
	DISTANCE_DIFF = 0.05

	# # Number of columns of LEDs.
	# COL_COUNT = 20
	# # Number of columns of LEDs.
	# ROW_COUNT = 1

	def __init__(self, *args):
		# Passed in via SculptureModuleBase.addPattern().
		grid_size = args[0]
		self.row_count = grid_size[0]
		self.col_count = grid_size[1]
		logger.info('HearBeat Pattern initialized (size=[%s,%s])',
			     self.row_count, self.col_count)
		# A dictionary of input parameters rendered in the UI. Note
		# that those are used by PatternBase.__init__() to construct
		# self.inputs, an InputManager.InputCollection object.
		#
		# 'type' and 'subtype' are used to create the input name as
		# defined in Inputs.Basic.inputTypes.
		self.inputParams = {
			'multiVal' : {
				'descriptionInPattern' : 'Parameters',
				'type' : 'multi',
				'subType' : 'basic',
				'number' : 3,
				'basicInputType' : 'int value',
				'min' : [1, 1],
				'max' : [self.col_count - 1, 100],
				'default' : [2, 1, 1],
				'description' : ['heart position',
						 'brightness'],
				'channels' : ['heart_pos',
					      'brightness',
					      'speed'],
			},
			'triggerStep' : {
				'descriptionInPattern' :
				'Interval between refreshs',
				'type' : 'pulse',
				'subType' : 'timer',
				'bindToFunction' : 'triggerStep',
				'min' : 1 ,
				'max' : 3000,
				'default' : 10,
			},
			'triggerSequence' : {
				'descriptionInPattern' : 'Activate',
				'type' : 'pulse',
				'subType' : 'onOff',
				'bindToFunction' : 'triggerSequence',
			},
			# Name must match channel defined above in 'multiVal'.
			#
			# Note that this is a one-dimensional value - we
			# simplify and assume the LED grid only has 1 row and
			# 'heart_pos' identifies the column position of the
			# heart.
			'heart_pos' : {
				'descriptionInPattern' :
				'Position of the heart.',
				'type' : 'value',
				'bindToFunction' : '_update_heart_position',
			},
			# Name must match channel defined above in 'multiVal'.
			'brightness' : {
				'descriptionInPattern' :
				'The brightness of the heart LED.',
				'type' : 'value',
			},
		}
		PatternBase.__init__(self, *args)
		self.sequenceTriggered = False


		self._led_grid = LEDGrid(self.row_count, self.col_count)
		self._heart_row = -1
		self._heart_col = -1
		self._heart_led = None
		self._max_distance = -1
		# Note that this sets the self._heart_... attributes.
		self._update_heart_position(0, self.col_count / 2)
		self._max_distance = (0, 0)
		self.increase = True

	def _update_heart_position(self, row, col):
		logger.info('HeartBeat._update_heart_position(%s, %s)',
			    row, col)
		self._heart_row = row
		self._heart_col = col
		self._heart_led = self._led_grid.getLED(row, col)
		self._max_distance = max(
			LEDGrid.getDistance((0, 0), (row, col)),
			LEDGrid.getDistance((self.row_count, self.col_count),
					    (row, col)))

	def _update_non_heart_leds(self):
		for row in range(self._led_grid.row_count):
			for col in range(self._led_grid.col_count):
				distance = LEDGrid.getDistance(
					(row, col),
					(self._heart_row, self._heart_col))
				# Use the smaller of the two dimensional
				# values.
				min_dist = max(distance[0], distance[1])
				new_brightness = (self._heart_led.brightness -
						  min_dist*self.DISTANCE_DIFF)
				new_brightness = max(0, new_brightness)
				self._led_grid.getLED(row, col).brightness = new_brightness

	def _update_leds(self):
		logging.debug('HeartBeat._update_leds() called.')
		if self._heart_led.brightness >= .99:
			brightness_diff = 0 - self.BRIGHTNESS_DIFF
		elif self._heart_led.brightness <= 0.3:
			# Don't turn off heart entirely
			brightness_diff = 0 + self.BRIGHTNESS_DIFF
		else:
			brightness_diff = 0 + self.BRIGHTNESS_DIFF
		self._heart_led.brightness += brightness_diff
		self._update_non_heart_leds()



	def triggerStep(self, *args):
		if self.inputs.triggerStep and self.sequenceTriggered:
			logging.debug('HeartBeat.triggerStep() called.')
			# HACK: As mentioned above, we assume a single row and
			# only update the column of the heart position
			if self._heart_col != self.inputs.heart_pos:
				self._update_heart_position(
					self._heart_row, self.inputs.heart_pos)
			self._update_leds()
			self.requestUpdate()

	def triggerSequence(self, *args):
		if self.inputs.triggerSequence:
			logging.info('HeartBeat.triggerSequence() called.')
			self.inputs.doCommand(['triggerStep', 'refresh'])
			self.sequenceTriggered = True

	def getState(self, row, col):
		if (row < 0) or (row >= self._led_grid.row_count):
			return (0, 0, 0)
		elif (col < 0) or (col >= self._led_grid.col_count):
			return (0, 0, 0)
		else:
			return self._led_grid.getLED(row, col).getColorWithBrightness()


class Image(object):
	"""A container class for Image data."""

	def __init__(self, name, path):
		# Name of the image.
		self.name = name
		# Path to the image
		#
		# TODO: specify whether it's an absolute or relative path.
		self.path = path


class FromImage(PatternBase):
	"""A pattern that generates data based on predefined images."""

	# A map of image IDs to Image() objects.
	supported_images = {
		"0": Image("image 1", "path/to/image1"),
		"1": Image("image 2", "path/to/image2"),
		"2": Image("image 3", "path/to/image3"),
		}

	def __init__(self, *args):
		# A dictionary of image IDs (as defined in 'supported_images'
		# above) to image names shown in the UI.
		choices = {}
		for image_id, image in self.supported_images.items():
			choices[image_id] = image.name
		# A dictionary of input parameters rendered in the UI. Note
		# that those are used by PatternBase.__init__() to construct
		# self.inputs, an InputManager.InputCollection object.
		#
		# 'type' and 'subtype' are used to create the input name as
		# defined in Inputs.Basic.inputTypes.
		self.inputParams = {
			'updateButton' : {
				'descriptionInPattern' : 'update',
				'type' : 'pulse',
				'subType' : 'button',
				'bindToFunction' : 'updateButtonPressed',
			},
			'imageSelection' : {
				'descriptionInPattern' : 'Image used for LED input',
				'type' : 'text',
				'subType' : 'choice',
				'choices': choices,
			},
		}
		PatternBase.__init__(self, *args)
		self.patternName = 'From Image'
		self._current_image_id = "0"

	def updateButtonPressed(self, *args):
		"""Change behavor when the user pressed the update button."""
		# Through the magic of the framework, user-provided input data
		# can be found in self.inputs.
		#
		# Use default in case user has not selected anything, yet.
		if not self.inputs.imageSelection:
			new_image_id = self._current_image_id
		else:
			new_image_id = self.inputs.imageSelection
		self._current_image_id = new_image_id
		logger.info('now using image %s (%s, %s)',
			    new_image_id,
			    self.supported_images[new_image_id].name,
			    self.supported_images[new_image_id].path)
		# TODO: update image used for LED pattern generation.
		if self.inputs.updateButton:
			self.requestUpdate()

	def getState(self, row, col):
		"""Return state of the LED at [row,col]."""
		return self._current_image_id

	def stop(self):
		PatternBase.stop(self)
