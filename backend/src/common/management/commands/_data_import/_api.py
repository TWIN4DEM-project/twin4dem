from django.test import Client

from ._exceptions import DataImportError


class Api:
    """
    The app's REST API, called in-process as a logged-in user, so that the
    imported records get the app's own permissions and validation.
    """

    def __init__(self, username: str, password: str):
        self._client = Client(SERVER_NAME="localhost")
        if not self._client.login(username=username, password=password):
            raise DataImportError("Invalid username or password.")

    def list(self, endpoint: str, **filters) -> list[dict]:
        return self._client.get(f"/api/v1/{endpoint}/", filters).json()
