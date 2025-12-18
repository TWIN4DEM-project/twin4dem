from __future__ import annotations

from dataclasses import dataclass

from simulator.common import Agent


@dataclass
class Minister(Agent):
    is_pm: bool = False
