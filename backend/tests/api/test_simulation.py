import pytest

from api.views import _SAMPLE_USER_SETTINGS


@pytest.fixture
def expected_simulation_json():
    return {
        "id": 1,
        "step": 0,
        "status": "new",
        "createdAt": "2025-12-15T21:41:00.000123Z",
        "updatedAt": "2025-12-15T21:41:00.000124Z",
        "globalParameters": _SAMPLE_USER_SETTINGS,
    }


def test_post_success(admin_client, expected_simulation_json):
    response = admin_client.post("/api/v1/simulation/")

    assert response.status_code == 201
    assert response.json() == expected_simulation_json


def test_post_anonymous_forbidden(client):
    response = client.get("/api/v1/simulation/")

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Authentication credentials were not provided."
    }


def test_list_success(admin_client, expected_simulation_json):
    response = admin_client.get("/api/v1/simulation/")

    assert response.status_code == 200
    assert response.json() == [expected_simulation_json]


def test_list_anonymous_forbidden(client):
    response = client.get("/api/v1/simulation/")

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Authentication credentials were not provided."
    }


def test_patch_success(admin_client):
    response = admin_client.patch("/api/v1/simulation/1/")

    assert response.status_code == 202
    assert response.json() == {"detail": "simulation 1 updated"}


def test_patch_anonymous_forbidden(client):
    response = client.patch("/api/v1/simulation/1/")

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Authentication credentials were not provided."
    }
