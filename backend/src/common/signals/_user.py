from django.conf import settings as dj_settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from common.models import UserSettings, PartySettings


@receiver(post_save, sender=dj_settings.AUTH_USER_MODEL)
def create_default_settings(sender, instance, created, **kwargs):
    if not created:
        return
    settings, _ = UserSettings.objects.get_or_create(user=instance)
    PartySettings.objects.get_or_create(
        user_settings_id=settings.id,
        label="Party A",
        member_count=25,
        position="majority",
    )
    PartySettings.objects.get_or_create(
        user_settings_id=settings.id,
        label="Party B",
        member_count=35,
        position="majority",
    )
    PartySettings.objects.get_or_create(
        user_settings_id=settings.id,
        label="Party C",
        member_count=40,
        position="opposition",
    )
