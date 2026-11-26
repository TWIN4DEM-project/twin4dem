import pytest

from common.models import (
    Country,
    Institution,
    InstitutionBranch,
    InstitutionKind,
    Party,
)


@pytest.fixture
def france(test_settings) -> Country:
    return Country.objects.create(user_settings=test_settings, name="France")


@pytest.fixture
def french_taxonomy(france) -> dict[str, InstitutionKind]:
    """The taxonomy from the 'User Settings — Next' example in the docs."""
    return {
        branch: InstitutionKind.objects.create(
            country=france, branch=branch, institution_name=type_
        )
        for branch, type_ in (
            (InstitutionBranch.EXECUTIVE, "cabinet"),
            (InstitutionBranch.LEGISLATIVE, "assemblee nationale"),
            (InstitutionBranch.JUDICIARY, "conseil constitutionnel"),
        )
    }


@pytest.fixture
def cabinet(french_taxonomy) -> Institution:
    return Institution.objects.create(
        kind=french_taxonomy[InstitutionBranch.EXECUTIVE],
        label="Castex",
        size=15,
    )


@pytest.fixture
def assemblee(french_taxonomy) -> Institution:
    return Institution.objects.create(
        kind=french_taxonomy[InstitutionBranch.LEGISLATIVE],
        label="RN2022",
        size=100,
    )


@pytest.fixture
def renaissance(france) -> Party:
    return Party.objects.create(country=france, label="Renaissance")
