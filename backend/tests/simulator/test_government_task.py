from celery import Task
from unittest.mock import patch, MagicMock, call

import pytest
from common.models import Cabinet
from simulator.tasks import run_government_steps


@pytest.fixture
def simulation(executive_simulation):
    return executive_simulation


@pytest.fixture
def cabinet(simulation, institution_params):
    return institution_params(simulation, Cabinet)


@pytest.fixture(autouse=True)
def run_legislative_steps(parliament_step_result):
    mock = MagicMock(name="run_legislative_steps mock", spec=Task)
    result_mock = MagicMock()
    result_mock.get.return_value = parliament_step_result
    mock.apply_async.return_value = result_mock
    with patch("simulator.tasks.run_legislative_steps", mock):
        yield mock


@pytest.fixture
def parliament_step_result():
    return {
        "type": "parliament",
        "approved": False,
        "vbar": 0.0,
        "votes": {"1": "0"},
    }


@pytest.fixture(autouse=True)
def run_judiciary_steps(judiciary_step_result):
    mock = MagicMock(name="run_judiciary_steps mock", spec=Task)
    result_mock = MagicMock()
    result_mock.get.return_value = judiciary_step_result
    mock.apply_async.return_value = result_mock
    with patch("simulator.tasks.run_judiciary_steps", mock):
        yield mock


@pytest.fixture
def judiciary_step_result():
    return {
        "type": "court",
        "approved": False,
        "vbar": 0.0,
        "votes": {"1": "0"},
    }


@pytest.mark.django_db
def test_response_message_structure(
    channel_layer, cabinet, simulation, run_legislative_steps
):
    cabinet.legislative_probability = 0.0
    cabinet.save()

    run_government_steps.delay(cabinet.label, simulation_id=simulation.id, n_steps=3)

    assert run_legislative_steps.apply_async.call_count == 0
    assert channel_layer.send.call_count == 3
    expected_votes = len(cabinet.ministers.all())
    for c in channel_layer.send.call_args_list:
        channel_name, data = c.args
        assert channel_name == cabinet.label
        assert "type" in data
        assert data["type"] == "step.finished"
        assert "payload" in data
        assert "t" in data["payload"]
        assert isinstance(data["payload"]["t"], int)
        assert "results" in data["payload"]
        assert isinstance(data["payload"]["results"], list)
        results = data["payload"]["results"]
        assert len(results) >= 1
        cabinet_result = results[0]
        assert cabinet_result["type"] == "cabinet"
        assert "approved" in cabinet_result
        assert isinstance(cabinet_result["approved"], bool)
        assert "path" in cabinet_result
        assert isinstance(cabinet_result["path"], str)
        assert cabinet_result["path"] in {"decree", "legislative_act"}
        assert "votes" in cabinet_result
        assert isinstance(cabinet_result["votes"], dict)
        assert len(cabinet_result["votes"]) == expected_votes
        assert all(isinstance(k, str) for k in cabinet_result["votes"])


@pytest.mark.parametrize("simulation", [1, 2, 3], indirect=("simulation",))
def test_extreme_adversity_to_aggrandisement(cabinet, simulation, channel_layer):
    cabinet.government_probability_for = 0.0
    simulation.office_retention_sensitivity = 450.0
    simulation.save()
    cabinet.save()

    run_government_steps.delay(cabinet.label, simulation_id=simulation.id, n_steps=5)

    payloads = [call.args[1]["payload"] for call in channel_layer.send.call_args_list]
    assert not any(p["results"][0]["approved"] for p in payloads)


@pytest.mark.parametrize("simulation", [1, 2, 3], indirect=("simulation",))
def test_extreme_favorability_towards_aggrandisement(
    cabinet, simulation, channel_layer
):
    cabinet.government_probability_for = 1.0
    simulation.office_retention_sensitivity = 25.0
    simulation.save()
    cabinet.save()

    run_government_steps.delay(cabinet.label, simulation_id=simulation.id, n_steps=5)

    payloads = [call.args[1]["payload"] for call in channel_layer.send.call_args_list]
    assert all(p["results"][0]["approved"] for p in payloads)


def test_run_legislative_steps_for_legislative_act(
    channel_layer,
    cabinet,
    simulation,
    parliament_config,
    run_legislative_steps,
    run_judiciary_steps,
):
    cabinet.legislative_probability = 1.0
    cabinet.save()

    run_government_steps.delay(
        cabinet.label,
        simulation_id=simulation.id,
        parl_data=parliament_config,
        n_steps=1,
    )

    assert run_judiciary_steps.apply_async.call_count == 0
    assert run_legislative_steps.apply_async.call_count == 1
    assert run_legislative_steps.apply_async.call_args_list == [
        call(kwargs={"simulation_id": simulation.id})
    ]
    assert channel_layer.send.call_count == 1


def test_run_legislative_steps_with_result_adds_to_channel_call(
    channel_layer,
    cabinet,
    simulation,
    parliament_config,
    run_legislative_steps,
    parliament_step_result,
    run_judiciary_steps,
):
    cabinet.legislative_probability = 1.0
    cabinet.save()

    run_government_steps.delay(
        cabinet.label,
        simulation_id=simulation.id,
        parl_data=parliament_config,
        n_steps=1,
    )

    assert run_judiciary_steps.apply_async.call_count == 0
    assert run_legislative_steps.apply_async.call_count == 1
    channel_name, event_data = channel_layer.send.call_args[0]
    assert channel_name == "scenario 1"
    assert event_data["type"] == "step.finished"
    payload = event_data["payload"]
    assert len(payload["results"]) == 2
    assert payload["results"][1] == parliament_step_result


@pytest.mark.parametrize("simulation", [3], indirect=True)
def test_flow_triggers_judiciary_task_on_decree(
    channel_layer,
    cabinet,
    simulation,
    judiciary_config,
    run_judiciary_steps,
    run_legislative_steps,
):
    cabinet.legislative_probability = 0.0
    cabinet.save()

    run_government_steps.delay(
        cabinet.label,
        simulation_id=simulation.id,
        council_data=judiciary_config,
        n_steps=1,
    )

    assert run_legislative_steps.apply_async.call_count == 0
    assert run_judiciary_steps.apply_async.call_count == 1
    assert run_judiciary_steps.apply_async.call_args_list == [
        call(kwargs={"simulation_id": simulation.id})
    ]
    assert channel_layer.send.call_count == 1


def test_run_judiciary_steps_with_result_adds_to_channel_call(
    channel_layer,
    cabinet,
    simulation,
    judiciary_config,
    judiciary_step_result,
    run_judiciary_steps,
    run_legislative_steps,
):
    cabinet.legislative_probability = 0.0
    cabinet.save()

    run_government_steps.delay(
        cabinet.label,
        simulation_id=simulation.id,
        council_data=judiciary_config,
        n_steps=1,
    )

    assert run_legislative_steps.apply_async.call_count == 0
    assert run_judiciary_steps.apply_async.call_count == 1
    channel_name, event_data = channel_layer.send.call_args[0]
    assert channel_name == "scenario 1"
    assert event_data["type"] == "step.finished"
    payload = event_data["payload"]
    assert len(payload["results"]) == 2
    assert payload["results"][1] == judiciary_step_result
