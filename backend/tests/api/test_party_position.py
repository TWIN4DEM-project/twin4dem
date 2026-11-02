from collections.abc import Iterable
from datetime import UTC, datetime

import pytest
from django.urls import reverse
from rest_framework.exceptions import NotAuthenticated, PermissionDenied

from common.models import (
    Country,
    Institution,
    InstitutionBranch,
    InstitutionKind,
    Party,
    PartyPosition,
    PartyPositionType,
    TimeFrame,
    VirtualTimeline,
    is_active,
)

pytestmark = pytest.mark.django_db


def list_url() -> str:
    return reverse("party-position-list")


def detail_url(pk: int) -> str:
    return reverse("party-position-detail", args=[pk])


def post(client, data):
    return client.post(list_url(), data, content_type="application/json")


def put(client, pk: int, data):
    return client.put(detail_url(pk), data, content_type="application/json")


def at(year: int) -> datetime:
    """The start of `year`, as stored in a time frame."""
    return datetime(year, 1, 1, tzinfo=UTC)


def dt(year: int) -> str:
    """The start of `year`, as sent to and returned by the API."""
    return at(year).isoformat().replace("+00:00", "Z")


def body(party: Party, **fields) -> dict:
    """The body of a majority position of `party`, overridden by `fields`."""
    return {"party": party.id, "position": PartyPositionType.MAJORITY, **fields}


def position_json(
    pk: int,
    party: int,
    position: str = PartyPositionType.MAJORITY,
    chamber: int | None = None,
    timeline: int | None = None,
    valid_from: str | None = None,
    valid_to: str | None = None,
) -> dict:
    """A position as returned by the API."""
    return {
        "id": pk,
        "party": party,
        "position": position,
        "chamber": chamber,
        "timeline": timeline,
        "validFrom": valid_from,
        "validTo": valid_to,
    }


def framed_position(
    party: Party,
    position: PartyPositionType = PartyPositionType.MAJORITY,
    chamber: Institution | None = None,
    valid_from: datetime | None = None,
    valid_to: datetime | None = None,
    timelines: Iterable[VirtualTimeline] = (),
) -> PartyPosition:
    """A validated position with a single time frame, as the API creates it."""
    party_position = PartyPosition(party=party, chamber=chamber, position=position)
    party_position.full_clean()
    party_position.save()
    TimeFrame.objects.occupy(party_position, valid_from, valid_to, timelines)
    return party_position


def overlap(position: str, interval: str, timelines: str = "all timelines") -> dict:
    """The error of a time frame overlapping a `position` of PSD."""
    return {
        "non_field_errors": [
            f"Overlaps with 'PSD' ({position}) {interval} on {timelines}."
        ]
    }


@pytest.fixture
def default_timeline(test_settings) -> VirtualTimeline:
    return test_settings.timelines.get(label=VirtualTimeline.DEFAULT_LABEL)


@pytest.fixture
def alternate_timeline(test_settings) -> VirtualTimeline:
    return VirtualTimeline.objects.create(
        user_settings=test_settings, label="alternate"
    )


@pytest.fixture
def government() -> Institution:
    """Testland's executive institution."""
    return Institution.objects.get(pk=1)


@pytest.fixture
def parliament() -> Institution:
    """Testland's chamber, holding the frameless positions of its parties."""
    return Institution.objects.get(pk=2)


@pytest.fixture
def majority_party() -> Party:
    """The Testland party labelled 'majority', frameless in the parliament."""
    return Party.objects.get(pk=1)


@pytest.fixture
def frameless_position() -> PartyPosition:
    """The majority position of `majority_party` in the parliament."""
    return PartyPosition.objects.get(pk=1)


@pytest.fixture
def psd() -> Party:
    """A Testland party without positions."""
    return Party.objects.create(country_id=1, label="PSD")


@pytest.fixture
def senate() -> Institution:
    """A second Testland chamber, without positions."""
    kind = InstitutionKind.objects.create(
        country_id=1, branch=InstitutionBranch.LEGISLATIVE, institution_name="senate"
    )
    return Institution.objects.create(kind=kind, label="Testland senate", size=136)


