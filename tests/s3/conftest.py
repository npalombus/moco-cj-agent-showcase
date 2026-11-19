"""Setup for the stage 3 Part A tests (docs/S3A-DESIGN.md, C12). The same guards as
tests/p1/conftest.py hold for every test in tests/s3/:

- No network: sockets can neither connect nor look up a name. Every fetch goes through a
  fake transport (s3support.FakeService); nothing reaches a real address.
- No real secrets file: MOCO_ENV_FILE points at an empty file in a temporary folder, HOME
  points into that folder too, and no NVIDIA_, SLACK_, MOCO_ or OPENAI_ variable from the
  real environment is visible. So MOCO_DATA is unset unless a test sets it.
- The repo's var/ folder (the default MOCO_STATE_DIR, C4) is left exactly as it was, and the
  repo's runs/ folder gains and loses no entry. Every test passes its own state folder and
  runs folder in tmp_path.
- No real sleep from moco_agent code.

A blocked network call or sleep raises inside the code under test, and that code may catch
it, so each attempt is also recorded and the test fails after it ends if any was made.
"""
import os
import socket
import sys
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
# Make tests/s3/s3support.py and tests/p1/p1support.py importable, with assert rewriting.
sys.path.insert(0, str(HERE.parent / "p1"))
sys.path.insert(0, str(HERE))
pytest.register_assert_rewrite("s3support", "p1support")

REPO = HERE.parents[1]
VAR = REPO / "var"
RUNS = REPO / "runs"

_REAL_SLEEP = time.sleep
_STATE = {"violations": []}


def _var_snapshot():
    if not VAR.exists():
        return None
    entries = []
    for path in VAR.rglob("*"):
        try:
            stat = path.stat()
        except FileNotFoundError:
            continue
        entries.append((str(path.relative_to(VAR)), stat.st_size, stat.st_mtime_ns))
    return sorted(entries)


def _runs_entries():
    # runs/.matplotlib is stage 1's chart cache (see tests/p1/conftest.py): left out.
    if not RUNS.exists():
        return []
    return sorted(name for name in os.listdir(RUNS) if name != ".matplotlib")


def _guarded_sleep(seconds):
    caller = sys._getframe(1).f_globals.get("__name__", "")
    if caller.startswith("moco_agent"):
        _STATE["violations"].append(f"a real time.sleep({seconds!r}) from {caller}")
        raise AssertionError(f"real time.sleep({seconds!r}) called from {caller}; "
                             f"the tests inject sleep")
    return _REAL_SLEEP(seconds)


@pytest.fixture(autouse=True)
def _stage3_guards(tmp_path_factory, monkeypatch):
    home = tmp_path_factory.mktemp("home")
    empty_env = home / "empty.env"
    empty_env.write_text("", encoding="utf-8")
    for key in list(os.environ):
        if key.startswith(("NVIDIA_", "SLACK_", "MOCO_", "OPENAI_", "ANTHROPIC_")):
            monkeypatch.delenv(key)
    monkeypatch.setenv("MOCO_ENV_FILE", str(empty_env))
    monkeypatch.setenv("HOME", str(home))

    violations = []
    _STATE["violations"] = violations

    def no_network(*args, **kwargs):
        violations.append("a network call")
        raise RuntimeError("network use is blocked in the stage 3 tests")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket.socket, "connect_ex", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket, "getaddrinfo", no_network)
    monkeypatch.setattr(time, "sleep", _guarded_sleep)

    before, runs_before = _var_snapshot(), _runs_entries()
    yield violations
    assert _var_snapshot() == before, "a stage 3 test changed the repo's var/ folder"
    assert _runs_entries() == runs_before, "a stage 3 test changed the repo's runs/ folder"
    assert not violations, f"blocked during the test: {violations}"
