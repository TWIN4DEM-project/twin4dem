from pathlib import Path

import pytest
from django.core.files.storage import FileSystemStorage, Storage

from common.importing import DataImportError, SourceError, resolve_source


def folder_of(storage: Storage) -> Path:
    assert isinstance(storage, FileSystemStorage)
    return Path(storage.location)


def test_returns_a_django_storage(testland_dir):
    assert isinstance(resolve_source(str(testland_dir)), Storage)


def test_csv_files_are_readable_through_the_storage(testland_dir):
    storage = resolve_source(str(testland_dir))

    assert storage.exists("country.csv")
    assert not storage.exists("nowhere.csv")
    with storage.open("country.csv") as stream:
        assert stream.readline().startswith(b"country_id,name")


def test_absolute_path(testland_dir):
    assert folder_of(resolve_source(str(testland_dir))) == testland_dir.resolve()


def test_relative_path_is_resolved_from_the_working_directory(
    testland_dir, monkeypatch
):
    monkeypatch.chdir(testland_dir.parent)

    assert folder_of(resolve_source("testland")) == testland_dir.resolve()


@pytest.mark.parametrize("location", ["", "   "])
def test_empty_location_is_rejected(location):
    with pytest.raises(SourceError, match="No import source given"):
        resolve_source(location)


def test_missing_folder_is_rejected(tmp_path):
    with pytest.raises(SourceError, match="does not exist"):
        resolve_source(str(tmp_path / "nowhere"))


def test_file_instead_of_folder_is_rejected(testland_dir):
    with pytest.raises(SourceError, match="is not a folder"):
        resolve_source(str(testland_dir / "country.csv"))


def test_windows_drive_letter_is_a_path_not_a_scheme():
    # 'C:' parses as a one-letter URL scheme: it must be treated as a path,
    # so the error is about the folder, not about an unsupported scheme
    with pytest.raises(SourceError, match="does not exist"):
        resolve_source("C:/twin4dem-nowhere/testland")


@pytest.mark.parametrize(
    "location",
    [
        "file:///data/testland",
        "ssh://example.org/data/testland",
        "sftp://example.org/data/testland",
        "ftp://example.org/data/testland",
        "https://example.org/data/testland.zip",
    ],
)
def test_url_schemes_are_not_supported_yet(location):
    scheme = location.split(":", 1)[0]

    with pytest.raises(SourceError, match=f"'{scheme}' scheme is not supported"):
        resolve_source(location)


def test_source_errors_are_import_errors():
    assert issubclass(SourceError, DataImportError)
