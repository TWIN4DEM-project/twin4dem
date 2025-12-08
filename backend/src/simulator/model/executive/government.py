from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict
import random
from ..agent import Agent
from ..config import MinisterConfig, GovernmentConfig


@dataclass
class Minister(Agent):
    is_pm: bool = False

    @classmethod
    def from_config(cls, config: MinisterConfig) -> Minister:
        return cls(
            id=config.id,
            T_i=config.type,
            P_i=config.party,
            S_i=config.influence,
            W=config.weights,
            o_i=config.opinion,
            o_sup1=config.support1,
            o_sup2=config.support2,
            is_pm=config.is_pm,
        )

class Government:
    def __init__(
            self,
            ministers: List[Minister],
            kgov: int,
            pact: float,
            alpha: float,
            epsilon: float,
            gamma: float,
    ):
        self.ministers = ministers
        self.kgov = kgov
        self.pact = pact
        self.alpha = alpha
        self.epsilon = epsilon
        self.gamma = gamma
        self.t = 0

        self.network: Dict[int, List[int]] = self._build_network()

    @classmethod
    def from_config(cls, config: GovernmentConfig) -> Government:
        ministers = [Minister.from_config(m_cfg) for m_cfg in config.ministers]

        return cls(
            ministers=ministers,
            kgov=config.kgov,
            pact=config.pact,
            alpha=config.alpha,
            epsilon=config.epsilon,
            gamma=config.gamma,
        )

    # build gov network: PM connected to all, others random up to kgov
    def _build_network(self) -> Dict[int, List[int]]:
        ids = [m.id for m in self.ministers]
        pm = next(m for m in self.ministers if m.is_pm)
        pm_id = pm.id

        net = {i: set() for i in ids}

        # Prime Minister linked to everyone
        for i in ids:
            if i == pm_id:
                continue
            net[pm_id].add(i)
            net[i].add(pm_id)

        # Other ministers: extra random neighbors up to kgov
        for m in self.ministers:
            if m.is_pm:
                continue

            current = net[m.id]
            if len(current) >= self.kgov:
                continue

            # only nodes that:
            #   - are not already connected to m
            #   - are not m
            #   - have degree < kgov themselves
            candidates = [
                i for i in ids
                if i != m.id
                   and i not in current
                   and len(net[i]) < self.kgov
            ]

            random.shuffle(candidates)

            # compute how many more neighbors m can still take
            max_needed = self.kgov - len(current)
            needed = random.randint(1, max_needed)

            for j in candidates:
                if needed <= 0:
                    break
                net[m.id].add(j)
                net[j].add(m.id)
                needed -= 1

        return {i: list(neigh) for i, neigh in net.items()}


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
                g="government"
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
            path = None
        else:
            Vbar = sum(votes) / len(votes)
            approved = Vbar > 0.5

            if approved:
                # 4. choose path of aggrandisement using pact
                path = "legislative act" if random.random() < self.pact else "decree"
            else:
                path = None

        # update v(i,t-1) for next step s reputation component
        for m in self.ministers:
            m.vote_prev = m.vote

        self.t += 1

        return {
            "t": self.t,
            "approved": approved,
            "path": path,
            "votes": {str(m.id): m.vote for m in self.ministers},
        }
