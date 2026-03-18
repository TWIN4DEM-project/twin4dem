from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class InputModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class Beliefs(InputModel):
    personal_opinion: Literal[0, 1]
    appointing_group: Literal[0, 1]
    supporting_group: Literal[0, 1]


class AgentSettings(Beliefs):
    label: str
    party: str


class InfluencerSettings(AgentSettings):
    influence: float = Field(default=0.0)


class ExecutiveSettings(InputModel):
    prime_minister: str
    ministers: list[InfluencerSettings]


class LegislativeSettings(InputModel):
    party_leaders: list[str]
    mps: list[AgentSettings]


class JudiciarySettings(InputModel):
    president: str
    judges: list[InfluencerSettings]


class AggrandisementBatchSettings(InputModel):
    executive: ExecutiveSettings
    legislative: LegislativeSettings
    judiciary: JudiciarySettings


class AggrandisementUnitAgentBeliefs(Beliefs):
    label: str


class AggrandisementUnitBeliefs(InputModel):
    ministers: list[AggrandisementUnitAgentBeliefs]
    mps: list[AggrandisementUnitAgentBeliefs]
    judges: list[AggrandisementUnitAgentBeliefs]


class AggrandisementUnit(InputModel):
    step: int
    beliefs: AggrandisementUnitBeliefs


class AggrandisementBatch(InputModel):
    start_date: datetime
    end_date: datetime
    settings: AggrandisementBatchSettings
    aggrandisement_units: list[AggrandisementUnit]
