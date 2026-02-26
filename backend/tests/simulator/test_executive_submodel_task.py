import pytest

from common.dto import SimulationStepResult
from common.models import Cabinet
from simulator.tasks import executive_submodel


@pytest.fixture
def simulation(executive_simulation):
    return executive_simulation


@pytest.fixture
def simulation_input_param(simulation):
    return SimulationStepResult(
        step_no=0, simulation_id=simulation.id, results=[]
    ).model_dump()


@pytest.fixture
def cabinet(simulation, institution_params):
    return institution_params(simulation, Cabinet)


@pytest.mark.django_db
def test_response_has_expected_structure(cabinet, simulation_input_param):
    response = executive_submodel.delay(simulation_input_param).get()

    cabinet_result = response["results"][0]
    expected_vote_count = len(cabinet.ministers.all())
    assert cabinet_result["type"] == "cabinet"
    assert "approved" in cabinet_result
    assert isinstance(cabinet_result["approved"], bool)
    assert "path" in cabinet_result
    assert isinstance(cabinet_result["path"], str)
    assert cabinet_result["path"] in {"decree", "legislative act"}
    assert "votes" in cabinet_result
    assert isinstance(cabinet_result["votes"], dict)
    assert len(cabinet_result["votes"]) == expected_vote_count
    assert all(isinstance(k, str) for k in cabinet_result["votes"])


@pytest.mark.parametrize("simulation", [1, 2, 3], indirect=("simulation",))
def test_extreme_adversity_to_aggrandisement(
    cabinet, simulation, simulation_input_param
):
    cabinet.government_probability_for = 0.0
    simulation.office_retention_sensitivity = 450.0
    simulation.save()
    cabinet.save()

    results = list(map(executive_submodel.delay(simulation_input_param).get, range(5)))

    assert not any(r["results"][0]["approved"] for r in results)


@pytest.mark.parametrize("simulation", [1, 2, 3], indirect=("simulation",))
def test_extreme_favorability_towards_aggrandisement(
    cabinet, simulation, simulation_input_param
):
    cabinet.government_probability_for = 1.0
    simulation.office_retention_sensitivity = 25.0
    simulation.save()
    cabinet.save()

    results = list(map(executive_submodel.delay(simulation_input_param).get, range(5)))

    assert all(r["results"][0]["approved"] for r in results)
