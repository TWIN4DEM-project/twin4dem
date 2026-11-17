from django.db import models

from ..timeline import TimeFrameModel
from ._party_position import PartyPosition


class PartyPositionTimeFrame(TimeFrameModel):
    """A time frame in which a party holds a position in a chamber."""

    subject = models.ForeignKey(
        to=PartyPosition, on_delete=models.CASCADE, related_name="time_frames"
    )
