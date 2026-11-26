from django.db import models

from common.models.timeline import TimeFrameSubject


class PartyMembership(TimeFrameSubject):
    person = models.ForeignKey(
        "Person", on_delete=models.CASCADE, related_name="party_membership"
    )
    party = models.ForeignKey(
        "Party", on_delete=models.CASCADE, related_name="party_members"
    )
