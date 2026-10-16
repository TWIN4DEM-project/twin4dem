import pytest
from django.core.exceptions import ValidationError

from common.models import Institution, InstitutionKind, PartyPosition, PartyPositionType


def test_position_str_mentions_party_and_chamber(renaissance, assemblee):
    position = PartyPosition(
        party=renaissance, chamber=assemblee, position=PartyPositionType.MAJORITY
    )

    assert str(position) == "Renaissance (majority) in RN2022"


def test_chamberless_position_passes_clean():
    PartyPosition(party_id=1, position=PartyPositionType.INDEPENDENT).clean()


def test_institution_payload_of_an_unknown_branch_is_rejected():
    kind = InstitutionKind(institution_name="council", country_id=1, branch="weird")

    with pytest.raises(LookupError, match="not supported"):
        Institution(kind=kind, label="hall", size=1).get_payload()


def test_institution_with_an_unknown_branch_fails_clean():
    kind = InstitutionKind(institution_name="council", country_id=1, branch="weird")

    with pytest.raises(ValidationError) as err_proxy:
        Institution(kind=kind, label="hall", size=1).clean()

    assert "not supported" in err_proxy.value.message_dict["kind"][0]
