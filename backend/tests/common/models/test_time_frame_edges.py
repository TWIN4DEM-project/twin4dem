from datetime import UTC, datetime

import pytest

from common.models import TimeFrame, TimeFrameSubjectType, TimelineTimeFrame
from common.models._timeframe import TimeFrameMixin, active_subjects


def make_mixin() -> TimeFrameMixin:
    return object.__new__(TimeFrameMixin)


def test_time_frame_siblings_guard_raises():
    with pytest.raises(NotImplementedError):
        make_mixin().time_frame_siblings()


def test_time_frame_label_guard_raises():
    with pytest.raises(NotImplementedError):
        make_mixin().time_frame_label()


def test_time_frame_user_settings_guard_raises():
    with pytest.raises(NotImplementedError):
        make_mixin().time_frame_user_settings_id()


def test_subject_of_unknown_type_is_none():
    frame = TimeFrame(subject_type="bogus", subject_id=1)

    assert frame.subject is None


def test_clean_of_unknown_subject_type_trivially_passes():
    frame = TimeFrame(subject_type="bogus", subject_id=1)

    frame.clean()


def test_timeline_link_of_unknown_subject_type_trivially_passes():
    frame = TimeFrame(subject_type="bogus", subject_id=1)
    link = TimelineTimeFrame(time_frame=frame, virtual_timeline_id=1)

    link.clean()


@pytest.mark.django_db
def test_get_timelines_of_a_vanished_subject_is_empty():
    frame = TimeFrame.objects.create(
        subject_type=TimeFrameSubjectType.INSTITUTION, subject_id=99999
    )

    assert not frame.get_timelines().exists()


def test_active_subjects_without_subjects_is_empty(default_timeline):
    now = datetime(2025, 1, 1, tzinfo=UTC)

    assert active_subjects([], default_timeline, now) == []
