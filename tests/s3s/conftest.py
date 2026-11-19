"""Setup for the stage 3 Part S tests (docs/S3S-DESIGN.md, S9). The same guards as
tests/s3/conftest.py hold for every test in tests/s3s/:

- No network: sockets can neither connect nor look up a name. Every fetch goes through a
  fake transport (s3support.FakeService); R is started as a local process and reads only
  files in pytest's temporary folder.
- No real secrets file: MOCO_ENV_FILE points at an empty file in a temporary folder, HOME
  points into that folder too, and no NVIDIA_, SLACK_, MOCO_ or OPENAI_ variable from the
  real environment is visible.
- The repo's var/ folder is left exactly as it was, and the repo's runs/ folder gains and
  loses no entry.
- No real sleep from moco_agent code.

The marker `needs_r` is on every test that starts R. Those tests FAIL (never skip) when
`Rscript` or one of the four packages of S9 is not there, with a message saying so, so that
`-m "not needs_r"` runs the rest on a machine without R.
"""
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
# Make tests/s3s, tests/s3 and tests/p1 helpers importable, with assert rewriting.
sys.path.insert(0, str(HERE.parent / "p1"))
sys.path.insert(0, str(HERE.parent / "s3"))
sys.path.insert(0, str(HERE))
pytest.register_assert_rewrite("s3ssupport", "s3sagent", "s3support", "p1support")

REPO = HERE.parents[1]
VAR = REPO / "var"
RUNS = REPO / "runs"
R_PACKAGES = ("MASS", "ggplot2", "jsonlite", "sandwich")

_REAL_SLEEP = time.sleep
_STATE = {"violations": [], "r_checked": None}


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "needs_r: the test starts R (Rscript with MASS, ggplot2, jsonlite and "
                   "sandwich); it fails, not skips, when R is not there")


def _r_problem():
    """None when Rscript and the four packages are there; else what is missing. Checked once."""
    if _STATE["r_checked"] is None:
        rscript = shutil.which("Rscript")
        if rscript is None:
            _STATE["r_checked"] = "Rscript was not found on PATH"
        else:
            code = ("for (p in c(%s)) if (!requireNamespace(p, quietly = TRUE)) "
                    "cat('missing', p, '\\n')" % ", ".join(f'"{p}"' for p in R_PACKAGES))
            done = subprocess.run([rscript, "-e", code], capture_output=True, text=True,
                                  timeout=120)
            missing = done.stdout.strip()
            _STATE["r_checked"] = (f"R packages {missing}" if missing else
                                   (None if done.returncode == 0 else
                                    f"Rscript failed: {done.stderr.strip()[:200]}"))
    return _STATE["r_checked"]


@pytest.fixture(autouse=True)
def _needs_r(request):
    if request.node.get_closest_marker("needs_r") is not None:
        problem = _r_problem()
        if problem:
            pytest.fail(f"needs_r: this test starts R, and {problem}. S9: R really runs in "
                        f"these tests; install R 4.6 with {', '.join(R_PACKAGES)}.",
                        pytrace=False)
    yield


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
def _stage3s_guards(tmp_path_factory, monkeypatch):
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
