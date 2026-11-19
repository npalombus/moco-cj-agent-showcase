"""Memory and filling in county mode: docs/S3A-DESIGN.md C9 (A5's rule, "stated, else
pending, else the last answer's", part by part: the source, the period, each filter by
field), with C5's "Left out: filled from memory (C9), else Python asks, as A5 does for the
year today", and C12's "filling and keeping part by part, and `clear`".

What this file covers (each turn after the first in the same thread, unless it says not)
- The period and a filter are kept from the last answer while a new filter is added; what
  was kept is said: `(I kept 2025 and district 3 from earlier.)` (C9's own example).
- A new filter on a field replaces the old one; `{"field": ..., "clear": true}` removes it;
  a period stated replaces the kept one while the filter is kept.
- Nothing to keep and no period: Python asks (NEEDS_INPUT), counts nothing; the next turn
  fills the filter it saved (pending).
- Part by part: after two counts of different years, the period is not kept (it is not
  one), so Python asks.
- The source is kept too (two sources with copies), and said.
- Another thread keeps nothing.
- A stored turn holds specs and slot texts, never a value; memory works from the database
  (a store opened again on the same file keeps the period).
- A breakdown is not kept (C9 lists the source, the period and the filters only), and the
  kept note stands where C10 puts it: after the table, before the left-out line.

Readings taken (kit-log/raw/S3A-A-notes.txt)
- The kept note for one part is `(I kept 2025 from earlier.)` / `(I kept district 3 from
  earlier.)` (C9's example with one part); its words for a kept source are not given, so a
  kept source is checked only as some kept note.
- `filters` left out of the call means no filter is stated; a list with one filter states
  that field only, and the other fields are filled from memory.
- The tests state the source in every count but the source tests, so that the kept note
  holds the period and filters only.
- A stored turn's spec is looked for as its field name or its fixed words.
"""
import json
import re

import pytest

from p1support import (LEAVE_OUT, THREAD_2, Step, db_cells, finish, has_number, open_store)
from s3support import (A_ID, C_ID, KEPT_ANY, NAMES, Q_BREAKDOWN, Q_COUNT, Q_FOLLOW, SCHOOL,
                       CountyEnv, assert_reply, check_county_reply, clear, compare, count, is_,
                       left_out_line, sensitive_line, source_re, table_lines, truth, year)

PAGE_A = "https://fixture.invalid/d/arrests-like"
TEXT = "I counted {r1.count}."


def first_answer(env, filters=(is_("district", "district 3"),), period=year(2025)):
    """2025 in district 3: 27 records, 9 with no district left out."""
    reply = env.ask(Q_COUNT, Step(count(A_ID, period, list(filters))),
                    Step(finish("finding", TEXT)))
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    return reply


def follow(env, *count_calls, text=TEXT, question=Q_FOLLOW, **kw):
    return env.ask(question, Step(*count_calls), Step(finish("finding", text)), **kw)


def kept(*parts):
    return " and ".join(parts).join(["(I kept ", " from earlier.)"])


def test_the_period_and_a_filter_are_kept_and_said(tmp_path, monkeypatch):
    """C9: the period and the district filter are the last answer's, the new gender filter
    is stated: 14 records of women in district 3 in 2025, and `(I kept 2025 and district 3
    from earlier.)`."""
    env = CountyEnv(tmp_path, monkeypatch)
    first_answer(env)
    spec = (year(2025), [is_("gender", "female"), is_("district", "district 3")])
    t = truth("arrests_like", *spec)
    assert t["total"] == 14 and t["left_out"] == {"gender": 0, "district": 3}
    reply = follow(env, count(A_ID, LEAVE_OUT, [is_("gender", "female")]))
    check_county_reply(reply)
    assert_reply(reply.text,
                 "I counted 14 arrest records of people recorded as female in district 3 in 2025.",
                 kept=kept("2025", "district 3"), left_out=[left_out_line(3, "district")],  # C49
                 hidden_optional=PAGE_A, sensitive=sensitive_line("arrest records"),
                 source=source_re("arrests_like", first=False))


def test_a_new_filter_on_a_field_replaces_the_old_one(tmp_path, monkeypatch):
    """C9: a new filter on a field replaces the old one; the period is kept."""
    env = CountyEnv(tmp_path, monkeypatch)
    first_answer(env)
    assert truth("arrests_like", year(2025), [is_("district", "district 4")])["total"] == 26
    reply = follow(env, count(A_ID, LEAVE_OUT, [is_("district", "district 4")]))
    check_county_reply(reply)
    assert_reply(reply.text, "I counted 26 arrest records in district 4 in 2025.",
                 kept=kept("2025"), left_out=[left_out_line(9, "district")],  # C49
                 hidden_optional=PAGE_A, source=source_re("arrests_like", first=False))


