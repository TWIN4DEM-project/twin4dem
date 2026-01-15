from unittest.mock import MagicMock, patch

import pytest

from simulator.adapters import AdapterFactory, Adapter
from simulator.config._adapter import ParliamentConfigAdapter
from simulator.tasks import run_legislative_steps


@pytest.fixture(autouse=True)
def adapter_factory(parliament):
    mock_adapter = MagicMock(name="mockadapter", spec=Adapter)
    mock_adapter.convert.return_value = parliament
    mock_factory = MagicMock(name="mockfactory", spec=AdapterFactory)
    mock_factory.new_parliament_adapter.return_value = mock_adapter
    with patch("simulator.tasks.get_adapter_factory") as mock:
        mock.return_value = mock_factory
        yield mock


@pytest.fixture
def parliament(parliament_config):
    return ParliamentConfigAdapter().convert(parliament_config)


def test_parliament_step_no_legislative_act_skips_voting(parliament):
    result = parliament.step(has_legislative_act=False)

    assert result["approved"] is None
    assert result["vbar"] is None
    assert isinstance(result["votes"], dict)
    assert set(result["votes"].keys()) == {mp.id for mp in parliament.mps}
    assert all(v is None for v in result["votes"].values())


def test_parliament_step_legislative_act_returns_votes_shape(parliament):
    result = parliament.step(has_legislative_act=True)

    assert "t" in result
    assert "approved" in result
    assert "vbar" in result
    assert "votes" in result

    assert result["approved"] in (True, False)
    assert isinstance(result["votes"], dict)
    assert set(result["votes"].keys()) == {mp.id for mp in parliament.mps}

    # votes are 0/1 or None (abstention)
    assert all(v in (0, 1, None) for v in result["votes"].values())
    assert result["vbar"] is None or isinstance(result["vbar"], float)


def test_party_heads_detected(parliament):
    assert "majority" in parliament.party_heads
    assert "opposition" in parliament.party_heads

    assert parliament.party_heads["majority"].is_head is True
    assert parliament.party_heads["opposition"].is_head is True


def test_response_message_structure(
    channel_layer, parliament_config, parliament, monkeypatch
):
    step_mock = MagicMock(
        name="parliament.step",
        spec=parliament.step,
        return_value={"t": 1, "approved": True, "vbar": 0.75, "votes": {1: 1}},
    )
    monkeypatch.setattr(parliament, "step", step_mock)
    expected_channel_name = "test-parliament-step"

    run_legislative_steps.delay(expected_channel_name, parliament_config)

    assert channel_layer.send.call_count == 1
    actual_channel_name, data = channel_layer.send.call_args_list[0].args
    assert actual_channel_name == expected_channel_name
    assert "type" in data
    assert "payload" in data
    assert data["type"] == "parliament.step"
    assert "votes" in data["payload"]
