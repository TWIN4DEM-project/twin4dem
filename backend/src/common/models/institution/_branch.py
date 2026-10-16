from django.db import models


class InstitutionBranch(models.TextChoices):
    EXECUTIVE = "executive"
    LEGISLATIVE = "legislative"
    JUDICIARY = "judiciary"
