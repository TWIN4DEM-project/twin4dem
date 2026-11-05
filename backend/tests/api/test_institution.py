from datetime import UTC, datetime

import pytest

from common.models import (
    Institution,
    InstitutionBranch,
    InstitutionKind,
    PartyPosition,
    PartyPositionType,
    Simulation,
    TimeFrame,
    VirtualTimeline,
)

pytestmark = pytest.mark.django_db

INSTITUTIONS = "/api/v1/institution/"
GOVERNMENT = "/api/v1/institution/1/"
JSON = "application/json"
NOT_PERMITTED = {"detail": "You do not have permission to perform this action."}
CABINET_PAYLOAD = {"connectivity_degree": 3, "probability_for": None}
CHAMBER_PAYLOAD = {"majority_probability_for": None, "opposition_probability_for": None}
COURT_PAYLOAD = {"probability_for": None}


def institution_url(institution: Institution) -> str:
    return f"{INSTITUTIONS}{institution.id}/"


def at(date: str) -> datetime:
    """Midnight UTC of `date` ('YYYY-MM-DD'), as stored in a time frame."""
    return datetime.fromisoformat(date).replace(tzinfo=UTC)


def frame(
    valid_from: str | None = None, valid_to: str | None = None, timelines=()
) -> dict:
    """A time frame as sent to and returned by the API, dates at midnight UTC."""
    return {
        "validFrom": f"{valid_from}T00:00:00Z" if valid_from else None,
        "validTo": f"{valid_to}T00:00:00Z" if valid_to else None,
        "timelines": list(timelines),
    }


def frames_of(institution: Institution) -> list[tuple]:
    """The stored bounds of the institution's time frames."""
    frames = TimeFrame.objects.of(institution).order_by("id")
    return list(frames.values_list("valid_from", "valid_to"))


def government_body(**fields) -> dict:
    """The body of Testland's government, as in the fixture."""
    return {"kind": 1, "label": "Testland government", "size": 15, **fields}


def government_json(**fields) -> dict:
    """Testland's government, as returned by the API."""
    return {
        "id": 1,
        **government_body(),
        "payload": CABINET_PAYLOAD,
        "timeFrames": [],
        **fields,
    }


def senate_body(
    kind: InstitutionKind, label: str, *time_frames: dict, **fields
) -> dict:
    """The body of a senate of `kind`, frameless when no time frame is given."""
    return {
        "kind": kind.id,
        "label": label,
        "size": 136,
        "timeFrames": list(time_frames),
        **fields,
    }


def senate_json(institution: Institution, *time_frames: dict, **fields) -> dict:
    """A senate as returned by the API."""
    return {
        "id": institution.id,
        "kind": institution.kind_id,
        "label": institution.label,
        "size": 136,
        "payload": CHAMBER_PAYLOAD,
        "timeFrames": list(time_frames),
        **fields,
    }


def cabinet_body(kind: InstitutionKind, **fields) -> dict:
    """The body of a frameless cabinet of `kind`."""
    return {"kind": kind.id, "label": "Userland cabinet", "size": 10, **fields}


@pytest.fixture
def senate_kind() -> InstitutionKind:
    """Testland's senate, without institutions."""
    return InstitutionKind.objects.create(
        country_id=1,
        branch=InstitutionBranch.LEGISLATIVE,
        institution_name="senate",
    )


@pytest.fixture
def senate_2020(framed_senate) -> Institution:
    return framed_senate.institutions.get()


@pytest.fixture
def senate_2016(framed_senate) -> Institution:
    """The predecessor of 'Senate 2020', until 2020-12-21 on all timelines."""
    institution = Institution.objects.create(
        kind=framed_senate, label="Senate 2016", size=136
    )
    TimeFrame.objects.occupy(
        institution, valid_from=at("2016-12-21"), valid_to=at("2020-12-21")
    )
    return institution


