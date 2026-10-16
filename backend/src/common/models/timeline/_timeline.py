from django.db import models

from .._settings import UserSettings


class VirtualTimeline(models.Model):
    """One of the alternative timelines a global context can be simulated on."""

    DEFAULT_LABEL = "default"

    id = models.AutoField(primary_key=True)
    user_settings = models.ForeignKey(
        to=UserSettings, on_delete=models.CASCADE, related_name="timelines"
    )
    label = models.CharField(max_length=50, default=DEFAULT_LABEL)

    def __str__(self):
        return f"{self.label}(id={self.id})"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                name="uq_virtualtimeline_user_settings_label",
                fields=["user_settings", "label"],
            )
        ]
