from typing import Annotated, Optional

import pydantic
from django.core.exceptions import ValidationError
from django.db import models
from pydantic import BaseModel, ConfigDict, Field

from common.models._settings import InstitutionBranch, InstitutionKind
from common.models._timeframe import TimeFrameMixin, TimeFrameSubjectType


type Probability = Annotated[float, Field(ge=0.0, le=1.0)]


class InstitutionPayload(BaseModel):
    """Base class for the type-specific attributes stored in `Institution.payload`."""

    model_config = ConfigDict(extra="forbid")


# probability overrides left as None fall back to the UserSettings defaults
class CabinetPayload(InstitutionPayload):
    connectivity_degree: int = Field(default=3, ge=1)
    probability_for: Optional[Probability] = None


class ChamberPayload(InstitutionPayload):
    majority_probability_for: Optional[Probability] = None
    opposition_probability_for: Optional[Probability] = None


class CourtPayload(InstitutionPayload):
    probability_for: Optional[Probability] = None


class SerializationModel(models.TextChoices):
    CABINET = "cabinet"
    CHAMBER = "chamber"
    COURT = "court"

    @property
    def branch(self) -> InstitutionBranch:
        """The institution branch that serialises as this model."""
        return {
            SerializationModel.CABINET: InstitutionBranch.EXECUTIVE,
            SerializationModel.CHAMBER: InstitutionBranch.LEGISLATIVE,
            SerializationModel.COURT: InstitutionBranch.JUDICIARY,
        }[self]


class Institution(TimeFrameMixin):
    """An instance of an institution type, e.g. the 'Castex' cabinet."""

    time_frame_subject_type = TimeFrameSubjectType.INSTITUTION

    _BRANCH_TO_PAYLOAD = {
        InstitutionBranch.EXECUTIVE.value: CabinetPayload,
        InstitutionBranch.LEGISLATIVE.value: ChamberPayload,
        InstitutionBranch.JUDICIARY.value: CourtPayload,
    }

    id = models.AutoField(primary_key=True)
    kind = models.ForeignKey(
        to=InstitutionKind, on_delete=models.CASCADE, related_name="institutions"
    )
    label = models.CharField(max_length=100)
    size = models.PositiveSmallIntegerField()
    payload = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.label}(id={self.id},kind={self.kind.institution_name})"

    @property
    def payload_schema(self) -> type[InstitutionPayload] | None:
        """The payload schema expected by the institution's branch."""
        return self._BRANCH_TO_PAYLOAD.get(self.kind.branch)

    def get_payload(self) -> InstitutionPayload:
        """Return the payload as an instance of its typed schema."""
        schema = self.payload_schema
        if schema is None:
            raise LookupError(
                f"Institutions from the '{self.kind.branch}' are not supported"
            )
        return schema.model_validate(self.payload)

    def time_frame_siblings(self) -> models.QuerySet:
        """The other institutions of the same kind."""
        siblings = Institution.objects.filter(kind_id=self.kind_id)
        return siblings.exclude(pk=self.pk) if self.pk is not None else siblings

    def time_frame_label(self) -> str:
        return f"'{self.label}'"

    def time_frame_user_settings_id(self) -> int:
        return self.kind.country.user_settings_id

    def clean(self) -> None:
        super().clean()
        errors = {}

        if self.pk is None and self.kind_id is not None:
            # imported here: _timeframe depends on this module
            from common.models._timeframe import frameless_sibling

            sibling = frameless_sibling(self)
            if sibling is not None:
                errors["kind"] = (
                    f"'{sibling.label}' has no time frame, so it is active at "
                    f"all times on all timelines: no other institution of type "
                    f"'{self.kind.institution_name}' can be added."
                )

        payload_schema = self.payload_schema
        if payload_schema is None:
            errors["kind"] = (
                f"Institutions from the '{self.kind.branch}' are not supported"
            )
        else:
            try:
                # store the normalized payload, with defaults filled in
                self.payload = payload_schema.model_validate(self.payload).model_dump(
                    mode="json"
                )
            except pydantic.ValidationError as e:
                errors["payload"] = [
                    f"{'.'.join(map(str, err['loc'])) or 'payload'}: {err['msg']}"
                    for err in e.errors()
                ]

        if errors:
            raise ValidationError(errors)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                name="uq_institution_kind_label",
                fields=["kind", "label"],
            ),
        ]