@pytest.fixture
def user_institution(user_kind) -> Institution:
    return Institution.objects.create(
        kind=user_kind, label="Userland cabinet", size=10, payload=CABINET_PAYLOAD
    )


def test_list_success(admin_client):
    response = admin_client.get(INSTITUTIONS)

    assert response.status_code == 200
    assert [institution["label"] for institution in response.json()] == [
        "Testland government",
        "Testland parliament",
        "Testland court",
    ]
    assert response.json()[0] == government_json()


def test_get_by_id_success(admin_client):
    response = admin_client.get(GOVERNMENT)

    assert response.status_code == 200
    assert response.json() == government_json()


def test_get_by_id_with_time_frames_success(admin_client, senate_2020):
    response = admin_client.get(institution_url(senate_2020))

    assert response.status_code == 200
    assert response.json()["timeFrames"] == [frame("2020-12-21")]


def test_head_success_without_body(admin_client):
    response = admin_client.head(GOVERNMENT)

    assert response.status_code == 200
    assert response.content == b""


@pytest.mark.parametrize("method", ["get", "head", "put", "delete"])
def test_unknown_id_404(admin_client, method):
    response = getattr(admin_client, method)(f"{INSTITUTIONS}0/")

    assert response.status_code == 404


def test_create_success(admin_client, senate_kind):
    response = admin_client.post(
        INSTITUTIONS,
        senate_body(senate_kind, "Senate 2020", frame("2020-12-21")),
        content_type=JSON,
    )

    assert response.status_code == 201
    institution = senate_kind.institutions.get()
    assert response.json() == senate_json(institution, frame("2020-12-21"))
    assert frames_of(institution) == [(at("2020-12-21"), None)]


def test_create_without_data_400(admin_client):
    response = admin_client.post(INSTITUTIONS, {}, content_type=JSON)

    assert response.status_code == 400
    assert response.json() == {
        "kind": ["This field is required."],
        "label": ["This field is required."],
        "size": ["This field is required."],
    }


def test_create_batch_success(admin_client, senate_kind):
    response = admin_client.post(
        INSTITUTIONS,
        [
            senate_body(senate_kind, "Senate 2016", frame("2016-12-21", "2020-12-21")),
            senate_body(senate_kind, "Senate 2020", frame("2020-12-21")),
        ],
        content_type=JSON,
    )

    assert response.status_code == 201
    first, second = senate_kind.institutions.order_by("id")
    assert response.json() == [
        senate_json(first, frame("2016-12-21", "2020-12-21")),
        senate_json(second, frame("2020-12-21")),
    ]


def test_update_success(admin_client, senate_2020):
    response = admin_client.put(
        institution_url(senate_2020),
        senate_body(senate_2020.kind, "Senate 2021", frame("2021-01-01"), size=140),
        content_type=JSON,
    )

    assert response.status_code == 200
    assert response.json() == senate_json(
        senate_2020, frame("2021-01-01"), label="Senate 2021", size=140
    )
    senate_2020.refresh_from_db()
    assert (senate_2020.label, senate_2020.size) == ("Senate 2021", 140)
    assert frames_of(senate_2020) == [(at("2021-01-01"), None)]


def test_update_keeping_label_success(admin_client):
    response = admin_client.put(GOVERNMENT, government_body(), content_type=JSON)

    assert response.status_code == 200
    assert response.json() == government_json()


def test_delete_success(admin_client, senate_2020):
    response = admin_client.delete(institution_url(senate_2020))

    assert response.status_code == 204
    assert response.content == b""
    assert not Institution.objects.filter(pk=senate_2020.pk).exists()


def test_patch_not_allowed(admin_client):
    response = admin_client.patch(GOVERNMENT, {"size": 1}, content_type=JSON)

    assert response.status_code == 405


@pytest.mark.parametrize(
    "branch, labels",
    [
        ("executive", ["Testland government"]),
        ("legislative", ["Testland parliament"]),
        ("judiciary", ["Testland court"]),
    ],
)
def test_list_filtered_by_branch(admin_client, branch, labels):
    response = admin_client.get(f"{INSTITUTIONS}?branch={branch}")

    assert response.status_code == 200
    assert [institution["label"] for institution in response.json()] == labels


