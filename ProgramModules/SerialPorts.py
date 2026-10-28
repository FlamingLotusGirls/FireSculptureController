"""Cross-platform discovery; use Linux by-id links when they are available."""
from __future__ import annotations

import os
from pathlib import Path
import sys

from serial.tools import list_ports
from .Types import AdaptorUpdate


def discoverSerialPorts() -> list[dict]:
	devices = sorted(list_ports.comports())
	links: dict[str, str] = {}
	if sys.platform.startswith('linux'):
		for link in sorted(Path('/dev/serial/by-id').glob('*')):
			if link.exists():
				links.setdefault(os.path.realpath(link), str(link))
	ports: list[dict] = []
	for device in devices:
		identity = None
		if device.serial_number:
			identity = {'serialNumber': device.serial_number, 'vid': device.vid,
				'pid': device.pid, 'interface': device.interface}
		ports.append({'device': device.device, 'port': device.device,
			'description': device.description or device.device, 'identity': identity})
	identities = [port['identity'] for port in ports]
	for port in ports:
		identity = port['identity']
		if identity and identities.count(identity) == 1:
			port['port'] = links.get(os.path.realpath(port['device']), port['device'])
		else:
			# Missing/duplicate serial numbers cannot identify an individual adapter.
			port['identity'] = None
		serial = port['identity']['serialNumber'] if port['identity'] else 'port name only'
		port['label'] = '%s — %s — %s' % (port['description'], serial, port['port'])
	return ports


def settingsForPort(port: str) -> AdaptorUpdate:
	for item in discoverSerialPorts():
		if port in (item['port'], item['device']):
			return {'ports': [item['port']], 'identity': item['identity']}
	return {'ports': [port], 'identity': None}


def resolveSerialIdentity(identity: dict) -> str:
	matches = [port for port in discoverSerialPorts() if port['identity'] and
		all(port['identity'].get(key) == identity.get(key) for key in ('serialNumber', 'vid', 'pid'))]
	if len(matches) > 1:
		matches = [port for port in matches if port['identity']['interface'] == identity.get('interface')]
	if len(matches) != 1:
		raise OSError('Saved USB adapter %s is missing or cannot be uniquely identified' % identity['serialNumber'])
	return matches[0]['port']
