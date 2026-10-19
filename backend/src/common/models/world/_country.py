from django.db import models

from ._settings import UserSettings


class Country(models.Model):
    id = models.AutoField(primary_key=True)
    user_settings = models.ForeignKey(
        to=UserSettings, on_delete=models.CASCADE, related_name="countries"
    )
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Countries"
        constraints = [
            models.UniqueConstraint(
                name="uq_country_user_settings_name",
                fields=["user_settings", "name"],
            )
        ]
