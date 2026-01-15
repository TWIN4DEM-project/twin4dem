from django.conf import settings as dj_settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from common.models import UserSettings


@receiver(post_save, sender=dj_settings.AUTH_USER_MODEL)
def create_default_settings(sender, instance, created, **kwargs):
    if not created:
        return
    UserSettings.objects.get_or_create(user=instance)
