from datetime import datetime, UTC

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from common.models import VirtualTimeline

from .stub_app.models import StubTimeFrame


pytestmark = pytest.mark.django_db


def _dt(year: int, month: int = 1, day: int = 1) -> datetime:
    return datetime(year, month, day, tzinfo=UTC)


def test_create_for_links_a_real_subject(stub_subject):
    frame = StubTimeFrame.objects.create_for(
        stub_subject, valid_from=_dt(2020), valid_to=_dt(2022)
    )

    assert frame.subject == stub_subject
    assert list(stub_subject.time_frames.all()) == [frame]


def test_create_for_rejects_a_non_subject():
    with pytest.raises(TypeError) as err_proxy:
        StubTimeFrame.objects.create_for(object())

    assert str(err_proxy.value) == "object cannot occupy a time frame"


def test_deleting_the_subject_cascades_to_frames(stub_subject):
    StubTimeFrame.objects.create_for(stub_subject)

    stub_subject.delete()

    assert not StubTimeFrame.objects.exists()


@pytest.mark.parametrize(
    "valid_from,valid_to",
    [(_dt(2022), _dt(2020)), (_dt(2020), _dt(2020))],
    ids=["reversed", "empty"],
)
def test_valid_from_must_precede_valid_to(stub_subject, valid_from, valid_to):
    with pytest.raises(IntegrityError) as err_proxy:
        with transaction.atomic():
            StubTimeFrame.objects.create_for(
                stub_subject, valid_from=valid_from, valid_to=valid_to
            )

    assert "valid_from_before_valid_to" in str(err_proxy.value)


def test_clean_rejects_reversed_bounds(stub_subject):
    frame = StubTimeFrame(
        subject=stub_subject, valid_from=_dt(2022), valid_to=_dt(2020)
    )

    with pytest.raises(ValidationError) as err_proxy:
        frame.full_clean()

    assert err_proxy.value.message_dict == {
        "valid_to": ["The time frame must end after it starts."]
    }


def test_timeline_links_control_get_timelines(
    stub_subject, default_timeline, alternate_timeline
):
    frame = StubTimeFrame.objects.create_for(stub_subject)
    assert frame.is_on_all_timelines
    assert set(frame.get_timelines()) == {default_timeline, alternate_timeline}

    frame.timelines.add(alternate_timeline)

    assert not frame.is_on_all_timelines
    assert list(frame.get_timelines()) == [alternate_timeline]


def test_frame_for_all_timelines_tracks_added_timelines(stub_subject, default_timeline):
    frame = StubTimeFrame.objects.create_for(stub_subject)
    added = VirtualTimeline.objects.create(
        user_settings=stub_subject.country.user_settings, label="new"
    )

    assert set(frame.get_timelines()) == {default_timeline, added}


@pytest.mark.parametrize(
    "at,expected",
    [
        (_dt(2019), False),
        (_dt(2020), True),
        (_dt(2021, 12, 31), True),
        (_dt(2022), False),
    ],
    ids=["before", "first day", "last day", "end is excluded"],
)
def test_covering(stub_subject, at, expected):
    frame = StubTimeFrame.objects.create_for(
        stub_subject, valid_from=_dt(2020), valid_to=_dt(2022)
    )

    assert list(StubTimeFrame.objects.of(stub_subject).covering(at)) == (
        [frame] if expected else []
    )


def test_on_timeline_includes_unrestricted_and_linked_frames(
    stub_subject, default_timeline, alternate_timeline
):
    unrestricted = StubTimeFrame.objects.create_for(stub_subject, valid_from=_dt(2020))
    on_default = StubTimeFrame.objects.create_for(stub_subject, valid_from=_dt(2021))
    on_default.timelines.add(default_timeline)
    on_alternate = StubTimeFrame.objects.create_for(stub_subject, valid_from=_dt(2022))
    on_alternate.timelines.add(alternate_timeline)

    assert set(StubTimeFrame.objects.on_timeline(default_timeline)) == {
        unrestricted,
        on_default,
    }
    assert set(StubTimeFrame.objects.on_timeline(alternate_timeline)) == {
        unrestricted,
        on_alternate,
    }


