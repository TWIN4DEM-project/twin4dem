import shutil
from pathlib import Path

import pytest

from common.management.commands._data_import._reader import Delivery, read_delivery

TESTLAND_DIR = Path(__file__).parents[3] / "data" / "constitutional" / "testland"


@pytest.fixture
def testland_copy(tmp_path) -> Path:
    """A copy of Testland's CSV files, for a test to edit into a variant."""
    return shutil.copytree(TESTLAND_DIR, tmp_path / "testland")


@pytest.fixture
def testland_delivery() -> Delivery:
    """Testland, read and validated."""
    return read_delivery(TESTLAND_DIR)
