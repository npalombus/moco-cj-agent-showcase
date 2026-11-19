"""C61 Part E of docs/S3A-DESIGN.md (D-076 point 5): the clean-up. Points 12 to 14. Brief:
briefs/S3-R23-A-tests.md. Tests only; red until the planning chat builds C61, except those that pin
what stays.

serve runs as the Part D tests run it (tests/d/dsupport.Sandbox): a copy of the program in pytest's
temporary folder, one subprocess, the Slack stand-in (tests/d/standin.py), the fixture sources, no
network; its state folder, records folder and log are in tmp_path. Every file made here is
SYNTHETIC filler. The daily run is called in this process through refresh.start with a clock and a
wait of the test's own (Part D's seam for tests), so no real time passes.

Readings (also in kit-log/raw/S3-R23-A-notes.txt; the open ones are in briefs/QUESTIONS.md):
- R23-E1. "The records folder" is MOCO_RUNS_DIR (Part D D2, runs_dir_of). A folder of it is old
  when every file under it, at any depth, was last changed more than MOCO_RETENTION_DAYS days
  before serve starts (the files' change times). Only folders straight under the records folder
  are looked at; a file straight under it is not looked at here.
- R23-E2. "Logs how many": a line of agent.log that holds the word "record" or "folder" and the
  number removed as a whole number. "Logged and left": a line of agent.log names the folder (its
  name or its path), and the folder is still there; serve goes on (exit 0) and the other old
  folders are removed. The tests run in county mode (C61 is county mode only); D2's folder is the
  same in both.
- R23-E3. Point 13's 5,000,000 is bytes, "larger than" is strict (5,000,000 is not renamed). The
  renamed file holds the old log's bytes exactly; the new agent.log holds this run's lines only.
- R23-E4. OPEN (asked in briefs/QUESTIONS.md): the daily run "beside" the refresh is read as part of
  refresh.start's loop, on its clock: refresh.start(settings, transport, clock, wait) with
  MOCO_REFRESH_HOURS above 0 in county mode removes old turns of <state dir>/agent.db and old
  record folders again once a day of that clock (not at every look); a failure of the clean-up is
  logged as a warning of a moco_agent logger and the loop goes on.
"""
import logging
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parents[1]
if str(TESTS / "d") not in sys.path:
    sys.path.insert(0, str(TESTS / "d"))

from dsupport import Sandbox, log_lines, serve_env  # noqa: E402
from p1support import mod, open_store  # noqa: E402
from s3support import CountyEnv, service_for  # noqa: E402

DAY = 86400
FILLER = b"SYNTHETIC filler line of an old log, made up for tests.\n"


