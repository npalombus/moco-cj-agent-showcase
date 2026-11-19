"""Setup for the Part T tests (docs/T-DESIGN.md). The same guards as tests/p1/conftest.py and
tests/s3/conftest.py hold for every test in tests/t/:

- No network: sockets can neither connect nor look up a name. No real model and no real
  Slack: the model is p1support.FakeModel, Slack a FakeSlack.
- No real secrets file: MOCO_ENV_FILE points at an empty file in a temporary folder, HOME
  points into that folder too, and no NVIDIA_, SLACK_, MOCO_ or OPENAI_ variable from the
  real environment is visible. So MOCO_TALK is unset unless a test sets it.
- The repo's var/ folder is left exactly as it was and the repo's runs/ folder gains and
  loses no entry. Every test passes its own store, state folder and runs folder in tmp_path.
- No real sleep from moco_agent code: time is injected (p1support.FakeClock).

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
# tsupport.py here, and the stand-ins of tests/p1 and tests/s3, with assert rewriting.
for folder in (HERE.parent / "p1", HERE.parent / "s3", HERE):
    sys.path.insert(0, str(folder))
pytest.register_assert_rewrite("tsupport", "s3support", "p1support")

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
def _part_t_guards(tmp_path_factory, monkeypatch):
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
        raise RuntimeError("network use is blocked in the Part T tests")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket.socket, "connect_ex", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket, "getaddrinfo", no_network)
    monkeypatch.setattr(time, "sleep", _guarded_sleep)

    before, runs_before = _var_snapshot(), _runs_entries()
    yield violations
    assert _var_snapshot() == before, "a Part T test changed the repo's var/ folder"
    assert _runs_entries() == runs_before, "a Part T test changed the repo's runs/ folder"
    assert not violations, f"blocked during the test: {violations}"
