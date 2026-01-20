import pytest

from common.models import Simulation
from simulator.tasks import send_result_to_channel


@pytest.fixture
def model_result(executive_submodel_output, approved, vbar_result):
    if approved:
        executive_submodel_output["results"].append(
            vbar_result.model_dump(mode="json", by_alias=True)
        )
    return executive_submodel_output


def test_send_result_uses_expected_event(channel_layer, model_result):
    send_result_to_channel.delay(model_result, "test-channel")

    assert channel_layer.send.call_count == 1
    channel_name, event_data = channel_layer.send.call_args[0]
    assert channel_name == "test-channel"
    assert event_data["type"] == "step.finished"
    assert event_data["payload"] == model_result


@pytest.mark.django_db
@pytest.mark.parametrize("step_no", [0, 1, 2])
def test_send_result_to_channel_increseases_step_no(model_result, step_no):
    model_result["stepNo"] = step_no

    send_result_to_channel.delay(model_result, "test-channel")

    assert (
        Simulation.objects.get(pk=model_result["simulationId"]).current_step == step_no
    )
