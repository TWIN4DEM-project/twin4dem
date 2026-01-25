from typing import Literal, Optional

from pydantic import BaseModel, Field, ConfigDict
from pydantic.alias_generators import to_camel

from common.dto._basic import SubmodelType, AggrandisementUnitPath


class SubmodelResult(BaseModel):
    type: SubmodelType
    approved: bool
    votes: dict[str, Optional[int]] = Field(default_factory=dict)


class ExecutiveSubmodelResult(SubmodelResult):
    type: Literal[SubmodelType.Cabinet]
    path: AggrandisementUnitPath


class VbarSubmodelResult(SubmodelResult):
    type: Literal[SubmodelType.Court, SubmodelType.Parliament]
    vbar: float


class SimulationStepResult(BaseModel):
    model_config = ConfigDict(
        validate_by_alias=True, validate_by_name=True, alias_generator=to_camel
    )
    step_no: int
    simulation_id: int
    results: list[ExecutiveSubmodelResult | VbarSubmodelResult]
