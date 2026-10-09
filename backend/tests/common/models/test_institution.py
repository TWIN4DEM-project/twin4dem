import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from common.models import (
    CabinetPayload,
    ChamberPayload,
    CourtPayload,
    Institution,
    InstitutionBranch,
)


def _institution(taxonomy, **kwargs) -> Institution:
    defaults = {
        "label": "Castex",
        "size": 15,
    }
    return Institution(kind=taxonomy, **(defaults | kwargs))


@pytest.fixture
def cabinet_type(french_taxonomy):
    return french_taxonomy[InstitutionBranch.EXECUTIVE]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "branch,schema",
    [
        (InstitutionBranch.EXECUTIVE, CabinetPayload),
        (InstitutionBranch.LEGISLATIVE, ChamberPayload),
        (InstitutionBranch.JUDICIARY, CourtPayload),
    ],
)
def test_branch_uses_its_payload_schema(french_taxonomy, branch, schema):
    institution = _institution(french_taxonomy[branch])

    institution.full_clean()
    institution.save()

    assert isinstance(institution.get_payload(), schema)


@pytest.mark.django_db
def test_clean_fills_in_payload_defaults(cabinet_type):
    institution = _institution(cabinet_type, payload={})

    institution.full_clean()

    assert institution.payload == {
        "connectivity_degree": 3,
        "probability_for": None,
    }


@pytest.mark.django_db
def test_get_payload_returns_typed_attributes(cabinet_type):
    institution = _institution(
        cabinet_type, payload={"connectivity_degree": 4, "probability_for": 0.7}
    )

    payload = institution.get_payload()

    assert payload.connectivity_degree == 4
    assert payload.probability_for == 0.7


@pytest.mark.django_db
@pytest.mark.parametrize(
    "payload,expected_error",
    [
        (
            {"probability_for": 1.01},
            "probability_for: Input should be less than or equal to 1",
        ),
        (
            {"probability_for": -0.01},
            "probability_for: Input should be greater than or equal to 0",
        ),
        (
            {"connectivity_degree": 0},
            "connectivity_degree: Input should be greater than or equal to 1",
        ),
        (
            {"conectivity_degree": 3},
            "conectivity_degree: Extra inputs are not permitted",
        ),
        (
            ["not", "an", "object"],
            "payload: Input should be a valid dictionary or instance of "
            "CabinetPayload",
        ),
    ],
)
def test_invalid_payload(cabinet_type, payload, expected_error):
    institution = _institution(cabinet_type, payload=payload)

    with pytest.raises(ValidationError) as err_proxy:
        institution.full_clean()

    assert err_proxy.value.message_dict["payload"] == [expected_error]


@pytest.mark.django_db
def test_label_is_unique_per_taxonomy(cabinet_type):
    _institution(cabinet_type).save()

    with pytest.raises(IntegrityError) as err_proxy:
        with transaction.atomic():
            _institution(cabinet_type).save()

    assert str(err_proxy.value) == (
        "UNIQUE constraint failed: common_institution.kind_id, common_institution.label"
    )


@pytest.mark.django_db
def test_deleting_country_deletes_institutions(france, cabinet_type):
    institution = _institution(cabinet_type)
    institution.save()

    france.delete()

    assert not Institution.objects.filter(pk=institution.pk).exists()
