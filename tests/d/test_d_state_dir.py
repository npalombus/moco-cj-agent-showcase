"""D1 (docs/D-DESIGN.md): the memory file and the log file follow MOCO_STATE_DIR.

- the memory file is <state dir>/agent.db for serve, agent-ask and requests; a --db given on
  the command line still wins;
- the log file is <state dir>/agent.log for serve;
- the folder is made if it is missing, parents included; if it cannot be made or written,
  the command stops before connecting to anything, with one line naming MOCO_STATE_DIR and
  the exit code of any other settings error (4 today).

D8: with MOCO_STATE_DIR set to a new folder two levels deep, serve (with the Slack
stand-in), agent-ask and requests use <state dir>/agent.db; serve writes <state
dir>/agent.log; nothing is written under the project's var; --db wins; a state folder that
cannot be made stops the command before the model or Slack is touched.

Readings (kit-log/raw/D-A-notes.txt): "two levels deep" is a folder whose parent does not
exist either. "Nothing is written under the project's var" is checked as: no file at all
under the copy's var/ after the command. "One line" is one non-empty line on standard output
and standard error together. "Before the model or Slack is touched": no model client and no
Slack app or Socket Mode handler was made, and no model call. Every command runs against a
copy of the program (dsupport.Sandbox); agent-ask is given --runs-dir in tmp_path so that
D2 does not come into these tests.
"""
import os
import stat

import pytest

from support import SUPPORTED

from dsupport import (SETTINGS_EXIT, SYNTHETIC_Q, SYNTHETIC_STEPS, Sandbox, Step, db_text,
                      files_under, log_lines, message, model_env, project_folders, refused_db,
                      serve_env)
from p1support import ONE_COUNT_TEXT, count, finish

OTHER_Q = SUPPORTED["S3"][0]  # "Monthly arrests in 2025 for people under 18"
OTHER_STEPS = (Step(count(2025, "under_18")), Step(finish("finding", ONE_COUNT_TEXT)))
REFUSED_STATE = "Show ibis arrests by neighborhood in 2025."
REFUSED_OTHER = "Show egret arrests by neighborhood in 2025."


def new_state(tmp_path):
    """A state folder two levels deep that does not exist yet."""
    state = tmp_path / "mount" / "state"
    assert not state.parent.exists()
    return state


def agent_ask(box, tmp_path, question, state, *extra, steps=SYNTHETIC_STEPS):
    return box.run("agent-ask", question, "--runs-dir", tmp_path / "runs", *extra,
                   env=model_env(MOCO_STATE_DIR=state), steps=steps)


# ---- the memory file -------------------------------------------------------------------------

def test_agent_ask_keeps_its_memory_in_the_state_dir(tmp_path):
    """agent-ask with MOCO_STATE_DIR set to a new folder two levels deep: the folder is made,
    the turn is in <state dir>/agent.db, and nothing is written under the project's var. The
    real project's var/ and runs/ are listed before and after: nothing changed."""
    before = project_folders()
    box, state = Sandbox(tmp_path), new_state(tmp_path)
    result = agent_ask(box, tmp_path, SYNTHETIC_Q, state)
    assert result.code == 0, result.explain()
    assert (state / "agent.db").is_file(), "no memory file in the state folder"
    assert SYNTHETIC_Q in db_text(state / "agent.db")
    assert files_under(box.var) == [], f"written under the project's var: {files_under(box.var)}"
    assert project_folders() == before, "the real project's var/ or runs/ changed"


def test_requests_makes_and_reads_the_memory_in_the_state_dir(tmp_path):
    """requests with a new MOCO_STATE_DIR: the folder and <state dir>/agent.db are made,
    nothing under the project's var."""
    box, state = Sandbox(tmp_path), new_state(tmp_path)
    result = box.run("requests", env={"MOCO_STATE_DIR": state})
    assert result.code == 0, result.explain()
    assert (state / "agent.db").is_file(), "no memory file in the state folder"
    assert files_under(box.var) == []


def test_requests_lists_the_turns_of_the_state_dir_memory_only(tmp_path):
    """The turn refused in <state dir>/agent.db is listed; one refused in the project's
    var/agent.db is not."""
    box, state = Sandbox(tmp_path), tmp_path / "mount" / "state"
    refused_db(tmp_path / "scratch-state", state / "agent.db", REFUSED_STATE)
    refused_db(tmp_path / "scratch-var", box.var / "agent.db", REFUSED_OTHER)
    result = box.run("requests", env={"MOCO_STATE_DIR": state})
    assert result.code == 0, result.explain()
    assert any(REFUSED_STATE in line for line in result.lines), result.explain()
    assert not any(REFUSED_OTHER in line for line in result.lines), result.explain()


