from __future__ import annotations

from copy import deepcopy

def makeCamelCase(parts: list[str], doFirstLetter: bool = False) -> str:
	for i in range(len(parts)):
		if (i > 0 or doFirstLetter) and len(parts[i]) > 0:
			parts[i] = ''.join([parts[i][0].upper(), parts[i][1:]])
	return ''.join(parts)

def multiExtendSettings(*settings):
	# Settings contain nested dicts, lists, and scalars; preserve those existing shapes.
	i = len(settings) - 1
	out = settings[i]
	i-= 1
	while i >= 0:
		out = extendSettings(settings[i], out)
		i-=1
	return out

def extendSettings(defaults, settings):
	typesMatch = False
	for type in [list, dict]:
		if isinstance(defaults, type) and isinstance(settings, type):
			typesMatch = True
	if not typesMatch:
		return deepcopy(settings)
	out = False
	if isinstance(defaults, list):
		if len(defaults) == len(settings):
			out = []
			for i in range(len(defaults)):
				out.append(extendSettings(defaults[i], settings[i]))
		else:
			out = deepcopy(settings)
	elif isinstance(defaults, dict):
		out = {}
		for key in defaults:
			if key in settings.keys():
				out[key] = extendSettings(defaults[key], settings[key])
			else:
				out[key] = deepcopy(defaults[key])
		for key in settings:
			if not (key in defaults.keys()):
				out[key] = deepcopy(settings[key])
	return out

