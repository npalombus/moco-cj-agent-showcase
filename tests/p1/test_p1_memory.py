"""Brief point 8, third part: memory (docs/P1A-DESIGN.md A12, and docs/P1-DESIGN.md section
10 where A12 does not change it). Revision 2 (docs/P1A-R2-DESIGN.md R5): a database file that
holds the table `turns` of stage 2's first build has that table dropped, with everything in
it, when it is opened; opening it still must not fail.

A12 does not give add_turn's new signature or the names of a stored turn's fields. So turns
are made through agent.handle_question with a FakeModel (p1support.Env), and memory is
checked through behaviour: thread_has_turns, reset_thread's and purge_older_than's counts,
the length of refused_turns' list, what the next turn fills, the THREAD SO FAR block the
model is given, and the database cells read with sqlite3. The store is a file in tmp_path.

Carried over from P1 unchanged (and passing today): seen_event, the per-person and per-day
counters, and the store making its file. Carried over in new form: every turn where the
model was called is remembered (A4 step 6, "Remember the turn", after the loop).

Accepted both ways (kit-log/raw/P1A-A-notes.txt):
- R5 says the old table is dropped, not under what name the new turns live: the check is
  that no table with the old table's columns is left and that no cell holds the old turn's
  question or user id (a name of its own, used by no new turn). Whether the dropped rows'
  bytes are gone from the file at once (a VACUUM) is not checked: R5 does not say.
- refused_turns(days) may return only the four request codes, or every UNSUPPORTED turn and
  leave the filter to the requests command (A15 puts the filter on the command).
- A turn that ends before the model is called (empty, too long, a guard refusal, a Python
  `details`, the daily cap) may or may not be remembered: A4 step 6 comes after the loop and
  A11 gives such a turn no wording.

Cannot check here: the default file var/agent.db (no test may touch var/); the inside of a
stored turn or of refused_turns' items (A12 names no fields; the requests command test in
test_p1_commands.py reads what is printed).
"""
import json
import re
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from p1support import (AGENT_USER, CHANNEL, DM_KEY, FAKE_MODEL_ID, FAKE_SECRETS, NOW,
                       ONE_COUNT_TEXT, TEAM, THREAD_1, THREAD_2, USER, USER2, Env, FakeModel,
                       FakeSlack, Step, all_totals, ask_user, compare_expect, count, db_bytes,
                       db_cells, decline, finish, has_number, later, mention, messages_text,
                       mod, months, open_store, process, real_agent, secret_parts,
                       thread_block)
from support import NOT_SYNTHETIC_COPIES, REFUSED, SUPPORTED

FOLLOW_UP = "And for people under 18?"
Q_FIELD = REFUSED["U3"][0]  # "Show arrests by race in 2025"


def refuse_field(env, **kw):
    """A turn the model declines with UNSUPPORTED_FIELD (it ran a tool, counted nothing)."""
    reply = env.ask(Q_FIELD, Step(decline("UNSUPPORTED_FIELD")), **kw)
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", "UNSUPPORTED_FIELD"), reply.text
    return reply


def count_filters(env, reply):
    """The filters of the one count a turn ran, from its saved record."""
    assert len(reply.run_ids) == 1, reply.run_ids
    manifest = env.runs_dir / reply.run_ids[0] / "manifest.json"
    return json.loads(manifest.read_text(encoding="utf-8"))["filters"]


def follow_up(env, **kw):
    """"And for people under 18?": the model counts with the year not stated (A5)."""
    return env.ask(FOLLOW_UP, Step(count(None, "under_18")),
                   Step(finish("finding", ONE_COUNT_TEXT)), **kw)


# ---- thread_has_turns, reset_thread, purge_older_than (A12, P1 section 10) -------------

