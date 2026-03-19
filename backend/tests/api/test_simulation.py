import json
import math
import pytest

from django.db.models import Sum

from common.dto import AggrandisementBatch
from common.models import UserSettings
from common.models._simulation import SubmodelType, Simulation
from common.models import (
    SimulationLogEntry,
    SimulationSubmodelLogEntry,
    PathSubmodelInfo,
    VbarSubmodelInfo,
)


@pytest.fixture
def uploaded_zip(aggrandisement_batch_path):
    from io import BytesIO
    import zipfile
    from django.core.files.uploadedfile import SimpleUploadedFile

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zip_file:
        zip_file.write(aggrandisement_batch_path, arcname="batch.json")
    zip_buffer.seek(0)

    return SimpleUploadedFile(
        "simulation_data.zip", zip_buffer.getvalue(), content_type="application/zip"
    )


def test_post_success_basic_data(admin_client):
    response = admin_client.post("/api/v1/simulation/")

    assert response.status_code == 201
    data = response.json()
    assert data["createdAt"] is not None
    assert data["currentStep"] == 0
    assert data["id"] is not None
    assert data["officeRetentionSensitivity"] == 5.0
    assert data["socialInfluenceSusceptibility"] == 0.5
    assert "params" in data and len(data["params"]) == 3


def test_post_success_cabinet_is_created(admin_client, admin_user):
    response = admin_client.post("/api/v1/simulation/")

    admin_settings = UserSettings.objects.get(user=admin_user)
    data = response.json()
    first_param = data["params"][0]
    assert first_param["type"] == "cabinet"
    assert first_param["cabinet"] is not None
    cabinet_settings = first_param["cabinet"]
    assert cabinet_settings["id"] is not None
    assert (
        cabinet_settings["label"]
        == f"test_admin-simulation-{cabinet_settings["id"]:06}-cabinet"
    )
    assert cabinet_settings["ministers"] is not None

    ministers = cabinet_settings["ministers"]
    assert len(ministers) == admin_settings.government_size
    assert len([m for m in ministers if m["isPrimeMinister"]]) == 1
    pm = next(m for m in ministers if m["isPrimeMinister"])
    assert len(pm["neighboursOut"]) == admin_settings.government_size - 1
    assert pm["influence"] == 1.0
    assert len(pm["weights"]) == 6
    assert all(0 <= x <= 1 for x in pm["weights"])
    assert round(sum(pm["weights"])) == 1
    minister_dict = {m["id"]: m for m in ministers}
    for m in ministers:
        assert len(m["weights"]) == 6
        assert all(0 <= x <= 1 for x in m["weights"])
        assert round(sum(m["weights"])) == 1, f"sum of weights of {m["id"]} != 1"
        if not m["isPrimeMinister"]:
            assert (
                len(m["neighboursOut"]) <= admin_settings.government_connectivity_degree
            ), f"minister {m["id"]} has invalid out-degree"
            assert (
                len(m["neighboursIn"]) <= admin_settings.government_connectivity_degree
            ), f"minister {m["id"]} has invalid in-degree"
        for out_n in m["neighboursOut"]:
            assert m["id"] in minister_dict[out_n]["neighboursIn"]
        for in_n in m["neighboursIn"]:
            assert m["id"] in minister_dict[in_n]["neighboursOut"]


def test_post_success_parliament_is_created(admin_client, admin_user):
    admin_settings = UserSettings.objects.get(user=admin_user)
    admin_settings.parliament_opposition_probability_for = 0.8
    admin_settings.parliament_majority_probability_for = 0.42
    admin_settings.save()

    response = admin_client.post("/api/v1/simulation/")

    data = response.json()
    parliament_param = data["params"][1]
    assert parliament_param["type"] == "parliament"
    parliament = parliament_param["parliament"]
    assert parliament["id"] == 1
    assert parliament["label"] == "test_admin-simulation-000001-parliament"
    assert parliament["majorityProbabilityFor"] == 0.42
    assert parliament["oppositionProbabilityFor"] == 0.8
    mps = parliament["members"]
    assert len(mps) == admin_settings.parliament_size
    heads = 0
    party_members = {party.label: 0 for party in admin_settings.parties.all()}
    for mp in mps:
        heads += mp["isHead"]
        party_members[mp["partyLabel"]] += 1
        assert math.isclose(sum(mp["weights"]), 1)

    assert heads == admin_settings.parties.count()
    assert party_members == {
        item["label"]: item["total"]
        for item in admin_settings.parties.values("label").annotate(
            total=Sum("member_count")
        )
    }


