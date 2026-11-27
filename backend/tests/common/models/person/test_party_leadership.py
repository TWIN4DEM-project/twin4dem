import pytest

from common.models import PartyLeadership


pytestmark = pytest.mark.django_db


def test_party_leadership_create_object(test_person, majority_party):
    sut = PartyLeadership.objects.create(person=test_person, party=majority_party)
    sut.stints.occupy(sut)

    assert sut is not None
    assert sut.stints.count() == 1
    assert sut.party == majority_party
    assert sut.stints.get().subject == sut
