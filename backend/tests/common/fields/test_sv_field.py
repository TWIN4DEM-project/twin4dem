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


class TestSeparatorValidation:
    def test_multi_char_separator_rejected(self):
        with pytest.raises(ValueError, match="single character"):
            SeparatedValuesField(base_field=models.IntegerField(), separator="ab")

    def test_non_str_separator_rejected(self):
        with pytest.raises(ValueError, match="single character"):
            SeparatedValuesField(base_field=models.IntegerField(), separator=5)


class TestSeparatorCheck:
    def test_valid_separator_reports_no_errors(self):
        field = SeparatedValuesField(base_field=models.IntegerField())

        assert field._check_separator() == []

    def test_invalid_separator_reports_error(self):
        field = SeparatedValuesField(base_field=models.IntegerField())
        field._SeparatedValuesField__separator = 42

        errors = field._check_separator()

        assert errors and errors[0].id == "fields.E900"


class TestDeserialize:
    def test_empty_string_deserializes_to_empty_list(self):
        field = SeparatedValuesField(base_field=models.IntegerField())

        assert field._deserialize("") == []

    def test_custom_separator_splits_values(self):
        field = SeparatedValuesField(base_field=models.IntegerField(), separator="|")

        assert field.to_python("1|2") == [1, 2]


class TestPrepAndToString:
    def test_prep_value_of_none_is_empty_string(self):
        field = SvFieldTestModel._meta.get_field("values")

        assert field._get_prep_value(None) == ""

    def test_value_to_string_serializes_model_instance(self):
        field = SvFieldTestModel._meta.get_field("values")

        assert field.value_to_string(SvFieldTestModel(values=[1, 2])) == "1,2"

    def test_value_to_string_of_none_is_empty(self):
        field = SvFieldTestModel._meta.get_field("values")

        assert field.value_to_string(SvFieldTestModel(values=None)) == ""


class TestDeconstruct:
    def test_non_char_base_field_is_kept(self):
        base_field = models.IntegerField()
        field = SeparatedValuesField(base_field=base_field, separator="|")

        _, _, _, kwargs = field.deconstruct()

        assert kwargs["base_field"] is base_field
        assert kwargs["separator"] == "|"

    def test_char_base_field_is_left_out(self):
        field = SeparatedValuesField(base_field=models.CharField(max_length=5))

        _, _, _, kwargs = field.deconstruct()

        assert "base_field" not in kwargs


class TestFormfield:
    def test_help_text_defaults_to_none(self):
        field = SvFieldTestModel._meta.get_field("values")

        assert field.formfield().help_text is None

    def test_help_text_is_overridable(self):
        field = SvFieldTestModel._meta.get_field("values")

        assert field.formfield(help_text="hint").help_text == "hint"
