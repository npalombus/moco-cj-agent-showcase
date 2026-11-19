"""D0 (docs/D-DESIGN.md): with MOCO_STATE_DIR, MOCO_RUNS_DIR, MOCO_LOG_STDOUT and
MOCO_REFRESH_HOURS unset, every file is written where it is today. D8: "the memory file,
the log file and the records are where they are today".

These tests describe today, so they pass before Part D is built and must still pass after.
Each command runs against a copy of the program (dsupport.Sandbox), so "the project's var"
and "the project's runs" below are the copy's; the real project's two folders are listed
before and after in the first test.
"""
from dsupport import (A_ID, A_NAME, A_ROWS, SYNTHETIC_Q, SYNTHETIC_STEPS, Sandbox, copy_names,
                      db_text, files_under, log_lines, message, model_env, project_folders,
                      refused_db, run_folders, serve_env, service, start_line, start_lines,
                      turn_folders)

REFUSED_Q = "Show ibis arrests by neighborhood in 2025."


def test_agent_ask_keeps_memory_and_records_in_the_project_folders(tmp_path):
    """agent-ask with nothing set: the memory file is <project>/var/agent.db; the turn's
    record and the count's run folder (with its chart) are under <project>/runs. The real
    project's var/ and runs/ are listed before and after: nothing changed."""
    before = project_folders()
    box = Sandbox(tmp_path)
    result = box.run("agent-ask", SYNTHETIC_Q, env=model_env(), steps=SYNTHETIC_STEPS)
    assert result.code == 0, result.explain()
    assert "STATUS: ANSWERED" in result.lines, result.explain()
    assert SYNTHETIC_Q in db_text(box.var / "agent.db")
    assert len(turn_folders(box.runs)) == 1 and len(run_folders(box.runs)) == 1
    (chart,) = [line for line in result.lines if line.startswith("CHART: ")]
    assert chart[len("CHART: "):].startswith(str(run_folders(box.runs)[0])), chart
    assert project_folders() == before, "the real project's var/ or runs/ changed"


def test_requests_reads_the_memory_in_the_project_var(tmp_path):
    """requests with nothing set lists the turns of <project>/var/agent.db."""
    box = Sandbox(tmp_path)
    refused_db(tmp_path / "scratch", box.var / "agent.db", REFUSED_Q)
    result = box.run("requests")
    assert result.code == 0, result.explain()
    assert any(REFUSED_Q in line for line in result.lines), result.explain()


def test_serve_writes_its_log_and_memory_in_the_project_var(tmp_path):
    """serve with nothing set (the Slack stand-in, one message): the log is
    <project>/var/agent.log, the memory <project>/var/agent.db, the turn's record under
    <project>/runs; the start line names that log file, says data SYNTHETIC, and is today's
    line exactly."""
    box = Sandbox(tmp_path)
    result = box.run("serve", env=serve_env(), steps=SYNTHETIC_STEPS,
                     events=[message(SYNTHETIC_Q)])
    assert result.code == 0, result.explain()
    assert result.report["answered"] == [True], result.explain()
    assert result.posts or result.report["uploads"], "the message got no reply"
    assert any("label=answered" in line for line in log_lines(box.var / "agent.log"))
    assert SYNTHETIC_Q in db_text(box.var / "agent.db")
    assert len(turn_folders(box.runs)) == 1
    assert start_lines(result) == [start_line("SYNTHETIC", box.var / "agent.log")], \
        result.explain()


def test_serve_puts_no_log_line_on_standard_output(tmp_path):
    """D3's default (off) is today: with MOCO_LOG_STDOUT unset no line of agent.log reaches
    standard output; the start line is the only line there."""
    box = Sandbox(tmp_path)
    result = box.run("serve", env=serve_env(), steps=SYNTHETIC_STEPS,
                     events=[message(SYNTHETIC_Q)])
    assert result.code == 0, result.explain()
    logged = log_lines(box.var / "agent.log")
    assert logged, "premise: serve wrote its log"
    assert not set(logged) & set(result.lines), "a log line is on standard output"
    assert result.lines == start_lines(result), result.explain()


def test_fetch_puts_the_copy_in_the_project_var(tmp_path):
    """fetch with nothing set: the copy is under <project>/var/copies (S3A C4, today); no
    other file is written in var/ and nothing in runs/."""
    box = Sandbox(tmp_path)
    result = box.run("fetch", A_ID, services=[service(A_NAME)])
    assert result.code == 0, result.explain()
    assert len(copy_names(box.var, A_NAME)) == 1
    assert f"ROWS: {A_ROWS}" in result.lines, result.explain()
    assert all(path.startswith("copies") for path in files_under(box.var))
    assert files_under(box.runs) == []
