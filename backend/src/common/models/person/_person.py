from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, F

from common.models import Country
from ._office_holding import OfficeSpan
from ._party_leadership import PartyLeadershipStint


class Person(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    country = models.ForeignKey(Country, on_delete=models.RESTRICT, null=False)
    dob = models.DateField(null=True, blank=True)
    dod = models.DateField(null=True, blank=True)

    @property
    def office_spans(self) -> models.QuerySet["OfficeSpan"]:
        return OfficeSpan.objects.filter(subject__person=self)

    @property
    def leadership_stints(self) -> models.QuerySet["PartyLeadershipStint"]:
        return PartyLeadershipStint.objects.filter(subject__person=self)

    class Meta:
        db_table = "people"
        verbose_name = "Person"
        verbose_name_plural = "People"
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(dod__isnull=True) | Q(dob__isnull=True) | Q(dod__gt=F("dob"))
                ),
                name="people_dod_after_dob",
                violation_error_message="Date of death must follow date of birth",
            )
        ]

    def clean(self) -> None:
        if self.dod is None or self.dob is None:
            return None
        if self.dod < self.dob:
            raise ValidationError("Date of death must follow date of birth")
