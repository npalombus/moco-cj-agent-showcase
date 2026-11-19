"""Setup for the Part S2 tests (docs/S3S2-DESIGN.md, R9). Every test in tests/s3s2/ runs under
the guards of tests/s3s/conftest.py, loaded from that file (nothing copied):

- No network: sockets can neither connect nor look up a name. The county service is
  s3support.FakeService; the Census service is s2agent.FakeCensus, reached through
  urllib (s2agent.CensusNet).
- No real secrets file: MOCO_ENV_FILE points at an empty file, HOME at a temporary folder,
  and no NVIDIA_, SLACK_, MOCO_ or OPENAI_ variable from the real environment is visible.
  This file also takes CENSUS_API_KEY out of the environment for every test; a test that
  needs a key sets the made-up `TEST-KEY-NOT-REAL` itself.
- The repo's var/ folder is left exactly as it was, and runs/ gains and loses no entry.
- No real sleep from moco_agent code.
- `needs_r` on every test that starts R: it FAILS (never skips) when Rscript or one of the
  four packages is missing.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
TESTS = HERE.parent
_spec = importlib.util.spec_from_file_location("s2_guards_from_s3s", TESTS / "s3s" / "conftest.py")
_s3s = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_s3s)   # also puts tests/p1, tests/s3 and tests/s3s on sys.path
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
pytest.register_assert_rewrite("s2support", "s2agent")

pytest_configure = _s3s.pytest_configure
_needs_r = _s3s._needs_r
_stage3s_guards = _s3s._stage3s_guards


@pytest.fixture(autouse=True)
def _no_census_key(monkeypatch):
    monkeypatch.delenv("CENSUS_API_KEY", raising=False)
    yield
