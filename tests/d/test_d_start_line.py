"""D6 (docs/D-DESIGN.md): the line serve prints at start says `data SYNTHETIC` only in
SYNTHETIC mode and `data COUNTY (real county open data)` in county mode, and names the log
file where D1 puts it. D8: the start line in each mode.

Reading (kit-log/raw/D-A-notes.txt): only the data phrase and the log file change, so the
line is today's line (slack_app.serve, written out by hand in dsupport.START_LINE) with
those two filled in. serve runs against a copy of the program with the Slack stand-in and
no message; MOCO_REFRESH_HOURS is unset, so nothing is fetched.
"""
import pytest

from dsupport import (Sandbox, log_lines, project_folders, serve_env, start_line, start_lines)

COUNTY = "COUNTY (real county open data)"


def serve(box, **env):
    result = box.run("serve", env=serve_env(**env))
    assert result.code == 0, result.explain()
    return result


@pytest.mark.parametrize("data", [None, "synthetic"], ids=["unset", "synthetic"])
def test_synthetic_mode_says_synthetic_and_names_the_log_in_the_state_dir(tmp_path, data):
    box, state = Sandbox(tmp_path), tmp_path / "mount" / "state"
    env = {"MOCO_STATE_DIR": state} if data is None else {"MOCO_STATE_DIR": state,
                                                          "MOCO_DATA": data}
    result = serve(box, **env)
    assert start_lines(result) == [start_line("SYNTHETIC", state / "agent.log")], \
        result.explain()


def test_county_mode_says_county_and_names_the_log_in_the_state_dir(tmp_path):
    """County mode: the line says data COUNTY (real county open data), not SYNTHETIC, and
    names <state dir>/agent.log, which is the log serve wrote. The real project's var/ and
    runs/ are listed before and after."""
    before = project_folders()
    box, state = Sandbox(tmp_path), tmp_path / "mount" / "state"
    result = serve(box, MOCO_DATA="county", MOCO_STATE_DIR=state)
    (line,) = start_lines(result)
    assert line == start_line(COUNTY, state / "agent.log"), result.explain()
    assert "SYNTHETIC" not in line
    assert any("serve starting" in entry for entry in log_lines(state / "agent.log"))
    assert project_folders() == before, "the real project's var/ or runs/ changed"


def test_county_mode_with_no_state_dir_names_the_project_var_log(tmp_path):
    box = Sandbox(tmp_path)
    result = serve(box, MOCO_DATA="county")
    assert start_lines(result) == [start_line(COUNTY, box.var / "agent.log")], result.explain()