def test_thread_has_turns_follows_the_exact_key(tmp_path):
    """A12: thread_has_turns(thread_key) -> bool, for that exact key only."""
    env = Env(tmp_path)
    assert env.store.thread_has_turns(THREAD_1) is False
    refuse_field(env)
    assert env.store.thread_has_turns(THREAD_1) is True
    for other in (THREAD_2, DM_KEY, THREAD_1[:-1], THREAD_1 + "1"):  # a prefix either way
        assert env.store.thread_has_turns(other) is False, other
    assert env.store.reset_thread(THREAD_1) == 1
    assert env.store.thread_has_turns(THREAD_1) is False


def test_reset_thread_deletes_one_threads_turns_and_says_how_many(tmp_path):
    """P1 section 10: reset_thread(thread_key) -> turns deleted; other threads stay."""
    env = Env(tmp_path)
    env.answered(SUPPORTED["S1"][0], (2025, "18_25"))
    refuse_field(env)
    refuse_field(env)
    env.answered(SUPPORTED["S2"][0], (2024, None), thread_key=THREAD_2)
    assert env.store.reset_thread(THREAD_1) == 3
    assert env.store.thread_has_turns(THREAD_1) is False
    assert env.store.thread_has_turns(THREAD_2) is True
    assert env.store.reset_thread(THREAD_1) == 0
    after = env.ask(FOLLOW_UP, Step(count(None, "under_18")))  # nothing left to fill from
    assert after.status == "NEEDS_INPUT", (after.status, after.reason_code, after.text)


def test_purge_older_than_deletes_only_old_turns(tmp_path):
    """P1 section 10: purge_older_than(days, now) -> turns deleted, by the time each turn
    was made (the `now` of its handle_question)."""
    env = Env(tmp_path)
    for thread_key in (THREAD_1, THREAD_2):
        for days in (40, 31, 29, 1):
            refuse_field(env, thread_key=thread_key, now=NOW - timedelta(days=days))
    assert env.store.purge_older_than(30, NOW) == 4
    assert env.store.purge_older_than(10, NOW) == 2  # follows `days`
    assert env.store.thread_has_turns(THREAD_1) is True
    assert env.store.purge_older_than(30, NOW + timedelta(days=40)) == 2  # follows `now`
    assert env.store.thread_has_turns(THREAD_1) is False
    assert env.store.thread_has_turns(THREAD_2) is False


# ---- refused_turns (A12, for the requests command of A15) -----------------------------

def test_refused_turns_counts_the_request_codes_within_the_days(tmp_path):
    """A12 and A15: turns refused with UNSUPPORTED_FIELD, UNSUPPORTED_METRIC,
    REAL_DATA_NOT_AVAILABLE or OUT_OF_COVERAGE, from the last `days` days. refused_turns
    has no `now`, so the turns are made at times near the real present.

    Accepted both ways: A15 puts the four-code filter on the requests command and A12 does
    not say what refused_turns returns, so it may also return the UNRECOGNIZED_QUESTION turn
    (5 in 30 days instead of 4). Either way the 40-day-old turn is in 60 days and not in 30.
    MOCO_RETENTION_DAYS is 90 so no reading of P1's retention can delete that old turn first
    (as in test_p1_commands.py)."""
    env = Env(tmp_path, MOCO_RETENTION_DAYS=90)
    real_now = datetime.now(timezone.utc)
    turns = [  # question, steps, expected status and code, days old
        (Q_FIELD, [Step(decline("UNSUPPORTED_FIELD"))], "UNSUPPORTED_FIELD", 0),
        (REFUSED["U1"][0], [Step(decline("UNSUPPORTED_METRIC"))], "UNSUPPORTED_METRIC", 0),
        (REFUSED["U5"][0], [Step(decline("REAL_DATA_NOT_AVAILABLE"))],
         "REAL_DATA_NOT_AVAILABLE", 0),
        (REFUSED["U4"][0], [Step(count(2019, "all")), Step(finish("finding", ONE_COUNT_TEXT))],
         "OUT_OF_COVERAGE", 0),
        (REFUSED["U8"][0], [Step(decline("UNRECOGNIZED_QUESTION"))], "UNRECOGNIZED_QUESTION",
         0),  # not a request code
        (Q_FIELD, [Step(decline("UNSUPPORTED_FIELD"))], "UNSUPPORTED_FIELD", 40),
    ]
    for i, (question, steps, code, days) in enumerate(turns):
        reply = env.ask(question, *steps, thread_key=f"{TEAM}:{CHANNEL}:17627900{i:02d}.000100",
                        now=real_now - timedelta(days=days, minutes=10 + i))
        assert (reply.status, reply.reason_code) == ("UNSUPPORTED", code), reply.text
    env.answered(SUPPORTED["S1"][0], (2025, "18_25"), now=real_now - timedelta(minutes=5))
    n30 = len(env.store.refused_turns(30))
    assert n30 in (4, 5), n30  # 5 when the UNRECOGNIZED_QUESTION turn is returned too
    assert len(env.store.refused_turns(60)) == n30 + 1  # the 40-day-old turn


