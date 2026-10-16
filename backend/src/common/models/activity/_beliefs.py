from django.db import models

from ..runtime import BeliefModel, Judge, MemberOfParliament, Minister
from ._unit import AggrandisementUnit


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
