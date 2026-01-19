from unittest.mock import MagicMock, patch

import pytest

from common.models import Court
from simulator.tasks import run_judiciary_steps
from simulator.tasks import get_adapter_factory


@pytest.fixture
def simulation(judiciary_simulation):
    return judiciary_simulation


@pytest.fixture
def court(simulation, institution_params):
    return institution_params(simulation, Court)


@pytest.fixture
def council_from_db(simulation):
    factory = get_adapter_factory()
    return factory.new_council_adapter().convert(simulation.id)


@pytest.fixture
def mocked_council_factory():
    council = MagicMock(name="council")
    council.step.return_value = {"t": 1, "approved": True, "vbar": 0.0, "votes": {}}

    adapter = MagicMock(name="council_adapter")
    adapter.convert.return_value = council

    factory = MagicMock(name="adapter_factory")
    factory.new_council_adapter.return_value = adapter

    with patch("simulator.tasks.get_adapter_factory", return_value=factory):
        yield factory, adapter, council


@pytest.mark.django_db
def test_run_judiciary_steps_integration_uses_db(simulation, court):
    actual = run_judiciary_steps.delay(simulation_id=simulation.id).get()

    assert actual["type"] == "court"
    assert "t" in actual and isinstance(actual["t"], int)
    assert "approved" in actual  # bool | None depending on model
    assert "vbar" in actual
    assert "votes" in actual and isinstance(actual["votes"], dict)

    expected_ids = {str(j.id) for j in court.judges.all()}
    actual_ids = {str(k) for k in actual["votes"].keys()}
    assert actual_ids == expected_ids


def test_run_judiciary_steps_calls_convert_with_simulation_id_when_provided(simulation, mocked_council_factory):
    factory, adapter, council = mocked_council_factory

    council.step.return_value = {"t": 1, "approved": False, "vbar": 0.0, "votes": {"1": 0}}

    adapter = MagicMock()
    adapter.convert.return_value = council

    factory = MagicMock()
    factory.new_council_adapter.return_value = adapter

    with patch("simulator.tasks.get_adapter_factory", return_value=factory):
        actual = run_judiciary_steps(simulation_id=simulation.id)

    factory.new_council_adapter.assert_called_once_with()
    adapter.convert.assert_called_once_with(simulation.id)
    council.step.assert_called_once_with()

    assert actual["type"] == "court"
    assert actual["t"] == 1
    assert isinstance(actual["votes"], dict)


def test_run_judiciary_steps_simulation_id_wins_over_data(simulation, mocked_council_factory):
    _, adapter, _ = mocked_council_factory
    fake_cfg = MagicMock(name="fake_council_config")

    run_judiciary_steps(simulation_id=simulation.id, data=fake_cfg)

    adapter.convert.assert_called_once_with(simulation.id)


@pytest.mark.django_db
def test_council_step_no_decree_skips_voting(council_from_db):
    result = council_from_db.step(has_decree=False)

    assert result["approved"] is None
    assert result["vbar"] is None
    assert isinstance(result["votes"], dict)
    assert set(map(str, result["votes"].keys())) == {str(j.id) for j in council_from_db.judges}
    assert all(v is None for v in result["votes"].values())


@pytest.mark.django_db
def test_council_step_decree_returns_votes_shape(council_from_db):
    result = council_from_db.step(has_decree=True)

    assert "t" in result
    assert "approved" in result
    assert "vbar" in result
    assert "votes" in result

    assert result["approved"] in (True, False)
    assert isinstance(result["votes"], dict)
    assert set(map(str, result["votes"].keys())) == {str(j.id) for j in council_from_db.judges}

    assert all(v in (0, 1, None) for v in result["votes"].values())
    assert result["vbar"] is None or isinstance(result["vbar"], float)