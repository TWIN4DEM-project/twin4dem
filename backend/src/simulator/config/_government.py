from typing import List, Literal
from pydantic import BaseModel, Field

from ._minister import MinisterConfig


class GovernmentConfig(BaseModel):
    action: Literal["start", "step"]
    ministers: List[MinisterConfig]
    kgov: int = Field(..., ge=1)
    pact: float = Field(..., ge=0.0, le=1.0)
    alpha: float = Field(..., ge=0.0, le=1.0)
    epsilon: float = Field(..., ge=0.0)
    gamma: float = Field(..., gt=0.0)