# ---- surviving a restart, and one thread never seeing another (A12, P1 section 10) -----

def test_a_close_and_reopen_keeps_the_turns(tmp_path):
    """P1 section 10: closing the store and opening the same file again keeps the turns. A
    follow-up after reopening still fills its year from the earlier answer (A5)."""
    env = Env(tmp_path)
    env.answered(SUPPORTED["S1"][0], (2025, "18_25"))
    env.store.close()
    env.store = open_store(tmp_path)
    assert env.store.thread_has_turns(THREAD_1) is True
    reply = follow_up(env)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert reply.carried == {"year": True, "age_group": False}
    assert count_filters(env, reply) == {"year": 2025, "age_group": "under_18"}
    block = thread_block(env.model.calls[0]["messages"])
    assert block is not None and SUPPORTED["S1"][0] in block


def test_one_thread_never_sees_another(tmp_path):
    """P1 section 10, the isolation rule: the same follow-up in another thread gets no
    THREAD SO FAR block and fills nothing; in the same thread it fills the year."""
    env = Env(tmp_path)
    env.answered(SUPPORTED["S1"][0], (2025, "18_25"))
    elsewhere = env.ask(FOLLOW_UP, Step(count(None, "under_18")), thread_key=THREAD_2)
    messages = env.model.calls[0]["messages"]
    assert thread_block(messages) is None
    assert SUPPORTED["S1"][0] not in messages_text(messages)
    assert elsewhere.status == "NEEDS_INPUT", (elsewhere.status, elsewhere.text)
    assert elsewhere.carried == {"year": False, "age_group": False}
    same = follow_up(env)
    assert same.status == "ANSWERED" and same.carried["year"] is True, same.text


# ---- what the database file holds (A12) ------------------------------------------------

def test_a_stored_turn_holds_no_value_from_the_data(tmp_path):
    """A12: results are stored with no values; never a number from an answer. No total of
    the data is in any cell, as text or as a number; no busiest or quietest count of the
    series counted, and not the compare's difference, in any text cell. Those other values
    are kept only from 44 up and are looked for outside dates and clock times (a stored time
    or turn id can hold 44 as a minute), so no Slack id, thread key or time can hold one by
    chance."""
    env = Env(tmp_path)
    env.answered(SUPPORTED["S2"][0], (2024, None))
    env.answered("Compare 2024 and 2025 for people under 18.", (2024, "under_18"),
                 (2025, "under_18"), compared=True)
    env.store.close()
    cells = db_cells(tmp_path)
    assert cells, "nothing was stored"
    totals = all_totals()
    series = [months(2024, None), months(2024, "under_18"), months(2025, "under_18")]
    expect = compare_expect([(2024, "under_18", sum(series[1])),
                             (2025, "under_18", sum(series[2]))])
    extra = {f(values) for values in series for f in (max, min)} | {expect["difference"]}
    extra = {n for n in extra if n >= 44}
    for cell in cells:
        if isinstance(cell, str):
            timeless = re.sub(r"\d+(?:[-:T]\d+)+", " ", cell)  # dates, times, ids from them
            found = ([n for n in totals if has_number(n, cell)]
                     + [n for n in extra if has_number(n, timeless)])
            assert not found, f"a value of the data {found} is stored: {cell[:200]!r}"
        elif isinstance(cell, (int, float)) and not isinstance(cell, bool):
            assert cell not in totals, f"a total of the data ({cell}) is stored as a number"


