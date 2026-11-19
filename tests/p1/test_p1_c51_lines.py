"""Brief S3-R15-A: C51 points 5 and 6 of docs/S3A-DESIGN.md (D-071) that no test proved
(CHAT-BUILDS-check-6, PROOF GAP 3; its breaks B53 and B54), and the test guards of "C51, after
CHAT-BUILDS-check-6" (S3-R14-A's question 1). Tests only; the program does not change.

- Point 5, the three lines: `agent-ask` prints `MODEL: ` with ANTHROPIC_MODEL under `anthropic`
  and NVIDIA_MODEL under `nvidia`; serve's first log line and its printed line name the same.
- Point 6, the two tools: given `--models X`, tools/county_check.py and tools/loop_check.py build
  their client from settings whose active service's model is X and whose other model is as set.
- The guards: every conftest guard, p1support.run_command and dsupport.Sandbox take every
  ANTHROPIC_ variable of the real environment out, as they take NVIDIA_ ones.

No model service, Slack or site is reached: `agent-ask` runs a question stage 1's guard refuses
(no model call), with every address at a closed local port (run_command); serve runs against a
copy of the program with the Slack and model stand-ins and no message (dsupport.Sandbox, as
tests/d/test_d_start_line.py runs it); each tool runs in this process with an empty cases file
and its client class replaced by a recorder that sends nothing. Every key is made up (p1support's
FAKE_SECRETS and FAKE_ANTHROPIC_KEY, built from pieces, shaped like no real key); both models
are given names of the tests' own, so a default cannot hide a mistake. All data is SYNTHETIC.

READINGS (also in kit-log/raw/S3-R15-A-notes.txt):
- "Serve's first log line" is the first line serve writes to agent.log (`serve starting:
  model=<model> ...`, slack_app.serve); "its printed line" is the start line of
  tests/d/dsupport.py's START_LINE, with the model filled in.
- "The settings the tool builds its client from" are the one argument the tool gives
  llm.NvidiaModelClient (each tool imports the name, so the recorder is put at the tool's
  own name).
- "What a guarded test sees" is os.environ inside the test, after its directory's autouse guard
  has run: proved for tests/p1 by a class-scoped fixture that sets the variables before the
  guard runs, and for each conftest guard (p1, s3, s3s, t; tests/d and tests/s3s2 load the s3
  and s3s guards) by running the guard's own function with the variables set. "What run_command
  sees" is the environment it hands the subprocess (subprocess.run replaced by a recorder);
  tests/d's commands get theirs from dsupport.Sandbox.environ. Only names are compared and shown,
  never a value.
"""
import importlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

