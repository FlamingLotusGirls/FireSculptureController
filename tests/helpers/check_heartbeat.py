"""Exercise the HeartBeat stub through real inputs, with manual timers and no hardware."""
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))

class ManualTimer:
    instances = []

    def __init__(self, repeating, interval, function, args=False, stopWhenDone=False):
        self.interval = interval
        self.function = function
        self.stopped = False
        self.refreshes = 0
        self.instances.append(self)

    def changeInterval(self, interval):
        self.interval = interval

    def refresh(self):
        self.refreshes += 1

    def stop(self):
        self.stopped = True

import ProgramModules.Timers as timers
timers.Timer = ManualTimer
from Patterns.LED import HeartBeat, LEDGrid
from ProgramModules.InputManager import InputManager
import ProgramModules.sharedObjects as app

config = json.loads((root / 'sculptureDefinitions/serpent.json').read_text())
mapping = config['modules']['leds']['protocol']['mapping']
rows, cols = len(mapping), len(mapping[0])
assert 'HeartBeat' in config['modules']['leds']['patterns']
app.inputManager = InputManager()
pattern = HeartBeat([rows, cols], 'heartbeat-check')
updates = []
pattern.setUpdateFunction(lambda: updates.append(True))

def set_input(channel, value):
    instance, index = pattern.inputs.getInputAssignment(channel)
    app.inputManager.getInputObj(instance).setInputValue(value, index)

def assert_dark():
    for row in range(rows):
        for col in range(cols):
            assert pattern.getState(row, col) == (0, 0, 0), (row, col)

try:
    assert_dark()
    controls = pattern.getCurrentStateData()['inputs']
    assert {'heart_pos', 'max_brightness', 'red', 'green', 'blue',
            'triggerStep', 'triggerSequence'} <= controls.keys()
    json.dumps(pattern.getCurrentStateData())
    step_id, _ = pattern.inputs.getInputAssignment('triggerStep')
    step_input = app.inputManager.getInputObj(step_id)
    set_input('triggerSequence', False)
    set_input('triggerSequence', True)
    assert pattern.sequenceTriggered
    assert step_input.timer.refreshes == 1
    for position, brightness, color in [
        (1, 100, (255, 255, 255)),
        (cols - 1, 1, (0, 255, 0)),
        (cols // 2, 70, (255, 0, 0)),
    ]:
        set_input('heart_pos', position)
        set_input('max_brightness', brightness)
        for channel, value in zip(('red', 'green', 'blue'), color):
            set_input(channel, value)
        for _ in range(120):
            step_input.timer.function()
            assert_dark()
        assert pattern._heart_col == position
        assert pattern._max_brightness == brightness
        assert pattern._led_grid.getLED(0, position).color_triple == color
    assert len(updates) == 360
    assert pattern.getState(-1, 0) == (0, 0, 0)
    assert pattern.getState(0, cols) == (0, 0, 0)
finally:
    pattern.stop()

assert not app.inputManager.inputInstances
assert all(timer.stopped for timer in ManualTimer.instances)
grid = LEDGrid(1, 3, (200, 100, 50))
grid.getLED(0, 1).brightness = 0.5
assert grid.getLED(0, 1).getColorWithBrightness() == (100, 50, 25)
assert grid.getDistance((0, 0), (0, 2)) == (0, 2)
assert not {'scipy', 'numpy'} & sys.modules.keys()
print('HeartBeat controls, 360 pulses on %d LEDs, black output, renderer, and cleanup passed on %s'
      % (rows * cols, sys.version.split()[0]))
