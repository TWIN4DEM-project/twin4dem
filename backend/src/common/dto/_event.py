from typing import Literal

from pydantic import BaseModel

from common.dto._basic import EventType
from common.dto._result import SimulationStepResult


class ChannelEventModel(BaseModel):
    type: EventType


class StepFinishedEvent(ChannelEventModel):
    type: Literal[EventType.StepFinished] = EventType.StepFinished
    payload: SimulationStepResult
