import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from common.models import MemberOfParliament


@pytest.mark.django_db
def test_members_unique_label_within_same_chamber(chamber_seat, renaissance):
    MemberOfParliament.objects.create(
        label="mp1", chamber=chamber_seat, party=renaissance
    )

    with pytest.raises(IntegrityError) as err_proxy:
        with transaction.atomic():
            MemberOfParliament.objects.create(
                label="mp1", chamber=chamber_seat, party=renaissance
            )

    assert (
        str(err_proxy.value)
        == "UNIQUE constraint failed: common_memberofparliament.label, "
        "common_memberofparliament.chamber_id"
    )


@pytest.mark.django_db
def test_member_valid(chamber_seat, renaissance):
    mp = MemberOfParliament(label="mp1", chamber=chamber_seat, party=renaissance)

    mp.full_clean()


@pytest.mark.django_db
def test_member_must_belong_to_chamber(court_seat, renaissance):
    mp = MemberOfParliament(label="mp1", chamber=court_seat, party=renaissance)

    with pytest.raises(ValidationError) as err_proxy:
        mp.full_clean()

    assert err_proxy.value.message_dict == {
        "chamber": ["A member of parliament must belong to a chamber, not to a court."]
    }


@pytest.mark.django_db
def test_party_members_in_chamber(france, chamber_seat, renaissance):
    modem = france.parties.create(label="MoDem")
    MemberOfParliament.objects.bulk_create(
        [
            MemberOfParliament(label="mp1", chamber=chamber_seat, party=renaissance),
            MemberOfParliament(label="mp2", chamber=chamber_seat, party=renaissance),
            MemberOfParliament(label="mp3", chamber=chamber_seat, party=modem),
        ]
    )

    assert renaissance.mps.count() == 2
    assert chamber_seat.members.count() == 3
