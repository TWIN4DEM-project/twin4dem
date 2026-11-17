from collections.abc import Callable
from urllib.parse import urlparse

from django.core.files.storage import FileSystemStorage, Storage

from ._errors import SourceError


def resolve_source(location: str) -> Storage:
    if not location.strip():
        raise SourceError("No import source given.")

    scheme = _scheme(location)
    factory = _STORAGE_FACTORIES.get(scheme)
    if factory is None:
        raise SourceError(
            f"Import source '{location}': the '{scheme}' scheme is not supported "
            "yet. Use a local path."
        )
    storage = factory(location)
    _check_is_folder(storage, location)
    return storage


def _scheme(location: str) -> str:
    scheme = urlparse(location).scheme
    # on Windows, the drive letter of 'C:/data' parses as a one-letter scheme
    return "" if len(scheme) == 1 else scheme


def _check_is_folder(storage: Storage, location: str) -> None:
    try:
        storage.listdir("")
    except FileNotFoundError as e:
        raise SourceError(f"Import source '{location}' does not exist.") from e
    except NotADirectoryError as e:
        raise SourceError(f"Import source '{location}' is not a folder.") from e


_STORAGE_FACTORIES: dict[str, Callable[[str], Storage]] = {
    "": lambda location: FileSystemStorage(location=location),  # plain path
}