def test_list_filtered_by_kind(admin_client):
    response = admin_client.get(f"{INSTITUTIONS}?kind=2")

    assert response.status_code == 200
    assert [institution["id"] for institution in response.json()] == [2]


def test_list_filtered_by_country(admin_client, user_institution):
    response = admin_client.get(
        f"{INSTITUTIONS}?country={user_institution.kind.country_id}"
    )

    assert response.status_code == 200
    assert [institution["id"] for institution in response.json()] == [
        user_institution.id
    ]


def test_list_filtered_by_country_and_branch(admin_client, user_institution):
    response = admin_client.get(f"{INSTITUTIONS}?country=1&branch=executive")

    assert response.status_code == 200
    assert [institution["id"] for institution in response.json()] == [1]


def test_list_filtered_by_unknown_kind_empty(admin_client):
    response = admin_client.get(f"{INSTITUTIONS}?kind=0")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize(
    "query, errors",
    [
        ("branch=military", {"branch": ['"military" is not a valid choice.']}),
        ("country=Testland", {"country": ["A valid integer is required."]}),
        ("kind=government", {"kind": ["A valid integer is required."]}),
    ],
)
def test_list_invalid_filter_400(admin_client, query, errors):
    response = admin_client.get(f"{INSTITUTIONS}?{query}")

    assert response.status_code == 400
    assert response.json() == errors


@pytest.mark.parametrize(
    "method, url",
    [
        ("get", INSTITUTIONS),
        ("post", INSTITUTIONS),
        ("get", GOVERNMENT),
        ("head", GOVERNMENT),
        ("put", GOVERNMENT),
        ("delete", GOVERNMENT),
    ],
)
def test_anonymous_forbidden(client, method, url):
    response = getattr(client, method)(url)

    assert response.status_code == 403


def test_list_anonymous_forbidden_message(client):
    response = client.get(INSTITUTIONS)

    assert response.json() == {
        "detail": "Authentication credentials were not provided."
    }


def test_list_without_permissions_shows_own_institutions(user_client, user_institution):
    response = user_client.get(INSTITUTIONS)

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": user_institution.id,
            "kind": user_institution.kind_id,
            "label": "Userland cabinet",
            "size": 10,
            "payload": CABINET_PAYLOAD,
            "timeFrames": [],
        }
    ]


def test_list_filtered_by_other_users_country_empty(user_client, user_institution):
    response = user_client.get(f"{INSTITUTIONS}?country=1")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize("method", ["get", "head"])
def test_get_by_id_without_permissions_success(user_client, user_institution, method):
    response = getattr(user_client, method)(institution_url(user_institution))

    assert response.status_code == 200


def test_create_without_permissions_forbidden(user_client, user_kind):
    response = user_client.post(
        INSTITUTIONS, cabinet_body(user_kind), content_type=JSON
    )

    assert response.status_code == 403
    assert response.json() == NOT_PERMITTED
    assert not user_kind.institutions.exists()


def test_update_without_permissions_forbidden(user_client, user_institution):
    response = user_client.put(
        institution_url(user_institution),
        cabinet_body(user_institution.kind, label="Renamed"),
        content_type=JSON,
    )

    assert response.status_code == 403
    assert response.json() == NOT_PERMITTED
    user_institution.refresh_from_db()
    assert user_institution.label == "Userland cabinet"


def test_delete_without_permissions_forbidden(user_client, user_institution):
    response = user_client.delete(institution_url(user_institution))

    assert response.status_code == 403
    assert response.json() == NOT_PERMITTED
    assert Institution.objects.filter(pk=user_institution.pk).exists()


