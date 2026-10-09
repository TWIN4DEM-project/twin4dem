import pytest
from django.db import models
from rest_framework import serializers

from api.fields import SeparatedValuesSerializerField
from common.fields import SeparatedValuesField


@pytest.fixture
def model_field() -> SeparatedValuesField:
    return SeparatedValuesField(base_field=models.IntegerField())


@pytest.fixture
def field(model_field) -> SeparatedValuesSerializerField:
    return SeparatedValuesSerializerField(model_field=model_field)


def test_to_representation_of_none(field):
    assert field.to_representation(None) is None


def test_to_representation_of_values(field):
    assert field.to_representation([1, 2]) == [1, 2]


def test_to_internal_value_of_none(field):
    assert field.to_internal_value(None) is None


def test_to_internal_value_coerces_through_the_model_field(field):
    assert field.to_internal_value([1, 2]) == [1, 2]


@pytest.mark.parametrize("data", ["1,2", 12])
def test_to_internal_value_rejects_non_collections(field, data):
    with pytest.raises(serializers.ValidationError, match="Expected a list"):
        field.to_internal_value(data)


def test_to_internal_value_wraps_coercion_errors(field):
    with pytest.raises(serializers.ValidationError):
        field.to_internal_value(["abc"])
