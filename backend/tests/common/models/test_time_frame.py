from datetime import datetime, UTC

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from common.models import (
    PartyPosition,
    PartyPositionType,
    TimeFrame,
    TimeFrameSubjectType,
    TimelineTimeFrame,
    UserSettings,
    VirtualTimeline,
)


def _dt(year: int, month: int = 1, day: int = 1) -> datetime:
    return datetime(year, month, day, tzinfo=UTC)


@pytest.fixture
def default_timeline(test_settings) -> VirtualTimeline:
    return test_settings.timelines.get(label="default")


@pytest.fixture
def alternate_timeline(test_settings) -> VirtualTimeline:
    return VirtualTimeline.objects.create(
        user_settings=test_settings, label="alternate"
    )


@pytest.fixture
def majority_position(renaissance, assemblee) -> PartyPosition:
    return PartyPosition.objects.create(
        party=renaissance, chamber=assemblee, position=PartyPositionType.MAJORITY
    )


# --- soft foreign key -----------------------------------------------------------


@pytest.mark.django_db
def test_create_for_institution(cabinet):
    frame = TimeFrame.objects.create_for(
        cabinet, valid_from=_dt(2020, 7, 3), valid_to=_dt(2022, 5, 16)
    )

    assert frame.subject_type == TimeFrameSubjectType.INSTITUTION
    assert frame.subject_id == cabinet.id
    assert frame.subject == cabinet
    assert list(TimeFrame.objects.of(cabinet)) == [frame]


@pytest.mark.django_db
def test_create_for_party_position(majority_position):
    frame = TimeFrame.objects.create_for(majority_position, valid_from=_dt(2022))

    assert frame.subject_type == TimeFrameSubjectType.PARTY_POSITION
    assert frame.subject == majority_position
    assert list(TimeFrame.objects.of(majority_position)) == [frame]


@pytest.mark.django_db
def test_create_for_unsupported_subject(renaissance):
    with pytest.raises(TypeError) as err_proxy:
        TimeFrame.objects.create_for(renaissance)

    assert str(err_proxy.value) == "Party cannot occupy a time frame"


@pytest.mark.django_db
def test_subjects_with_same_id_are_kept_apart(cabinet, renaissance, assemblee):
    # same primary key in two different tables
    position = PartyPosition.objects.create(
        id=cabinet.id,
        party=renaissance,
        chamber=assemblee,
        position=PartyPositionType.MAJORITY,
    )
    cabinet_frame = TimeFrame.objects.create_for(cabinet)
    position_frame = TimeFrame.objects.create_for(position)

    assert list(TimeFrame.objects.of(cabinet)) == [cabinet_frame]
    assert list(TimeFrame.objects.of(position)) == [position_frame]

    cabinet.delete()

    assert list(TimeFrame.objects.all()) == [position_frame]


@pytest.mark.django_db
def test_dangling_subject_is_none_and_rejected_by_validation(cabinet):
    frame = TimeFrame(subject_type=TimeFrameSubjectType.INSTITUTION, subject_id=9999)

    assert frame.subject is None
    with pytest.raises(ValidationError) as err_proxy:
        frame.full_clean()
    assert err_proxy.value.message_dict == {
        "subject_id": ["There is no institution with id 9999."]
    }


@pytest.mark.django_db
def test_subject_type_rejected_by_database(cabinet):
    with pytest.raises(IntegrityError) as err_proxy:
        with transaction.atomic():
            TimeFrame.objects.create(subject_type="party", subject_id=cabinet.id)

    assert str(err_proxy.value) == "CHECK constraint failed: ck_timeframe_subject_type"


# --- interval bounds ------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "valid_from,valid_to",
    [
        (_dt(2017, 5, 15), _dt(2017, 6, 21)),
        (None, _dt(2017, 6, 21)),
        (_dt(2017, 5, 15), None),
        (None, None),
    ],
    ids=["bounded", "open start", "open end", "unbounded"],
)
def test_bounded_and_open_ended_frames(cabinet, valid_from, valid_to):
    frame = TimeFrame.objects.create_for(
        cabinet, valid_from=valid_from, valid_to=valid_to
    )

    frame.full_clean()

    assert frame.pk is not None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "valid_from,valid_to",
    [(_dt(2022), _dt(2020)), (_dt(2020), _dt(2020))],
    ids=["reversed", "empty"],
)
def test_valid_from_must_precede_valid_to(cabinet, valid_from, valid_to):
    with pytest.raises(IntegrityError) as err_proxy:
        with transaction.atomic():
            TimeFrame.objects.create_for(
                cabinet, valid_from=valid_from, valid_to=valid_to
            )

    assert str(err_proxy.value) == (
        "CHECK constraint failed: ck_timeframe_valid_from_before_valid_to"
    )


# --- timeline association -------------------------------------------------------


