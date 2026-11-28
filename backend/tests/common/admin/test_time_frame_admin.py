import json
from datetime import UTC, datetime

import pytest

from common.models import (
    InstitutionTimeFrame,
    PartyPosition,
    PartyPositionTimeFrame,
    PartyPositionType,
)

pytestmark = pytest.mark.urls("tests.common.admin.urls")

INSTITUTION_CHANGE_URL = "/admin/common/institution/{pk}/change/"
PARTY_CHANGE_URL = "/admin/common/party/{pk}/change/"


def _institution_form_data(cabinet, frames) -> dict:
    data = {
        "kind": cabinet.kind_id,
        "label": cabinet.label,
        "size": cabinet.size,
        "payload": json.dumps(cabinet.payload),
        "time_frames-TOTAL_FORMS": str(len(frames)),
        "time_frames-INITIAL_FORMS": "0",
        "time_frames-MIN_NUM_FORMS": "0",
        "time_frames-MAX_NUM_FORMS": "1000",
    }
    for i, frame in enumerate(frames):
        if frame.get("valid_from") is not None:
            data[f"time_frames-{i}-valid_from_0"] = frame.get("valid_from")
            data[f"time_frames-{i}-valid_from_1"] = "00:00:00"
        if frame.get("valid_to") is not None:
            data[f"time_frames-{i}-valid_to_0"] = frame.get("valid_to")
            data[f"time_frames-{i}-valid_to_1"] = "00:00:00"
        data[f"time_frames-{i}-timeline_selection"] = [
            timeline.pk for timeline in frame.get("timelines", ())
        ]
    return data


def _party_form_data(party, positions) -> dict:
    data = {
        "country": party.country_id,
        "label": party.label,
        "positions-TOTAL_FORMS": str(len(positions)),
        "positions-INITIAL_FORMS": "0",
        "positions-MIN_NUM_FORMS": "0",
        "positions-MAX_NUM_FORMS": "1000",
    }
    for i, position in enumerate(positions):
        data[f"positions-{i}-position"] = position["position"]
        data[f"positions-{i}-chamber"] = position["chamber"].pk
        if position.get("valid_from") is not None:
            data[f"positions-{i}-valid_from"] = position.get("valid_from")
        if position.get("valid_to") is not None:
            data[f"positions-{i}-valid_to"] = position.get("valid_to")
        data[f"positions-{i}-timeline_selection"] = [
            timeline.pk for timeline in position.get("timelines", ())
        ]
    return data


@pytest.mark.django_db
def test_add_institution_frame_with_timelines(
    admin_client, cabinet, alternate_timeline
):
    response = admin_client.post(
        INSTITUTION_CHANGE_URL.format(pk=cabinet.pk),
        _institution_form_data(
            cabinet,
            [
                {
                    "valid_from": "2020-07-03",
                    "valid_to": "2022-05-16",
                    "timelines": [alternate_timeline],
                }
            ],
        ),
    )

    assert response.status_code == 302
    frame = InstitutionTimeFrame.objects.of(cabinet).get()
    assert list(frame.timelines.all()) == [alternate_timeline]


@pytest.mark.django_db
def test_add_institution_frame_without_timelines_applies_to_all(
    admin_client, cabinet, default_timeline, alternate_timeline
):
    response = admin_client.post(
        INSTITUTION_CHANGE_URL.format(pk=cabinet.pk),
        _institution_form_data(
            cabinet, [{"valid_from": "2020-07-03", "valid_to": "2022-05-16"}]
        ),
    )

    assert response.status_code == 302
    frame = InstitutionTimeFrame.objects.of(cabinet).get()
    assert frame.is_on_all_timelines
    assert set(frame.get_timelines()) == {default_timeline, alternate_timeline}


