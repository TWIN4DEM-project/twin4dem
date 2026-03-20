from unittest.mock import MagicMock, patch

import pytest

from common.dto import SimulationStepResult, ExecutiveSubmodelResult, SubmodelType
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
    if cabinet_result["approved"]:
        assert isinstance(cabinet_result["path"], str)
        assert cabinet_result["path"] in {"decree", "legislative act"}
    else:
        assert cabinet_result["path"] is None
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
    cabinet.ministers.all().update(
        personal_opinion=1, appointing_group_opinion=1, supporting_group_opinion=1
    )

    results = list(map(executive_submodel.delay(simulation_input_param).get, range(5)))

    assert all(r["results"][0]["approved"] for r in results)


@pytest.fixture
def step_input(simulation, step_no):
    return SimulationStepResult(
        step_no=step_no, simulation_id=simulation.id, results=[]
    ).model_dump()


@pytest.fixture
def government_adapter_factory_mock():
    adapter_factory = MagicMock(name="adapter-factory")
    adapter = MagicMock(name="government-adapter")
    government = MagicMock(name="government")
    government.step.return_value = ExecutiveSubmodelResult(
        approved=True, votes={"1": 1}, type=SubmodelType.Cabinet, path="decree"
    )
    adapter.convert.return_value = government
    adapter_factory.new_government_adapter.return_value = adapter
    with patch("simulator.tasks.get_adapter_factory", return_value=adapter_factory):
        yield adapter_factory, adapter


@pytest.mark.django_db
@pytest.mark.parametrize("step_no", [1, 9])
def test_executive_submodel_forwards_step_no_to_government_adapter(
    simulation, step_no, step_input, government_adapter_factory_mock
):
    _, adapter = government_adapter_factory_mock
    executive_submodel.delay(step_input).get()

    adapter.convert.assert_called_once_with(simulation.id, step_no=step_no)
