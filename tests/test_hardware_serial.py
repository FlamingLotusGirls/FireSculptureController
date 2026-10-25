"""Real USB Serial checks, enabled only with --hardware-serial-port=PORT.

Use an adapter with no equipment attached. These tests transmit Serpent relay packets.
"""
from time import sleep

import pytest
import serial

from ProgramModules.Messenger import Messenger
from ProgramModules.Runtime import failureEvent
from ProgramModules.SafeModeController import SafeModeController
from ProgramModules.Timers import Timer
import ProgramModules.sharedObjects as app
from SculptureController import SculptureController


@pytest.fixture
def hardware_controller(request, monkeypatch):
    port = request.config.getoption('--hardware-serial-port')
    if not port:
        pytest.skip('Use --hardware-serial-port=PORT with no equipment attached')

    monkeypatch.setattr(app, 'safeMode', SafeModeController())
    monkeypatch.setattr(app, 'messenger', Messenger())
    failureEvent.clear()
    writes = []
    connections = []
    open_serial = serial.serial_for_url
    write_serial = serial.Serial.write

    def record_open(*args, **kwargs):
        connection = open_serial(*args, **kwargs)
        connections.append(connection)
        return connection

    def record_write(connection, data):
        writes.append((bytes(data), app.safeMode.isSet()))
        return write_serial(connection, data)

    monkeypatch.setattr(serial, 'serial_for_url', record_open)
    monkeypatch.setattr(serial.Serial, 'write', record_write)
    controller = SculptureController()
    # Only the explicitly selected bus uses hardware. Other adaptors use loopback.
    config = controller.sculptureDefinitions['serpent']
    for adaptor in config['adaptors'].values():
        adaptor['ports'] = ['loop://']
    config['adaptors']['flameBus']['ports'] = [port]
    try:
        controller.loadSculpture('serpent')
        state = controller.dataChannelManager.getCurrentStateData()['flameBus']
        assert state['connected'], state['lastError']
        yield controller, writes
    finally:
        assert controller.stop()
        assert all(not connection.is_open for connection in connections)
        assert not Timer.activeTimers
        assert not app.safeMode.bindings
        assert not failureEvent.is_set()


def test_real_serial_packets_and_reopen_restore_only_current_off(hardware_controller):
    controller, writes = hardware_controller
    manager = controller.dataChannelManager
    adaptor = manager.adaptors['flameBus'].adaptor
    settings = adaptor.connection.get_settings()
    assert settings['baudrate'] == 19200
    assert settings['bytesize'] == 8
    assert settings['parity'] == 'N'
    assert settings['stopbits'] == 1
    assert manager.flush()
    assert writes == []

    controller.setSafeMode(False)
    assert manager.send('poofers', [([0, 0], True), ([0, 0], False)])
    assert manager.flush()
    assert b''.join(data for data, safe in writes) == b'!0111.!0110.'
    assert all(not safe for data, safe in writes)
    writes.clear()

    assert manager.send('leds', [([0, 0], (255, 0, 0))])
    assert manager.flush()
    assert writes == []  # The Serpent LED protocol remains a stub.

    previous = adaptor.connection
    assert manager.updateSerialConnection('flameBus', {'baudrate': '19200'})
    assert manager.flush()
    assert not previous.is_open
    assert adaptor.connection.is_open
    assert b''.join(data for data, safe in writes) == b'!0110.'
    assert all(not safe for data, safe in writes)
    writes.clear()

    controller.setSafeMode(True)
    assert manager.flush()
    assert controller.stop()
    assert writes == []


def test_real_serial_safe_mode_stays_silent_through_reload_and_shutdown(hardware_controller):
    controller, writes = hardware_controller
    manager = controller.dataChannelManager
    assert app.safeMode.isSet()
    assert manager.flush()
    assert writes == []

    for module_id, module in controller.sculptureModules.items():
        for pattern in module.availablePatternNames:
            controller.doCommand(['addPattern', module_id, pattern])
    controller.doCommand(['setItemState', 'poofers', [0, 0], True])
    controller.doCommand(['setItemState', 'poofers', [0, 0], False])
    sleep(0.25)  # Let real pattern timers run with safe mode still on.
    manager.allOff()
    assert manager.flush()
    assert writes == []

    previous = manager.adaptors['flameBus'].adaptor.connection
    assert manager.updateSerialConnection('flameBus', {'baudrate': '19200'})
    assert manager.flush()
    assert not previous.is_open
    assert manager.adaptors['flameBus'].adaptor.connection.is_open
    assert writes == []

    controller.loadSculpture('serpent')
    assert all(not writer.is_alive() for writer in manager.adaptors.values())
    manager = controller.dataChannelManager
    assert manager.flush()
    assert manager.getCurrentStateData()['flameBus']['connected']
    assert app.safeMode.isSet()
    assert controller.stop()
    assert all(not writer.is_alive() for writer in manager.adaptors.values())
    assert writes == []
