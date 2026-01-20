from unittest.mock import MagicMock, patch

import pytest

from simulator.adapters import Adapter, AdapterFactory
from simulator.tasks import subsequent_submodel


@pytest.fixture
def submodel_mock(vbar_result):
    mock = MagicMock(name="submodel")
    mock.step = MagicMock(name="submodel.convert", return_value=vbar_result)
    return mock


@pytest.fixture
def adapter_mock(submodel_mock):
    mock = MagicMock(name="mock-adapter", spec=Adapter)
    mock.convert.return_value = submodel_mock
    return mock


@pytest.fixture(autouse=True)
def adapter_factory_mock(adapter_mock):
    mock = MagicMock(name="mock-adapter-factory", spec=AdapterFactory)
    mock.new_council_adapter.return_value = adapter_mock
    mock.new_parliament_adapter.return_value = adapter_mock
    with patch("simulator.tasks.get_adapter_factory", return_value=mock):
        yield mock


@pytest.mark.parametrize(
    "approved,aggrandisement_path", [(True, "decree")], indirect=True
)
def test_decree_path_runs_council_submodel(
    executive_submodel_output, adapter_factory_mock
):
    subsequent_submodel.delay(executive_submodel_output).get()

    assert adapter_factory_mock.new_council_adapter.call_count == 1
    assert adapter_factory_mock.new_parliament_adapter.call_count == 0


@pytest.mark.parametrize(
    "approved,aggrandisement_path", [(True, "legislative act")], indirect=True
)
def test_legislative_path_runs_parliament_submodel(
    executive_submodel_output, adapter_factory_mock
):
    subsequent_submodel.delay(executive_submodel_output).get()

    assert adapter_factory_mock.new_council_adapter.call_count == 0
    assert adapter_factory_mock.new_parliament_adapter.call_count == 1


@pytest.mark.parametrize("vbar_approved", [True, False], indirect=True)
@pytest.mark.parametrize(
    "approved,aggrandisement_path",
    [
        (True, "decree"),
        (True, "legislative act"),
    ],
    indirect=True,
)
def test_task_returns_expected_output(executive_submodel_output, vbar_result):
    expected = vbar_result.model_dump(mode="json", by_alias=True)
    actual = subsequent_submodel.delay(executive_submodel_output).get()

    assert len(actual["results"]) == 2
    assert actual["results"][-1] == expected
