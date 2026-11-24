from typing import TYPE_CHECKING
from django.db import models
from ..timeline import TimeFrameSubject, TimeFrameModel

if TYPE_CHECKING:
    from ._person import Person


class OfficeHolding(TimeFrameSubject):
    person = models.ForeignKey(
        "Person", on_delete=models.CASCADE, null=False, related_name="offices"
    )
    institution = models.ForeignKey(
        "Institution",
        on_delete=models.CASCADE,
        null=False,
        related_name="office_holders",
    )


class OfficeSpan(TimeFrameModel):
    subject = models.ForeignKey(OfficeHolding, on_delete=models.CASCADE, null=False)

    @property
    def person(self) -> "Person":
        return self.subject.person
