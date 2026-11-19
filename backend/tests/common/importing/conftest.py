from pathlib import Path

import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import InMemoryStorage

from common.importing import Delivery, read_delivery, resolve_source

TESTLAND_DIR = Path(__file__).parents[2] / "data" / "constitutional" / "testland"


@pytest.fixture
def testland_dir() -> Path:
    """The complete, valid Testland delivery. Read-only: do not edit it in tests."""
    return TESTLAND_DIR


@pytest.fixture
def testland_storage() -> InMemoryStorage:
    """Testland's CSV files in memory, for a test to edit into a variant."""
    storage = InMemoryStorage()
    for path in TESTLAND_DIR.glob("*.csv"):
        storage.save(path.name, ContentFile(path.read_bytes()))
    return storage


@pytest.fixture
def testland_delivery() -> Delivery:
    """Testland, read and validated."""
    return read_delivery(resolve_source(str(TESTLAND_DIR)))
