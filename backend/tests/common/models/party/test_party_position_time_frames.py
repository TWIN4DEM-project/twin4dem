from datetime import datetime, UTC

import pytest
from django.core.exceptions import ValidationError

from common.models import (
    PartyPosition,
    PartyPositionTimeFrame,
    PartyPositionType,
    party_position_at,
)


pytestmark = pytest.mark.django_db


def _dt(year: int, month: int = 1, day: int = 1) -> datetime:
    return datetime(year, month, day, tzinfo=UTC)


def _position(
    party,
    chamber,
    position,
    valid_from=None,
    valid_to=None,
    timelines=(),
):
    party_position = PartyPosition.objects.create(
        party=party, chamber=chamber, position=position
    )
    if valid_from is not None or valid_to is not None or timelines:
        PartyPositionTimeFrame.objects.occupy(
            party_position, valid_from, valid_to, timelines
        )
    return party_position


def test_same_party_and_chamber_positions_may_not_overlap(
    renaissance, assemblee, default_timeline, alternate_timeline
):
    _position(
        renaissance,
        assemblee,
        PartyPositionType.MAJORITY,
        _dt(2020),
        _dt(2022),
        [default_timeline],
    )
    second = _position(
        renaissance,
        assemblee,
        PartyPositionType.OPPOSITION,
        _dt(2030),
        _dt(2031),
        [alternate_timeline],
    )

    with pytest.raises(ValidationError) as err_proxy:
        PartyPositionTimeFrame.objects.occupy(
            second, _dt(2021), _dt(2023), [default_timeline]
        )

    assert err_proxy.value.messages == [
        "Overlaps with 'Renaissance' (majority) [2020-01-01 00:00:00+00:00, 2022-01-01 00:00:00+00:00) "
        "on timeline 'default'."
    ]


def test_positions_in_different_chambers_may_overlap(renaissance, assemblee, senat):
    _position(renaissance, assemblee, PartyPositionType.MAJORITY, _dt(2020), _dt(2022))
    _position(renaissance, senat, PartyPositionType.OPPOSITION, _dt(2020), _dt(2022))

    assert PartyPositionTimeFrame.objects.count() == 2


def test_positions_of_different_parties_may_overlap(france, renaissance, assemblee):
    modem = france.parties.create(label="MoDem")
    _position(renaissance, assemblee, PartyPositionType.MAJORITY, _dt(2020), _dt(2022))
    _position(modem, assemblee, PartyPositionType.MAJORITY, _dt(2020), _dt(2022))

    assert PartyPositionTimeFrame.objects.count() == 2


def test_frameless_position_blocks_a_same_party_and_chamber_sibling(
    renaissance, assemblee
):
    _position(renaissance, assemblee, PartyPositionType.MAJORITY)
    opposition = PartyPosition(
        party=renaissance,
        chamber=assemblee,
        position=PartyPositionType.OPPOSITION,
    )

    with pytest.raises(ValidationError) as err_proxy:
        opposition.full_clean()

    assert err_proxy.value.message_dict == {
        "chamber": [
            "'Renaissance' holds the majority position in 'RN2022' without a time "
            "frame, i.e. at all times on all timelines: no other position can be "
            "added."
        ]
    }


def test_party_position_at_uses_frames(
    renaissance, assemblee, default_timeline, django_assert_num_queries
):
    _position(
        renaissance,
        assemblee,
        PartyPositionType.MAJORITY,
        _dt(2017, 6, 21),
        _dt(2022, 6, 19),
    )
    _position(
        renaissance,
        assemblee,
        PartyPositionType.OPPOSITION,
        _dt(2022, 6, 19),
    )

    with django_assert_num_queries(1):
        assert (
            party_position_at(
                renaissance, assemblee, default_timeline, _dt(2021)
            ).position
            == PartyPositionType.MAJORITY
        )
    assert (
        party_position_at(renaissance, assemblee, default_timeline, _dt(2023)).position
        == PartyPositionType.OPPOSITION
    )


def test_party_position_at_honours_timeline_links(
    renaissance, assemblee, default_timeline, alternate_timeline
):
    position = _position(
        renaissance,
        assemblee,
        PartyPositionType.MAJORITY,
        _dt(2020),
        _dt(2022),
        [default_timeline],
    )

    assert party_position_at(renaissance, assemblee, default_timeline, _dt(2021)) == (
        position
    )
    assert party_position_at(renaissance, assemblee, alternate_timeline, _dt(2021)) is (
        None
    )
