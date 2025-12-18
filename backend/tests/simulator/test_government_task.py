import json
from pathlib import Path
from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import InMemoryChannelLayer
from unittest.mock import patch

from simulator.tasks import run_government_steps
from simulator.config import GovernmentConfig


def load_json(name):
    path = Path(__file__).parent.parent / "data" / name
    return json.loads(path.read_text())


def test_run_government_steps():
    channel_name = "test-government"

    config = load_json("scenario3.json")
    gov_cfg = GovernmentConfig.model_validate(config)

    layer = InMemoryChannelLayer()
    receive = async_to_sync(layer.receive)

    with patch("simulator.tasks.get_channel_layer", return_value=layer):
        run_government_steps.delay(channel_name, gov_cfg, 3)

    messages = [receive(channel_name) for _ in range(3)]

    assert len(messages) == 3

    for msg in messages:
        assert msg["type"] == "government.step"
        payload = msg["payload"]
        assert "approved" in payload
        assert "path" in payload
        assert "votes" in payload


def test_government_scenario_1_output():
    channel_name = "test-government-scenario-1"
    n_steps = 5

    config = load_json("scenario1.json")
    gov_cfg = GovernmentConfig.model_validate(config)

    layer = InMemoryChannelLayer()
    receive = async_to_sync(layer.receive)

    with patch("simulator.tasks.get_channel_layer", return_value=layer):
        run_government_steps.delay(channel_name, gov_cfg, n_steps)

    messages: list[dict[str, Any]] = [receive(channel_name) for _ in range(n_steps)]
    payloads: list[dict[str, Any]] = [msg["payload"] for msg in messages]

    for p in payloads:
        assert "approved" in p
        assert "path" in p

    assert (step["approved"] is False for step in payloads)


def test_government_scenario_2_output():
    channel_name = "test-government-scenario-2"
    n_steps = 5

    config = load_json("scenario3.json")
    gov_cfg = GovernmentConfig.model_validate(config)

    layer = InMemoryChannelLayer()
    receive = async_to_sync(layer.receive)

    with patch("simulator.tasks.get_channel_layer", return_value=layer):
        run_government_steps.delay(channel_name, gov_cfg, n_steps)

    messages: list[dict[str, Any]] = [receive(channel_name) for _ in range(n_steps)]
    payloads: list[dict[str, Any]] = [msg["payload"] for msg in messages]

    for p in payloads:
        assert "approved" in p
        assert "path" in p

    assert (step["approved"] is True for step in payloads)
