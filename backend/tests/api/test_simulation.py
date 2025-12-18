import json

import pytest

from common.models import UserSettings


@pytest.mark.django_db
def test_post_success(admin_client, django_user_model):
    admin = django_user_model.objects.first()
    admin_settings = UserSettings.objects.get(user=admin)
    response = admin_client.post("/api/v1/simulation/")

    assert response.status_code == 201
    data = response.json()
    assert data["createdAt"] is not None
    assert data["currentStep"] == 0
    assert data["id"] is not None
    assert "params" in data and len(data["params"]) > 0
    first_param = data["params"][0]
    assert first_param["type"] == "cabinet"
    assert first_param["cabinet"] is not None
    cabinet_settings = first_param["cabinet"]
    assert cabinet_settings["id"] is not None
    assert cabinet_settings["label"] == f"admin-simulation-{cabinet_settings["id"]:06}"
    assert cabinet_settings["ministers"] is not None
    ministers = cabinet_settings["ministers"]
    assert len(ministers) == admin_settings.government_size
    assert len([m for m in ministers if m["isPrimeMinister"]]) == 1
    pm = next(m for m in ministers if m["isPrimeMinister"])
    assert len(pm["neighboursOut"]) == admin_settings.government_size - 1
    assert pm["influence"] == 1.0
    minister_dict = {m["id"]: m for m in ministers}
    for m in ministers:
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


@pytest.mark.django_db
def test_post_anonymous_forbidden(client):
    response = client.get("/api/v1/simulation/")

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Authentication credentials were not provided."
    }


@pytest.mark.django_db
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


@pytest.mark.django_db
def test_list_anonymous_forbidden(client):
    response = client.get("/api/v1/simulation/")

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Authentication credentials were not provided."
    }


@pytest.mark.django_db
def test_patch_success(admin_client):
    admin_client.post("/api/v1/simulation/")
    response = admin_client.patch(
        "/api/v1/simulation/1/",
        data=json.dumps({"status": "complete"}),
        content_type="application/json",
    )

    assert response.status_code == 202
    assert response.json() == {"detail": "simulation 1 updated"}


@pytest.mark.django_db
def test_patch_not_found(admin_client):
    response = admin_client.patch(
        "/api/v1/simulation/1/",
        data=json.dumps({"status": "complete"}),
        content_type="application/json",
    )

    assert response.status_code == 404


@pytest.mark.django_db
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


@pytest.mark.django_db
def test_patch_bad_field(admin_client):
    admin_client.post("/api/v1/simulation/")
    response = admin_client.patch(
        "/api/v1/simulation/1/",
        data=json.dumps({"currentStep": 1}),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json() == {"currentStep": ["not allowed to update field"]}


@pytest.mark.django_db
def test_patch_anonymous_forbidden(client):
    response = client.patch("/api/v1/simulation/1/")

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Authentication credentials were not provided."
    }
