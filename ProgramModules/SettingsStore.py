"""Per-sculpture settings, replaced atomically after each user edit."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile


class SettingsStore:
	def __init__(self, directory: Path) -> None:
		self.directory = directory

	def _path(self, sculptureId: str) -> Path:
		# IDs also come from JSON definitions; never interpret them as paths.
		from urllib.parse import quote
		return self.directory / (quote(sculptureId, safe='') + '.json')

	def load(self, sculptureId: str) -> dict | None:
		try:
			with self._path(sculptureId).open(encoding='utf-8') as source:
				settings = json.load(source)
		except FileNotFoundError:
			return None
		if not isinstance(settings, dict) or settings.get('version') != 1:
			raise ValueError('Unsupported saved settings format')
		if not all(isinstance(settings.get(key), dict) for key in ('adaptors', 'modules', 'inputs')):
			raise ValueError('Invalid saved settings')
		if not isinstance(settings.get('globalInputs'), list):
			raise ValueError('Invalid saved global inputs')
		return settings

	def save(self, sculptureId: str, settings: dict) -> None:
		encoded = json.dumps(settings, indent=2) + '\n'
		try:
			if self._path(sculptureId).read_text(encoding='utf-8') == encoded:
				return
		except FileNotFoundError:
			pass
		self.directory.mkdir(parents=True, exist_ok=True)
		temporary = None
		try:
			with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
				dir=self.directory, prefix='.settings-', suffix='.tmp', delete=False) as output:
				temporary = output.name
				output.write(encoded)
				output.flush()
				os.fsync(output.fileno())
			os.replace(temporary, self._path(sculptureId))
		finally:
			if temporary is not None and os.path.exists(temporary):
				os.unlink(temporary)
