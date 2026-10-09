from datetime import datetime, UTC

import pytest
from django.core.exceptions import ValidationError

from common.models import (
    Institution,
    InstitutionBranch,
    PartyPosition,
    PartyPositionType,
    TimeFrame,
    TimelineTimeFrame,
    UserSettings,
)
from common.models._timeframe import FrameSpec


def _dt(year: int, month: int = 1, day: int = 1) -> datetime:
    return datetime(year, month, day, tzinfo=UTC)


# --- FrameSpec: pure interval and timeline logic --------------------------------


@pytest.mark.parametrize(
    "a,b,expected",
    [
        ((_dt(2017), _dt(2018)), (_dt(2018), _dt(2019)), False),
        ((_dt(2017), _dt(2019)), (_dt(2018), _dt(2020)), True),
        ((_dt(2017), _dt(2020)), (_dt(2018), _dt(2019)), True),
        ((_dt(2017), _dt(2018)), (_dt(2019), _dt(2020)), False),
        ((None, _dt(2018)), (_dt(2017), _dt(2019)), True),
        ((None, _dt(2018)), (_dt(2018), None), False),
        ((_dt(2017), None), (_dt(2030), _dt(2031)), True),
        ((None, None), (_dt(2017), _dt(2018)), True),
    ],
    ids=[
        "adjacent",
        "overlapping",
        "contained",
        "disjoint",
        "open start overlapping",
        "open start adjacent to open end",
        "open end",
        "unbounded",
    ],
)
def test_overlaps_in_time(a, b, expected):
    frame_a = FrameSpec(*a, timeline_ids=None)
    frame_b = FrameSpec(*b, timeline_ids=None)

    assert frame_a.overlaps_in_time(frame_b) is expected
    assert frame_b.overlaps_in_time(frame_a) is expected


@pytest.mark.parametrize(
    "a,b,expected_shared",
    [
        (None, None, None),
        (None, frozenset({1}), frozenset({1})),
        (frozenset({1, 2}), frozenset({2, 3}), frozenset({2})),
        (frozenset({1}), frozenset({2}), frozenset()),
    ],
    ids=["all and all", "all and one", "intersecting", "disjoint"],
)
def test_shared_timelines(a, b, expected_shared):
    frame_a = FrameSpec(None, None, timeline_ids=a)
    frame_b = FrameSpec(None, None, timeline_ids=b)

    assert frame_a.shared_timelines(frame_b) == expected_shared
    assert frame_a.shares_timeline_with(frame_b) is (expected_shared != frozenset())


# --- the example from the 'User Settings — Next' page ---------------------------


def _create(taxonomy, label, valid_from=None, valid_to=None, timelines=None):
    """Create an institution and, unless both bounds are None, its time frame."""
    institution = Institution(kind=taxonomy, label=label, size=10)
    institution.full_clean()
    institution.save()
    if valid_from is not None or valid_to is not None:
        TimeFrame.objects.occupy(institution, valid_from, valid_to, timelines or ())
    return institution


@pytest.fixture
def france_2017(
    french_taxonomy, default_timeline, alternate_timeline
) -> dict[str, Institution]:
    cabinet = french_taxonomy[InstitutionBranch.EXECUTIVE]
    chamber = french_taxonomy[InstitutionBranch.LEGISLATIVE]
    court = french_taxonomy[InstitutionBranch.JUDICIARY]
    return {
        institution.label: institution
        for institution in (
            _create(
                cabinet,
                "Philippe I",
                _dt(2017, 5, 15),
                _dt(2017, 6, 21),
                [default_timeline],
            ),
            _create(
                cabinet,
                "Philippe II",
                _dt(2017, 6, 21),
                _dt(2020, 7, 3),
                [default_timeline, alternate_timeline],
            ),
            _create(cabinet, "Castex", _dt(2020, 7, 3), _dt(2022, 5, 16)),
            _create(chamber, "RN2017", _dt(2017, 7, 1), _dt(2022, 6, 30)),
            _create(chamber, "RN2022", _dt(2022, 7, 1), _dt(2024, 7, 7)),
            _create(court, "CC"),
        )
    }


@pytest.mark.django_db
def test_docs_example_is_valid(france_2017):
    assert set(france_2017) == {
        "Philippe I",
        "Philippe II",
        "Castex",
        "RN2017",
        "RN2022",
        "CC",
    }
    assert TimeFrame.objects.count() == 5


@pytest.mark.django_db
def test_extend_philippe_ii_on_alternate_timeline(
    france_2017, default_timeline, alternate_timeline
):
    philippe_ii = france_2017["Philippe II"]
    TimeFrame.objects.of(philippe_ii).get().timelines.set([default_timeline])

    extended = TimeFrame.objects.occupy(
        philippe_ii, _dt(2017, 5, 15), _dt(2020, 7, 3), [alternate_timeline]
    )

    assert list(extended.get_timelines()) == [alternate_timeline]


