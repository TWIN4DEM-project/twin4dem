from datetime import UTC, datetime

import pytest

from common.models import (
    Institution,
    InstitutionBranch,
    InstitutionKind,
    Simulation,
    TimeFrame,
    VirtualTimeline,
)

pytestmark = pytest.mark.django_db

KINDS = "/api/v1/institution-kind/"
GOVERNMENT = "/api/v1/institution-kind/1/"
JSON = "application/json"
NOT_PERMITTED = {"detail": "You do not have permission to perform this action."}


def kind_url(kind: InstitutionKind) -> str:
    return f"{KINDS}{kind.id}/"


def government_body(**fields) -> dict:
    """The body of the government kind of Testland."""
    return {"name": "government", "country": 1, "branch": "executive", **fields}


def government_json(**fields) -> dict:
    """The government kind of Testland, as returned by the API."""
    testland_government = {
        "id": 1,
        "label": "Testland government",
        "size": 15,
        "payload": {"connectivity_degree": 3, "probability_for": None},
        "timeFrames": [],
    }
    return {
        "id": 1,
        **government_body(),
        "institutions": [testland_government],
        **fields,
    }


def senate_body(country_id: int = 1, **fields) -> dict:
    """The body creating the 'senate' kind, in Testland by default."""
    return {"name": "senate", "country": country_id, "branch": "legislative", **fields}


def institution(label: str, *time_frames: dict, **fields) -> dict:
    """The body of a nested institution, frameless when no time frame is given."""
    return {"label": label, "size": 136, "timeFrames": list(time_frames), **fields}


def assert_senate_not_created():
    assert not InstitutionKind.objects.filter(institution_name="senate").exists()
    assert not Institution.objects.filter(label__startswith="Senate").exists()
    assert not TimeFrame.objects.exists()


@pytest.fixture
def user_kind(userland) -> InstitutionKind:
    return InstitutionKind.objects.create(
        country=userland,
        branch=InstitutionBranch.EXECUTIVE,
        institution_name="cabinet",
    )


@pytest.fixture
def framed_senate() -> InstitutionKind:
    kind = InstitutionKind.objects.create(
        country_id=1,
        branch=InstitutionBranch.LEGISLATIVE,
        institution_name="senate",
    )
    institution = Institution.objects.create(kind=kind, label="Senate 2020", size=136)
    TimeFrame.objects.occupy(institution, valid_from=datetime(2020, 12, 21, tzinfo=UTC))
    return kind


def test_list_success(admin_client):
    response = admin_client.get(KINDS)

    assert response.status_code == 200
    assert [kind["name"] for kind in response.json()] == [
        "government",
        "parliament",
        "court",
    ]
    assert response.json()[0] == government_json()


def test_get_by_id_success(admin_client):
    response = admin_client.get(GOVERNMENT)

    assert response.status_code == 200
    assert response.json() == government_json()


def test_head_success_without_body(admin_client):
    response = admin_client.head(GOVERNMENT)

    assert response.status_code == 200
    assert response.content == b""


@pytest.mark.parametrize("method", ["get", "head"])
def test_get_by_id_404(admin_client, method):
    response = getattr(admin_client, method)(f"{KINDS}0/")

    assert response.status_code == 404


def test_create_success(admin_client):
    response = admin_client.post(KINDS, senate_body(), content_type=JSON)

    assert response.status_code == 201
    kind = InstitutionKind.objects.get(pk=response.json()["id"])
    assert response.json() == {
        "id": kind.id,
        "name": "senate",
        "country": 1,
        "branch": "legislative",
        "institutions": [],
    }


def test_create_without_data_400(admin_client):
    response = admin_client.post(KINDS, {}, content_type=JSON)

    assert response.status_code == 400
    assert response.json() == {
        "name": ["This field is required."],
        "country": ["This field is required."],
        "branch": ["This field is required."],
    }


def test_create_unknown_branch_400(admin_client):
    response = admin_client.post(
        KINDS, senate_body(branch="military"), content_type=JSON
    )

    assert response.status_code == 400
    assert response.json() == {"branch": ['"military" is not a valid choice.']}


def test_update_success(admin_client):
    response = admin_client.put(
        GOVERNMENT, government_body(name="cabinet"), content_type=JSON
    )

    assert response.status_code == 200
    assert response.json() == government_json(name="cabinet")
    assert InstitutionKind.objects.get(pk=1).institution_name == "cabinet"


