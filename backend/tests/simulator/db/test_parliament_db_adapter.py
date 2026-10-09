import pytest

from common.models import (
    Simulation,
    SimulationInstitution,
    MemberOfParliament,
    Party,
    MPBelief,
)
import simulator.db._adapter as adapter_module
from simulator.db._adapter import ParliamentDbAdapter


# world.json: country 1 with its chamber (institution 2) and parties 1 and 2
COUNTRY_ID = 1
CHAMBER_ID = 2
SEATS = {"majority": 51, "opposition": 49}


@pytest.fixture
def parliament(world_simulation) -> SimulationInstitution:
    return SimulationInstitution.objects.create(
        simulation=world_simulation, institution_id=CHAMBER_ID
    )


def _create_mp(parliament, label, weights, party):
    return MemberOfParliament.objects.create(
        label=f"{parliament.institution.label}-{label}",
        weights=weights,
        chamber=parliament,
        party=party,
    )


@pytest.fixture
def weights(request):
    return getattr(request, "param", [0.1667, 0.1667, 0.1667, 0.1667, 0.1667, 0.1667])


@pytest.fixture
def members_of_parliament(parliament, weights):
    return [
        _create_mp(parliament, f"{party.label}-{member_idx+1}", weights, party)
        for party in Party.objects.filter(country_id=COUNTRY_ID).order_by("id")
        for member_idx in range(SEATS[party.label])
    ]


@pytest.fixture
def populated_world_simulation(world_simulation, members_of_parliament) -> Simulation:
    return world_simulation


@pytest.fixture
def sut():
    return ParliamentDbAdapter()


def test_convert_parliament_has_expected_global_params(
    sut, parliament, populated_world_simulation, test_settings
):
    result = sut.convert(populated_world_simulation.id)

    assert result.alpha == populated_world_simulation.social_influence_susceptibility
    assert result.gamma == populated_world_simulation.office_retention_sensitivity
    assert result.epsilon == test_settings.abstention_threshold
    assert result.n_party == 2
    assert result.n_sits == [51, 49]
    assert len(result.mps) == parliament.members.count()


@pytest.mark.parametrize("weights", [[0.1, 0.2, 0.3, 0.3, 0.05, 0.05]], indirect=True)
def test_convert_parliament_members_have_expected_weights(
    sut, populated_world_simulation, weights
):
    result = sut.convert(populated_world_simulation.id)

    assert all(mp.W == weights for mp in result.mps)


def test_convert_parliament_members_have_expected_party_labels(
    sut, populated_world_simulation, test_settings
):
    result = sut.convert(populated_world_simulation.id)

    expected_party_labels = set(
        Party.objects.filter(country_id=COUNTRY_ID).values_list("label", flat=True)
    )
    assert all(mp.P_i in expected_party_labels for mp in result.mps)


def test_convert_parliament_members_have_zero_influence(
    sut, populated_world_simulation
):
    result = sut.convert(populated_world_simulation.id)

    assert all(mp.S_i == 0 for mp in result.mps)


def test_convert_parliament_members_use_persisted_personal_opinion(
    sut, populated_world_simulation, parliament
):
    members = list(parliament.members.all())
    for idx, mp in enumerate(members):
        mp.personal_opinion = idx % 2
        mp.save(update_fields=["personal_opinion"])

    result = sut.convert(populated_world_simulation.id)
    opinions = {mp.id: mp.belief.o_i for mp in result.mps}
    expected = {mp.id: mp.personal_opinion for mp in members}

    assert opinions == expected


def test_convert_parliament_members_support_group_1(
    sut, populated_world_simulation, parliament
):
    members = list(parliament.members.all())
    for idx, mp in enumerate(members):
        mp.appointing_group_opinion = idx % 2
        mp.save(update_fields=["appointing_group_opinion"])

    result = sut.convert(populated_world_simulation.id)
    opinions = {mp.id: mp.belief.o_sup1 for mp in result.mps}
    expected = {mp.id: mp.appointing_group_opinion for mp in members}

    assert opinions == expected


def test_convert_parliament_members_support_group_2(sut, populated_world_simulation):
    parliament = sut.convert(populated_world_simulation.id)

    assert not any(mp.belief.o_sup2 for mp in parliament.mps)


def test_mp_personal_opinion_stable_across_conversions(
    sut, populated_world_simulation, monkeypatch
):
    phase = {"value": 0.9}

    def fake_random_gauss(center, spread=1.0, lo=0.0, hi=1.0):
        return phase["value"]

    monkeypatch.setattr(adapter_module, "_random_gauss", fake_random_gauss)

    parliament_first = sut.convert(populated_world_simulation.id)
    opinions_first = {mp.id: mp.belief.o_i for mp in parliament_first.mps}

    phase["value"] = 0.1
    parliament_second = sut.convert(populated_world_simulation.id)
    opinions_second = {mp.id: mp.belief.o_i for mp in parliament_second.mps}

    assert opinions_first == opinions_second


@pytest.fixture
def step_no():
    return 5


@pytest.fixture
def aggrandisement_unit(populated_world_simulation, step_no, make_aggrandisement_unit):
    return make_aggrandisement_unit(populated_world_simulation, step_no)


@pytest.fixture
def targeted_and_fallback(parliament):
    members = list(parliament.members.all().order_by("id"))
    assert len(members) >= 2
    return members[0], members[1]


@pytest.fixture
def mp_step_belief(aggrandisement_unit, configured_global_beliefs):
    targeted, _ = configured_global_beliefs
    return MPBelief.objects.create(
        unit=aggrandisement_unit,
        agent=targeted,
        personal_opinion=1.0,
        appointing_group_opinion=1.0,
        supporting_group_opinion=1.0,
    )


@pytest.mark.django_db
def test_convert_uses_step_specific_mp_beliefs_with_global_fallback(
    sut, populated_world_simulation, step_no, configured_global_beliefs, mp_step_belief
):
    targeted, fallback = configured_global_beliefs
    converted_parliament = sut.convert(populated_world_simulation.id, step_no=step_no)
    converted = {mp.id: mp for mp in converted_parliament.mps}

    assert converted[targeted.id].belief.o_i == 1.0
    assert converted[targeted.id].belief.o_sup1 == 1.0
    assert converted[targeted.id].belief.o_sup2 == 1.0

    assert converted[fallback.id].belief.o_i == fallback.personal_opinion
    assert converted[fallback.id].belief.o_sup1 == fallback.appointing_group_opinion
    assert converted[fallback.id].belief.o_sup2 == fallback.supporting_group_opinion