@pytest.mark.django_db
def test_extend_philippe_ii_on_default_timeline_rejected(france_2017):
    frame = TimeFrame.objects.of(france_2017["Philippe II"]).get()
    frame.valid_from = _dt(2017, 5, 15)

    with pytest.raises(ValidationError) as err_proxy:
        frame.full_clean()

    assert err_proxy.value.messages == [
        "Overlaps with 'Philippe I' [2017-05-15, 2017-06-21) on timeline 'default'."
    ]


@pytest.mark.django_db
def test_second_conseil_constitutionnel_rejected(france_2017, french_taxonomy):
    second_court = Institution(
        kind=french_taxonomy[InstitutionBranch.JUDICIARY],
        label="CC2",
        size=9,
    )

    with pytest.raises(ValidationError) as err_proxy:
        second_court.full_clean()

    assert err_proxy.value.message_dict == {
        "kind": [
            "'CC' has no time frame, so it is active at all times on all "
            "timelines: no other institution of type 'conseil constitutionnel' "
            "can be added."
        ]
    }


@pytest.mark.django_db
def test_frame_rejected_next_to_frameless_sibling(france_2017, french_taxonomy):
    # bypass Institution.clean(), e.g. through bulk_create
    second_court = Institution.objects.create(
        kind=french_taxonomy[InstitutionBranch.JUDICIARY],
        label="CC2",
        size=9,
    )

    with pytest.raises(ValidationError) as err_proxy:
        TimeFrame.objects.occupy(second_court, _dt(2030), _dt(2031))

    assert err_proxy.value.messages == [
        "'CC' has no time frame, so it is active at all times on all timelines."
    ]


@pytest.mark.django_db
def test_new_institution_allowed_when_siblings_have_frames(
    france_2017, french_taxonomy
):
    borne = _create(
        french_taxonomy[InstitutionBranch.EXECUTIVE],
        "Borne",
        _dt(2022, 5, 16),
        _dt(2024, 1, 9),
    )

    assert TimeFrame.objects.of(borne).exists()


@pytest.mark.django_db
def test_different_institution_types_may_overlap(france_2017):
    castex = TimeFrame.objects.of(france_2017["Castex"]).get().spec
    rn2017 = TimeFrame.objects.of(france_2017["RN2017"]).get().spec

    assert castex.overlaps_in_time(rn2017)


@pytest.mark.django_db
def test_open_ended_frame_blocks_later_siblings(france_2017, french_taxonomy):
    cabinet = french_taxonomy[InstitutionBranch.EXECUTIVE]
    _create(cabinet, "Borne", valid_from=_dt(2022, 5, 16))
    attal = _create(cabinet, "Attal")  # no frame yet

    with pytest.raises(ValidationError) as err_proxy:
        TimeFrame.objects.occupy(attal, _dt(2024, 1, 9), _dt(2024, 9, 5))

    assert err_proxy.value.messages == [
        "Overlaps with 'Borne' [2022-05-16, +inf) on all timelines."
    ]


# --- rule 1: one time frame per subject and timeline ----------------------------


@pytest.mark.django_db
def test_subject_occupies_one_frame_per_timeline(france_2017, alternate_timeline):
    with pytest.raises(ValidationError) as err_proxy:
        TimeFrame.objects.occupy(
            france_2017["Castex"], _dt(2030), _dt(2031), [alternate_timeline]
        )

    assert err_proxy.value.messages == [
        "'Castex' already occupies the time frame [2020-07-03, 2022-05-16) "
        "on timeline 'alternate'."
    ]


@pytest.mark.django_db
def test_subject_occupies_different_frames_on_different_timelines(
    france_2017, french_taxonomy, default_timeline, alternate_timeline
):
    borne = _create(
        french_taxonomy[InstitutionBranch.EXECUTIVE],
        "Borne",
        _dt(2022, 5, 16),
        _dt(2024, 1, 9),
        [default_timeline],
    )

    TimeFrame.objects.occupy(
        borne, _dt(2022, 5, 16), _dt(2023, 1, 1), [alternate_timeline]
    )

    assert TimeFrame.objects.of(borne).count() == 2


@pytest.mark.django_db
def test_editing_frame_does_not_conflict_with_itself(france_2017):
    frame = TimeFrame.objects.of(france_2017["Castex"]).get()
    frame.valid_to = _dt(2022, 5, 1)

    frame.full_clean()


# --- entry points ---------------------------------------------------------------


