"""Never a row, and never a hidden figure: docs/S3A-DESIGN.md C1 ("No reply, tool answer, log
line, stored turn or `details` text ever holds a single record of a source, and no count
from 1 to 9 is ever shown as a figure"), C8.3 ("No tool returns records; `details` shows
totals and tables only") and C12's "no record and no hidden figure in any reply, tool
answer, log line, stored turn or `details`".

What this file covers
- A sweep over every kind of breakdown, on both fixtures, in a finished year and in the
  copy's unfinished one (some of them too fine): after the answer and its `details`, no
  row id and no row's exact time is in the reply, the details, any tool answer, any log
  line, the database (its cells and its raw bytes) or any file of the runs folder; no
  figure from 1 to 9 stands in the reply or the details; and a result's tool answer holds no
  figure at all.
- Ways to ask for a row: a filter or a breakdown on the key field is refused (BAD_FIELD);
  a period that holds one record alone (the copy's newest, alone on its day) gives `fewer
  than 10`, never 1, and its details show no more; the facts of describe_data hold no row.
- Log lines hold neither the question nor the reply (A0, still true).

Readings taken (kit-log/raw/S3A-A-notes.txt)
- "A single record" is looked for as a row's id (every fixture id starts FIXTURE-) or its
  exact time to the minute (s3support.assert_no_row), except the copy's newest record time,
  which copy.json holds by C4 and a reply or a log line may name as the copy's reach. The
  runs folder (stage 1's records and turn.json, not in C1's list) is checked for row ids
  only.
- Only log lines that reach the root logger can be seen (caplog), as in tests/p1.
- The database may hold numbers that are not values (steps, times), so it is checked for
  rows only here; test_s3_filling.py checks that it holds no value.
"""
import json
import logging
from pathlib import Path

import pytest

from p1support import Step, db_bytes, db_cells, describe, finish, show_details, tool_messages
from s3support import (A_ID, C_ID, Q_ABOUT, Q_BREAKDOWN, Q_COUNT, SCHOOL, CountyEnv,
                       assert_no_hidden_figure, assert_no_row, count, dates, figures,
                       fixture_rows, guard_free, is_, year)

SWEEP_A = ["district", "gender", "race", "ethnicity", SCHOOL, "age_band", "month", "weekday",
           "hour", None]
SWEEP_C = ["station", "race_code", "sex", "age_band", "month", None]
SWEEP = ([("arrests_like", y, by) for y in (2025, 2026) for by in SWEEP_A]
         + [("coded_like", y, by) for y in (2025, 2026) for by in SWEEP_C])


def every_row_free(texts, rows, where):
    for text in texts:
        assert_no_row(text, rows, where)


def but_the_newest(rows):
    """The rows whose exact time is looked for: all but the copy's newest record (its id is
    still looked for, as every FIXTURE- id is)."""
    key = "event_date_time" if "event_date_time" in rows[0] else "booked_at"
    newest = max(r[key] for r in rows)
    return [r for r in rows if r[key] != newest]


def log_text(caplog):
    return caplog.text + "\n".join(r.getMessage() for r in caplog.records)


def runs_texts(runs_dir):
    out = []
    for path in Path(runs_dir).rglob("*"):
        if path.is_file() and path.suffix in (".json", ".md", ".txt", ".jsonl", ".csv", ""):
            out.append(path.read_text(encoding="utf-8", errors="replace"))
    return out


@pytest.mark.parametrize("name, y, by", SWEEP,
                         ids=[f"{n}-{y}-{by or 'no breakdown'}" for n, y, by in SWEEP])
def test_no_row_and_no_hidden_figure_anywhere(tmp_path, monkeypatch, caplog, name, y, by):
    """C1, C8.3, C12: one count (with its breakdown, if any) and `details`; then every place
    C1 names is searched for a row and for a figure from 1 to 9."""
    caplog.set_level(logging.DEBUG)
    caplog.set_level(logging.DEBUG, logger="moco_agent")
    rows = but_the_newest(fixture_rows(name))
    sid = A_ID if name == "arrests_like" else C_ID
    env = CountyEnv(tmp_path, monkeypatch, names=(name,))
    text = "I counted {r1.count}. {r1.groups}." if by else "I counted {r1.count}."
    reply = env.ask(Q_BREAKDOWN, Step(count(sid, year(y), [], [by] if by else [])),
                    Step(finish("finding", text)))
    answers = [m["content"] for call in env.model.calls for m in tool_messages(call["messages"])]
    # C36 point 5 (S3-R6-A): `details` goes to the model, which calls show_details
    details = env.ask("details", Step(show_details()))
    every_row_free([reply.text, details.text], rows, "reply or details")
    for shown_text in (reply.text, details.text):
        assert_no_hidden_figure(shown_text)
    every_row_free(answers, rows, "tool answer")
    for content in answers:
        parsed = json.loads(content)
        if isinstance(parsed, dict) and "result_id" in parsed:
            assert figures(content) == set(), f"a value in a tool answer: {content}"
    every_row_free([log_text(caplog)], rows, "log")
    cells = [str(c) for c in db_cells(env.tmp_path)]
    every_row_free(cells, rows, "stored turn")
    assert "FIXTURE-" not in db_bytes(env.tmp_path)
    for text_of_file in runs_texts(env.runs_dir):
        assert "FIXTURE-" not in text_of_file, "a row id in the runs folder"