@pytest.mark.parametrize("user_client", [["add_institution"]], indirect=True)
def test_create_with_add_permission_success(user_client, user_kind):
    response = user_client.post(
        INSTITUTIONS, cabinet_body(user_kind), content_type=JSON
    )

    assert response.status_code == 201
    assert user_kind.institutions.get().label == "Userland cabinet"


@pytest.mark.parametrize("user_client", [["add_institution"]], indirect=True)
def test_delete_with_only_add_permission_forbidden(user_client, user_institution):
    response = user_client.delete(institution_url(user_institution))

    assert response.status_code == 403
    assert Institution.objects.filter(pk=user_institution.pk).exists()


@pytest.mark.parametrize("user_client", [["change_institution"]], indirect=True)
def test_update_with_change_permission_success(user_client, user_institution):
    response = user_client.put(
        institution_url(user_institution),
        cabinet_body(user_institution.kind, label="Renamed"),
        content_type=JSON,
    )

    assert response.status_code == 200
    user_institution.refresh_from_db()
    assert user_institution.label == "Renamed"


@pytest.mark.parametrize("user_client", [["delete_institution"]], indirect=True)
def test_delete_with_delete_permission_success(user_client, user_institution):
    response = user_client.delete(institution_url(user_institution))

    assert response.status_code == 204
    assert not Institution.objects.filter(pk=user_institution.pk).exists()


@pytest.mark.parametrize(
    "user_client",
    [["add_institution", "change_institution", "delete_institution"]],
    indirect=True,
)
@pytest.mark.parametrize("method", ["get", "head", "put", "delete"])
def test_other_users_institution_404(user_client, method):
    response = getattr(user_client, method)(GOVERNMENT)

    assert response.status_code == 404
    assert Institution.objects.get(pk=1).label == "Testland government"


@pytest.mark.parametrize("user_client", [["add_institution"]], indirect=True)
def test_create_in_other_users_kind_400(user_client):
    response = user_client.post(
        INSTITUTIONS, government_body(label="Castex cabinet"), content_type=JSON
    )

    assert response.status_code == 400
    assert response.json() == {"kind": ['Invalid pk "1" - object does not exist.']}
    assert not Institution.objects.filter(label="Castex cabinet").exists()


@pytest.mark.parametrize("user_client", [["add_institution"]], indirect=True)
def test_create_on_other_users_timeline_400(user_client, user_kind):
    response = user_client.post(
        INSTITUTIONS,
        cabinet_body(user_kind, timeFrames=[frame("2020-01-01", timelines=[1])]),
        content_type=JSON,
    )

    assert response.status_code == 400
    assert response.json() == {
        "time_frames": [{"timelines": ['Invalid pk "1" - object does not exist.']}]
    }
    assert not user_kind.institutions.exists()


@pytest.mark.parametrize("user_client", [["add_institution"]], indirect=True)
def test_create_batch_with_other_users_kind_400(user_client, user_kind):
    response = user_client.post(
        INSTITUTIONS,
        [cabinet_body(user_kind), government_body(label="Castex cabinet")],
        content_type=JSON,
    )

    assert response.status_code == 400
    assert response.json() == [
        {},
        {"kind": ['Invalid pk "1" - object does not exist.']},
    ]
    assert not user_kind.institutions.exists()


def test_superuser_lists_institutions_of_all_users(admin_client, user_institution):
    response = admin_client.get(INSTITUTIONS)

    assert response.status_code == 200
    assert [institution["id"] for institution in response.json()] == [
        1,
        2,
        3,
        user_institution.id,
    ]


@pytest.mark.parametrize("method", ["get", "head"])
def test_superuser_gets_other_users_institution(admin_client, user_institution, method):
    response = getattr(admin_client, method)(institution_url(user_institution))

    assert response.status_code == 200


