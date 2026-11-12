from datetime import UTC, datetime

import pytest

from api.serializers._party import PositionSummary, position_summaries
from common.models import (
    Institution,
    Party,
    PartyPosition,
    PartyPositionType,
    TimeFrame,
    VirtualTimeline,
    is_active,
)

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 6, 1, tzinfo=UTC)


def at(year: int) -> datetime:
    """The start of `year`, as stored in a time frame."""
    return datetime(year, 1, 1, tzinfo=UTC)


def position(
    party: Party,
    kind: PartyPositionType,
    chamber: Institution,
    *frames: tuple[datetime | None, datetime | None],
) -> PartyPosition:
    """A position with one time frame per (valid_from, valid_to), unvalidated."""
    party_position = PartyPosition.objects.create(
        party=party, chamber=chamber, position=kind
    )
    for valid_from, valid_to in frames:
        TimeFrame.objects.create_for(
            party_position, valid_from=valid_from, valid_to=valid_to
        )
    return party_position


def summary(party: Party, timeline: VirtualTimeline | None = None) -> PositionSummary:
    return position_summaries([party], NOW, timeline)[party.pk]


def on_timelines(
    party_position: PartyPosition,
    *timelines: VirtualTimeline,
    valid_from: datetime | None = at(2020),
    valid_to: datetime | None = None,
) -> None:
    """Add a validated time frame, restricted to the given timelines."""
    TimeFrame.objects.occupy(party_position, valid_from, valid_to, timelines)


@pytest.fixture
def psd() -> Party:
    return Party.objects.create(country_id=1, label="PSD")


@pytest.fixture
def parliament() -> Institution:
    return Institution.objects.get(pk=2)


@pytest.fixture
def senate(make_senate) -> Institution:
    return make_senate("Senate")


@pytest.fixture
def default_timeline(test_settings) -> VirtualTimeline:
    return test_settings.timelines.get(label=VirtualTimeline.DEFAULT_LABEL)


# latest position: the same as Party.latest_position


def test_open_ended_frame_beats_a_later_end(psd, parliament, senate):
    position(psd, PartyPositionType.MAJORITY, parliament, (at(2017), at(2099)))
    open_ended = position(psd, PartyPositionType.OPPOSITION, senate, (at(2017), None))

    assert summary(psd).latest == open_ended == psd.latest_position


def test_frameless_position_beats_a_framed_one(psd, parliament, senate):
    position(psd, PartyPositionType.MAJORITY, parliament, (at(2017), at(2099)))
    frameless = position(psd, PartyPositionType.OPPOSITION, senate)

    assert summary(psd).latest == frameless == psd.latest_position


def test_latest_end_wins(psd, parliament):
    position(psd, PartyPositionType.MAJORITY, parliament, (at(2017), at(2022)))
    newest = position(
        psd, PartyPositionType.OPPOSITION, parliament, (at(2022), at(2024))
    )

    assert summary(psd).latest == newest == psd.latest_position


def test_latest_tie_goes_to_the_highest_id(psd, parliament, senate):
    position(psd, PartyPositionType.MAJORITY, parliament, (at(2017), at(2024)))
    second = position(psd, PartyPositionType.OPPOSITION, senate, (at(2020), at(2024)))

    assert summary(psd).latest == second == psd.latest_position


def test_two_frameless_positions_rank_by_id(psd, parliament, senate):
    position(psd, PartyPositionType.MAJORITY, parliament)
    second = position(psd, PartyPositionType.OPPOSITION, senate)

    assert summary(psd).latest == second == psd.latest_position


def test_latest_counts_the_last_frame_of_a_position(psd, parliament, senate):
    returning = position(
        psd,
        PartyPositionType.MAJORITY,
        parliament,
        (at(2010), at(2012)),
        (at(2020), at(2030)),
    )
    position(psd, PartyPositionType.OPPOSITION, senate, (at(2015), at(2025)))

    assert summary(psd).latest == returning == psd.latest_position


