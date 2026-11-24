import logging

from twin4dem_data_contracts import models as contracts

from common.models import InstitutionBranch

from ._api import Api
from ._exceptions import DataImportError
from ._selection import Instance

logger = logging.getLogger(__name__)


def find_settings(api: Api, label: str) -> int:
    """The id of the logged-in user's settings with `label`."""
    for settings in api.list("settings"):
        if settings["label"] == label:
            return settings["id"]
    raise DataImportError(f"settings '{label}' not found.")


def write_country(
    api: Api,
    settings_id: int,
    country: contracts.Country,
    institutions: list[tuple[InstitutionBranch, contracts.Institution, Instance]],
    parties: list[tuple[contracts.PoliticalParty, contracts.PartyPosition | None]],
) -> None:
    saved_country = _find_or_create_country(api, settings_id, country.name)
    chambers = []
    for branch, institution, instance in institutions:
        kind = _find_or_create_kind(api, saved_country, institution.name, branch)
        if isinstance(instance, contracts.Cabinet):
            label = instance.name
        else:
            label = institution.name
        saved_institution = _find_or_create_institution(
            api, saved_country, kind, label, instance.size
        )
        if branch == InstitutionBranch.LEGISLATIVE:
            chambers.append(saved_institution)
    saved_parties = _find_or_create_parties(
        api, saved_country, [party.name for party, _ in parties]
    )
    positions = [
        (saved_parties[party.name], position.position)
        for party, position in parties
        if position is not None
    ]
    for chamber in chambers:
        _find_or_create_positions(api, chamber, positions)
        if len(saved_parties) >= chamber["size"]:
            logger.warning(
                f"{country.name}: {len(saved_parties)} parties for "
                f"{chamber['size']} seats in '{chamber['label']}', each party "
                "gets only its leader."
            )
    if not chambers and positions:
        logger.warning(f"{country.name}: no chamber, party positions not imported.")


def _find_or_create_country(api: Api, settings_id: int, name: str) -> dict:
    for found in api.list("country"):
        if found["userSettings"] == settings_id and found["name"] == name:
            return found
    return api.create(
        "country", {"userSettings": settings_id, "name": name}, f"country '{name}'"
    )


def _find_or_create_kind(
    api: Api, country: dict, name: str, branch: InstitutionBranch
) -> dict:
    for found in api.list("institution-kind", country=country["id"], branch=branch):
        if found["name"] == name:
            return found
    return api.create(
        "institution-kind",
        {"country": country["id"], "name": name, "branch": branch},
        f"{branch} institution '{name}' of {country['name']}",
    )


def _find_or_create_institution(
    api: Api, country: dict, kind: dict, label: str, size: int
) -> dict:
    found = api.list("institution", kind=kind["id"])
    if found:
        return found[0]
    return api.create(
        "institution",
        {"country": country["id"], "kind": kind["id"], "label": label, "size": size},
        f"institution '{label}' of {country['name']}",
    )


def _find_or_create_parties(
    api: Api, country: dict, labels: list[str]
) -> dict[str, dict]:
    """The saved party of each label, the missing ones created."""
    saved = {
        party["label"]: party for party in api.list("party", country=country["id"])
    }
    for label in labels:
        if label not in saved:
            saved[label] = api.create(
                "party",
                {"country": country["id"], "label": label},
                f"party '{label}' of {country['name']}",
            )
    return saved


def _find_or_create_positions(
    api: Api, chamber: dict, positions: list[tuple[dict, str]]
) -> None:
    """
    The position of each party in `chamber`, unless it already has one there,
    created in one request.
    """
    positioned = {p["party"] for p in api.list("party-position", chamber=chamber["id"])}
    missing = [
        {"party": party["id"], "chamber": chamber["id"], "position": position}
        for party, position in positions
        if party["id"] not in positioned
    ]
    if missing:
        api.create("party-position", missing, f"positions in '{chamber['label']}'")