def test_clear_removes_a_kept_filter(tmp_path, monkeypatch):
    """C9: a `filters` entry {"field": "district", "clear": true} removes it."""
    env = CountyEnv(tmp_path, monkeypatch)
    first_answer(env)
    reply = follow(env, count(A_ID, LEAVE_OUT, [clear("district")]))
    check_county_reply(reply)
    assert_reply(reply.text, "I counted 240 arrest records in 2025.", kept=kept("2025"),
                 source=source_re("arrests_like", first=False))


def test_clear_keeps_the_other_filters(tmp_path, monkeypatch):
    """C9: `clear` removes that field's filter only; the others are kept by field."""
    env = CountyEnv(tmp_path, monkeypatch)
    first_answer(env, filters=(is_("district", "district 3"), is_(SCHOOL, True)))
    t = truth("arrests_like", year(2025), [is_(SCHOOL, True)])
    assert t["total"] == 76
    reply = follow(env, count(A_ID, LEAVE_OUT, [clear("district")]))
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert reply.text.startswith("I counted 76 arrest records within 500 feet of a school in "
                                 "2025."), reply.text
    assert KEPT_ANY.search(reply.text) and "district 3" not in reply.text


def test_a_stated_period_replaces_the_kept_one(tmp_path, monkeypatch):
    """C9: the period stated wins; the filter is kept: 45 records in district 3 in 2024."""
    env = CountyEnv(tmp_path, monkeypatch)
    first_answer(env)
    assert truth("arrests_like", year(2024), [is_("district", "district 3")])["total"] == 45
    reply = follow(env, count(A_ID, year(2024)))
    check_county_reply(reply)
    assert_reply(reply.text, "I counted 45 arrest records in district 3 in 2024.",
                 kept=kept("district 3"), left_out=[left_out_line(10, "district")],  # C49
                 source=source_re("arrests_like", first=False))


def test_with_no_period_and_nothing_kept_python_asks(tmp_path, monkeypatch):
    """C5: period left out, nothing in memory: Python asks, as A5 does for the year today
    (NEEDS_INPUT / NEEDS_CLARIFICATION), and counts nothing."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply = follow(env, count(A_ID, LEAVE_OUT, [is_("district", "district 3")]),
                   question=Q_COUNT)
    check_county_reply(reply)
    assert (reply.status, reply.reason_code) == ("NEEDS_INPUT", "NEEDS_CLARIFICATION"), \
        (reply.status, reply.reason_code, reply.text)
    assert reply.run_ids == [] and "27" not in reply.text


def test_a_pending_filter_fills_the_next_turn(tmp_path, monkeypatch):
    """C9 with A5's pending: the turn that asked saved its district filter; the next turn
    states the period and keeps the filter."""
    env = CountyEnv(tmp_path, monkeypatch)
    asked = follow(env, count(A_ID, LEAVE_OUT, [is_("district", "district 3")]),
                   question=Q_COUNT)
    assert asked.status == "NEEDS_INPUT", (asked.status, asked.reason_code, asked.text)
    reply = follow(env, count(A_ID, year(2025)), question="2025")
    check_county_reply(reply)
    assert_reply(reply.text, "I counted 27 arrest records in district 3 in 2025.",
                 kept=kept("district 3"), left_out=[left_out_line(9, "district")],  # C49
                 hidden_optional=PAGE_A, source=source_re("arrests_like", first=True))


def test_a_period_that_is_not_one_is_not_kept(tmp_path, monkeypatch):
    """C9 part by part, with A5's base ("its year, if those counts share exactly one"): after
    counts of 2024 and 2025 in district 3, there is no one period to keep, so Python asks."""
    env = CountyEnv(tmp_path, monkeypatch)
    first = env.ask(Q_COUNT, Step(count(A_ID, year(2024), [is_("district", "district 3")]),
                                  count(A_ID, year(2025), [is_("district", "district 3")])),
                    Step(compare("r1", "r2")),
                    Step(finish("finding", "Here is the comparison: {r3.compare}.")))
    assert first.status == "ANSWERED", (first.status, first.reason_code, first.text)
    reply = follow(env, count(A_ID, LEAVE_OUT, [is_("gender", "female")]))
    assert reply.status == "NEEDS_INPUT", (reply.status, reply.reason_code, reply.text)
    assert reply.run_ids == []


def test_the_source_is_kept_and_said(tmp_path, monkeypatch):
    """C9: the source is one of the parts kept. Two sources have copies; the follow-up
    leaves the source out and gets the last answer's (coded_like), and says what it kept."""
    env = CountyEnv(tmp_path, monkeypatch, names=NAMES)
    first = env.ask(Q_COUNT, Step(count(C_ID, year(2025))), Step(finish("finding", TEXT)))
    assert first.text.startswith("I counted 200 intake records in 2025."), first.text
    reply = follow(env, count(LEAVE_OUT, year(2026)))
    check_county_reply(reply)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert reply.text.startswith("I counted 100 intake records in 2026 (through 20 August 2026, "
                                 "the latest in this copy)."), reply.text
    assert KEPT_ANY.search(reply.text), reply.text


