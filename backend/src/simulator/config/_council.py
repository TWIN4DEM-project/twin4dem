from typing import List, Literal
from pydantic import BaseModel, Field

from ._judge import JudgeConfig


class CouncilConfig(BaseModel):
    action: Literal["start", "step"]
    judges: List[JudgeConfig]
    alpha: float = Field(..., ge=0.0, le=1.0)
    epsilon: float = Field(..., ge=0.0)
    gamma: float = Field(..., gt=0.0)
