from datetime import UTC, datetime

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.exceptions import NotAuthenticated, PermissionDenied

from common.models import (
    Institution,
    Party,
    PartyPosition,
    PartyPositionType,
    Simulation,
    TimeFrame,
)

pytestmark = pytest.mark.django_db


def list_url() -> str:
    return reverse("party-list")


def detail_url(pk: int) -> str:
    return reverse("party-detail", args=[pk])


def post(client, data):
    return client.post(list_url(), data, content_type="application/json")


def put(client, pk: int, data):
    return client.put(detail_url(pk), data, content_type="application/json")


def at(year: int) -> datetime:
    """The start of `year`, as stored in a time frame."""
    return datetime(year, 1, 1, tzinfo=UTC)


def party_json(
    pk: int,
    country: int,
    label: str,
    latest: str | None = None,
    active: str | None = None,
) -> dict:
    """A party as returned by the API."""
    return {
        "id": pk,
        "country": country,
        "label": label,
        "latestPosition": latest,
        "activePosition": active,
    }


def framed_position(
    party: Party,
    position: PartyPositionType,
    chamber: Institution,
    valid_from: datetime | None = None,
    valid_to: datetime | None = None,
) -> PartyPosition:
    """A validated position with a single time frame, on all timelines."""
    party_position = PartyPosition(party=party, chamber=chamber, position=position)
    party_position.full_clean()
    party_position.save()
    TimeFrame.objects.occupy(party_position, valid_from, valid_to)
    return party_position


@pytest.fixture
def majority_party() -> Party:
    """The Testland party labelled 'majority', frameless in the parliament."""
    return Party.objects.get(pk=1)


@pytest.fixture
def parliament() -> Institution:
    """Testland's chamber, holding the frameless positions of its parties."""
    return Institution.objects.get(pk=2)


@pytest.fixture
def psd() -> Party:
    """A Testland party without positions."""
    return Party.objects.create(country_id=1, label="PSD")


@pytest.fixture
def user_party(userland) -> Party:
    return Party.objects.create(country=userland, label="Userland party")


# AC2: list, get and head


def test_list_success(admin_client):
    response = admin_client.get(list_url())

    assert response.status_code == 200
    assert response.json() == [
        party_json(1, 1, "majority", latest="majority", active="majority"),
        party_json(2, 1, "opposition", latest="opposition", active="opposition"),
    ]


def test_get_by_id_success(admin_client, majority_party):
    response = admin_client.get(detail_url(majority_party.id))

    assert response.status_code == 200
    assert response.json() == party_json(
        1, 1, "majority", latest="majority", active="majority"
    )


def test_get_party_without_positions(admin_client, psd):
    response = admin_client.get(detail_url(psd.id))

    assert response.status_code == 200
    assert response.json() == party_json(psd.id, 1, "PSD")


def test_get_shows_the_active_and_the_planned_position(admin_client, psd, parliament):
    framed_position(psd, PartyPositionType.MAJORITY, parliament, at(2020), at(2099))
    framed_position(psd, PartyPositionType.OPPOSITION, parliament, at(2099))

    response = admin_client.get(detail_url(psd.id))

    assert response.json() == party_json(
        psd.id, 1, "PSD", latest="opposition", active="majority"
    )


def test_get_shows_no_active_position_once_all_have_ended(
    admin_client, psd, parliament
):
    framed_position(psd, PartyPositionType.MAJORITY, parliament, at(2016), at(2020))

    response = admin_client.get(detail_url(psd.id))

    assert response.json() == party_json(psd.id, 1, "PSD", latest="majority")


def test_list_shows_the_positions_of_each_party(admin_client, psd, parliament):
    framed_position(psd, PartyPositionType.OPPOSITION, parliament, at(2099))

    response = admin_client.get(list_url())

    assert response.json()[2] == party_json(psd.id, 1, "PSD", latest="opposition")


def test_list_queries_are_flat_and_do_not_grow_with_the_parties(
    admin_client, parliament
):
    with CaptureQueriesContext(connection) as two_parties:
        admin_client.get(list_url())
    for i in range(4):
        party = Party.objects.create(country_id=1, label=f"party {i}")
        framed_position(party, PartyPositionType.MAJORITY, parliament, at(2099))

    with CaptureQueriesContext(connection) as six_parties:
        response = admin_client.get(list_url())

    assert len(response.json()) == 6
    assert len(six_parties) == len(two_parties)
    for query in six_parties.captured_queries:
        assert query["sql"].count("SELECT") == 1, query["sql"]


def test_head_success_without_body(admin_client, majority_party):
    response = admin_client.head(detail_url(majority_party.id))

    assert response.status_code == 200
    assert response.content == b""


@pytest.mark.parametrize("method", ["get", "head", "put", "delete"])
def test_missing_party_404(admin_client, method):
    response = getattr(admin_client, method)(detail_url(0))

    assert response.status_code == 404


# AC3: create, update and delete


