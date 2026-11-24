import pytest

from common.models import Person, OfficeHolding


@pytest.fixture
def person(france):
    return Person.objects.create(name="test", country=france)


def test_senator(person, senat):
    senator = OfficeHolding.objects.create(person=person, institution=senat)

    assert senator is not None
    assert senator.person == person
    assert senator.institution == senat
    assert person.offices.count() == 1
    assert person.offices.first() == senator
    assert senat.office_holders.count() == 1
    assert senat.office_holders.first() == senator
