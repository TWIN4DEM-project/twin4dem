from datetime import datetime, UTC

import pytest

from common.models import (
    Country,
    Institution,
    InstitutionBranch,
    InstitutionKind,
    Party,
    Simulation,
    SimulationInstitution,
    VirtualTimeline,
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
def default_timeline(test_settings) -> VirtualTimeline:
    return test_settings.timelines.get(label=VirtualTimeline.DEFAULT_LABEL)


@pytest.fixture
def alternate_timeline(test_settings) -> VirtualTimeline:
    return VirtualTimeline.objects.create(
        user_settings=test_settings, label="alternate"
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
