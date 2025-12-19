from typing import Literal, List
from pydantic import BaseModel, Field


class MPConfig(BaseModel):
    id: int
    type: Literal["MP"] = "MP"
    party: Literal["majority", "opposition", "independent"]
    influence: float = Field(..., ge=0, le=1)
    weights: List[float] = Field(..., min_length=6, max_length=6)
    opinion: int = Field(..., ge=0, le=1)
    support1: int = Field(..., ge=0, le=1)
    support2: int = Field(..., ge=0, le=1)
    is_head: bool = False
