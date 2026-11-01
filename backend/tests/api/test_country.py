import pytest

from common.models import Country, InstitutionBranch, InstitutionKind, UserSettings

pytestmark = pytest.mark.django_db

COUNTRIES = "/api/v1/country/"
TESTLAND = "/api/v1/country/1/"
JSON = "application/json"
ALL_PERMISSIONS = ["add_country", "change_country", "delete_country"]
NOT_AUTHENTICATED = {"detail": "Authentication credentials were not provided."}
NOT_PERMITTED = {"detail": "You do not have permission to perform this action."}


def country_url(country: Country) -> str:
    return f"{COUNTRIES}{country.id}/"


@pytest.fixture
def unused_country(test_settings) -> Country:
    return Country.objects.create(user_settings=test_settings, name="Freedonia")


@pytest.fixture
def other_settings(test_settings) -> UserSettings:
    return UserSettings.objects.create(user=test_settings.user, label="other world")


def test_list_success(admin_client):
    response = admin_client.get(COUNTRIES)

    assert response.status_code == 200
    assert response.json() == [{"id": 1, "name": "Testland", "userSettings": 1}]


def test_get_by_id_success(admin_client):
    response = admin_client.get(TESTLAND)

    assert response.status_code == 200
    assert response.json() == {"id": 1, "name": "Testland", "userSettings": 1}


def test_head_success_without_body(admin_client):
    response = admin_client.head(TESTLAND)

    assert response.status_code == 200
    assert response.content == b""


@pytest.mark.parametrize("method", ["get", "head"])
def test_get_by_id_404(admin_client, method):
    response = getattr(admin_client, method)(f"{COUNTRIES}0/")

    assert response.status_code == 404


def test_create_success(admin_client, test_settings):
    response = admin_client.post(
        COUNTRIES,
        {"name": "Freedonia", "userSettings": test_settings.id},
        content_type=JSON,
    )

    assert response.status_code == 201
    country = Country.objects.get(pk=response.json()["id"])
    assert response.json() == {
        "id": country.id,
        "name": "Freedonia",
        "userSettings": test_settings.id,
    }


def test_create_without_data_400(admin_client):
    response = admin_client.post(COUNTRIES, {}, content_type=JSON)

    assert response.status_code == 400
    assert response.json() == {
        "name": ["This field is required."],
        "user_settings": ["This field is required."],
    }


def test_update_success(admin_client, test_settings):
    response = admin_client.put(
        TESTLAND,
        {"name": "Testland 2", "userSettings": test_settings.id},
        content_type=JSON,
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": 1,
        "name": "Testland 2",
        "userSettings": test_settings.id,
    }
    assert Country.objects.get(pk=1).name == "Testland 2"


def test_delete_success(admin_client, unused_country):
    response = admin_client.delete(country_url(unused_country))

    assert response.status_code == 204
    assert response.content == b""
    assert not Country.objects.filter(pk=unused_country.pk).exists()


def test_patch_not_allowed(admin_client):
    response = admin_client.patch(TESTLAND, {"name": "x"}, content_type=JSON)

    assert response.status_code == 405


@pytest.mark.parametrize(
    "method, url",
    [
        ("get", COUNTRIES),
        ("post", COUNTRIES),
        ("get", TESTLAND),
        ("head", TESTLAND),
        ("put", TESTLAND),
        ("delete", TESTLAND),
    ],
)
def test_anonymous_forbidden(client, method, url):
    response = getattr(client, method)(url)

    assert response.status_code == 403


def test_list_anonymous_forbidden_message(client):
    response = client.get(COUNTRIES)

    assert response.json() == NOT_AUTHENTICATED


def test_list_without_permissions_shows_own_countries(user_client, userland):
    response = user_client.get(COUNTRIES)

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": userland.id,
            "name": "Userland",
            "userSettings": userland.user_settings_id,
        }
    ]


@pytest.mark.parametrize("method", ["get", "head"])
def test_get_by_id_without_permissions_success(user_client, userland, method):
    response = getattr(user_client, method)(country_url(userland))

    assert response.status_code == 200


def test_create_without_permissions_forbidden(user_client, test_user_settings):
    response = user_client.post(
        COUNTRIES,
        {"name": "Mine", "userSettings": test_user_settings.id},
        content_type=JSON,
    )

    assert response.status_code == 403
    assert response.json() == NOT_PERMITTED


def test_update_without_permissions_forbidden(user_client, userland):
    response = user_client.put(
        country_url(userland),
        {"name": "Renamed", "userSettings": userland.user_settings_id},
        content_type=JSON,
    )

    assert response.status_code == 403
    assert response.json() == NOT_PERMITTED


def test_delete_without_permissions_forbidden(user_client, userland):
    response = user_client.delete(country_url(userland))

    assert response.status_code == 403
    assert response.json() == NOT_PERMITTED
    assert Country.objects.filter(pk=userland.pk).exists()


@pytest.mark.parametrize("user_client", [["add_country"]], indirect=True)
def test_create_with_add_permission_success(user_client, test_user_settings):
    response = user_client.post(
        COUNTRIES,
        {"name": "Mine", "userSettings": test_user_settings.id},
        content_type=JSON,
    )

    assert response.status_code == 201


