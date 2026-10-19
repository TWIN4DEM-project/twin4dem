from django.db import models

from ._batch import AggrandisementBatch


class AggrandisementUnit(models.Model):
    id = models.AutoField(primary_key=True)
    batch = models.ForeignKey(
        to=AggrandisementBatch, on_delete=models.CASCADE, related_name="units"
    )
    step_no = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                name="uq_step_per_batch", fields=["step_no", "batch"]
            )
        ]
