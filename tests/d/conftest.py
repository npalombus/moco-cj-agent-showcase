"""Setup for the Part D tests (docs/D-DESIGN.md). Every test in tests/d/ runs under the guards
of tests/s3/conftest.py, imported from that file (nothing copied):

- No network in this process: sockets can neither connect nor look up a name.
- No real secrets file: MOCO_ENV_FILE points at an empty file in a temporary folder, HOME
  points there too, and no NVIDIA_, SLACK_, MOCO_ or OPENAI_ variable from the real
  environment is visible.
- The project's var/ folder is left exactly as it was, and its runs/ folder gains and loses
  no entry (runs/.matplotlib, stage 1's chart cache, left out as before).
- No real sleep from moco_agent code.

Every command (serve, agent-ask, requests, refresh, fetch) runs in a subprocess against a
copy of the program made in pytest's temporary folder (dsupport.Sandbox), never against the
project itself: today's serve opens the project's var/agent.db and purges old turns from
it, so running it here for real could change Nino's memory file. The subprocess blocks its
own network too (tests/d/standin.py).
"""
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
TESTS = HERE.parent
for folder in (TESTS, TESTS / "p1", TESTS / "s3", HERE):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
pytest.register_assert_rewrite("dsupport", "s3support", "p1support")

# tests/s3/conftest.py's autouse guard, loaded under a name of its own so that it is the same
# code and not a copy. pytest finds the fixture by its name in this module.
_spec = importlib.util.spec_from_file_location("d_guards_from_s3", TESTS / "s3" / "conftest.py")
_s3_guards = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_s3_guards)
_stage3_guards = _s3_guards._stage3_guards
