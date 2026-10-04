from datetime import datetime, UTC

import pytest

from common.models import TimeFrame, TimeFrameSubjectType, VirtualTimeline

ADD_URL = "/admin/common/timeframe/add/"


@pytest.fixture
def alternate(test_settings) -> VirtualTimeline:
    return VirtualTimeline.objects.create(
        user_settings=test_settings, label="alternate"
    )


def _form_data(subject, valid_from: str, valid_to: str, timelines=()) -> dict:
    # the admin splits datetimes into a date and a time input
    return {
        "subject_type": TimeFrameSubjectType.INSTITUTION,
        "subject_id": subject.id,
        "valid_from_0": valid_from,
        "valid_from_1": "00:00:00",
        "valid_to_0": valid_to,
        "valid_to_1": "00:00:00",
        "timeline_selection": [t.id for t in timelines],
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url",
    [
        "/admin/common/usersettings/",
        "/admin/common/usersettings/1/change/",
        "/admin/common/country/",
        "/admin/common/country/add/",
        "/admin/common/institution/",
        "/admin/common/institution/add/",
        "/admin/common/party/",
        "/admin/common/party/add/",
        "/admin/common/timeframe/",
        ADD_URL,
    ],
)
def test_admin_pages_render(admin_client, url):
    response = admin_client.get(url)

    assert response.status_code == 200


@pytest.mark.django_db
def test_add_time_frame_with_timelines(admin_client, cabinet, alternate):
    response = admin_client.post(
        ADD_URL, _form_data(cabinet, "2020-07-03", "2022-05-16", [alternate])
    )

    assert response.status_code == 302
    frame = TimeFrame.objects.of(cabinet).get()
    assert frame.valid_from == datetime(2020, 7, 3, tzinfo=UTC)
    assert list(frame.timelines.all()) == [alternate]


@pytest.mark.django_db
def test_add_overlapping_time_frame_shows_error(admin_client, cabinet, alternate):
    TimeFrame.objects.occupy(cabinet, valid_from=datetime(2020, 7, 3, tzinfo=UTC))

    response = admin_client.post(
        ADD_URL, _form_data(cabinet, "2030-01-01", "2031-01-01", [alternate])
    )

    assert response.status_code == 200
    assert response.context["adminform"].form.non_field_errors() == [
        "'Castex' already occupies the time frame [2020-07-03, +inf) "
        "on timeline 'alternate'."
    ]
    assert TimeFrame.objects.count() == 1
