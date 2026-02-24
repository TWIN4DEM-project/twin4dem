import itertools
import random

import pytest
from django.contrib.contenttypes.models import ContentType

import simulator.db._adapter as adapter_module
from common.models import Court, Judge, JudgeLink, Simulation, SimulationParams
from simulator.db._adapter import CouncilDbAdapter

pytestmark = pytest.mark.django_db
TEST_SIMULATION_ID = 42


@pytest.fixture
def court_size(test_settings, request):
    test_settings.court_size = getattr(request, "param", 5)
    test_settings.save()
    return test_settings.court_size


@pytest.fixture
def probability_for(request):
    return getattr(request, "param", 0.5)


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
        label=f"{court.label}-{idx}",
        court=court,
        party=random.choice(parties),
        weights=weights,
        is_president=is_president,
        influence=random.random() if not is_president else 1.0,
    )


@pytest.fixture
def court(weights, test_settings, probability_for, court_size):
    result = Court.objects.create(
        label="test-court",
        probability_for=probability_for,
    )
    parties = list(test_settings.parties.all())
    judges = [
        _create_judge(idx, result, parties, weights, idx == 0)
        for idx in range(court_size)
    ]
    for judge_from, judge_to in itertools.permutations(judges, 2):
        JudgeLink.objects.create(from_judge=judge_from, to_judge=judge_to)

    return result


@pytest.fixture
def simulation(test_settings, court) -> Simulation:
    content_type = ContentType.objects.get_for_model(Court)
    simulation, ok = Simulation.objects.get_or_create(
        pk=TEST_SIMULATION_ID,
        user_settings=test_settings,
    )
    if not ok:
        raise AssertionError("simulation fixture failed")
    SimulationParams.objects.get_or_create(
        content_id=court.id,
        type_id=content_type.id,
        simulation_id=TEST_SIMULATION_ID,
    )
    return simulation


@pytest.fixture
def sut(simulation, court) -> CouncilDbAdapter:
    return CouncilDbAdapter()


def test_convert_sets_expected_basic_council_properties(sut, simulation, test_settings):
    council = sut.convert(simulation.id)

    assert council.alpha == simulation.social_influence_susceptibility
    assert council.gamma == simulation.office_retention_sensitivity
    assert council.epsilon == test_settings.abstention_threshold


@pytest.mark.parametrize("court_size", [1, 2, 5], indirect=("court_size",))
def test_convert_returns_judges_with_expected_basic_attributes(
    sut, simulation, court_size
):
    council = sut.convert(simulation.id)

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
def test_convert_returns_judges_with_expected_weights(sut, simulation, weights):
    council = sut.convert(simulation.id)

    assert all(j.W == weights for j in council.judges)


def test_convert_uses_persisted_personal_opinion(sut, simulation, court):
    judges = list(court.judges.all())
    for idx, judge in enumerate(judges):
        judge.personal_opinion = idx % 2
        judge.save(update_fields=["personal_opinion"])

    council = sut.convert(simulation.id)
    opinions = {j.id: j.belief.o_i for j in council.judges}

    expected = {j.id: j.personal_opinion for j in judges}
    assert opinions == expected


@pytest.mark.parametrize("court_size", [1, 2, 5], indirect=True)
def test_convert_creates_expected_network(sut, simulation, court_size):
    council = sut.convert(simulation.id)

    assert len(council.network) == court_size
    for judge_id, linked_judge_ids in council.network.items():
        assert isinstance(judge_id, int)
        assert all(isinstance(x, int) for x in linked_judge_ids)
        assert len(linked_judge_ids) == court_size - 1
        assert len(linked_judge_ids) == len(set(linked_judge_ids))


def test_judge_personal_opinion_stable_across_conversions(
    sut, simulation, monkeypatch
):
    phase = {"value": 0.9}

    def fake_random_gauss(center, spread=1.0, lo=0.0, hi=1.0):
        return phase["value"]

    monkeypatch.setattr(adapter_module, "_random_gauss", fake_random_gauss)

    council_first = sut.convert(simulation.id)
    opinions_first = {j.id: j.belief.o_i for j in council_first.judges}

    phase["value"] = 0.1
    council_second = sut.convert(simulation.id)
    opinions_second = {j.id: j.belief.o_i for j in council_second.judges}

    assert opinions_first == opinions_second