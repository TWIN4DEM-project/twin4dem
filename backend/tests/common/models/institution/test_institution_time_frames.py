import pytest
from django.core.exceptions import ValidationError

from common.models import (
    Institution,
    InstitutionBranch,
    InstitutionTimeFrame,
)


pytestmark = pytest.mark.django_db


def _create(kind, label, valid_from=None, valid_to=None, timelines=()):
    institution = Institution.objects.create(kind=kind, label=label, size=10)
    if valid_from is not None or valid_to is not None or timelines:
        InstitutionTimeFrame.objects.occupy(
            institution, valid_from, valid_to, timelines
        )
    return institution


def test_same_kind_institutions_may_not_overlap(
    dt, french_taxonomy, default_timeline, alternate_timeline
):
    cabinet = french_taxonomy[InstitutionBranch.EXECUTIVE]
    _create(cabinet, "Philippe", dt(2020), dt(2022), [default_timeline])
    second = _create(cabinet, "Borne", dt(2030), dt(2031), [alternate_timeline])

    with pytest.raises(ValidationError) as err_proxy:
        InstitutionTimeFrame.objects.occupy(
            second, dt(2021), dt(2023), [default_timeline]
        )

    assert err_proxy.value.messages == [
        "Overlaps with 'Philippe' [2020-01-01 00:00:00+00:00, 2022-01-01 00:00:00+00:00) "
        "on timeline 'default'."
    ]


def test_different_kinds_may_overlap(dt, cabinet, assemblee):
    InstitutionTimeFrame.objects.occupy(cabinet, dt(2020), dt(2022))
    InstitutionTimeFrame.objects.occupy(assemblee, dt(2020), dt(2022))

    assert InstitutionTimeFrame.objects.count() == 2


def test_frameless_institution_blocks_a_same_kind_sibling(french_taxonomy, cabinet):
    second = Institution(
        kind=french_taxonomy[InstitutionBranch.EXECUTIVE], label="Borne", size=10
    )

    with pytest.raises(ValidationError) as err_proxy:
        second.full_clean()

    assert err_proxy.value.message_dict == {
        "kind": [
            "'Castex' has no time frame, so it is active at all times on all "
            "timelines: no other institution of type 'cabinet' can be added."
        ]
    }
