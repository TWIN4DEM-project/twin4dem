from django.db import models

from common.models import Country, TimeFrameModel, TimeFrameSubject


class StubSubject(TimeFrameSubject):
    country = models.ForeignKey(
        to=Country, on_delete=models.CASCADE, related_name="stub_subjects"
    )
    group = models.CharField(max_length=50)
    label = models.CharField(max_length=50)

    sibling_fields = ("group",)

    def time_frame_user_settings_id(self) -> int:
        """The global context whose timelines the subject's frames apply to."""
        return self.country.user_settings_id


class StubTimeFrame(TimeFrameModel):
    subject = models.ForeignKey(
        to=StubSubject, on_delete=models.CASCADE, related_name="time_frames"
    )