def test_superuser_creates_in_the_country_of_the_kind(admin_client, user_kind):
    # the body has no country: the institution's country is its kind's, so
    # Userland's kind cannot be used in Testland
    response = admin_client.post(
        INSTITUTIONS, cabinet_body(user_kind, country=1), content_type=JSON
    )

    assert response.status_code == 201
    institution = user_kind.institutions.get()
    assert institution.kind.country_id == user_kind.country_id
    assert not Institution.objects.filter(
        kind__country_id=1, label="Userland cabinet"
    ).exists()


def test_superuser_updates_other_users_institution(admin_client, user_institution):
    response = admin_client.put(
        institution_url(user_institution),
        cabinet_body(user_institution.kind, label="Renamed"),
        content_type=JSON,
    )

    assert response.status_code == 200
    user_institution.refresh_from_db()
    assert user_institution.label == "Renamed"


def test_superuser_deletes_other_users_institution(admin_client, user_institution):
    response = admin_client.delete(institution_url(user_institution))

    assert response.status_code == 204
    assert not Institution.objects.filter(pk=user_institution.pk).exists()


def test_create_duplicate_label_400(admin_client, framed_senate):
    response = admin_client.post(
        INSTITUTIONS,
        senate_body(framed_senate, "Senate 2020", frame("2016-12-21", "2020-12-21")),
        content_type=JSON,
    )

    assert response.status_code == 400
    assert response.json() == {
        "non_field_errors": [
            "An institution with this label already exists for this kind."
        ]
    }
    assert framed_senate.institutions.count() == 1


def test_create_same_label_in_other_kind_success(admin_client, user_kind):
    response = admin_client.post(
        INSTITUTIONS,
        cabinet_body(user_kind, label="Testland government"),
        content_type=JSON,
    )

    assert response.status_code == 201


def test_create_batch_with_duplicate_labels_400(admin_client, senate_kind):
    response = admin_client.post(
        INSTITUTIONS,
        [
            senate_body(senate_kind, "Senate", frame("2016-12-21", "2020-12-21")),
            senate_body(senate_kind, "Senate", frame("2020-12-21")),
        ],
        content_type=JSON,
    )

    assert response.status_code == 400
    # checked by the model: the validator cannot see the other items of the batch
    assert response.json() == [
        {},
        {"non_field_errors": ["Institution with this Kind and Label already exists."]},
    ]
    assert not senate_kind.institutions.exists()


def test_update_duplicate_label_400(admin_client, senate_2016):
    response = admin_client.put(
        institution_url(senate_2016),
        senate_body(senate_2016.kind, "Senate 2020", frame("2016-12-21", "2020-12-21")),
        content_type=JSON,
    )

    assert response.status_code == 400
    assert response.json() == {
        "non_field_errors": [
            "An institution with this label already exists for this kind."
        ]
    }
    senate_2016.refresh_from_db()
    assert senate_2016.label == "Senate 2016"


@pytest.mark.parametrize(
    "branch, payload",
    [
        (InstitutionBranch.EXECUTIVE, CABINET_PAYLOAD),
        (InstitutionBranch.LEGISLATIVE, CHAMBER_PAYLOAD),
        (InstitutionBranch.JUDICIARY, COURT_PAYLOAD),
    ],
)
def test_create_fills_payload_defaults_of_branch(admin_client, branch, payload):
    kind = InstitutionKind.objects.create(
        country_id=1, branch=branch, institution_name="new kind"
    )

    response = admin_client.post(
        INSTITUTIONS, {"kind": kind.id, "label": "New", "size": 1}, content_type=JSON
    )

    assert response.status_code == 201
    assert response.json()["payload"] == payload
    assert kind.institutions.get().payload == payload


def test_create_invalid_payload_400(admin_client, user_kind):
    response = admin_client.post(
        INSTITUTIONS,
        cabinet_body(user_kind, payload={"connectivity_degree": 0}),
        content_type=JSON,
    )

    assert response.status_code == 400
    assert response.json() == {
        "payload": ["connectivity_degree: Input should be greater than or equal to 1"]
    }
    assert not user_kind.institutions.exists()


