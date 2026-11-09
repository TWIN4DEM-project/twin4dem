from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime
from typing import NamedTuple

from common.models import Party, PartyPosition, TimeFrame, TimeFrameSubjectType


class PositionSummary(NamedTuple):
    latest: PartyPosition | None
    active: PartyPosition | None


def _newest(
    positions: list[PartyPosition], ends: dict[int, list[datetime | None]]
) -> PartyPosition | None:
    """
    Takes a list of positions and returns the one that ends last.
    """

    def rank(position: PartyPosition) -> tuple:
        own_ends = ends[position.pk]
        end = None if not own_ends or None in own_ends else max(own_ends)
        return end is None, end, position.pk

    return max(positions, key=rank, default=None)


def position_summaries(
    parties: Sequence[Party], at: datetime
) -> dict[int, PositionSummary]:
    """
    Find the latest and the active position of each party.
    """
    positions = list(
        PartyPosition.objects.filter(party_id__in=[party.pk for party in parties])
    )
    ends = defaultdict(list)
    covering_ends = defaultdict(list)
    for subject_id, valid_from, valid_to in TimeFrame.objects.filter(
        subject_type=TimeFrameSubjectType.PARTY_POSITION,
        subject_id__in=[position.pk for position in positions],
    ).values_list("subject_id", "valid_from", "valid_to"):
        ends[subject_id].append(valid_to)
        if (valid_from is None or valid_from <= at) and (
            valid_to is None or at < valid_to
        ):
            covering_ends[subject_id].append(valid_to)

    by_party = defaultdict(list)
    for position in positions:
        by_party[position.party_id].append(position)

    summaries = {}
    for party in parties:
        own = by_party[party.pk]
        active = [p for p in own if not ends[p.pk] or covering_ends[p.pk]]
        summaries[party.pk] = PositionSummary(
            latest=_newest(own, ends), active=_newest(active, covering_ends)
        )
    return summaries
