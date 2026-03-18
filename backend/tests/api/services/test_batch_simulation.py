from datetime import datetime

import pytest
from django.contrib.contenttypes.models import ContentType

from api.serializers import SimulationSerializer
from api.services._batch_simulation import AggrandisementBatchBuilder
from common.models import UserSettings, Cabinet, Parliament, Court


@pytest.fixture
def test_user(django_user_model):
    return django_user_model.objects.get(username="test_user")


@pytest.fixture
def test_user_settings(test_user):
    return UserSettings.objects.get(user=test_user)


@pytest.fixture
def empty_sut(test_user_settings):
    return AggrandisementBatchBuilder(test_user_settings)


@pytest.fixture
def sut(empty_sut, aggrandisement_batch_path):
    return empty_sut.load_aggrandisement_batch(aggrandisement_batch_path)


@pytest.fixture
def serializer():
    serializer = SimulationSerializer(data={})
    serializer.is_valid()
    return serializer


def test_load_initializes_builder_data(sut):
    assert isinstance(sut.aggrandisement_batch.start_date, datetime)
    assert isinstance(sut.aggrandisement_batch.end_date, datetime)
    assert len(sut.aggrandisement_batch.aggrandisement_units) == 1
    assert sut.aggrandisement_batch.aggrandisement_units[0].step == 1
    executive_settings = sut.aggrandisement_batch.settings.executive
    assert executive_settings.prime_minister in set(
        x.label for x in executive_settings.ministers
    )
    legislative_settings = sut.aggrandisement_batch.settings.legislative
    mps = set(x.label for x in legislative_settings.mps)
    assert all(h in mps for h in legislative_settings.party_leaders)
    judiciary_settings = sut.aggrandisement_batch.settings.judiciary
    judges = set(x.label for x in judiciary_settings.judges)
    assert judiciary_settings.president in judges


def _get_related[T](simulation, model_class: type[T]) -> T:
    related_of_type = simulation.params.filter(
        type=ContentType.objects.get_for_model(model_class)
    ).select_related("type")
    return related_of_type.first().params


def test_create_adds_cabinet(sut, serializer, test_user_settings):
    cabinet = _get_related(sut.create(serializer), Cabinet)

    executive_settings = sut.aggrandisement_batch.settings.executive
    assert cabinet.ministers.count() == len(executive_settings.ministers)
    assert (
        cabinet.government_probability_for
        == test_user_settings.government_probability_for
    )


def test_create_adds_parliament(sut, serializer, test_user_settings):
    parliament = _get_related(sut.create(serializer), Parliament)

    legislative_settings = sut.aggrandisement_batch.settings.legislative
    assert parliament.members.count() == len(legislative_settings.mps)
    assert (
        parliament.majority_probability_for
        == test_user_settings.parliament_majority_probability_for
    )
    assert (
        parliament.opposition_probability_for
        == test_user_settings.parliament_opposition_probability_for
    )


def test_create_adds_court(sut, serializer, test_user_settings):
    court = _get_related(sut.create(serializer), Court)

    judiciary_settings = sut.aggrandisement_batch.settings.judiciary
    assert court.judges.count() == len(judiciary_settings.judges)
    assert court.probability_for == test_user_settings.court_probability_for
