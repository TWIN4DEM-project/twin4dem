from typing import Annotated, Optional, Union

from django.core.exceptions import ValidationError
from django.db import models
from django_pydantic_field import SchemaField
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
    payload = SchemaField(
        schema=Union[CabinetPayload, ChamberPayload, CourtPayload], null=False
    )

    def __str__(self):
        return f"{self.label}(id={self.id},kind={self.kind.institution_name})"

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
        if self.kind.branch not in self._BRANCH_TO_PAYLOAD:
            error_message = (
                f"Institutions from the '{self.kind.branch}' are not supported"
            )
            errors.update({"kind": error_message})
        elif not isinstance(
            self.payload,
            expected_payload_type := self._BRANCH_TO_PAYLOAD[self.kind.branch],
        ):
            error_message = f"Institutions from the '{self.kind.branch}' must have '{expected_payload_type.__name__}' payloads"
            errors.update({"payload": error_message})
        if errors:
            raise ValidationError(errors)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                name="uq_institution_kind_label",
                fields=["kind", "label"],
            ),
        ]
