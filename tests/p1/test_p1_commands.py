"""Brief P1A-A point 12: the commands (docs/P1A-DESIGN.md A15; P1 section 12 where A15 says
"as now"), run through subprocess with the .venv Python, MOCO_ENV_FILE pointing at an empty
file in tmp_path, HOME in tmp_path, and every proxy variable pointed at a closed local port
(so a mistake cannot reach the network).

Covered: agent-ask, serve and whoami exit 4 and name the missing KEY; agent-ask on the two
paths that never call the model (a guard refusal: exit 3; `details` after an answer made
in-process: exit 0), with its MODEL:, STATUS: and STYLE: lines, a made-up key and
NVIDIA_BASE_URL at the closed port; tools/loop_check.py is there and tools/model_check.py
is gone; ask works exactly as in stage 1; `requests [--days N] [--db PATH]` (answer A1 in
briefs/QUESTIONS.md) lists the turns refused with UNSUPPORTED_FIELD, UNSUPPORTED_METRIC,
REAL_DATA_NOT_AVAILABLE or OUT_OF_COVERAGE from a database in tmp_path, newest first, each
with its own code, then a count per code, with no user id, and --days sets the window (30
days by default).

The `requests` database is made in-process: turns run through agent.handle_question with
the fake model (p1support.Env, store file tmp_path/agent.db), each at a `now` a set time
before the real clock, because the command counts days from the real clock. The store is
closed before the command runs.

Accepted both ways (A15 gives no layout for `requests`):
- each code's count may come after the code or before it (in the same order for every
  code), with up to 40 characters that are not digits between them, on the same line;
- each turn's code may stand before its question, after it on the same line, or on the
  line just above;
- the time of each line is not checked (its format is not given); the exit code is checked
  as 0 (kit-log/raw/P1A-A-notes.txt).

Not checkable here: agent-ask's answers from the model and its exit code 5 (they need the
real model), what loop_check prints (the real model), what whoami prints when the tokens
are there (it needs Slack), and the default `--db` of `requests` (var/agent.db, which no
test may touch).

These commands run from the repo folder, and every stage 2 test fails if the repo's var/
folder changes. So a command that finds a KEY missing must stop before it makes anything
under var/ (P1 section 11: serve calls require_for_serve before it opens the store), and
`requests --db PATH` must not touch var/ at all.
"""
import json
import os
import re
from datetime import datetime, timedelta, timezone

import pytest

from p1support import (DEAD_PROXY, DETAILS_HEAD, FAKE_SECRETS, ONE_COUNT_TEXT, USER, Env, Step,
                       assert_no_secret, count, decline, explain, finish, fixed_parts, fixed_re,
                       run_command)
from support import REFUSED, REPO, ROUTER_RULES, SUPPORTED, expected_values

SERVE_KEYS = ["NVIDIA_API_KEY", "SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "SLACK_ALLOWED_TEAM_ID",
              "SLACK_ALLOWED_USER_IDS"]
SLACK_TOKENS = {k: v for k, v in FAKE_SECRETS.items() if k.startswith("SLACK_")}


def output(proc):
    return proc.stdout + proc.stderr


