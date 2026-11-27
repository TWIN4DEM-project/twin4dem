import pytest
from common.models import OfficeHolding, OfficeSpan


pytestmark = pytest.mark.django_db


def test_senator(test_person, senat):
    senator = OfficeHolding.objects.create(person=test_person, institution=senat)

    assert senator is not None
    assert senator.person == test_person
    assert senator.institution == senat
    assert test_person.offices.count() == 1
    assert test_person.offices.first() == senator
    assert senat.office_holders.count() == 1
    assert senat.office_holders.first() == senator


def test_senator_office_span(test_person, senat, dt, django_assert_max_num_queries):
    senator = OfficeHolding.objects.create(person=test_person, institution=senat)

    span = OfficeSpan.objects.create(
        subject=senator, valid_from=dt(2022), valid_to=dt(2025)
    )
    with django_assert_max_num_queries(1):
        person_spans = list(test_person.office_spans.all())

    assert len(person_spans) == 1
    assert person_spans[0] == span
