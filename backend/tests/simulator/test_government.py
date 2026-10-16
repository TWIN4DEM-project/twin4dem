from common.dto import SubmodelType
from simulator.common._agent import AgentBelief, Weights
from simulator.executive._government import Government
from simulator.executive._minister import Minister

OPINION_WEIGHTS = [0.99, 0.0, 0.0, 0.0, 0.0, 0.01]


def make_minister(id_: int, opinion: int, is_pm: bool = False) -> Minister:
    return Minister(
        id=id_,
        T_i="Minister",
        P_i="party-1",
        S_i=1.0,
        W=Weights(OPINION_WEIGHTS),
        belief=AgentBelief(o_i=opinion, o_sup1=1, o_sup2=0),
        is_pm=is_pm,
    )


def make_government(opinions: list[int], **overrides) -> Government:
    ministers = [
        make_minister(idx + 1, opinion, is_pm=idx == 0)
        for idx, opinion in enumerate(opinions)
    ]
    network = {
        minister.id: [other.id for other in ministers if other.id != minister.id]
        for minister in ministers
    }
    options = dict(
        ministers=ministers,
        pact=0.0,
        alpha=1.0,
        epsilon=0.05,
        gamma=1.0,
        network=network,
        previous_votes={},
    )
    options.update(overrides)
    return Government(**options)


def test_cabinet_majority_approves_and_falls_back_to_decree_path():
    result = make_government([1, 1, 0], pact=0.0).step()

    assert result.approved is True
    assert result.path == "decree"
    assert result.type == SubmodelType.Cabinet


def test_cabinet_minority_rejects_without_a_path():
    result = make_government([0, 0, 1]).step()

    assert result.approved is False
    assert result.path is None


def test_unanimous_abstention_rejects_without_a_path():
    result = make_government([1, 1], epsilon=2.0).step()

    assert result.approved is False
    assert result.path is None
    assert all(vote is None for vote in result.votes.values())


def test_approved_cabinet_can_take_the_legislative_act_path():
    result = make_government([1, 1, 0], pact=1.0).step()

    assert result.approved is True
    assert result.path == "legislative act"
