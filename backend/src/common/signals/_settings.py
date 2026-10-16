from django.db.models.signals import post_save
from django.dispatch import receiver

from common.models import UserSettings, VirtualTimeline


@receiver(post_save, sender=UserSettings)
def create_default_timeline(sender, instance, created, **kwargs):
    if not created:
        return
    VirtualTimeline.objects.get_or_create(
        user_settings=instance, label=VirtualTimeline.DEFAULT_LABEL
    )