def test_post_judiciary_is_created(admin_client, admin_user):
    admin_settings = UserSettings.objects.get(user=admin_user)
    admin_settings.court_probability_for = 0.42
    admin_settings.save()

    response = admin_client.post("/api/v1/simulation/")

    data = response.json()
    court_param = data["params"][2]
    assert court_param["type"] == "court"
    court = court_param["court"]
    assert court["id"] == 1
    assert court["label"] == "test_admin-simulation-000001-court"
    assert court["probabilityFor"] == 0.42
    judges = court["judges"]
    assert len(judges) == admin_settings.court_size
    party_positions = set(
        x["position"] for x in admin_settings.parties.values("position").distinct()
    )
    party_labels = set(
        x["label"] for x in admin_settings.parties.values("label").distinct()
    )
    heads = 0
    for judge in judges:
        heads += judge["isPresident"]
        assert math.isclose(sum(judge["weights"]), 1)
        assert judge["partyLabel"] in party_labels
        assert judge["partyPosition"] in party_positions


def test_post_anonymous_forbidden(client):
    response = client.get("/api/v1/simulation/")

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Authentication credentials were not provided."
    }


def test_list_success(admin_client):
    admin_client.post("/api/v1/simulation/")
    response = admin_client.get("/api/v1/simulation/")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["createdAt"] is not None
    assert data[0]["updatedAt"] is not None
    assert data[0]["id"] is not None
    assert data[0]["currentStep"] == 0
    assert data[0]["status"] == "new"


def test_list_anonymous_forbidden(client):
    response = client.get("/api/v1/simulation/")

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Authentication credentials were not provided."
    }


def test_patch_success(admin_client):
    admin_client.post("/api/v1/simulation/")
    response = admin_client.patch(
        "/api/v1/simulation/1/",
        data=json.dumps({"status": "complete"}),
        content_type="application/json",
    )

    assert response.status_code == 202
    assert response.json() == {"detail": "simulation 1 updated"}


def test_patch_not_found(admin_client):
    response = admin_client.patch(
        "/api/v1/simulation/1/",
        data=json.dumps({"status": "complete"}),
        content_type="application/json",
    )

    assert response.status_code == 404