def aged(path, days, text="SYNTHETIC record, made up for tests\n"):
    """A file at `path` whose change time is `days` days ago."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    moment = time.time() - days * DAY
    os.utime(path, (moment, moment))
    return path


def serve(tmp_path, box=None, **values):
    """serve in county mode with its state folder and records folder in tmp_path; no event, so
    the Slack session ends at once (as Ctrl+C would)."""
    box = box or Sandbox(tmp_path)
    env = serve_env(MOCO_DATA="county", MOCO_STATE_DIR=tmp_path / "state",
                    MOCO_RUNS_DIR=tmp_path / "records", **values)
    result = box.run("serve", env=env)
    assert result.code == 0 and result.report["started"], result.explain()
    return result


def counted_line(lines, n):
    return [l for l in lines if re.search(r"record|folder", l, re.IGNORECASE)
            and re.search(rf"(?<![\d.,]){n}(?![\d.,])", l)]


# ==== point 12: old record folders at serve's start ============================================

def records_layout(tmp_path):
    records = tmp_path / "records"
    aged(records / "T-old-a" / "turn.json", 40)
    aged(records / "R-old-b" / "manifest.json", 31)
    aged(records / "R-old-b" / "sub" / "chart.png", 35)
    aged(records / "T-new-c" / "turn.json", 40)
    aged(records / "T-new-c" / "later.json", 1)
    aged(records / "T-recent-d" / "turn.json", 29)
    aged(tmp_path / "outside" / "T-old-e" / "turn.json", 40)
    return records


def test_e12_old_record_folders_go_and_new_ones_stay(tmp_path):
    """C61's test: with MOCO_RETENTION_DAYS at its 30, the two folders whose newest file is older
    are removed and the count logged; a folder with one new file, a folder of 29 days and a
    folder outside the records folder stay."""
    records = records_layout(tmp_path)
    serve(tmp_path)
    left = sorted(p.name for p in records.iterdir() if p.is_dir())
    assert left == ["T-new-c", "T-recent-d"], left
    assert (tmp_path / "outside" / "T-old-e" / "turn.json").is_file()
    assert counted_line(log_lines(tmp_path / "state" / "agent.log"), 2), \
        log_lines(tmp_path / "state" / "agent.log")


def test_e12_the_retention_days_are_the_setting(tmp_path):
    """Point 12 with MOCO_RETENTION_DAYS=7: the folder of 29 days goes too (three removed)."""
    records = records_layout(tmp_path)
    serve(tmp_path, MOCO_RETENTION_DAYS=7)
    assert sorted(p.name for p in records.iterdir() if p.is_dir()) == ["T-new-c"]
    assert counted_line(log_lines(tmp_path / "state" / "agent.log"), 3)


def test_e12_a_folder_that_cannot_be_removed_is_logged_and_left(tmp_path):
    """C61's test: an old folder holding a folder that cannot be written (so its file cannot be
    deleted) is logged and left; serve starts all the same and the other old folder goes."""
    records = tmp_path / "records"
    aged(records / "T-old-a" / "turn.json", 40)
    aged(records / "T-locked-z" / "sub" / "turn.json", 40)
    locked = records / "T-locked-z" / "sub"
    os.chmod(locked, 0o500)
    try:
        serve(tmp_path)
        assert (locked / "turn.json").is_file(), "the folder that cannot be removed is gone"
        assert not (records / "T-old-a").exists(), "the other old folder was not removed"
        lines = log_lines(tmp_path / "state" / "agent.log")
        assert any("T-locked-z" in line for line in lines), lines
    finally:
        os.chmod(locked, 0o700)


def test_e12_nothing_is_removed_when_nothing_is_old(tmp_path):
    """Point 12: folders of 29 days and of today stay. Passes today; must still pass."""
    records = tmp_path / "records"
    aged(records / "T-recent-d" / "turn.json", 29)
    aged(records / "T-today-f" / "turn.json", 0)
    serve(tmp_path)
    assert sorted(p.name for p in records.iterdir()) == ["T-recent-d", "T-today-f"]


# ==== point 13: the log file at 5,000,000 bytes =================================================

def old_log(path, size):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (FILLER * (size // len(FILLER) + 1))[:size]
    path.write_bytes(data)
    return data


@pytest.mark.parametrize("size", [4_999_999, 5_000_000])
def test_e13_a_log_of_5000000_bytes_or_less_is_kept(tmp_path, size):
    """C61's test (4,999,999) and R23-E3 (5,000,000, not larger): the log is not renamed and
    serve's lines follow the old ones."""
    log = tmp_path / "state" / "agent.log"
    data = old_log(log, size)
    serve(tmp_path)
    assert not (tmp_path / "state" / "agent.log.1").exists()
    now = log.read_bytes()
    assert now.startswith(data) and len(now) > size, len(now)


def test_e13_a_log_over_5000000_bytes_is_renamed_first(tmp_path):
    """C61's test (5,000,001): agent.log is renamed agent.log.1 before logging starts; the new
    agent.log holds this run's lines only."""
    log = tmp_path / "state" / "agent.log"
    data = old_log(log, 5_000_001)
    serve(tmp_path)
    assert (tmp_path / "state" / "agent.log.1").read_bytes() == data
    lines = log_lines(log)
    assert lines and any("serve starting" in line for line in lines), lines
    assert FILLER.decode().strip() not in log.read_text(encoding="utf-8")


def test_e13_an_older_log_1_is_replaced(tmp_path):
    """Point 13 "replacing an older one"."""
    state = tmp_path / "state"
    (state / "agent.log.1").parent.mkdir(parents=True, exist_ok=True)
    (state / "agent.log.1").write_bytes(b"SYNTHETIC older rotated log, made up for tests.\n")
    data = old_log(state / "agent.log", 5_000_001)
    serve(tmp_path)
    assert (state / "agent.log.1").read_bytes() == data


# ==== point 14: once a day beside the refresh (R23-E4) ==========================================

