import pytest
from django.core.exceptions import ValidationError

from .stub_app.models import StubSubject, StubTimeFrame


pytestmark = pytest.mark.django_db


def test_sibling_axes_come_from_the_subject_declaration(make_stub_subject):
    subject = make_stub_subject("subject", group="a")
    same_group = make_stub_subject("same", group="a")
    other_group = make_stub_subject("other", group="b")

    assert set(subject.siblings()) == {same_group}
    assert other_group not in subject.siblings()


@pytest.mark.parametrize("sibling_has_frame", [False, True])
def test_frameless_sibling(dt, make_stub_subject, sibling_has_frame):
    sibling = make_stub_subject("sibling")
    if sibling_has_frame:
        StubTimeFrame.objects.occupy(sibling, dt(2020), dt(2022))
    subject = make_stub_subject("subject")

    assert subject.frameless_sibling() == (None if sibling_has_frame else sibling)


def test_sibling_overlap_is_rejected(
    dt, make_stub_subject, default_timeline, alternate_timeline
):
    second = make_stub_subject("second")
    StubTimeFrame.objects.occupy(second, dt(2030), dt(2031), [default_timeline])
    first = make_stub_subject("first")
    StubTimeFrame.objects.occupy(first, dt(2020), dt(2022), [alternate_timeline])

    with pytest.raises(ValidationError) as err_proxy:
        StubTimeFrame.objects.occupy(second, dt(2021), dt(2023), [alternate_timeline])

    assert err_proxy.value.messages == [
        "Overlaps with 'first' [2020-01-01 00:00:00+00:00, 2022-01-01 00:00:00+00:00) "
        "on timeline 'alternate'."
    ]


def test_blank_pending_timelines_validate_as_all_timelines(
    dt, make_stub_subject, alternate_timeline
):
    first = make_stub_subject("first")
    StubTimeFrame.objects.occupy(first, dt(2020), dt(2022), [alternate_timeline])
    second = make_stub_subject("second")
    frame = StubTimeFrame(subject=second, valid_from=dt(2021), valid_to=dt(2023))
    frame.pending_timelines = []

    with pytest.raises(ValidationError):
        frame.full_clean()


def test_frameless_subject_is_active(dt, stub_subject, default_timeline):
    assert stub_subject.is_active(default_timeline, dt(1900))
    assert stub_subject.is_active(default_timeline, dt(2100))


def test_subject_activity_respects_interval_and_timeline(
    dt, stub_subject, default_timeline, alternate_timeline
):
    frame = StubTimeFrame.objects.occupy(stub_subject, dt(2020), dt(2022))
    frame.timelines.add(default_timeline)

    assert not stub_subject.is_active(default_timeline, dt(2019))
    assert stub_subject.is_active(default_timeline, dt(2021))
    assert not stub_subject.is_active(default_timeline, dt(2022))
    assert not stub_subject.is_active(alternate_timeline, dt(2021))


def test_subject_queryset_active_on(dt, make_stub_subject, default_timeline):
    active = make_stub_subject("active")
    StubTimeFrame.objects.occupy(active, dt(2020), dt(2022))
    inactive = make_stub_subject("inactive")
    StubTimeFrame.objects.occupy(inactive, dt(2030), dt(2031))
    frameless = make_stub_subject("frameless")

    assert set(StubSubject.objects.active_on(default_timeline, dt(2021))) == {
        active,
        frameless,
    }
    assert inactive not in StubSubject.objects.active_on(default_timeline, dt(2021))


def test_is_active_uses_one_joined_query(
    dt, stub_subject, default_timeline, django_assert_num_queries
):
    StubTimeFrame.objects.create_for(stub_subject, valid_from=dt(2020))

    with django_assert_num_queries(1):
        assert stub_subject.is_active(default_timeline, dt(2021))


def test_most_recent_per_timeline_groups_by_timeline(
    dt, make_stub_subject, default_timeline, alternate_timeline
):
    make_stub_subject("frameless", group="b")
    everywhere = make_stub_subject("everywhere", group="a")
    on_default = make_stub_subject("on_default", group="c")
    on_alternate = make_stub_subject("on_alternate", group="d")
    StubTimeFrame.objects.occupy(everywhere, dt(2020), dt(2022))
    StubTimeFrame.objects.occupy(on_default, dt(2023), None, [default_timeline])
    StubTimeFrame.objects.occupy(on_alternate, dt(2024), None, [alternate_timeline])

    def timeline_of(subject) -> int | None:
        return next(
            (
                frame.timelines.values_list("id", flat=True).first()
                for frame in subject.time_frames.all()
            ),
            None,
        )

    ranked = StubSubject.objects.most_recent(per_timeline=True)
    assert {(s.label, timeline_of(s)) for s in ranked} == {
        ("frameless", None),
        ("everywhere", None),
        ("on_default", default_timeline.pk),
        ("on_alternate", alternate_timeline.pk),
    }


def test_most_recent_per_timeline_keeps_the_latest_within_each_timeline(
    dt, make_stub_subject, default_timeline, alternate_timeline
):
    subject_old_default = make_stub_subject("old", group="a")
    subject_new = make_stub_subject("new", group="c")
    subject_old_alternate = make_stub_subject("old-alt", group="b")
    StubTimeFrame.objects.occupy(
        subject_old_default, dt(2020), dt(2022), [default_timeline]
    )
    StubTimeFrame.objects.occupy(subject_new, dt(2023), dt(2025), [default_timeline])
    StubTimeFrame.objects.occupy(
        subject_old_alternate, dt(2026), None, [alternate_timeline]
    )

    ranked = StubSubject.objects.most_recent(per_timeline=True)
    assert {
        (s.label, frozenset(s.time_frames.values_list("timelines__id", flat=True)))
        for s in ranked
    } == {
        ("new", frozenset({default_timeline.pk})),
        ("old-alt", frozenset({alternate_timeline.pk})),
        ("old", frozenset({default_timeline.pk})),
    }


def test_most_recent_per_timeline_with_a_timeline_filter(
    dt, make_stub_subject, default_timeline, alternate_timeline
):
    subject = make_stub_subject("subject", group="a")
    everywhere = make_stub_subject("everywhere", group="b")
    on_alternate = make_stub_subject("on_alternate", group="c")
    StubTimeFrame.objects.occupy(everywhere, dt(2020), dt(2022))
    StubTimeFrame.objects.occupy(subject, dt(2023), None, [default_timeline])
    StubTimeFrame.objects.occupy(on_alternate, dt(2024), None, [alternate_timeline])

    ranked = StubSubject.objects.most_recent(default_timeline, per_timeline=True)
    assert {s.label for s in ranked} == {"everywhere", "subject"}


def test_most_recent_per_timeline_is_one_flat_query(
    dt, make_stub_subject, django_assert_num_queries
):
    for i in range(5):
        subject = make_stub_subject(f"subject {i}", group=f"group {i}")
        StubTimeFrame.objects.occupy(subject, dt(2020), dt(2022))

    with django_assert_num_queries(1):
        ranked = list(StubSubject.objects.most_recent(per_timeline=True))

    assert len(ranked) == 5
