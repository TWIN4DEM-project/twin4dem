import pytest
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from common.models import (
    Simulation,
    Parliament as ParliamentModel,
    MemberOfParliament,
    SimulationParams,
    AggrandisementBatch,
    AggrandisementUnit,
    MPBelief,
)
import simulator.db._adapter as adapter_module
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


def test_convert_parliament_members_use_persisted_personal_opinion(
    sut, simulation, parliament
):
    members = list(parliament.members.all())
    for idx, mp in enumerate(members):
        mp.personal_opinion = idx % 2
        mp.save(update_fields=["personal_opinion"])

    result = sut.convert(simulation.id)
    opinions = {mp.id: mp.belief.o_i for mp in result.mps}
    expected = {mp.id: mp.personal_opinion for mp in members}

    assert opinions == expected


def test_convert_parliament_members_support_group_1(sut, simulation, parliament):
    members = list(parliament.members.all())
    for idx, mp in enumerate(members):
        mp.appointing_group_opinion = idx % 2
        mp.save(update_fields=["appointing_group_opinion"])

    result = sut.convert(simulation.id)
    opinions = {mp.id: mp.belief.o_sup1 for mp in result.mps}
    expected = {mp.id: mp.appointing_group_opinion for mp in members}

    assert opinions == expected


def test_convert_parliament_members_support_group_2(sut, simulation):
    parliament = sut.convert(simulation.id)

    assert not any(mp.belief.o_sup2 for mp in parliament.mps)


def test_mp_personal_opinion_stable_across_conversions(sut, simulation, monkeypatch):
    phase = {"value": 0.9}

    def fake_random_gauss(center, spread=1.0, lo=0.0, hi=1.0):
        return phase["value"]

    monkeypatch.setattr(adapter_module, "_random_gauss", fake_random_gauss)

    parliament_first = sut.convert(simulation.id)
    opinions_first = {mp.id: mp.belief.o_i for mp in parliament_first.mps}

    phase["value"] = 0.1
    parliament_second = sut.convert(simulation.id)
    opinions_second = {mp.id: mp.belief.o_i for mp in parliament_second.mps}

    assert opinions_first == opinions_second


@pytest.fixture
def step_no():
    return 5


@pytest.fixture
def aggrandisement_unit(simulation, step_no):
    batch = AggrandisementBatch.objects.create(
        simulation=simulation,
        start_date=timezone.now(),
        end_date=timezone.now(),
    )
    return AggrandisementUnit.objects.create(batch=batch, step_no=step_no)


@pytest.fixture
def targeted_and_fallback_mps(parliament):
    members = list(parliament.members.all().order_by("id"))
    assert len(members) >= 2
    return members[0], members[1]


@pytest.fixture
def configured_global_mp_beliefs(targeted_and_fallback_mps):
    targeted, fallback = targeted_and_fallback_mps
    targeted.personal_opinion = 0.0
    targeted.appointing_group_opinion = 0.0
    targeted.supporting_group_opinion = 0.0
    targeted.save(
        update_fields=[
            "personal_opinion",
            "appointing_group_opinion",
            "supporting_group_opinion",
        ]
    )
    fallback.personal_opinion = 1.0
    fallback.appointing_group_opinion = 1.0
    fallback.supporting_group_opinion = 1.0
    fallback.save(
        update_fields=[
            "personal_opinion",
            "appointing_group_opinion",
            "supporting_group_opinion",
        ]
    )
    return targeted, fallback


@pytest.fixture
def mp_step_belief(aggrandisement_unit, configured_global_mp_beliefs):
    targeted, _ = configured_global_mp_beliefs
    return MPBelief.objects.create(
        unit=aggrandisement_unit,
        agent=targeted,
        personal_opinion=1.0,
        appointing_group_opinion=1.0,
        supporting_group_opinion=1.0,
    )


@pytest.mark.django_db
def test_convert_uses_step_specific_mp_beliefs_with_global_fallback(
    sut, simulation, step_no, configured_global_mp_beliefs, mp_step_belief
):
    targeted, fallback = configured_global_mp_beliefs
    converted_parliament = sut.convert(simulation.id, step_no=step_no)
    converted = {mp.id: mp for mp in converted_parliament.mps}

    assert converted[targeted.id].belief.o_i == 1.0
    assert converted[targeted.id].belief.o_sup1 == 1.0
    assert converted[targeted.id].belief.o_sup2 == 1.0

    assert converted[fallback.id].belief.o_i == fallback.personal_opinion
    assert converted[fallback.id].belief.o_sup1 == fallback.appointing_group_opinion
    assert converted[fallback.id].belief.o_sup2 == fallback.supporting_group_opinion
