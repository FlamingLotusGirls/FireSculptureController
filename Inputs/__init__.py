from collections.abc import Callable
from typing import Literal, TYPE_CHECKING
from ProgramModules import utils

from .InputBase import InputBase
from .Basic import TimerPulseInput, BasicMultiInput, RandomPulseInput, RandomPulseMultiInput
from .Osc import OscMultiInput

from . import Osc, Basic
inputTypes = utils.multiExtendSettings(Basic.inputTypes, Osc.inputTypes)
availableInputTypes: dict[str, list[str]] = {}
for key in inputTypes.keys():
	subType: str | Literal[False] = False
	parts = key.split(' ')
	type = parts[-1]
	if len(parts) > 1:
		subType = parts[0]
	if not type in availableInputTypes.keys():
		availableInputTypes[type] = []
	if subType:
		availableInputTypes[type].append(subType)


if TYPE_CHECKING:
	from ProgramModules.Interfaces import Input
	_inputClasses: tuple[Callable[..., Input], ...] = (
		InputBase, TimerPulseInput, BasicMultiInput, RandomPulseInput, RandomPulseMultiInput, OscMultiInput,
	)