def test_agent_ask_without_the_key_exits_4_and_names_it(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    proc = run_command(tmp_path, "agent-ask", SUPPORTED["S2"][0], "--db",
                       str(tmp_path / "agent.db"), "--runs-dir", str(runs),
                       extra_env=SLACK_TOKENS)
    assert proc.returncode == 4, explain(proc)
    assert "NVIDIA_API_KEY" in output(proc), explain(proc)
    assert_no_secret(output(proc))
    assert list(runs.iterdir()) == [], "nothing may run without the key"


# P1 section 12: agent-ask's thread when --thread is not given.
TERMINAL_THREAD = "local:terminal:default"
# A made-up key, and the endpoint (like every proxy, set by run_command) at a closed local
# port: the turns below never call the model (A2, A4 step 2), so nothing may reach out.
AGENT_ASK_ENV = {"NVIDIA_API_KEY": FAKE_SECRETS["NVIDIA_API_KEY"], "NVIDIA_BASE_URL": DEAD_PROXY}


def repo_var_and_runs():
    """What the repo's var/ and runs/ hold (conftest.py checks the same after every test)."""
    var, runs = REPO / "var", REPO / "runs"
    return ([(str(p), p.stat().st_size, p.stat().st_mtime_ns) for p in sorted(var.rglob("*"))]
            if var.exists() else None,
            sorted(n for n in os.listdir(runs) if n != ".matplotlib") if runs.exists() else [])


def run_agent_ask(tmp_path, *args):
    """agent-ask with its database and runs folder in tmp_path. Checks that no secret is
    shown, that the repo's var/ and runs/ are left alone, and that the MODEL: and STYLE:
    lines are printed (A15). Returns the process and its stdout lines, stripped."""
    before = repo_var_and_runs()
    proc = run_command(tmp_path, "agent-ask", *args, "--db", str(tmp_path / "agent.db"),
                       "--runs-dir", str(tmp_path / "runs"), extra_env=AGENT_ASK_ENV)
    assert_no_secret(output(proc))
    assert repo_var_and_runs() == before, "agent-ask wrote under the repo's var/ or runs/"
    lines = [line.strip() for line in proc.stdout.splitlines()]
    for head in ("MODEL:", "STYLE:"):
        assert any(line.startswith(head) for line in lines), (head, explain(proc))
    return proc, lines


def test_agent_ask_on_a_guard_refusal_exits_3_with_the_fixed_refusal(tmp_path):
    """A2: `refuse` ends the turn with the fixed refusal and no model call. A15: exit 3 for
    UNSUPPORTED, with the STATUS: line."""
    question, code = REFUSED["U6"]
    (tmp_path / "runs").mkdir()
    proc, lines = run_agent_ask(tmp_path, question)
    assert proc.returncode == 3, explain(proc)
    assert any(line.startswith("STATUS: UNSUPPORTED") for line in lines), explain(proc)
    assert re.search(fixed_re(fixed_parts(code)), proc.stdout), explain(proc)


def test_agent_ask_details_after_an_answer_exits_0(tmp_path):
    """A4 step 2: `details` is Python's, with no model call. A15: exit 0 for DETAILS. The
    earlier answer is made in-process (fake model) in the same database and runs folder,
    in agent-ask's default thread, a minute before the real clock; the store is closed
    before the command runs."""
    question, year, group = SUPPORTED["S1"]
    env = Env(tmp_path)
    env.answered(question, (year, group), thread_key=TERMINAL_THREAD,
                 now=datetime.now(timezone.utc) - timedelta(minutes=1))
    env.store.close()
    proc, lines = run_agent_ask(tmp_path, "details")
    assert proc.returncode == 0, explain(proc)
    assert any(line.startswith("STATUS: DETAILS") for line in lines), explain(proc)
    assert DETAILS_HEAD in proc.stdout, explain(proc)


def test_loop_check_replaces_model_check():
    """A15: tools/loop_check.py replaces tools/model_check.py, which is removed. (What it
    prints needs the real model.)"""
    tools = REPO / "tools"
    assert (tools / "loop_check.py").is_file(), "no tools/loop_check.py"
    assert not (tools / "model_check.py").exists(), "tools/model_check.py is still there"


def test_serve_without_secrets_exits_4_and_names_each_missing_key(tmp_path):
    proc = run_command(tmp_path, "serve")
    assert proc.returncode == 4, explain(proc)
    for key in SERVE_KEYS:
        assert key in output(proc), (key, explain(proc))


def test_serve_with_the_secrets_but_no_approved_ids_exits_4_and_shows_no_value(tmp_path):
    proc = run_command(tmp_path, "serve", extra_env=FAKE_SECRETS)
    assert proc.returncode == 4, explain(proc)
    for key in ("SLACK_ALLOWED_TEAM_ID", "SLACK_ALLOWED_USER_IDS"):
        assert key in output(proc), (key, explain(proc))
    assert_no_secret(output(proc))


def test_whoami_without_the_token_exits_4_and_names_it(tmp_path):
    proc = run_command(tmp_path, "whoami",
                       extra_env={"NVIDIA_API_KEY": FAKE_SECRETS["NVIDIA_API_KEY"],
                                  "SLACK_APP_TOKEN": FAKE_SECRETS["SLACK_APP_TOKEN"]})
    assert proc.returncode == 4, explain(proc)
    assert "SLACK_BOT_TOKEN" in output(proc), explain(proc)
    assert_no_secret(output(proc))


@pytest.mark.parametrize("with_secrets", [False, True], ids=["empty_env_file", "secrets_set"])
def test_ask_still_works_exactly_as_in_stage_1(with_secrets, tmp_path):
    """Stage 1's command, unchanged: the rules router, no model, no secret needed."""
    extra = FAKE_SECRETS if with_secrets else None
    for key, expected_exit in [("S1", 0), ("U1", 3)]:
        runs = tmp_path / f"runs-{key}"
        runs.mkdir()
        question = SUPPORTED[key][0] if key in SUPPORTED else REFUSED[key][0]
        proc = run_command(tmp_path, "ask", question, "--runs-dir", str(runs), extra_env=extra)
        assert proc.returncode == expected_exit, explain(proc)
        assert "DATA: SYNTHETIC" in [line.strip() for line in output(proc).splitlines()]
        assert_no_secret(output(proc))
        (run,) = [p for p in runs.iterdir() if p.is_dir()]
        manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["router"] == ROUTER_RULES
        assert run.name in output(proc)
        if key == "S1":
            _, year, age_group = SUPPORTED["S1"]
            assert manifest["status"] == "ANSWERED"
            assert manifest["computed_values"] == expected_values(year, age_group)
        else:
            assert (manifest["status"], manifest["reason_code"]) == ("UNSUPPORTED", REFUSED["U1"][1])


# ---- requests (A15, answer A1) ---------------------------------------------------------
# Made-up questions, each with one word no other question, code or line holds, so its
# place in the output can be found. Each matches the stage 1 rule of its own code (or none),
# so the guard restricts the turn to that code or not at all, and the fake model declines
# with the same code.
FIELD_OLD = "Show pelican arrests by neighborhood in 2025."            # 5 days ago
METRIC = "What was the walrus conviction rate in 2025?"              # 4 days ago
REAL = "What are the real otter arrest numbers for 2025?"            # 3 days ago
COVERAGE = "How many heron arrests each month in 2019?"              # 2 days ago
FIELD_NEW = "How many badger theft arrests were there in 2025?"      # 2 hours ago
ANSWERED_Q = "How many lynx arrests were there in 2025?"             # 1 hour ago, not listed
UNRECOGNIZED_Q = "What is the marmot weather like?"                  # 30 minutes ago, not listed
METRIC_40_DAYS = "How many falcon arrests led to a sentence in 2024?"  # 40 days ago

LISTED_NEWEST_FIRST = [(FIELD_NEW, "UNSUPPORTED_FIELD"), (COVERAGE, "OUT_OF_COVERAGE"),
                       (REAL, "REAL_DATA_NOT_AVAILABLE"), (METRIC, "UNSUPPORTED_METRIC"),
                       (FIELD_OLD, "UNSUPPORTED_FIELD")]


def refused_database(tmp_path):
    """The database file tmp_path/agent.db, made by running each turn above through
    handle_question with the fake model, oldest first, at `now` = the real clock minus its
    age. Returns its path, closed."""
    real_now = datetime.now(timezone.utc)
    # A retention longer than every age here, so no reading of P1's MOCO_RETENTION_DAYS can
    # delete the 40-day-old turn before the command runs.
    env = Env(tmp_path, MOCO_RETENTION_DAYS=90)

    def declined(question, code, age):
        reply = env.ask(question, Step(decline(code)), now=real_now - age)
        assert (reply.status, reply.reason_code) == ("UNSUPPORTED", code), reply.text

    declined(METRIC_40_DAYS, "UNSUPPORTED_METRIC", timedelta(days=40))
    declined(FIELD_OLD, "UNSUPPORTED_FIELD", timedelta(days=5))
    declined(METRIC, "UNSUPPORTED_METRIC", timedelta(days=4))
    declined(REAL, "REAL_DATA_NOT_AVAILABLE", timedelta(days=3))
    # A7: a finish in a turn whose only count error was OUT_OF_COVERAGE uses that row.
    reply = env.ask(COVERAGE, Step(count(2019, "all")), Step(finish("finding", ONE_COUNT_TEXT)),
                    now=real_now - timedelta(days=2))
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", "OUT_OF_COVERAGE"), reply.text
    declined(FIELD_NEW, "UNSUPPORTED_FIELD", timedelta(hours=2))
    env.answered(ANSWERED_Q, (2025, None), now=real_now - timedelta(hours=1))
    declined(UNRECOGNIZED_Q, "UNRECOGNIZED_QUESTION", timedelta(minutes=30))
    env.store.close()
    return tmp_path / "agent.db"


def run_requests(tmp_path, db, *args):
    """requests with the made-up secrets in its environment, so a printed value would show.
    The same long retention as refused_database."""
    proc = run_command(tmp_path, "requests", "--db", str(db), *args,
                       extra_env=dict(FAKE_SECRETS, MOCO_RETENTION_DAYS="90"))
    assert proc.returncode == 0, explain(proc)
    out = output(proc)
    assert USER not in out, "a user id is shown"
    assert_no_secret(out)
    return out


def check_listed_newest_first(out, listed):
    """`listed` is [(question, its code)], newest first. Each question appears once, their
    places follow their time, and each one's code stands between the end of the line before
    it and the end of its own line (before the question, after it on its line, or on the
    line just above). Returns what comes after the line of the last one (the counts)."""
    for question, _ in listed:
        assert out.count(question) == 1, (question, out)
    places = [out.index(question) for question, _ in listed]
    assert places == sorted(places), f"not newest first:\n{out}"
    start = 0
    for question, code in listed:
        end = out.find("\n", out.index(question))
        end = len(out) if end == -1 else end
        assert code in out[start:end], (question, code, out)
        start = end
    return out[start:]


def counts_match(text, expected):
    """Each code of `expected` {code: n} with its count n on one line, with at most 40
    characters that are not digits between them. A15 gives no layout, so the count may
    come after the code or before it, but in the same order for every code (so one code's
    count is never read as the next one's)."""
    def after(code, n):
        return rf"{code}[^\d\n]{{0,40}}{n}(?!\d|[,.]\d)"

    def before(code, n):
        return rf"(?<![\d.]){n}[^\d\n]{{0,40}}{code}"

    return any(all(re.search(pattern(code, n), text) for code, n in expected.items())
               for pattern in (after, before))


def test_requests_lists_refused_turns_newest_first_with_a_count_per_code(tmp_path):
    """A15: the turns refused with the four request codes in the last 30 days, newest
    first, then a count per code; no answered or UNRECOGNIZED_QUESTION turn, no user id."""
    db = refused_database(tmp_path)
    out = run_requests(tmp_path, db)
    counts = check_listed_newest_first(out, LISTED_NEWEST_FIRST)
    assert counts_match(counts, {"UNSUPPORTED_FIELD": 2, "UNSUPPORTED_METRIC": 1,
                                 "REAL_DATA_NOT_AVAILABLE": 1, "OUT_OF_COVERAGE": 1}), out
    for question in (ANSWERED_Q, UNRECOGNIZED_Q):
        assert question not in out, (question, out)
    assert "lynx" not in out and "marmot" not in out, out
    # 30 days by default: the 40-day-old turn is left out.
    assert "falcon" not in out, out


def test_requests_days_sets_how_far_back_it_looks(tmp_path):
    """A15 `--days N`: --days 60 adds the 40-day-old turn (the oldest, so last) and its count;
    --days 1 leaves out every turn older than one day."""
    db = refused_database(tmp_path)

    out = run_requests(tmp_path, db, "--days", "60")
    counts = check_listed_newest_first(
        out, LISTED_NEWEST_FIRST + [(METRIC_40_DAYS, "UNSUPPORTED_METRIC")])
    assert counts_match(counts, {"UNSUPPORTED_FIELD": 2, "UNSUPPORTED_METRIC": 2,
                                 "REAL_DATA_NOT_AVAILABLE": 1, "OUT_OF_COVERAGE": 1}), out
    assert "lynx" not in out and "marmot" not in out, out

    out = run_requests(tmp_path, db, "--days", "1")
    counts = check_listed_newest_first(out, [(FIELD_NEW, "UNSUPPORTED_FIELD")])
    # Codes with no turn in the window may be shown with 0 or left out (A15 does not say).
    assert counts_match(counts, {"UNSUPPORTED_FIELD": 1}), out
    for word in ("pelican", "walrus", "otter", "heron", "falcon", "lynx", "marmot"):
        assert word not in out, (word, out)
