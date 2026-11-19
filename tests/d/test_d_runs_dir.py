"""D2 (docs/D-DESIGN.md): MOCO_RUNS_DIR is where saved records go (each turn's folder with
turn.json, each run's folder, charts, and from Part S the statistics job folders). Default:
the project's runs folder, as today (test_d_off.py). Made if missing, parents included.

D8: with MOCO_RUNS_DIR set, a turn's turn.json and a count's run folder are under it and
nothing is written under the project's runs.

The commands keep their memory out of the project's var with --db (agent-ask) or leave it
there (serve), so that D1 does not come into these tests. Every command runs against a copy
of the program (dsupport.Sandbox). Not tested (kit-log/raw/D-A-notes.txt): whether
--runs-dir on the command line wins over MOCO_RUNS_DIR (D2 does not say), the stage 1
command `ask`, and the statistics job folders (they need R).
"""
from datetime import timedelta

from dsupport import (A_NAME, COUNTY_FIRST, COUNTY_Q, COUNTY_STEPS, SYNTHETIC_Q, SYNTHETIC_STEPS,
                      Sandbox, files_under, make_copies, message, model_env, project_folders,
                      run_folders, serve_env, turn_folders, utc_now)


def new_runs(tmp_path):
    """A runs folder two levels deep that does not exist yet."""
    runs = tmp_path / "records" / "runs"
    assert not runs.parent.exists()
    return runs


def test_agent_ask_saves_the_turn_the_run_and_the_chart_under_the_runs_dir(tmp_path):
    """agent-ask with MOCO_RUNS_DIR set to a new folder two levels deep: the turn's
    turn.json, the count's run folder and its chart are under it; nothing is written under
    the project's runs. The real project's var/ and runs/ are listed before and after."""
    before = project_folders()
    box, runs = Sandbox(tmp_path), new_runs(tmp_path)
    result = box.run("agent-ask", SYNTHETIC_Q, "--db", tmp_path / "agent.db",
                     env=model_env(MOCO_RUNS_DIR=runs), steps=SYNTHETIC_STEPS)
    assert result.code == 0, result.explain()
    assert len(turn_folders(runs)) == 1, "no turn.json under MOCO_RUNS_DIR"
    (run,) = run_folders(runs)
    (chart,) = [line for line in result.lines if line.startswith("CHART: ")]
    assert chart[len("CHART: "):].startswith(str(run)), chart
    assert files_under(box.runs) == [], f"written under the project's runs: {files_under(box.runs)}"
    assert project_folders() == before, "the real project's var/ or runs/ changed"


def test_serve_saves_its_records_under_the_runs_dir(tmp_path):
    """serve (the Slack stand-in, one message) with MOCO_RUNS_DIR: the turn's turn.json, the
    count's run folder and the chart it uploads are under it; nothing under the project's
    runs."""
    box, runs = Sandbox(tmp_path), new_runs(tmp_path)
    result = box.run("serve", env=serve_env(MOCO_RUNS_DIR=runs), steps=SYNTHETIC_STEPS,
                     events=[message(SYNTHETIC_Q)])
    assert result.code == 0, result.explain()
    assert result.report["answered"] == [True], result.explain()
    assert len(turn_folders(runs)) == 1, "no turn.json under MOCO_RUNS_DIR"
    (run,) = run_folders(runs)
    uploads = result.report["uploads"]
    assert uploads and all(u["file"].startswith(str(run)) for u in uploads), uploads
    assert files_under(box.runs) == [], f"written under the project's runs: {files_under(box.runs)}"


def test_a_county_count_saves_its_run_folder_under_the_runs_dir(tmp_path, monkeypatch):
    """A county-mode count (agent-ask, MOCO_DATA=county, a copy in the state folder) saves
    its run folder and the turn's turn.json under MOCO_RUNS_DIR; nothing under the project's
    runs."""
    box, runs, state = Sandbox(tmp_path), new_runs(tmp_path), tmp_path / "state"
    make_copies(monkeypatch, box.sources_dir, state, A_NAME, [utc_now() - timedelta(hours=1)])
    result = box.run("agent-ask", COUNTY_Q, "--db", tmp_path / "agent.db",
                     env=model_env(MOCO_DATA="county", MOCO_STATE_DIR=state,
                                   MOCO_RUNS_DIR=runs), steps=COUNTY_STEPS)
    assert result.code == 0, result.explain()
    assert result.lines[0].startswith(COUNTY_FIRST), result.explain()
    (run_line,) = [line for line in result.lines if line.startswith("RUN IDS: ")]
    run_id = run_line[len("RUN IDS: "):]
    assert (runs / run_id / "manifest.json").is_file(), "the count's run is not under it"
    assert len(turn_folders(runs)) == 1, "no turn.json under MOCO_RUNS_DIR"
    assert files_under(box.runs) == [], f"written under the project's runs: {files_under(box.runs)}"
