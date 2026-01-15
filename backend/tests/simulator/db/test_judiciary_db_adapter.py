import itertools
import random

import pytest
from django.contrib.contenttypes.models import ContentType

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
        assert j.o_sup1 == 0
        assert j.o_sup2 == 0
    assert presidents == 1


@pytest.mark.parametrize("weights", [[0.1, 0.2, 0.3, 0.2, 0.1, 0.1]], indirect=True)
def test_convert_returns_judges_with_expected_weights(sut, simulation, weights):
    council = sut.convert(simulation.id)

    assert all(j.W == weights for j in council.judges)


@pytest.mark.parametrize(
    "court_size,probability_for,expected_min,expected_max",
    [
        (1, 0.8, 95, 100),
        (1, 0.7, 90, 100),
        (1, 0.6, 70, 90),
        (1, 0.5, 30, 70),
        (1, 0.4, 10, 30),
        (1, 0.3, 0, 10),
        (1, 0.2, 0, 5),
    ],
    indirect=(
        "court_size",
        "probability_for",
    ),
)
def test_convert_personal_opinion_follows_probability_for(
    sut, simulation, expected_min, expected_max
):
    councils = [sut.convert(simulation.id) for _ in range(100)]
    judges_for = int(sum(j.o_i for c in councils for j in c.judges))

    assert all(j.o_i in {0, 1} for c in councils for j in c.judges)
    assert expected_min <= judges_for <= expected_max


@pytest.mark.parametrize("court_size", [1, 2, 5], indirect=True)
def test_convert_creates_expected_network(sut, simulation, court_size):
    council = sut.convert(simulation.id)

    assert len(council.network) == court_size
    for judge_id, linked_judge_ids in council.network.items():
        assert isinstance(judge_id, int)
        assert all(isinstance(x, int) for x in linked_judge_ids)
        assert len(linked_judge_ids) == court_size - 1
        assert len(linked_judge_ids) == len(set(linked_judge_ids))
