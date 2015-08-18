import json
import logging

# Used to compute heartbeat. Importing these slows down load time noticeably.
import scipy
from scipy import signal

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
			self.color_triple = (0, 0, 0)
		else:
			self.color_triple = color_triple
		self._brightness = 0

	@property
	def color_triple(self):
		return self._color_triple

	@color_triple.setter
	def color_triple(self, color_triple):
		if color_triple[0] < 0 or color_triple[0] > 255:
			msg = ('color_triple[0] must be between 0 and 255, '
			       'was %s instead' % color_triple[0])
			raise ValueError(msg)
		if color_triple[1] < 0 or color_triple[1] > 255:
			msg = ('color_triple[1] must be between 0 and 255, '
			       'was %s instead' % color_triple[1])
			raise ValueError(msg)
		if color_triple[2] < 0 or color_triple[2] > 255:
			msg = ('color_triple[2] must be between 0 and 255, '
			       'was %s instead' % color_triple[2])
			raise ValueError(msg)
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

	def __init__(self, row_count, col_count, default_color_triple=None):
		"""Initialize.

		Args:
		  row_count: The number of rows.
		  col_count: The number of columns.
		"""
		self._row_count = row_count
		self._col_count = col_count
		if not default_color_triple:
			default_color_triple = (0, 0, 0)
		self._leds = []
		self._leds = [[LED(default_color_triple)
			       for col in range(col_count)]
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

	# Difference in brightness per step (either increasing of decreasing).
	BRIGHTNESS_DIFF = 0.1

	# Differences in brightness in relation to the distance to the point
	# (the further away, the darker).
	DISTANCE_DIFF = 0.05

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
			'PatternMultiVal' : {
				'descriptionInPattern' : 'Parameters',
				'type' : 'multi',
				'subType' : 'basic',
				'number' : 3,
				'basicInputType' : 'int value',
				'min' : [1, 1],
				'max' : [self.col_count - 1, 100],
				'default' : [self.col_count / 2, 70],
				'description' : ['heart position',
						 'maximum brightness',
					 ],
				'channels' : ['heart_pos',
					      'max_brightness',
				      ],
			},
			'ColorMultiVal' : {
				'descriptionInPattern' : 'Parameters',
				'type' : 'multi',
				'subType' : 'basic',
				'number' : 3,
				'basicInputType' : 'int value',
				'min' : [0, 0, 0],
				'max' : [255, 255, 255],
				# red is a good default for a heartbeat.
				'default' : [255, 0, 0],
				'description' : ['red color additive',
						 'green color additive',
						 'blue color additive',
				],
				'channels' : ['red',
					      'green',
					      'blue',
				],
			},
			'triggerStep' : {
				'descriptionInPattern' :
				'Interval between refreshs',
				'type' : 'pulse',
				'subType' : 'timer',
				'bindToFunction' : 'triggerStep',
				'min' : 1 ,
				'max' : 100,
				'default' : 1,
			},
			'triggerSequence' : {
				'descriptionInPattern' : 'Activate',
				'type' : 'pulse',
				'subType' : 'onOff',
				'bindToFunction' : 'triggerSequence',
			},
			# Name must match channel defined above in
			# 'multiVal'. This inputs do not have corresponding
			# function bindings, but we update the matching
			# internal values on triggerStep(), thus having a
			# near-immediate effect.
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
			'max_brightness' : {
				'descriptionInPattern' :
				'The maximum brightness of the heart LED.',
				'type' : 'value',
			},
			'red' : {
				'descriptionInPattern' : 'Red value of color.',
				'type' : 'value',
			},
			'green' : {
				'descriptionInPattern' : 'Green value of color.',
				'type' : 'value',
			},
			'blue' : {
				'descriptionInPattern' : 'Blue value of color.',
				'type' : 'value',
			},
		}
		PatternBase.__init__(self, *args)
		self.sequenceTriggered = False

		self._red = self.inputs.red
		self._green = self.inputs.green
		self._blue = self.inputs.blue

		self._led_grid = LEDGrid(self.row_count, self.col_count,
					 (self._red, self._green, self._blue))
		self._heart_row = -1
		self._heart_col = -1
		self._heart_led = None
		self._max_distance = -1
		# Note that this sets the self._heart_... attributes.
		self._update_heart_position(0, self.inputs.heart_pos)
		self._max_distance = (0, 0)
		self._max_brightness = self.inputs.max_brightness
		self.increase = True

		# A list of precomputed heart brightness values we will read
		# from on update.
		self._led_values = self._compute_heart_values()
		# Determine the last index once, so we dont' have to do it for
		# every update.
		self._led_values_last_index = len(self._led_values) - 1
		# Index of the currently used heart brightness value.
		self._led_values_index = 0

	def _compute_heart_values(self):
		"""Precompute heart brightness values.

		The returned list reflects brightness values emulating a
		beating heart. A visualization can iterate over the values
		repeatedly for a good heart beat pattern.

		We precompute them because the operation is expensive.

		Returns:
		  A list of precomputed heart beat values.
		"""

		values = []
		# No variability as we are going to loop anyway.
		rate_variability = [1.0, 1.0]
		# The higher the sample rate, the more values we get. The
		# current value was determined by trial-and-error.
		sample_rate = 50.0
		# To be honest, no idea what this means or affects the values.
		daub_array = signal.wavelets.daub(10)
		ecg_data_points = []
		for r in rate_variability:
			ecg_data_points.append(signal.resample(
				daub_array, int(r*sample_rate)))
		values = scipy.concatenate(ecg_data_points)
		# Equalize data to fit into our expected brightness spectrum.
		minimum = min(values)
		maximum = max(values)
		# We multiply by 2 to end up with a value greater than 1, but
		# smaller than 2 (heuristically determined, no smart reason
		# why).
		factor = max(minimum, maximum)*2
		# The brightness boost is computed based on the factor (a value
		# between 2 and 1), multiplied by the user-configured maximum
		# brightness of the heart (which is something between 1 and
		# 100, so we divide it accordingly.)
		brightness_boost = (factor - 1)*(self._max_brightness/100.0)
		# Now we take the computed values, devide them by the
		# precomputed factor, which equalizes them somewhat, and add
		# the computed brightness boost. The addition allows us to set
		# the heart to the proper brightness value and aligns all other
		# values accordingly.
		values = [(value/factor)+brightness_boost for value in values]
		return values

	def _update_heart_position(self, row, col):
		"""Set a new heart position and update related values."""
		logger.info('HeartBeat._update_heart_position(%s, %s)',
			    row, col)
		self._heart_row = row
		self._heart_col = col
		self._heart_led = self._led_grid.getLED(row, col)
		self._max_distance = max(
			LEDGrid.getDistance((0, 0), (row, col)),
			LEDGrid.getDistance((self.row_count, self.col_count),
					    (row, col)))

	def _update_color(self, color_triple):
		"""Update the color of all LEDs.

		Args:
		  color_triple: A (red, green, blue) color tuple.
		"""
		for row in range(self._led_grid.row_count):
			for col in range(self._led_grid.col_count):
				self._led_grid.getLED(row, col).color_triple = color_triple
		self._red = self.inputs.red
		self._green = self.inputs.green
		self._blue = self.inputs.blue

	def _update_non_heart_leds(self):
		"""Update all LEDs that are not the heart LED.

		This function iterates through all LEDs, and adjusts their
		brightness based on the distance to the heart.

		"""
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
		"""Update all LEDs.

		This function determines the new heart brightness value, then
		updates all LEDs accordingly.
		"""
		logging.debug('HeartBeat._update_leds() called.')
		# Iterate through precomputed values, start at the beginning
		# when done.
		if self._led_values_index < self._led_values_last_index:
			self._led_values_index += 1
		else:
			self._led_values_index = 0
		# Determine the brightness based on the precomputed value and
		# the max_brightness multiplier.
		brightness = self._led_values[self._led_values_index]
		self._heart_led.brightness = brightness
		self._update_non_heart_leds()

	def triggerStep(self, *args):
		"""Run one step in the pattern.

		If input values have been updated, also update the local values
		and recompute the heart brightness values.

		"""
		if self.inputs.triggerStep and self.sequenceTriggered:
			logging.debug('HeartBeat.triggerStep() called.')
			# HACK: As mentioned above, we assume a single row and
			# only update the column of the heart position
			if self._heart_col != self.inputs.heart_pos:
				self._update_heart_position(
					self._heart_row, self.inputs.heart_pos)
			# Update brightness based on input values.
			if self._max_brightness != self.inputs.max_brightness:
				self._max_brightness = self.inputs.max_brightness
				self._led_values = self._compute_heart_values()
			if ((self._red != self.inputs.red) or
			    (self._green != self.inputs.green) or
			    (self._blue != self.inputs.blue)):
				self._update_color((self.inputs.red,
						    self.inputs.green,
						    self.inputs.blue))
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
