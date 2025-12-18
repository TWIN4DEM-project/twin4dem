from django.contrib.contenttypes import fields as ct_fields, models as ct_models
from django.db import models

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
    user_settings = models.ForeignKey(
        to=UserSettings, on_delete=models.CASCADE, related_name="simulations"
    )


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
