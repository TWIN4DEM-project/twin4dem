import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from common.models.person import Person


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(name="Joey Diaz", dob="1963-02-19"),
        dict(name="Jean Vicompte", dod="2023-11-20"),
        dict(name="Karl Dorf"),
    ],
    ids=["name-dob", "name-dod", "just-name"],
)
def test_ok_person(france, kwargs):
    p = Person.objects.create(country=france, **kwargs)

    assert p is not None
    assert isinstance(p.id, int)


def test_person_without_name_raises_integrity_error(france):
    with pytest.raises(IntegrityError) as err_proxy:
        Person.objects.create(
            name=None, dob="1990-01-01", dod="1994-12-31", country=france
        )

    assert err_proxy.value is not None
    assert str(err_proxy.value) == "NOT NULL constraint failed: people.name"


def test_person_without_country_raises_integrity_error(france):
    with pytest.raises(IntegrityError) as err_proxy:
        Person.objects.create(
            name="Lulu Lemon", dob="1990-01-01", dod="1994-12-31", country=None
        )

    assert err_proxy.value is not None
    assert str(err_proxy.value) == "NOT NULL constraint failed: people.country_id"


@pytest.mark.django_db(transaction=True)
def test_person_with_wrong_country_raises_integrity_error():
    with pytest.raises(IntegrityError) as err_proxy:
        Person.objects.create(
            name="Lulu Lemon", dob="1990-01-01", dod="1994-12-31", country_id=-2
        )

    assert err_proxy.value is not None
    assert str(err_proxy.value) == "FOREIGN KEY constraint failed"


def test_person_with_dod_before_dob_raises_integrity_error(france):
    with pytest.raises(IntegrityError) as err_proxy:
        Person.objects.create(
            name="Alphonse Godot", dob="1995-01-01", dod="1994-12-31", country=france
        )

    assert err_proxy.value is not None
    assert str(err_proxy.value) == "CHECK constraint failed: people_dod_after_dob"


def test_clean_person_with_dod_after_dob_raises_validation_error(france):
    with pytest.raises(ValidationError) as err_proxy:
        p = Person(
            name="Alphonse Godot", dob="1995-01-01", dod="1994-12-31", country=france
        )
        p.clean()

    assert err_proxy.value is not None
    assert err_proxy.value.messages == ["Date of death must follow date of birth"]
