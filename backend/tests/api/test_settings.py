from types import SimpleNamespace

import pytest

from api.serializers import UserSettingsSerializer
from common.models import Country, Party, UserSettings


def test_list_success(admin_client):
    response = admin_client.get("/api/v1/settings/")

    assert response.status_code == 200
    assert response.json() == [{"id": 1, "label": "test_admin settings"}]


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
        "parties": [
            {"id": 1, "label": "majority", "position": "majority"},
            {"id": 2, "label": "opposition", "position": "opposition"},
        ],
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


@pytest.mark.django_db
def test_parties_is_empty_without_countries(test_user):
    user_settings = UserSettings.objects.create(user=test_user, label="no-country")

    data = UserSettingsSerializer(user_settings).data

    assert data["parties"] == []


@pytest.mark.django_db
def test_parties_map_to_the_default_country(test_user):
    user_settings = UserSettings.objects.create(user=test_user, label="parties")
    country = Country.objects.create(user_settings=user_settings, name="Testland")
    party = Party.objects.create(country=country, label="majority")
    other_country = Country.objects.create(
        user_settings=user_settings, name="Otherland"
    )
    Party.objects.create(country=other_country, label="other")

    data = UserSettingsSerializer(user_settings).data

    assert data["parties"] == [{"id": party.id, "label": "majority", "position": None}]
