import argparse
import json
from io import StringIO

import pytest
from django.core.management import call_command

from common.dto import AggrandisementBatch
from common.models import (
    Country,
    Institution,
    InstitutionBranch,
    InstitutionKind,
    UserSettings,
)
from common.management.commands.generate_aggrandisement_batch import Command

BATCH_PASSWORD = "s3cret-password"
START_DATE = "2025-01-01T00:00:00"
END_DATE = "2025-02-01T00:00:00"


@pytest.fixture
def admin_with_password(admin_user):
    admin_user.set_password(BATCH_PASSWORD)
    admin_user.save()


@pytest.fixture
def call_batch(admin_with_password):
    def _call(**overrides):
        options = {
            "username": "test_admin",
            "password": BATCH_PASSWORD,
            "start_date": START_DATE,
            "end_date": END_DATE,
            **overrides,
        }
        cli_args = [
            f"--{key.replace('_', '-')}={value}"
            for key, value in options.items()
            if value is not None
        ]
        out, err = StringIO(), StringIO()
        call_command("generate_aggrandisement_batch", *cli_args, stdout=out, stderr=err)
        return out.getvalue(), err.getvalue()

    return _call


@pytest.fixture
def batch(call_batch):
    out, _ = call_batch()
    return json.loads(out)


@pytest.mark.parametrize("value", ["0", "-2"])
def test_positive_int_flags_non_positive(value):
    with pytest.raises(argparse.ArgumentTypeError, match="less than or equal to zero"):
        Command._positive_int(value)


def test_positive_int_rejects_non_numeric():
    with pytest.raises(argparse.ArgumentTypeError, match="invalid positive int abc"):
        Command._positive_int("abc")


@pytest.mark.parametrize("value", ["0.0", "0.5", "1"])
def test_probability(value):
    assert Command._probability(value) == float(value)


@pytest.mark.parametrize("value", ["-0.1", "1.1"])
def test_probability_rejects_out_of_range(value):
    with pytest.raises(argparse.ArgumentTypeError, match="not between"):
        Command._probability(value)


def test_probability_rejects_non_numeric():
    with pytest.raises(argparse.ArgumentTypeError, match="invalid float xyz"):
        Command._probability("xyz")


def test_random_freq_lower_center_is_always_for():
    assert Command.random_freq(0) == 1


def test_random_freq_upper_center_is_always_against():
    assert Command.random_freq(1) == 0


def test_output_is_valid_aggrandisement_batch(batch):
    parsed = AggrandisementBatch.model_validate(batch)
    assert parsed.settings.executive.prime_minister


def test_default_batch_has_one_unit(batch):
    assert [unit["step"] for unit in batch["aggrandisementUnits"]] == [1]


def test_aggrandisement_unit_count_creates_steps(call_batch):
    out, _ = call_batch(aggrandisement_unit_count=3)
    units = json.loads(out)["aggrandisementUnits"]
    assert [unit["step"] for unit in units] == [1, 2, 3]


def test_batch_settings_use_country_institutions(batch):
    settings = batch["settings"]
    assert len(settings["executive"]["ministers"]) == 15
    assert len(settings["legislative"]["mps"]) == 98
    assert len(settings["legislative"]["partyLeaders"]) == 2
    assert len(settings["judiciary"]["judges"]) == 5


def test_majority_parties_fill_the_cabinet(batch):
    ministers = batch["settings"]["executive"]["ministers"]
    assert all(m["party"] == "majority" for m in ministers)


def test_prime_minister_and_court_president_are_influential(batch):
    settings = batch["settings"]
    prime_minister = next(
        m
        for m in settings["executive"]["ministers"]
        if m["label"] == settings["executive"]["primeMinister"]
    )
    president = next(
        j
        for j in settings["judiciary"]["judges"]
        if j["label"] == settings["judiciary"]["president"]
    )
    assert prime_minister["influence"] == 1.0
    assert president["influence"] == 1.0


def test_party_leaders_belong_to_their_party(batch):
    leaders = batch["settings"]["legislative"]["partyLeaders"]
    mps = {mp["label"]: mp["party"] for mp in batch["settings"]["legislative"]["mps"]}
    assert {mps[leader] for leader in leaders} == {"majority", "opposition"}


@pytest.mark.parametrize(
    "belief_center,expected", [("0", 1), ("1", 0)], ids=["for", "against"]
)
def test_belief_center_biases_unit_beliefs(call_batch, belief_center, expected):
    out, _ = call_batch(belief_center=belief_center)
    beliefs = json.loads(out)["aggrandisementUnits"][0]["beliefs"]
    opinions = [
        agent["personalOpinion"]
        for agent in beliefs["ministers"] + beliefs["mps"] + beliefs["judges"]
    ]
    assert all(opinion == expected for opinion in opinions)


