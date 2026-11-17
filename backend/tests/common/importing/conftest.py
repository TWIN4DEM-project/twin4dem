import shutil
from pathlib import Path

import pytest

TESTLAND_DIR = Path(__file__).parents[2] / "data" / "constitutional" / "testland"


@pytest.fixture
def testland_dir() -> Path:
    """The complete, valid Testland delivery. Read-only: do not edit it in tests."""
    return TESTLAND_DIR


@pytest.fixture
def testland_copy(tmp_path) -> Path:
    """A private copy of Testland that a test can edit to build a variant."""
    target = tmp_path / "testland"
    shutil.copytree(TESTLAND_DIR, target)
    return target
