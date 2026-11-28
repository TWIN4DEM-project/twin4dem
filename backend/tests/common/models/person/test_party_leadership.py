import pytest
from django.db import transaction

from common.models import PartyLeadership, Person, PartyLeadershipStint

pytestmark = pytest.mark.django_db


def test_party_leadership_create_object(test_person, majority_party):
    sut = PartyLeadership.objects.create(person=test_person, party=majority_party)
    sut.stints.occupy(sut)

    assert sut is not None
    assert sut.stints.count() == 1
    assert sut.party == majority_party
    assert sut.stints.get().subject == sut


def test_person_allows_accessing_own_time_frames(
    test_person,
    test_country,
    majority_party,
    opposition_party,
    default_timeline,
    alternate_timeline,
):
    with transaction.atomic():
        other = Person.objects.create(name="other", country=test_country)
        other_leader = PartyLeadership.objects.create(
            person=other, party=opposition_party
        )
        other_leader.stints.occupy(other_leader)
        items = [
            PartyLeadership(person=test_person, party=party)
            for party in [majority_party, opposition_party]
        ]
        PartyLeadership.objects.bulk_create(items)
        for item in items:
            for timeline in (default_timeline, alternate_timeline):
                PartyLeadershipStint.objects.occupy(subject=item, timelines=[timeline])

    stints = list(test_person.leadership_stints.all())
    assert len(stints) == 4
