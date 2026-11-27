from collections import Counter

from django.test import Client

from ._exceptions import DataImportError

type Records = dict | list[dict]


class Api:
    """
    The app's REST API, called in-process as a logged-in user, so that the
    imported records get the app's own permissions and validation. Counts the
    records it creates, per endpoint.
    """

    def __init__(self, username: str, password: str):
        self._client = Client(SERVER_NAME="localhost")
        if not self._client.login(username=username, password=password):
            raise DataImportError("Invalid username or password.")
        self.created: Counter[str] = Counter()

    def list(self, endpoint: str, **filters) -> list[dict]:
        return self._client.get(f"/api/v1/{endpoint}/", filters).json()

    def create(self, endpoint: str, data: Records, description: str) -> Records:
        """Create one record, or a list of records in one request."""
        response = self._client.post(
            f"/api/v1/{endpoint}/", data, content_type="application/json"
        )
        if response.status_code != 201:
            raise DataImportError(f"{description}: {response.json()}")
        self.created[endpoint] += len(data) if isinstance(data, list) else 1
        return response.json()
