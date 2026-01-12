from __future__ import annotations

from dataclasses import dataclass

from simulator.common import Agent


@dataclass
class Judge(Agent):
    is_president: bool = False

    def __post_init__(self):
        self.T_i = "Judge"
