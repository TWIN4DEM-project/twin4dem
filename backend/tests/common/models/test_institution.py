import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from common.models import (
    CabinetPayload,
    ChamberPayload,
    CourtPayload,
    Institution,
    InstitutionBranch,
    SerializationModel,
)


def _institution(taxonomy, **kwargs) -> Institution:
    defaults = {
        "label": "Castex",
        "size": 15,
        "serialization_model": SerializationModel.CABINET,
    }
    return Institution(institution_taxonomy=taxonomy, **(defaults | kwargs))


@pytest.fixture
def cabinet_type(french_taxonomy):
    return french_taxonomy[InstitutionBranch.EXECUTIVE]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "branch,serialization_model,schema",
    [
        (InstitutionBranch.EXECUTIVE, SerializationModel.CABINET, CabinetPayload),
        (InstitutionBranch.LEGISLATIVE, SerializationModel.CHAMBER, ChamberPayload),
        (InstitutionBranch.JUDICIARY, SerializationModel.COURT, CourtPayload),
    ],
)
def test_branch_uses_its_payload_schema(
    french_taxonomy, branch, serialization_model, schema
):
    institution = _institution(
        french_taxonomy[branch], serialization_model=serialization_model
    )

    institution.full_clean()
    institution.save()

    assert isinstance(institution.get_payload(), schema)


@pytest.mark.django_db
def test_clean_fills_in_payload_defaults(cabinet_type):
    institution = _institution(cabinet_type, payload={})

    institution.full_clean()

    assert institution.payload == {
        "connectivity_degree": 3,
        "government_probability_for": None,
    }


@pytest.mark.django_db
def test_get_payload_returns_typed_attributes(cabinet_type):
    institution = _institution(
        cabinet_type,
        payload={"connectivity_degree": 4, "government_probability_for": 0.7},
    )

    payload = institution.get_payload()

    assert payload.connectivity_degree == 4
    assert payload.government_probability_for == 0.7


@pytest.mark.django_db
def test_serialization_model_must_match_branch(cabinet_type):
    institution = _institution(
        cabinet_type, serialization_model=SerializationModel.COURT
    )

    with pytest.raises(ValidationError) as err_proxy:
        institution.full_clean()

    assert err_proxy.value.message_dict == {
        "serialization_model": [
            "Institutions of the executive branch must use "
            "the 'cabinet' serialization model."
        ]
    }


@pytest.mark.django_db
def test_unknown_serialization_version(cabinet_type):
    institution = _institution(cabinet_type, serialization_version=99)

    with pytest.raises(ValidationError) as err_proxy:
        institution.full_clean()

    assert err_proxy.value.message_dict == {
        "serialization_version": ["No payload schema for 'cabinet' version 99."]
    }

    with pytest.raises(LookupError):
        institution.get_payload()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "payload,expected_error",
    [
        (
            {"government_probability_for": 1.01},
            "government_probability_for: Input should be less than or equal to 1",
        ),
        (
            {"government_probability_for": -0.01},
            "government_probability_for: Input should be greater than or equal to 0",
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
        "UNIQUE constraint failed: "
        "common_institution.institution_taxonomy_id, common_institution.label"
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "field,value,check_name",
    [
        ("serialization_model", "monarchy", "ck_institution_serialization_model"),
        ("serialization_version", 0, "ck_institution_serialization_version"),
    ],
)
def test_database_rejects_invalid_serialization(cabinet_type, field, value, check_name):
    with pytest.raises(IntegrityError) as err_proxy:
        with transaction.atomic():
            _institution(cabinet_type, **{field: value}).save()

    assert str(err_proxy.value) == f"CHECK constraint failed: {check_name}"


@pytest.mark.django_db
def test_deleting_country_deletes_institutions(france, cabinet_type):
    institution = _institution(cabinet_type)
    institution.save()

    france.delete()

    assert not Institution.objects.filter(pk=institution.pk).exists()