def test_a_slack_turn_stores_no_secret_or_part_of_one(tmp_path):
    """A12: never stored: a token or a key. A full Slack event through the real agent, with
    made-up secrets in the settings."""
    env = Env(tmp_path, slack=True)
    env.model = FakeModel(Step(count(2024, "all")), Step(finish("finding", ONE_COUNT_TEXT)),
                          clock=env.clock)
    slack = FakeSlack()
    label = process(mention(f"<@{AGENT_USER}> {SUPPORTED['S2'][0]}"), settings=env.settings,
                    store=env.store, agent=real_agent(env), slack=slack)
    assert label == "answered", (label, slack.log)
    env.store.close()
    raw = db_bytes(tmp_path)
    for value in FAKE_SECRETS.values():
        assert value not in raw, "a secret value is in the database"
    for part in secret_parts(window=6):  # 6 characters: raw bytes hold short runs by chance
        assert part not in raw, "part of a secret value is in the database"


def test_the_store_makes_its_file(tmp_path):
    """P1 section 10: Store(path) makes the SQLite file with its tables if absent."""
    store = open_store(tmp_path, "new.db")
    store.close()
    path = tmp_path / "new.db"
    assert path.is_file()
    connection = sqlite3.connect(path)
    try:
        assert connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")\
            .fetchall()
    finally:
        connection.close()


# The tables of stage 2's first build, copied from git show e495c46:src/moco_agent/memory.py.
P1_SCHEMA = """
CREATE TABLE IF NOT EXISTS turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_key TEXT NOT NULL, user_id TEXT, question TEXT, status TEXT, reason_code TEXT,
    skill TEXT, arguments TEXT, run_id TEXT, model_id TEXT, guard_code TEXT,
    clarification TEXT, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS turns_by_thread ON turns (thread_key, id);
CREATE TABLE IF NOT EXISTS seen_events (event_id TEXT PRIMARY KEY, seen_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS user_requests (user_id TEXT NOT NULL, at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS user_requests_by_user ON user_requests (user_id, at);
CREATE TABLE IF NOT EXISTS model_calls (utc_date TEXT PRIMARY KEY, calls INTEGER NOT NULL);
"""
OLD_USER = "UOLDTURN01"                                   # a user id no new turn uses
OLD_QUESTION = "How many arrests were there in the old kestrel table?"
P1_COLUMNS = {"id", "thread_key", "user_id", "question", "status", "reason_code", "skill",
              "arguments", "run_id", "model_id", "guard_code", "clarification", "created_at"}
P1_TURN = {"thread_key": THREAD_1, "user_id": OLD_USER,
           "question": OLD_QUESTION, "status": "ANSWERED", "reason_code": None,
           "skill": "arrest_count_trend", "arguments": '{"year": 2024, "age_group": "41_plus"}',
           "run_id": "20261110T140000Z-0a1b2c3d", "model_id": FAKE_MODEL_ID,
           "guard_code": None, "clarification": None,
           "created_at": "2026-11-10T14:00:00.000000Z"}


