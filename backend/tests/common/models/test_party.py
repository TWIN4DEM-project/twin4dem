import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from common.models import (
    Country,
    Institution,
    InstitutionBranch,
    InstitutionTaxonomy,
    Party,
    PartyPosition,
    PartyPositionType,
    SerializationModel,
)


@pytest.fixture
def senat(france) -> Institution:
    taxonomy = InstitutionTaxonomy.objects.create(
        country=france, branch=InstitutionBranch.LEGISLATIVE, type="senat"
    )
    return Institution.objects.create(
        institution_taxonomy=taxonomy,
        label="Senat2023",
        size=100,
        serialization_model=SerializationModel.CHAMBER,
    )


@pytest.mark.django_db
def test_party_label_is_unique_per_country(france, renaissance):
    with pytest.raises(IntegrityError) as err_proxy:
        with transaction.atomic():
            Party.objects.create(country=france, label="Renaissance")

    assert str(err_proxy.value) == (
        "UNIQUE constraint failed: common_party.country_id, common_party.label"
    )


@pytest.mark.django_db
def test_same_party_label_allowed_in_different_countries(test_settings, renaissance):
    belgium = Country.objects.create(user_settings=test_settings, name="Belgium")

    belgian_party = Party.objects.create(country=belgium, label="Renaissance")

    assert belgian_party.id != renaissance.id


@pytest.mark.django_db
def test_party_holds_different_positions_in_different_chambers(
    renaissance, assemblee, senat
):
    for chamber, position in (
        (assemblee, PartyPositionType.MAJORITY),
        (senat, PartyPositionType.OPPOSITION),
    ):
        party_position = PartyPosition(
            party=renaissance, chamber=chamber, position=position
        )
        party_position.full_clean()
        party_position.save()

    positions = {p.chamber.label: p.position for p in renaissance.positions.all()}

    assert positions == {"RN2022": "majority", "Senat2023": "opposition"}


@pytest.mark.django_db
def test_position_must_be_held_in_a_chamber(renaissance, cabinet):
    party_position = PartyPosition(
        party=renaissance, chamber=cabinet, position=PartyPositionType.MAJORITY
    )

    with pytest.raises(ValidationError) as err_proxy:
        party_position.full_clean()

    assert err_proxy.value.message_dict == {
        "chamber": ["Party positions can only be held in a chamber."]
    }


@pytest.mark.django_db
def test_chamber_must_belong_to_party_country(test_settings, assemblee):
    germany = Country.objects.create(user_settings=test_settings, name="Germany")
    spd = Party.objects.create(country=germany, label="SPD")
    party_position = PartyPosition(
        party=spd, chamber=assemblee, position=PartyPositionType.OPPOSITION
    )

    with pytest.raises(ValidationError) as err_proxy:
        party_position.full_clean()

    assert err_proxy.value.message_dict == {
        "chamber": ["The chamber must belong to the party's country."]
    }


@pytest.mark.django_db
def test_position_rejected_by_validation(renaissance, assemblee):
    party_position = PartyPosition(
        party=renaissance, chamber=assemblee, position="coalition"
    )

    with pytest.raises(ValidationError) as err_proxy:
        party_position.full_clean()

    assert "position" in err_proxy.value.message_dict


@pytest.mark.django_db
def test_position_rejected_by_database(renaissance, assemblee):
    with pytest.raises(IntegrityError) as err_proxy:
        with transaction.atomic():
            PartyPosition.objects.create(
                party=renaissance, chamber=assemblee, position="coalition"
            )

    assert str(err_proxy.value) == "CHECK constraint failed: ck_partyposition_position"


@pytest.mark.django_db
def test_deleting_party_deletes_positions(renaissance, assemblee):
    PartyPosition.objects.create(
        party=renaissance, chamber=assemblee, position=PartyPositionType.MAJORITY
    )

    renaissance.delete()

    assert not PartyPosition.objects.exists()


@pytest.mark.django_db
def test_deleting_chamber_deletes_positions(renaissance, assemblee):
    PartyPosition.objects.create(
        party=renaissance, chamber=assemblee, position=PartyPositionType.MAJORITY
    )

    assemblee.delete()

    assert not PartyPosition.objects.exists()
    assert Party.objects.filter(pk=renaissance.pk).exists()


@pytest.mark.django_db
def test_deleting_country_deletes_parties(france, renaissance):
    france.delete()

    assert not Party.objects.exists()
