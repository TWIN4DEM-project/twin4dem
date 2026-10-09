from django.db import models
from django.db.models import Q

from common.models._institution import Institution
from common.models._settings import Country


class Party(models.Model):
    """A political party of a country; available across all timelines."""

    id = models.AutoField(primary_key=True)
    country = models.ForeignKey(
        to=Country, on_delete=models.CASCADE, related_name="parties"
    )
    label = models.CharField(max_length=50)

    def __str__(self):
        return self.label

    class Meta:
        verbose_name_plural = "Parties"
        constraints = [
            models.UniqueConstraint(
                name="uq_party_country_label", fields=["country", "label"]
            )
        ]


class PartyPositionType(models.TextChoices):
    MAJORITY = "majority"
    OPPOSITION = "opposition"
    INDEPENDENT = "independent"


class PartyPosition(models.Model):
    """The position a party holds in a parliamentary chamber."""

    id = models.AutoField(primary_key=True)
    party = models.ForeignKey(
        to=Party, on_delete=models.CASCADE, related_name="positions"
    )
    chamber = models.ForeignKey(
        to=Institution, on_delete=models.CASCADE, related_name="party_positions"
    )
    position = models.CharField(choices=PartyPositionType.choices)

    def __str__(self):
        return f"{self.party} ({self.position}) in {self.chamber.label}"

    class Meta:
        constraints = [
            models.CheckConstraint(
                name="ck_partyposition_position",
                condition=Q(position__in=PartyPositionType.values),
            )
        ]