@pytest.fixture
def foreign_chamber(test_settings) -> Institution:
    """A chamber of another country in the same settings as Testland."""
    otherland = Country.objects.create(user_settings=test_settings, name="Otherland")
    kind = InstitutionKind.objects.create(
        country=otherland,
        branch=InstitutionBranch.LEGISLATIVE,
        institution_name="parliament",
    )
    return Institution.objects.create(kind=kind, label="Otherland parliament", size=50)


@pytest.fixture
def user_timeline(test_user_settings) -> VirtualTimeline:
    """The test user's default timeline: a timeline of other settings for Testland."""
    return test_user_settings.timelines.get(label=VirtualTimeline.DEFAULT_LABEL)


@pytest.fixture
def user_party(userland) -> Party:
    return Party.objects.create(country=userland, label="Userland party")


@pytest.fixture
def user_chamber(userland) -> Institution:
    kind = InstitutionKind.objects.create(
        country=userland,
        branch=InstitutionBranch.LEGISLATIVE,
        institution_name="parliament",
    )
    return Institution.objects.create(kind=kind, label="Userland parliament", size=50)


@pytest.fixture
def user_position(user_party, user_chamber) -> PartyPosition:
    return framed_position(user_party, chamber=user_chamber, valid_from=at(2020))


def test_list_success(admin_client):
    response = admin_client.get(list_url())

    assert response.status_code == 200
    assert response.json() == [
        position_json(1, party=1, chamber=2),
        position_json(2, party=2, position="opposition", chamber=2),
    ]


def test_get_by_id_success(admin_client, psd, senate, alternate_timeline):
    position = framed_position(
        psd,
        chamber=senate,
        valid_from=at(2020),
        valid_to=at(2024),
        timelines=[alternate_timeline],
    )

    response = admin_client.get(detail_url(position.id))

    assert response.status_code == 200
    assert response.json() == position_json(
        position.id,
        psd.id,
        chamber=senate.id,
        timeline=alternate_timeline.id,
        valid_from=dt(2020),
        valid_to=dt(2024),
    )


def test_get_position_with_several_frames_shows_the_first(
    admin_client, psd, default_timeline, alternate_timeline
):
    # only possible in the admin: the API gives every position a single frame
    position = framed_position(psd, valid_from=at(2020), timelines=[default_timeline])
    TimeFrame.objects.occupy(position, at(2010), at(2015), [alternate_timeline])

    response = admin_client.get(detail_url(position.id))

    assert response.status_code == 200
    assert response.json() == position_json(
        position.id, psd.id, timeline=default_timeline.id, valid_from=dt(2020)
    )


def test_head_success_without_body(admin_client, frameless_position):
    response = admin_client.head(detail_url(frameless_position.id))

    assert response.status_code == 200
    assert response.content == b""


@pytest.mark.parametrize("method", ["get", "head", "put", "delete"])
def test_missing_position_404(admin_client, method):
    response = getattr(admin_client, method)(detail_url(0))

    assert response.status_code == 404


def test_create_success(admin_client, psd, senate, alternate_timeline):
    response = post(
        admin_client,
        body(
            psd,
            chamber=senate.id,
            timeline=alternate_timeline.id,
            validFrom=dt(2020),
            validTo=dt(2024),
        ),
    )

    assert response.status_code == 201
    position = psd.positions.get()
    assert response.json() == position_json(
        position.id,
        psd.id,
        chamber=senate.id,
        timeline=alternate_timeline.id,
        valid_from=dt(2020),
        valid_to=dt(2024),
    )


def test_create_without_data_400(admin_client):
    response = post(admin_client, {})

    assert response.status_code == 400
    assert response.json() == {
        "party": ["This field is required."],
        "position": ["This field is required."],
    }


def test_create_unknown_position_400(admin_client, psd):
    response = post(admin_client, body(psd, position="leader"))

    assert response.status_code == 400
    assert response.json() == {"position": ['"leader" is not a valid choice.']}
    assert not psd.positions.exists()


