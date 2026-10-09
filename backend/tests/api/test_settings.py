from types import SimpleNamespace

import pytest

from api.serializers import UserSettingsSerializer


def test_list_success(admin_client):
    response = admin_client.get("/api/v1/settings/")

    assert response.status_code == 200
    assert response.json() == [
        {
            "courtProbabilityFor": 0.5,
            "governmentProbabilityFor": 0.7,
            "id": 1,
            "label": "test_admin settings",
            "parliamentMajorityProbabilityFor": 0.5,
            "parliamentOppositionProbabilityFor": 0.5,
        }
    ]


def test_list_anonymous_forbidden(client):
    response = client.get("/api/v1/settings/")

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Authentication credentials were not provided."
    }


def test_get_by_id_success(admin_client):
    response = admin_client.get("/api/v1/settings/1/")

    assert response.status_code == 200
    assert response.json() == {
        "abstentionThreshold": 0.1,
        "courtProbabilityFor": 0.5,
        "dataUpdateFrequency": 10,
        "governmentProbabilityFor": 0.7,
        "parliamentMajorityProbabilityFor": 0.5,
        "parliamentOppositionProbabilityFor": 0.5,
        "id": 1,
        "label": "test_admin settings",
        "legislativePathProbability": 0.7,
        "officeRetentionSensitivity": 5.0,
        "socialInfluenceSusceptibility": 0.5,
        "userId": 1,
    }


def test_get_by_id_404(admin_client):
    response = admin_client.get("/api/v1/settings/0/")

    assert response.status_code == 404


def test_get_by_id_anonymous_forbidden(client):
    response = client.get("/api/v1/settings/1/")

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Authentication credentials were not provided."
    }


@pytest.mark.django_db
def test_settings_serializer_without_a_view_returns_all_fields(test_settings):
    fields = UserSettingsSerializer().get_fields()

    assert "data_update_frequency" in fields


@pytest.mark.django_db
def test_settings_serializer_for_a_non_list_view_returns_all_fields(test_settings):
    serializer = UserSettingsSerializer(instance=test_settings)
    serializer._context = {"view": SimpleNamespace(action="retrieve")}

    fields = serializer.get_fields()

    assert "data_update_frequency" in fields
