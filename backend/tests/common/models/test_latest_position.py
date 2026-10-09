from datetime import UTC, datetime

import pytest

from common.models import (
    ChamberPayload,
    Institution,
    InstitutionBranch,
    InstitutionKind,
    PartyPosition,
    PartyPositionType,
    TimeFrame,
)


def _dt(year: int, month: int = 1, day: int = 1) -> datetime:
    return datetime(year, month, day, tzinfo=UTC)


@pytest.fixture
def chamber(france) -> Institution:
    kind = InstitutionKind.objects.create(
        country=france,
        branch=InstitutionBranch.LEGISLATIVE,
        institution_name="assemblee nationale",
    )
    return Institution.objects.create(
        kind=kind, label="AN2022", size=100, payload=ChamberPayload()
    )


def _position(party, chamber, position, valid_from=None, valid_to=None):
    """Create a position and, unless both bounds are None, its time frame."""
    party_position = PartyPosition.objects.create(
        party=party, chamber=chamber, position=position
    )
    if valid_from is not None or valid_to is not None:
        TimeFrame.objects.create_for(
            party_position, valid_from=valid_from, valid_to=valid_to
        )
    return party_position


@pytest.mark.django_db
def test_active_frame_beats_a_later_ended_frame(renaissance, chamber):
    # the ended frame ends far later than the active frame started; under
    # Max("valid_to") the ended position would win, because MAX ignores NULLs
    _position(
        renaissance,
        chamber,
        PartyPositionType.MAJORITY,
        valid_from=_dt(2017),
        valid_to=_dt(2099),
    )
    active = _position(
        renaissance, chamber, PartyPositionType.OPPOSITION, valid_from=_dt(2017)
    )

    assert renaissance.latest_position == active


@pytest.mark.django_db
def test_frameless_position_counts_as_active(renaissance, chamber):
    _position(
        renaissance,
        chamber,
        PartyPositionType.MAJORITY,
        valid_from=_dt(2017),
        valid_to=_dt(2099),
    )
    frameless = PartyPosition.objects.create(
        party=renaissance, chamber=chamber, position=PartyPositionType.OPPOSITION
    )

    assert renaissance.latest_position == frameless


@pytest.mark.django_db
def test_ended_positions_rank_by_valid_to(renaissance, chamber):
    _position(renaissance, chamber, PartyPositionType.MAJORITY, _dt(2017), _dt(2022))
    newest = _position(
        renaissance, chamber, PartyPositionType.OPPOSITION, _dt(2022), _dt(2024)
    )

    assert renaissance.latest_position == newest


@pytest.mark.django_db
def test_party_without_positions_has_no_latest_position(renaissance):
    assert renaissance.latest_position is None


@pytest.mark.django_db
def test_time_frames_lists_the_subjects_frames(renaissance, chamber):
    position = PartyPosition.objects.create(
        party=renaissance, chamber=chamber, position=PartyPositionType.MAJORITY
    )
    frame = TimeFrame.objects.create_for(position, valid_from=_dt(2017))

    assert list(position.time_frames) == [frame]


@pytest.mark.django_db
def test_subject_type_of_returns_the_declared_tag(renaissance, chamber):
    position = PartyPosition.objects.create(
        party=renaissance, chamber=chamber, position=PartyPositionType.MAJORITY
    )

    assert position.time_frame_subject_type == "party_position"
