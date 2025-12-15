from typing import List, Literal
from pydantic import BaseModel, Field


class MinisterConfig(BaseModel):
    id: int
    type: Literal["Minister"] = "Minister"
    party: Literal["majority", "opposition", "independent"]
    influence: float = Field(..., ge=0, le=1)
    weights: List[float] = Field(..., min_length=6, max_length=6)
    opinion: int = Field(..., ge=0, le=1)
    support1: int = Field(..., ge=0, le=1)
    support2: int = Field(..., ge=0, le=1)
    is_pm: bool = False


class GovernmentConfig(BaseModel):
    ministers: List[MinisterConfig]
    kgov: int = Field(..., ge=1)
    pact: float = Field(..., ge=0.0, le=1.0)
    alpha: float = Field(..., ge=0.0, le=1.0)
    epsilon: float = Field(..., ge=0.0)
    gamma: float = Field(..., gt=0.0)