def add_old_turns_table(path):
    """Stage 2's first build's tables (P1_SCHEMA) and one old turn, in the file at path."""
    connection = sqlite3.connect(path)
    try:
        connection.executescript(P1_SCHEMA)
        connection.execute(f"INSERT INTO turns ({', '.join(P1_TURN)}) "
                           f"VALUES ({', '.join('?' * len(P1_TURN))})", list(P1_TURN.values()))
        connection.commit()
    finally:
        connection.close()


def table_columns(path):
    """{table name: set of its column names}, read with sqlite3 itself."""
    connection = sqlite3.connect(path)
    try:
        names = [row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")]
        return {name: {row[1] for row in connection.execute(f'PRAGMA table_info("{name}")')}
                for name in names}
    finally:
        connection.close()


def check_old_table_dropped(folder):
    """R5: no table of the old shape is left, and no cell holds the old turn's question or
    user id."""
    columns = table_columns(Path(folder) / "agent.db")
    assert P1_COLUMNS not in columns.values(), f"the old turns table is still there: {columns}"
    for cell in db_cells(folder):
        if isinstance(cell, str):
            assert OLD_QUESTION not in cell and OLD_USER not in cell, \
                f"an old turn is still stored: {cell[:120]!r}"


def test_a_database_with_stage_2s_first_tables_opens_and_drops_the_old_table(tmp_path):
    """R5 (and A12): opening a database file with the table `turns` of stage 2's first build
    must not fail, and drops that table with everything in it: its turn is not remembered.
    A new turn is then remembered and the next turn fills from it."""
    add_old_turns_table(tmp_path / "agent.db")
    assert P1_COLUMNS in table_columns(tmp_path / "agent.db").values()
    env = Env(tmp_path)  # opens memory.Store on that file
    assert env.store.thread_has_turns(THREAD_1) is False  # the old turn went with its table
    env.store.close()
    check_old_table_dropped(tmp_path)
    env.store = open_store(tmp_path)
    env.answered(SUPPORTED["S1"][0], (2025, "18_25"))
    assert env.store.thread_has_turns(THREAD_1) is True
    reply = follow_up(env)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert reply.carried == {"year": True, "age_group": False}
    assert count_filters(env, reply) == {"year": 2025, "age_group": "under_18"}


def test_an_old_turns_table_beside_this_rounds_turns_is_dropped_and_they_stay(tmp_path):
    """R5: a file this round's store already wrote, to which the old `turns` table is added
    (as a file that went through the first build and then this one would hold): reopening
    drops the old table only. This round's turn is still remembered and still fills the
    next turn. Premise (R5 does not name this round's table): this round's store keeps its
    turns in a table not named `turns`, so the old one can be added beside it."""
    env = Env(tmp_path)
    env.answered(SUPPORTED["S1"][0], (2025, "18_25"))
    env.store.close()
    assert "turns" not in table_columns(tmp_path / "agent.db"), \
        "premise: this round's turns are not in a table named turns"
    add_old_turns_table(tmp_path / "agent.db")
    env.store = open_store(tmp_path)
    assert env.store.thread_has_turns(THREAD_1) is True
    env.store.close()
    check_old_table_dropped(tmp_path)
    env.store = open_store(tmp_path)
    reply = follow_up(env)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert reply.carried == {"year": True, "age_group": False}
    assert count_filters(env, reply) == {"year": 2025, "age_group": "under_18"}


# ---- every turn that called the model is remembered (A4 step 6) -------------------------

OUTCOMES = {
    # name: (question, steps, settings, status, reason code)
    "answered": (SUPPORTED["S1"][0], [Step(count(2025, "18_25")),
                                      Step(finish("finding", ONE_COUNT_TEXT))], {},
                 "ANSWERED", None),
    "empty": ("", [], {}, "UNSUPPORTED", "UNRECOGNIZED_QUESTION"),
    "too_long": ("How many arrests " + "x" * 600, [], {}, "UNSUPPORTED", "INPUT_TOO_LONG"),
    "guard_refused": (REFUSED["U6"][0], [], {}, "UNSUPPORTED", "UNRECOGNIZED_QUESTION"),
    "details_with_no_answer": ("details", [], {}, "UNSUPPORTED", "NO_PREVIOUS_ANSWER"),
    "declined": (Q_FIELD, [Step(decline("UNSUPPORTED_FIELD"))], {}, "UNSUPPORTED",
                 "UNSUPPORTED_FIELD"),
    "needs_input": ("How many arrests?", [Step(ask_user("year"))], {}, "NEEDS_INPUT",
                    "NEEDS_CLARIFICATION"),
    "model_unavailable": ("How many arrests?", "unavailable", {}, "ERROR",
                          "MODEL_UNAVAILABLE"),
    "rate_limited": ("How many arrests?", [Step(ask_user("year"))],
                     {"MOCO_DAILY_MODEL_CALLS": "1"}, "ERROR", "RATE_LIMITED"),
    "data_class_mismatch": (SUPPORTED["S1"][0], [Step(count(2025, "18_25"))], {}, "ERROR",
                            "DATA_CLASS_MISMATCH"),
}


# The turns that end before the model is called (A4 steps 1 to 4).
BEFORE_THE_MODEL = ("empty", "too_long", "guard_refused", "details_with_no_answer",
                    "rate_limited")


@pytest.mark.parametrize("name", OUTCOMES)
def test_every_outcome_is_remembered(name, tmp_path):
    """A4 step 6: a turn where the model was called is remembered in its own thread, whatever
    its outcome. Accepted both ways: a turn that ends before the model is called (empty, too
    long, a guard refusal, a Python `details`, the daily cap) may or may not be remembered,
    because A4 step 6 comes after the loop and A11 gives such a turn no wording; for those
    only the reply and "no turn in another thread" are checked."""
    question, steps, settings_values, status, code = OUTCOMES[name]
    env = Env(tmp_path, **settings_values)
    if name == "rate_limited":  # use up the cap of 1 in a third thread first
        refuse_field(env, thread_key=DM_KEY)
    kw = {}
    if steps == "unavailable":
        steps, kw["error"] = [], mod("llm").ModelUnavailable("down")
    if name == "data_class_mismatch":
        kw["data_path"] = NOT_SYNTHETIC_COPIES["first_row_VERIFIED_OFFICIAL"](tmp_path)
    reply = env.ask(question, *steps, **kw)
    assert reply.status == status, (reply.status, reply.reason_code, reply.text)
    if status != "ANSWERED":
        assert reply.reason_code == code, reply.reason_code
    if name not in BEFORE_THE_MODEL:
        assert env.store.thread_has_turns(THREAD_1) is True
    assert env.store.thread_has_turns(THREAD_2) is False


# ---- unchanged from P1 (section 10) ------------------------------------------------------

def test_seen_event_is_false_then_true(tmp_path):
    store = open_store(tmp_path)
    assert store.seen_event("EvTEST000001") is False
    assert store.seen_event("EvTEST000001") is True
    assert store.seen_event("EvTEST000002") is False


def test_per_person_request_counter(tmp_path):
    store = open_store(tmp_path)
    for seconds in (0, 10, 50):
        store.record_user_request(USER, later(seconds))
    store.record_user_request(USER2, later(20))
    assert store.user_requests_since(USER, later(5)) == 2
    assert store.user_requests_since(USER, later(-5)) == 3
    assert store.user_requests_since(USER2, later(-5)) == 1
    assert store.user_requests_since("UTEST7777", later(-5)) == 0


def test_per_day_model_call_counter(tmp_path):
    store = open_store(tmp_path)
    day = date(2026, 11, 10)
    for _ in range(3):
        store.record_model_call(day)
    store.record_model_call(day + timedelta(days=1))
    assert store.model_calls_on(day) == 3
    assert store.model_calls_on(day + timedelta(days=1)) == 1
    assert store.model_calls_on(day - timedelta(days=1)) == 0
