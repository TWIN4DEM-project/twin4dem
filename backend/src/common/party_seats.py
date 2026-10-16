from random import randint, random

from common.models._party import Party
from common.models._party_position import PartyPositionType
from common.models._settings import Country

DEFAULT_PARTY_POSITION = PartyPositionType.INDEPENDENT

MAX_INDEPENDENT_POOL_SHARE = 8
MIN_SPLIT_WEIGHT = 1.0


def party_positions(parties: list[Party]) -> dict[int, PartyPositionType]:
    """The latest position of each party; without one, the party counts as independent."""
    return {
        party.id: (
            PartyPositionType(latest.position)
            if (latest := party.latest_position) is not None
            else DEFAULT_PARTY_POSITION
        )
        for party in parties
    }


def allocate_member_seats(
    pool: int, parties: list[Party], positions: dict[int, PartyPositionType]
) -> dict[int, int]:
    """Split `pool` seats per party while keeping the position blocs coherent."""
    blocs = {
        position_type: [
            party for party in parties if positions[party.id] == position_type
        ]
        for position_type in PartyPositionType
    }
    member_counts: dict[int, int] = {}
    for position_type, seats in bloc_member_seats(pool, blocs).items():
        member_counts.update(split_seats(seats, blocs[position_type]))
    return member_counts


def bloc_member_seats(
    pool: int, blocs: dict[PartyPositionType, list[Party]]
) -> dict[PartyPositionType, int]:
    """Seats per position bloc, so majorities outweigh the opposition."""
    majorities = blocs[PartyPositionType.MAJORITY]
    opposition = blocs[PartyPositionType.OPPOSITION]
    independents = blocs[PartyPositionType.INDEPENDENT]

    independent_seats = (
        randint(0, pool // MAX_INDEPENDENT_POOL_SHARE)
        if independents and pool > 0
        else 0
    )
    remaining = max(pool - independent_seats, 0)

    if majorities and opposition:
        head_gap = len(opposition) - len(majorities)
        opposition_seats = randint(
            0, min(max(0, (remaining - head_gap - 1) // 2), remaining)
        )
        majority_seats = remaining - opposition_seats
    elif majorities:
        majority_seats, opposition_seats = remaining, 0
    elif opposition:
        majority_seats, opposition_seats = 0, remaining
    else:
        independent_seats += remaining
        majority_seats, opposition_seats = 0, 0

    return {
        PartyPositionType.MAJORITY: majority_seats,
        PartyPositionType.OPPOSITION: opposition_seats,
        PartyPositionType.INDEPENDENT: independent_seats,
    }


def split_seats(total: int, bloc: list[Party]) -> dict[int, int]:
    """Split `total` seats across `bloc` roughly proportionally."""
    if not bloc or total <= 0:
        return {party.id: 0 for party in bloc}

    weights = [MIN_SPLIT_WEIGHT + random() for _ in bloc]
    total_weight = sum(weights)
    exact = [weight * total / total_weight for weight in weights]
    seats = [int(value) for value in exact]
    leftover = max(total - sum(seats), 0)
    order = sorted(
        range(len(bloc)),
        key=lambda idx: exact[idx] - seats[idx],
        reverse=True,
    )
    for idx in order[:leftover]:
        seats[idx] += 1
    return {party.id: seat for party, seat in zip(bloc, seats)}


def party_seats(
    country: Country, parliament_size: int
) -> list[tuple[Party, PartyPositionType, int]]:
    """`(party, position, member_count)` tuples filling a chamber of `parliament_size`."""
    parties = list(country.parties.all())
    if not parties:
        return []

    positions = party_positions(parties)
    pool = parliament_size - len(parties)
    member_counts = allocate_member_seats(pool, parties, positions)
    return [(party, positions[party.id], member_counts[party.id]) for party in parties]
