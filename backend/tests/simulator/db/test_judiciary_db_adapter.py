import itertools
import random

import pytest

import simulator.db._adapter as adapter_module
from common.models import (
    Judge,
    JudgeLink,
    Party,
    PartyPositionType,
    Simulation,
    SimulationInstitution,
    JudgeBelief,
)
from simulator.db._adapter import CouncilDbAdapter

pytestmark = pytest.mark.django_db
# world.json: country 1 with its chamber (institution 2), its court (institution 3)
# and parties 1 (majority) and 2 (opposition)
COUNTRY_ID = 1
CHAMBER_ID = 2
COURT_ID = 3


@pytest.fixture
def court_size(request):
    return getattr(request, "param", 5)


@pytest.fixture
def weights(request):
    if hasattr(request, "param") and isinstance(
        getattr(request, "param"), (list, tuple)
    ):
        return request.param
    x = [random.expovariate(1.0) for _ in range(6)]
    s = sum(x)
    return [x_i / s for x_i in x]


def _create_judge(idx, court, parties, weights, is_president=False):
    return Judge.objects.create(
        label=f"{court.institution.label}-{idx}",
        court=court,
        party=random.choice(parties),
        weights=weights,
        is_president=is_president,
        influence=random.random() if not is_president else 1.0,
    )


@pytest.fixture
def chamber(world_simulation) -> SimulationInstitution:
    # the chamber determines the judges' party positions
    return SimulationInstitution.objects.create(
        simulation=world_simulation, institution_id=CHAMBER_ID
    )


@pytest.fixture
def court(world_simulation, chamber, weights, court_size):
    result = SimulationInstitution.objects.create(
        simulation=world_simulation, institution_id=COURT_ID
    )
    parties = list(Party.objects.filter(country_id=COUNTRY_ID))
    judges = [
        _create_judge(idx, result, parties, weights, idx == 0)
        for idx in range(court_size)
    ]
    for judge_from, judge_to in itertools.permutations(judges, 2):
        JudgeLink.objects.create(from_judge=judge_from, to_judge=judge_to)

    return result


@pytest.fixture
def populated_world_simulation(world_simulation, court) -> Simulation:
    return world_simulation


@pytest.fixture
def sut(populated_world_simulation, court) -> CouncilDbAdapter:
    return CouncilDbAdapter()


def test_convert_sets_expected_basic_council_properties(
    sut, populated_world_simulation, test_settings
):
    council = sut.convert(populated_world_simulation.id)

    assert council.alpha == populated_world_simulation.social_influence_susceptibility
    assert council.gamma == populated_world_simulation.office_retention_sensitivity
    assert council.epsilon == test_settings.abstention_threshold


@pytest.mark.parametrize("court_size", [1, 2, 5], indirect=("court_size",))
def test_convert_returns_judges_with_expected_basic_attributes(
    sut, populated_world_simulation, court_size
):
    council = sut.convert(populated_world_simulation.id)

    assert len(council.judges) == court_size
    presidents = 0
    for j in council.judges:
        presidents += int(j.is_president)
        assert j.T_i == "Judge"
        assert j.P_i in {"majority", "opposition"}
        assert (not j.is_president and 0 <= j.S_i <= 1.0) ^ (
            j.is_president and j.S_i == 1.0
        )
        assert j.belief.o_sup1 == 0
        assert j.belief.o_sup2 == 0
    assert presidents == 1


@pytest.mark.parametrize("weights", [[0.1, 0.2, 0.3, 0.2, 0.1, 0.1]], indirect=True)
def test_convert_returns_judges_with_expected_weights(
    sut, populated_world_simulation, weights
):
    council = sut.convert(populated_world_simulation.id)

    assert all(j.W == weights for j in council.judges)


def test_convert_uses_persisted_personal_opinion(
    sut, populated_world_simulation, court
):
    judges = list(court.judges.all())
    for idx, judge in enumerate(judges):
        judge.personal_opinion = idx % 2
        judge.save(update_fields=["personal_opinion"])

    council = sut.convert(populated_world_simulation.id)
    opinions = {j.id: j.belief.o_i for j in council.judges}

    expected = {j.id: j.personal_opinion for j in judges}
    assert opinions == expected


@pytest.mark.parametrize("court_size", [1, 2, 5], indirect=True)
def test_convert_creates_expected_network(sut, populated_world_simulation, court_size):
    council = sut.convert(populated_world_simulation.id)

    assert len(council.network) == court_size
    for judge_id, linked_judge_ids in council.network.items():
        assert isinstance(judge_id, int)
        assert all(isinstance(x, int) for x in linked_judge_ids)
        assert len(linked_judge_ids) == court_size - 1
        assert len(linked_judge_ids) == len(set(linked_judge_ids))


def test_judge_personal_opinion_stable_across_conversions(
    sut, populated_world_simulation, monkeypatch
):
    phase = {"value": 0.9}

    def fake_random_gauss(center, spread=1.0, lo=0.0, hi=1.0):
        return phase["value"]

    monkeypatch.setattr(adapter_module, "_random_gauss", fake_random_gauss)

    council_first = sut.convert(populated_world_simulation.id)
    opinions_first = {j.id: j.belief.o_i for j in council_first.judges}

    phase["value"] = 0.1
    council_second = sut.convert(populated_world_simulation.id)
    opinions_second = {j.id: j.belief.o_i for j in council_second.judges}

    assert opinions_first == opinions_second


@pytest.fixture
def step_no():
    return 4


@pytest.fixture
def aggrandisement_unit(populated_world_simulation, step_no, make_aggrandisement_unit):
    return make_aggrandisement_unit(populated_world_simulation, step_no)


@pytest.fixture
def targeted_and_fallback(court):
    judges = list(court.judges.all().order_by("id"))
    assert len(judges) >= 2
    return judges[0], judges[1]


@pytest.fixture
def judge_step_belief(aggrandisement_unit, configured_global_beliefs):
    targeted, _ = configured_global_beliefs
    return JudgeBelief.objects.create(
        unit=aggrandisement_unit,
        agent=targeted,
        personal_opinion=1.0,
        appointing_group_opinion=1.0,
        supporting_group_opinion=1.0,
    )


@pytest.mark.django_db
def test_convert_uses_step_specific_judge_beliefs_with_global_fallback(
    sut,
    populated_world_simulation,
    step_no,
    configured_global_beliefs,
    judge_step_belief,
):
    targeted, fallback = configured_global_beliefs
    council = sut.convert(populated_world_simulation.id, step_no=step_no)
    converted = {j.id: j for j in council.judges}

    assert converted[targeted.id].belief.o_i == 1.0
    assert converted[targeted.id].belief.o_sup1 == 1.0
    assert converted[targeted.id].belief.o_sup2 == 1.0

    assert converted[fallback.id].belief.o_i == fallback.personal_opinion
    assert converted[fallback.id].belief.o_sup1 == fallback.appointing_group_opinion
    assert converted[fallback.id].belief.o_sup2 == fallback.supporting_group_opinion


def test_judges_are_independent_without_chamber(sut, populated_world_simulation):
    populated_world_simulation.institutions.filter(institution_id=CHAMBER_ID).delete()

    council = sut.convert(populated_world_simulation.id)

    assert {j.P_i for j in council.judges} == {PartyPositionType.INDEPENDENT}


def test_convert_without_court_raises(sut, populated_world_simulation, court):
    court.delete()

    with pytest.raises(ValueError) as err_proxy:
        sut.convert(populated_world_simulation.id)

    assert (
        str(err_proxy.value)
        == f"there is no court in simulation {populated_world_simulation.id}"
    )
