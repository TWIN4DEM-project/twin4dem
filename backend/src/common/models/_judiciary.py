from django.contrib.contenttypes.fields import GenericRelation
from django.db import models

from common import fields
from common.models._influence import InfluencerModel
from common.models._settings import PartySettings
from common.models._simulation import SimulationParams


class Court(models.Model):
    id = models.AutoField(primary_key=True)
    label = models.CharField(max_length=50, unique=True)
    probability_for = models.FloatField(default=0.5)
    simulation_param = GenericRelation(
        to=SimulationParams,
        content_type_field="type",
        object_id_field="content_id",
        related_query_name="court",
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                name="ck_court_probability_for_is_prob",
                condition=models.Q(probability_for__gte=0)
                & models.Q(probability_for__lte=1),
            ),
        ]


class Judge(InfluencerModel):
    id = models.AutoField(primary_key=True)
    label = models.CharField(max_length=50)
    is_president = models.BooleanField(null=False, default=False)
    weights = fields.SeparatedValuesField(base_field=models.FloatField(), blank=True)
    court = models.ForeignKey(to=Court, on_delete=models.CASCADE, related_name="judges")
    party = models.ForeignKey(
        to=PartySettings, on_delete=models.RESTRICT, related_name="judges"
    )
    neighbours_out = models.ManyToManyField(
        "self",
        through="JudgeLink",
        symmetrical=False,
        related_name="neighbours_in",
        blank=True,
        editable=False,
    )

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