def test_create_batch_success(admin_client, psd, senate):
    response = post(
        admin_client,
        [
            body(psd, validFrom=dt(2020)),
            body(psd, position="opposition", chamber=senate.id),
        ],
    )

    assert response.status_code == 201
    default, in_senate = psd.positions.order_by("id")
    assert response.json() == [
        position_json(default.id, psd.id, valid_from=dt(2020)),
        position_json(in_senate.id, psd.id, position="opposition", chamber=senate.id),
    ]


def test_update_success(admin_client, psd):
    position = framed_position(psd, valid_from=at(2020))

    response = put(
        admin_client, position.id, body(psd, position="opposition", validTo=dt(2030))
    )

    assert response.status_code == 200
    assert response.json() == position_json(
        position.id, psd.id, position="opposition", valid_to=dt(2030)
    )
    position.refresh_from_db()
    assert position.position == PartyPositionType.OPPOSITION
    assert TimeFrame.objects.of(position).get().valid_to == at(2030)


def test_update_without_data_400(admin_client, frameless_position):
    response = put(admin_client, frameless_position.id, {})

    assert response.status_code == 400
    assert response.json() == {
        "party": ["This field is required."],
        "position": ["This field is required."],
    }


def test_update_with_array_400(admin_client, majority_party, frameless_position):
    response = put(
        admin_client,
        frameless_position.id,
        [body(majority_party, position="opposition")],
    )

    assert response.status_code == 400
    assert response.json() == {
        "non_field_errors": ["Invalid data. Expected a dictionary, but got list."]
    }
    frameless_position.refresh_from_db()
    assert frameless_position.position == PartyPositionType.MAJORITY


def test_delete_success(admin_client, psd):
    position = framed_position(psd, valid_from=at(2020))

    response = admin_client.delete(detail_url(position.id))

    assert response.status_code == 204
    assert response.content == b""
    assert not PartyPosition.objects.filter(pk=position.pk).exists()
    assert not TimeFrame.objects.of(position).exists()


def test_patch_not_allowed(admin_client, frameless_position):
    response = admin_client.patch(
        detail_url(frameless_position.id),
        {"position": "opposition"},
        content_type="application/json",
    )

    assert response.status_code == 405


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
def test_anonymous_forbidden(client, frameless_position, method, on_detail):
    url = detail_url(frameless_position.id) if on_detail else list_url()

    response = getattr(client, method)(url)

    assert response.status_code == 403
    assert PartyPosition.objects.filter(pk=frameless_position.pk).exists()


def test_list_anonymous_forbidden_message(client):
    response = client.get(list_url())

    assert response.json() == {"detail": str(NotAuthenticated.default_detail)}


def test_list_without_permissions_shows_own_positions(user_client, user_position):
    response = user_client.get(list_url())

    assert response.status_code == 200
    assert response.json() == [
        position_json(
            user_position.id,
            user_position.party_id,
            chamber=user_position.chamber_id,
            valid_from=dt(2020),
        )
    ]


@pytest.mark.parametrize("method", ["get", "head"])
def test_get_by_id_without_permissions_success(user_client, user_position, method):
    response = getattr(user_client, method)(detail_url(user_position.id))

    assert response.status_code == 200


def test_create_without_permissions_forbidden(user_client, user_party):
    response = post(user_client, body(user_party))

    assert response.status_code == 403
    assert response.json() == {"detail": str(PermissionDenied.default_detail)}
    assert not user_party.positions.exists()


