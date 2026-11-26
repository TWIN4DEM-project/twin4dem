import pytest
from django.db import transaction
from common.models import (
    PartyMembership,
    PartyPositionType,
    PartyPosition,
    Institution,
    Party,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def party(majority_party, opposition_party, request, test_country, transactional_db):
    position = getattr(request, "param", PartyPositionType.INDEPENDENT)
    match position:
        case PartyPositionType.MAJORITY:
            return majority_party
        case PartyPositionType.OPPOSITION:
            return opposition_party
    with transaction.atomic():
        chamber = Institution.objects.get(pk=2)
        result, ok = Party.objects.get_or_create(
            country=test_country, label="independents"
        )
        assert ok, "could not create party object"
        _, ok = PartyPosition.objects.get_or_create(
            party=result,
            chamber=chamber,
            position=PartyPositionType.INDEPENDENT,
        )

    assert ok, "could not create independent position"
    return result


def test_party_membership_create(test_person, party):
    party_member = PartyMembership.objects.create(person=test_person, party=party)

    assert party_member is not None
