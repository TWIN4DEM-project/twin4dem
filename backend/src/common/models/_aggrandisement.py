from django.db import models

from common.models import Simulation, Minister, MemberOfParliament, Judge
from common.models._belief import BeliefModel


class AggrandisementBatch(models.Model):
    id = models.AutoField(primary_key=True)
    file_name = models.CharField(max_length=32, null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    start_date = models.DateTimeField(null=False, blank=False, db_index=True)
    end_date = models.DateTimeField(null=False, blank=False, db_index=True)

    simulation = models.ForeignKey(
        to=Simulation, on_delete=models.CASCADE, related_name="batch", unique=True
    )

    def __str__(self):
        if self.file_name:
            return "{0} [{1} → {2}]".format(
                self.file_name,
                self.start_date.strftime("%Y-%m-%d"),
                self.end_date.strftime("%Y-%m-%d"),
            )
            return self.file_name
        return "[id={0:06}, {1} → {2}]".format(
            self.id,
            self.start_date.strftime("%Y-%m-%d"),
            self.end_date.strftime("%Y-%m-%d"),
        )


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


class MinisterBelief(BeliefModel):
    id = models.AutoField(primary_key=True)
    unit = models.ForeignKey(
        to=AggrandisementUnit, on_delete=models.CASCADE, related_name="ministers"
    )
    agent = models.ForeignKey(
        to=Minister, on_delete=models.CASCADE, related_name="beliefs"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(name="uq_minister_unit", fields=["agent", "unit"])
        ]


class MPBelief(BeliefModel):
    id = models.AutoField(primary_key=True)
    unit = models.ForeignKey(
        to=AggrandisementUnit, on_delete=models.CASCADE, related_name="mps"
    )
    agent = models.ForeignKey(
        to=MemberOfParliament, on_delete=models.CASCADE, related_name="beliefs"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(name="uq_mp_unit", fields=["agent", "unit"])
        ]


class JudgeBelief(BeliefModel):
    id = models.AutoField(primary_key=True)
    unit = models.ForeignKey(
        to=AggrandisementUnit, on_delete=models.CASCADE, related_name="judges"
    )
    agent = models.ForeignKey(
        to=Judge, on_delete=models.CASCADE, related_name="beliefs"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(name="uq_judge_unit", fields=["agent", "unit"])
        ]
