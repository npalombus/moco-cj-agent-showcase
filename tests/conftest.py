import sys
from pathlib import Path

import pytest

# Make tests/support.py importable under any pytest import mode, with assert rewriting.
sys.path.insert(0, str(Path(__file__).resolve().parent))
pytest.register_assert_rewrite("support")


@pytest.fixture
def runs_dir(tmp_path):
    """A fresh, empty runs folder inside pytest's tmp_path (nothing lands in the repo)."""
    path = tmp_path / "runs"
    path.mkdir()
    return path
