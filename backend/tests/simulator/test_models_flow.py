import json
from pathlib import Path
from typing import Any
from unittest.mock import patch, MagicMock

from asgiref.sync import async_to_sync
from channels.layers import InMemoryChannelLayer

from simulator.tasks import (
    run_government_steps,
    run_legislative_steps,
    run_judiciary_steps,
)
from simulator.config import GovernmentConfig, ParliamentConfig, CouncilConfig


def load_json(name: str) -> dict[str, Any]:
    path = Path(__file__).parent.parent / "data" / name
    return json.loads(path.read_text())


def test_flow_triggers_legislative_task_on_legislative_act():
    channel_name = "test-flow-legislative-act"

    gov_cfg = GovernmentConfig.model_validate(load_json("scenario3.json"))
    parl_cfg = ParliamentConfig.model_validate(load_json("legislative.json"))

    layer = InMemoryChannelLayer()

    gov = MagicMock()
    gov.step.return_value = {"approved": True, "path": "legislative act", "votes": {}}

    gov_adapter = MagicMock()
    gov_adapter.convert.return_value = gov

    parl_adapter = MagicMock()

    factory = MagicMock()
    factory.new_government_adapter.return_value = gov_adapter
    factory.new_parliament_adapter.return_value = parl_adapter

    with (
        patch("simulator.tasks.get_channel_layer", return_value=layer),
        patch("simulator.tasks.get_adapter_factory", return_value=factory),
        patch.object(run_legislative_steps, "apply_async") as mocked_apply_async,
    ):
        run_government_steps.delay(
            channel_name, data=gov_cfg, parl_data=parl_cfg, n_steps=1
        )

    mocked_apply_async.assert_called_once_with(args=[channel_name, parl_cfg])


def test_flow_does_not_trigger_legislative_task_on_decree_and_sends_government_step():
    channel_name = "test-flow-decree"

    gov_cfg = GovernmentConfig.model_validate(load_json("scenario3.json"))
    parl_cfg = ParliamentConfig.model_validate(load_json("legislative.json"))

    layer = InMemoryChannelLayer()
    receive = async_to_sync(layer.receive)

    gov = MagicMock()
    gov.step.return_value = {"approved": True, "path": "decree", "votes": {}}

    gov_adapter = MagicMock()
    gov_adapter.convert.return_value = gov

    factory = MagicMock()
    factory.new_government_adapter.return_value = gov_adapter

    with (
        patch("simulator.tasks.get_channel_layer", return_value=layer),
        patch("simulator.tasks.get_adapter_factory", return_value=factory),
        patch.object(run_legislative_steps, "apply_async") as mocked_apply_async,
    ):
        run_government_steps.delay(
            channel_name, data=gov_cfg, parl_data=parl_cfg, n_steps=1
        )

    mocked_apply_async.assert_not_called()

    msg = receive(channel_name)
    assert msg["type"] == "government.step"
    assert msg["payload"]["path"] == "decree"


def test_run_legislative_steps_sends_parliament_step():
    channel_name = "test-parliament-step"

    parl_cfg = ParliamentConfig.model_validate(load_json("legislative.json"))

    layer = InMemoryChannelLayer()
    receive = async_to_sync(layer.receive)

    parl = MagicMock()
    parl.step.return_value = {"t": 1, "approved": True, "vbar": 0.75, "votes": {1: 1}}

    parl_adapter = MagicMock()
    parl_adapter.convert.return_value = parl

    factory = MagicMock()
    factory.new_parliament_adapter.return_value = parl_adapter

    with (
        patch("simulator.tasks.get_channel_layer", return_value=layer),
        patch("simulator.tasks.get_adapter_factory", return_value=factory),
    ):
        run_legislative_steps.delay(channel_name, parl_cfg)

    msg = receive(channel_name)
    assert msg["type"] == "parliament.step"
    assert "votes" in msg["payload"]


def test_flow_triggers_judiciary_task_on_decree():
    channel_name = "test-flow-decree-triggers-judiciary"

    gov_cfg = GovernmentConfig.model_validate(load_json("scenario3.json"))
    parl_cfg = ParliamentConfig.model_validate(load_json("legislative.json"))
    council_cfg = CouncilConfig.model_validate(load_json("judiciary.json"))

    layer = InMemoryChannelLayer()
    receive = async_to_sync(layer.receive)

    gov = MagicMock()
    gov.step.return_value = {"approved": True, "path": "decree", "votes": {}}

    gov_adapter = MagicMock()
    gov_adapter.convert.return_value = gov

    factory = MagicMock()
    factory.new_government_adapter.return_value = gov_adapter

    with (
        patch("simulator.tasks.get_channel_layer", return_value=layer),
        patch("simulator.tasks.get_adapter_factory", return_value=factory),
        patch.object(run_legislative_steps, "apply_async") as mocked_leg_apply_async,
        patch.object(run_judiciary_steps, "apply_async") as mocked_jud_apply_async,
    ):
        run_government_steps.delay(
            channel_name,
            data=gov_cfg,
            parl_data=parl_cfg,
            council_data=council_cfg,
            n_steps=1,
        )

    mocked_leg_apply_async.assert_not_called()

    mocked_jud_apply_async.assert_called_once_with(args=[channel_name, council_cfg])

    msg = receive(channel_name)
    assert msg["payload"]["path"] == "decree"
