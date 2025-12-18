from django.core.exceptions import ValidationError
from django.db import models
from django.conf import settings
from django.db.models import Q, Sum


class UserSettings(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.OneToOneField(to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    label = models.CharField(null=False, max_length=50, default="default")
    government_size = models.PositiveSmallIntegerField(null=False, default=15)
    government_connectivity_degree = models.PositiveSmallIntegerField(
        null=False, default=3
    )
    government_probability_for = models.FloatField(default=0.5)
    parliament_size = models.PositiveSmallIntegerField(null=False, default=100)
    court_size = models.PositiveSmallIntegerField(null=False, default=5)
    abstention_threshold = models.FloatField(null=False, default=0.2)
    data_update_frequency = models.PositiveSmallIntegerField(null=False, default=10)
    legislative_path_probability = models.FloatField(null=False, default=0.5)

    def __str__(self):
        return f"{self.label}(id={self.id})"

    def clean(self):
        super().clean()
        parties = self.parties.all()
        if not parties.exists():
            return

        total_members = parties.aggregate(total=Sum("member_count"))["total"] or 0

        if total_members != self.parliament_size:
            raise ValidationError(
                {
                    "parliament_size": (
                        f"Sum of party member_count ({total_members}) "
                        f"must equal parliament_size ({self.parliament_size})."
                    )
                }
            )

    class Meta:
        verbose_name = "User settings"
        verbose_name_plural = "User settings"

        constraints = [
            models.CheckConstraint(
                name="ck_usersettings_abstention_threshold",
                condition=Q(abstention_threshold__gte=0.0)
                & Q(abstention_threshold__lte=1.0),
            ),
            models.CheckConstraint(
                name="ck_usersettings_legislative_path_probability",
                condition=Q(legislative_path_probability__gte=0.0)
                & Q(legislative_path_probability__lte=1.0),
            ),
            models.CheckConstraint(
                name="ck_usersettings_government_probability_for",
                condition=Q(government_probability_for__gte=0.0)
                & Q(government_probability_for__lte=1.0),
            ),
        ]


class PartySettings(models.Model):
    class Meta:
        ordering = ["position", "member_count"]

    class PartyPosition(models.TextChoices):
        MAJORITY = "majority"
        OPPOSITION = "opposition"
        INDEPENDENT = "independent"

    id = models.AutoField(primary_key=True)
    user_settings = models.ForeignKey(
        to=UserSettings, related_name="parties", on_delete=models.CASCADE
    )
    label = models.CharField(max_length=50)
    member_count = models.PositiveSmallIntegerField()
    position = models.CharField(choices=PartyPosition.choices)

    def clean(self):
        super().clean()

        if self.user_settings_id is None:
            return
        self.user_settings.clean()