@pytest.mark.parametrize(
    "field,branch,group",
    [
        ("government_probability_for", "executive", "ministers"),
        ("court_probability_for", "judiciary", "judges"),
    ],
    ids=["cabinet", "court"],
)
def test_institution_probability_falls_back_to_user_settings(
    call_batch, test_settings, field, branch, group
):
    setattr(test_settings, field, 1.0)
    test_settings.save()

    agents = json.loads(call_batch()[0])["settings"][branch][group]
    assert all(agent["personalOpinion"] == 0 for agent in agents)


def test_chamber_probabilities_fall_back_to_user_settings(call_batch, test_settings):
    test_settings.parliament_opposition_probability_for = 1.0
    test_settings.save()

    mps = json.loads(call_batch()[0])["settings"]["legislative"]["mps"]
    opposition_mps = [mp for mp in mps if mp["party"] == "opposition"]
    assert all(mp["personalOpinion"] == 0 for mp in opposition_mps)


def test_institution_payload_overrides_user_settings(call_batch):
    Institution.objects.filter(kind__branch=InstitutionBranch.EXECUTIVE).update(
        payload={"probability_for": 1.0}
    )
    Institution.objects.filter(kind__branch=InstitutionBranch.LEGISLATIVE).update(
        payload={"majority_probability_for": 1.0, "opposition_probability_for": 0.0}
    )

    settings = json.loads(call_batch(belief_center="0")[0])["settings"]
    ministers = [m["personalOpinion"] for m in settings["executive"]["ministers"]]
    majority_mps = [
        mp["personalOpinion"]
        for mp in settings["legislative"]["mps"]
        if mp["party"] == "majority"
    ]
    opposition_mps = [
        mp["personalOpinion"]
        for mp in settings["legislative"]["mps"]
        if mp["party"] == "opposition"
    ]
    assert all(opinion == 0 for opinion in ministers + majority_mps)
    assert all(opinion == 1 for opinion in opposition_mps)


def test_end_date_must_be_after_start_date(call_batch):
    out, err = call_batch(start_date=END_DATE, end_date=START_DATE)

    assert out == ""
    assert "must be after --start-date" in err


def test_invalid_credentials_fail(call_batch):
    out, err = call_batch(password="wrong-password")

    assert out == ""
    assert "Invalid credentials" in err


def test_missing_password_prompts_user(call_batch, monkeypatch):
    monkeypatch.setattr("getpass.getpass", lambda *args, **kwargs: BATCH_PASSWORD)

    out, _ = call_batch(password=None)

    assert json.loads(out)["aggrandisementUnits"]


def test_user_without_settings_fails(django_user_model):
    settingsless_user = django_user_model.objects.create_user(
        username="settingsless", password="x"
    )
    settingsless_user.user_settings.all().delete()
    out, err = StringIO(), StringIO()
    call_command(
        "generate_aggrandisement_batch",
        username="settingsless",
        password="x",
        start_date=START_DATE,
        end_date=END_DATE,
        stdout=out,
        stderr=err,
    )

    assert out.getvalue() == ""
    assert "has no user settings" in err.getvalue()


def test_settings_without_countries_fail(test_user):
    test_user.set_password(BATCH_PASSWORD)
    test_user.save()
    UserSettings.objects.create(user=test_user, label="bare")
    out, err = StringIO(), StringIO()
    call_command(
        "generate_aggrandisement_batch",
        username=test_user.username,
        password=BATCH_PASSWORD,
        start_date=START_DATE,
        end_date=END_DATE,
        stdout=out,
        stderr=err,
    )

    assert out.getvalue() == ""
    assert "have no countries" in err.getvalue()


@pytest.fixture
def barren_country(test_settings):
    test_settings.countries.all().delete()
    return Country.objects.create(user_settings=test_settings, name="Barrenland")


def test_country_without_institutions_fail(admin_with_password, barren_country):
    out, err = StringIO(), StringIO()
    call_command(
        "generate_aggrandisement_batch",
        username="test_admin",
        password=BATCH_PASSWORD,
        start_date=START_DATE,
        end_date=END_DATE,
        stdout=out,
        stderr=err,
    )

    assert "has no 'executive, legislative, judiciary' institutions" in err.getvalue()


def test_country_with_partial_institutions_reports_only_missing_branch(
    admin_with_password, barren_country
):
    cabinet_kind = InstitutionKind.objects.create(
        country=barren_country,
        branch=InstitutionBranch.EXECUTIVE,
        institution_name="cabinet",
    )
    Institution.objects.create(kind=cabinet_kind, label="Cabinet", size=3)
    out, err = StringIO(), StringIO()
    call_command(
        "generate_aggrandisement_batch",
        username="test_admin",
        password=BATCH_PASSWORD,
        start_date=START_DATE,
        end_date=END_DATE,
        stdout=out,
        stderr=err,
    )

    assert "has no 'legislative, judiciary' institutions" in err.getvalue()
