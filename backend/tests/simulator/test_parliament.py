import pytest

from common.dto import SubmodelType
from simulator.common._agent import AgentBelief, Weights
from simulator.legislative._mp import MP
from simulator.legislative._parliament import Parliament

OPINION_WEIGHTS = [0.99, 0.0, 0.0, 0.0, 0.0, 0.01]


def make_mp(id_: int, opinion: int, is_head: bool = False, party: str = None) -> MP:
    return MP(
        id=id_,
        T_i="MP",
        P_i=party or f"party-{opinion}",
        S_i=1.0,
        W=Weights(OPINION_WEIGHTS),
        belief=AgentBelief(o_i=opinion, o_sup1=1, o_sup2=0),
        is_head=is_head,
    )


def make_parliament(opinions: list[int], **overrides) -> Parliament:
    mps = [
        make_mp(idx + 1, opinion, is_head=idx in (0, 1))
        for idx, opinion in enumerate(opinions)
    ]
    options = dict(
        mps=mps,
        n_party=2,
        n_sits=[20, 20],
        alpha=0.5,
        epsilon=0.05,
        gamma=1.0,
        prev_votes={},
    )
    options.update(overrides)
    return Parliament(**options)


def test_party_heads_map_the_first_head_per_party():
    parliament = make_parliament([1, 0, 1])

    assert set(parliament.party_heads) == {"party-1", "party-0"}
    assert parliament.party_heads["party-1"] is parliament.mps[0]


def test_headless_mp_falls_back_to_any_head():
    parliament = make_parliament([1, 0])
    headless = make_mp(3, opinion=0, party="independent")

    assert (
        parliament._get_party_head_opinion(headless)
        == parliament.party_heads["party-1"].belief.o_i
    )


def test_mp_without_any_party_head_uses_the_own_opinion():
    parliament = make_parliament([])
    lone = make_mp(4, opinion=1)

    assert parliament._get_party_head_opinion(lone) == lone.belief.o_i


def test_majority_of_mps_approves_the_batch():
    result = make_parliament([1, 1, 0]).step()

    assert result.approved is True
    assert result.vbar == pytest.approx(2 / 3)
    assert result.type == SubmodelType.Parliament


def test_minority_of_mps_rejects_the_batch():
    result = make_parliament([0, 0, 1]).step()

    assert result.approved is False
    assert result.vbar == pytest.approx(1 / 3)


def test_unanimous_abstention_leaves_the_vbar_unset():
    result = make_parliament([1, 0], epsilon=2.0).step()

    assert result.approved is False
    assert result.vbar == 0.0
    assert all(vote is None for vote in result.votes.values())