def test_latest_ranks_an_open_frame_among_others_highest(psd, parliament, senate):
    reopened = position(
        psd,
        PartyPositionType.MAJORITY,
        parliament,
        (at(2010), at(2012)),
        (at(2020), None),
    )
    position(psd, PartyPositionType.OPPOSITION, senate, (at(2015), at(2099)))

    assert summary(psd).latest == reopened == psd.latest_position


def test_party_without_positions_has_neither(psd):
    assert summary(psd) == PositionSummary(latest=None, active=None)
    assert psd.latest_position is None


def test_active_is_the_current_one_not_the_planned_one(psd, parliament):
    current = position(
        psd, PartyPositionType.MAJORITY, parliament, (at(2020), at(2099))
    )
    planned = position(psd, PartyPositionType.OPPOSITION, parliament, (at(2099), None))

    assert summary(psd) == PositionSummary(latest=planned, active=current)
    assert psd.latest_position == planned


def test_no_active_position_when_all_have_ended(psd, parliament):
    ended = position(psd, PartyPositionType.MAJORITY, parliament, (at(2017), at(2022)))

    assert summary(psd) == PositionSummary(latest=ended, active=None)


def test_no_active_position_before_any_has_started(psd, parliament):
    planned = position(psd, PartyPositionType.OPPOSITION, parliament, (at(2099), None))

    assert summary(psd) == PositionSummary(latest=planned, active=None)


def test_frameless_position_is_always_active(psd, parliament, senate):
    position(psd, PartyPositionType.MAJORITY, parliament, (at(2020), at(2030)))
    frameless = position(psd, PartyPositionType.OPPOSITION, senate)

    assert summary(psd).active == frameless


def test_active_in_two_chambers_goes_to_the_later_end(psd, parliament, senate):
    longer = position(psd, PartyPositionType.MAJORITY, parliament, (at(2024), at(2030)))
    position(psd, PartyPositionType.OPPOSITION, senate, (at(2025), at(2028)))

    assert summary(psd).active == longer


def test_active_ranks_only_the_frames_covering_at(psd, parliament, senate):
    # by all its frames, the majority ends last (2095); by the frames covering
    # NOW, the opposition does (2029 against 2027)
    returning = position(
        psd,
        PartyPositionType.MAJORITY,
        parliament,
        (at(2024), at(2027)),
        (at(2090), at(2095)),
    )
    covering = position(psd, PartyPositionType.OPPOSITION, senate, (at(2020), at(2029)))

    assert summary(psd) == PositionSummary(latest=returning, active=covering)


@pytest.mark.parametrize(
    "valid_from, valid_to, is_active",
    [
        (NOW, at(2030), True),
        (at(2020), NOW, False),
        (None, at(2030), True),
        (None, None, True),
    ],
    ids=["starts at", "ends at", "no start", "no bounds"],
)
def test_frames_cover_from_their_start_until_before_their_end(
    psd, parliament, valid_from, valid_to, is_active
):
    party_position = position(
        psd, PartyPositionType.MAJORITY, parliament, (valid_from, valid_to)
    )

    assert summary(psd).active == (party_position if is_active else None)


# timelines: the rule of is_active


def test_frame_on_another_timeline_does_not_count(
    psd, parliament, default_timeline, alternate_timeline
):
    party_position = position(psd, PartyPositionType.MAJORITY, parliament)
    on_timelines(party_position, alternate_timeline, valid_to=at(2030))

    assert summary(psd) == PositionSummary(latest=None, active=None)
    assert not is_active(party_position, default_timeline, NOW)
    assert summary(psd, alternate_timeline) == PositionSummary(
        latest=party_position, active=party_position
    )
    assert is_active(party_position, alternate_timeline, NOW)


def test_frame_without_timeline_links_counts_on_every_timeline(
    psd, parliament, alternate_timeline
):
    party_position = position(
        psd, PartyPositionType.MAJORITY, parliament, (at(2020), at(2030))
    )
    expected = PositionSummary(latest=party_position, active=party_position)

    assert summary(psd) == expected
    assert summary(psd, alternate_timeline) == expected


