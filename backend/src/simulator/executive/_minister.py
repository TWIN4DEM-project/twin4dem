from __future__ import annotations

from dataclasses import dataclass

from simulator.common import Agent


@dataclass
class Minister(Agent):
    is_pm: bool = False

    def __post_init__(self):
        self.T_i = "Minister"
