from datetime import datetime, UTC

import pytest

from common.models import FrameSpec


def _dt(year: int, month: int = 1, day: int = 1) -> datetime:
    return datetime(year, month, day, tzinfo=UTC)


@pytest.mark.parametrize(
    "a,b,expected",
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
def test_overlaps_in_time(a, b, expected):
    frame_a = FrameSpec(*a, timeline_ids=None)
    frame_b = FrameSpec(*b, timeline_ids=None)

    assert frame_a.overlaps_in_time(frame_b) is expected
    assert frame_b.overlaps_in_time(frame_a) is expected


@pytest.mark.parametrize(
    "a,b,expected_shared",
    [
        (None, None, None),
        (None, frozenset({1}), frozenset({1})),
        (frozenset({1, 2}), frozenset({2, 3}), frozenset({2})),
        (frozenset({1}), frozenset({2}), frozenset()),
    ],
    ids=["all and all", "all and one", "intersecting", "disjoint"],
)
def test_shared_timelines(a, b, expected_shared):
    frame_a = FrameSpec(None, None, timeline_ids=a)
    frame_b = FrameSpec(None, None, timeline_ids=b)

    assert frame_a.shared_timelines(frame_b) == expected_shared
    assert frame_a.shares_timeline_with(frame_b) is (expected_shared != frozenset())
