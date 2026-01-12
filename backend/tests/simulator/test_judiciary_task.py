import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from asgiref.sync import async_to_sync
from channels.layers import InMemoryChannelLayer

from simulator.tasks import run_judiciary_steps

from simulator.config import CouncilConfig
from simulator.config._adapter import CouncilConfigAdapter


def load_json(name: str) -> dict[str, Any]:
    path = Path(__file__).parent.parent / "data" / name
    return json.loads(path.read_text())


def build_council_from_config(cfg: CouncilConfig):
    return CouncilConfigAdapter().convert(cfg)


def test_council_step_no_decree_skips_voting():
    cfg = CouncilConfig.model_validate(load_json("judiciary.json"))
    council = build_council_from_config(cfg)

    result = council.step(has_decree=False)

    assert result["approved"] is None
    assert result["vbar"] is None
    assert isinstance(result["votes"], dict)
    assert set(result["votes"].keys()) == {j.id for j in council.judges}
    assert all(v is None for v in result["votes"].values())


def test_council_step_decree_returns_votes_shape():
    cfg = CouncilConfig.model_validate(load_json("judiciary.json"))
    council = build_council_from_config(cfg)

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


def test_council_president_detected():
    cfg = CouncilConfig.model_validate(load_json("judiciary.json"))
    council = build_council_from_config(cfg)

    presidents = [j for j in council.judges if j.is_president]
    assert len(presidents) == 1


def test_run_judiciary_steps_sends_council_step():
    channel_name = "test-council-step"

    cfg = CouncilConfig.model_validate(load_json("judiciary.json"))

    layer = InMemoryChannelLayer()
    receive = async_to_sync(layer.receive)

    council = MagicMock()
    council.step.return_value = {
        "t": 1,
        "approved": True,
        "vbar": 1.0,
        "votes": {1: 1, 2: 1},
    }

    council_adapter = MagicMock()
    council_adapter.convert.return_value = council

    factory = MagicMock()
    factory.new_council_adapter.return_value = council_adapter

    with (
        patch("simulator.tasks.get_channel_layer", return_value=layer),
        patch("simulator.tasks.get_adapter_factory", return_value=factory),
    ):
        run_judiciary_steps.delay(channel_name, cfg)

    msg = receive(channel_name)
    assert msg["type"] == "council.step"
    assert "votes" in msg["payload"]
    assert "approved" in msg["payload"]