def test_create_success(admin_client):
    response = post(admin_client, {"country": 1, "label": "PNL"})

    assert response.status_code == 201
    party = Party.objects.get(label="PNL")
    assert party.country_id == 1
    assert response.json() == party_json(party.id, 1, "PNL")


def test_create_without_data_400(admin_client):
    response = post(admin_client, {})

    assert response.status_code == 400
    assert response.json() == {
        "country": ["This field is required."],
        "label": ["This field is required."],
    }


def test_create_duplicate_label_400(admin_client, majority_party):
    response = post(admin_client, {"country": 1, "label": "majority"})

    assert response.status_code == 400
    assert response.json() == {
        "non_field_errors": ["A party with this label already exists in this country."]
    }
    assert Party.objects.filter(label="majority").count() == 1


def test_create_same_label_in_other_country_success(admin_client, userland):
    response = post(admin_client, {"country": userland.id, "label": "majority"})

    assert response.status_code == 201
    assert Party.objects.filter(label="majority").count() == 2


def test_create_batch_400(admin_client):
    response = post(admin_client, [{"country": 1, "label": "PNL"}])

    assert response.status_code == 400
    assert response.json() == {
        "non_field_errors": ["Invalid data. Expected a dictionary, but got list."]
    }
    assert not Party.objects.filter(label="PNL").exists()


def test_update_label_success(admin_client, majority_party):
    response = put(admin_client, majority_party.id, {"country": 1, "label": "PSD"})

    assert response.status_code == 200
    assert response.json() == party_json(
        1, 1, "PSD", latest="majority", active="majority"
    )
    majority_party.refresh_from_db()
    assert majority_party.label == "PSD"


def test_update_with_the_same_label_success(admin_client, majority_party):
    response = put(admin_client, majority_party.id, {"country": 1, "label": "majority"})

    assert response.status_code == 200


def test_update_without_data_400(admin_client, majority_party):
    response = put(admin_client, majority_party.id, {})

    assert response.status_code == 400
    assert response.json() == {
        "country": ["This field is required."],
        "label": ["This field is required."],
    }


def test_update_move_to_other_country_400(admin_client, majority_party, userland):
    response = put(
        admin_client, majority_party.id, {"country": userland.id, "label": "majority"}
    )

    assert response.status_code == 400
    assert response.json() == {
        "country": ["A party cannot be moved to another country."]
    }
    majority_party.refresh_from_db()
    assert majority_party.country_id == 1


def test_update_to_duplicate_label_400(admin_client, majority_party):
    response = put(
        admin_client, majority_party.id, {"country": 1, "label": "opposition"}
    )

    assert response.status_code == 400
    assert response.json() == {
        "non_field_errors": ["A party with this label already exists in this country."]
    }
    majority_party.refresh_from_db()
    assert majority_party.label == "majority"


def test_patch_not_allowed(admin_client, majority_party):
    response = admin_client.patch(
        detail_url(majority_party.id),
        {"label": "PSD"},
        content_type="application/json",
    )

    assert response.status_code == 405


def test_delete_deletes_positions_and_time_frames(admin_client, psd, parliament):
    position = framed_position(psd, PartyPositionType.MAJORITY, parliament, at(2020))

    response = admin_client.delete(detail_url(psd.id))

    assert response.status_code == 204
    assert response.content == b""
    assert not Party.objects.filter(pk=psd.pk).exists()
    assert not PartyPosition.objects.filter(pk=position.pk).exists()
    assert not TimeFrame.objects.of(position).exists()


@pytest.mark.parametrize(
    "simulation, agents",
    [
        ("judiciary_log_simulation", "ministers"),
        ("legislative_log_simulation", "mps"),
        ("judiciary_log_simulation", "judges"),
    ],
)
@pytest.mark.parametrize("status", Simulation.Status.values)
def test_delete_party_with_agents_in_simulations_409(
    request, admin_client, majority_party, simulation, agents, status
):
    simulation = request.getfixturevalue(simulation)
    Simulation.objects.filter(pk=simulation.pk).update(status=status)
    for other in {"ministers", "mps", "judges"} - {agents}:
        getattr(majority_party, other).all().delete()
    assert getattr(majority_party, agents).exists()

    response = admin_client.delete(detail_url(majority_party.id))

    assert response.status_code == 409
    assert response.json() == {
        "detail": "The party has agents in simulations and cannot be deleted."
    }
    assert Party.objects.filter(pk=majority_party.pk).exists()
    assert majority_party.positions.exists()


# AC4: authentication and permissions


@pytest.mark.parametrize(
    "method, on_detail",
    [
        ("get", False),
        ("post", False),
        ("get", True),
        ("head", True),
        ("put", True),
        ("delete", True),
    ],
)
def test_anonymous_forbidden(client, majority_party, method, on_detail):
    url = detail_url(majority_party.id) if on_detail else list_url()

    response = getattr(client, method)(url)

    assert response.status_code == 403
    assert Party.objects.filter(pk=majority_party.pk).exists()


def test_list_anonymous_forbidden_message(client):
    response = client.get(list_url())

    assert response.json() == {"detail": str(NotAuthenticated.default_detail)}


