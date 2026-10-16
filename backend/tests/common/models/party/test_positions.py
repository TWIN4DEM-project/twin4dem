from common.models import PartyPosition, PartyPositionType


def test_position_str_mentions_party_and_chamber(renaissance, assemblee):
    position = PartyPosition(
        party=renaissance, chamber=assemblee, position=PartyPositionType.MAJORITY
    )

    assert str(position) == "Renaissance (majority) in RN2022"


def test_chamberless_position_passes_clean():
    PartyPosition(party_id=1, position=PartyPositionType.INDEPENDENT).clean()
