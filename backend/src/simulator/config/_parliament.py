from typing import List, Literal
from pydantic import BaseModel, Field

from ._mp import MPConfig


class ParliamentConfig(BaseModel):
    mps: List[MPConfig]
    n_party: int = Field(..., ge=1)
    n_sits: List[int] = Field(..., min_length=1)
    position_p: List[Literal["majority", "opposition"]] = Field(..., min_length=1)
    alpha: float = Field(..., ge=0.0, le=1.0)
    epsilon: float = Field(..., ge=0.0)
    gamma: float = Field(..., gt=0.0)
