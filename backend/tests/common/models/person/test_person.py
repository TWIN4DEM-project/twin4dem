import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from common.models.person import Person


def test_ok_person(france):
    p = Person.objects.create(name="Joey Diaz", dob="1963-02-19", dod=None, country=france)

    assert p is not None
    assert isinstance(p.id, int)


def test_person_with_dod_before_dob_raises_integrity_error(france):
    with pytest.raises(IntegrityError) as err_proxy:
        Person.objects.create(name="Alphonse Godot", dob="1995-01-01", dod="1994-12-31", country=france)

    assert err_proxy.value is not None
    assert str(err_proxy.value) == "CHECK constraint failed: people_dod_after_dob"


def test_clean_person_with_dod_after_dob_raises_validation_error(france):
    with pytest.raises(ValidationError) as err_proxy:
        p = Person(name="Alphonse Godot", dob="1995-01-01", dod="1994-12-31", country=france)
        p.clean()

    assert err_proxy.value is not None
    assert err_proxy.value.messages == ["Date of death must follow date of birth"]


