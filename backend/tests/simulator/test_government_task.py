from celery import Task
from unittest.mock import patch, MagicMock, call

import pytest
from django.core.management import call_command
from django.contrib.contenttypes.models import ContentType
from common.models import Simulation, Cabinet
from simulator.tasks import run_government_steps


@pytest.fixture
def simulation(db, django_db_blocker, request):
    simulation_id = getattr(request, "param", 1)
    with django_db_blocker.unblock():
        call_command("loaddata", f"executive/scenario{simulation_id}.json")
        return Simulation.objects.get(pk=simulation_id)


@pytest.fixture
def cabinet(simulation):
    cabinet_params = simulation.params.filter(
        type=ContentType.objects.get_for_model(Cabinet)
    ).select_related("type")
    return cabinet_params.first().params


@pytest.fixture(autouse=True)
def run_legislative_steps():
    mock = MagicMock(name="run_legislative_steps mock", spec=Task)
    with patch("simulator.tasks.run_legislative_steps", mock):
        yield mock


@pytest.fixture(autouse=True)
def run_judiciary_steps():
    mock = MagicMock(name="run_judiciary_steps mock", spec=Task)
    with patch("simulator.tasks.run_judiciary_steps", mock):
        yield mock


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
        assert data["type"] == "government.step"
        assert "payload" in data
        assert "t" in data["payload"]
        assert "approved" in data["payload"]
        assert "path" in data["payload"]
        assert "votes" in data["payload"]
        assert len(data["payload"]["votes"]) == expected_votes


@pytest.mark.parametrize("simulation", [1, 2, 3], indirect=("simulation",))
def test_extreme_adversity_to_aggrandisement(cabinet, simulation, channel_layer):
    cabinet.government_probability_for = 0.0
    simulation.office_retention_sensitivity = 450.0
    simulation.save()
    cabinet.save()

    run_government_steps.delay(cabinet.label, simulation_id=simulation.id, n_steps=5)

    payloads = [call.args[1]["payload"] for call in channel_layer.send.call_args_list]
    assert not any(p["approved"] for p in payloads)


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
    assert all(p["approved"] for p in payloads)


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
        call(args=[cabinet.label, parliament_config])
    ]
    assert channel_layer.send.call_count == 1


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
        call(args=[cabinet.label, judiciary_config])
    ]
    assert channel_layer.send.call_count == 1
