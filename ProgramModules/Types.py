"""Shared value types and the existing JSON configuration shapes.

These are annotations, not validators: configuration files and runtime values stay as-is.
"""
from collections.abc import Callable, Iterable
from typing import NotRequired, TypeAlias, TypedDict

RGB: TypeAlias = tuple[int, int, int]
GridAddress: TypeAlias = list[int] | tuple[int, ...]
LogicalAddress: TypeAlias = str | int | GridAddress
AddressKey: TypeAlias = str | int | tuple[int, ...]
HardwareAddress: TypeAlias = list[int]
AddressMapping: TypeAlias = dict[str, HardwareAddress] | list[HardwareAddress] | list[list[HardwareAddress]]
OutputValue: TypeAlias = bool | int | float | str | RGB
OutputCommands: TypeAlias = Iterable[tuple[LogicalAddress, OutputValue]]
Callback: TypeAlias = Callable[..., object]


class AdaptorConfig(TypedDict):
	type: str
	ports: list[str]
	baudrate: int | str
	adaptorId: NotRequired[str]


class AdaptorUpdate(TypedDict, total=False):
	ports: list[str]
	baudrate: int | str


class ProtocolConfig(TypedDict):
	type: str
	mapping: AddressMapping
	ignoreSafeMode: NotRequired[bool]
	resendDataInterval: NotRequired[int]


class ModuleConfig(TypedDict):
	name: str
	moduleType: str
	adaptor: str
	protocol: ProtocolConfig
	moduleId: NotRequired[str]
	patternType: NotRequired[str]
	patterns: NotRequired[list[str]]
	inputs: NotRequired[dict]


class SculptureConfig(TypedDict):
	sculptureId: str
	sculptureName: str
	adaptors: dict[str, AdaptorConfig]
	modules: dict[str, ModuleConfig]
