import pytest
from django.core.exceptions import ImproperlyConfigured

from common.models import Institution, Party, PartyPosition
from common.models import _timeframe


@pytest.fixture(autouse=True)
def _clear_subject_model_cache():
    """Keep the registry cache from leaking across tests."""
    yield
    cache = _timeframe._subject_models
    if hasattr(cache, "cache_clear"):
        cache.cache_clear()


def test_subject_type_of_rejects_a_non_subject():
    with pytest.raises(TypeError) as err_proxy:
        _timeframe.subject_type_of(Party(label="Renaissance"))

    assert str(err_proxy.value) == "Party cannot occupy a time frame"


def test_registry_covers_the_declared_subject_types():
    subject_models = _timeframe._subject_models()

    assert set(subject_models) == set(_timeframe.TimeFrameSubjectType.values)
    assert set(subject_models.values()) == {Institution, PartyPosition}


def test_check_passes_when_every_subject_type_is_claimed():
    assert _timeframe.check_time_frame_subjects() == []


def test_check_fails_when_a_subject_type_has_no_model(monkeypatch):
    monkeypatch.setattr(_timeframe, "_subject_models", lambda: {})

    errors = _timeframe.check_time_frame_subjects()

    assert sorted(e.msg for e in errors) == [
        "A model must opt in as the time frame subject type 'institution'.",
        "A model must opt in as the time frame subject type 'party_position'.",
    ]


def test_check_fails_on_an_unknown_subject_type(monkeypatch):
    class Rogue:
        pass

    monkeypatch.setattr(_timeframe, "_subject_models", lambda: {"galaxy": Rogue})

    errors = _timeframe.check_time_frame_subjects()

    assert [(e.id, e.obj) for e in errors if e.id == "common.E002"] == [
        ("common.E002", Rogue)
    ]


def test_duplicate_subject_type_is_improperly_configured(monkeypatch):
    class FakeApps:
        @staticmethod
        def get_models():
            return [Institution, Institution]

    monkeypatch.setattr(_timeframe, "apps", FakeApps)
    _timeframe._subject_models.cache_clear()

    with pytest.raises(ImproperlyConfigured) as err_proxy:
        _timeframe._subject_models()

    assert "both claim the time frame subject type 'institution'" in str(
        err_proxy.value
    )
