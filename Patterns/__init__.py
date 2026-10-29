from .PatternBase import *
from .Poof import *
from .LED import *

from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from ProgramModules.Interfaces import Pattern
	_patternClasses: tuple[type[Pattern], ...] = (Chase, Twister, AllPoof, RandomPoof, HeartBeat, FromImage)
