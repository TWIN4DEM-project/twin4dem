from dataclasses import dataclass
from typing import List, Dict

from simulator.legislative._mp import MP


class Parliament:
    def __init__(
        self,
        mps: List[MP],
        n_party: int,
        n_sits: List[int],
        alpha: float,
        epsilon: float,
        gamma: float,
    ):
        self.mps = mps
        self.n_party = n_party
        self.n_sits = n_sits
        self.alpha = alpha
        self.epsilon = epsilon
        self.gamma = gamma
        self.t = 0

        # map from party label (P_i) to its head MP
        self.party_heads: Dict[str, MP] = self._compute_party_heads()

    def _compute_party_heads(self) -> Dict[str, MP]:
        """
        Build mapping from party label P_i to the MP marked as is_head.
        Assumes at most one head per party label.
        """
        heads: Dict[str, MP] = {}
        for mp in self.mps:
            if getattr(mp, "is_head", False):
                heads[mp.P_i] = mp
        return heads

    def _get_party_head_opinion(self, mp: MP) -> float:
        """
        Get the reference 'powerful actor' opinion for prestige component (u4).
        For MPs this is the head of their party group.
        Fallbacks:
          - if party has no head, use any available head
          - if no heads at all, use the MP's own opinion
        """
        head = self.party_heads.get(mp.P_i)
        if head is not None:
            return head.o_i

        # fallback: any head in parliament
        if self.party_heads:
            return next(iter(self.party_heads.values())).o_i

        # last resort: own opinion
        return mp.o_i

    def step(self, has_legislative_act: bool = True) -> Dict:
        """
        1. If there is no aggrandisement attempt OR form is 'decree', skip.
        2. Compute utilities U(i,t,for) and U(i,t,against) for all MPs.
        3. MPs vote using Eq. 3.
        4. If the majority is in favour, the aggrandisement is approved, if not, rejected.
        """
        # 1. If executive didn't send a legislative act, nothing happens
        if not has_legislative_act:
            self.t += 1
            return {
                "t": self.t,
                "approved": None,
                "vbar": None,
                "votes": {mp.id: None for mp in self.mps},
            }

        # 2. Compute utilities (no peer influence for MPs)
        for mp in self.mps:
            # reputation: peers are ALL other MPs
            peers_prev = [p.vote_prev for p in self.mps if p.id != mp.id]

            ref_opinion = self._get_party_head_opinion(mp)

            mp.compute_individual_utilities(
                gamma=self.gamma,
                ref_opinion=ref_opinion,
                peers_prev_votes=peers_prev,
                g="parliament",  # this flips u2 correctly
            )

            # MPs are not subject to peer influence, but in Agent implementation
            # apply_peer_influence() sets U*_for = U_for when T_i == "MP" or no neighbors.
            mp.apply_peer_influence(alpha=self.alpha, neighbors=[])

            # 3. Voting (Eq. 3)
            mp.decide_vote(self.epsilon)

        # 4. Majority decision ignoring abstentions
        votes = [mp.vote for mp in self.mps if mp.vote is not None]
        if votes:
            vbar = sum(votes) / len(votes)
            approved = vbar > 0.5
        else:
            vbar = None
            approved = False

            # update v(i,t-1) for reputation in next step
        for mp in self.mps:
            mp.vote_prev = mp.vote

        self.t += 1

        return {
            "t": self.t,
            "approved": approved,
            "vbar": vbar,
            "votes": {mp.id: mp.vote for mp in self.mps},
        }
