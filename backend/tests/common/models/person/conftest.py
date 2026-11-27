import pytest

from django.db import transaction

from common.models import (
    Institution,
    Party,
    PartyMembership,
    PartyPosition,
    PartyPositionType,
    Person,
)


@pytest.fixture
def person_name():
    return "a test name"


@pytest.fixture
def person_dob(dt, request):
    return getattr(request, "param", dt(1990))


@pytest.fixture
def person_dod(dt, request):
    return getattr(request, "param", None)


@pytest.fixture
def test_person(
    django_db_blocker, test_country, person_name, person_dob, person_dod
) -> Person:
    with django_db_blocker.unblock():
        person, ok = Person.objects.get_or_create(
            country=test_country,
            name=person_name,
            dob=person_dob,
            dod=person_dod,
        )
        assert ok, "get or create person failed"
        return person


@pytest.fixture
def party(django_db_setup, majority_party, opposition_party, request, test_country):
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


@pytest.fixture
def party_member(test_person):
    return PartyMembership.objects.create(person=test_person)
