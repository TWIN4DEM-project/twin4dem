import json
import math
import zipfile
from datetime import datetime
from io import BytesIO

import pytest

from api.viewsets._simulation import SimulationViewSet


from common.dto import AggrandisementBatch
from common.models import UserSettings
from common.models._simulation import SubmodelType, Simulation
from common.models import (
    SimulationLogEntry,
    SimulationSubmodelLogEntry,
    PathSubmodelInfo,
    VbarSubmodelInfo,
)
from django.core.files.uploadedfile import SimpleUploadedFile, TemporaryUploadedFile
from unittest.mock import patch

from common.models import (
    AggrandisementBatch as AggrandisementBatchModel,
    AggrandisementUnit,
    Party,
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


def test_post_success_cabinet_is_created(admin_client):
    response = admin_client.post("/api/v1/simulation/")

    data = response.json()
    first_param = data["params"][0]
    assert first_param["type"] == "cabinet"
    cabinet_settings = first_param["cabinet"]
    assert cabinet_settings["id"] == 1
    assert cabinet_settings["label"] == "test_admin-simulation-000001-cabinet"
    assert cabinet_settings["probabilityFor"] == 0.7
    assert cabinet_settings["connectivityDegree"] == 2

    ministers = cabinet_settings["ministers"]
    assert 3 <= len(ministers) <= 9
    assert len([m for m in ministers if m["isPrimeMinister"]]) == 1
    pm = next(m for m in ministers if m["isPrimeMinister"])
    assert pm["influence"] == 1.0
    assert len(pm["neighboursOut"]) == len(ministers) - 1
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
                len(m["neighboursOut"]) <= 2
            ), f"minister {m["id"]} has invalid out-degree"
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
    assert parliament["id"] == 2
    assert parliament["label"] == "test_admin-simulation-000001-parliament"
    assert parliament["majorityProbabilityFor"] == 0.42
    assert parliament["oppositionProbabilityFor"] == 0.8
    mps = parliament["members"]
    assert len(mps) == 100
    heads = 0
    for mp in mps:
        heads += mp["isHead"]
        assert mp["partyLabel"] in ("majority", "opposition")
        assert mp["partyPosition"] in ("majority", "opposition")
        assert math.isclose(sum(mp["weights"]), 1)

    assert heads == 2


def test_post_judiciary_is_created(admin_client, admin_user):
    admin_settings = UserSettings.objects.get(user=admin_user)
    admin_settings.court_probability_for = 0.42
    admin_settings.save()

    response = admin_client.post("/api/v1/simulation/")

    data = response.json()
    court_param = data["params"][2]
    assert court_param["type"] == "court"
    court = court_param["court"]
    assert court["id"] == 3
    assert court["label"] == "test_admin-simulation-000001-court"
    assert court["probabilityFor"] == 0.42
    judges = court["judges"]
    assert len(judges) == 5
    heads = 0
    for judge in judges:
        heads += judge["isPresident"]
        assert math.isclose(sum(judge["weights"]), 1)
        assert judge["partyLabel"] in ("majority", "opposition")
        assert judge["partyPosition"] in ("majority", "opposition")
    assert heads == 1
    president = next(judge for judge in judges if judge["isPresident"])
    assert president["influence"] == 1.0


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
    assert data[0]["id"] == 1
    assert data[0]["currentStep"] == 0
    assert data[0]["status"] == "new"
    assert data[0]["label"] == "random simulation 1"


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


def create_simulation_with_steps(admin_client, steps):
    """Create an approved cabinet decision and its selected branch per step."""
    response = admin_client.post("/api/v1/simulation/")
    data: dict = response.json()

    for i, step in enumerate(steps):
        if step == "judiciary":
            aggrandisement_path = "decree"
        else:
            aggrandisement_path = "legislative act"

        log = SimulationLogEntry.objects.create(
            simulation_id=data["id"],
            step_no=i + 1,
            approved=True,
            last_decision_type=step,
            aggrandisement_path=aggrandisement_path,
        )

        SimulationSubmodelLogEntry.objects.create(
            log_entry=log,
            submodel_type=SubmodelType.EXECUTIVE,
            approved=True,
            additional_info=PathSubmodelInfo(
                votes={f"{i+1}": 1}, path=aggrandisement_path
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
        "approved": True,
        "votes": {"1": 1},
    },
    {"type": "court", "vbar": 0.3, "approved": True, "votes": {"1": 1}},
]

EXPECTED_LEG = [
    {
        "type": "cabinet",
        "path": "legislative act",
        "approved": True,
        "votes": {"1": 1},
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
        "approved": True,
        "votes": {"2": 1},
    },
    {"type": "court", "vbar": 0.3, "approved": True, "votes": {"2": 1}},
]

EXPECTED_LEG_LEG = [
    {
        "type": "cabinet",
        "path": "legislative act",
        "approved": True,
        "votes": {"2": 1},
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
        "approved": True,
        "votes": {"2": 1},
    },
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
        "approved": True,
        "votes": {"2": 1},
    },
    {"type": "court", "vbar": 0.3, "approved": True, "votes": {"2": 1}},
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
    "steps, expected_results",
    TEST_CASES,
)
def test_get_simulation_with_historic_votes(admin_client, steps, expected_results):
    simulation_id = create_simulation_with_steps(admin_client, steps)
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