@pytest.mark.parametrize("flt, group_by", [
    (is_("id", "FIXTURE-A-0001"), []),
    (None, ["id"]),
], ids=["a filter on the key", "a breakdown by the key"])
def test_the_key_field_never_shows_a_row(tmp_path, monkeypatch, flt, group_by):
    """C3 (`key`: never a filter, never a breakdown, never shown) and C8.3: BAD_FIELD, and
    no row id in the answer or the reply."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask("Show me one of the 2025 records.",
                    Step(count(A_ID, year(2025), [flt] if flt else [], group_by)),
                    Step(finish("finding", "I counted {r1.count}.")))
    answer = env.model.answer(0)
    assert answer.get("error") == "BAD_FIELD", answer
    rows = but_the_newest(fixture_rows("arrests_like"))
    assert_no_row(json.dumps(answer), rows, "tool answer")
    assert_no_row(reply.text, rows, "reply")
    assert reply.run_ids == []


def test_a_period_that_holds_one_record_shows_fewer_than_10(tmp_path, monkeypatch, caplog):
    """C1 and C8: the copy's newest record stands alone on 17 September 2026; a count of
    that day is `fewer than 10`, never 1, in the reply and in its details; nothing about the
    record itself is shown."""
    caplog.set_level(logging.DEBUG, logger="moco_agent")
    day = [r for r in fixture_rows("arrests_like") if r["event_date_time"].startswith("2026-09-17")]
    assert len(day) == 1
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask(Q_COUNT, Step(count(A_ID, dates("2026-09-17", "2026-09-17"))),
                    Step(finish("finding", "I counted {r1.count}.")))
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    # Turned round for C76 (D-093, planning chat, 21 Nov 2026): one day reads "on ...".
    assert reply.text.startswith("I counted fewer than 10 arrest records on 17 September 2026."), \
        reply.text
    # C36 point 5 (S3-R6-A): `details` goes to the model, which calls show_details
    details = env.ask("details", Step(show_details()))
    rows = but_the_newest(fixture_rows("arrests_like"))
    for text in (reply.text, details.text):
        assert_no_hidden_figure(text)
        assert_no_row(text, rows)
    assert "T08:30" not in reply.text + details.text, "the record's own time is shown"
    assert_no_row(log_text(caplog), rows, "log")


def test_the_facts_of_describe_data_hold_no_row(tmp_path, monkeypatch):
    """C11 with C1: describe_data's facts are generated from the source files and hold no
    record."""
    env = CountyEnv(tmp_path, monkeypatch, names=("arrests_like", "coded_like"))
    env.ask(Q_ABOUT, Step(describe()), Step(finish("about_data", "{f1}.")))
    contents = [m["content"] for call in env.model.calls for m in tool_messages(call["messages"])]
    for name in ("arrests_like", "coded_like"):
        every_row_free(contents, but_the_newest(fixture_rows(name)), "describe_data")


def test_log_lines_hold_neither_the_question_nor_the_reply(tmp_path, monkeypatch, caplog):
    """A0, unchanged in county mode: the log never holds question or reply text."""
    caplog.set_level(logging.DEBUG)
    caplog.set_level(logging.DEBUG, logger="moco_agent")
    env = CountyEnv(tmp_path, monkeypatch)
    question = guard_free("How many arrests were there in 2025, zebra-quartz?")
    reply = env.ask(question, Step(count(A_ID, year(2025), [is_(SCHOOL, True)], ["district"])),
                    Step(finish("finding", "I counted {r1.count}. {r1.groups}.")))
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    logged = log_text(caplog)
    assert "zebra-quartz" not in logged
    assert reply.text.split("\n")[0][:40] not in logged
