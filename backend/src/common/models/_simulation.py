from typing import Union, Optional

from django.contrib.contenttypes import fields as ct_fields, models as ct_models
from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django_pydantic_field import SchemaField
from pydantic import BaseModel

from common.models._settings import UserSettings


class Simulation(models.Model):
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


class SimulationParams(models.Model):
    simulation = models.ForeignKey(
        to=Simulation, on_delete=models.CASCADE, related_name="params"
    )
    type = models.ForeignKey(to=ct_models.ContentType, on_delete=models.CASCADE)
    content_id = models.PositiveBigIntegerField()
    params = ct_fields.GenericForeignKey("type", "content_id")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                name="uq_params_id_per_type", fields=["simulation", "type"]
            )
        ]


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
