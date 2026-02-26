from __future__ import annotations

from common.dto import VbarSubmodelResult, SubmodelType
from simulator.judiciary._judge import Judge


class Council:
    def __init__(
        self,
        judges: list[Judge],
        alpha: float,
        epsilon: float,
        gamma: float,
        network: dict[int, list[int]],
        prev_votes: dict[str, int],
    ):
        self.judges = judges
        self.alpha = alpha
        self.epsilon = epsilon
        self.gamma = gamma
        self.t = 0
        self.network = network
        self.prev_votes = prev_votes

    def _get_judge(self, jid: int) -> Judge:
        return next(j for j in self.judges if j.id == jid)

    def step(self) -> VbarSubmodelResult:
        """
        1. if executive did NOT initiate OR the form is legislative act => skip -- this is decided in the Celery task
        2. Compute U(i,t,for) and U(i,t,against) for each judge
        3. The utility is updated on the basis of social influence
        4. Agents vote and a decision on aggrandisement
        5. If the majority is in favour of the aggrandisement (i.e., V¯t > 0.5), the path of aggrandizement
        is randomly chosen based on the pact parameter
        """
        pres = next(m for m in self.judges if m.is_president)
        pres_opinion = pres.o_i

        # 2) compute individual utilities (no peer influence yet)
        for j in self.judges:
            peers_prev = [v for k, v in self.prev_votes.items() if k != str(j.id)]
            j.compute_individual_utilities(
                gamma=self.gamma,
                ref_opinion=pres_opinion,  # prestige compares to president (Section 2.2.4)
                peers_prev_votes=peers_prev,
                g="council",  # power-of-office group is courts (Eq. 5)
            )

        # 3) peer influence (Eq. 2)
        for m in self.judges:
            neighbors = [self._get_judge(j) for j in self.network[m.id]]
            m.apply_peer_influence(self.alpha, neighbors)

        # 4) vote (Eq. 3)
        for j in self.judges:
            j.decide_vote(self.epsilon)

        # 5) majority rule ignoring abstentions
        votes = [j.vote for j in self.judges if j.vote is not None]
        if votes:
            vbar = sum(votes) / len(votes)
            approved = vbar > 0.5
        else:
            vbar = None
            approved = False

        return VbarSubmodelResult(
            approved=approved,
            votes={str(j.id): j.vote for j in self.judges},
            type=SubmodelType.Court,
            vbar=vbar,
        )