@pytest.mark.parametrize("user_client", [["add_country"]], indirect=True)
def test_delete_with_only_add_permission_forbidden(user_client, userland):
    response = user_client.delete(country_url(userland))

    assert response.status_code == 403


@pytest.mark.parametrize("user_client", [["change_country"]], indirect=True)
def test_update_with_change_permission_success(user_client, userland):
    response = user_client.put(
        country_url(userland),
        {"name": "Renamed", "userSettings": userland.user_settings_id},
        content_type=JSON,
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Renamed"


@pytest.mark.parametrize("user_client", [["delete_country"]], indirect=True)
def test_delete_with_delete_permission_success(user_client, userland):
    response = user_client.delete(country_url(userland))

    assert response.status_code == 204


@pytest.mark.parametrize("user_client", [ALL_PERMISSIONS], indirect=True)
@pytest.mark.parametrize("method", ["get", "head", "put", "delete"])
def test_other_users_country_404(user_client, method):
    response = getattr(user_client, method)(TESTLAND)

    assert response.status_code == 404
    assert Country.objects.get(pk=1).name == "Testland"


def test_superuser_lists_countries_of_all_users(admin_client, userland):
    response = admin_client.get(COUNTRIES)

    assert response.status_code == 200
    assert response.json() == [
        {"id": 1, "name": "Testland", "userSettings": 1},
        {
            "id": userland.id,
            "name": "Userland",
            "userSettings": userland.user_settings_id,
        },
    ]


@pytest.mark.parametrize("method", ["get", "head"])
def test_superuser_gets_other_users_country(admin_client, userland, method):
    response = getattr(admin_client, method)(country_url(userland))

    assert response.status_code == 200


def test_superuser_creates_in_other_users_settings(admin_client, test_user_settings):
    response = admin_client.post(
        COUNTRIES,
        {"name": "Elsewhere", "userSettings": test_user_settings.id},
        content_type=JSON,
    )

    assert response.status_code == 201
    country = Country.objects.get(name="Elsewhere")
    assert country.user_settings_id == test_user_settings.id


def test_superuser_updates_other_users_country(admin_client, userland):
    response = admin_client.put(
        country_url(userland),
        {"name": "Renamed", "userSettings": userland.user_settings_id},
        content_type=JSON,
    )

    assert response.status_code == 200
    assert Country.objects.get(pk=userland.pk).name == "Renamed"


def test_superuser_deletes_other_users_country(admin_client, userland):
    response = admin_client.delete(country_url(userland))

    assert response.status_code == 204
    assert not Country.objects.filter(pk=userland.pk).exists()


def test_superuser_cannot_move_country_to_other_users_settings(admin_client, userland):
    response = admin_client.put(
        TESTLAND,
        {"name": "Testland", "userSettings": userland.user_settings_id},
        content_type=JSON,
    )

    assert response.status_code == 400
    assert response.json() == {
        "user_settings": ["A country cannot be moved to other settings."]
    }


def test_delete_simulated_country_409(admin_client, legislative_log_simulation):
    country = legislative_log_simulation.country

    response = admin_client.delete(country_url(country))

    assert response.status_code == 409
    assert response.json() == {
        "detail": "The country has simulations and cannot be deleted."
    }
    assert Country.objects.filter(pk=country.pk).exists()


def test_delete_deletes_institution_kinds(admin_client, unused_country):
    kind = InstitutionKind.objects.create(
        country=unused_country,
        branch=InstitutionBranch.EXECUTIVE,
        institution_name="cabinet",
    )

    response = admin_client.delete(country_url(unused_country))

    assert response.status_code == 204
    assert not InstitutionKind.objects.filter(pk=kind.pk).exists()


def test_create_duplicate_name_400(admin_client, test_settings):
    response = admin_client.post(
        COUNTRIES,
        {"name": "Testland", "userSettings": test_settings.id},
        content_type=JSON,
    )

    assert response.status_code == 400
    assert response.json() == {
        "non_field_errors": [
            "A country with this name already exists in these settings."
        ]
    }


def test_create_same_name_in_other_settings_success(admin_client, other_settings):
    response = admin_client.post(
        COUNTRIES,
        {"name": "Testland", "userSettings": other_settings.id},
        content_type=JSON,
    )

    assert response.status_code == 201


@pytest.mark.parametrize("user_client", [["add_country"]], indirect=True)
def test_create_in_other_users_settings_400(user_client, test_settings):
    response = user_client.post(
        COUNTRIES,
        {"name": "Elsewhere", "userSettings": test_settings.id},
        content_type=JSON,
    )

    assert response.status_code == 400
    assert response.json() == {
        "user_settings": [f'Invalid pk "{test_settings.id}" - object does not exist.']
    }
    assert not Country.objects.filter(name="Elsewhere").exists()


def test_update_move_to_other_settings_400(admin_client, other_settings):
    response = admin_client.put(
        TESTLAND,
        {"name": "Testland", "userSettings": other_settings.id},
        content_type=JSON,
    )

    assert response.status_code == 400
    assert response.json() == {
        "user_settings": ["A country cannot be moved to other settings."]
    }
    assert Country.objects.get(pk=1).user_settings_id == 1