def test_another_thread_keeps_nothing(tmp_path, monkeypatch):
    """C9 is per thread (A5: "for one thread key")."""
    env = CountyEnv(tmp_path, monkeypatch)
    first_answer(env)
    reply = follow(env, count(A_ID, LEAVE_OUT, [is_("gender", "female")]), thread_key=THREAD_2)
    assert reply.status == "NEEDS_INPUT", (reply.status, reply.reason_code, reply.text)
    assert "I kept" not in reply.text


def _without_sent(cell, sent):
    """A memory record (JSON) without its `sent` key, which must be the reply sent (C61 point 4;
    added by briefs/S3-R23-A-tests.md); any other cell as it is."""
    try:
        record = json.loads(cell)
    except ValueError:
        return cell
    if not isinstance(record, dict) or "sent" not in record:
        return cell
    kept = record.pop("sent")
    head = kept[:-4] if kept.endswith(" ...") and len(sent) > 600 else kept  # cut to 600
    assert sent.startswith(head) and (head == sent or len(head) <= 600), \
        "`sent` is not the reply as sent"
    return json.dumps(record)


def test_a_stored_turn_holds_specs_and_slot_texts_never_a_value(tmp_path, monkeypatch):
    """C9: a stored turn holds specs and slot texts, never a value. 2025 near a school by
    district (total 75, groups 31 and 24): the database holds the model's text with its slots
    and the spec, and none of those values. Memory comes from the database: a store opened
    again on the same file keeps the period."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask(Q_BREAKDOWN, Step(count(A_ID, year(2025), [is_(SCHOOL, True)], ["district"])),
                    Step(finish("finding", "I counted {r1.count}. {r1.groups}.")))
    assert reply.reply_style == "agent", (reply.draft_failures, reply.text)
    # Changed by briefs/S3-R23-A-tests.md (C61 points 4 and 6 of docs/S3A-DESIGN.md: the record
    # holds `sent`, the reply as sent, figures and all, and nothing else of it may hold a value):
    # `sent` is the reply, and it is taken out of the record before the cells are looked at.
    cells = [_without_sent(c, reply.text) for c in db_cells(env.tmp_path) if isinstance(c, str)]
    assert any("{r1.count}" in c and "{r1.groups}" in c for c in cells), "no slot text stored"
    assert any(SCHOOL in c or "within 500 feet of a school" in c for c in cells), \
        "no spec stored"
    for value in (75, 31, 24):
        assert not [c for c in cells if has_number(value, c)], f"a value ({value}) is stored"
    assert not [c for c in cells if "fewer than" in c or "FIXTURE-" in c]
    env.store = open_store(env.tmp_path)
    again = follow(env, count(A_ID, LEAVE_OUT, [is_("district", "district 1")]))
    assert again.status == "ANSWERED", (again.status, again.reason_code, again.text)
    assert again.text.startswith("I counted 10 arrest records in district 1 within 500 feet of "
                                 "a school in 2025."), again.text


def test_a_breakdown_is_not_kept_and_the_kept_note_follows_the_table(tmp_path, monkeypatch):
    """C9 keeps the source, the period and the filters, not the breakdown; C10 puts the kept
    note after the table and before the left-out line. 2024 by district, then by gender with
    the period kept: 121 women, 107 men, 2 with no gender."""
    env = CountyEnv(tmp_path, monkeypatch)
    env.ask(Q_BREAKDOWN, Step(count(A_ID, year(2024), [], ["district"])),
            Step(finish("finding", TEXT)))
    t = truth("arrests_like", year(2024), [], ["gender"])
    assert dict(t["groups"]) == {"female": 121, "male": 107} and t["left_out"]["gender"] == 2
    reply = follow(env, count(A_ID, LEAVE_OUT, LEAVE_OUT, ["gender"]), question=Q_BREAKDOWN)
    check_county_reply(reply)
    assert_reply(reply.text, "I counted 228 arrest records in 2024 with a gender recorded.",
                 table=table_lines(t["groups"]), kept=kept("2024"),
                 left_out=[left_out_line(2, "gender")], hidden_optional=PAGE_A,
                 sensitive=sensitive_line("arrest records"),
                 source=source_re("arrests_like", first=False))
    plain = follow(env, count(A_ID, LEAVE_OUT))
    assert plain.text.startswith("I counted 230 arrest records in 2024."), plain.text
    assert "district 1:" not in plain.text and "female:" not in plain.text
    assert re.search(r"\(I kept 2024 from earlier\.\)", plain.text), plain.text
