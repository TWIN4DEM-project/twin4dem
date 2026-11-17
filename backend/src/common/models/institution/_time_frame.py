from django.db import models

from ..timeline import TimeFrameModel
from ._institution import Institution


class InstitutionTimeFrame(TimeFrameModel):
    """A time frame in which an institution is active."""

    subject = models.ForeignKey(
        to=Institution, on_delete=models.CASCADE, related_name="time_frames"
    )