@pytest.mark.django_db
def test_add_overlapping_institution_frame_shows_error(
    admin_client, cabinet, alternate_timeline
):
    InstitutionTimeFrame.objects.occupy(
        cabinet, valid_from=datetime(2020, 7, 3, tzinfo=UTC)
    )

    response = admin_client.post(
        INSTITUTION_CHANGE_URL.format(pk=cabinet.pk),
        _institution_form_data(
            cabinet,
            [
                {
                    "valid_from": "2030-01-01",
                    "valid_to": "2031-01-01",
                    "timelines": [alternate_timeline],
                }
            ],
        ),
    )

    assert response.status_code == 200
    inline_formset = response.context["inline_admin_formsets"][0].formset
    assert inline_formset.forms[0].non_field_errors() == [
        "'Castex' already occupies the time frame [2020-07-03 00:00:00+00:00, +inf) on timeline 'alternate'."
    ]
    assert InstitutionTimeFrame.objects.count() == 1


@pytest.mark.django_db
def test_add_party_position_with_timeline(
    admin_client, renaissance, assemblee, alternate_timeline
):
    response = admin_client.post(
        PARTY_CHANGE_URL.format(pk=renaissance.pk),
        _party_form_data(
            renaissance,
            [
                {
                    "position": PartyPositionType.MAJORITY,
                    "chamber": assemblee,
                    "valid_from": "2020-07-03",
                    "valid_to": "2022-05-16",
                    "timelines": [alternate_timeline],
                }
            ],
        ),
    )

    assert response.status_code == 302
    position = renaissance.positions.get()
    frame = PartyPositionTimeFrame.objects.of(position).get()
    assert list(frame.timelines.all()) == [alternate_timeline]


@pytest.mark.django_db
def test_add_party_position_without_timeline_applies_to_all(
    admin_client, renaissance, assemblee, default_timeline, alternate_timeline
):
    response = admin_client.post(
        PARTY_CHANGE_URL.format(pk=renaissance.pk),
        _party_form_data(
            renaissance,
            [
                {
                    "position": PartyPositionType.MAJORITY,
                    "chamber": assemblee,
                    "valid_from": "2020-07-03",
                    "valid_to": "2022-05-16",
                }
            ],
        ),
    )

    assert response.status_code == 302
    position = renaissance.positions.get()
    frame = PartyPositionTimeFrame.objects.of(position).get()
    assert frame.is_on_all_timelines
    assert set(frame.get_timelines()) == {default_timeline, alternate_timeline}


@pytest.mark.django_db
def test_add_adjacent_party_positions_success(admin_client, renaissance, assemblee):
    response = admin_client.post(
        PARTY_CHANGE_URL.format(pk=renaissance.pk),
        _party_form_data(
            renaissance,
            [
                {
                    "position": PartyPositionType.MAJORITY,
                    "chamber": assemblee,
                    "valid_from": "2026-01-01",
                    "valid_to": "2026-02-15",
                },
                {
                    "position": PartyPositionType.OPPOSITION,
                    "chamber": assemblee,
                    "valid_from": "2026-02-15",
                },
            ],
        ),
    )

    assert response.status_code == 302
    frames = list(PartyPositionTimeFrame.objects.order_by("id"))
    assert frames[0].valid_to == frames[1].valid_from


@pytest.mark.django_db
def test_add_overlapping_party_positions_shows_error(
    admin_client, renaissance, assemblee
):
    response = admin_client.post(
        PARTY_CHANGE_URL.format(pk=renaissance.pk),
        _party_form_data(
            renaissance,
            [
                {
                    "position": PartyPositionType.MAJORITY,
                    "chamber": assemblee,
                    "valid_from": "2026-01-01",
                    "valid_to": "2026-02-15",
                },
                {
                    "position": PartyPositionType.OPPOSITION,
                    "chamber": assemblee,
                    "valid_from": "2026-02-01",
                    "valid_to": "2026-03-01",
                },
            ],
        ),
    )

    assert response.status_code == 200
    inline_formset = response.context["inline_admin_formsets"][0].formset
    assert inline_formset.forms[1].non_field_errors() == [
        "Overlaps with 'Renaissance' (majority) [2026-01-01 00:00:00+00:00, 2026-02-15 00:00:00+00:00) "
        "on all timelines."
    ]
    assert PartyPosition.objects.filter(party=renaissance).count() == 0
    assert PartyPositionTimeFrame.objects.count() == 0
