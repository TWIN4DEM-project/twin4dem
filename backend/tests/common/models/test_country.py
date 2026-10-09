import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from common.models import (
    Country,
    InstitutionBranch,
    InstitutionKind,
    UserSettings,
)


@pytest.mark.django_db
def test_country_name_is_unique_per_settings(test_settings, france):
    with pytest.raises(IntegrityError) as err_proxy:
        with transaction.atomic():
            Country.objects.create(user_settings=test_settings, name="France")

    assert str(err_proxy.value) == (
        "UNIQUE constraint failed: common_country.user_settings_id, common_country.name"
    )


@pytest.mark.django_db
def test_same_country_allowed_in_different_settings(test_settings, france):
    other_settings = UserSettings.objects.create(
        user=test_settings.user, label="alternate world"
    )

    other_france = Country.objects.create(user_settings=other_settings, name="France")

    assert other_france.id != france.id


@pytest.mark.django_db
def test_country_declares_taxonomy(france):
    InstitutionKind.objects.bulk_create(
        [
            InstitutionKind(
                country=france,
                branch=InstitutionBranch.EXECUTIVE,
                institution_name="cabinet",
            ),
            InstitutionKind(
                country=france,
                branch=InstitutionBranch.LEGISLATIVE,
                institution_name="assemblee nationale",
            ),
            InstitutionKind(
                country=france,
                branch=InstitutionBranch.LEGISLATIVE,
                institution_name="senat",
            ),
            InstitutionKind(
                country=france,
                branch=InstitutionBranch.JUDICIARY,
                institution_name="conseil constitutionnel",
            ),
        ]
    )

    legislative = france.institution_kinds.filter(branch=InstitutionBranch.LEGISLATIVE)

    assert france.institution_kinds.count() == 4
    assert set(legislative.values_list("institution_name", flat=True)) == {
        "assemblee nationale",
        "senat",
    }


@pytest.mark.django_db
def test_taxonomy_type_is_unique_per_country(france):
    InstitutionKind.objects.create(
        country=france,
        branch=InstitutionBranch.EXECUTIVE,
        institution_name="cabinet",
    )

    with pytest.raises(IntegrityError) as err_proxy:
        with transaction.atomic():
            InstitutionKind.objects.create(
                country=france,
                branch=InstitutionBranch.JUDICIARY,
                institution_name="cabinet",
            )

    assert str(err_proxy.value) == (
        "UNIQUE constraint failed: "
        "common_institutionkind.institution_name, common_institutionkind.country_id"
    )


@pytest.mark.django_db
def test_taxonomy_branch_rejected_by_database(france):
    with pytest.raises(IntegrityError) as err_proxy:
        with transaction.atomic():
            InstitutionKind.objects.create(
                country=france, branch="monarchy", institution_name="crown"
            )

    assert str(err_proxy.value) == (
        "CHECK constraint failed: ck_institutiontaxonomy_branch"
    )


@pytest.mark.django_db
def test_taxonomy_branch_rejected_by_validation(france):
    taxonomy = InstitutionKind(
        country=france, branch="monarchy", institution_name="crown"
    )

    with pytest.raises(ValidationError) as err_proxy:
        taxonomy.full_clean()

    assert "branch" in err_proxy.value.message_dict


@pytest.mark.django_db
def test_deleting_country_deletes_taxonomy(france):
    taxonomy = InstitutionKind.objects.create(
        country=france, branch=InstitutionBranch.EXECUTIVE, institution_name="cabinet"
    )

    france.delete()

    assert not InstitutionKind.objects.filter(pk=taxonomy.pk).exists()
