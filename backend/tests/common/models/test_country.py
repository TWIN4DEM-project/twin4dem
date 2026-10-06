import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from common.models import (
    Country,
    InstitutionBranch,
    InstitutionTaxonomy,
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
    InstitutionTaxonomy.objects.bulk_create(
        [
            InstitutionTaxonomy(
                country=france, branch=InstitutionBranch.EXECUTIVE, type="cabinet"
            ),
            InstitutionTaxonomy(
                country=france,
                branch=InstitutionBranch.LEGISLATIVE,
                type="assemblee nationale",
            ),
            InstitutionTaxonomy(
                country=france, branch=InstitutionBranch.LEGISLATIVE, type="senat"
            ),
            InstitutionTaxonomy(
                country=france,
                branch=InstitutionBranch.JUDICIARY,
                type="conseil constitutionnel",
            ),
        ]
    )

    legislative = france.taxonomy.filter(branch=InstitutionBranch.LEGISLATIVE)

    assert france.taxonomy.count() == 4
    assert set(legislative.values_list("type", flat=True)) == {
        "assemblee nationale",
        "senat",
    }


@pytest.mark.django_db
def test_taxonomy_type_is_unique_per_country(france):
    InstitutionTaxonomy.objects.create(
        country=france, branch=InstitutionBranch.EXECUTIVE, type="cabinet"
    )

    with pytest.raises(IntegrityError) as err_proxy:
        with transaction.atomic():
            InstitutionTaxonomy.objects.create(
                country=france, branch=InstitutionBranch.JUDICIARY, type="cabinet"
            )

    assert str(err_proxy.value) == (
        "UNIQUE constraint failed: "
        "common_institutiontaxonomy.country_id, common_institutiontaxonomy.type"
    )


@pytest.mark.django_db
def test_taxonomy_branch_rejected_by_database(france):
    with pytest.raises(IntegrityError) as err_proxy:
        with transaction.atomic():
            InstitutionTaxonomy.objects.create(
                country=france, branch="monarchy", type="crown"
            )

    assert str(err_proxy.value) == (
        "CHECK constraint failed: ck_institutiontaxonomy_branch"
    )


@pytest.mark.django_db
def test_taxonomy_branch_rejected_by_validation(france):
    taxonomy = InstitutionTaxonomy(country=france, branch="monarchy", type="crown")

    with pytest.raises(ValidationError) as err_proxy:
        taxonomy.full_clean()

    assert "branch" in err_proxy.value.message_dict


@pytest.mark.django_db
def test_deleting_country_deletes_taxonomy(france):
    taxonomy = InstitutionTaxonomy.objects.create(
        country=france, branch=InstitutionBranch.EXECUTIVE, type="cabinet"
    )

    france.delete()

    assert not InstitutionTaxonomy.objects.filter(pk=taxonomy.pk).exists()
