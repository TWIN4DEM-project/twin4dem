import pytest

from common.models import Person, OfficeHolding, OfficeSpan


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


def test_senator_office_span(person, senat, dt, django_assert_max_num_queries):
    senator = OfficeHolding.objects.create(person=person, institution=senat)

    span = OfficeSpan.objects.create(
        subject=senator, valid_from=dt(2022), valid_to=dt(2025)
    )
    with django_assert_max_num_queries(1):
        person_spans = list(person.office_spans.all())

    assert len(person_spans) == 1
    assert person_spans[0] == span
