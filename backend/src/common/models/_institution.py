from typing import Annotated, Optional, Union

from django.core.exceptions import ValidationError
from django.db import models
from django_pydantic_field import SchemaField
from pydantic import BaseModel, ConfigDict, Field

from common.models import InstitutionBranch
from common.models._settings import InstitutionKind


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


class Institution(models.Model):
    """An instance of an institution type, e.g. the 'Castex' cabinet."""

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
        return f"{self.label}(id={self.id},kind={self.kind.name})"

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
