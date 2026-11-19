class DataImportError(Exception):
    """Base class for the errors that stop an import before anything is saved."""


class SourceError(DataImportError):
    """The location given for the import cannot be used."""


def raise_if_any(errors: list[str]) -> None:
    """Raise one DataImportError listing every problem, if there is any."""
    if errors:
        raise DataImportError(
            "The import data is invalid:\n" + "\n".join(f"- {e}" for e in errors)
        )
