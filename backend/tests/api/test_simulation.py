import json
import math

from django.db.models import Sum

from common.models import UserSettings


def test_post_success_basic_data(admin_client, admin_user):
    response = admin_client.post("/api/v1/simulation/")

    assert response.status_code == 201
    data = response.json()
    assert data["createdAt"] is not None
    assert data["currentStep"] == 0
    assert data["id"] is not None
    assert data["officeRetentionSensitivity"] == 5.0
    assert data["socialInfluenceSusceptibility"] == 0.5
    assert "params" in data and len(data["params"]) == 2


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
