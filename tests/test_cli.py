"""Point 11: the command line (design section 5), run with the .venv Python through
subprocess, from the repo folder. Run folders go to pytest's tmp_path via --runs-dir."""
import json
import subprocess

from support import (NOT_SYNTHETIC_COPIES, REFUSED, REPO, SUPPORTED, VENV_PYTHON,
                     expected_values)


def run_cli(question, *options):
    assert VENV_PYTHON.is_file(), f"no .venv Python at {VENV_PYTHON}"
    return subprocess.run([str(VENV_PYTHON), "-m", "moco_agent", "ask", question, *options],
                          cwd=REPO, capture_output=True, text=True, timeout=300)


def explain(proc):
    last_error = proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else ""
    return (f"exit code {proc.returncode}: {last_error}\n"
            f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr[-3000:]}")


def run_folders(runs):
    return sorted(p for p in runs.iterdir() if p.is_dir())


def check_printed(proc, run):
    """It prints the plain-language summary, a line DATA: SYNTHETIC, the run id and the
    saved file paths (the design names no stream, so stdout and stderr both count)."""
    output = proc.stdout + proc.stderr
    assert "DATA: SYNTHETIC" in [line.strip() for line in output.splitlines()], explain(proc)
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["run_id"] == run.name
    assert run.name in output, explain(proc)
    assert manifest["user_facing_summary"] in output, explain(proc)
    assert manifest["manifest_path"] in output, explain(proc)
    if manifest["chart_uri"] is not None:
        assert manifest["chart_uri"] in output, explain(proc)
    return manifest


def test_cli_answers_s1_and_exits_0(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    question, year, age_group = SUPPORTED["S1"]
    proc = run_cli(question, "--runs-dir", str(runs))
    assert proc.returncode == 0, explain(proc)
    folders = run_folders(runs)
    assert len(folders) == 1, folders
    manifest = check_printed(proc, folders[0])
    assert manifest["status"] == "ANSWERED"
    assert manifest["computed_values"] == expected_values(year, age_group)
    assert (folders[0] / "chart.png").is_file() and (folders[0] / "report.md").is_file()


def test_cli_refuses_u1_and_exits_3(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    question, code = REFUSED["U1"]
    proc = run_cli(question, "--runs-dir", str(runs))
    assert proc.returncode == 3, explain(proc)
    folders = run_folders(runs)
    assert len(folders) == 1, folders
    manifest = check_printed(proc, folders[0])
    assert (manifest["status"], manifest["reason_code"]) == ("UNSUPPORTED", code)
    assert not (folders[0] / "chart.png").exists()


def test_cli_error_exits_4(tmp_path):
    """Added by the tests session: an ERROR (a VERIFIED_OFFICIAL row in --data) exits 4."""
    runs = tmp_path / "runs"
    runs.mkdir()
    bad = NOT_SYNTHETIC_COPIES["first_row_VERIFIED_OFFICIAL"](tmp_path)
    proc = run_cli(SUPPORTED["S1"][0], "--data", str(bad), "--runs-dir", str(runs))
    assert proc.returncode == 4, explain(proc)
    folders = run_folders(runs)
    assert len(folders) == 1, folders
    manifest = check_printed(proc, folders[0])
    assert (manifest["status"], manifest["reason_code"]) == ("ERROR", "DATA_CLASS_MISMATCH")


def test_cli_two_runs_get_two_run_folders(tmp_path):
    """Added by the tests session: run ids stay unique across separate commands."""
    runs = tmp_path / "runs"
    runs.mkdir()
    for _ in range(2):
        proc = run_cli(SUPPORTED["S1"][0], "--runs-dir", str(runs))
        assert proc.returncode == 0, explain(proc)
    folders = run_folders(runs)
    assert len(folders) == 2, folders
    for folder in folders:
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["run_id"] == folder.name
