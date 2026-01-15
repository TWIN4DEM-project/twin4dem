import pytest

from django.db import IntegrityError
from common.models._judiciary import Court, Judge, JudgeLink

pytestmark = pytest.mark.django_db  # allows the entire module to access the Django DB


@pytest.fixture
def party(test_settings):
    return test_settings.parties.first()


def test_court_unique_labels():
    Court.objects.create(label="abc")

    with pytest.raises(IntegrityError) as err_proxy:
        Court.objects.create(label="abc")

    assert str(err_proxy.value) == "UNIQUE constraint failed: common_court.label"


def test_judges_unique_labels_within_same_court(party):
    court = Court.objects.create(label="abc")
    Judge.objects.create(label="judge1", court=court, party=party)
    with pytest.raises(IntegrityError) as err_proxy:
        Judge.objects.create(label="judge1", court=court, party=party)

    assert (
        str(err_proxy.value)
        == "UNIQUE constraint failed: common_judge.label, common_judge.court_id"
    )


def test_judges_same_label_different_courts(party):
    c1 = Court.objects.create(label="abc")
    c2 = Court.objects.create(label="def")
    Judge.objects.create(label="j1", court=c1, party_id=party.id)

    Judge.objects.create(label="j1", court=c2, party_id=party.id)

    assert len(Judge.objects.all()) == 2


@pytest.mark.parametrize("value", [-0.01, 1.01])
def test_court_probability_for_out_of_range(value):
    with pytest.raises(IntegrityError) as err_proxy:
        Court.objects.create(label="abc", probability_for=value)

    assert (
        str(err_proxy.value)
        == "CHECK constraint failed: ck_court_probability_for_is_prob"
    )


def test_judge_network_contains_expected_influence(party):
    court = Court.objects.create(label="test court")
    judge_from = Judge.objects.create(
        label="judge from", court=court, party=party, influence=0.43
    )
    judge_to = Judge.objects.create(
        label="judge to", court=court, party=party, influence=0.73
    )

    link = JudgeLink.objects.create(from_judge=judge_from, to_judge=judge_to)

    assert link.influence == 0.43
