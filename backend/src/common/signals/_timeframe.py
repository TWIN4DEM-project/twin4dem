from django.db.models.signals import post_delete, pre_delete
from django.dispatch import receiver

from common.models import (
    Institution,
    PartyPosition,
    TimeFrame,
    TimelineTimeFrame,
    VirtualTimeline,
)


@receiver(post_delete, sender=Institution)
@receiver(post_delete, sender=PartyPosition)
def delete_subject_time_frames(sender, instance, **kwargs):
    """The soft foreign key has no ON DELETE CASCADE, so cascade manually."""
    TimeFrame.objects.of(instance).delete()


@receiver(pre_delete, sender=VirtualTimeline)
def delete_orphaned_time_frames(sender, instance, **kwargs):
    """
    Delete the time frames restricted to this timeline only. Otherwise, losing
    their last timeline link would silently make them apply to all timelines.
    """
    linked_elsewhere = TimelineTimeFrame.objects.exclude(
        virtual_timeline=instance
    ).values("time_frame_id")
    TimeFrame.objects.filter(timeline_links__virtual_timeline=instance).exclude(
        id__in=linked_elsewhere
    ).delete()
