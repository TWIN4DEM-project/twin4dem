from django.db import models

from common.models.timeline import TimeFrameSubject, TimeFrameModel


class PartyLeadership(TimeFrameSubject):
    person = models.ForeignKey(
        "Person", on_delete=models.CASCADE, null=False, related_name="party_leadership"
    )
    party = models.ForeignKey(
        "Party", on_delete=models.CASCADE, null=False, related_name="leaders"
    )
    sibling_fields = ("person",)

    @property
    def time_frames(self) -> models.Manager:
        return self.stints

    def time_frame_user_settings_id(self) -> int:
        return self.party.country.user_settings_id

    def sibling_time_frames(self) -> models.QuerySet:
        return self.stints.filter(subject__in=self.siblings())


class PartyLeadershipStint(TimeFrameModel):
    subject = models.ForeignKey(
        "PartyLeadership", on_delete=models.CASCADE, null=False, related_name="stints"
    )
