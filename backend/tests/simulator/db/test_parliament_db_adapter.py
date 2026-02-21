import pytest
from django.contrib.contenttypes.models import ContentType

from common.models import (
    Simulation,
    Parliament as ParliamentModel,
    MemberOfParliament,
    SimulationParams,
)
from simulator.db._adapter import ParliamentDbAdapter


TEST_SIMULATION_ID = 42


@pytest.fixture
def parliament(db) -> ParliamentModel:
    result, ok = ParliamentModel.objects.get_or_create(label="test parliament")
    if not ok:
        raise AssertionError("parliament fixture failed")
    return result


def _create_mp(parliament, label, weights, party):
    result, ok = MemberOfParliament.objects.get_or_create(
        label=f"{parliament.label}-{label}",
        weights=weights,
        parliament=parliament,
        party=party,
    )
    if not ok:
        raise AssertionError("member_of_parliament fixture failed")
    return result


@pytest.fixture
def weights(request):
    return getattr(request, "param", [0.1667, 0.1667, 0.1667, 0.1667, 0.1667, 0.1667])


@pytest.fixture
def members_of_parliament(test_settings, parliament, weights):
    return [
        _create_mp(parliament, f"{party.label}-{member_idx+1}", weights, party)
        for party in test_settings.parties.all()
        for member_idx in range(party.member_count)
    ]


@pytest.fixture
def simulation(test_settings, parliament, members_of_parliament) -> Simulation:
    content_type = ContentType.objects.get_for_model(ParliamentModel)
    simulation, ok = Simulation.objects.get_or_create(
        pk=TEST_SIMULATION_ID,
        user_settings=test_settings,
    )
    if not ok:
        raise AssertionError("simulation fixture failed")
    SimulationParams.objects.get_or_create(
        content_id=parliament.id,
        type_id=content_type.id,
        simulation_id=TEST_SIMULATION_ID,
    )
    return simulation


@pytest.fixture
def sut():
    return ParliamentDbAdapter()


def test_convert_parliament_has_expected_global_params(
    sut, parliament, simulation, test_settings
):
    result = sut.convert(simulation.id)

    assert result.alpha == simulation.social_influence_susceptibility
    assert result.gamma == simulation.office_retention_sensitivity
    assert result.epsilon == test_settings.abstention_threshold
    assert result.n_party == 2
    assert result.n_sits == [51, 49]
    assert len(result.mps) == parliament.members.count()


@pytest.mark.parametrize("weights", [[0.1, 0.2, 0.3, 0.3, 0.05, 0.05]], indirect=True)
def test_convert_parliament_members_have_expected_weights(sut, simulation, weights):
    result = sut.convert(simulation.id)

    assert all(mp.W == weights for mp in result.mps)


def test_convert_parliament_members_have_expected_party_labels(
    sut, simulation, test_settings
):
    result = sut.convert(simulation.id)

    expected_party_labels = set(
        x["position"] for x in test_settings.parties.values("position").distinct()
    )
    assert all(mp.P_i in expected_party_labels for mp in result.mps)


def test_convert_parliament_members_have_zero_influence(sut, simulation):
    result = sut.convert(simulation.id)

    assert all(mp.S_i == 0 for mp in result.mps)


def test_convert_parliament_members_personal_opinion_range(sut, simulation, parliament):
    parliament.majority_probability_for = 0.7
    parliament.opposition_probability_for = 0.3
    parliament.save()
    parliaments = [sut.convert(simulation.id) for _ in range(100)]

    mp_sums = [
        (sum(x.belief.o_i for x in mp), mp[0].P_i)
        for mp in zip(*[p.mps for p in parliaments])
    ]

    assert all(
        90 <= sum_o_i <= 100 for sum_o_i, position in mp_sums if position == "majority"
    )
    assert all(
        0 <= sum_o_i <= 10 for sum_o_i, position in mp_sums if position == "opposition"
    )


def test_convert_parliament_members_support_group_1(sut, simulation):
    parliament = sut.convert(simulation.id)

    assert all(mp.belief.o_sup1 for mp in parliament.mps if mp.P_i == "majority")
    assert not any(mp.belief.o_sup1 for mp in parliament.mps if mp.P_i == "opposition")


def test_convert_parliament_members_support_group_2(sut, simulation):
    parliament = sut.convert(simulation.id)

    assert not any(mp.belief.o_sup2 for mp in parliament.mps)
