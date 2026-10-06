from django.db import models

from common import fields
from common.models._belief import BeliefModel
from common.models._influence import InfluencerModel
from common.models._institution import SerializationModel
from common.models._party import Party
from common.models._simulation import SimulationInstitution, validate_membership


class Judge(InfluencerModel, BeliefModel):
    id = models.AutoField(primary_key=True)
    label = models.CharField(max_length=50)
    is_president = models.BooleanField(null=False, default=False)
    weights = fields.SeparatedValuesField(base_field=models.FloatField(), blank=True)
    court = models.ForeignKey(
        to=SimulationInstitution, on_delete=models.CASCADE, related_name="judges"
    )
    party = models.ForeignKey(
        to=Party, on_delete=models.RESTRICT, related_name="judges"
    )
    neighbours_out = models.ManyToManyField(
        "self",
        through="JudgeLink",
        symmetrical=False,
        related_name="neighbours_in",
        blank=True,
        editable=False,
    )

    def clean(self):
        super().clean()
        validate_membership(self, "court", SerializationModel.COURT)

    class Meta(InfluencerModel.Meta):
        constraints = InfluencerModel.Meta.constraints + [
            models.UniqueConstraint(
                name="uq_judge_label_in_court", fields=["label", "court"]
            )
        ]


class JudgeLink(models.Model):
    id = models.BigAutoField(primary_key=True)

    from_judge = models.ForeignKey(
        Judge,
        on_delete=models.CASCADE,
        related_name="out_edges",
    )
    to_judge = models.ForeignKey(
        Judge,
        on_delete=models.CASCADE,
        related_name="in_edges",
    )

    @property
    def influence(self):
        return self.from_judge.influence

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["from_judge", "to_judge"],
                name="uq_judgelink_no_duplicate_edges",
            ),
            models.CheckConstraint(
                condition=~models.Q(from_judge=models.F("to_judge")),
                name="ck_judgelink_no_self_loop",
            ),
        ]