def test_serve_keeps_its_memory_and_log_in_the_state_dir(tmp_path):
    """serve (the Slack stand-in, one message) with a new MOCO_STATE_DIR: the turn is in
    <state dir>/agent.db, the log is <state dir>/agent.log (its start line and the event's
    line), and nothing is written under the project's var."""
    box, state = Sandbox(tmp_path), new_state(tmp_path)
    result = box.run("serve", env=serve_env(MOCO_STATE_DIR=state), steps=SYNTHETIC_STEPS,
                     events=[message(SYNTHETIC_Q)])
    assert result.code == 0, result.explain()
    assert result.report["answered"] == [True], result.explain()
    assert SYNTHETIC_Q in db_text(state / "agent.db")
    logged = log_lines(state / "agent.log")
    assert any("serve starting" in line for line in logged), logged
    assert any("label=answered" in line for line in logged), logged
    assert files_under(box.var) == [], f"written under the project's var: {files_under(box.var)}"


# ---- --db still wins ---------------------------------------------------------------------------

def test_db_on_the_command_line_wins_for_agent_ask(tmp_path):
    """Without --db the turn goes to <state dir>/agent.db; with --db it goes to that file,
    and the state folder's memory does not get it."""
    box, state = Sandbox(tmp_path), new_state(tmp_path)
    other = tmp_path / "elsewhere" / "chosen.db"
    first = agent_ask(box, tmp_path, SYNTHETIC_Q, state)
    assert first.code == 0, first.explain()
    second = agent_ask(box, tmp_path, OTHER_Q, state, "--db", other, steps=OTHER_STEPS)
    assert second.code == 0, second.explain()
    assert SYNTHETIC_Q in db_text(state / "agent.db")
    assert OTHER_Q not in db_text(state / "agent.db")
    assert OTHER_Q in db_text(other) and SYNTHETIC_Q not in db_text(other)
    assert files_under(box.var) == []


def test_db_on_the_command_line_wins_for_requests(tmp_path):
    """requests reads <state dir>/agent.db, or the --db file when one is given."""
    box, state = Sandbox(tmp_path), tmp_path / "mount" / "state"
    other = tmp_path / "elsewhere" / "chosen.db"
    refused_db(tmp_path / "scratch-state", state / "agent.db", REFUSED_STATE)
    refused_db(tmp_path / "scratch-other", other, REFUSED_OTHER)
    plain = box.run("requests", env={"MOCO_STATE_DIR": state})
    chosen = box.run("requests", "--db", other, env={"MOCO_STATE_DIR": state})
    assert plain.code == 0 and chosen.code == 0, plain.explain() + chosen.explain()
    assert any(REFUSED_STATE in line for line in plain.lines), plain.explain()
    assert not any(REFUSED_OTHER in line for line in plain.lines), plain.explain()
    assert any(REFUSED_OTHER in line for line in chosen.lines), chosen.explain()
    assert not any(REFUSED_STATE in line for line in chosen.lines), chosen.explain()


# ---- a state folder that cannot be made or written --------------------------------------------

def stopped_on_the_state_dir(result, box):
    """Exit 4, one line naming MOCO_STATE_DIR (no traceback), no model and no Slack touched,
    nothing under the project's var."""
    lines = result.lines + result.err_lines
    assert result.code == SETTINGS_EXIT, result.explain()
    assert len(lines) == 1 and "MOCO_STATE_DIR" in lines[0], result.explain()
    assert "Traceback" not in result.stderr
    report = result.report
    assert report["model_clients"] == 0 and report["model_calls"] == 0, "the model was touched"
    assert report["apps"] == 0 and report["socket_handlers"] == 0, "Slack was touched"
    assert files_under(box.var) == []


def command_for(name, tmp_path, state):
    if name == "serve":
        return ("serve",), serve_env(MOCO_STATE_DIR=state)
    if name == "agent-ask":
        return (("agent-ask", SYNTHETIC_Q, "--runs-dir", tmp_path / "runs"),
                model_env(MOCO_STATE_DIR=state))
    return ("requests",), {"MOCO_STATE_DIR": state}


@pytest.mark.parametrize("name", ["serve", "agent-ask", "requests"])
def test_a_state_dir_that_cannot_be_made_stops_the_command(tmp_path, name):
    """MOCO_STATE_DIR names a folder inside a file, so it cannot be made: the command stops
    with one line naming MOCO_STATE_DIR and exit code 4, before the model or Slack."""
    box = Sandbox(tmp_path)
    blocker = tmp_path / "a-file"
    blocker.write_text("not a folder\n", encoding="utf-8")
    argv, env = command_for(name, tmp_path, blocker / "state")
    result = box.run(*argv, env=env, steps=SYNTHETIC_STEPS, events=[message(SYNTHETIC_Q)])
    stopped_on_the_state_dir(result, box)


@pytest.mark.parametrize("name", ["serve", "agent-ask"])
def test_a_state_dir_that_cannot_be_written_stops_the_command(tmp_path, name):
    """MOCO_STATE_DIR names a folder that exists but cannot be written: the same stop."""
    box = Sandbox(tmp_path)
    state = tmp_path / "read-only"
    state.mkdir()
    state.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        assert not os.access(state, os.W_OK), "premise: the folder cannot be written"
        argv, env = command_for(name, tmp_path, state)
        result = box.run(*argv, env=env, steps=SYNTHETIC_STEPS, events=[message(SYNTHETIC_Q)])
    finally:
        state.chmod(stat.S_IRWXU)
    stopped_on_the_state_dir(result, box)
    assert list(state.iterdir()) == []
