from enum import StrEnum
from typing import Literal, Optional


class SubmodelType(StrEnum):
    Cabinet = "cabinet"
    Parliament = "parliament"
    Court = "court"


type AggrandisementUnitPath = Optional[Literal["decree", "legislative act"]]


class EventType(StrEnum):
    StepFinished = "step.finished"
