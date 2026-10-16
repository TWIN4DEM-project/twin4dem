from django.db import models
from django.db.models import Q

from ..world import Country
from ._branch import InstitutionBranch


class InstitutionKind(models.Model):
    """A kind of institution that a country supports (e.g. 'cabinet', 'senate')."""

    id = models.AutoField(primary_key=True)

    institution_name = models.CharField(max_length=100)
    country = models.ForeignKey(
        to=Country, on_delete=models.CASCADE, related_name="institution_kinds"
    )

    branch = models.CharField(choices=InstitutionBranch.choices)

    def __str__(self):
        return f"{self.country}: {self.institution_name} ({self.branch})"

    class Meta:
        verbose_name_plural = "Institution kinds"
        constraints = [
            models.UniqueConstraint(
                name="uq_institutionkind_institution_name_per_country",
                fields=["institution_name", "country"],
            ),
            models.CheckConstraint(
                name="ck_institutiontaxonomy_branch",
                condition=Q(branch__in=InstitutionBranch.values),
            ),
        ]