def test_create_payload_of_other_branch_400(admin_client, user_kind):
    response = admin_client.post(
        INSTITUTIONS,
        cabinet_body(user_kind, payload={"majority_probability_for": 0.5}),
        content_type=JSON,
    )

    assert response.status_code == 400
    assert response.json() == {
        "payload": ["majority_probability_for: Extra inputs are not permitted"]
    }


def test_update_fills_payload_defaults(admin_client):
    response = admin_client.put(
        GOVERNMENT, government_body(payload={"probability_for": 0.5}), content_type=JSON
    )

    assert response.status_code == 200
    payload = {"connectivity_degree": 3, "probability_for": 0.5}
    assert response.json()["payload"] == payload
    assert Institution.objects.get(pk=1).payload == payload


def test_update_without_payload_resets_defaults(admin_client):
    Institution.objects.filter(pk=1).update(
        payload={"connectivity_degree": 5, "probability_for": 0.5}
    )

    response = admin_client.put(GOVERNMENT, government_body(), content_type=JSON)

    assert response.status_code == 200
    assert response.json()["payload"] == CABINET_PAYLOAD
    assert Institution.objects.get(pk=1).payload == CABINET_PAYLOAD


def test_update_kind_400(admin_client):
    response = admin_client.put(GOVERNMENT, government_body(kind=2), content_type=JSON)

    assert response.status_code == 400
    assert response.json() == {
        "kind": ["The kind of an institution cannot be changed."]
    }
    assert Institution.objects.get(pk=1).kind_id == 1


def test_create_adjacent_time_frame_success(admin_client, framed_senate):
    # time frames end before their valid_to: 'Senate 2020' starts right after
    response = admin_client.post(
        INSTITUTIONS,
        senate_body(framed_senate, "Senate 2016", frame("2016-12-21", "2020-12-21")),
        content_type=JSON,
    )

    assert response.status_code == 201


def test_create_overlapping_sibling_400(admin_client, framed_senate):
    response = admin_client.post(
        INSTITUTIONS,
        senate_body(framed_senate, "Senate 2016", frame("2016-12-21", "2021-01-01")),
        content_type=JSON,
    )

    assert response.status_code == 400
    assert response.json() == {
        "time_frames": [
            {
                "non_field_errors": [
                    "Overlaps with 'Senate 2020' [2020-12-21, +inf) on all timelines."
                ]
            }
        ]
    }
    assert not Institution.objects.filter(label="Senate 2016").exists()


def test_create_same_dates_as_sibling_on_other_timeline_success(
    admin_client, senate_kind, alternate_timeline
):
    response = admin_client.post(
        INSTITUTIONS,
        [
            senate_body(senate_kind, "Senate", frame("2016-12-21", timelines=[1])),
            senate_body(
                senate_kind,
                "Alternate senate",
                frame("2016-12-21", timelines=[alternate_timeline.id]),
            ),
        ],
        content_type=JSON,
    )

    assert response.status_code == 201


def test_create_two_time_frames_on_a_timeline_400(admin_client, senate_kind):
    # at most one time frame per timeline, even without overlapping in time
    response = admin_client.post(
        INSTITUTIONS,
        senate_body(
            senate_kind,
            "Senate",
            frame("2016-12-21", "2020-12-21"),
            frame("2024-01-01"),
        ),
        content_type=JSON,
    )

    assert response.status_code == 400
    assert response.json() == {
        "time_frames": [
            {},
            {
                "non_field_errors": [
                    "'Senate' already occupies the time frame [2016-12-21, 2020-12-21) "
                    "on all timelines."
                ]
            },
        ]
    }
    assert not senate_kind.institutions.exists()
    assert not TimeFrame.objects.exists()


def test_create_time_frames_on_different_timelines_success(
    admin_client, senate_kind, alternate_timeline
):
    time_frames = [
        frame("2016-12-21", timelines=[1]),
        frame("2020-12-21", timelines=[alternate_timeline.id]),
    ]

    response = admin_client.post(
        INSTITUTIONS,
        senate_body(senate_kind, "Senate", *time_frames),
        content_type=JSON,
    )

    assert response.status_code == 201
    assert response.json()["timeFrames"] == time_frames