TESTS = Path(__file__).resolve().parents[1]
for folder in (TESTS / "s3", TESTS / "d"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import p1support  # noqa: E402
from dsupport import START_LINE, Sandbox, log_lines, serve_env  # noqa: E402
from p1support import (DEAD_PROXY, FAKE_ANTHROPIC_KEY, FAKE_SECRETS, assert_no_anthropic_key,  # noqa: E402
                       assert_no_secret, explain, run_command)
from s3support import use_sources, write_sources  # noqa: E402
from support import REFUSED, REPO  # noqa: E402

N_MODEL = "test-org/nvidia-model-r15"
A_MODEL = "test-org/anthropic-model-r15"
X_MODEL = "test-org/given-with-models-r15"
MODELS = {"nvidia": N_MODEL, "anthropic": A_MODEL}
PROVIDERS = ["anthropic", "nvidia"]
BOTH = {"NVIDIA_API_KEY": FAKE_SECRETS["NVIDIA_API_KEY"], "NVIDIA_MODEL": N_MODEL,
        "ANTHROPIC_API_KEY": FAKE_ANTHROPIC_KEY, "ANTHROPIC_MODEL": A_MODEL}


def output(proc):
    return proc.stdout + proc.stderr


def no_key_shown(text):
    assert_no_secret(text)
    assert_no_anthropic_key(text)


# ==== point 5: the terminal's MODEL: line ========================================================

@pytest.mark.parametrize("provider", PROVIDERS)
def test_agent_ask_prints_the_active_services_model(tmp_path, provider):
    """A question stage 1's guard refuses (exit 3, no model call), so nothing is sent; both
    addresses are a closed local port all the same."""
    question, _ = REFUSED["U6"]
    (tmp_path / "runs").mkdir()
    env = dict(BOTH, MOCO_MODEL_PROVIDER=provider, NVIDIA_BASE_URL=DEAD_PROXY,
               ANTHROPIC_BASE_URL=DEAD_PROXY)
    proc = run_command(tmp_path, "agent-ask", question, "--db", str(tmp_path / "agent.db"),
                       "--runs-dir", str(tmp_path / "runs"), extra_env=env)
    assert proc.returncode == 3, explain(proc)
    lines = [line.strip() for line in proc.stdout.splitlines()]
    assert [line for line in lines if line.startswith("MODEL:")] == \
        [f"MODEL: {MODELS[provider]}"], explain(proc)
    no_key_shown(output(proc))


# ==== point 5: serve's first log line and its printed line =======================================

@pytest.mark.parametrize("provider", PROVIDERS)
def test_serve_names_the_active_services_model_in_its_first_log_line_and_printed_line(
        tmp_path, provider):
    box = Sandbox(tmp_path)
    result = box.run("serve", env=serve_env(MOCO_MODEL_PROVIDER=provider, **BOTH))
    assert result.code == 0, result.explain()
    log = box.var / "agent.log"
    printed = [line for line in result.lines if line.startswith("The agent is connecting")]
    assert printed == [START_LINE.format(model=MODELS[provider], data="SYNTHETIC", log=log)], \
        result.explain()
    logged = [line for line in log_lines(log) if line.strip()]
    assert logged, "serve wrote no log line"
    found = re.search(r"serve starting: model=(\S+) ", logged[0])
    assert found and found[1] == MODELS[provider], logged[0]
    no_key_shown(result.stdout + result.stderr + "\n".join(logged))


# ==== point 6: the two tools use with_model ======================================================

def load_tool(monkeypatch, name):
    """tools/<name>.py, imported with tools/ on the path for this test only."""
    monkeypatch.syspath_prepend(str(REPO / "tools"))
    return importlib.import_module(name)


def recorder(monkeypatch, tool):
    """Put a recorder in the place of the client class the tool builds; it keeps the settings
    it is given and sends nothing."""
    made = []

    class Recorder:
        model_id = "recorder-sends-nothing"

        def __init__(self, settings, *args, **kwargs):
            made.append(settings)

        def step(self, messages, tools):
            raise AssertionError("the recorder sends nothing")

    monkeypatch.setattr(tool, "NvidiaModelClient", Recorder)
    return made


def tool_environment(monkeypatch, tmp_path, provider):
    """The settings the tool reads (the environment; the guard's empty settings file)."""
    monkeypatch.setenv("MOCO_MODEL_PROVIDER", provider)
    monkeypatch.setenv("MOCO_STATE_DIR", str(tmp_path / "state"))
    for key, value in BOTH.items():
        monkeypatch.setenv(key, value)


def cases_file(tmp_path, data):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def assert_built_with(made, provider):
    assert len(made) == 1, f"{len(made)} clients built"
    (settings,) = made
    other = "nvidia" if provider == "anthropic" else "anthropic"
    assert getattr(settings, f"{provider}_model") == X_MODEL, \
        "the active service's model is not the one --models gives"
    assert getattr(settings, f"{other}_model") == MODELS[other], \
        "the other service's model changed"
    assert settings.moco_model_provider == provider


@pytest.mark.parametrize("provider", PROVIDERS)
def test_loop_check_builds_its_client_with_the_model_given(tmp_path, monkeypatch, capsys,
                                                           provider):
    tool = load_tool(monkeypatch, "loop_check")
    made = recorder(monkeypatch, tool)
    tool_environment(monkeypatch, tmp_path, provider)
    cases = cases_file(tmp_path, {"today": "2026-11-10", "cases": []})
    code = tool.main(["--models", X_MODEL, "--cases", cases, "--repeat", "1"])
    out = capsys.readouterr()
    assert code in (0, 1), out.out + out.err
    assert_built_with(made, provider)
    no_key_shown(out.out + out.err)


@pytest.mark.parametrize("provider", PROVIDERS)
def test_county_check_builds_its_client_with_the_model_given(tmp_path, monkeypatch, capsys,
                                                             provider):
    """The fixture source files of tests/s3 stand for config/sources/ (s3support.use_sources);
    the state folder is in tmp_path and holds no copy; no case needs one."""
    use_sources(monkeypatch, write_sources(tmp_path / "sources", ("arrests_like",)))
    tool = load_tool(monkeypatch, "county_check")
    made = recorder(monkeypatch, tool)
    tool_environment(monkeypatch, tmp_path, provider)
    code = tool.main(["--models", X_MODEL, "--cases", cases_file(tmp_path, {"cases": []}),
                      "--repeat", "1"])
    out = capsys.readouterr()
    assert code in (0, 1), out.out + out.err
    assert_built_with(made, provider)
    no_key_shown(out.out + out.err)


# ==== the guards: no ANTHROPIC_ variable of the real environment is seen ==========================

MADE_UP = {"ANTHROPIC_API_KEY": FAKE_ANTHROPIC_KEY, "ANTHROPIC_MODEL": "made-up-model-r15"}
PREMISE = {"NVIDIA_MODEL": "made-up-nvidia-model-r15"}  # taken out today: the way of testing works


def seen(environ):
    """The names (never the values) of the made-up variables that `environ` still holds."""
    return sorted(key for key in (*MADE_UP, *PREMISE) if key in environ)


@pytest.fixture(scope="class")
def _set_before_the_guard():
    """Class scope: set up before tests/p1/conftest.py's function-scoped autouse guard."""
    with pytest.MonkeyPatch.context() as mp:
        for key, value in {**MADE_UP, **PREMISE}.items():
            mp.setenv(key, value)
        yield


class TestAGuardedTest:
    def test_sees_no_anthropic_variable_of_the_real_environment(self, _set_before_the_guard):
        assert seen(os.environ) == [], "a guarded test sees these variables"


GUARDS = {  # the conftest, and its autouse guard
    "p1": (TESTS / "p1" / "conftest.py", "_stage2_guards"),
    "s3 (and d)": (TESTS / "s3" / "conftest.py", "_stage3_guards"),
    "s3s (and s3s2)": (TESTS / "s3s" / "conftest.py", "_stage3s_guards"),
    "t": (TESTS / "t" / "conftest.py", "_part_t_guards"),
}


@pytest.mark.parametrize("which", list(GUARDS))
def test_each_conftest_guard_takes_anthropic_variables_out(tmp_path_factory, monkeypatch, which):
    """The guard's own function, run with the made-up variables in the environment."""
    path, name = GUARDS[which]
    spec = importlib.util.spec_from_file_location(f"r15_guard_{path.parent.name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    guard = getattr(module, name).__wrapped__  # the function under pytest's fixture marker
    for key, value in {**MADE_UP, **PREMISE}.items():
        monkeypatch.setenv(key, value)
    with pytest.MonkeyPatch.context() as mp:
        running = guard(tmp_path_factory, mp)
        next(running)
        inside = seen(os.environ)
        with pytest.raises(StopIteration):
            next(running)
    assert inside == [], f"the {which} guard leaves these variables in place"
    assert seen(os.environ) == sorted({**MADE_UP, **PREMISE}), "premise: set again after"


def test_run_command_hands_on_no_anthropic_variable(tmp_path, monkeypatch):
    for key, value in {**MADE_UP, **PREMISE}.items():
        monkeypatch.setenv(key, value)
    handed = []

    def run(argv, **kwargs):
        handed.append(seen(kwargs["env"]))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    p1support.run_command(tmp_path, "agent-ask", "nothing is run")
    assert handed == [[]], "run_command hands these variables to the command"


def test_the_part_d_sandbox_hands_on_no_anthropic_variable(tmp_path, monkeypatch):
    for key, value in {**MADE_UP, **PREMISE}.items():
        monkeypatch.setenv(key, value)
    environ = Sandbox(tmp_path).environ({})
    assert seen(environ) == ["NVIDIA_MODEL"], \
        "the sandbox hands these to the command (NVIDIA_MODEL is its own stand-in's, not ours)"
    assert environ["NVIDIA_MODEL"] != PREMISE["NVIDIA_MODEL"]
