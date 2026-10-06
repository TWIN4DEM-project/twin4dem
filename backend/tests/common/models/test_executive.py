import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from common.models import (
    Country,
    Minister,
    MinisterLink,
    Simulation,
    SimulationInstitution,
)


@pytest.mark.django_db
def test_same_cabinet_same_minister_names(cabinet_seat, renaissance):
    Minister.objects.create(label="m1", cabinet=cabinet_seat, party=renaissance)

    with pytest.raises(IntegrityError) as err_proxy:
        with transaction.atomic():
            Minister.objects.create(label="m1", cabinet=cabinet_seat, party=renaissance)

    assert (
        str(err_proxy.value)
        == "UNIQUE constraint failed: common_minister.label, common_minister.cabinet_id"
    )


@pytest.mark.django_db
def test_same_cabinet_in_two_simulations_has_separate_ministers(
    french_simulation, cabinet, cabinet_seat, renaissance
):
    other_simulation = Simulation.objects.create(
        user_settings=french_simulation.user_settings,
        country=french_simulation.country,
        timeline=french_simulation.timeline,
    )
    other_seat = SimulationInstitution.objects.create(
        simulation=other_simulation, institution=cabinet
    )
    Minister.objects.create(label="m1", cabinet=cabinet_seat, party=renaissance)
    Minister.objects.create(label="m1", cabinet=other_seat, party=renaissance)

    assert cabinet_seat.ministers.count() == 1
    assert other_seat.ministers.count() == 1


@pytest.mark.django_db
def test_minister_valid(cabinet_seat, renaissance):
    minister = Minister(label="m1", cabinet=cabinet_seat, party=renaissance)

    minister.full_clean()


@pytest.mark.django_db
def test_minister_must_belong_to_cabinet(chamber_seat, renaissance):
    minister = Minister(label="m1", cabinet=chamber_seat, party=renaissance)

    with pytest.raises(ValidationError) as err_proxy:
        minister.full_clean()

    assert err_proxy.value.message_dict == {
        "cabinet": ["A minister must belong to a cabinet, not to a chamber."]
    }


@pytest.mark.django_db
def test_minister_party_must_belong_to_country(test_settings, cabinet_seat):
    belgium = Country.objects.create(user_settings=test_settings, name="Belgium")
    minister = Minister(
        label="m1", cabinet=cabinet_seat, party=belgium.parties.create(label="MR")
    )

    with pytest.raises(ValidationError) as err_proxy:
        minister.full_clean()

    assert err_proxy.value.message_dict == {
        "party": ["The party must belong to the institution's country."]
    }


@pytest.mark.django_db
def test_simple_minister_link(cabinet_seat, renaissance):
    m1 = Minister.objects.create(
        label="m1",
        cabinet=cabinet_seat,
        party=renaissance,
        influence=1.0,
        is_prime_minister=True,
    )
    m2 = Minister.objects.create(
        label="m2", cabinet=cabinet_seat, party=renaissance, influence=0.3
    )

    pm_edge = MinisterLink.objects.create(from_minister=m1, to_minister=m2)
    other_edge = MinisterLink.objects.create(from_minister=m2, to_minister=m1)

    assert len(Minister.objects.all()) == 2
    assert len(m1.neighbours_out.all()) == 1
    assert len(m1.neighbours_in.all()) == 1
    assert len(m2.neighbours_out.all()) == 1
    assert len(m2.neighbours_in.all()) == 1
    assert pm_edge in m1.out_edges.all()
    assert pm_edge in m2.in_edges.all()
    assert other_edge in m1.in_edges.all()
    assert other_edge in m2.out_edges.all()
    assert pm_edge.influence == 1.0
    assert other_edge.influence == 0.3


@pytest.mark.django_db
def test_deleting_simulation_deletes_ministers(
    french_simulation, cabinet_seat, renaissance
):
    Minister.objects.create(label="m1", cabinet=cabinet_seat, party=renaissance)

    french_simulation.delete()

    assert not Minister.objects.exists()
