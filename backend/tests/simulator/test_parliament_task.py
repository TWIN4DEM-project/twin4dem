from unittest.mock import MagicMock, patch

import pytest

from common.models import Parliament
from simulator.tasks import run_legislative_steps
from simulator.adapters import AdapterFactory, Adapter
from simulator.tasks import get_adapter_factory


@pytest.fixture
def simulation(legislative_simulation):
    return legislative_simulation


@pytest.fixture
def parliament(simulation, institution_params):
    return institution_params(simulation, Parliament)


@pytest.fixture
def parliament_from_db(simulation):
    factory = get_adapter_factory()
    return factory.new_parliament_adapter().convert(simulation.id)


@pytest.fixture
def mocked_parliament_factory():
    """
    Provides (factory, adapter, parl) and patches simulator.tasks.get_adapter_factory
    so run_legislative_steps uses these mocks.
    """
    parl = MagicMock(name="parliament")
    parl.step.return_value = {"approved": True, "vbar": 0.5, "votes": {}}

    adapter = MagicMock(name="parliament_adapter", spec=Adapter)
    adapter.convert.return_value = parl

    factory = MagicMock(name="adapter_factory", spec=AdapterFactory)
    factory.new_parliament_adapter.return_value = adapter

    with patch("simulator.tasks.get_adapter_factory", return_value=factory):
        yield factory, adapter, parl


@pytest.mark.django_db
def test_run_legislative_steps_integration_uses_db_via_simulation_id(simulation, parliament):
    result = run_legislative_steps.delay(simulation_id=simulation.id).get()

    assert result["type"] == "parliament"
    assert "t" in result
    assert "approved" in result
    assert "vbar" in result
    assert "votes" in result and isinstance(result["votes"], dict)

    expected_ids = {str(mp.id) for mp in parliament.members.all()}
    actual_ids = {str(k) for k in result["votes"].keys()}
    assert actual_ids == expected_ids


def test_run_legislative_steps_calls_convert_with_simulation_id(mocked_parliament_factory):
    factory, adapter, parl = mocked_parliament_factory

    parl.step.return_value = {"approved": True, "vbar": 0.5, "votes": {}}

    result = run_legislative_steps(simulation_id=123)

    factory.new_parliament_adapter.assert_called_once_with()
    adapter.convert.assert_called_once_with(123)
    parl.step.assert_called_once_with()

    assert result["type"] == "parliament"
    assert result["approved"] is True


def test_run_legislative_steps_calls_convert_with_data_when_no_simulation_id(mocked_parliament_factory):
    _, adapter, parl = mocked_parliament_factory
    fake_cfg = MagicMock(name="fake_parliament_config")

    parl.step.return_value = {"approved": False, "vbar": 0.0, "votes": {}}

    result = run_legislative_steps(simulation_id=None, data=fake_cfg)

    adapter.convert.assert_called_once_with(fake_cfg)
    assert result["type"] == "parliament"
    assert result["approved"] is False


def test_run_legislative_steps_simulation_id_wins_over_data(mocked_parliament_factory):
    _, adapter, _ = mocked_parliament_factory
    fake_cfg = MagicMock(name="fake_parliament_config")

    run_legislative_steps(simulation_id=999, data=fake_cfg)

    adapter.convert.assert_called_once_with(999)


@pytest.mark.django_db
def test_parliament_step_no_legislative_act_skips_voting(parliament_from_db):
    result = parliament_from_db.step(has_legislative_act=False)

    assert result["approved"] is None
    assert result["vbar"] is None
    assert isinstance(result["votes"], dict)

    expected_ids = {str(mp.id) for mp in parliament_from_db.mps}  # see note below
    assert set(map(str, result["votes"].keys())) == expected_ids
    assert all(v is None for v in result["votes"].values())


@pytest.mark.django_db
def test_parliament_step_legislative_act_returns_votes_shape(parliament_from_db):
    result = parliament_from_db.step(has_legislative_act=True)

    assert "t" in result
    assert "approved" in result
    assert "vbar" in result
    assert "votes" in result

    assert result["approved"] in (True, False)
    assert isinstance(result["votes"], dict)

    expected_ids = {str(mp.id) for mp in parliament_from_db.mps}
    assert set(map(str, result["votes"].keys())) == expected_ids

    assert all(v in (0, 1, None) for v in result["votes"].values())
    assert result["vbar"] is None or isinstance(result["vbar"], float)
