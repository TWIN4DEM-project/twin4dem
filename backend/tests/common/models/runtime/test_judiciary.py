import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from common.models import Judge, JudgeLink

pytestmark = pytest.mark.django_db  # allows the entire module to access the Django DB


def test_judges_unique_labels_within_same_court(court_seat, renaissance):
    Judge.objects.create(label="judge1", court=court_seat, party=renaissance)

    with pytest.raises(IntegrityError) as err_proxy:
        with transaction.atomic():
            Judge.objects.create(label="judge1", court=court_seat, party=renaissance)

    assert (
        str(err_proxy.value)
        == "UNIQUE constraint failed: common_judge.label, common_judge.court_id"
    )


def test_judge_valid(court_seat, renaissance):
    judge = Judge(label="judge1", court=court_seat, party=renaissance)

    judge.full_clean()


def test_judge_must_belong_to_court(cabinet_seat, renaissance):
    judge = Judge(label="judge1", court=cabinet_seat, party=renaissance)

    with pytest.raises(ValidationError) as err_proxy:
        judge.full_clean()

    assert err_proxy.value.message_dict == {
        "court": ["A judge must belong to a court, not to a cabinet."]
    }


def test_judge_network_contains_expected_influence(court_seat, renaissance):
    judge_from = Judge.objects.create(
        label="judge from", court=court_seat, party=renaissance, influence=0.43
    )
    judge_to = Judge.objects.create(
        label="judge to", court=court_seat, party=renaissance, influence=0.73
    )

    link = JudgeLink.objects.create(from_judge=judge_from, to_judge=judge_to)

    assert link.influence == 0.43