class Day:
    """A clock for refresh.start and its wait: each wait moves the clock on by the seconds asked;
    `at(hours, do)` runs `do` once when the clock has passed that hour; the loop stops after
    `stop` hours."""

    def __init__(self, stop=26):
        self.start = self.now = datetime.now(timezone.utc)
        self.stop, self.todo, self.waits = stop, [], 0

    def at(self, hours, do):
        self.todo.append((self.start + timedelta(hours=hours), do))

    def clock(self):
        return self.now

    def wait(self, seconds):
        self.waits += 1
        self.now += timedelta(seconds=seconds)
        for when, do in [t for t in self.todo if t[0] <= self.now]:
            self.todo.remove((when, do))
            do()
        return self.now >= self.start + timedelta(hours=self.stop)


def daily_env(tmp_path, monkeypatch, **values):
    env = CountyEnv(tmp_path, monkeypatch, copies=(), MOCO_REFRESH_HOURS="1",
                    MOCO_RUNS_DIR=str(tmp_path / "records"), **values)
    return env


def run_refresh(env, day):
    thread = mod("refresh").start(env.settings, transport=service_for("arrests_like"),
                                  clock=day.clock, wait=day.wait)
    assert thread is not None, "premise: the refresh is on"
    thread.join(60)
    assert not thread.is_alive(), "the refresh loop did not end"


def old_turn(store, question, days):
    store.add_turn(thread_key="SYNTHETIC-thread", user_id="UTEST0001", question=question,
                   status="UNSUPPORTED", reason_code="UNRECOGNIZED_QUESTION",
                   created_at=datetime.now(timezone.utc) - timedelta(days=days),
                   record={"turn_id": f"T-{question}", "results": []})


def test_e14_the_two_clean_ups_run_again_once_a_day(tmp_path, monkeypatch):
    """C61's test, "the daily run" (R23-E4): a turn and a record folder made old an hour after the
    refresh starts are still there at 23 hours and gone after a day; an old turn and folder
    from before the start are gone too; new ones stay."""
    env = daily_env(tmp_path, monkeypatch)
    records, state = tmp_path / "records", Path(env.settings.moco_state_dir)
    store = open_store(state)
    old_turn(store, "SYNTHETIC-old-before", 40)
    old_turn(store, "SYNTHETIC-new", 1)
    aged(records / "T-old-before" / "turn.json", 40)
    aged(records / "T-new" / "turn.json", 1)
    seen = {}
    day = Day()
    day.at(1, lambda: (old_turn(store, "SYNTHETIC-old-later", 40),
                       aged(records / "T-old-later" / "turn.json", 40)))
    day.at(23, lambda: seen.update(
        folder=(records / "T-old-later").exists(),
        turn="SYNTHETIC-old-later" in str(store.recent_turns("SYNTHETIC-thread", 10))))
    run_refresh(env, day)
    assert seen == {"folder": True, "turn": True}, f"cleaned before a day had passed: {seen}"
    questions = [t["question"] for t in store.recent_turns("SYNTHETIC-thread", 10)]
    assert questions == ["SYNTHETIC-new"], questions
    assert sorted(p.name for p in records.iterdir()) == ["T-new"]


def test_e14_a_failed_clean_up_is_logged_and_the_refresh_goes_on(tmp_path, monkeypatch, caplog):
    """Point 14 "a failure is logged and never stops serve": the records folder is a file, so its
    clean-up fails: a warning is logged and the loop goes on to its end (every wait asked)."""
    caplog.set_level(logging.INFO)
    (tmp_path / "records").write_text("SYNTHETIC: not a folder\n", encoding="utf-8")
    env = daily_env(tmp_path, monkeypatch)
    day = Day()
    run_refresh(env, day)
    assert day.waits >= 26 * 6, day.waits
    warned = [r for r in caplog.records if r.levelno >= logging.WARNING
              and r.name.startswith("moco_agent")]
    assert warned, [r.getMessage() for r in caplog.records]


def test_e14_no_refresh_no_daily_run(tmp_path, monkeypatch):
    """Point 14 "with the data refresh on": at MOCO_REFRESH_HOURS=0 refresh.start starts
    nothing. Passes today; must still pass."""
    env = CountyEnv(tmp_path, monkeypatch, copies=(), MOCO_REFRESH_HOURS="0")
    day = Day()
    assert mod("refresh").start(env.settings, clock=day.clock, wait=day.wait) is None
    assert day.waits == 0