def test_each_timeline_reports_its_own_position(
    test_settings, psd, parliament, alternate_timeline
):
    other_timeline = VirtualTimeline.objects.create(
        user_settings=test_settings, label="other"
    )
    majority = position(psd, PartyPositionType.MAJORITY, parliament)
    on_timelines(majority, alternate_timeline)
    opposition = position(psd, PartyPositionType.OPPOSITION, parliament)
    on_timelines(opposition, other_timeline)

    assert summary(psd) == PositionSummary(latest=None, active=None)
    assert summary(psd, alternate_timeline) == PositionSummary(
        latest=majority, active=majority
    )
    assert summary(psd, other_timeline) == PositionSummary(
        latest=opposition, active=opposition
    )


def test_latest_ignores_frames_on_other_timelines(
    psd, parliament, senate, alternate_timeline
):
    everywhere = position(
        psd, PartyPositionType.MAJORITY, parliament, (at(2017), at(2099))
    )
    open_ended = position(psd, PartyPositionType.OPPOSITION, senate)
    on_timelines(open_ended, alternate_timeline, valid_from=at(2017))

    assert summary(psd).latest == everywhere
    assert summary(psd, alternate_timeline).latest == open_ended


def test_default_timeline_is_the_one_of_each_party_context(
    psd, parliament, default_timeline, userland, test_user_settings
):
    own = position(psd, PartyPositionType.MAJORITY, parliament)
    on_timelines(own, default_timeline)
    user_party = Party.objects.create(country=userland, label="Userland party")
    theirs = position(user_party, PartyPositionType.OPPOSITION, None)
    on_timelines(
        theirs, test_user_settings.timelines.get(label=VirtualTimeline.DEFAULT_LABEL)
    )

    assert position_summaries([psd, user_party], NOW) == {
        psd.pk: PositionSummary(latest=own, active=own),
        user_party.pk: PositionSummary(latest=theirs, active=theirs),
    }


def test_without_default_timeline_only_frames_on_all_timelines_count(
    psd, parliament, senate, default_timeline
):
    everywhere = position(
        psd, PartyPositionType.MAJORITY, parliament, (at(2020), at(2030))
    )
    restricted = position(psd, PartyPositionType.OPPOSITION, senate)
    on_timelines(restricted, default_timeline)
    default_timeline.label = "renamed"
    default_timeline.save()

    assert summary(psd) == PositionSummary(latest=everywhere, active=everywhere)


def test_summaries_are_per_party(psd, parliament):
    own = position(psd, PartyPositionType.MAJORITY, parliament, (at(2020), at(2030)))
    pnl = Party.objects.create(country_id=1, label="PNL")

    assert position_summaries([psd, pnl], NOW) == {
        psd.pk: PositionSummary(latest=own, active=own),
        pnl.pk: PositionSummary(latest=None, active=None),
    }


@pytest.mark.parametrize("on_alternate_timeline", [False, True])
@pytest.mark.parametrize("party_count", [1, 6])
def test_two_flat_queries_whatever_the_number_of_parties(
    django_assert_num_queries,
    parliament,
    senate,
    alternate_timeline,
    party_count,
    on_alternate_timeline,
):
    parties = [
        Party.objects.create(country_id=1, label=f"party {i}")
        for i in range(party_count)
    ]
    for party in parties:
        position(party, PartyPositionType.MAJORITY, parliament, (at(2020), at(2030)))
        position(party, PartyPositionType.OPPOSITION, senate, (at(2030), None))

    timeline = alternate_timeline if on_alternate_timeline else None

    with django_assert_num_queries(2) as captured:
        position_summaries(parties, NOW, timeline)

    for query in captured.captured_queries:
        assert query["sql"].count("SELECT") == 1, query["sql"]


def test_no_parties_need_no_queries(django_assert_num_queries):
    with django_assert_num_queries(0):
        assert position_summaries([], NOW) == {}
