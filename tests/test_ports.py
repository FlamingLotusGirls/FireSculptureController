"""Use pySerial metadata fixtures for Linux, macOS, and Windows."""
from pathlib import Path

import pytest
from serial.tools.list_ports_common import ListPortInfo

import flaskServer as web
from ProgramModules import Adaptors, SerialPorts


def usb(device, serial='A50285BI', interface=None):
    info = ListPortInfo(device)
    info.description = 'FTDI USB Serial'
    info.vid, info.pid = 0x0403, 0x6001
    info.serial_number = serial
    info.interface = interface
    return info


@pytest.mark.parametrize('platform,device', [('darwin', '/dev/cu.usbserial-A50285BI'), ('win32', 'COM7')])
def test_native_names_and_hardware_identity(platform, device, monkeypatch):
    monkeypatch.setattr(SerialPorts.sys, 'platform', platform)
    monkeypatch.setattr(SerialPorts.list_ports, 'comports', lambda: [usb(device)])
    port = SerialPorts.discoverSerialPorts()[0]
    assert port['port'] == device
    assert port['identity']['serialNumber'] == 'A50285BI'
    assert device in port['label']


def test_linux_prefers_by_id_and_does_not_list_alias_twice(monkeypatch, tmp_path):
    native = tmp_path / 'ttyUSB0'
    native.touch()
    links = tmp_path / 'by-id'
    links.mkdir()
    alias = links / 'usb-FTDI_A50285BI-if00-port0'
    alias.symlink_to(native)
    monkeypatch.setattr(SerialPorts.sys, 'platform', 'linux')
    monkeypatch.setattr(SerialPorts, 'Path', lambda path: links)
    monkeypatch.setattr(SerialPorts.list_ports, 'comports', lambda: [usb(str(native))])
    ports = SerialPorts.discoverSerialPorts()
    assert len(ports) == 1
    assert ports[0]['port'] == str(alias)
    assert SerialPorts.settingsForPort(str(native))['ports'] == [str(alias)]


def test_saved_identity_follows_renumbering_and_does_not_fall_back_to_wrong_device(monkeypatch):
    monkeypatch.setattr(SerialPorts.list_ports, 'comports', lambda: [usb('/dev/cu.old', interface='UART')])
    identity = SerialPorts.discoverSerialPorts()[0]['identity']
    monkeypatch.setattr(SerialPorts.list_ports, 'comports', lambda: [usb('/dev/cu.new'), usb('/dev/cu.old', 'OTHER')])
    assert SerialPorts.resolveSerialIdentity(identity) == '/dev/cu.new'
    monkeypatch.setattr(SerialPorts.list_ports, 'comports', lambda: [usb('/dev/cu.old', 'OTHER')])
    with pytest.raises(OSError, match='missing'):
        SerialPorts.resolveSerialIdentity(identity)


def test_missing_and_duplicate_serials_are_explicitly_port_name_only(monkeypatch):
    monkeypatch.setattr(SerialPorts.list_ports, 'comports', lambda: [usb('COM1', None), usb('COM2'), usb('COM3')])
    ports = SerialPorts.discoverSerialPorts()
    assert all(port['identity'] is None for port in ports)
    assert all('port name only' in port['label'] for port in ports)


def test_discovery_endpoint_does_not_open_any_serial_port(monkeypatch):
    monkeypatch.setattr(SerialPorts.list_ports, 'comports', lambda: [usb('/dev/cu.usbserial-A50285BI')])
    def forbidden(*args, **kwargs):
        pytest.fail('Discovery opened a physical serial port')
    monkeypatch.setattr(Adaptors.serial, 'serial_for_url', forbidden)
    response = web.flaskApp.test_client().get('/serialPorts')
    assert response.status_code == 200
    assert response.json['ports'][0]['identity']['serialNumber'] == 'A50285BI'


def test_discovery_errors_are_visible(monkeypatch):
    def broken():
        raise OSError('enumeration unavailable')
    monkeypatch.setattr(SerialPorts.list_ports, 'comports', broken)
    response = web.flaskApp.test_client().get('/serialPorts')
    assert response.status_code == 200
    assert response.json['ports'] == []
    assert 'enumeration unavailable' in response.json['error']


def test_identity_reconnect_never_opens_saved_path_when_device_is_missing(monkeypatch):
    monkeypatch.setattr(SerialPorts.list_ports, 'comports', lambda: [usb('COM2', 'OTHER')])
    opened = []
    monkeypatch.setattr(Adaptors.serial, 'serial_for_url', lambda *args, **kwargs: opened.append(args))
    adaptor = Adaptors.SerialAdaptor({'type': 'serial', 'adaptorId': 'test', 'ports': ['COM2'],
        'baudrate': 19200, 'identity': {'vid': 0x0403, 'pid': 0x6001, 'serialNumber': 'SAVED', 'interface': None}})
    assert opened == []
    assert adaptor.getCurrentStateData()['connected'] is False
    assert 'SAVED' in adaptor.lastError
    adaptor.stop()
