import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from common.models._simulation import SubmodelType
from common.models import (
    SimulationLogEntry,
    SimulationSubmodelLogEntry,
    PathSubmodelInfo,
    VbarSubmodelInfo,
)


@pytest.mark.parametrize("approved", [True, False])
@pytest.mark.parametrize(
    "log_simulation_type",
    [SubmodelType.LEGISLATIVE, SubmodelType.JUDICIARY],
    indirect=True,
)
def test_simulation_log_unique_step_per_simulation(
    log_simulation, log_simulation_type, approved
):
    SimulationLogEntry.objects.create(
        simulation=log_simulation, approved=approved, step_no=1
    )
    with pytest.raises(ValidationError) as err_proxy:
        SimulationLogEntry.objects.create(
            simulation=log_simulation, approved=approved, step_no=1
        )

    assert (
        str(err_proxy.value.message_dict["__all__"])
        == "['Simulation log entry with this Simulation and Step no already exists.']"
    )


@pytest.mark.parametrize(
    "log_simulation_type",
    [SubmodelType.LEGISLATIVE, SubmodelType.JUDICIARY],
    indirect=True,
)
def test_simulation_log_invalid_aggrandisement_path_raises_error(
    log_simulation, log_simulation_type
):
    with pytest.raises(ValidationError) as err_proxy:
        SimulationLogEntry.objects.create(
            simulation=log_simulation,
            approved=True,
            step_no=1,
            aggrandisement_path="abc",
        )

    assert (
        str(err_proxy.value.message_dict["aggrandisement_path"])
        == "[\"Value 'abc' is not a valid choice.\"]"
    )


def test_simulation_submodel_log_unique_submodel_type_per_log_entry(log_simulation):
    log = SimulationLogEntry.objects.create(
        simulation=log_simulation,
        approved=False,
        step_no=1,
    )
    path_info = PathSubmodelInfo(votes={"1": 0}, path="decree")
    SimulationSubmodelLogEntry.objects.create(
        log_entry=log,
        submodel_type=SubmodelType.EXECUTIVE,
        approved=False,
        additional_info=path_info,
    )

    with pytest.raises(IntegrityError) as err_proxy:
        path_info.votes["1"] = 1
        SimulationSubmodelLogEntry.objects.create(
            log_entry=log,
            submodel_type=SubmodelType.EXECUTIVE,
            approved=True,
            additional_info=path_info,
        )

    assert (
        str(err_proxy.value)
        == "UNIQUE constraint failed: simulation_submodel_log.log_entry_id, simulation_submodel_log.submodel_type"
    )


@pytest.mark.parametrize(
    "additional_info",
    [
        (PathSubmodelInfo(votes={"1": 0}, path="decree")),
        (VbarSubmodelInfo(votes={"1": 1}, vbar=0.3)),
    ],
)
def test_simulation_submodel_log_allows_both_path_and_vbar(
    log_simulation, additional_info
):
    log = SimulationLogEntry.objects.create(
        simulation=log_simulation,
        approved=False,
        step_no=1,
    )
    submodel_log = SimulationSubmodelLogEntry.objects.create(
        log_entry=log,
        submodel_type=SubmodelType.EXECUTIVE,
        approved=False,
        additional_info=additional_info,
    )

    # the assertion verifies the deserialization of data
    assert submodel_log.additional_info == additional_info
