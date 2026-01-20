from unittest.mock import MagicMock, patch

import pytest
from channels.layers import BaseChannelLayer

from common.dto import (
    AggrandisementUnitPath,
    SimulationStepResult,
    ExecutiveSubmodelResult,
    SubmodelType,
    VbarSubmodelResult,
)


@pytest.fixture
def channel_layer():
    mock = MagicMock(name="mock channel layer", spec=BaseChannelLayer)
    with patch("simulator.tasks.get_channel_layer", return_value=mock):
        yield mock


@pytest.fixture
def simulation(executive_simulation):
    return executive_simulation


@pytest.fixture
def approved(request):
    return bool(getattr(request, "param", False))


@pytest.fixture
def aggrandisement_path(request) -> AggrandisementUnitPath:
    return getattr(request, "param", None)


@pytest.fixture
def executive_submodel_output(simulation, approved, aggrandisement_path):
    return SimulationStepResult(
        step_no=0,
        simulation_id=simulation.id,
        results=[
            ExecutiveSubmodelResult(
                approved=approved,
                votes={"1": 1},
                type=SubmodelType.Cabinet,
                path=aggrandisement_path,
            )
        ],
    ).model_dump(mode="json", by_alias=True)


@pytest.fixture
def vbar_approved(request):
    return bool(getattr(request, "param", False))


@pytest.fixture
def vbar_result(request, vbar_approved, aggrandisement_path):
    result_type = (
        SubmodelType.Court
        if aggrandisement_path == "decree"
        else SubmodelType.Parliament
    )
    default = VbarSubmodelResult(
        approved=vbar_approved, votes={"1": 1}, vbar=1.0, type=result_type
    )
    return getattr(request, "param", default)