@pytest.mark.django_db
def test_adding_timeline_link_validates_overlaps(
    france_2017, default_timeline, alternate_timeline
):
    philippe_ii = france_2017["Philippe II"]
    TimeFrame.objects.of(philippe_ii).get().timelines.set([default_timeline])
    TimeFrame.objects.occupy(
        philippe_ii, _dt(2017, 5, 15), _dt(2020, 7, 3), [alternate_timeline]
    )
    philippe_i_frame = TimeFrame.objects.of(france_2017["Philippe I"]).get()
    link = TimelineTimeFrame(
        time_frame=philippe_i_frame, virtual_timeline=alternate_timeline
    )

    with pytest.raises(ValidationError) as err_proxy:
        link.full_clean()

    assert err_proxy.value.message_dict == {
        "virtual_timeline": [
            "Overlaps with 'Philippe II' [2017-05-15, 2020-07-03) "
            "on timeline 'alternate'."
        ]
    }


@pytest.mark.django_db
def test_occupy_saves_nothing_when_invalid(france_2017):
    frame_count = TimeFrame.objects.count()

    with pytest.raises(ValidationError):
        TimeFrame.objects.occupy(france_2017["Castex"], _dt(2030), _dt(2031))

    assert TimeFrame.objects.count() == frame_count


@pytest.mark.django_db
def test_occupy_rejects_timeline_of_other_context(france_2017, test_settings):
    other_settings = UserSettings.objects.create(
        user=test_settings.user, label="alternate world"
    )

    with pytest.raises(ValidationError) as err_proxy:
        TimeFrame.objects.occupy(
            france_2017["CC"], timelines=[other_settings.timelines.get()]
        )

    assert err_proxy.value.messages == [
        "The timelines must belong to the same global context as the "
        "time frame's subject."
    ]


# --- party positions ------------------------------------------------------------


def _position(party, chamber, position, valid_from=None, valid_to=None):
    party_position = PartyPosition(party=party, chamber=chamber, position=position)
    party_position.full_clean()
    party_position.save()
    if valid_from is not None or valid_to is not None:
        TimeFrame.objects.occupy(party_position, valid_from, valid_to)
    return party_position


@pytest.mark.django_db
def test_party_changes_position_over_time(renaissance, assemblee):
    _position(
        renaissance,
        assemblee,
        PartyPositionType.MAJORITY,
        _dt(2017, 6, 21),
        _dt(2022, 6, 19),
    )
    _position(
        renaissance,
        assemblee,
        PartyPositionType.OPPOSITION,
        valid_from=_dt(2022, 6, 19),
    )

    assert renaissance.positions.count() == 2


@pytest.mark.django_db
def test_party_positions_in_same_chamber_may_not_overlap(renaissance, assemblee):
    _position(
        renaissance,
        assemblee,
        PartyPositionType.MAJORITY,
        _dt(2017, 6, 21),
        _dt(2022, 6, 19),
    )
    opposition = _position(renaissance, assemblee, PartyPositionType.OPPOSITION)

    with pytest.raises(ValidationError) as err_proxy:
        TimeFrame.objects.occupy(opposition, valid_from=_dt(2020))

    assert err_proxy.value.messages == [
        "Overlaps with 'Renaissance' (majority) [2017-06-21, 2022-06-19) "
        "on all timelines."
    ]


@pytest.mark.django_db
def test_party_positions_in_different_chambers_may_overlap(
    renaissance, assemblee, senat
):
    _position(renaissance, assemblee, PartyPositionType.MAJORITY, valid_from=_dt(2017))
    _position(renaissance, senat, PartyPositionType.OPPOSITION, valid_from=_dt(2017))

    assert TimeFrame.objects.count() == 2


@pytest.mark.django_db
def test_parties_in_same_chamber_may_overlap(france, renaissance, assemblee):
    modem = france.parties.create(label="MoDem")
    _position(renaissance, assemblee, PartyPositionType.MAJORITY, valid_from=_dt(2017))
    _position(modem, assemblee, PartyPositionType.MAJORITY, valid_from=_dt(2017))

    assert TimeFrame.objects.count() == 2


@pytest.mark.django_db
def test_second_position_rejected_next_to_frameless_position(renaissance, assemblee):
    _position(renaissance, assemblee, PartyPositionType.MAJORITY)
    opposition = PartyPosition(
        party=renaissance, chamber=assemblee, position=PartyPositionType.OPPOSITION
    )

    with pytest.raises(ValidationError) as err_proxy:
        opposition.full_clean()

    assert err_proxy.value.message_dict == {
        "chamber": [
            "'Renaissance' holds the majority position in 'RN2022' without a time "
            "frame, i.e. at all times on all timelines: no other position can be "
            "added."
        ]
    }
