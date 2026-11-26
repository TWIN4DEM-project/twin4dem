import pytest

from common.models import PartyPosition, PartyPositionTimeFrame, PartyPositionType


def _position(party, chamber, position, valid_from=None, valid_to=None):
    """Create a position and, unless both bounds are None, its time frame."""
    party_position = PartyPosition.objects.create(
        party=party, chamber=chamber, position=position
    )
    if valid_from is not None or valid_to is not None:
        PartyPositionTimeFrame.objects.create_for(
            party_position, valid_from=valid_from, valid_to=valid_to
        )
    return party_position


@pytest.mark.django_db
def test_active_frame_beats_a_later_ended_frame(dt, renaissance, assemblee):
    # the ended frame ends far later than the active frame started; under
    # Max("valid_to") the ended position would win, because MAX ignores NULLs
    _position(
        renaissance,
        assemblee,
        PartyPositionType.MAJORITY,
        valid_from=dt(2017),
        valid_to=dt(2099),
    )
    active = _position(
        renaissance, assemblee, PartyPositionType.OPPOSITION, valid_from=dt(2017)
    )

    assert renaissance.latest_position == active


@pytest.mark.django_db
def test_position_with_a_mixed_open_and_ended_frames_ranks_as_active(
    dt, renaissance, assemblee, senat, default_timeline, alternate_timeline
):
    _position(renaissance, senat, PartyPositionType.OPPOSITION, dt(2017), dt(2099))
    mixed = PartyPosition.objects.create(
        party=renaissance, chamber=assemblee, position=PartyPositionType.MAJORITY
    )
    PartyPositionTimeFrame.objects.occupy(
        mixed, dt(2017), dt(2022), [alternate_timeline]
    )
    PartyPositionTimeFrame.objects.occupy(mixed, dt(2017), None, [default_timeline])

    assert renaissance.latest_position == mixed


@pytest.mark.django_db
def test_frameless_position_counts_as_active(dt, renaissance, assemblee):
    _position(
        renaissance,
        assemblee,
        PartyPositionType.MAJORITY,
        valid_from=dt(2017),
        valid_to=dt(2099),
    )
    frameless = PartyPosition.objects.create(
        party=renaissance, chamber=assemblee, position=PartyPositionType.OPPOSITION
    )

    assert renaissance.latest_position == frameless


@pytest.mark.django_db
def test_ended_positions_rank_by_valid_to(dt, renaissance, assemblee):
    _position(renaissance, assemblee, PartyPositionType.MAJORITY, dt(2017), dt(2022))
    newest = _position(
        renaissance, assemblee, PartyPositionType.OPPOSITION, dt(2022), dt(2024)
    )

    assert renaissance.latest_position == newest


@pytest.mark.django_db
def test_party_without_positions_has_no_latest_position(renaissance):
    assert renaissance.latest_position is None


@pytest.mark.django_db
def test_latest_position_uses_a_single_joined_query(
    dt, renaissance, assemblee, django_assert_num_queries
):
    _position(renaissance, assemblee, PartyPositionType.MAJORITY, dt(2017), dt(2022))

    with django_assert_num_queries(1):
        assert renaissance.latest_position is not None


@pytest.mark.django_db
def test_time_frames_lists_the_subjects_frames(dt, renaissance, assemblee):
    position = PartyPosition.objects.create(
        party=renaissance, chamber=assemblee, position=PartyPositionType.MAJORITY
    )
    frame = PartyPositionTimeFrame.objects.create_for(position, valid_from=dt(2017))

    assert list(position.time_frames.all()) == [frame]
