import pytest

from simulator.common._agent import (
    Agent,
    AgentBelief,
    StepState,
    UtilityCalculator,
)
from simulator.common._agent import Weights

VALID_WEIGHTS = [0.1, 0.2, 0.3, 0.1, 0.1, 0.2]


def make_calculator(vote_prev: int | None) -> UtilityCalculator:
    return UtilityCalculator(
        weights=Weights(VALID_WEIGHTS),
        belief=AgentBelief(o_i=1, o_sup1=1, o_sup2=0),
        vote_prev=vote_prev,
    )


def make_agent(type_: str = "Minister", **step_state) -> Agent:
    agent = Agent(
        id=1,
        T_i=type_,
        P_i="majority",
        S_i=1.0,
        W=Weights(VALID_WEIGHTS),
        belief=AgentBelief(o_i=1, o_sup1=1, o_sup2=0),
        step_state=StepState(),
    )
    for key, value in step_state.items():
        setattr(agent.step_state, key, value)
    return agent


def make_peer() -> Agent:
    peer = make_agent()
    peer.id = 2
    peer.S_i = 2.0
    peer.step_state.pre_for = 0.8
    peer.step_state.pre_against = 0.2
    return peer


def test_weights_reject_wrong_length():
    with pytest.raises(ValueError, match="length 6"):
        Weights([0.1] * 5)


def test_weights_reject_wrong_sum():
    with pytest.raises(ValueError, match="must sum to 1"):
        Weights([0.1, 0.2, 0.3, 0.1, 0.1, 0.3])


def test_weights_tolerate_rounding_error():
    assert Weights([1 / 3] * 3 + [0.0, 0.0, 0.0])


def test_reputation_without_history_is_neutral():
    assert make_calculator(vote_prev=None)._u6_reputation([1, 0]) == 0.5


def test_reputation_counts_matching_peer_votes_keeping_abstentions():
    assert make_calculator(vote_prev=1)._u6_reputation(
        [1, None, 1, 0]
    ) == pytest.approx(2 / 3)


def test_reputation_without_matching_peers_is_neutral():
    assert make_calculator(vote_prev=1)._u6_reputation([None]) == 0.5


@pytest.mark.parametrize("decision", [0, 1])
@pytest.mark.parametrize("group", ["government", "parliament", "council", "courts"])
def test_utilities_are_weighted_component_sums(decision, group):
    calculator = make_calculator(vote_prev=1)

    for reference in (0.0, 1.0):
        utility = calculator.utility_for_decision(
            decision, gamma=1.0, ref_opinion=reference, peers_prev_votes=[1], g=group
        )
        assert 0.0 <= utility <= 1.0


def test_agent_utilities_match_the_calculator():
    agent = make_agent()
    agent.compute_individual_utilities(
        gamma=1.0, ref_opinion=1.0, peers_prev_votes=[1], g="government"
    )

    calculator = make_calculator(vote_prev=None)
    assert agent.step_state.pre_for == calculator.utility_for_decision(
        1, 1.0, 1.0, [1], "government"
    )
    assert agent.step_state.pre_against == calculator.utility_for_decision(
        0, 1.0, 1.0, [1], "government"
    )


@pytest.mark.parametrize(
    "difference,epsilon,expected",
    [(0.2, 0.1, 1), (-0.2, 0.1, 0), (0.05, 0.1, None)],
    ids=["for", "against", "abstain"],
)
def test_decide_vote(difference, epsilon, expected):
    agent = make_agent(post_for=0.5 + difference / 2, post_against=0.5 - difference / 2)

    agent.decide_vote(epsilon)

    assert agent.step_state.vote == expected


def test_mps_ignore_peer_influence():
    mp = make_agent(type_="MP", pre_for=0.4, pre_against=0.6)

    mp.apply_peer_influence(alpha=0.5, neighbors=[make_peer()])

    assert mp.step_state.post_for == mp.step_state.pre_for
    assert mp.step_state.post_against == mp.step_state.pre_against


def test_agents_without_neighbours_ignore_peer_influence():
    agent = make_agent(type_="Minister", pre_for=0.4, pre_against=0.6)

    agent.apply_peer_influence(alpha=0.5, neighbors=[])

    assert agent.step_state.post_for == agent.step_state.pre_for


def test_ministers_blend_own_and_peer_utilities():
    minister = make_agent(type_="Minister", pre_for=0.4, pre_against=0.6)

    minister.apply_peer_influence(alpha=0.5, neighbors=[make_peer()])

    expected_for = 0.5 * 0.4 + 0.5 * 0.8
    expected_against = 0.5 * 0.6 + 0.5 * 0.2
    assert minister.step_state.post_for == pytest.approx(expected_for)
    assert minister.step_state.post_against == pytest.approx(expected_against)


def test_agents_of_unknown_type_skip_peer_influence():
    clerk = make_agent(type_="Clerk", pre_for=0.4, pre_against=0.6)

    clerk.apply_peer_influence(alpha=0.5, neighbors=[make_peer()])

    assert clerk.step_state.post_for == 0.0
    assert clerk.step_state.post_against == 0.0
