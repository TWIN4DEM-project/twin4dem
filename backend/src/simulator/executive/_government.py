from __future__ import annotations

import random

from common.dto import ExecutiveSubmodelResult, SubmodelType
from simulator.executive._minister import Minister


class Government:
    def __init__(
        self,
        ministers: list[Minister],
        pact: float,
        alpha: float,
        epsilon: float,
        gamma: float,
        network: dict[int, list[int]],
    ):
        self.ministers = ministers
        self.pact = pact
        self.alpha = alpha
        self.epsilon = epsilon
        self.gamma = gamma
        self.t = 0
        self.network = network

    def _get_minister(self, mid: int) -> Minister:
        return next(m for m in self.ministers if m.id == mid)

    def step(self):
        """
        1. Compute U(i,t,for) and U(i,t,against) for each minister
        2. The utility is updated on the basis of social influence
        3. Agents vote and a decision on aggrandisement
        4. If the majority is in favour of the aggrandisement (i.e., V¯t > 0.5), the path of aggrandizement
        is randomly chosen based on the pact parameter
        """
        pm = next(m for m in self.ministers if m.is_pm)
        pm_opinion = pm.o_i

        # 1. individual utilities (no social influence yet)
        for m in self.ministers:
            peers_prev = [p.vote_prev for p in self.ministers if p.id != m.id]
            m.compute_individual_utilities(
                gamma=self.gamma,
                ref_opinion=pm_opinion,
                peers_prev_votes=peers_prev,
                g="government",
            )

        # 2. peer influence (Eq. 2)
        for m in self.ministers:
            neighbors = [self._get_minister(j) for j in self.network[m.id]]
            m.apply_peer_influence(self.alpha, neighbors)

        # 3. voting (Eq. 3)
        for m in self.ministers:
            m.decide_vote(self.epsilon)

        votes = [m.vote for m in self.ministers if m.vote is not None]
        if not votes:
            approved = False
        else:
            Vbar = sum(votes) / len(votes)
            approved = Vbar > 0.5

        # update v(i,t-1) for next step s reputation component
        # FIXME: vote_prev isn't persisted across task runs
        for m in self.ministers:
            m.vote_prev = m.vote

        path = None
        if approved:
            path = "legislative act" if random.random() < self.pact else "decree"
        return ExecutiveSubmodelResult(
            approved=approved,
            type=SubmodelType.Cabinet,
            path=path,
            votes={str(m.id): m.vote for m in self.ministers},
        )
