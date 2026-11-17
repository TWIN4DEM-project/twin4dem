class DataImportError(Exception):
    """Base class for the errors that stop an import before anything is saved."""


class SourceError(DataImportError):
    """The location given for the import cannot be used."""
