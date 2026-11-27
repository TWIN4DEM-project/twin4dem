import pytest
from common.models import (
    PartyPositionType,
    PartyPosition,
    PartyPositionTimeFrame,
    Party,
    PartyMembershipPeriod,
)

pytestmark = pytest.mark.django_db


def test_party_membership_create(party_member):
    assert party_member is not None


@pytest.mark.parametrize(
    "party,expected_position",
    [
        (PartyPositionType.MAJORITY, PartyPositionType.MAJORITY),
        (PartyPositionType.OPPOSITION, PartyPositionType.OPPOSITION),
        (PartyPositionType.INDEPENDENT, PartyPositionType.INDEPENDENT),
    ],
    indirect=["party"],
    ids=["majority", "opposition", "independent"],
)
def test_party_membership_period(party_member, party, expected_position):
    membership_period = PartyMembershipPeriod.objects.create(
        subject=party_member,
        party=party,
    )

    assert membership_period.party == party


@pytest.mark.parametrize(
    "party,expected_position",
    [
        (PartyPositionType.MAJORITY, PartyPositionType.MAJORITY),
        (PartyPositionType.OPPOSITION, PartyPositionType.OPPOSITION),
        (PartyPositionType.INDEPENDENT, PartyPositionType.INDEPENDENT),
    ],
    indirect=["party"],
    ids=["majority", "opposition", "independent"],
)
def test_party_membership_most_recent_positions_all_timelines(
    party_member, party, expected_position
):
    PartyMembershipPeriod.objects.create(
        subject=party_member,
        party=party,
    )

    positions = party_member.most_recent_positions()

    assert positions.all_timelines == expected_position


@pytest.mark.parametrize(
    "party,expected_position",
    [
        (PartyPositionType.MAJORITY, PartyPositionType.MAJORITY),
        (PartyPositionType.OPPOSITION, PartyPositionType.OPPOSITION),
        (PartyPositionType.INDEPENDENT, PartyPositionType.INDEPENDENT),
    ],
    indirect=["party"],
    ids=["majority", "opposition", "independent"],
)
def test_party_membership_positions_on_a_single_timeline(
    party_member, party, expected_position, default_timeline, alternate_timeline
):
    membership_period = PartyMembershipPeriod.objects.create(
        subject=party_member,
        party=party,
    )
    membership_period.timelines.set([default_timeline])
    PartyPositionTimeFrame.objects.occupy(
        party.positions.get(),
        timelines=[default_timeline],
    )

    positions = party_member.most_recent_positions()

    assert positions.all_timelines is None
    assert positions.for_timeline(default_timeline) == expected_position
    assert positions.get(alternate_timeline) is None
    assert len(party_member.most_recent_positions(alternate_timeline)) == 0


def test_party_membership_positions_on_two_timelines(
    party_member,
    majority_party,
    opposition_party,
    default_timeline,
    alternate_timeline,
):
    majority_period = PartyMembershipPeriod.objects.create(
        subject=party_member,
        party=majority_party,
    )
    majority_period.timelines.set([default_timeline])
    opposition_period = PartyMembershipPeriod.objects.create(
        subject=party_member,
        party=opposition_party,
    )
    opposition_period.timelines.set([alternate_timeline])

    PartyPositionTimeFrame.objects.occupy(
        majority_party.positions.get(),
        timelines=[default_timeline],
    )
    PartyPositionTimeFrame.objects.occupy(
        opposition_party.positions.get(),
        timelines=[alternate_timeline],
    )

    positions = party_member.most_recent_positions()

    assert positions.all_timelines is None
    assert positions.for_timeline(default_timeline) == PartyPositionType.MAJORITY
    assert positions.for_timeline(alternate_timeline) == PartyPositionType.OPPOSITION

    default_positions = party_member.most_recent_positions(default_timeline)
    assert set(default_positions) == {default_timeline.pk}
    assert (
        default_positions.for_timeline(default_timeline) == PartyPositionType.MAJORITY
    )

    alternate_positions = party_member.most_recent_positions(alternate_timeline)
    assert set(alternate_positions) == {alternate_timeline.pk}
    assert (
        alternate_positions.for_timeline(alternate_timeline)
        == PartyPositionType.OPPOSITION
    )


def test_party_membership_without_periods_has_no_positions(party_member):
    positions = party_member.most_recent_positions()

    assert len(positions) == 0


def test_party_membership_with_party_without_positions_has_no_positions(
    party_member, test_country
):
    party = Party.objects.create(country=test_country, label="no positions")
    PartyMembershipPeriod.objects.create(subject=party_member, party=party)

    positions = party_member.most_recent_positions()

    assert len(positions) == 0


@pytest.mark.parametrize(
    "party,expected_position",
    [
        (PartyPositionType.MAJORITY, PartyPositionType.MAJORITY),
        (PartyPositionType.OPPOSITION, PartyPositionType.OPPOSITION),
        (PartyPositionType.INDEPENDENT, PartyPositionType.INDEPENDENT),
    ],
    indirect=["party"],
    ids=["majority", "opposition", "independent"],
)
def test_party_membership_multiple_periods_for_the_same_party(
    party_member, party, expected_position, default_timeline, dt
):
    first_period = PartyMembershipPeriod.objects.create(
        subject=party_member,
        party=party,
        valid_from=dt(2000),
        valid_to=dt(2010),
    )
    first_period.timelines.set([default_timeline])
    second_period = PartyMembershipPeriod.objects.create(
        subject=party_member,
        party=party,
        valid_from=dt(2010),
    )
    second_period.timelines.set([default_timeline])
    PartyPositionTimeFrame.objects.occupy(
        party.positions.get(),
        timelines=[default_timeline],
    )

    positions = party_member.most_recent_positions()

    assert set(positions) == {default_timeline.pk}
    assert positions.for_timeline(default_timeline) == expected_position


def test_party_membership_newer_position_wins(
    party_member, majority_party, default_timeline, dt
):
    PartyMembershipPeriod.objects.create(
        subject=party_member,
        party=majority_party,
    )
    current_position = majority_party.positions.get()
    PartyPositionTimeFrame.objects.occupy(
        current_position,
        dt(2000),
        dt(2010),
        [default_timeline],
    )
    newer_position = PartyPosition.objects.create(
        party=majority_party,
        chamber=current_position.chamber,
        position=PartyPositionType.OPPOSITION,
    )
    PartyPositionTimeFrame.objects.occupy(
        newer_position,
        dt(2010),
        None,
        [default_timeline],
    )

    positions = party_member.most_recent_positions()

    assert positions.for_timeline(default_timeline) == PartyPositionType.OPPOSITION


def test_party_membership_period_timeline_restricts_positions(
    party_member, majority_party, default_timeline, alternate_timeline
):
    membership_period = PartyMembershipPeriod.objects.create(
        subject=party_member,
        party=majority_party,
    )
    membership_period.timelines.set([default_timeline])
    PartyPositionTimeFrame.objects.occupy(
        majority_party.positions.get(),
        timelines=[alternate_timeline],
    )

    # The membership period only covers the default timeline, so the party's
    # position on the alternate timeline must not leak into the result.
    assert len(party_member.most_recent_positions()) == 0
