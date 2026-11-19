"""Setup for the stage 2 tests (docs/P1-DESIGN.md section 14, docs/P1A-DESIGN.md A16).
These guards hold for every test in tests/p1/:

- No network: sockets can neither connect nor look up a name.
- No real secrets file: MOCO_ENV_FILE points at an empty file in a temporary folder, HOME
  points into that folder too (so "~/.config/..." cannot reach the real file), and no
  NVIDIA_, SLACK_, MOCO_ or OPENAI_ variable from the real environment is visible.
- The repo's var/ folder is left exactly as it was (a test that changes it fails). So do not
  run the tests while the agent's `serve` command is running: its own writes to var/ would
  fail this check. The repo's runs/ folder gains and loses no entry either (every test
  passes a runs folder in tmp_path; a turn record or a run saved in the real runs/ fails).
- No real sleep from moco_agent code: time is injected (sleep, clock, today, now).

A blocked network call or sleep raises inside the code under test, and that code may catch
it (process_event and handle_question are built never to raise). So each attempt is also
recorded, and the test fails after it ends if any was made.
"""
import os
import socket
import sys
import time
from pathlib import Path

import pytest

# Make tests/p1/p1support.py importable, with assert rewriting, like tests/support.py.
sys.path.insert(0, str(Path(__file__).resolve().parent))
pytest.register_assert_rewrite("p1support")

REPO = Path(__file__).resolve().parents[2]
VAR = REPO / "var"
RUNS = REPO / "runs"


def _var_snapshot():
    if not VAR.exists():
        return None
    entries = []
    for path in VAR.rglob("*"):
        try:
            stat = path.stat()
        except FileNotFoundError:  # a file that went away while looking
            continue
        entries.append((str(path.relative_to(VAR)), stat.st_size, stat.st_mtime_ns))
    return sorted(entries)


# One sleep guard for the whole run, reporting to the test that is running. (A default
# argument such as `sleep=time.sleep`, bound when a moco_agent module is first imported,
# then still reports to the right test.)
_REAL_SLEEP = time.sleep
_STATE = {"violations": []}


def _guarded_sleep(seconds):
    caller = sys._getframe(1).f_globals.get("__name__", "")
    if caller.startswith("moco_agent"):
        _STATE["violations"].append(f"a real time.sleep({seconds!r}) from {caller}")
        raise AssertionError(f"real time.sleep({seconds!r}) called from {caller}; "
                             f"the tests inject sleep")
    return _REAL_SLEEP(seconds)  # e.g. subprocess's own polling


def _runs_entries():
    # Stage 1's chart code keeps matplotlib's cache in runs/.matplotlib and makes that
    # folder on first use (core.py), so on a fresh copy of the repo the `ask` command
    # creates it. That is not a test changing runs/: it is left out, and a missing runs/
    # counts as empty. (Planning chat, 2026-11-11, after its check of the tests.)
    if not RUNS.exists():
        return []
    return sorted(name for name in os.listdir(RUNS) if name != ".matplotlib")


@pytest.fixture(autouse=True)
def _stage2_guards(tmp_path_factory, monkeypatch):
    home = tmp_path_factory.mktemp("home")
    empty_env = home / "empty.env"
    empty_env.write_text("", encoding="utf-8")
    for key in list(os.environ):
        if key.startswith(("NVIDIA_", "SLACK_", "MOCO_", "OPENAI_", "ANTHROPIC_")):
            monkeypatch.delenv(key)
    monkeypatch.setenv("MOCO_ENV_FILE", str(empty_env))
    monkeypatch.setenv("HOME", str(home))

    violations = []
    _STATE["violations"] = violations  # the sleep guard below reports to the running test

    def no_network(*args, **kwargs):
        violations.append("a network call")
        raise RuntimeError("network use is blocked in the stage 2 tests")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket.socket, "connect_ex", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket, "getaddrinfo", no_network)

    monkeypatch.setattr(time, "sleep", _guarded_sleep)

    before, runs_before = _var_snapshot(), _runs_entries()
    yield violations
    assert _var_snapshot() == before, "a stage 2 test changed the repo's var/ folder"
    assert _runs_entries() == runs_before, "a stage 2 test changed the repo's runs/ folder"
    assert not violations, f"blocked during the test: {violations}"

# The runs_dir fixture comes from tests/conftest.py.
