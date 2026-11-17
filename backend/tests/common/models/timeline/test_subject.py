from datetime import datetime, UTC

import pytest
from django.core.exceptions import ValidationError

from common.models import UserSettings

from .stub_app.models import StubSubject, StubTimeFrame


pytestmark = pytest.mark.django_db


def _dt(year: int, month: int = 1, day: int = 1) -> datetime:
    return datetime(year, month, day, tzinfo=UTC)


def test_sibling_axes_come_from_the_subject_declaration(make_stub_subject):
    subject = make_stub_subject("subject", group="a")
    same_group = make_stub_subject("same", group="a")
    other_group = make_stub_subject("other", group="b")

    assert set(subject.siblings()) == {same_group}
    assert other_group not in subject.siblings()


@pytest.mark.parametrize("sibling_has_frame", [False, True])
def test_frameless_sibling(make_stub_subject, sibling_has_frame):
    sibling = make_stub_subject("sibling")
    if sibling_has_frame:
        StubTimeFrame.objects.occupy(sibling, _dt(2020), _dt(2022))
    subject = make_stub_subject("subject")

    assert subject.frameless_sibling() == (None if sibling_has_frame else sibling)


def test_sibling_overlap_is_rejected(
    make_stub_subject, default_timeline, alternate_timeline
):
    second = make_stub_subject("second")
    StubTimeFrame.objects.occupy(second, _dt(2030), _dt(2031), [default_timeline])
    first = make_stub_subject("first")
    StubTimeFrame.objects.occupy(first, _dt(2020), _dt(2022), [alternate_timeline])

    with pytest.raises(ValidationError) as err_proxy:
        StubTimeFrame.objects.occupy(second, _dt(2021), _dt(2023), [alternate_timeline])

    assert err_proxy.value.messages == [
        "Overlaps with 'first' [2020-01-01, 2022-01-01) " "on timeline 'alternate'."
    ]


def test_blank_pending_timelines_validate_as_all_timelines(
    make_stub_subject, alternate_timeline
):
    first = make_stub_subject("first")
    StubTimeFrame.objects.occupy(first, _dt(2020), _dt(2022), [alternate_timeline])
    second = make_stub_subject("second")
    frame = StubTimeFrame(subject=second, valid_from=_dt(2021), valid_to=_dt(2023))
    frame.pending_timeline_ids = []

    with pytest.raises(ValidationError):
        frame.full_clean()


def test_timeline_must_belong_to_subject_country_context(stub_subject):
    other_settings = UserSettings.objects.create(
        user=stub_subject.country.user_settings.user, label="alternate world"
    )

    with pytest.raises(ValidationError) as err_proxy:
        StubTimeFrame.objects.occupy(
            stub_subject, timelines=[other_settings.timelines.get()]
        )

    assert err_proxy.value.messages == [
        "The timelines must belong to the same global context as the "
        "time frame's subject."
    ]


def test_frameless_subject_is_active(stub_subject, default_timeline):
    assert stub_subject.is_active(default_timeline, _dt(1900))
    assert stub_subject.is_active(default_timeline, _dt(2100))


def test_subject_activity_respects_interval_and_timeline(
    stub_subject, default_timeline, alternate_timeline
):
    frame = StubTimeFrame.objects.occupy(stub_subject, _dt(2020), _dt(2022))
    frame.timelines.add(default_timeline)

    assert not stub_subject.is_active(default_timeline, _dt(2019))
    assert stub_subject.is_active(default_timeline, _dt(2021))
    assert not stub_subject.is_active(default_timeline, _dt(2022))
    assert not stub_subject.is_active(alternate_timeline, _dt(2021))


def test_subject_queryset_active_on(make_stub_subject, default_timeline):
    active = make_stub_subject("active")
    StubTimeFrame.objects.occupy(active, _dt(2020), _dt(2022))
    inactive = make_stub_subject("inactive")
    StubTimeFrame.objects.occupy(inactive, _dt(2030), _dt(2031))
    frameless = make_stub_subject("frameless")

    assert set(StubSubject.objects.active_on(default_timeline, _dt(2021))) == {
        active,
        frameless,
    }
    assert inactive not in StubSubject.objects.active_on(default_timeline, _dt(2021))


def test_is_active_uses_one_joined_query(
    stub_subject, default_timeline, django_assert_num_queries
):
    StubTimeFrame.objects.create_for(stub_subject, valid_from=_dt(2020))

    with django_assert_num_queries(1):
        assert stub_subject.is_active(default_timeline, _dt(2021))
