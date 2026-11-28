from django.db import models

from common.models import Country, TimeFrameModel, TimeFrameSubject


class StubSubject(TimeFrameSubject):
    country = models.ForeignKey(
        to=Country, on_delete=models.CASCADE, related_name="stub_subjects"
    )
    group = models.CharField(max_length=50)
    label = models.CharField(max_length=50)

    sibling_fields = ("group",)

    def sibling_time_frames(self) -> models.QuerySet:
        """The time frames of this subject's siblings."""
        return StubTimeFrame.objects.filter(subject__in=self.siblings())


class StubTimeFrame(TimeFrameModel):
    subject = models.ForeignKey(
        to=StubSubject, on_delete=models.CASCADE, related_name="time_frames"
    )
