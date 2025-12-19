import pytest
from django.core.exceptions import ValidationError
from django.db import models

from common.fields._sv_field import SeparatedValuesField


class SvFieldTestModel(models.Model):
    values = SeparatedValuesField(
        base_field=models.IntegerField(),
        blank=True,
        null=True,
    )

    class Meta:
        app_label = "tests"


@pytest.mark.django_db
class TestSeparatedValuesFieldSerialization:
    def test_none_round_trip(self):
        field = SvFieldTestModel._meta.get_field("values")

        assert field.to_python(None) is None
        assert field.get_prep_value(None) is None

    def test_empty_string_round_trip(self):
        field = SvFieldTestModel._meta.get_field("values")

        python_value = field.to_python("")
        assert python_value == []

        db_value = field.get_prep_value(python_value)
        assert db_value == ""

        assert field.to_python(db_value) == []

    def test_single_item(self):
        field = SvFieldTestModel._meta.get_field("values")

        python_value = [1]
        db_value = field.get_prep_value(python_value)
        assert db_value == "1"

        restored = field.to_python(db_value)
        assert restored == [1]

    def test_two_items(self):
        field = SvFieldTestModel._meta.get_field("values")

        python_value = [1, 2]
        db_value = field.get_prep_value(python_value)
        assert db_value == "1,2"

        restored = field.to_python(db_value)
        assert restored == [1, 2]


@pytest.mark.django_db
class TestSeparatedValuesFieldTypeHandling:
    def test_string_input_deserializes(self):
        field = SvFieldTestModel._meta.get_field("values")

        assert field.to_python("1,2,3") == [1, 2, 3]

    def test_iterable_input(self):
        field = SvFieldTestModel._meta.get_field("values")

        assert field.to_python((1, 2)) == (1, 2)
        assert field.to_python({1, 2}) == {1, 2}

    def test_invalid_input_raises(self):
        field = SvFieldTestModel._meta.get_field("values")

        with pytest.raises(ValidationError):
            field.to_python(123)
