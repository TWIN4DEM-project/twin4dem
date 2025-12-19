from django.contrib.contenttypes.fields import GenericRelation
from django.db import models

from common import fields
from common.models._settings import PartySettings
from ._simulation import SimulationParams


class InfluencerModel(models.Model):
    influence = models.FloatField(null=False, default=0.0)

    class Meta:
        abstract = True
        constraints = [
            models.CheckConstraint(
                name="ck_influencer_influence",
                condition=models.Q(influence__gte=0.0) & models.Q(influence__lte=1.0),
            )
        ]


class Cabinet(models.Model):
    id = models.AutoField(primary_key=True)
    label = models.CharField(max_length=50, unique=True)
    government_probability_for = models.FloatField(default=0.5)
    legislative_probability = models.FloatField()
    simulation_param = GenericRelation(
        to=SimulationParams,
        content_type_field="type",
        object_id_field="content_id",
        related_query_name="cabinet",
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                name="ck_government_probability_for_is_prob",
                condition=models.Q(government_probability_for__gte=0)
                & models.Q(government_probability_for__lte=1),
            ),
        ]


class Minister(InfluencerModel):
    id = models.AutoField(primary_key=True)
    label = models.CharField(max_length=50)
    is_prime_minister = models.BooleanField(null=False, default=False)
    party = models.ForeignKey(
        to=PartySettings, on_delete=models.RESTRICT, related_name="ministers"
    )
    cabinet = models.ForeignKey(
        to=Cabinet, on_delete=models.CASCADE, related_name="ministers"
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
