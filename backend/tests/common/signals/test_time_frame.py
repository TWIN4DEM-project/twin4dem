import pytest

from common.models import (
    InstitutionTimeFrame,
    PartyPosition,
    PartyPositionTimeFrame,
    PartyPositionType,
)


pytestmark = pytest.mark.django_db


@pytest.fixture(
    params=[
        ("institution", InstitutionTimeFrame),
        ("party_position", PartyPositionTimeFrame),
    ],
    ids=["institution", "party_position"],
)
def framed_subject(request, cabinet, renaissance, assemblee):
    kind, frame_model = request.param
    if kind == "institution":
        return cabinet, frame_model
    position = PartyPosition.objects.create(
        party=renaissance, chamber=assemblee, position=PartyPositionType.MAJORITY
    )
    return position, frame_model


def test_deleting_the_only_timeline_deletes_the_frame(
    framed_subject, alternate_timeline
):
    subject, frame_model = framed_subject
    frame_model.objects.occupy(subject, timelines=[alternate_timeline])

    alternate_timeline.delete()

    assert not frame_model.objects.exists()


def test_deleting_one_of_several_timelines_keeps_the_frame(
    framed_subject, default_timeline, alternate_timeline
):
    subject, frame_model = framed_subject
    frame = frame_model.objects.occupy(
        subject, timelines=[default_timeline, alternate_timeline]
    )

    alternate_timeline.delete()

    assert frame_model.objects.filter(pk=frame.pk).exists()


def test_frameless_timeline_frames_survive_deleting_a_timeline(
    framed_subject, alternate_timeline
):
    subject, frame_model = framed_subject
    frame = frame_model.objects.occupy(subject)

    alternate_timeline.delete()

    assert frame.is_on_all_timelines
