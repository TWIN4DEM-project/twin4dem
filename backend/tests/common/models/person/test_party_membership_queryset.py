import pytest
from django.db.models import F

from common.models import (
    Party,
    PartyMembership,
    PartyMembershipPeriod,
    PartyPositionTimeFrame,
    Person,
)

pytestmark = pytest.mark.django_db


def test_related_positions_on_default_timeline_exclude_alternate_positions(
    party_member, majority_party, default_timeline, alternate_timeline
):
    period = PartyMembershipPeriod.objects.create(
        subject=party_member,
        party=majority_party,
    )
    period.timelines.set([default_timeline])
    PartyPositionTimeFrame.objects.occupy(
        majority_party.positions.get(),
        timelines=[alternate_timeline],
    )

    positions = PartyMembership.objects.filter(pk=party_member.pk).related_positions()

    assert not positions.exists()


@pytest.mark.django_db(transaction=True)
def test_related_positions_return_all_distinct_related_positions(
    party_member,
    majority_party,
    opposition_party,
    default_timeline,
    alternate_timeline,
    test_country,
):
    for timeline in (default_timeline, alternate_timeline):
        period = PartyMembershipPeriod.objects.create(
            subject=party_member,
            party=majority_party,
        )
        period.timelines.set([timeline])

    other_member = PartyMembership.objects.create(
        person=Person.objects.create(name="other", country=test_country)
    )
    PartyMembershipPeriod.objects.create(subject=other_member, party=opposition_party)

    positions = list(
        PartyMembership.objects.related_positions().values(
            pp_id=F("party__pk"),
            pp_pos=F("position"),
            pp_time=F("time_frames__timelines"),
            per_id=F("party__party_members__subject__person__id"),
            per_name=F("party__party_members__subject__person__name"),
            per_time=F("party__party_members__timelines"),
        )
    )
    assert len(positions) == 3
    assert positions == [
        {
            "per_id": 1,
            "per_name": "a test name",
            "per_time": 1,
            "pp_id": 1,
            "pp_pos": "majority",
            "pp_time": None,
        },
        {
            "per_id": 1,
            "per_name": "a test name",
            "per_time": 4,
            "pp_id": 1,
            "pp_pos": "majority",
            "pp_time": None,
        },
        {
            "per_id": 2,
            "per_name": "other",
            "per_time": None,
            "pp_id": 2,
            "pp_pos": "opposition",
            "pp_time": None,
        },
    ]


def test_related_positions_filter_by_party(
    party_member, majority_party, opposition_party
):
    PartyMembershipPeriod.objects.create(subject=party_member, party=majority_party)
    PartyMembershipPeriod.objects.create(subject=party_member, party=opposition_party)

    positions = PartyMembership.objects.related_positions(
        parties=Party.objects.filter(pk=majority_party.pk)
    )

    assert set(positions.values_list("pk", flat=True)) == {
        majority_party.positions.get().pk
    }
