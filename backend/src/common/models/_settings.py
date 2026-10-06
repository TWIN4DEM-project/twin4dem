from django.db import models
from django.conf import settings
from django.db.models import Q


class UserSettings(models.Model):
    """A global context: the simulated 'world' of a user (one user, many contexts)."""

    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        to=settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="user_settings",
    )
    label = models.CharField(null=False, max_length=50, default="default")
    # defaults for the institutions (cabinets, chambers, courts) of this context
    government_probability_for = models.FloatField(default=0.5)
    parliament_majority_probability_for = models.FloatField(default=0.5)
    parliament_opposition_probability_for = models.FloatField(default=0.5)
    court_probability_for = models.FloatField(default=0.5)
    # general parameters
    office_retention_sensitivity = models.FloatField(default=5.0)
    social_influence_susceptibility = models.FloatField(default=0.5)
    abstention_threshold = models.FloatField(null=False, default=0.2)
    data_update_frequency = models.PositiveSmallIntegerField(null=False, default=10)
    legislative_path_probability = models.FloatField(null=False, default=0.5)

    def __str__(self):
        return f"{self.label}(id={self.id})"

    class Meta:
        verbose_name = "User settings"
        verbose_name_plural = "User settings"

        constraints = [
            models.UniqueConstraint(
                name="uq_usersettings_user_label", fields=["user", "label"]
            ),
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
            models.CheckConstraint(
                name="ck_usersettings_parliament_majority_probability_for",
                condition=Q(parliament_majority_probability_for__gte=0.0)
                & Q(parliament_majority_probability_for__lte=1.0),
            ),
            models.CheckConstraint(
                name="ck_usersettings_parliament_opposition_probability_for",
                condition=Q(parliament_opposition_probability_for__gte=0.0)
                & Q(parliament_opposition_probability_for__lte=1.0),
            ),
            models.CheckConstraint(
                name="ck_usersettings_court_probability_for",
                condition=Q(court_probability_for__gte=0.0)
                & Q(court_probability_for__lte=1.0),
            ),
            models.CheckConstraint(
                name="ck_usersettings_office_retention_sensitivity",
                condition=Q(office_retention_sensitivity__gte=5.0),
            ),
            models.CheckConstraint(
                name="ck_usersettings_social_influence_susceptibility",
                condition=Q(social_influence_susceptibility__gte=0.0)
                & Q(social_influence_susceptibility__lte=1.0),
            ),
        ]


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


class Country(models.Model):
    id = models.AutoField(primary_key=True)
    user_settings = models.ForeignKey(
        to=UserSettings, on_delete=models.CASCADE, related_name="countries"
    )
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Countries"
        constraints = [
            models.UniqueConstraint(
                name="uq_country_user_settings_name",
                fields=["user_settings", "name"],
            )
        ]


class InstitutionBranch(models.TextChoices):
    EXECUTIVE = "executive"
    LEGISLATIVE = "legislative"
    JUDICIARY = "judiciary"


class InstitutionTaxonomy(models.Model):
    """A type of institution that a country supports (e.g. 'cabinet', 'senate')."""

    id = models.AutoField(primary_key=True)
    country = models.ForeignKey(
        to=Country, on_delete=models.CASCADE, related_name="taxonomy"
    )
    branch = models.CharField(choices=InstitutionBranch.choices)
    type = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.country}: {self.type} ({self.branch})"

    class Meta:
        verbose_name_plural = "Institution taxonomies"
        constraints = [
            models.UniqueConstraint(
                name="uq_institutiontaxonomy_country_type",
                fields=["country", "type"],
            ),
            models.CheckConstraint(
                name="ck_institutiontaxonomy_branch",
                condition=Q(branch__in=InstitutionBranch.values),
            ),
        ]
