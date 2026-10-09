import pytest

from common.dto import SubmodelType
from simulator.common._agent import AgentBelief, Weights
from simulator.judiciary._council import Council
from simulator.judiciary._judge import Judge

OPINION_WEIGHTS = [0.99, 0.0, 0.0, 0.0, 0.0, 0.01]


def make_judge(id_: int, opinion: int, is_president: bool = False) -> Judge:
    return Judge(
        id=id_,
        T_i="Judge",
        P_i="majority",
        S_i=1.0,
        W=Weights(OPINION_WEIGHTS),
        belief=AgentBelief(o_i=opinion, o_sup1=1, o_sup2=0),
        is_president=is_president,
    )


def make_council(opinions: list[int], alpha: float = 1.0, **overrides) -> Council:
    judges = [make_judge(idx + 1, opinion) for idx, opinion in enumerate(opinions)]
    judges[0].is_president = True
    options = dict(
        judges=judges,
        alpha=alpha,
        epsilon=0.05,
        gamma=1.0,
        network=fully_connected(judges),
        prev_votes={},
    )
    options.update(overrides)
    return Council(**options)


def fully_connected(judges: list[Judge]) -> dict[int, list[int]]:
    return {
        judge.id: [other.id for other in judges if other.id != judge.id]
        for judge in judges
    }


def test_unanimous_opinions_approve_batch():
    result = make_council([1, 1, 1]).step()

    assert result.approved is True
    assert result.vbar == pytest.approx(1.0)
    assert result.votes == {"1": 1, "2": 1, "3": 1}
    assert result.type == SubmodelType.Court


def test_majority_opinions_approve_batch():
    result = make_council([1, 1, 0]).step()

    assert result.approved is True
    assert result.vbar == pytest.approx(2 / 3)


def test_minority_opinion_rejects_batch():
    result = make_council([0, 0, 1]).step()

    assert result.approved is False
    assert result.vbar == pytest.approx(1 / 3)


def test_peer_influence_pulls_the_lone_dissenter_to_abstain():
    result = make_council([0, 0, 1], alpha=0.5, prev_votes={"1": 1, "2": 0}).step()

    assert result.votes == {"1": 0, "2": 0, "3": None}
    assert result.vbar == 0.0
    assert result.approved is False


def test_unanimous_abstention_leaves_batch_unapproved():
    result = make_council([1, 1], epsilon=1.0).step()

    assert result.approved is False
    assert result.vbar == 0.0
    assert all(vote is None for vote in result.votes.values())
