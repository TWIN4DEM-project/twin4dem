from django.db import models

from common import fields
from ._belief import BeliefModel
from ._influence import InfluencerModel
from ._party import Party
from ._simulation import SimulationInstitution


class Minister(InfluencerModel, BeliefModel):
    id = models.AutoField(primary_key=True)
    label = models.CharField(max_length=50)
    is_prime_minister = models.BooleanField(null=False, default=False)
    party = models.ForeignKey(
        to=Party, on_delete=models.RESTRICT, related_name="ministers"
    )
    cabinet = models.ForeignKey(
        to=SimulationInstitution, on_delete=models.CASCADE, related_name="ministers"
    )
    weights = fields.SeparatedValuesField(base_field=models.FloatField(), blank=True)
    neighbours_out = models.ManyToManyField(
        "self",
        through="MinisterLink",
        symmetrical=False,
        related_name="neighbours_in",
        blank=True,
        editable=False,
    )

    class Meta(InfluencerModel.Meta):
        constraints = InfluencerModel.Meta.constraints + [
            models.UniqueConstraint(
                name="uq_minister_label_in_cabinet", fields=["label", "cabinet"]
            )
        ]


class MinisterLink(models.Model):
    id = models.BigAutoField(primary_key=True)

    from_minister = models.ForeignKey(
        Minister,
        on_delete=models.CASCADE,
        related_name="out_edges",
    )
    to_minister = models.ForeignKey(
        Minister,
        on_delete=models.CASCADE,
        related_name="in_edges",
    )

    @property
    def influence(self):
        return self.from_minister.influence

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["from_minister", "to_minister"],
                name="uq_ministerlink_no_duplicate_edges",
            ),
            models.CheckConstraint(
                condition=~models.Q(from_minister=models.F("to_minister")),
                name="ck_ministerlink_no_self_loop",
            ),
        ]
