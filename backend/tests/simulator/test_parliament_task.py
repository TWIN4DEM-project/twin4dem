import json
from pathlib import Path
from typing import Any

from simulator.config import ParliamentConfig
from simulator.config._adapter import ParliamentConfigAdapter


def load_json(name: str) -> dict[str, Any]:
    path = Path(__file__).parent.parent / "data" / name
    return json.loads(path.read_text())


def build_parliament_from_config(cfg: ParliamentConfig):
    return ParliamentConfigAdapter().convert(cfg)


def test_parliament_step_no_legislative_act_skips_voting():
    cfg = ParliamentConfig.model_validate(load_json("legislative.json"))
    parl = build_parliament_from_config(cfg)

    result = parl.step(has_legislative_act=False)

    assert result["approved"] is None
    assert result["vbar"] is None
    assert isinstance(result["votes"], dict)
    assert set(result["votes"].keys()) == {mp.id for mp in parl.mps}
    assert all(v is None for v in result["votes"].values())


def test_parliament_step_legislative_act_returns_votes_shape():
    cfg = ParliamentConfig.model_validate(load_json("legislative.json"))
    parl = build_parliament_from_config(cfg)

    result = parl.step(has_legislative_act=True)

    assert "t" in result
    assert "approved" in result
    assert "vbar" in result
    assert "votes" in result

    assert result["approved"] in (True, False)
    assert isinstance(result["votes"], dict)
    assert set(result["votes"].keys()) == {mp.id for mp in parl.mps}

    # votes are 0/1 or None (abstention)
    assert all(v in (0, 1, None) for v in result["votes"].values())
    assert result["vbar"] is None or isinstance(result["vbar"], float)


def test_party_heads_detected():
    cfg = ParliamentConfig.model_validate(load_json("legislative.json"))
    parl = build_parliament_from_config(cfg)

    assert "majority" in parl.party_heads
    assert "opposition" in parl.party_heads

    assert parl.party_heads["majority"].is_head is True
    assert parl.party_heads["opposition"].is_head is True
