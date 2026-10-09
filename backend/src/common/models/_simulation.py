from typing import Union, Optional

from django.contrib.postgres.indexes import GinIndex
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django_pydantic_field import SchemaField
from pydantic import BaseModel

from common.models._institution import Institution
from common.models._settings import Country, UserSettings, VirtualTimeline
from common.models._timeframe import is_active


class Simulation(models.Model):
    """A simulation of a country on a virtual timeline, at a point in time."""

    class Status(models.TextChoices):
        NEW = "new"
        RUNNING = "running"
        COMPLETE = "complete"
        ERROR = "error"

    id = models.AutoField(primary_key=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(choices=Status.choices, default=Status.NEW)
    current_step = models.PositiveBigIntegerField(default=0)
    office_retention_sensitivity = models.FloatField(default=5.0)
    social_influence_susceptibility = models.FloatField(default=0.5)

    user_settings = models.ForeignKey(
        to=UserSettings, on_delete=models.CASCADE, related_name="simulations"
    )
    # where and when the simulation takes place; a country or timeline that was
    # simulated cannot be deleted on its own
    country = models.ForeignKey(
        to=Country, on_delete=models.RESTRICT, related_name="simulations"
    )
    timeline = models.ForeignKey(
        to=VirtualTimeline, on_delete=models.RESTRICT, related_name="simulations"
    )
    valid_at = models.DateTimeField(default=timezone.now)

    def clean(self):
        super().clean()
        errors = {}
        if self.user_settings_id is not None:
            if (
                self.country_id is not None
                and self.country.user_settings_id != self.user_settings_id
            ):
                errors["country"] = "The country must belong to the user settings."
            if (
                self.timeline_id is not None
                and self.timeline.user_settings_id != self.user_settings_id
            ):
                errors["timeline"] = "The timeline must belong to the user settings."
        if errors:
            raise ValidationError(errors)

    class Meta:
        constraints = [
            models.CheckConstraint(
                name="ck_simulation_office_retention_sensitivity",
                condition=models.Q(office_retention_sensitivity__gte=5.0),
            ),
            models.CheckConstraint(
                name="ck_simulation_social_influence_susceptibility",
                condition=models.Q(social_influence_susceptibility__gte=0.0)
                & models.Q(social_influence_susceptibility__lte=1.0),
            ),
        ]


class SimulationInstitution(models.Model):
    """
    An institution taking part in a simulation. The agents of the simulation
    (ministers, MPs, judges) belong to it, so every simulation has its own agents
    while the institutions themselves are shared.
    """

    id = models.AutoField(primary_key=True)
    simulation = models.ForeignKey(
        to=Simulation, on_delete=models.CASCADE, related_name="institutions"
    )
    institution = models.ForeignKey(
        to=Institution, on_delete=models.RESTRICT, related_name="simulations"
    )

    def __str__(self):
        return f"{self.institution.label} in simulation {self.simulation_id}"

    def clean(self):
        super().clean()

        simulation = self.simulation
        institution = self.institution

        if institution.kind.country_id != simulation.country_id:
            raise ValidationError(
                {"institution": "The institution must belong to the simulated country."}
            )

        same_model = SimulationInstitution.objects.filter(
            simulation_id=self.simulation_id, institution__kind=institution.kind
        ).exclude(pk=self.pk)
        if same_model.exists():
            raise ValidationError(
                {
                    "institution": f"The simulation already has a {institution.kind.institution_name}"
                }
            )

        if not is_active(institution, simulation.timeline, simulation.valid_at):
            raise ValidationError(
                {
                    "institution": (
                        f"'{institution.label}' is not active on timeline "
                        f"'{simulation.timeline.label}' at {simulation.valid_at}."
                    )
                }
            )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                name="uq_simulationinstitution_simulation_institution",
                fields=["simulation", "institution"],
            )
        ]


def validate_membership(agent: models.Model, field_name: str, serialization_model: str):
    """
    Check that an agent (minister, MP or judge) sits in an institution of the
    expected kind and that its party belongs to the institution's country.
    """
    if getattr(agent, f"{field_name}_id") is None:
        return
    institution = getattr(agent, field_name).institution
    if (
        agent.party_id is not None
        and agent.party.country_id != institution.kind.country_id
    ):
        raise ValidationError(
            {"party": "The party must belong to the institution's country."}
        )


class AggrandisementPathType(models.TextChoices):
    DECREE = "decree"
    LEGISLATIVE_ACT = "legislative act"


class SubmodelType(models.TextChoices):
    EXECUTIVE = "executive"
    LEGISLATIVE = "legislative"
    JUDICIARY = "judiciary"


class SimulationLogEntry(models.Model):
    id = models.BigAutoField(primary_key=True)
    simulation = models.ForeignKey(
        to=Simulation, on_delete=models.CASCADE, related_name="log"
    )
    step_no = models.IntegerField(null=False)
    approved = models.BooleanField(null=False)
    last_decision_type = models.CharField(
        choices=SubmodelType.choices, null=True, blank=True, default=None
    )
    aggrandisement_path = models.CharField(
        choices=AggrandisementPathType.choices, null=True, blank=True, default=None
    )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        db_table = "simulation_log"
        constraints = [
            models.UniqueConstraint(
                name="uq_simulation_log_simulation_step_no",
                fields=["simulation", "step_no"],
            )
        ]


class SubmodelLogEntryInfoBase(BaseModel):
    votes: dict[str, Optional[int]]


class VbarSubmodelInfo(SubmodelLogEntryInfoBase):
    vbar: float


class PathSubmodelInfo(SubmodelLogEntryInfoBase):
    path: Optional[str]


class SimulationSubmodelLogEntry(models.Model):
    id = models.BigAutoField(primary_key=True)
    log_entry = models.ForeignKey(
        to=SimulationLogEntry, on_delete=models.CASCADE, related_name="submodels"
    )
    submodel_type = models.CharField(choices=SubmodelType.choices, null=False)
    approved = models.BooleanField(null=False)
    additional_info = SchemaField(
        schema=Union[PathSubmodelInfo, VbarSubmodelInfo], null=False
    )

    class Meta:
        db_table = "simulation_submodel_log"
        constraints = [
            models.UniqueConstraint(
                name="uq_simulation_submodel_log_log_entry_submodel_type",
                fields=["log_entry", "submodel_type"],
            )
        ]
        indexes = [GinIndex(name="ix_ssl_additional_info", fields=["additional_info"])]
