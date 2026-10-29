"""Settings survive new controllers; no test opens physical serial hardware."""
from copy import deepcopy
import json
from time import monotonic, sleep

import pytest

import flaskServer as web
from ProgramModules import Adaptors
from ProgramModules.Messenger import Messenger
from ProgramModules.Runtime import engineLock, failureEvent
from ProgramModules.SafeModeController import SafeModeController
from ProgramModules.SettingsStore import SettingsStore
from ProgramModules.Timers import Timer
import ProgramModules.sharedObjects as app
from SculptureController import SculptureController


@pytest.fixture
def controllers(monkeypatch):
    monkeypatch.setattr(app, 'safeMode', SafeModeController())
    monkeypatch.setattr(app, 'messenger', Messenger())
    failureEvent.clear()
    created = []

    def create():
        controller = SculptureController()
        for definition in controller.sculptureDefinitions.values():
            for adaptor in definition['adaptors'].values():
                adaptor['ports'] = ['loop://']
        created.append(controller)
        return controller

    yield create
    for controller in reversed(created):
        controller.stop()
    assert not Timer.activeTimers
    assert not failureEvent.is_set()


def set_channel(controller, pattern, channel, value):
    instance, index = pattern.inputs.getInputAssignment(channel)
    controller.doCommand(['setInputValue', instance, value, index])


def test_patterns_parameters_rows_enabled_outputs_and_usb_survive_restart(controllers):
    controller = controllers()
    controller.loadSculpture('serpent')
    with engineLock:
        chase_id = controller.doCommand(['addPattern', 'poofers', 'Chase'])
        controller.doCommand(['addPattern', 'poofers', 'AllPoof'])
        led_id = controller.doCommand(['addPattern', 'leds', 'HeartBeat'])
        chase = controller.sculptureModules['poofers'].patterns[chase_id]
        led = controller.sculptureModules['leds'].patterns[led_id]
        set_channel(controller, chase, 'numberOn', 4)
        set_channel(controller, chase, 'stepping', 3)
        set_channel(controller, chase, 'triggerStep', 975)
        set_channel(controller, chase, 'stayOnTime', 500)
        set_channel(controller, chase, 'reverse', True)
        set_channel(controller, chase, 'triggerSequence', False)
        set_channel(controller, led, 'red', 123)
        set_channel(controller, led, 'max_brightness', 42)
        controller.doCommand(['toggleRowSelection', 'leds', led_id, 0])
        controller.doCommand(['toggleEnable', 'poofers', [0, 4]])
        controller.doCommand(['updateSerialConnection', 'flameBus', {'ports': ['loop://'], 'baudrate': 38400}])
    saved = controller.settingsStore.load('serpent')
    assert [pattern['type'] for pattern in saved['modules']['poofers']['patterns']] == ['Chase', 'AllPoof']
    controller.stop()
    restored = controllers()
    restored.loadSculpture('serpent')
    with engineLock:
        poofers = restored.sculptureModules['poofers']
        chase = next(iter(poofers.patterns.values()))
        assert (chase.inputs.numberOn, chase.inputs.stepping, chase.inputs.reverse) == (4, 3, True)
        assert chase.inputs.triggerSequence is False
        assert chase.inputs.stayOnTime == 500
        timer_id, _ = chase.inputs.getInputAssignment('triggerStep')
        assert restored.inputManager.getInputObj(timer_id).timer.interval == 975
        led = next(iter(restored.sculptureModules['leds'].patterns.values()))
        assert (led.inputs.red, led.inputs.max_brightness) == (123, 42)
        assert restored.sculptureModules['leds'].patternRowSettings[led_id] == [False]
        assert poofers.enabledStatus[0][4] is False
        assert restored.getCurrentStateData()['adaptors']['flameBus']['baudrate'] == 38400
        assert app.safeMode.isSet()
        assert not any(any(row) for row in poofers.currentOutputState)


def test_shared_input_bindings_global_controls_and_removals_survive(controllers):
    controller = controllers()
    controller.loadSculpture('serpent')
    first = controller.doCommand(['addPattern', 'poofers', 'Chase'])
    second = controller.doCommand(['addPattern', 'poofers', 'Chase'])
    controller.doCommand(['addGlobalInput', {'type': 'multi', 'subType': 'basic', 'number': 2,
                                          'default': [2, 3], 'min': 1, 'max': 5}])
    shared_id = next(iter(controller.globalInputs))
    for pattern in (first, second):
        controller.doCommand(['reassignPatternInput', 'poofers', pattern, 'numberOn', shared_id, 1])
    controller.doCommand(['setInputValue', shared_id, 4, 1])
    controller.stop()
    restored = controllers()
    restored.loadSculpture('serpent')
    patterns = list(restored.sculptureModules['poofers'].patterns.values())
    assignments = [pattern.inputs.getInputAssignment('numberOn') for pattern in patterns]
    assert assignments[0] == assignments[1]
    assert assignments[0][0] in restored.globalInputs
    assert [pattern.inputs.numberOn for pattern in patterns] == [4, 4]
    for pattern_id in list(restored.sculptureModules['poofers'].patterns):
        restored.doCommand(['removePattern', 'poofers', pattern_id])
    restored.doCommand(['removeGlobalInput', assignments[0][0]])
    restored.loadSculpture('serpent')
    assert restored.sculptureModules['poofers'].patterns == {}
    assert restored.globalInputs == {}