@pytest.mark.skip(
    reason=(
        "batch simulation from a zip upload is deprecated pending "
        "a complete rewrite of the batch builder for the new data model"
    )
)
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
    assert (
        data["label"] == "user simulation 1\nsimulation_data [2025-01-01 → 2025-12-31]"
    )
    assert "params" in data and len(data["params"]) == 3
    cabinet = data["params"][0]["cabinet"]
    assert len(cabinet["ministers"]) == len(settings.executive.ministers)
    parliament = data["params"][1]["parliament"]
    assert len(parliament["members"]) == len(settings.legislative.mps)
    court = data["params"][2]["court"]
    assert len(court["judges"]) == len(settings.judiciary.judges)


@pytest.mark.skip(
    reason=(
        "batch simulation from a zip upload is deprecated pending "
        "a complete rewrite of the batch builder for the new data model"
    )
)
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


@pytest.mark.skip(
    reason=(
        "batch simulation from a zip upload is deprecated pending "
        "a complete rewrite of the batch builder for the new data model"
    )
)
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


def _temporary_upload(content: bytes, name: str = "batch.zip") -> TemporaryUploadedFile:
    upload = TemporaryUploadedFile(name, "application/zip", len(content), "utf-8")
    upload.file.write(content)
    upload.file.seek(0)
    return upload


def _zip_bytes_of(members: dict[str, str] | None = None) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as zip_file:
        for member_name, member_content in (members or {"other.json": "{}"}).items():
            zip_file.writestr(member_name, member_content)
    return buffer.getvalue()


class TestZipUploadGuard:
    def test_zip_without_batch_json_is_rejected(self, admin_client):
        upload = SimpleUploadedFile(
            "batch.zip",
            _zip_bytes_of({"other.json": "{}"}),
            content_type="application/zip",
        )
        response = admin_client.post(
            "/api/v1/simulation/", {"file": upload}, format="multipart"
        )

        assert response.status_code == 400
        assert "Missing 'batch.json' in uploaded zip file" in response.json()["detail"]

    def test_corrupt_zip_is_rejected(self, admin_client):
        upload = SimpleUploadedFile(
            "batch.zip", b"definitely not a zip", content_type="application/zip"
        )
        response = admin_client.post(
            "/api/v1/simulation/", {"file": upload}, format="multipart"
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "uploaded zip file was invalid"

    def test_non_zip_content_type_is_rejected(self, admin_client):
        upload = SimpleUploadedFile("batch.txt", b"{}", content_type="text/plain")
        response = admin_client.post(
            "/api/v1/simulation/", {"file": upload}, format="multipart"
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Only ZIP files are supported"

    def test_upload_without_user_settings_is_forbidden(self, admin_client, admin_user):
        admin_user.user_settings.all().delete()
        response = admin_client.post("/api/v1/simulation/")

        assert response.status_code == 403
        assert response.json()["detail"] == "User settings not found"

    def test_in_memory_upload_is_rejected(self):
        upload = SimpleUploadedFile("batch.zip", _zip_bytes_of())

        response = SimulationViewSet._handle_zip_file(upload)

        assert response.status_code == 400
        assert (
            response.data["error"]
            == "File must be processed via TemporaryFileUploadHandler"
        )

    def test_temporary_zip_upload_is_parsed(self):
        batch_data = {"startDate": "2025-01-01", "endDate": "2025-02-01"}

        response = SimulationViewSet._handle_zip_file(
            _temporary_upload(_zip_bytes_of({"batch.json": json.dumps(batch_data)}))
        )

        assert response == batch_data


def test_post_with_a_party_without_positions_treats_it_as_independent(
    admin_client, admin_user
):
    country = UserSettings.objects.get(user=admin_user).countries.first()
    Party.objects.create(country=country, label="swing")

    with patch(
        "api.services._random_simulation.choice", side_effect=lambda seq: seq[-1]
    ):
        response = admin_client.post("/api/v1/simulation/")

    parliament = response.json()["params"][1]["parliament"]
    swing_mps = [mp for mp in parliament["members"] if mp["partyLabel"] == "swing"]
    court = response.json()["params"][2]["court"]

    assert swing_mps and all(mp["partyPosition"] == "independent" for mp in swing_mps)
    assert all(judge["partyLabel"] == "swing" for judge in court["judges"])
    assert all(judge["partyPosition"] == "independent" for judge in court["judges"])


def test_simulation_with_a_batch_reports_label_and_max_step_count(
    admin_client, admin_user
):
    random_response = admin_client.post("/api/v1/simulation/")
    simulation = Simulation.objects.get(pk=random_response.json()["id"])
    batch_model = AggrandisementBatchModel.objects.create(
        file_name="batch.zip",
        simulation=simulation,
        start_date=datetime(2025, 1, 1),
        end_date=datetime(2025, 12, 31),
    )
    AggrandisementUnit.objects.create(batch=batch_model, step_no=7)

    listed = admin_client.get("/api/v1/simulation/")
    detailed = admin_client.get(f"/api/v1/simulation/{simulation.id}/")

    label = next(s["label"] for s in listed.json() if s["id"] == simulation.id)
    assert (
        label == f"user simulation {simulation.id}\nbatch.zip [2025-01-01 → 2025-12-31]"
    )
    assert detailed.json()["maxStepCount"] == 7


def test_simulation_with_a_nameless_batch_labelled_by_batch(admin_client):
    random_response = admin_client.post("/api/v1/simulation/")
    simulation = Simulation.objects.get(pk=random_response.json()["id"])
    AggrandisementBatchModel.objects.create(
        simulation=simulation,
        start_date=datetime(2025, 1, 1),
        end_date=datetime(2025, 12, 31),
    )

    listed = admin_client.get("/api/v1/simulation/").json()
    label = next(s["label"] for s in listed if s["id"] == simulation.id)

    assert label.startswith(f"user simulation {simulation.id}\nbatch [id=")
