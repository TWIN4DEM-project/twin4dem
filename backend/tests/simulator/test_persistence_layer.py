import pytest

from common.dto import (
    ExecutiveSubmodelResult,
    SimulationStepResult,
    SubmodelType as DtoSubmodelType,
    VbarSubmodelResult,
)
from common.models import (
    PathSubmodelInfo,
    SimulationLogEntry,
    SimulationSubmodelLogEntry,
    SubmodelType,
    VbarSubmodelInfo,
)
from simulator.persistence import DjangoSimulationPersistence


@pytest.fixture
def persistence():
    return DjangoSimulationPersistence()


@pytest.fixture
def cabinet_result(aggrandisement_path):
    def _make(approved=True, votes=None):
        return ExecutiveSubmodelResult(
            approved=approved,
            votes=votes or {"1": 1, "2": 0},
            type=DtoSubmodelType.Cabinet,
            path=aggrandisement_path,
        )

    return _make


@pytest.fixture
def vbar_result():
    def _make(result_type=DtoSubmodelType.Court, approved=False, votes=None, vbar=0.6):
        return VbarSubmodelResult(
            approved=approved,
            votes=votes or {"1": 1, "2": 0},
            vbar=vbar,
            type=result_type,
        )

    return _make


@pytest.fixture
def step_result_factory(simulation):
    def _make(step_no=1, results=None):
        return SimulationStepResult(
            step_no=step_no,
            simulation_id=simulation.id,
            results=results or [],
        )

    return _make


@pytest.mark.django_db
def test_persist_step_requires_results(persistence, step_result_factory):
    step_result = step_result_factory(results=[])

    with pytest.raises(ValueError, match="no submodel results"):
        persistence.persist_step(step_result)

    assert SimulationLogEntry.objects.count() == 0
    assert SimulationSubmodelLogEntry.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    "final_type,expected_last_type",
    [
        (DtoSubmodelType.Court, SubmodelType.JUDICIARY),
        (DtoSubmodelType.Parliament, SubmodelType.LEGISLATIVE),
    ],
)
@pytest.mark.parametrize(
    "aggrandisement_path",
    ["decree", "legislative act"],
    indirect=True,
)
def test_persist_step_creates_log_and_submodels(
    persistence,
    simulation,
    cabinet_result,
    vbar_result,
    step_result_factory,
    final_type,
    expected_last_type,
    aggrandisement_path,
):
    results = [
        cabinet_result(approved=True, votes={"1": 1, "2": 1}),
        vbar_result(result_type=final_type, approved=False, vbar=0.25),
    ]
    step_result = step_result_factory(step_no=3, results=results)

    persistence.persist_step(step_result)

    simulation.refresh_from_db()
    assert simulation.current_step == 3
    log_entry = SimulationLogEntry.objects.get(simulation=simulation, step_no=3)
    assert log_entry.approved is False
    assert log_entry.last_decision_type == expected_last_type
    assert log_entry.aggrandisement_path == aggrandisement_path

    submodels = {entry.submodel_type: entry for entry in log_entry.submodels.all()}
    cabinet_entry = submodels[SubmodelType.EXECUTIVE]
    assert cabinet_entry.approved is True
    assert isinstance(cabinet_entry.additional_info, PathSubmodelInfo)
    assert cabinet_entry.additional_info.path == aggrandisement_path
    assert cabinet_entry.additional_info.votes == {"1": 1, "2": 1}

    final_entry = submodels[expected_last_type]
    assert final_entry.approved is False
    assert isinstance(final_entry.additional_info, VbarSubmodelInfo)
    assert final_entry.additional_info.vbar == 0.25


@pytest.mark.django_db
@pytest.mark.parametrize("aggrandisement_path", [None], indirect=True)
def test_persist_step_cabinet_without_path_uses_path_info(
    persistence,
    simulation,
    cabinet_result,
    vbar_result,
    step_result_factory,
):
    results = [
        cabinet_result(approved=False, votes={"1": 1, "2": 0}),
        vbar_result(result_type=DtoSubmodelType.Court, approved=True, vbar=0.75),
    ]
    step_result = step_result_factory(step_no=2, results=results)

    persistence.persist_step(step_result)

    log_entry = SimulationLogEntry.objects.get(simulation=simulation, step_no=2)
    assert log_entry.aggrandisement_path is None

    cabinet_entry = log_entry.submodels.get(submodel_type=SubmodelType.EXECUTIVE)
    assert isinstance(cabinet_entry.additional_info, PathSubmodelInfo)
    assert cabinet_entry.additional_info.path is None

    final_entry = log_entry.submodels.get(submodel_type=SubmodelType.JUDICIARY)
    assert isinstance(final_entry.additional_info, VbarSubmodelInfo)
    assert final_entry.additional_info.vbar == 0.75


@pytest.mark.django_db
def test_persist_step_requires_cabinet_result(
    persistence, vbar_result, step_result_factory
):
    results = [vbar_result(result_type=DtoSubmodelType.Parliament, approved=True)]
    step_result = step_result_factory(step_no=1, results=results)

    with pytest.raises(ValueError, match="no cabinet result"):
        persistence.persist_step(step_result)

    assert SimulationLogEntry.objects.count() == 0
    assert SimulationSubmodelLogEntry.objects.count() == 0