def test_sculptures_have_separate_settings_and_reloading_restores_them(controllers):
    controller = controllers()
    controller.loadSculpture('serpent')
    controller.doCommand(['addPattern', 'poofers', 'AllPoof'])
    controller.loadSculpture('aota')
    assert controller.sculptureModules['poofers'].patterns == {}
    controller.doCommand(['addPattern', 'poofers', 'Chase'])
    controller.loadSculpture('serpent')
    assert list(controller.sculptureModules['poofers'].patternTypes.values()) == ['AllPoof']


def test_momentary_presses_and_run_mode_are_not_replayed(controllers):
    controller = controllers()
    controller.loadSculpture('serpent')
    pattern_id = controller.doCommand(['addPattern', 'poofers', 'AllPoof'])
    pattern = controller.sculptureModules['poofers'].patterns[pattern_id]
    controller.setSafeMode(False)
    set_channel(controller, pattern, 'poofButton', True)
    controller.doCommand(['setItemState', 'poofers', [0, 1], True])
    saved = controller.settingsStore.load('serpent')
    assert 'safeMode' not in saved
    controller.stop()
    restored = controllers()
    restored.loadSculpture('serpent')
    pattern = restored.sculptureModules['poofers'].patterns[pattern_id]
    assert pattern.inputs.poofButton is False
    assert pattern.poofState is False
    assert app.safeMode.isSet()


def test_applied_image_selection_restores_without_replaying_update_button(controllers):
    controller = controllers()
    controller.loadSculpture('serpent')
    pattern_id = controller.doCommand(['addPattern', 'leds', 'FromImage'])
    pattern = controller.sculptureModules['leds'].patterns[pattern_id]
    image = list(pattern.supported_images)[-1]
    set_channel(controller, pattern, 'imageSelection', image)
    set_channel(controller, pattern, 'updateButton', True)
    controller.stop()
    restored = controllers()
    restored.loadSculpture('serpent')
    pattern = restored.sculptureModules['leds'].patterns[pattern_id]
    assert pattern.getState(0, 0) == image
    assert pattern.inputs.updateButton is False


def test_settings_write_failure_is_visible_without_stopping_controller(controllers, monkeypatch):
    controller = controllers()
    controller.loadSculpture('serpent')
    controller.doCommand(['addPattern', 'poofers', 'AllPoof'])
    previous = deepcopy(controller.settingsStore.load('serpent'))

    def cannot_replace(*args):
        raise OSError('disk unavailable')

    monkeypatch.setattr('ProgramModules.SettingsStore.os.replace', cannot_replace)
    monkeypatch.setattr(web, 'sculpture', controller)
    client = web.flaskApp.test_client()
    result = client.post('/doCommand', json=['addPattern', 'poofers', 'Chase'])
    assert result.status_code == 200
    assert 'could not be saved' in result.json['settingsError']
    assert 'disk unavailable' in client.get('/connectionStatus').json['settingsError']
    assert controller.settingsStore.load('serpent') == previous
    assert list(controller.settingsStore.directory.glob('*.tmp')) == []
    assert len(controller.sculptureModules['poofers'].patterns) == 2


def test_corrupt_saved_json_reports_error_and_loads_defaults(controllers):
    controller = controllers()
    controller.settingsStore.directory.mkdir(parents=True)
    (controller.settingsStore.directory / 'serpent.json').write_text('{invalid')
    controller.loadSculpture('serpent')
    assert 'Could not load saved settings' in controller.settingsError
    assert controller.sculptureModules['poofers'].patterns == {}
    assert app.safeMode.isSet()


def test_late_writer_error_is_reported_independently_of_accepted_command(controllers, monkeypatch):
    controller = controllers()
    controller.loadSculpture('serpent')
    monkeypatch.setattr(web, 'sculpture', controller)
    adaptor = controller.dataChannelManager.adaptors['flameBus'].adaptor

    def fail_write(data):
        adaptor.lastError = 'USB adapter unplugged during write'
        adaptor._closeConnection()
        return False

    monkeypatch.setattr(adaptor, 'transmitData', fail_write)
    monkeypatch.setattr(adaptor, 'connect', lambda: False)
    client = web.flaskApp.test_client()
    assert client.post('/doCommand', json=['setSafeMode', False]).status_code == 200
    assert client.post('/doCommand', json=['setItemState', 'poofers', [0, 0], True]).status_code == 200
    deadline = monotonic() + 1
    while monotonic() < deadline:
        status = client.get('/connectionStatus').json
        bus = next(bus for bus in status['connections'] if bus['adaptorId'] == 'flameBus')
        if not bus['connected']:
            break
        sleep(0.01)
    assert status['safeMode'] is False
    assert bus['connected'] is False
    assert bus['deliveryPending'] is True
    assert 'unplugged' in bus['lastError']
    assert 'delivery failed' in bus['writerError']
    controller.setSafeMode(True)


def test_store_does_not_rewrite_unchanged_settings(tmp_path):
    store = SettingsStore(tmp_path)
    settings = {'version': 1, 'adaptors': {}, 'modules': {}, 'inputs': {}, 'globalInputs': []}
    store.save('serpent', settings)
    before = (tmp_path / 'serpent.json').stat().st_mtime_ns
    store.save('serpent', settings)
    assert (tmp_path / 'serpent.json').stat().st_mtime_ns == before
