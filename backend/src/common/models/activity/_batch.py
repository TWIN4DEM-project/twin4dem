from django.db import models

from ..runtime import Simulation


class AggrandisementBatch(models.Model):
    id = models.AutoField(primary_key=True)
    file_name = models.CharField(max_length=32, null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    start_date = models.DateTimeField(null=False, blank=False, db_index=True)
    end_date = models.DateTimeField(null=False, blank=False, db_index=True)

    simulation = models.ForeignKey(
        to=Simulation, on_delete=models.CASCADE, related_name="batch", unique=True
    )

    def __str__(self):
        if self.file_name:
            return "{0} [{1} → {2}]".format(
                self.file_name,
                self.start_date.strftime("%Y-%m-%d"),
                self.end_date.strftime("%Y-%m-%d"),
            )
        return "[id={0:06}, {1} → {2}]".format(
            self.id,
            self.start_date.strftime("%Y-%m-%d"),
            self.end_date.strftime("%Y-%m-%d"),
        )
