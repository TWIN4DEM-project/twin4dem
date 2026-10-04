import pytest

from common.models import Country, InstitutionBranch, InstitutionTaxonomy


@pytest.fixture
def france(test_settings) -> Country:
    return Country.objects.create(user_settings=test_settings, name="France")


@pytest.fixture
def french_taxonomy(france) -> dict[str, InstitutionTaxonomy]:
    """The taxonomy from the 'User Settings — Next' example in the docs."""
    return {
        branch: InstitutionTaxonomy.objects.create(
            country=france, branch=branch, type=type_
        )
        for branch, type_ in (
            (InstitutionBranch.EXECUTIVE, "cabinet"),
            (InstitutionBranch.LEGISLATIVE, "assemblee nationale"),
            (InstitutionBranch.JUDICIARY, "conseil constitutionnel"),
        )
    }
