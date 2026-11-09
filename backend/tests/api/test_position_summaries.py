from datetime import UTC, datetime

import pytest

from api.serializers._party import PositionSummary, position_summaries
from common.models import (
    Institution,
    Party,
    PartyPosition,
    PartyPositionType,
    TimeFrame,
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


def summary(party: Party) -> PositionSummary:
    return position_summaries([party], NOW)[party.pk]


@pytest.fixture
def psd() -> Party:
    return Party.objects.create(country_id=1, label="PSD")


@pytest.fixture
def parliament() -> Institution:
    return Institution.objects.get(pk=2)


@pytest.fixture
def senate(make_senate) -> Institution:
    return make_senate("Senate")


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


def test_frame_on_a_single_timeline_counts_as_active(
    psd, parliament, alternate_timeline
):
    party_position = position(psd, PartyPositionType.MAJORITY, parliament)
    TimeFrame.objects.occupy(party_position, at(2020), at(2030), [alternate_timeline])

    assert summary(psd).active == party_position


def test_summaries_are_per_party(psd, parliament):
    own = position(psd, PartyPositionType.MAJORITY, parliament, (at(2020), at(2030)))
    pnl = Party.objects.create(country_id=1, label="PNL")

    assert position_summaries([psd, pnl], NOW) == {
        psd.pk: PositionSummary(latest=own, active=own),
        pnl.pk: PositionSummary(latest=None, active=None),
    }


@pytest.mark.parametrize("party_count", [1, 6])
def test_two_flat_queries_whatever_the_number_of_parties(
    django_assert_num_queries, parliament, senate, party_count
):
    parties = [
        Party.objects.create(country_id=1, label=f"party {i}")
        for i in range(party_count)
    ]
    for party in parties:
        position(party, PartyPositionType.MAJORITY, parliament, (at(2020), at(2030)))
        position(party, PartyPositionType.OPPOSITION, senate, (at(2030), None))

    with django_assert_num_queries(2) as captured:
        position_summaries(parties, NOW)

    for query in captured.captured_queries:
        assert query["sql"].count("SELECT") == 1, query["sql"]


def test_no_parties_need_no_queries(django_assert_num_queries):
    with django_assert_num_queries(0):
        assert position_summaries([], NOW) == {}
