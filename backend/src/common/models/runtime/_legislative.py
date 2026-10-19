from django.db import models

from common import fields

from ..institution import InstitutionBranch
from ..party import Party
from ._belief import BeliefModel
from ._simulation import SimulationInstitution, validate_membership


class MemberOfParliament(BeliefModel):
    id = models.AutoField(primary_key=True)
    label = models.CharField(max_length=100)
    is_head = models.BooleanField(null=False, default=False)
    weights = fields.SeparatedValuesField(base_field=models.FloatField(), blank=True)

    party = models.ForeignKey(to=Party, on_delete=models.RESTRICT, related_name="mps")
    chamber = models.ForeignKey(
        to=SimulationInstitution, on_delete=models.CASCADE, related_name="members"
    )

    def clean(self):
        super().clean()
        validate_membership(
            self, "chamber", InstitutionBranch.LEGISLATIVE, "member of parliament"
        )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                name="uq_mp_label_in_chamber", fields=["label", "chamber"]
            )
        ]