def test_update_keeping_name_success(admin_client):
    response = admin_client.put(GOVERNMENT, government_body(), content_type=JSON)

    assert response.status_code == 200


def test_delete_success(admin_client):
    response = admin_client.delete(GOVERNMENT)

    assert response.status_code == 204
    assert response.content == b""
    assert not InstitutionKind.objects.filter(pk=1).exists()
    assert not Institution.objects.filter(pk=1).exists()


def test_patch_not_allowed(admin_client):
    response = admin_client.patch(GOVERNMENT, {"name": "x"}, content_type=JSON)

    assert response.status_code == 405


@pytest.mark.parametrize(
    "branch, names",
    [
        ("executive", ["government"]),
        ("legislative", ["parliament"]),
        ("judiciary", ["court"]),
    ],
)
def test_list_filtered_by_branch(admin_client, branch, names):
    response = admin_client.get(f"{KINDS}?branch={branch}")

    assert response.status_code == 200
    assert [kind["name"] for kind in response.json()] == names


def test_list_filtered_by_country(admin_client, user_kind):
    response = admin_client.get(f"{KINDS}?country={user_kind.country_id}")

    assert response.status_code == 200
    assert [kind["id"] for kind in response.json()] == [user_kind.id]


def test_list_filtered_by_country_and_branch(admin_client, user_kind):
    response = admin_client.get(f"{KINDS}?country=1&branch=executive")

    assert response.status_code == 200
    assert [kind["name"] for kind in response.json()] == ["government"]


def test_list_filtered_by_unknown_country_empty(admin_client):
    response = admin_client.get(f"{KINDS}?country=0")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize(
    "query, errors",
    [
        ("branch=military", {"branch": ['"military" is not a valid choice.']}),
        ("country=Testland", {"country": ["A valid integer is required."]}),
    ],
)
def test_list_invalid_filter_400(admin_client, query, errors):
    response = admin_client.get(f"{KINDS}?{query}")

    assert response.status_code == 400
    assert response.json() == errors


@pytest.mark.parametrize(
    "method, url",
    [
        ("get", KINDS),
        ("post", KINDS),
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
    response = client.get(KINDS)

    assert response.json() == {
        "detail": "Authentication credentials were not provided."
    }


def test_list_without_permissions_shows_own_kinds(user_client, user_kind):
    response = user_client.get(KINDS)

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": user_kind.id,
            "name": "cabinet",
            "country": user_kind.country_id,
            "branch": "executive",
            "institutions": [],
        }
    ]


def test_list_filtered_by_other_users_country_empty(user_client, user_kind):
    response = user_client.get(f"{KINDS}?country=1")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize("method", ["get", "head"])
def test_get_by_id_without_permissions_success(user_client, user_kind, method):
    response = getattr(user_client, method)(kind_url(user_kind))

    assert response.status_code == 200


def test_create_without_permissions_forbidden(user_client, userland):
    response = user_client.post(KINDS, senate_body(userland.id), content_type=JSON)

    assert response.status_code == 403
    assert response.json() == NOT_PERMITTED


def test_update_without_permissions_forbidden(user_client, user_kind):
    response = user_client.put(
        kind_url(user_kind),
        {"name": "Renamed", "country": user_kind.country_id, "branch": "executive"},
        content_type=JSON,
    )

    assert response.status_code == 403
    assert response.json() == NOT_PERMITTED


def test_delete_without_permissions_forbidden(user_client, user_kind):
    response = user_client.delete(kind_url(user_kind))

    assert response.status_code == 403
    assert response.json() == NOT_PERMITTED
    assert InstitutionKind.objects.filter(pk=user_kind.pk).exists()


@pytest.mark.parametrize("user_client", [["add_institutionkind"]], indirect=True)
def test_create_with_add_permission_success(user_client, userland):
    response = user_client.post(KINDS, senate_body(userland.id), content_type=JSON)

    assert response.status_code == 201


@pytest.mark.parametrize("user_client", [["add_institutionkind"]], indirect=True)
def test_delete_with_only_add_permission_forbidden(user_client, user_kind):
    response = user_client.delete(kind_url(user_kind))

    assert response.status_code == 403