def test_list_without_permissions_shows_own_parties(user_client, user_party):
    response = user_client.get(list_url())

    assert response.status_code == 200
    assert response.json() == [
        party_json(user_party.id, user_party.country_id, "Userland party")
    ]


@pytest.mark.parametrize("method", ["get", "head"])
def test_get_by_id_without_permissions_success(user_client, user_party, method):
    response = getattr(user_client, method)(detail_url(user_party.id))

    assert response.status_code == 200


def test_create_without_permissions_forbidden(user_client, userland):
    response = post(user_client, {"country": userland.id, "label": "PNL"})

    assert response.status_code == 403
    assert response.json() == {"detail": str(PermissionDenied.default_detail)}
    assert not Party.objects.filter(label="PNL").exists()


def test_update_without_permissions_forbidden(user_client, user_party):
    response = put(
        user_client, user_party.id, {"country": user_party.country_id, "label": "PNL"}
    )

    assert response.status_code == 403
    assert response.json() == {"detail": str(PermissionDenied.default_detail)}
    user_party.refresh_from_db()
    assert user_party.label == "Userland party"


def test_delete_without_permissions_forbidden(user_client, user_party):
    response = user_client.delete(detail_url(user_party.id))

    assert response.status_code == 403
    assert response.json() == {"detail": str(PermissionDenied.default_detail)}
    assert Party.objects.filter(pk=user_party.pk).exists()


@pytest.mark.parametrize("user_client", [["add_party"]], indirect=True)
def test_create_with_add_permission_success(user_client, userland):
    response = post(user_client, {"country": userland.id, "label": "PNL"})

    assert response.status_code == 201
    assert userland.parties.get().label == "PNL"


@pytest.mark.parametrize("user_client", [["add_party"]], indirect=True)
def test_create_in_other_users_country_400(user_client):
    response = post(user_client, {"country": 1, "label": "PNL"})

    assert response.status_code == 400
    assert response.json() == {"country": ['Invalid pk "1" - object does not exist.']}
    assert not Party.objects.filter(label="PNL").exists()


@pytest.mark.parametrize("user_client", [["add_party"]], indirect=True)
def test_delete_with_only_add_permission_forbidden(user_client, user_party):
    response = user_client.delete(detail_url(user_party.id))

    assert response.status_code == 403
    assert Party.objects.filter(pk=user_party.pk).exists()


@pytest.mark.parametrize("user_client", [["change_party"]], indirect=True)
def test_update_with_change_permission_success(user_client, user_party):
    response = put(
        user_client, user_party.id, {"country": user_party.country_id, "label": "PNL"}
    )

    assert response.status_code == 200
    assert response.json()["label"] == "PNL"


@pytest.mark.parametrize("user_client", [["delete_party"]], indirect=True)
def test_delete_with_delete_permission_success(user_client, user_party):
    response = user_client.delete(detail_url(user_party.id))

    assert response.status_code == 204
    assert not Party.objects.filter(pk=user_party.pk).exists()


@pytest.mark.parametrize(
    "user_client", [["add_party", "change_party", "delete_party"]], indirect=True
)
@pytest.mark.parametrize("method", ["get", "head", "delete"])
def test_other_users_party_404(user_client, majority_party, method):
    response = getattr(user_client, method)(detail_url(majority_party.id))

    assert response.status_code == 404
    assert Party.objects.filter(pk=majority_party.pk).exists()


@pytest.mark.parametrize("user_client", [["change_party"]], indirect=True)
def test_update_other_users_party_404(user_client, majority_party, userland):
    # whatever the body names as country, the party itself is out of reach
    for country in (1, userland.id):
        response = put(
            user_client, majority_party.id, {"country": country, "label": "PSD"}
        )

        assert response.status_code == 404
    majority_party.refresh_from_db()
    assert majority_party.label == "majority"


def test_superuser_lists_parties_of_all_users(admin_client, user_party):
    response = admin_client.get(list_url())

    assert response.status_code == 200
    assert [p["id"] for p in response.json()] == [1, 2, user_party.id]


@pytest.mark.parametrize("method", ["get", "head"])
def test_superuser_gets_other_users_party(admin_client, user_party, method):
    response = getattr(admin_client, method)(detail_url(user_party.id))

    assert response.status_code == 200


def test_superuser_creates_in_other_users_country(admin_client, userland):
    response = post(admin_client, {"country": userland.id, "label": "PNL"})

    assert response.status_code == 201
    assert userland.parties.get().label == "PNL"


def test_superuser_updates_other_users_party(admin_client, user_party):
    response = put(
        admin_client, user_party.id, {"country": user_party.country_id, "label": "PNL"}
    )

    assert response.status_code == 200
    user_party.refresh_from_db()
    assert user_party.label == "PNL"


def test_superuser_deletes_other_users_party(admin_client, user_party):
    response = admin_client.delete(detail_url(user_party.id))

    assert response.status_code == 204
    assert not Party.objects.filter(pk=user_party.pk).exists()
