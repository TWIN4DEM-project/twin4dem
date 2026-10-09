from datetime import datetime, UTC

import pytest
from django.core.exceptions import ValidationError
from django.db.models import RestrictedError

from common.models import (
    Country,
    Institution,
    InstitutionBranch,
    Simulation,
    SimulationInstitution,
    TimeFrame,
    UserSettings,
)


@pytest.fixture
def other_settings(test_settings) -> UserSettings:
    return UserSettings.objects.create(user=test_settings.user, label="other world")


@pytest.mark.django_db
def test_create_simulation(test_settings, french_simulation):
    assert french_simulation.status == Simulation.Status.NEW
    assert french_simulation.current_step == 0
    assert french_simulation.created_at is not None
    assert french_simulation.updated_at is not None
    assert french_simulation in test_settings.simulations.all()


@pytest.mark.django_db
def test_valid_at_defaults_to_now(test_settings, france, default_timeline):
    before = datetime.now(UTC)

    simulation = Simulation.objects.create(
        user_settings=test_settings, country=france, timeline=default_timeline
    )

    assert before <= simulation.valid_at <= datetime.now(UTC)


@pytest.mark.django_db
def test_country_must_belong_to_settings(french_simulation, other_settings):
    french_simulation.country = Country.objects.create(
        user_settings=other_settings, name="France"
    )

    with pytest.raises(ValidationError) as err_proxy:
        french_simulation.full_clean()

    assert err_proxy.value.message_dict == {
        "country": ["The country must belong to the user settings."]
    }


@pytest.mark.django_db
def test_timeline_must_belong_to_settings(french_simulation, other_settings):
    french_simulation.timeline = other_settings.timelines.get()

    with pytest.raises(ValidationError) as err_proxy:
        french_simulation.full_clean()

    assert err_proxy.value.message_dict == {
        "timeline": ["The timeline must belong to the user settings."]
    }


@pytest.mark.django_db
def test_simulated_timeline_cannot_be_deleted(french_simulation, default_timeline):
    with pytest.raises(RestrictedError):
        default_timeline.delete()


@pytest.mark.django_db
def test_deleting_settings_deletes_simulations(
    test_settings, french_simulation, cabinet_seat
):
    test_settings.delete()

    assert not Simulation.objects.exists()
    assert not SimulationInstitution.objects.exists()
    assert not Institution.objects.exists()


# --- SimulationInstitution ------------------------------------------------------


@pytest.mark.django_db
def test_simulation_has_one_institution_per_branch(
    french_simulation, cabinet_seat, chamber_seat, court_seat
):
    institutions = {
        seat.institution.kind.branch: seat.institution.label
        for seat in french_simulation.institutions.all()
    }

    assert institutions == {
        InstitutionBranch.EXECUTIVE: "Castex",
        InstitutionBranch.LEGISLATIVE: "RN2022",
        InstitutionBranch.JUDICIARY: "CC",
    }


@pytest.mark.django_db
def test_simulation_institution_valid(french_simulation, cabinet):
    seat = SimulationInstitution(simulation=french_simulation, institution=cabinet)

    seat.full_clean()


@pytest.mark.django_db
def test_second_institution_of_same_kind_rejected(
    french_simulation, cabinet_seat, french_taxonomy
):
    other_cabinet = Institution.objects.create(
        kind=french_taxonomy[InstitutionBranch.EXECUTIVE],
        label="Philippe II",
        size=15,
    )
    seat = SimulationInstitution(
        simulation=french_simulation, institution=other_cabinet
    )

    with pytest.raises(ValidationError) as err_proxy:
        seat.full_clean()

    assert err_proxy.value.message_dict == {
        "institution": ["The simulation already has a cabinet."]
    }


@pytest.mark.django_db
def test_institution_must_belong_to_simulated_country(test_settings, french_simulation):
    belgium = Country.objects.create(user_settings=test_settings, name="Belgium")
    belgian_cabinet = Institution.objects.create(
        kind=belgium.institution_kinds.create(
            branch=InstitutionBranch.EXECUTIVE, institution_name="government"
        ),
        label="De Croo",
        size=15,
    )
    seat = SimulationInstitution(
        simulation=french_simulation, institution=belgian_cabinet
    )

    with pytest.raises(ValidationError) as err_proxy:
        seat.full_clean()

    assert err_proxy.value.message_dict == {
        "institution": ["The institution must belong to the simulated country."]
    }


@pytest.mark.django_db
def test_institution_must_be_active_at_simulated_time(french_simulation, cabinet):
    TimeFrame.objects.occupy(
        cabinet,
        valid_from=datetime(2022, 5, 16, tzinfo=UTC),
        valid_to=datetime(2024, 1, 9, tzinfo=UTC),
    )
    seat = SimulationInstitution(simulation=french_simulation, institution=cabinet)

    with pytest.raises(ValidationError) as err_proxy:
        seat.full_clean()

    assert err_proxy.value.message_dict == {
        "institution": [
            "'Castex' is not active on timeline 'default' at 2021-01-01 00:00:00+00:00."
        ]
    }


@pytest.mark.django_db
def test_simulated_institution_cannot_be_deleted(cabinet, cabinet_seat):
    with pytest.raises(RestrictedError):
        cabinet.delete()
