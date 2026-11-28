import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction


from .stub_app.models import StubTimeFrame


pytestmark = pytest.mark.django_db


def test_create_for_links_a_real_subject(dt, stub_subject):
    frame = StubTimeFrame.objects.create_for(
        stub_subject, valid_from=dt(2020), valid_to=dt(2022)
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
    [((2022,), (2020,)), ((2020,), (2020,))],
    ids=["reversed", "empty"],
)
def test_valid_from_must_precede_valid_to(dt, stub_subject, valid_from, valid_to):
    with pytest.raises(IntegrityError) as err_proxy:
        with transaction.atomic():
            StubTimeFrame.objects.create_for(
                stub_subject, valid_from=dt(*valid_from), valid_to=dt(*valid_to)
            )

    assert "valid_from_before_valid_to" in str(err_proxy.value)


def test_clean_rejects_reversed_bounds(dt, stub_subject):
    frame = StubTimeFrame(subject=stub_subject, valid_from=dt(2022), valid_to=dt(2020))

    with pytest.raises(ValidationError) as err_proxy:
        frame.full_clean()

    assert err_proxy.value.message_dict == {
        "valid_to": ["The time frame must end after it starts."]
    }


def test_timeline_links_control_get_timelines(
    stub_subject, default_timeline, alternate_timeline
):
    frame = StubTimeFrame.objects.create_for(stub_subject)

    frame.timelines.add(alternate_timeline)

    assert not frame.is_on_all_timelines


@pytest.mark.parametrize(
    "at,expected",
    [((2019,), False), ((2020,), True), ((2021, 12, 31), True), ((2022,), False)],
    ids=["before", "first day", "last day", "end is excluded"],
)
def test_covering(dt, stub_subject, at, expected):
    at = dt(*at)
    frame = StubTimeFrame.objects.create_for(
        stub_subject, valid_from=dt(2020), valid_to=dt(2022)
    )

    assert list(StubTimeFrame.objects.of(stub_subject).covering(at)) == (
        [frame] if expected else []
    )


def test_on_timeline_includes_unrestricted_and_linked_frames(
    dt, stub_subject, default_timeline, alternate_timeline
):
    unrestricted = StubTimeFrame.objects.create_for(stub_subject, valid_from=dt(2020))
    on_default = StubTimeFrame.objects.create_for(stub_subject, valid_from=dt(2021))
    on_default.timelines.add(default_timeline)
    on_alternate = StubTimeFrame.objects.create_for(stub_subject, valid_from=dt(2022))
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
    dt, stub_subject, default_timeline, alternate_timeline
):
    covering = StubTimeFrame.objects.create_for(
        stub_subject, valid_from=dt(2020), valid_to=dt(2022)
    )
    covering.timelines.add(default_timeline)
    StubTimeFrame.objects.create_for(
        stub_subject, valid_from=dt(2030), valid_to=dt(2031)
    )

    assert list(StubTimeFrame.objects.active_on(default_timeline, dt(2021))) == [
        covering
    ]
    assert not StubTimeFrame.objects.active_on(alternate_timeline, dt(2021)).exists()


def test_subject_occupies_one_frame_per_timeline(dt, stub_subject, alternate_timeline):
    StubTimeFrame.objects.occupy(stub_subject, dt(2020), dt(2022), [alternate_timeline])

    with pytest.raises(ValidationError) as err_proxy:
        StubTimeFrame.objects.occupy(
            stub_subject, dt(2030), dt(2031), [alternate_timeline]
        )

    assert err_proxy.value.messages == [
        "'stub' already occupies the time frame [2020-01-01 00:00:00+00:00, 2022-01-01 00:00:00+00:00) "
        "on timeline 'alternate'."
    ]


@pytest.mark.parametrize(
    "first,second,conflict",
    [
        (((2017,), (2018,)), ((2018,), (2019,)), False),
        (((2017,), (2019,)), ((2018,), (2020,)), True),
        (((2017,), (2020,)), ((2018,), (2019,)), True),
        (((2017,), (2018,)), ((2019,), (2020,)), False),
        ((None, (2018,)), ((2017,), (2019,)), True),
        ((None, (2018,)), ((2018,), None), False),
        (((2017,), None), ((2030,), (2031,)), True),
        ((None, None), ((2017,), (2018,)), True),
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
    dt, make_stub_subject, first, second, conflict
):
    first = tuple(dt(*part) if part else None for part in first)
    second = tuple(dt(*part) if part else None for part in second)
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
    dt,
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
        make_stub_subject("first"), dt(2020), dt(2022), select(first_timelines)
    )
    second_subject = make_stub_subject("second")

    if conflict:
        with pytest.raises(ValidationError, match="Overlaps with 'first'"):
            StubTimeFrame.objects.occupy(
                second_subject, dt(2021), dt(2023), select(second_timelines)
            )
    else:
        StubTimeFrame.objects.occupy(
            second_subject, dt(2021), dt(2023), select(second_timelines)
        )
