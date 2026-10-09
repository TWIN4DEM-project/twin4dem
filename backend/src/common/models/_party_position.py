from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from common.models._institution import Institution
from common.models._party import Party
from common.models._settings import InstitutionBranch, VirtualTimeline
from common.models._timeframe import (
    TimeFrameMixin,
    TimeFrameSubjectType,
    active_subjects,
    frameless_sibling,
)


class PartyPositionType(models.TextChoices):
    MAJORITY = "majority"
    OPPOSITION = "opposition"
    INDEPENDENT = "independent"


class PartyPosition(TimeFrameMixin):
    """The position a party holds in a parliamentary chamber."""

    time_frame_subject_type = TimeFrameSubjectType.PARTY_POSITION

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

    def time_frame_siblings(self) -> models.QuerySet:
        """The other positions of the same party in the same chamber."""
        siblings = PartyPosition.objects.filter(
            party_id=self.party_id, chamber_id=self.chamber_id
        ).select_related("party")
        return siblings.exclude(pk=self.pk) if self.pk is not None else siblings

    def time_frame_label(self) -> str:
        return f"'{self.party.label}' ({self.position})"

    def time_frame_user_settings_id(self) -> int:
        return self.party.country.user_settings_id

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
            sibling = frameless_sibling(self)
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
    positions = active_subjects(
        PartyPosition.objects.filter(party=party, chamber=chamber), timeline, at
    )
    return positions[0] if positions else None
