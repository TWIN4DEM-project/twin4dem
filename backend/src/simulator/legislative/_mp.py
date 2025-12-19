from __future__ import annotations

from dataclasses import dataclass

from simulator.common import Agent


@dataclass
class MP(Agent):
    is_head: bool = False
