import pytest

from common.models import Person


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
