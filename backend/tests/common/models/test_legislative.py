import pytest

from django.db import IntegrityError
from common.models._legislative import Parliament, MemberOfParliament


@pytest.mark.django_db
def test_parliament_unique_labels():
    Parliament.objects.create(label="abc")

    with pytest.raises(IntegrityError) as err_proxy:
        Parliament.objects.create(label="abc")

    assert str(err_proxy.value) == "UNIQUE constraint failed: common_parliament.label"


@pytest.mark.django_db
def test_parliament_members_unique_label_within_same_parliament(test_settings):
    party = test_settings.parties.first()
    parliament = Parliament.objects.create(label="abc")
    MemberOfParliament.objects.create(label="mp1", parliament=parliament, party=party)
    with pytest.raises(IntegrityError) as err_proxy:
        MemberOfParliament.objects.create(
            label="mp1", parliament=parliament, party=party
        )

    assert (
        str(err_proxy.value)
        == "UNIQUE constraint failed: common_memberofparliament.label, common_memberofparliament.parliament_id"
    )


@pytest.mark.django_db
def test_parliament_members_same_label_two_parliaments(test_settings):
    party = test_settings.parties.first()
    p1 = Parliament.objects.create(label="abc")
    p2 = Parliament.objects.create(label="def")
    MemberOfParliament.objects.create(label="m1", parliament=p1, party_id=party.id)
    MemberOfParliament.objects.create(label="m1", parliament=p2, party_id=party.id)

    assert len(MemberOfParliament.objects.all()) == 2
