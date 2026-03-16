import pytest

from common.models import (
    SubmodelType,
    SimulationLogEntry,
    SimulationSubmodelLogEntry,
    PathSubmodelInfo,
)


@pytest.fixture
def judiciary_simulation(load_simulation):
    return load_simulation("complete/judiciary_simulation.json", 3)


@pytest.fixture
def legislative_simulation(load_simulation):
    return load_simulation("complete/legislative_simulation.json", 1)


@pytest.fixture
def simulation_type(request):
    return getattr(request, "param", SubmodelType.LEGISLATIVE)


@pytest.fixture
def simulation(request, legislative_simulation, judiciary_simulation, simulation_type):
    match simulation_type:
        case (SubmodelType.EXECUTIVE, SubmodelType.LEGISLATIVE):
            return legislative_simulation
        case _:
            return judiciary_simulation


@pytest.fixture
def additional_info(request):
    info = getattr(request, "param", None)
    if info is not None:
        return info
    return {SubmodelType.EXECUTIVE: PathSubmodelInfo(votes={"1": 0}, path=None)}


@pytest.fixture(autouse=True)
def simulation_log(request, simulation, simulation_type, additional_info):
    n = getattr(request, "param", 1)
    for step_no in range(1, n + 1):
        log = SimulationLogEntry.objects.create(
            simulation=simulation,
            approved=False,
            step_no=step_no,
        )
        for submodel_type, result in additional_info.items():
            n = len(result.votes)
            approvals = sum(1 for v in result.votes.values() if v == 1)
            SimulationSubmodelLogEntry.objects.create(
                log_entry=log,
                submodel_type=submodel_type,
                approved=approvals > (n // 2),
                additional_info=result,
            )


def test_get_by_id_not_found(admin_client):
    # 110201 could be anything as long as it's not in the database
    response = admin_client.get("/api/v1/simulation/110201/log/")

    assert response.status_code == 404
    assert response.json() == {"detail": "simulation 110201 not found"}


def test_get_by_id_anonymous_forbidden(client):
    response = client.get("/api/v1/simulation/1/log/")

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Authentication credentials were not provided."
    }


def test_get_by_id_returns_log_entries(admin_client, simulation):
    response = admin_client.get(f"/api/v1/simulation/{simulation.id}/log/")

    assert response.status_code == 200
    assert response.json() == [
        {
            "aggrandisementPath": None,
            "approved": False,
            "lastDecisionType": None,
            "simulationId": 3,
            "stepNo": 1,
            "submodelResults": [
                {
                    "abstentions": 0,
                    "approved": False,
                    "submodelType": "executive",
                    "votesAgainst": 1,
                    "votesFor": 0,
                },
            ],
        },
    ]


@pytest.mark.parametrize(
    "simulation_log,max_entries,expected_entries",
    [(2, 2, 2), (3, 2, 2), (2, 3, 2)],
    indirect=["simulation_log"],
)
def test_get_by_id_returns_top_n_log_entries(
    admin_client, simulation, max_entries, expected_entries
):
    response = admin_client.get(
        f"/api/v1/simulation/{simulation.id}/log/?max_steps={max_entries}"
    )

    assert response.status_code == 200
    # check count
    assert len(response.json()) == expected_entries
    # check descending order
    steps = [x["stepNo"] for x in response.json()]
    assert sorted(steps, reverse=True) == steps
