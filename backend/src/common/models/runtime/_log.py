from typing import Optional, Union

from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django_pydantic_field import SchemaField
from pydantic import BaseModel

from ._simulation import Simulation


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
