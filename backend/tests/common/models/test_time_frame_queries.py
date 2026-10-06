from datetime import datetime, UTC

import pytest

from common.models import (
    Institution,
    InstitutionBranch,
    PartyPosition,
    PartyPositionType,
    SerializationModel,
    TimeFrame,
    VirtualTimeline,
    is_active,
    party_position_at,
)


def _dt(year: int, month: int = 1, day: int = 1) -> datetime:
    return datetime(year, month, day, tzinfo=UTC)


@pytest.fixture
def alternate(test_settings) -> VirtualTimeline:
    return VirtualTimeline.objects.create(
        user_settings=test_settings, label="alternate"
    )


@pytest.fixture
def philippe_cabinets(french_taxonomy, default_timeline) -> dict[str, Institution]:
    cabinets = {}
    for label, valid_from, valid_to, timelines in (
        ("Philippe I", _dt(2017, 5, 15), _dt(2017, 6, 21), [default_timeline]),
        ("Philippe II", _dt(2017, 6, 21), _dt(2020, 7, 3), []),
    ):
        cabinets[label] = Institution.objects.create(
            institution_taxonomy=french_taxonomy[InstitutionBranch.EXECUTIVE],
            label=label,
            size=15,
            serialization_model=SerializationModel.CABINET,
        )
        TimeFrame.objects.occupy(cabinets[label], valid_from, valid_to, timelines)
    return cabinets


@pytest.mark.django_db
def test_institution_without_frames_is_always_active(court, default_timeline):
    assert is_active(court, default_timeline, _dt(1900))
    assert is_active(court, default_timeline, _dt(2100))


@pytest.mark.django_db
@pytest.mark.parametrize(
    "at,expected",
    [
        (_dt(2017, 5, 14), False),
        (_dt(2017, 5, 15), True),
        (_dt(2017, 6, 20), True),
        (_dt(2017, 6, 21), False),
    ],
    ids=["before", "first day", "last day", "end is excluded"],
)
def test_is_active_within_bounds(philippe_cabinets, default_timeline, at, expected):
    assert is_active(philippe_cabinets["Philippe I"], default_timeline, at) is expected


@pytest.mark.django_db
def test_is_active_only_on_linked_timelines(philippe_cabinets, alternate):
    assert not is_active(philippe_cabinets["Philippe I"], alternate, _dt(2017, 6, 1))


@pytest.mark.django_db
def test_frame_for_all_timelines_is_active_on_each(
    philippe_cabinets, default_timeline, alternate
):
    for timeline in (default_timeline, alternate):
        assert is_active(philippe_cabinets["Philippe II"], timeline, _dt(2018))


@pytest.mark.django_db
@pytest.mark.parametrize(
    "at,expected",
    [(_dt(2016), None), (_dt(2021), "majority"), (_dt(2023), "opposition")],
)
def test_party_position_at(renaissance, assemblee, default_timeline, at, expected):
    for position, valid_from, valid_to in (
        (PartyPositionType.MAJORITY, _dt(2017, 6, 21), _dt(2022, 6, 19)),
        (PartyPositionType.OPPOSITION, _dt(2022, 6, 19), None),
    ):
        party_position = PartyPosition.objects.create(
            party=renaissance, chamber=assemblee, position=position
        )
        TimeFrame.objects.occupy(party_position, valid_from, valid_to)

    party_position = party_position_at(renaissance, assemblee, default_timeline, at)

    assert (party_position.position if party_position else None) == expected
