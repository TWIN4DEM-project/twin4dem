from dataclasses import dataclass
from typing import List, Optional, Sequence
import math


@dataclass
class Agent:
    id: int
    T_i: str  # type of agent (e.g., Prime minister, Minister, MP, Judge)
    P_i: str  # reference party for the agent: majority, opposition, independent
    S_i: float  # influence of each agent on its network neighbours
    W: List[float]  # individual weights of the six components, the sum should be 1
    o_i: float  # personal political opinion {for, against}
    o_sup1: float  # opinion of the group that supports the agent (e.g., party)
    o_sup2: float  # opinion of the second group that supports the agent (e.g., interest group)

    U_for: float = 0.0  # U(i,t,for) before peer influence
    U_against: float = 0.0  # U(i,t,against) before peer influence
    U_for_star: float = 0.0  # U*(i,t,for) after peer influence
    U_against_star: float = 0.0  # U*(i,t,against) after peer influence

    vote_prev: Optional[int] = None  # v(i,t-1) vote at time t-1
    vote: Optional[int] = None  # v(i,t) vote at time t

    def _u1_personal_opinion(self, d: int) -> float:
        # Eq. 4 – matching d with oi, d = decision (for=1, against=0)
        return 1.0 if d == self.o_i else 0.0

    def _u2_power_of_office(self, d: int, g: str) -> float:
        # Eq. 5 – for ministers, g = {government, parlamient, courts}
        if d == 1:
            return 1.0 if g == "government" else 0.0
        else:
            return 1.0 if g in ("parliament", "courts") else 0.0

    def _logistic(self, x: float, gamma: float) -> float:
        return 1.0 / (1.0 + math.exp(-gamma * x))

    def _u3_stay_in_office(self, d: int, gamma: float) -> float:
        # Eq. 6 – compare decision with osup1
        c = 1 if d == self.o_sup1 else -1
        return self._logistic(c, gamma)

    def _u4_prestige_office(self, d: int, gamma: float, pm_oi: float) -> float:
        # Same structure as Eq. 6 but compare to PM opinion (for ministers)
        c = 1 if d == pm_oi else -1
        return self._logistic(c, gamma)

    def _u5_support_groups(self, d: int) -> float:
        # Eq. 7 – congruence with supporting groups osup2
        return 1.0 if d == self.o_sup2 else 0.0

    def _u6_reputation(self, peers_prev_votes: Sequence[Optional[int]]) -> float:
        # Eq. 8 – fraction of peers that voted like i at t-1
        if self.vote_prev is None:
            return 0.5  # neutral if no history yet

        same = 0
        total = 0
        for vj in peers_prev_votes:
            if vj is None:
                continue
            total += 1
            if vj == self.vote_prev:
                same += 1
        return same / total if total > 0 else 0.5

    def compute_individual_utilities(self, gamma: float, ref_opinion: float, peers_prev_votes: Sequence[Optional[int]],
                                     g: str):
        """
        Compute U(i,t,for) and U(i,t,against) BEFORE peer influence (Eq. 1).
        ref_opinion: opinion of 'powerful' actor for component 4
                     - PM for ministers
                     - party head for MPs
                     - court president for judges
        """
        u_for = (
                self.W[0] * self._u1_personal_opinion(1) +
                self.W[1] * self._u2_power_of_office(1, g) +
                self.W[2] * self._u3_stay_in_office(1, gamma) +
                self.W[3] * self._u4_prestige_office(1, gamma, ref_opinion) +
                self.W[4] * self._u5_support_groups(1) +
                self.W[5] * self._u6_reputation(peers_prev_votes)
        )

        u_against = (
                self.W[0] * self._u1_personal_opinion(0) +
                self.W[1] * self._u2_power_of_office(0, g) +
                self.W[2] * self._u3_stay_in_office(0, gamma) +
                self.W[3] * self._u4_prestige_office(0, gamma, ref_opinion) +
                self.W[4] * self._u5_support_groups(0) +
                self.W[5] * self._u6_reputation(peers_prev_votes)
        )
        self.U_for = u_for
        self.U_against = u_against

    def apply_peer_influence(self, alpha: float, neighbors: Sequence["Agent"]) -> None:
        """
        Apply social influence (Eq. 2).
        Ministers & judges: mix own utility with weighted utilities of neighbors.
        MPs: no peer influence in this version.
        """
        if self.T_i == "MP" or not neighbors:
            # No peer influence
            self.U_for_star = self.U_for
            self.U_against_star = self.U_against
            return

        if self.T_i in ["Minister", "Judge"]:
            peer_for = sum(neigh.S_i * neigh.U_for for neigh in neighbors) / sum(neigh.S_i for neigh in neighbors)
            peer_against = sum(neigh.S_i * neigh.U_against for neigh in neighbors) / sum(
                neigh.S_i for neigh in neighbors)

            self.U_for_star = alpha * self.U_for + (1 - alpha) * peer_for
            self.U_against_star = alpha * self.U_against + (1 - alpha) * peer_against

    def decide_vote(self, epsilon: float) -> None:
        """
        Decide vote based on final utilities (Eq. 3).
        """
        if self.U_for_star - self.U_against_star > epsilon:
            self.vote = 1
        elif self.U_for_star - self.U_against_star < -epsilon:
            self.vote = 0
        else:
            self.vote = None  # Abstain