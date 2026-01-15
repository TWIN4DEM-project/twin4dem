from django.contrib.contenttypes.fields import GenericRelation
from django.db import models

from common import fields
from common.models._settings import UserSettings, PartySettings
from common.models._simulation import SimulationParams


class Parliament(models.Model):
    id = models.AutoField(primary_key=True)
    label = models.CharField(max_length=50, unique=True)
    majority_probability_for = models.FloatField(default=0.5)
    opposition_probability_for = models.FloatField(default=0.5)
    simulation_param = GenericRelation(
        to=SimulationParams,
        content_type_field="type",
        object_id_field="content_id",
        related_query_name="parliament",
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                name="ck_majority_probability_for_is_prob",
                condition=models.Q(majority_probability_for__gte=0)
                & models.Q(majority_probability_for__lte=1),
            ),
            models.CheckConstraint(
                name="ck_opposition_probability_for_is_prob",
                condition=models.Q(opposition_probability_for__gte=0)
                & models.Q(opposition_probability_for__lte=1),
            ),
        ]

    @property
    def user_settings(self) -> UserSettings:
        qs = self.simulation_param.all()
        if not qs.exists():
            raise ValueError("orphan parliament")
        sim_param = qs.first()
        return sim_param.simulation.user_settings

    @property
    def party_count(self) -> int:
        return self.user_settings.parties.count()

    @property
    def parliament_size(self) -> int:
        return self.user_settings.parliament_size


class MemberOfParliament(models.Model):
    id = models.AutoField(primary_key=True)
    label = models.CharField(max_length=100)
    is_head = models.BooleanField(null=False, default=False)
    weights = fields.SeparatedValuesField(base_field=models.FloatField(), blank=True)

    party = models.ForeignKey(
        to=PartySettings, on_delete=models.RESTRICT, related_name="mps"
    )
    parliament = models.ForeignKey(
        to=Parliament, on_delete=models.CASCADE, related_name="members"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                name="uq_mp_label_in_parliament", fields=["label", "parliament"]
            )
        ]
