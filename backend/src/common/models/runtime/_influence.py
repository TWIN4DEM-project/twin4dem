from django.db import models


class InfluencerModel(models.Model):
    influence = models.FloatField(null=False, default=0.0)

    class Meta:
        abstract = True
        constraints = [
            models.CheckConstraint(
                name="ck_%(class)s_influence",
                condition=models.Q(influence__gte=0.0) & models.Q(influence__lte=1.0),
            )
        ]
