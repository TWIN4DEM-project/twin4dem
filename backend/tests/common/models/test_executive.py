import pytest
from django.db import IntegrityError

from common.models import Cabinet, Minister, MinisterLink


@pytest.mark.django_db
def test_cabinet_unique_name():
    Cabinet.objects.create(label="abc", legislative_probability=0.3)

    with pytest.raises(IntegrityError) as err_proxy:
        Cabinet.objects.create(label="abc", legislative_probability=0.3)

    assert str(err_proxy.value) == "UNIQUE constraint failed: common_cabinet.label"


@pytest.mark.django_db
def test_same_cabinet_same_minister_names(test_settings):
    p = test_settings.parties.first()
    c = Cabinet.objects.create(label="abc", legislative_probability=0.3)
    Minister.objects.create(label="m1", cabinet=c, party_id=p.id)
    with pytest.raises(IntegrityError) as err_proxy:
        Minister.objects.create(label="m1", cabinet=c, party_id=p.id)

    assert (
        str(err_proxy.value)
        == "UNIQUE constraint failed: common_minister.label, common_minister.cabinet_id"
    )


@pytest.mark.django_db
def test_different_cabinets_same_minister_names(test_settings):
    p = test_settings.parties.first()
    c1 = Cabinet.objects.create(label="abc", legislative_probability=0.3)
    c2 = Cabinet.objects.create(label="def", legislative_probability=0.3)
    Minister.objects.create(label="m1", cabinet=c1, party_id=p.id)
    Minister.objects.create(label="m1", cabinet=c2, party_id=p.id)

    assert len(Minister.objects.all()) == 2


@pytest.mark.django_db
def test_simple_minister_link(test_settings):
    p = test_settings.parties.first()
    c = Cabinet.objects.create(label="abc", legislative_probability=0.3)
    m1 = Minister.objects.create(
        label="m1", cabinet=c, party_id=p.id, influence=1.0, is_prime_minister=True
    )
    m2 = Minister.objects.create(label="m2", cabinet=c, party_id=p.id, influence=0.3)

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
