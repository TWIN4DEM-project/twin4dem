from django.apps import apps
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from common.models import TimeFrameModel, VirtualTimeline


def time_frame_models() -> list[type[TimeFrameModel]]:
    """The concrete time frame models registered in the app registry."""
    return [
        model
        for model in apps.get_models()
        if issubclass(model, TimeFrameModel) and not model._meta.abstract
    ]


@receiver(pre_delete, sender=VirtualTimeline)
def delete_orphaned_time_frames(sender, instance, **kwargs):
    """
    Delete the time frames restricted to this timeline only. Otherwise, losing
    their last timeline link would silently make them apply to all timelines.
    """
    other_timelines = VirtualTimeline.objects.exclude(pk=instance.pk)
    for model in time_frame_models():
        model.objects.filter(timelines=instance).exclude(
            timelines__in=other_timelines
        ).delete()