def test_active_on_combines_timeline_and_interval(
    stub_subject, default_timeline, alternate_timeline
):
    covering = StubTimeFrame.objects.create_for(
        stub_subject, valid_from=_dt(2020), valid_to=_dt(2022)
    )
    covering.timelines.add(default_timeline)
    StubTimeFrame.objects.create_for(
        stub_subject, valid_from=_dt(2030), valid_to=_dt(2031)
    )

    assert list(StubTimeFrame.objects.active_on(default_timeline, _dt(2021))) == [
        covering
    ]
    assert not StubTimeFrame.objects.active_on(alternate_timeline, _dt(2021)).exists()


def test_subject_occupies_one_frame_per_timeline(stub_subject, alternate_timeline):
    StubTimeFrame.objects.occupy(
        stub_subject, _dt(2020), _dt(2022), [alternate_timeline]
    )

    with pytest.raises(ValidationError) as err_proxy:
        StubTimeFrame.objects.occupy(
            stub_subject, _dt(2030), _dt(2031), [alternate_timeline]
        )

    assert err_proxy.value.messages == [
        "'stub' already occupies the time frame [2020-01-01 00:00:00+00:00, 2022-01-01 00:00:00+00:00) "
        "on timeline 'alternate'."
    ]


@pytest.mark.parametrize(
    "first,second,conflict",
    [
        ((_dt(2017), _dt(2018)), (_dt(2018), _dt(2019)), False),
        ((_dt(2017), _dt(2019)), (_dt(2018), _dt(2020)), True),
        ((_dt(2017), _dt(2020)), (_dt(2018), _dt(2019)), True),
        ((_dt(2017), _dt(2018)), (_dt(2019), _dt(2020)), False),
        ((None, _dt(2018)), (_dt(2017), _dt(2019)), True),
        ((None, _dt(2018)), (_dt(2018), None), False),
        ((_dt(2017), None), (_dt(2030), _dt(2031)), True),
        ((None, None), (_dt(2017), _dt(2018)), True),
    ],
    ids=[
        "adjacent",
        "overlapping",
        "contained",
        "disjoint",
        "open start overlapping",
        "open start adjacent to open end",
        "open end",
        "unbounded",
    ],
)
def test_siblings_conflict_only_when_their_intervals_intersect(
    make_stub_subject, first, second, conflict
):
    StubTimeFrame.objects.occupy(make_stub_subject("first"), *first)
    second_subject = make_stub_subject("second")

    if conflict:
        with pytest.raises(ValidationError, match="Overlaps with 'first'"):
            StubTimeFrame.objects.occupy(second_subject, *second)
    else:
        StubTimeFrame.objects.occupy(second_subject, *second)


@pytest.mark.parametrize(
    "first_timelines,second_timelines,conflict",
    [
        (("default",), ("alternate",), False),
        (("default",), ("default",), True),
        (("default",), (), True),
    ],
    ids=["disjoint", "shared", "shared with all timelines"],
)
def test_siblings_conflict_only_on_shared_timelines(
    make_stub_subject,
    default_timeline,
    alternate_timeline,
    first_timelines,
    second_timelines,
    conflict,
):
    timelines = {"default": default_timeline, "alternate": alternate_timeline}

    def select(labels):
        return [timelines[label] for label in labels]

    StubTimeFrame.objects.occupy(
        make_stub_subject("first"), _dt(2020), _dt(2022), select(first_timelines)
    )
    second_subject = make_stub_subject("second")

    if conflict:
        with pytest.raises(ValidationError, match="Overlaps with 'first'"):
            StubTimeFrame.objects.occupy(
                second_subject, _dt(2021), _dt(2023), select(second_timelines)
            )
    else:
        StubTimeFrame.objects.occupy(
            second_subject, _dt(2021), _dt(2023), select(second_timelines)
        )
