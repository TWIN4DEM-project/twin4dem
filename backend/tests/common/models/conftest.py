from datetime import datetime, UTC

import pytest

from common.models import (
    Country,
    Institution,
    InstitutionBranch,
    InstitutionKind,
    Simulation,
    SimulationInstitution,
)


@pytest.fixture
def test_country(django_db_setup) -> Country:
    return Country.objects.get(pk=1)


@pytest.fixture
def senat(france) -> Institution:
    taxonomy = InstitutionKind.objects.create(
        country=france, branch=InstitutionBranch.LEGISLATIVE, institution_name="senat"
    )
    return Institution.objects.create(
        kind=taxonomy,
        label="Senat2023",
        size=348,
    )


@pytest.fixture
def court(french_taxonomy) -> Institution:
    return Institution.objects.create(
        kind=french_taxonomy[InstitutionBranch.JUDICIARY],
        label="CC",
        size=9,
    )


@pytest.fixture
def french_simulation(test_settings, france, default_timeline) -> Simulation:
    return Simulation.objects.create(
        user_settings=test_settings,
        country=france,
        timeline=default_timeline,
        valid_at=datetime(2021, 1, 1, tzinfo=UTC),
    )


@pytest.fixture
def cabinet_seat(french_simulation, cabinet) -> SimulationInstitution:
    return SimulationInstitution.objects.create(
        simulation=french_simulation, institution=cabinet
    )


@pytest.fixture
def chamber_seat(french_simulation, assemblee) -> SimulationInstitution:
    return SimulationInstitution.objects.create(
        simulation=french_simulation, institution=assemblee
    )


@pytest.fixture
def court_seat(french_simulation, court) -> SimulationInstitution:
    return SimulationInstitution.objects.create(
        simulation=french_simulation, institution=court
    )