@pytest.mark.django_db
def test_frame_without_links_applies_to_all_timelines(
    cabinet, default_timeline, alternate_timeline
):
    frame = TimeFrame.objects.create_for(cabinet)

    assert frame.applies_to_all_timelines
    assert set(frame.get_timelines()) == {default_timeline, alternate_timeline}


@pytest.mark.django_db
def test_frame_for_all_timelines_tracks_added_timelines(
    test_settings, cabinet, default_timeline
):
    frame = TimeFrame.objects.create_for(cabinet)

    added = VirtualTimeline.objects.create(user_settings=test_settings, label="new")

    assert set(frame.get_timelines()) == {default_timeline, added}


@pytest.mark.django_db
def test_frame_with_links_applies_to_linked_timelines_only(
    cabinet, default_timeline, alternate_timeline
):
    frame = TimeFrame.objects.create_for(cabinet)
    frame.timelines.add(alternate_timeline)

    assert not frame.applies_to_all_timelines
    assert list(frame.get_timelines()) == [alternate_timeline]


@pytest.mark.django_db
def test_frame_for_all_timelines_excludes_other_contexts(test_settings, cabinet):
    other_settings = UserSettings.objects.create(
        user=test_settings.user, label="alternate world"
    )
    frame = TimeFrame.objects.create_for(cabinet)

    assert other_settings.timelines.get() not in frame.get_timelines()


@pytest.mark.django_db
def test_timeline_link_is_unique(cabinet, default_timeline):
    frame = TimeFrame.objects.create_for(cabinet)
    TimelineTimeFrame.objects.create(
        time_frame=frame, virtual_timeline=default_timeline
    )

    with pytest.raises(IntegrityError) as err_proxy:
        with transaction.atomic():
            TimelineTimeFrame.objects.create(
                time_frame=frame, virtual_timeline=default_timeline
            )

    assert str(err_proxy.value) == (
        "UNIQUE constraint failed: common_timelinetimeframe.time_frame_id, "
        "common_timelinetimeframe.virtual_timeline_id"
    )


@pytest.mark.django_db
def test_timeline_must_belong_to_subject_context(test_settings, cabinet):
    other_settings = UserSettings.objects.create(
        user=test_settings.user, label="alternate world"
    )
    frame = TimeFrame.objects.create_for(cabinet)
    link = TimelineTimeFrame(
        time_frame=frame, virtual_timeline=other_settings.timelines.get()
    )

    with pytest.raises(ValidationError) as err_proxy:
        link.full_clean()

    assert err_proxy.value.message_dict == {
        "virtual_timeline": [
            "The timeline must belong to the same global context "
            "as the time frame's subject."
        ]
    }


# --- cleanup --------------------------------------------------------------------


@pytest.mark.django_db
def test_deleting_institution_deletes_its_frames(cabinet, default_timeline):
    frame = TimeFrame.objects.create_for(cabinet)
    frame.timelines.add(default_timeline)

    cabinet.delete()

    assert not TimeFrame.objects.exists()
    assert not TimelineTimeFrame.objects.exists()


@pytest.mark.django_db
def test_deleting_party_position_deletes_its_frames(majority_position):
    TimeFrame.objects.create_for(majority_position)

    majority_position.delete()

    assert not TimeFrame.objects.exists()


@pytest.mark.django_db
def test_cascading_country_delete_deletes_frames(france, cabinet, majority_position):
    TimeFrame.objects.create_for(cabinet)
    TimeFrame.objects.create_for(majority_position)

    france.delete()

    assert not TimeFrame.objects.exists()


@pytest.mark.django_db
def test_deleting_only_timeline_of_frame_deletes_frame(cabinet, alternate_timeline):
    frame = TimeFrame.objects.create_for(cabinet)
    frame.timelines.add(alternate_timeline)

    alternate_timeline.delete()

    # without the cleanup, the frame would now apply to all timelines
    assert not TimeFrame.objects.exists()


@pytest.mark.django_db
def test_deleting_one_of_several_timelines_keeps_frame(
    cabinet, default_timeline, alternate_timeline
):
    frame = TimeFrame.objects.create_for(cabinet)
    frame.timelines.add(default_timeline, alternate_timeline)

    alternate_timeline.delete()

    assert list(frame.get_timelines()) == [default_timeline]


@pytest.mark.django_db
def test_deleting_timeline_keeps_frames_for_all_timelines(
    cabinet, default_timeline, alternate_timeline
):
    frame = TimeFrame.objects.create_for(cabinet)

    alternate_timeline.delete()

    assert frame.applies_to_all_timelines
    assert list(frame.get_timelines()) == [default_timeline]


@pytest.mark.django_db
def test_deleting_settings_deletes_frames(test_settings, cabinet, alternate_timeline):
    frame = TimeFrame.objects.create_for(cabinet)
    frame.timelines.add(alternate_timeline)
    TimeFrame.objects.create_for(cabinet)

    test_settings.delete()

    assert not TimeFrame.objects.exists()