@pytest.mark.parametrize("user_client", [["change_institutionkind"]], indirect=True)
def test_update_with_change_permission_success(user_client, user_kind):
    response = user_client.put(
        kind_url(user_kind),
        {"name": "Renamed", "country": user_kind.country_id, "branch": "executive"},
        content_type=JSON,
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Renamed"


@pytest.mark.parametrize("user_client", [["delete_institutionkind"]], indirect=True)
def test_delete_with_delete_permission_success(user_client, user_kind):
    response = user_client.delete(kind_url(user_kind))

    assert response.status_code == 204


@pytest.mark.parametrize(
    "user_client, institutions, status",
    [
        (["add_institutionkind"], [], 201),
        (["add_institutionkind"], [institution("Senate")], 403),
        (["add_institution"], [], 403),
        (["add_institution"], [institution("Senate")], 403),
        (["add_institutionkind", "add_institution"], [institution("Senate")], 201),
    ],
    indirect=["user_client"],
)
def test_create_with_institutions_requires_both_add_permissions(
    user_client, userland, institutions, status
):
    response = user_client.post(
        KINDS, senate_body(userland.id, institutions=institutions), content_type=JSON
    )

    assert response.status_code == status
    created = InstitutionKind.objects.filter(institution_name="senate").exists()
    assert created == (status == 201)


@pytest.mark.parametrize("user_client", [["add_institutionkind"]], indirect=True)
def test_create_with_institutions_without_add_institution_forbidden(
    user_client, userland
):
    response = user_client.post(
        KINDS,
        senate_body(userland.id, institutions=[institution("Senate")]),
        content_type=JSON,
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Creating institutions also requires the permission to add "
        "institutions."
    }
    assert_senate_not_created()


@pytest.mark.parametrize(
    "user_client",
    [["add_institutionkind", "change_institutionkind", "delete_institutionkind"]],
    indirect=True,
)
@pytest.mark.parametrize("method", ["get", "head", "put", "delete"])
def test_other_users_kind_404(user_client, method):
    response = getattr(user_client, method)(GOVERNMENT)

    assert response.status_code == 404
    assert InstitutionKind.objects.get(pk=1).institution_name == "government"


@pytest.mark.parametrize("user_client", [["add_institutionkind"]], indirect=True)
def test_create_in_other_users_country_400(user_client):
    response = user_client.post(KINDS, senate_body(), content_type=JSON)

    assert response.status_code == 400
    assert response.json() == {"country": ['Invalid pk "1" - object does not exist.']}
    assert_senate_not_created()


@pytest.mark.parametrize(
    "user_client", [["add_institutionkind", "add_institution"]], indirect=True
)
def test_create_on_other_users_timeline_400(user_client, userland):
    senate = institution("Senate", {"timelines": [1]})

    response = user_client.post(
        KINDS, senate_body(userland.id, institutions=[senate]), content_type=JSON
    )

    assert response.status_code == 400
    assert response.json() == {
        "institutions": [
            {
                "time_frames": [
                    {"timelines": ['Invalid pk "1" - object does not exist.']}
                ]
            }
        ]
    }
    assert_senate_not_created()


def test_superuser_lists_kinds_of_all_users(admin_client, user_kind):
    response = admin_client.get(KINDS)

    assert response.status_code == 200
    assert [kind["name"] for kind in response.json()] == [
        "government",
        "parliament",
        "court",
        "cabinet",
    ]


@pytest.mark.parametrize("method", ["get", "head"])
def test_superuser_gets_other_users_kind(admin_client, user_kind, method):
    response = getattr(admin_client, method)(kind_url(user_kind))

    assert response.status_code == 200


def test_superuser_creates_in_other_users_country(admin_client, userland):
    response = admin_client.post(KINDS, senate_body(userland.id), content_type=JSON)

    assert response.status_code == 201
    kind = InstitutionKind.objects.get(institution_name="senate")
    assert kind.country_id == userland.id


def test_superuser_updates_other_users_kind(admin_client, user_kind):
    response = admin_client.put(
        kind_url(user_kind),
        {"name": "Renamed", "country": user_kind.country_id, "branch": "executive"},
        content_type=JSON,
    )

    assert response.status_code == 200
    assert InstitutionKind.objects.get(pk=user_kind.pk).institution_name == "Renamed"


def test_superuser_deletes_other_users_kind(admin_client, user_kind):
    response = admin_client.delete(kind_url(user_kind))

    assert response.status_code == 204
    assert not InstitutionKind.objects.filter(pk=user_kind.pk).exists()


def test_create_duplicate_name_400(admin_client):
    response = admin_client.post(KINDS, government_body(), content_type=JSON)

    assert response.status_code == 400
    assert response.json() == {
        "non_field_errors": [
            "An institution kind with this name already exists in this country."
        ]
    }


def test_create_same_name_in_other_country_success(admin_client, userland):
    response = admin_client.post(
        KINDS, government_body(country=userland.id), content_type=JSON
    )

    assert response.status_code == 201


def test_create_with_institutions_success(admin_client):
    institutions = [
        institution(
            "Senate 2016",
            {"validFrom": "2016-12-21T00:00:00Z", "validTo": "2020-12-21T00:00:00Z"},
        ),
        institution(
            "Senate 2020", {"validFrom": "2020-12-21T00:00:00Z", "timelines": [1]}
        ),
    ]

    response = admin_client.post(
        KINDS, senate_body(institutions=institutions), content_type=JSON
    )

    assert response.status_code == 201
    kind = InstitutionKind.objects.get(institution_name="senate")
    first, second = kind.institutions.order_by("id")
    default_payload = {
        "majority_probability_for": None,
        "opposition_probability_for": None,
    }
    assert response.json() == {
        "id": kind.id,
        "name": "senate",
        "country": 1,
        "branch": "legislative",
        "institutions": [
            {
                "id": first.id,
                "label": "Senate 2016",
                "size": 136,
                "payload": default_payload,
                "timeFrames": [
                    {
                        "validFrom": "2016-12-21T00:00:00Z",
                        "validTo": "2020-12-21T00:00:00Z",
                        "timelines": [],
                    }
                ],
            },
            {
                "id": second.id,
                "label": "Senate 2020",
                "size": 136,
                "payload": default_payload,
                "timeFrames": [
                    {
                        "validFrom": "2020-12-21T00:00:00Z",
                        "validTo": None,
                        "timelines": [1],
                    }
                ],
            },
        ],
    }
    assert TimeFrame.objects.count() == 2


@pytest.mark.parametrize(
    "senate",
    [institution("Senate"), {"label": "Senate", "size": 136}],
    ids=["empty-time-frames", "without-time-frames"],
)
def test_create_with_frameless_institution_success(admin_client, senate):
    response = admin_client.post(
        KINDS, senate_body(institutions=[senate]), content_type=JSON
    )

    assert response.status_code == 201
    assert response.json()["institutions"][0]["timeFrames"] == []
    assert not TimeFrame.objects.exists()


def test_create_with_overlapping_institutions_400(admin_client):
    institutions = [
        institution(
            "Senate 2016",
            {"validFrom": "2016-12-21T00:00:00Z", "validTo": "2020-12-21T00:00:00Z"},
        ),
        institution("Senate 2019", {"validFrom": "2019-01-01T00:00:00Z"}),
    ]

    response = admin_client.post(
        KINDS, senate_body(institutions=institutions), content_type=JSON
    )

    assert response.status_code == 400
    assert response.json() == {
        "institutions": {
            "1": {
                "time_frames": {
                    "0": [
                        "Overlaps with 'Senate 2016' [2016-12-21, 2020-12-21) on all timelines."
                    ]
                }
            }
        }
    }
    assert_senate_not_created()


@pytest.mark.parametrize(
    "institutions",
    [
        [
            institution("Senate 2020", {"validFrom": "2020-12-21T00:00:00Z"}),
            institution("Senate"),
        ],
        [
            institution("Senate"),
            institution("Senate 2020", {"validFrom": "2020-12-21T00:00:00Z"}),
        ],
    ],
    ids=["frameless-last", "frameless-first"],
)
def test_create_frameless_institution_with_siblings_400(admin_client, institutions):
    response = admin_client.post(
        KINDS, senate_body(institutions=institutions), content_type=JSON
    )

    assert response.status_code == 400
    assert list(response.json()["institutions"]) == ["1"]
    assert_senate_not_created()


def test_create_institution_with_invalid_payload_400(admin_client):
    cabinet = institution("Senate", payload={"connectivity_degree": 0})

    response = admin_client.post(
        KINDS,
        senate_body(branch="executive", institutions=[cabinet]),
        content_type=JSON,
    )

    assert response.status_code == 400
    assert response.json() == {
        "institutions": {
            "0": {
                "payload": [
                    "connectivity_degree: Input should be greater than or equal to 1"
                ]
            }
        }
    }
    assert_senate_not_created()


def test_create_institutions_with_duplicate_label_400(admin_client):
    institutions = [
        institution(
            "Senate",
            {"validFrom": "2016-12-21T00:00:00Z", "validTo": "2020-12-21T00:00:00Z"},
        ),
        institution("Senate", {"validFrom": "2020-12-21T00:00:00Z"}),
    ]

    response = admin_client.post(
        KINDS, senate_body(institutions=institutions), content_type=JSON
    )

    assert response.status_code == 400
    assert list(response.json()["institutions"]) == ["1"]
    assert_senate_not_created()


def test_create_time_frame_ending_before_start_400(admin_client):
    reversed_frame = {
        "validFrom": "2020-12-21T00:00:00Z",
        "validTo": "2016-12-21T00:00:00Z",
    }

    response = admin_client.post(
        KINDS,
        senate_body(institutions=[institution("Senate", reversed_frame)]),
        content_type=JSON,
    )

    assert response.status_code == 400
    assert list(response.json()["institutions"]["0"]["time_frames"]) == ["0"]
    assert_senate_not_created()


def test_create_on_timeline_of_other_settings_400(admin_client, test_user_settings):
    timeline = VirtualTimeline.objects.get(user_settings=test_user_settings)
    senate = institution("Senate", {"timelines": [timeline.id]})

    response = admin_client.post(
        KINDS, senate_body(institutions=[senate]), content_type=JSON
    )

    assert response.status_code == 400
    assert response.json() == {
        "institutions": {
            "0": {
                "time_frames": {
                    "0": [
                        "The timelines must belong to the same global context as "
                        "the time frame's subject."
                    ]
                }
            }
        }
    }
    assert_senate_not_created()


def test_update_branch_400(admin_client):
    response = admin_client.put(
        GOVERNMENT, government_body(branch="judiciary"), content_type=JSON
    )

    assert response.status_code == 400
    assert response.json() == {
        "branch": ["The branch of an institution kind cannot be changed."]
    }
    assert InstitutionKind.objects.get(pk=1).branch == "executive"


def test_update_move_to_other_country_400(admin_client, userland):
    response = admin_client.put(
        GOVERNMENT, government_body(country=userland.id), content_type=JSON
    )

    assert response.status_code == 400
    assert response.json() == {
        "country": ["An institution kind cannot be moved to another country."]
    }
    assert InstitutionKind.objects.get(pk=1).country_id == 1


def test_update_with_institutions_400(admin_client):
    response = admin_client.put(
        GOVERNMENT, government_body(institutions=[]), content_type=JSON
    )

    assert response.status_code == 400
    assert response.json() == {
        "institutions": ["Institutions can only be created together with their kind."]
    }


def test_update_duplicate_name_400(admin_client):
    response = admin_client.put(
        GOVERNMENT, government_body(name="parliament"), content_type=JSON
    )

    assert response.status_code == 400
    assert response.json() == {
        "non_field_errors": [
            "An institution kind with this name already exists in this country."
        ]
    }
    assert InstitutionKind.objects.get(pk=1).institution_name == "government"


def test_delete_deletes_institutions_and_time_frames(admin_client, framed_senate):
    response = admin_client.delete(kind_url(framed_senate))

    assert response.status_code == 204
    assert not Institution.objects.filter(kind_id=framed_senate.id).exists()
    assert not TimeFrame.objects.exists()


@pytest.mark.parametrize("status", Simulation.Status.values)
def test_delete_simulated_kind_409(admin_client, legislative_log_simulation, status):
    Simulation.objects.filter(pk=legislative_log_simulation.pk).update(status=status)

    response = admin_client.delete(GOVERNMENT)

    assert response.status_code == 409
    assert response.json() == {
        "detail": "The institution kind has institutions used in simulations and "
        "cannot be deleted."
    }
    assert InstitutionKind.objects.filter(pk=1).exists()
    assert Institution.objects.filter(pk=1).exists()