@pytest.mark.parametrize(
    "valid_to", ["2016-12-21", "2020-12-21"], ids=["ends-before-start", "ends-at-start"]
)
def test_create_time_frame_not_ending_after_start_400(
    admin_client, senate_kind, valid_to
):
    response = admin_client.post(
        INSTITUTIONS,
        senate_body(senate_kind, "Senate", frame("2020-12-21", valid_to)),
        content_type=JSON,
    )

    assert response.status_code == 400
    assert response.json() == {
        "time_frames": [{"valid_to": ["The time frame must end after it starts."]}]
    }
    assert not senate_kind.institutions.exists()


def test_create_on_timeline_of_other_settings_400(
    admin_client, senate_kind, test_user_settings
):
    timeline = VirtualTimeline.objects.get(user_settings=test_user_settings)

    response = admin_client.post(
        INSTITUTIONS,
        senate_body(senate_kind, "Senate", frame(timelines=[timeline.id])),
        content_type=JSON,
    )

    assert response.status_code == 400
    assert response.json() == {
        "time_frames": [
            {
                "non_field_errors": [
                    "The timelines must belong to the same global context as the "
                    "time frame's subject."
                ]
            }
        ]
    }
    assert not senate_kind.institutions.exists()


def test_create_frameless_without_siblings_success(admin_client, senate_kind):
    response = admin_client.post(
        INSTITUTIONS, senate_body(senate_kind, "Senate"), content_type=JSON
    )

    assert response.status_code == 201
    assert response.json()["timeFrames"] == []
    assert not TimeFrame.objects.exists()


def test_create_frameless_with_siblings_400(admin_client, framed_senate):
    response = admin_client.post(
        INSTITUTIONS,
        {"kind": framed_senate.id, "label": "Senate", "size": 136},
        content_type=JSON,
    )

    assert response.status_code == 400
    assert response.json() == {
        "time_frames": [
            "Without time frames the institution is active at all times, so it "
            "would overlap the other institutions of the same kind."
        ]
    }
    assert framed_senate.institutions.count() == 1


def test_create_sibling_of_frameless_institution_400(admin_client):
    response = admin_client.post(
        INSTITUTIONS,
        government_body(label="Castex cabinet", timeFrames=[frame("2020-07-03")]),
        content_type=JSON,
    )

    assert response.status_code == 400
    assert response.json() == {
        "kind": [
            "'Testland government' has no time frame, so it is active at all times "
            "on all timelines: no other institution of type 'government' can be "
            "added."
        ]
    }
    assert not Institution.objects.filter(label="Castex cabinet").exists()


def test_create_batch_reports_all_errors_and_creates_nothing(admin_client, senate_kind):
    # 'Senate 2020' overlaps 'Senate 2016', created earlier in the batch
    response = admin_client.post(
        INSTITUTIONS,
        [
            senate_body(senate_kind, "Senate 2016", frame("2016-12-21", "2021-01-01")),
            senate_body(
                senate_kind,
                "Senate 2012",
                frame("2012-12-21", "2016-12-21"),
                payload={"connectivity_degree": 3},
            ),
            senate_body(senate_kind, "Senate 2020", frame("2020-12-21")),
        ],
        content_type=JSON,
    )

    assert response.status_code == 400
    assert response.json() == [
        {},
        {"payload": ["connectivity_degree: Extra inputs are not permitted"]},
        {
            "time_frames": [
                {
                    "non_field_errors": [
                        "Overlaps with 'Senate 2016' [2016-12-21, 2021-01-01) on all "
                        "timelines."
                    ]
                }
            ]
        },
    ]
    assert not senate_kind.institutions.exists()
    assert not TimeFrame.objects.exists()


