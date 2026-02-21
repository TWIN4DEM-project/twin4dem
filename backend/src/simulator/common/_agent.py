from dataclasses import dataclass, field
from typing import Optional, Sequence, Callable
import math

from typing import Iterable


class Weights(list[float]):

    def __init__(self, values: Iterable[float]):
        super().__init__(values)
        self._validate()

    def _validate(self) -> None:
        if len(self) != 6:
            raise ValueError(f"Weights must have length 6, got {len(self)}")
        total = sum(self)
        if not math.isclose(total, 1.0, rel_tol=1e-3, abs_tol=1e-3):
            raise ValueError(f"Weights must sum to 1. Got {total}")


@dataclass
class AgentBelief:
    o_i: float  # personal political opinion {for, against}
    o_sup1: float  # opinion of the group that supports the agent (e.g., party)
    o_sup2: float  # opinion of the second group that supports the agent (e.g., interest group)


@dataclass
class StepState:
    pre_for: float = 0.0  # U(i,t,for) before peer influence
    pre_against: float = 0.0  # U(i,t,against) before peer influence
    post_for: float = 0.0  # U*(i,t,for) after peer influence
    post_against: float = 0.0  # U*(i,t,against) after peer influence
    vote_prev: Optional[int] = None  # v(i,t-1) vote at time t-1
    vote: Optional[int] = None  # v(i,t) vote at time t


@dataclass(frozen=True)
class UtilityCalculator:
    weights: Weights
    belief: AgentBelief
    vote_prev: Optional[int]

    def _u1_personal_opinion(self, d: int) -> float:
        # Eq. 4 - matching d with oi, d = decision (for=1, against=0)
        return 1.0 if d == self.belief.o_i else 0.0

    def _u2_power_of_office(self, d: int, g: str) -> float:
        # Eq. 5 - for ministers, g = {government, parliament, courts}
        if d == 1:
            return 1.0 if g == "government" else 0.0
        return 1.0 if g in ("parliament", "courts") else 0.0

    def _logistic(self, x: float, gamma: float) -> float:
        return 1.0 / (1.0 + math.exp(-gamma * x))

    def _u3_stay_in_office(self, d: int, gamma: float) -> float:
        # Eq. 6 - compare decision with osup1
        c = 1 if d == self.belief.o_sup1 else -1
        return self._logistic(c, gamma)

    def _u4_prestige_office(self, d: int, gamma: float, pm_oi: float) -> float:
        # Same structure as Eq. 6 but compare to PM opinion (for ministers)
        c = 1 if d == pm_oi else -1
        return self._logistic(c, gamma)

    def _u5_support_groups(self, d: int) -> float:
        # Eq. 7 - congruence with supporting groups osup2
        return 1.0 if d == self.belief.o_sup2 else 0.0

    def _u6_reputation(self, peers_prev_votes: Sequence[Optional[int]]) -> float:
        # Eq. 8 - fraction of peers that voted like i at t-1
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

    def utility_for_decision(
        self,
        d: int,
        gamma: float,
        ref_opinion: float,
        peers_prev_votes: Sequence[Optional[int]],
        g: str,
    ) -> float:
        return (
            self.weights[0] * self._u1_personal_opinion(d)
            + self.weights[1] * self._u2_power_of_office(d, g)
            + self.weights[2] * self._u3_stay_in_office(d, gamma)
            + self.weights[3] * self._u4_prestige_office(d, gamma, ref_opinion)
            + self.weights[4] * self._u5_support_groups(d)
            + self.weights[5] * self._u6_reputation(peers_prev_votes)
        )


@dataclass
class Agent:
    id: int
    T_i: str  # type of agent (e.g., Prime minister, Minister, MP, Judge)
    P_i: str  # reference party for the agent: majority, opposition, independent
    S_i: float  # influence of each agent on its network neighbours
    W: Weights  # individual weights of the six components, the sum should be 1
    belief: AgentBelief
    step_state: StepState = field(default_factory=StepState)

    def compute_individual_utilities(
        self,
        gamma: float,
        ref_opinion: float,
        peers_prev_votes: Sequence[Optional[int]],
        g: str,
    ):
        """
        Compute U(i,t,for) and U(i,t,against) BEFORE peer influence (Eq. 1).
        ref_opinion: opinion of 'powerful' actor for component 4
                     - PM for ministers
                     - party head for MPs
                     - court president for judges
        """
        calculator = UtilityCalculator(self.W, self.belief, self.step_state.vote_prev)
        self.step_state.pre_for = calculator.utility_for_decision(
            1, gamma, ref_opinion, peers_prev_votes, g
        )
        self.step_state.pre_against = calculator.utility_for_decision(
            0, gamma, ref_opinion, peers_prev_votes, g
        )

    def _weighted_peer_average(
        self, neighbors: Sequence["Agent"], value: Callable[["Agent"], float]
    ) -> float:
        total_w = sum(n.S_i for n in neighbors)
        return sum(n.S_i * value(n) for n in neighbors) / total_w

    def _calculate_u_star(self, alpha: float, own: float, peer: float) -> float:
        return alpha * own + (1 - alpha) * peer

    def apply_peer_influence(self, alpha: float, neighbors: Sequence["Agent"]) -> None:
        """
        Apply social influence (Eq. 2).
        Ministers & judges: mix own utility with weighted utilities of neighbors.
        MPs: no peer influence in this version.
        """
        if self.T_i == "MP" or not neighbors:
            # No peer influence
            self.step_state.post_for = self.step_state.pre_for
            self.step_state.post_against = self.step_state.pre_against
            return

        if self.T_i in ("Minister", "Judge"):
            peer_for = self._weighted_peer_average(
                neighbors, lambda a: a.step_state.pre_for
            )
            peer_against = self._weighted_peer_average(
                neighbors, lambda a: a.step_state.pre_against
            )

            self.step_state.post_for = self._calculate_u_star(
                alpha, self.step_state.pre_for, peer_for
            )
            self.step_state.post_against = self._calculate_u_star(
                alpha, self.step_state.pre_against, peer_against
            )

    def decide_vote(self, epsilon: float) -> None:
        """
        Decide vote based on final utilities (Eq. 3).
        """
        if self.step_state.post_for - self.step_state.post_against > epsilon:
            self.step_state.vote = 1
        elif self.step_state.post_for - self.step_state.post_against < -epsilon:
            self.step_state.vote = 0
        else:
            self.step_state.vote = None  # Abstain
