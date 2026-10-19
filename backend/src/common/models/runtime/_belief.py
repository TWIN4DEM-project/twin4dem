from django.db import models


class BeliefModel(models.Model):
    personal_opinion = models.FloatField(default=0)
    appointing_group_opinion = models.FloatField(default=0)
    supporting_group_opinion = models.FloatField(default=0)

    class Meta:
        abstract = True
