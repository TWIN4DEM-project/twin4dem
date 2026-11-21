class DataImportError(Exception):
    """Stops an import before anything is saved, listing every problem found."""

    def __init__(self, *problems: str):
        super().__init__(
            "The import data is invalid:\n" + "\n".join(f"- {p}" for p in problems)
        )


class SourceError(DataImportError):
    """The location given for the import cannot be used."""