def test_create_empty_batch_400(admin_client):
    response = admin_client.post(INSTITUTIONS, [], content_type=JSON)

    assert response.status_code == 400
    assert response.json() == {"non_field_errors": ["This list may not be empty."]}


def test_update_replaces_time_frames(admin_client, senate_2020, alternate_timeline):
    time_frames = [
        frame("2020-12-21", timelines=[1]),
        frame("2022-01-01", timelines=[alternate_timeline.id]),
    ]

    response = admin_client.put(
        institution_url(senate_2020),
        senate_body(senate_2020.kind, "Senate 2020", *time_frames),
        content_type=JSON,
    )

    assert response.status_code == 200
    assert response.json()["timeFrames"] == time_frames
    assert frames_of(senate_2020) == [
        (at("2020-12-21"), None),
        (at("2022-01-01"), None),
    ]


def test_update_overlapping_sibling_400(admin_client, senate_2016):
    response = admin_client.put(
        institution_url(senate_2016),
        senate_body(
            senate_2016.kind, "Senate 2016 bis", frame("2016-12-21", "2021-01-01")
        ),
        content_type=JSON,
    )

    assert response.status_code == 400
    assert response.json() == {
        "time_frames": [
            {
                "non_field_errors": [
                    "Overlaps with 'Senate 2020' [2020-12-21, +inf) on all timelines."
                ]
            }
        ]
    }
    # the label was saved before the time frames: rolled back with them
    senate_2016.refresh_from_db()
    assert senate_2016.label == "Senate 2016"
    assert frames_of(senate_2016) == [(at("2016-12-21"), at("2020-12-21"))]


def test_update_time_frame_ending_before_start_400(admin_client, senate_2020):
    response = admin_client.put(
        institution_url(senate_2020),
        senate_body(senate_2020.kind, "Senate 2020", frame("2020-12-21", "2016-12-21")),
        content_type=JSON,
    )

    assert response.status_code == 400
    assert response.json() == {
        "time_frames": [{"valid_to": ["The time frame must end after it starts."]}]
    }
    assert frames_of(senate_2020) == [(at("2020-12-21"), None)]


def test_update_without_time_frames_makes_frameless(admin_client, senate_2020):
    response = admin_client.put(
        institution_url(senate_2020),
        {"kind": senate_2020.kind_id, "label": "Senate 2020", "size": 136},
        content_type=JSON,
    )

    assert response.status_code == 200
    assert response.json()["timeFrames"] == []
    assert frames_of(senate_2020) == []


def test_update_without_time_frames_with_siblings_400(admin_client, senate_2016):
    response = admin_client.put(
        institution_url(senate_2016),
        {"kind": senate_2016.kind_id, "label": "Senate 2016", "size": 136},
        content_type=JSON,
    )

    assert response.status_code == 400
    assert response.json() == {
        "time_frames": [
            "Without time frames the institution is active at all times, so it "
            "would overlap the other institutions of the same kind."
        ]
    }
    assert frames_of(senate_2016) == [(at("2016-12-21"), at("2020-12-21"))]


@pytest.mark.parametrize("status", Simulation.Status.values)
def test_delete_simulated_institution_409(
    admin_client, legislative_log_simulation, status
):
    Simulation.objects.filter(pk=legislative_log_simulation.pk).update(status=status)

    response = admin_client.delete(GOVERNMENT)

    assert response.status_code == 409
    assert response.json() == {
        "detail": "The institution is used in simulations and cannot be deleted."
    }
    assert Institution.objects.filter(pk=1).exists()


def test_delete_deletes_time_frames_and_party_positions(admin_client, senate_2020):
    PartyPosition.objects.create(
        party_id=1, chamber=senate_2020, position=PartyPositionType.MAJORITY
    )

    response = admin_client.delete(institution_url(senate_2020))

    assert response.status_code == 204
    assert not TimeFrame.objects.exists()
    assert not PartyPosition.objects.filter(chamber_id=senate_2020.id).exists()
