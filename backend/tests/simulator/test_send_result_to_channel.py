import pytest

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
