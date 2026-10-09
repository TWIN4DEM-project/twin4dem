from common.models import Party, PartyPosition, PartyPositionType
from common.party_seats import (
    allocate_member_seats,
    bloc_member_seats,
    party_positions,
    party_seats,
    split_seats,
)


def make_party(id_: int) -> Party:
    party = Party(country_id=1, label=f"party-{id_}")
    party.id = id_
    return party


def blocs_with(majorities=(), opposition=(), independents=()) -> dict:
    def bloc(ids):
        return [make_party(id_) for id_ in ids]

    return {
        PartyPositionType.MAJORITY: bloc(majorities),
        PartyPositionType.OPPOSITION: bloc(opposition),
        PartyPositionType.INDEPENDENT: bloc(independents),
    }


def test_bloc_member_seats_without_parties_pool_to_independents():
    seats = bloc_member_seats(10, blocs_with())

    assert seats == {
        PartyPositionType.MAJORITY: 0,
        PartyPositionType.OPPOSITION: 0,
        PartyPositionType.INDEPENDENT: 10,
    }


def test_bloc_member_seats_favor_the_majority_bloc():
    seats = bloc_member_seats(50, blocs_with(majorities=[1], opposition=[2, 3]))

    assert seats[PartyPositionType.MAJORITY] + seats[PartyPositionType.OPPOSITION] == 50
    assert seats[PartyPositionType.MAJORITY] >= seats[PartyPositionType.OPPOSITION]


def test_bloc_member_seats_give_majority_everything_alone():
    seats = bloc_member_seats(20, blocs_with(majorities=[1]))

    assert seats == {
        PartyPositionType.MAJORITY: 20,
        PartyPositionType.OPPOSITION: 0,
        PartyPositionType.INDEPENDENT: 0,
    }


def test_bloc_member_seats_give_opposition_everything_alone():
    seats = bloc_member_seats(20, blocs_with(opposition=[1]))

    assert seats == {
        PartyPositionType.MAJORITY: 0,
        PartyPositionType.OPPOSITION: 20,
        PartyPositionType.INDEPENDENT: 0,
    }


def test_bloc_member_seats_reserve_a_share_for_independents():
    seats = bloc_member_seats(20, blocs_with(majorities=[1], independents=[3]))

    assert (
        seats[PartyPositionType.MAJORITY] + seats[PartyPositionType.INDEPENDENT] == 20
    )
    assert 0 <= seats[PartyPositionType.INDEPENDENT] <= 2


def test_zero_pool_leaves_independents_without_seats():
    seats = bloc_member_seats(0, blocs_with(independents=[1]))

    assert seats == {
        PartyPositionType.MAJORITY: 0,
        PartyPositionType.OPPOSITION: 0,
        PartyPositionType.INDEPENDENT: 0,
    }


def test_split_seats_without_parties_is_empty():
    assert split_seats(10, []) == {}


def test_split_seats_with_a_non_positive_total_are_zero():
    assert split_seats(0, [make_party(1)]) == {1: 0}


def test_split_seats_distribute_the_total():
    parties = [make_party(1), make_party(2), make_party(3)]

    seats = split_seats(10, parties)

    assert sum(seats.values()) == 10
    assert all(seat >= 0 for seat in seats.values())


def test_allocate_member_seats_cover_the_pool():
    parties = [make_party(1), make_party(2), make_party(3)]
    positions = {
        1: PartyPositionType.MAJORITY,
        2: PartyPositionType.OPPOSITION,
        3: PartyPositionType.INDEPENDENT,
    }

    counts = allocate_member_seats(50, parties, positions)

    assert sum(counts.values()) == 50


def test_positions_default_to_independent(france, db):
    unpositioned = Party.objects.create(country=france, label="unpositioned")

    assert party_positions(list(france.parties.all())) == {
        unpositioned.id: PartyPositionType.INDEPENDENT
    }


def test_positions_read_the_latest_position(renaissance, assemblee, db):
    PartyPosition.objects.create(
        party=renaissance, chamber=assemblee, position=PartyPositionType.MAJORITY
    )

    assert party_positions([renaissance]) == {
        renaissance.id: PartyPositionType.MAJORITY
    }


def test_party_seats_without_parties_is_empty(france, db):
    assert party_seats(france, 100) == []


def test_party_seats_fill_the_chamber(renaissance, assemblee, france, db):
    opposition = Party.objects.create(country=france, label="opposition")
    PartyPosition.objects.create(
        party=renaissance, chamber=assemblee, position=PartyPositionType.MAJORITY
    )
    PartyPosition.objects.create(
        party=opposition, chamber=assemblee, position=PartyPositionType.OPPOSITION
    )

    seats = party_seats(france, 100)
    by_label = {party.label: (position, count) for party, position, count in seats}

    assert by_label["Renaissance"][0] == PartyPositionType.MAJORITY
    assert by_label["opposition"][0] == PartyPositionType.OPPOSITION
    assert by_label["Renaissance"][1] + by_label["opposition"][1] == 98