def test_patch_bad_status(admin_client):
    admin_client.post("/api/v1/simulation/")
    response = admin_client.patch(
        "/api/v1/simulation/1/",
        data=json.dumps({"status": "invalid status value"}),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json() == {
        "status": ['"invalid status value" is not a valid choice.']
    }


def test_patch_bad_field(admin_client):
    admin_client.post("/api/v1/simulation/")
    response = admin_client.patch(
        "/api/v1/simulation/1/",
        data=json.dumps({"currentStep": 1}),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json() == {"currentStep": ["not allowed to update field"]}


def test_patch_anonymous_forbidden(client):
    response = client.patch("/api/v1/simulation/1/")

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Authentication credentials were not provided."
    }


@pytest.fixture
def simulation_id(admin_client, request):
    steps = request.param

    # create new simulation entry
    response = admin_client.post("/api/v1/simulation/")
    data: dict = response.json()

    # create a step for each step specified
    for i, step in enumerate(steps):
        # create simulation log entry
        if step == "judiciary":
            aggrandisement_path = "decree"
        else:
            aggrandisement_path = "legislative act"

        # create log entry
        log = SimulationLogEntry.objects.create(
            simulation_id=data["id"],
            step_no=i + 1,
            approved=False,
            last_decision_type=step,
            aggrandisement_path=aggrandisement_path,
        )

        # create executive submodel entry AND judiciary or legislative one
        SimulationSubmodelLogEntry.objects.create(
            log_entry=log,
            submodel_type=SubmodelType.EXECUTIVE,
            approved=False,
            additional_info=PathSubmodelInfo(
                votes={f"{i+1}": 0}, path=aggrandisement_path
            ),
        )

        SimulationSubmodelLogEntry.objects.create(
            log_entry=log,
            submodel_type=(
                SubmodelType.JUDICIARY
                if step == "judiciary"
                else SubmodelType.LEGISLATIVE
            ),
            approved=True,
            additional_info=VbarSubmodelInfo(votes={f"{i + 1}": 1}, vbar=0.3),
        )

    return data["id"]


EXPECTED_EMPTY = []
EXPECTED_JUD = [
    {
        "type": "cabinet",
        "path": "decree",
        "approved": False,
        "votes": {"1": 0},
    },
    {"type": "court", "vbar": 0.3, "approved": True, "votes": {"1": 1}},
]

EXPECTED_LEG = [
    {
        "type": "cabinet",
        "path": "legislative act",
        "approved": False,
        "votes": {"1": 0},
    },
    {
        "type": "parliament",
        "vbar": 0.3,
        "approved": True,
        "votes": {"1": 1},
    },
]

EXPECTED_JUD_JUD = [
    {
        "type": "cabinet",
        "path": "decree",
        "approved": False,
        "votes": {"2": 0},
    },
    {"type": "court", "vbar": 0.3, "approved": True, "votes": {"2": 1}},
]

EXPECTED_LEG_LEG = [
    {
        "type": "cabinet",
        "path": "legislative act",
        "approved": False,
        "votes": {"2": 0},
    },
    {
        "type": "parliament",
        "vbar": 0.3,
        "approved": True,
        "votes": {"2": 1},
    },
]

EXPECTED_JUD_LEG = [
    {
        "type": "cabinet",
        "path": "legislative act",
        "approved": False,
        "votes": {"2": 0},
    },
    {"type": "court", "vbar": 0.3, "approved": True, "votes": {"1": 1}},
    {
        "type": "parliament",
        "vbar": 0.3,
        "approved": True,
        "votes": {"2": 1},
    },
]

EXPECTED_LEG_JUD = [
    {
        "type": "cabinet",
        "path": "decree",
        "approved": False,
        "votes": {"2": 0},
    },
    {"type": "court", "vbar": 0.3, "approved": True, "votes": {"2": 1}},
    {
        "type": "parliament",
        "vbar": 0.3,
        "approved": True,
        "votes": {"1": 1},
    },
]

EXPECTED_JUD_JUD_LEG = [
    {
        "type": "cabinet",
        "path": "legislative act",
        "approved": False,
        "votes": {"3": 0},
    },
    {"type": "court", "vbar": 0.3, "approved": True, "votes": {"2": 1}},
    {
        "type": "parliament",
        "vbar": 0.3,
        "approved": True,
        "votes": {"3": 1},
    },
]

EXPECTED_JUD_LEG_JUD = [
    {
        "type": "cabinet",
        "path": "decree",
        "approved": False,
        "votes": {"3": 0},
    },
    {"type": "court", "vbar": 0.3, "approved": True, "votes": {"3": 1}},
    {
        "type": "parliament",
        "vbar": 0.3,
        "approved": True,
        "votes": {"2": 1},
    },
]

EXPECTED_LEG_LEG_JUD = [
    {
        "type": "cabinet",
        "path": "decree",
        "approved": False,
        "votes": {"3": 0},
    },
    {"type": "court", "vbar": 0.3, "approved": True, "votes": {"3": 1}},
    {
        "type": "parliament",
        "vbar": 0.3,
        "approved": True,
        "votes": {"2": 1},
    },
]


TEST_CASES = [
    pytest.param([], EXPECTED_EMPTY, id="no_steps"),
    pytest.param(
        ["judiciary"],
        EXPECTED_JUD,
        id="judiciary",
    ),
    pytest.param(
        ["legislative"],
        EXPECTED_LEG,
        id="legislative",
    ),
    pytest.param(
        ["judiciary", "judiciary"],
        EXPECTED_JUD_JUD,
        id="judiciary_judiciary",
    ),
    pytest.param(
        ["legislative", "legislative"],
        EXPECTED_LEG_LEG,
        id="legislative_legislative",
    ),
    pytest.param(
        ["judiciary", "legislative"],
        EXPECTED_JUD_LEG,
        id="judiciary_legislative",
    ),
    pytest.param(
        ["legislative", "judiciary"],
        EXPECTED_LEG_JUD,
        id="legislative_judiciary",
    ),
]


@pytest.mark.parametrize(
    "simulation_id, expected_results",
    TEST_CASES,
    indirect=["simulation_id"],
)
def test_get_simulation_with_historic_votes(
    admin_client, simulation_id, expected_results
):
    response = admin_client.get(
        f"/api/v1/simulation/{simulation_id}/?withHistoricVotes=true"
    )

    assert response.status_code == 200
    data = response.json()
    # order: cabinet, court, parliament
    results = sorted(data["results"], key=lambda result: result["type"])
    print(results)
    assert results == expected_results


@pytest.mark.parametrize("flag", ["true", "True", "1", "yes", "Yes"])
def test_get_simulation_with_historic_votes_valid_flags(admin_client, flag):
    # create new simulation
    response = admin_client.post("/api/v1/simulation/")
    data: dict = response.json()

    response = admin_client.get(
        f"/api/v1/simulation/{data["id"]}/?withHistoricVotes={flag}"
    )

    assert response.status_code == 200
    data = response.json()
    # order: cabinet, court, parliament

    assert data.get("results") == []


@pytest.mark.parametrize("flag", ["false", "0", "", "random", "hai", "yep", None])
def test_get_simulation_with_historic_votes_invalid_flags(admin_client, flag):
    # create new simulation
    response = admin_client.post("/api/v1/simulation/")
    data: dict = response.json()

    query_params = "" if flag is None else f"?withHistoricVotes={flag}"

    response = admin_client.get(f"/api/v1/simulation/{data["id"]}/{query_params}")

    assert response.status_code == 200
    data = response.json()
    # order: cabinet, court, parliament

    print(data)

    assert data.get("results") is None


def test_post_with_zip_file_upload(admin_client, uploaded_zip, aggrandisement_batch):
    settings = AggrandisementBatch.model_validate(aggrandisement_batch).settings
    response = admin_client.post(
        "/api/v1/simulation/", {"file": uploaded_zip}, format="multipart"
    )

    assert response.status_code == 201
    data = response.json()
    assert data["createdAt"] is not None
    assert data["currentStep"] == 0
    assert data["id"] is not None
    assert data["officeRetentionSensitivity"] == 5.0
    assert data["socialInfluenceSusceptibility"] == 0.5
    assert "params" in data and len(data["params"]) == 3
    cabinet = data["params"][0]["cabinet"]
    assert len(cabinet["ministers"]) == len(settings.executive.ministers)
    parliament = data["params"][1]["parliament"]
    assert len(parliament["members"]) == len(settings.legislative.mps)
    court = data["params"][2]["court"]
    assert len(court["judges"]) == len(settings.judiciary.judges)


def test_post_with_zip_file_sets_influence(
    admin_client, uploaded_zip, aggrandisement_batch
):
    settings = AggrandisementBatch.model_validate(aggrandisement_batch).settings
    response = admin_client.post(
        "/api/v1/simulation/", {"file": uploaded_zip}, format="multipart"
    )

    assert response.status_code == 201
    data = response.json()
    assert data["createdAt"] is not None
    assert data["currentStep"] == 0
    assert data["id"] is not None
    assert data["officeRetentionSensitivity"] == 5.0
    assert data["socialInfluenceSusceptibility"] == 0.5
    assert "params" in data and len(data["params"]) == 3
    cabinet = data["params"][0]["cabinet"]
    assert len(cabinet["ministers"]) == len(settings.executive.ministers)
    for x, y in zip(cabinet["ministers"], settings.executive.ministers):
        assert (
            x["influence"] == y.influence
        ), f"minister {x["label"]} did not have the expected influence {y.influence}"
    court = data["params"][2]["court"]
    assert len(court["judges"]) == len(settings.judiciary.judges)
    for x, y in zip(court["judges"], settings.judiciary.judges):
        assert (
            x["influence"] == y.influence
        ), f"judge {x["label"]} did not have the expected influence {y.influence}"


def test_post_with_zip_file_initializes_simulation_steps(
    admin_client, admin_user, uploaded_zip, aggrandisement_batch
):
    user_settings = UserSettings.objects.get(user=admin_user)
    batch_dto = AggrandisementBatch.model_validate(aggrandisement_batch)
    admin_client.post("/api/v1/simulation/", {"file": uploaded_zip}, format="multipart")

    simulation = Simulation.objects.filter(user_settings=user_settings).first()

    assert simulation.batch.count() == 1
    batch = simulation.batch.first()
    assert batch.units.count() == len(batch_dto.aggrandisement_units)
    u = batch.units.first()
    assert u.step_no == batch_dto.aggrandisement_units[0].step
    assert u.ministers.count() == len(
        batch_dto.aggrandisement_units[0].beliefs.ministers
    )
    assert u.mps.count() == len(batch_dto.aggrandisement_units[0].beliefs.mps)
    assert u.judges.count() == len(batch_dto.aggrandisement_units[0].beliefs.judges)
