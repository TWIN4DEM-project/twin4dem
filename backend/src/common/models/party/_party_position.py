from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from ..institution import Institution, InstitutionBranch
from ..timeline import TimeFrameSubject, VirtualTimeline
from ._party import Party


class PartyPositionType(models.TextChoices):
    MAJORITY = "majority"
    OPPOSITION = "opposition"
    INDEPENDENT = "independent"


class PartyPosition(TimeFrameSubject):
    """The position a party holds in a parliamentary chamber."""

    sibling_fields = ("party", "chamber")

    id = models.AutoField(primary_key=True)
    party = models.ForeignKey(
        to=Party, on_delete=models.CASCADE, related_name="positions"
    )
    chamber = models.ForeignKey(
        to=Institution,
        on_delete=models.CASCADE,
        related_name="party_positions",
        null=True,
        blank=True,
    )
    position = models.CharField(choices=PartyPositionType.choices)

    def __str__(self):
        return (
            f"{self.party} ({self.position}) in {self.chamber.label}"
            if self.chamber
            else f"{self.party} ({self.position})"
        )

    @property
    def country(self):
        return self.party.country

    def time_frame_user_settings_id(self) -> int:
        """The global context whose timelines the subject's frames apply to."""
        return self.country.user_settings_id

    def time_frame_label(self) -> str:
        return f"'{self.party.label}' ({self.position})"

    def clean(self) -> None:
        super().clean()
        if self.chamber_id is None:
            return
        errors = {}
        if self.chamber.kind.branch != InstitutionBranch.LEGISLATIVE:
            errors["chamber"] = "Party positions can only be held in a chamber."
        elif self.party.country_id != self.chamber.kind.country_id:
            errors["chamber"] = "The chamber must belong to the party's country."
        elif self.pk is None:
            sibling = self.frameless_sibling()
            if sibling is not None:
                errors["chamber"] = (
                    f"'{sibling.party.label}' holds the {sibling.position} "
                    f"position in '{sibling.chamber.label}' without a time frame, "
                    "i.e. at all times on all timelines: no other position can "
                    "be added."
                )
        if errors:
            raise ValidationError(errors)

    class Meta:
        constraints = [
            models.CheckConstraint(
                name="ck_partyposition_position",
                condition=Q(position__in=PartyPositionType.values),
            )
        ]


def party_position_at(
    party: Party | int, chamber: Institution, timeline: VirtualTimeline, at: datetime
) -> PartyPosition | None:
    """The position `party` holds in `chamber` on `timeline` at `at`, if any."""
    return (
        PartyPosition.objects.filter(party=party, chamber=chamber)
        .active_on(timeline, at)
        .order_by("pk")
        .first()
    )