def test_update_without_permissions_forbidden(user_client, user_position):
    response = put(
        user_client,
        user_position.id,
        body(user_position.party, position="opposition"),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": str(PermissionDenied.default_detail)}
    user_position.refresh_from_db()
    assert user_position.position == PartyPositionType.MAJORITY


def test_delete_without_permissions_forbidden(user_client, user_position):
    response = user_client.delete(detail_url(user_position.id))

    assert response.status_code == 403
    assert response.json() == {"detail": str(PermissionDenied.default_detail)}
    assert PartyPosition.objects.filter(pk=user_position.pk).exists()


@pytest.mark.parametrize("user_client", [["add_partyposition"]], indirect=True)
def test_create_with_add_permission_success(
    user_client, user_party, user_chamber, user_timeline
):
    response = post(
        user_client,
        body(user_party, chamber=user_chamber.id, timeline=user_timeline.id),
    )

    assert response.status_code == 201
    assert user_party.positions.get().chamber == user_chamber


@pytest.mark.parametrize("user_client", [["add_partyposition"]], indirect=True)
def test_create_batch_with_add_permission_success(
    user_client, user_party, user_chamber
):
    response = post(
        user_client, [body(user_party), body(user_party, chamber=user_chamber.id)]
    )

    assert response.status_code == 201
    assert user_party.positions.count() == 2


@pytest.mark.parametrize("user_client", [["add_partyposition"]], indirect=True)
def test_delete_with_only_add_permission_forbidden(user_client, user_position):
    response = user_client.delete(detail_url(user_position.id))

    assert response.status_code == 403
    assert PartyPosition.objects.filter(pk=user_position.pk).exists()


@pytest.mark.parametrize("user_client", [["change_partyposition"]], indirect=True)
def test_update_with_change_permission_success(user_client, user_position):
    response = put(
        user_client,
        user_position.id,
        body(
            user_position.party,
            position="opposition",
            chamber=user_position.chamber_id,
            validFrom=dt(2020),
        ),
    )

    assert response.status_code == 200
    assert response.json()["position"] == "opposition"


@pytest.mark.parametrize("user_client", [["delete_partyposition"]], indirect=True)
def test_delete_with_delete_permission_success(user_client, user_position):
    response = user_client.delete(detail_url(user_position.id))

    assert response.status_code == 204
    assert not PartyPosition.objects.filter(pk=user_position.pk).exists()


@pytest.mark.parametrize(
    "user_client",
    [["add_partyposition", "change_partyposition", "delete_partyposition"]],
    indirect=True,
)
@pytest.mark.parametrize("method", ["get", "head", "put", "delete"])
def test_other_users_position_404(user_client, frameless_position, method):
    response = getattr(user_client, method)(detail_url(frameless_position.id))

    assert response.status_code == 404
    frameless_position.refresh_from_db()
    assert frameless_position.position == PartyPositionType.MAJORITY


@pytest.mark.parametrize("user_client", [["add_partyposition"]], indirect=True)
def test_create_for_other_users_party_400(user_client, majority_party):
    response = post(user_client, body(majority_party))

    assert response.status_code == 400
    assert response.json() == {
        "party": [f'Invalid pk "{majority_party.id}" - object does not exist.']
    }


@pytest.mark.parametrize("user_client", [["add_partyposition"]], indirect=True)
def test_create_in_other_users_chamber_400(user_client, user_party, parliament):
    response = post(user_client, body(user_party, chamber=parliament.id))

    assert response.status_code == 400
    assert response.json() == {
        "chamber": [f'Invalid pk "{parliament.id}" - object does not exist.']
    }
    assert not user_party.positions.exists()


@pytest.mark.parametrize("user_client", [["add_partyposition"]], indirect=True)
def test_create_on_other_users_timeline_400(user_client, user_party, default_timeline):
    response = post(user_client, body(user_party, timeline=default_timeline.id))

    assert response.status_code == 400
    assert response.json() == {
        "timeline": [f'Invalid pk "{default_timeline.id}" - object does not exist.']
    }
    assert not user_party.positions.exists()


def test_list_filtered_by_other_users_party_empty(user_client, majority_party):
    response = user_client.get(list_url(), {"party": majority_party.id})

    assert response.status_code == 200
    assert response.json() == []


def test_superuser_lists_positions_of_all_users(admin_client, user_position):
    response = admin_client.get(list_url())

    assert response.status_code == 200
    assert [p["id"] for p in response.json()] == [1, 2, user_position.id]


@pytest.mark.parametrize("method", ["get", "head"])
def test_superuser_gets_other_users_position(admin_client, user_position, method):
    response = getattr(admin_client, method)(detail_url(user_position.id))

    assert response.status_code == 200


def test_superuser_creates_for_other_users_party(
    admin_client, user_party, user_chamber, user_timeline
):
    response = post(
        admin_client,
        body(user_party, chamber=user_chamber.id, timeline=user_timeline.id),
    )

    assert response.status_code == 201
    assert user_party.positions.get().chamber == user_chamber


def test_superuser_updates_other_users_position(admin_client, user_position):
    response = put(
        admin_client,
        user_position.id,
        body(user_position.party, position="opposition"),
    )

    assert response.status_code == 200
    user_position.refresh_from_db()
    assert user_position.position == PartyPositionType.OPPOSITION


def test_superuser_deletes_other_users_position(admin_client, user_position):
    response = admin_client.delete(detail_url(user_position.id))

    assert response.status_code == 204
    assert not PartyPosition.objects.filter(pk=user_position.pk).exists()


@pytest.mark.parametrize(
    "institution, message",
    [
        ("government", "Party positions can only be held in a chamber."),
        ("foreign_chamber", "The chamber must belong to the party's country."),
    ],
)
def test_create_outside_the_party_chambers_400(
    request, admin_client, psd, institution, message
):
    chamber = request.getfixturevalue(institution)

    response = post(admin_client, body(psd, chamber=chamber.id))

    assert response.status_code == 400
    assert response.json() == {"chamber": [message]}
    assert not psd.positions.exists()


@pytest.mark.parametrize(
    "institution, message",
    [
        ("government", "Party positions can only be held in a chamber."),
        ("foreign_chamber", "The chamber must belong to the party's country."),
    ],
)
def test_update_outside_the_party_chambers_400(
    request, admin_client, psd, senate, institution, message
):
    position = framed_position(psd, chamber=senate)
    chamber = request.getfixturevalue(institution)

    response = put(admin_client, position.id, body(psd, chamber=chamber.id))

    assert response.status_code == 400
    assert response.json() == {"chamber": [message]}
    position.refresh_from_db()
    assert position.chamber == senate


def test_create_without_chamber_is_default_position(admin_client, psd):
    response = post(admin_client, body(psd))

    assert response.status_code == 201
    assert response.json()["chamber"] is None
    assert psd.positions.get().chamber is None


def test_create_without_time_frame_occupies_one_open_frame(
    admin_client, psd, default_timeline, alternate_timeline
):
    response = post(admin_client, body(psd))

    assert response.status_code == 201
    position = psd.positions.get()
    frame = TimeFrame.objects.of(position).get()
    assert (frame.valid_from, frame.valid_to) == (None, None)
    assert frame.is_on_all_timelines
    assert is_active(position, default_timeline, at(1900))
    assert is_active(position, alternate_timeline, at(2100))


def test_create_without_timeline_is_on_all_timelines(
    admin_client, psd, default_timeline, alternate_timeline
):
    response = post(admin_client, body(psd, validFrom=dt(2020)))

    assert response.status_code == 201
    assert response.json()["timeline"] is None
    position = psd.positions.get()
    assert is_active(position, default_timeline, at(2021))
    assert is_active(position, alternate_timeline, at(2021))


def test_create_on_timeline_is_only_on_that_timeline(
    admin_client, psd, default_timeline, alternate_timeline
):
    response = post(
        admin_client, body(psd, validFrom=dt(2020), timeline=alternate_timeline.id)
    )

    assert response.status_code == 201
    assert response.json()["timeline"] == alternate_timeline.id
    position = psd.positions.get()
    assert not is_active(position, default_timeline, at(2021))
    assert is_active(position, alternate_timeline, at(2021))


def test_create_without_valid_to_is_active_from_valid_from_on(
    admin_client, psd, default_timeline
):
    response = post(admin_client, body(psd, validFrom=dt(2020)))

    assert response.status_code == 201
    assert response.json()["validTo"] is None
    position = psd.positions.get()
    assert not is_active(position, default_timeline, at(2019))
    assert is_active(position, default_timeline, at(2100))


def test_create_without_valid_from_is_active_until_valid_to(
    admin_client, psd, default_timeline
):
    response = post(admin_client, body(psd, validTo=dt(2020)))

    assert response.status_code == 201
    assert response.json()["validFrom"] is None
    position = psd.positions.get()
    assert is_active(position, default_timeline, at(1900))
    assert not is_active(position, default_timeline, at(2020))


def test_create_second_position_without_end_400(admin_client, psd):
    framed_position(psd, valid_from=at(2020))

    response = post(admin_client, body(psd, position="opposition", validFrom=dt(2024)))

    assert response.status_code == 400
    assert response.json() == overlap("majority", "[2020-01-01, +inf)")
    assert psd.positions.count() == 1


def test_create_second_position_without_start_400(admin_client, psd):
    framed_position(psd, valid_to=at(2010))

    response = post(admin_client, body(psd, position="opposition", validTo=dt(2000)))

    assert response.status_code == 400
    assert response.json() == overlap("majority", "[-inf, 2010-01-01)")
    assert psd.positions.count() == 1


def test_create_position_starting_when_the_previous_ends_success(admin_client, psd):
    framed_position(psd, valid_from=at(2010), valid_to=at(2020))

    response = post(admin_client, body(psd, position="opposition", validFrom=dt(2020)))

    assert response.status_code == 201


def test_create_overlapping_position_on_other_timeline_success(
    admin_client, psd, default_timeline, alternate_timeline
):
    framed_position(psd, valid_from=at(2020), timelines=[default_timeline])

    response = post(
        admin_client,
        body(
            psd,
            position="opposition",
            validFrom=dt(2020),
            timeline=alternate_timeline.id,
        ),
    )

    assert response.status_code == 201


def test_create_overlapping_position_on_all_timelines_400(
    admin_client, psd, alternate_timeline
):
    framed_position(psd, valid_from=at(2020))

    response = post(
        admin_client,
        body(
            psd,
            position="opposition",
            validFrom=dt(2024),
            timeline=alternate_timeline.id,
        ),
    )

    assert response.status_code == 400
    assert response.json() == overlap(
        "majority", "[2020-01-01, +inf)", "timeline 'alternate'"
    )


@pytest.mark.parametrize("end_year", [2020, 2019])
def test_create_time_frame_ending_before_start_400(admin_client, psd, end_year):
    response = post(admin_client, body(psd, validFrom=dt(2020), validTo=dt(end_year)))

    assert response.status_code == 400
    assert response.json() == {"valid_to": ["The time frame must end after it starts."]}
    assert not psd.positions.exists()


def test_create_on_timeline_of_other_settings_400(admin_client, psd, user_timeline):
    response = post(admin_client, body(psd, timeline=user_timeline.id))

    assert response.status_code == 400
    assert response.json() == {
        "non_field_errors": [
            "The timelines must belong to the same global context as the time "
            "frame's subject."
        ]
    }
    assert not psd.positions.exists()


def test_create_next_to_frameless_position_400(
    admin_client, majority_party, parliament
):
    response = post(
        admin_client,
        body(
            majority_party,
            position="opposition",
            chamber=parliament.id,
            validFrom=dt(2020),
        ),
    )

    assert response.status_code == 400
    assert response.json() == {
        "chamber": [
            "'majority' holds the majority position in 'Testland parliament' "
            "without a time frame, i.e. at all times on all timelines: no other "
            "position can be added."
        ]
    }
    assert majority_party.positions.count() == 1


def test_default_and_chamber_positions_may_overlap(admin_client, psd, senate):
    default = post(admin_client, body(psd, validFrom=dt(2020)))
    in_senate = post(
        admin_client,
        body(
            psd,
            position="opposition",
            chamber=senate.id,
            validFrom=dt(2022),
            validTo=dt(2024),
        ),
    )

    assert (default.status_code, in_senate.status_code) == (201, 201)


def test_default_positions_may_not_overlap(admin_client, psd):
    framed_position(psd, valid_from=at(2020), valid_to=at(2030))

    response = post(
        admin_client,
        body(psd, position="opposition", validFrom=dt(2022), validTo=dt(2024)),
    )

    assert response.status_code == 400
    assert response.json() == overlap("majority", "[2020-01-01, 2030-01-01)")


def test_positions_in_the_same_chamber_may_not_overlap(admin_client, psd, senate):
    framed_position(psd, chamber=senate, valid_from=at(2020))

    response = post(
        admin_client,
        body(
            psd,
            position="opposition",
            chamber=senate.id,
            validFrom=dt(2022),
            validTo=dt(2024),
        ),
    )

    assert response.status_code == 400
    assert response.json() == overlap("majority", "[2020-01-01, +inf)")


def test_positions_in_different_chambers_may_overlap(
    admin_client, psd, senate, parliament
):
    framed_position(psd, chamber=senate, valid_from=at(2020))

    response = post(
        admin_client,
        body(psd, position="opposition", chamber=parliament.id, validFrom=dt(2020)),
    )

    assert response.status_code == 201


def test_create_default_position_next_to_frameless_chamber_position_success(
    admin_client, majority_party
):
    response = post(admin_client, body(majority_party, position="opposition"))

    assert response.status_code == 201
    assert majority_party.positions.count() == 2


def test_update_specializes_default_position_to_chamber(admin_client, psd, senate):
    position = framed_position(psd, valid_from=at(2020))

    response = put(
        admin_client, position.id, body(psd, chamber=senate.id, validFrom=dt(2020))
    )

    assert response.status_code == 200
    assert response.json()["chamber"] == senate.id
    position.refresh_from_db()
    assert position.chamber == senate


def test_update_generalizes_chamber_position_to_default(admin_client, psd, senate):
    position = framed_position(psd, chamber=senate, valid_from=at(2020))

    response = put(admin_client, position.id, body(psd, validFrom=dt(2020)))

    assert response.status_code == 200
    assert response.json()["chamber"] is None
    position.refresh_from_db()
    assert position.chamber is None


def test_update_restricts_position_to_timeline(
    admin_client, psd, default_timeline, alternate_timeline
):
    position = framed_position(psd, valid_from=at(2020))

    response = put(
        admin_client,
        position.id,
        body(psd, validFrom=dt(2020), timeline=alternate_timeline.id),
    )

    assert response.status_code == 200
    assert not is_active(position, default_timeline, at(2021))
    assert is_active(position, alternate_timeline, at(2021))


def test_update_extends_position_to_all_timelines(
    admin_client, psd, default_timeline, alternate_timeline
):
    position = framed_position(psd, valid_from=at(2020), timelines=[alternate_timeline])

    response = put(admin_client, position.id, body(psd, validFrom=dt(2020)))

    assert response.status_code == 200
    assert response.json()["timeline"] is None
    assert is_active(position, default_timeline, at(2021))


def test_update_resets_omitted_fields(admin_client, psd, senate, alternate_timeline):
    position = framed_position(
        psd,
        chamber=senate,
        valid_from=at(2020),
        valid_to=at(2024),
        timelines=[alternate_timeline],
    )

    response = put(admin_client, position.id, body(psd))

    assert response.status_code == 200
    assert response.json() == position_json(position.id, psd.id)


def test_update_extends_own_time_frame_success(admin_client, psd):
    position = framed_position(psd, valid_from=at(2020), valid_to=at(2022))

    response = put(
        admin_client, position.id, body(psd, validFrom=dt(2018), validTo=dt(2024))
    )

    assert response.status_code == 200
    frame = TimeFrame.objects.of(position).get()
    assert (frame.valid_from, frame.valid_to) == (at(2018), at(2024))


def test_update_replaces_all_time_frames_with_one(
    admin_client, psd, default_timeline, alternate_timeline
):
    position = framed_position(psd, valid_from=at(2020), timelines=[default_timeline])
    TimeFrame.objects.occupy(position, at(2010), at(2015), [alternate_timeline])

    response = put(admin_client, position.id, body(psd, validFrom=dt(2000)))

    assert response.status_code == 200
    frame = TimeFrame.objects.of(position).get()
    assert (frame.valid_from, frame.valid_to) == (at(2000), None)
    assert frame.is_on_all_timelines


def test_update_frameless_position_occupies_one_frame(
    admin_client, majority_party, parliament, frameless_position
):
    response = put(
        admin_client,
        frameless_position.id,
        body(majority_party, chamber=parliament.id, validFrom=dt(2020)),
    )

    assert response.status_code == 200
    assert TimeFrame.objects.of(frameless_position).get().valid_from == at(2020)


def test_update_into_overlap_400_keeps_position(admin_client, psd, senate):
    framed_position(psd, chamber=senate, valid_from=at(2020))
    default = framed_position(psd, PartyPositionType.OPPOSITION, valid_from=at(2021))

    response = put(
        admin_client,
        default.id,
        body(psd, position="opposition", chamber=senate.id, validFrom=dt(2022)),
    )

    assert response.status_code == 400
    assert response.json() == overlap("majority", "[2020-01-01, +inf)")
    default.refresh_from_db()
    assert default.chamber is None
    assert TimeFrame.objects.of(default).get().valid_from == at(2021)


def test_update_into_chamber_with_frameless_position_400(
    admin_client, majority_party, parliament
):
    default = framed_position(
        majority_party, PartyPositionType.OPPOSITION, valid_from=at(2020)
    )

    response = put(
        admin_client,
        default.id,
        body(
            majority_party,
            position="opposition",
            chamber=parliament.id,
            validFrom=dt(2020),
        ),
    )

    assert response.status_code == 400
    assert response.json() == {
        "non_field_errors": [
            "'majority' (majority) has no time frame, so it is active at all "
            "times on all timelines."
        ]
    }
    default.refresh_from_db()
    assert default.chamber is None


def test_update_move_to_other_party_400(
    admin_client, majority_party, frameless_position, parliament, psd
):
    response = put(
        admin_client, frameless_position.id, body(psd, chamber=parliament.id)
    )

    assert response.status_code == 400
    assert response.json() == {
        "party": ["A party position cannot be moved to another party."]
    }
    frameless_position.refresh_from_db()
    assert frameless_position.party == majority_party


def test_create_batch_with_invalid_position_400_creates_nothing(admin_client, psd):
    response = post(admin_client, [body(psd), body(psd, position="leader")])

    assert response.status_code == 400
    assert response.json() == [{}, {"position": ['"leader" is not a valid choice.']}]
    assert not psd.positions.exists()


def test_create_batch_with_overlapping_positions_400_creates_nothing(admin_client, psd):
    response = post(
        admin_client,
        [
            body(psd, validFrom=dt(2020)),
            body(psd, position="opposition", validFrom=dt(2024)),
        ],
    )

    assert response.status_code == 400
    assert response.json() == [{}, overlap("majority", "[2020-01-01, +inf)")]
    assert not psd.positions.exists()
    assert not TimeFrame.objects.exists()


def test_create_empty_batch_400(admin_client):
    response = post(admin_client, [])

    assert response.status_code == 400
    assert response.json() == {"non_field_errors": ["This list may not be empty."]}


def test_list_filtered_by_party(admin_client, psd):
    position = framed_position(psd)

    response = admin_client.get(list_url(), {"party": psd.id})

    assert response.status_code == 200
    assert [p["id"] for p in response.json()] == [position.id]


def test_list_filtered_by_chamber_excludes_default_positions(admin_client, psd, senate):
    in_senate = framed_position(psd, chamber=senate)
    framed_position(psd, PartyPositionType.OPPOSITION)

    response = admin_client.get(list_url(), {"chamber": senate.id})

    assert response.status_code == 200
    assert [p["id"] for p in response.json()] == [in_senate.id]


def test_list_filtered_by_party_and_chamber(admin_client, psd, parliament):
    in_parliament = framed_position(psd, chamber=parliament)
    framed_position(psd, PartyPositionType.OPPOSITION)

    response = admin_client.get(list_url(), {"party": psd.id, "chamber": parliament.id})

    assert response.status_code == 200
    assert [p["id"] for p in response.json()] == [in_parliament.id]


@pytest.mark.parametrize(
    "query, errors",
    [
        ({"party": "PSD"}, {"party": ["A valid integer is required."]}),
        ({"chamber": "senate"}, {"chamber": ["A valid integer is required."]}),
    ],
)
def test_list_invalid_filter_400(admin_client, query, errors):
    response = admin_client.get(list_url(), query)

    assert response.status_code == 400
    assert response.json() == errors


def test_delete_default_position_keeps_chamber_positions(admin_client, psd, senate):
    default = framed_position(psd, valid_from=at(2020))
    in_senate = framed_position(
        psd, PartyPositionType.OPPOSITION, senate, valid_from=at(2022)
    )

    response = admin_client.delete(detail_url(default.id))

    assert response.status_code == 204
    assert list(psd.positions.all()) == [in_senate]
    assert TimeFrame.objects.of(in_senate).exists()
