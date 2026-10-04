from typing import Annotated, Optional

import pydantic
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from pydantic import BaseModel, ConfigDict, Field

from common.models._settings import InstitutionBranch, InstitutionTaxonomy


type Probability = Annotated[float, Field(ge=0.0, le=1.0)]


class InstitutionPayload(BaseModel):
    """Base class for the type-specific attributes stored in `Institution.payload`."""

    model_config = ConfigDict(extra="forbid")


# probability overrides left as None fall back to the UserSettings defaults
class CabinetPayload(InstitutionPayload):
    connectivity_degree: int = Field(default=3, ge=1)
    government_probability_for: Optional[Probability] = None


class ChamberPayload(InstitutionPayload):
    parliament_majority_probability_for: Optional[Probability] = None
    parliament_opposition_probability_for: Optional[Probability] = None


class CourtPayload(InstitutionPayload):
    court_probability_for: Optional[Probability] = None


class SerializationModel(models.TextChoices):
    CABINET = "cabinet"
    CHAMBER = "chamber"
    COURT = "court"


PAYLOAD_SCHEMAS: dict[tuple[str, int], type[InstitutionPayload]] = {
    (SerializationModel.CABINET, 1): CabinetPayload,
    (SerializationModel.CHAMBER, 1): ChamberPayload,
    (SerializationModel.COURT, 1): CourtPayload,
}

BRANCH_SERIALIZATION_MODELS: dict[str, str] = {
    InstitutionBranch.EXECUTIVE: SerializationModel.CABINET,
    InstitutionBranch.LEGISLATIVE: SerializationModel.CHAMBER,
    InstitutionBranch.JUDICIARY: SerializationModel.COURT,
}


class Institution(models.Model):
    """An instance of an institution type, e.g. the 'Castex' cabinet."""

    id = models.AutoField(primary_key=True)
    institution_taxonomy = models.ForeignKey(
        to=InstitutionTaxonomy, on_delete=models.CASCADE, related_name="institutions"
    )
    label = models.CharField(max_length=100)
    size = models.PositiveSmallIntegerField()
    serialization_model = models.CharField(choices=SerializationModel.choices)
    serialization_version = models.PositiveSmallIntegerField(default=1)
    payload = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.label}(id={self.id})"

    @property
    def payload_schema(self) -> type[InstitutionPayload] | None:
        return PAYLOAD_SCHEMAS.get(
            (self.serialization_model, self.serialization_version)
        )

    def get_payload(self) -> InstitutionPayload:
        """Return the payload as an instance of its typed schema."""
        schema = self.payload_schema
        if schema is None:
            raise LookupError(
                f"no payload schema for {self.serialization_model!r} "
                f"version {self.serialization_version}"
            )
        return schema.model_validate(self.payload)

    def clean(self):
        super().clean()
        errors = {}

        if self.institution_taxonomy_id is not None:
            branch = self.institution_taxonomy.branch
            expected = BRANCH_SERIALIZATION_MODELS[branch]
            if self.serialization_model != expected:
                errors["serialization_model"] = (
                    f"Institutions of the {branch} branch must use "
                    f"the '{expected}' serialization model."
                )

        schema = self.payload_schema
        if schema is None:
            errors["serialization_version"] = (
                f"No payload schema for '{self.serialization_model}' "
                f"version {self.serialization_version}."
            )
        else:
            try:
                # store the normalized payload, with defaults filled in
                self.payload = schema.model_validate(self.payload).model_dump(
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
                name="uq_institution_taxonomy_label",
                fields=["institution_taxonomy", "label"],
            ),
            models.CheckConstraint(
                name="ck_institution_serialization_model",
                condition=Q(serialization_model__in=SerializationModel.values),
            ),
            models.CheckConstraint(
                name="ck_institution_serialization_version",
                condition=Q(serialization_version__gte=1),
            ),
        ]
