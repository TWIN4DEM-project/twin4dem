import json
import pytest

from src.simulator.model.serialization.pydantic_serializer import (
    pydantic_dumps,
    pydantic_loads,
    pydantic_decoder,
    MODEL_REGISTRY,
)
from src.simulator.model.config import GovernmentConfig, MinisterConfig


@pytest.fixture
def minister_config():
    return MinisterConfig(
        id=1,
        type="Minister",
        party="majority",
        influence=0.8,
        weights=[0.2, 0.1, 0.2, 0.2, 0.1, 0.2],
        opinion=1,
        support1=1,
        support2=0,
        is_pm=True,
    )


@pytest.fixture
def government_config(minister_config):
    return GovernmentConfig(
        action="start",
        ministers=[minister_config],
        kgov=3,
        pact=0.6,
        alpha=0.5,
        epsilon=0.1,
        gamma=1.0,
    )


def test_pydantic_dumps_single_model(minister_config):
    dumped = pydantic_dumps(minister_config)
    loaded_raw = json.loads(dumped)

    # Structure and tag
    assert "__pydantic_model__" in loaded_raw
    assert loaded_raw["__pydantic_model__"] == "MinisterConfig"
    assert "data" in loaded_raw

    # Data corresponds to model_dump
    assert loaded_raw["data"]["id"] == minister_config.id
    assert loaded_raw["data"]["party"] == minister_config.party
    assert loaded_raw["data"]["is_pm"] == minister_config.is_pm


def test_roundtrip_single_model(minister_config):
    dumped = pydantic_dumps(minister_config)
    restored = pydantic_loads(dumped)

    assert isinstance(restored, MinisterConfig)
    # Pydantic models compare by value
    assert restored == minister_config


def test_roundtrip_nested_structures(government_config, minister_config):
    obj = {
        "gov": government_config,
        "ministers": [minister_config],
        "meta": {"note": "test", "count": 1},
    }

    dumped = pydantic_dumps(obj)
    restored = pydantic_loads(dumped)

    assert isinstance(restored, dict)
    assert "gov" in restored and "ministers" in restored

    assert isinstance(restored["gov"], GovernmentConfig)
    assert isinstance(restored["ministers"][0], MinisterConfig)

    # Check some field to be sure data survived
    assert restored["gov"].kgov == government_config.kgov
    assert restored["ministers"][0].id == minister_config.id


def test_pydantic_serializer_non_pydantic_objects():
    data = {"a": 1, "b": "text", "c": [1, 2, 3]}
    dumped = pydantic_dumps(data)
    restored = pydantic_loads(dumped)

    assert restored == data


def test_pydantic_decoder_unknown_model():
    obj = {
        "__pydantic_model__": "UnknownModel",
        "data": {"x": 1},
    }

    restored = pydantic_decoder(obj)

    # Since UnknownModel is not in MODEL_REGISTRY, it should stay as raw dict
    assert restored == obj


def test_pydantic_decoder_known_model(minister_config):
    # Simulate already decoded JSON object with tag + data
    obj = {
        "__pydantic_model__": "MinisterConfig",
        "data": minister_config.model_dump(),
    }

    restored = pydantic_decoder(obj)

    assert isinstance(restored, MinisterConfig)
    assert restored == minister_config


def test_model_registry_keys_match_class_names():
    for name, cls in MODEL_REGISTRY.items():
        assert name == cls.__name__
