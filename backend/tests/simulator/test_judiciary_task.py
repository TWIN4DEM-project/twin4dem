from unittest.mock import MagicMock, patch

import pytest

from simulator.adapters import Adapter, AdapterFactory
from simulator.tasks import run_judiciary_steps

from simulator.config._adapter import CouncilConfigAdapter


@pytest.fixture
def council(judiciary_config):
    return CouncilConfigAdapter().convert(judiciary_config)


@pytest.fixture(autouse=True)
def adapter_factory(council):
    mock_adapter = MagicMock(name="mockadapter", spec=Adapter)
    mock_adapter.convert.return_value = council
    mock_factory = MagicMock(name="mockfactory", spec=AdapterFactory)
    mock_factory.new_council_adapter.return_value = mock_adapter
    with patch("simulator.tasks.get_adapter_factory") as mock:
        mock.return_value = mock_factory
        yield mock


def test_council_step_no_decree_skips_voting(council):
    result = council.step(has_decree=False)

    assert result["approved"] is None
    assert result["vbar"] is None
    assert isinstance(result["votes"], dict)
    assert set(result["votes"].keys()) == {j.id for j in council.judges}
    assert all(v is None for v in result["votes"].values())


def test_council_step_decree_returns_votes_shape(council):
    result = council.step(has_decree=True)

    assert "t" in result
    assert "approved" in result
    assert "vbar" in result
    assert "votes" in result

    assert result["approved"] in (True, False)
    assert isinstance(result["votes"], dict)
    assert set(result["votes"].keys()) == {j.id for j in council.judges}

    # votes are 0 / 1 / None
    assert all(v in (0, 1, None) for v in result["votes"].values())
    assert result["vbar"] is None or isinstance(result["vbar"], float)


def test_council_president_detected(council):
    presidents = [j for j in council.judges if j.is_president]
    assert len(presidents) == 1


def test_run_judiciary_steps_sends_council_step(
    channel_layer, judiciary_config, council, monkeypatch
):
    step_mock = MagicMock(
        name="parliament.step",
        spec=council.step,
        return_value={"t": 1, "approved": True, "vbar": 1.0, "votes": {1: 1, 2: 1}},
    )
    monkeypatch.setattr(council, "step", step_mock)
    expected_channel_name = "test-council-step"

    run_judiciary_steps.delay(expected_channel_name, data=judiciary_config)

    assert channel_layer.send.call_count == 1
    actual_channel_name, data = channel_layer.send.call_args_list[0].args
    assert actual_channel_name == expected_channel_name
    assert "type" in data
    assert "payload" in data
    assert data["type"] == "council.step"
    assert "votes" in data["payload"]
