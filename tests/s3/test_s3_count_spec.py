"""The `count` tool and its spec: docs/S3A-DESIGN.md C5 (with C3's kinds of field, C8.4 and
C0's "only county sources can be counted"), and C12's "every row of C5's error table; a spec
the file allows gives the truth file's figures" and "no age filter narrower than two years
below 18, by any wording of the spec".

What this file covers
- A good spec makes a result: Python answers {"result_id", "read_as", "slots"} with no value
  from the data; `read_as` is the count phrase without its number; `{rN.groups}` is offered
  for a one-way breakdown only. The record (stage 1's kind: runs/<run id>/manifest.json)
  holds the exact total, every group's exact value, what was left out, the spec's source and
  the figures as shown. The reply's total is the truth's, on both fixtures, for each kind of
  period, filter and breakdown (the phrases themselves are test_s3_phrases.py's).
- Every row of the error table but PARTIAL_YEAR (test_s3_share_compare.py): BAD_FIELD,
  BAD_VALUE, OUT_OF_COVERAGE (naming what is covered), NOT_ALLOWED, TOO_FINE (naming
  breakdowns that would not be), TOO_MANY (three breakdowns, more than 400 groups, a ninth
  count). Each is a tool error, nothing is counted (no record), and the turn goes on.
- No age filter narrower than two years that touches an age below 18, by any wording: one
  age written both ends, only `to` at the bottom of `usable`, a range whose usable part is
  one age, a part of a year, the age as text, two age filters, bands of the model's own;
  and the wordings next to them that are allowed.
- The source: left out with exactly one copy, filled; with two copies, NEEDS_SOURCE listing
  both titles; an unknown id or the SYNTHETIC source is not counted; a source with no copy
  gives NO_COPY.
- At most one filter per field.

Readings taken (kit-log/raw/S3A-A-notes.txt)
- An error answer is {"error": <code>, ...}; other keys may be there.
- A result made after an error is still r1 (an error makes no result, as in stage 2).
- "Narrower than two years" is measured on the usable whole ages the filter can match: a
  filter whose usable part is one age (`{"to": 10}` when `usable` starts at 10; 5 to 10) is
  as narrow as `aged 10`. A part of a year or an age written as text may be NOT_ALLOWED or
  BAD_VALUE, and two age filters any spec error: each must count nothing.
- Bands of the model's own are given as a group_by entry {"field": "age_band", "bands": ...}
  (C5 gives no other place for them).
- A flag filter written with `in`, a category filter written with `from`/`to` and an age
  filter written with `is` are "a field used in a way its kind does not allow" (BAD_FIELD).
- TOO_MANY for more than 400 groups is checked on rows made so that the breakdown is not
  also too fine; three breakdowns are TOO_MANY whatever their groups.
- NEEDS_SOURCE ends the turn as NEEDS_INPUT, with the reason code NEEDS_SOURCE or A4's
  NEEDS_CLARIFICATION.
- A filter that names a field twice, an unknown source and the SYNTHETIC source get some
  spec error (the code is not given); nothing is counted.
"""
import json

import pytest

from p1support import LEAVE_OUT, Step, deep_leaves, finish, has_leaf, manifests
from s3support import (A_ID, C_ID, NAMES, Q_COUNT, SCHOOL, SPEC_ERRORS, CountyEnv, age,
                       check_county_reply, count, dates, figures, hours, in_, is_,
                       made_rows, months, run_records, shown, source_json, too_fine, truth,
                       weekdays, year, years)

CODED_AGE = "age_years"


def ask_count(env, *count_calls, text="I counted {r1.count}."):
    """One turn: the counts in one step, then a finish."""
    return env.ask(Q_COUNT, Step(*count_calls), Step(finish("finding", text)))


def answer_of(env, position=0):
    return env.model.answer(0, position)


def assert_spec_error(env, code, *, position=0):
    answer = answer_of(env, position)
    assert isinstance(answer, dict) and answer.get("error") == code, answer
    assert "result_id" not in answer
    return answer


def assert_nothing_counted(env, reply):
    assert reply.run_ids == [] and reply.results == []
    assert manifests(env.runs_dir) == [], "a record was saved for a spec that failed"


# ---- a good spec ---------------------------------------------------------------------------

GOOD = {
    # id: (fixture, period, filters, group_by)
    "a year": ("arrests_like", year(2025), [], []),
    "two years": ("arrests_like", years(2024, 2025), [], []),
    "months of a year": ("arrests_like", months(2025, 1, 10), [], []),
    "a date range": ("arrests_like", dates("2025-03-01", "2025-08-31"), [], []),
    "an age range": ("arrests_like", year(2025), [age(18, 21)], []),
    "under 18": ("arrests_like", year(2025), [age(None, 17)], []),
    "a person category": ("arrests_like", year(2025), [is_("gender", "female")], []),
    "two districts": ("arrests_like", year(2025), [in_("district", "district 3", "district 4")],
                      []),
    "a flag": ("arrests_like", year(2025), [is_(SCHOOL, True)], []),
    "a flag, false": ("arrests_like", year(2025), [is_(SCHOOL, False)], []),
    "weekends": ("arrests_like", year(2025), [weekdays("Saturday", "Sunday")], []),
    "hours over midnight": ("arrests_like", year(2025), [hours(22, 5)], []),
    "by district": ("arrests_like", year(2024), [], ["district"]),
    "by flag": ("arrests_like", year(2025), [], [SCHOOL]),
    "by age band": ("arrests_like", year(2025), [], ["age_band"]),
    "by year": ("arrests_like", years(2024, 2025), [], ["year"]),
    "by month": ("arrests_like", year(2025), [], ["month"]),
    "by weekday": ("arrests_like", year(2025), [], ["weekday"]),
    "by hour": ("arrests_like", year(2025), [], ["hour"]),
    "near a school by district": ("arrests_like", year(2025), [is_(SCHOOL, True)],
                                  ["district"]),
    "by district and gender": ("arrests_like", year(2024), [], ["district", "gender"]),
    "coded: two spellings, one label": ("coded_like", year(2025), [is_("race_code", "group W")],
                                        []),
    "coded: station 3 (3D and 3rd)": ("coded_like", year(2025), [is_("station", "station 3")],
                                      []),
    "coded: by station": ("coded_like", year(2025), [], ["station"]),
    "coded: by race": ("coded_like", year(2025), [], ["race_code"]),
    "coded: under 18": ("coded_like", year(2025), [age(None, 17, CODED_AGE)], []),
    "coded: by age band": ("coded_like", year(2026), [], ["age_band"]),
}


def unit_many(name):
    return source_json(name)["unit"]["many"]


@pytest.mark.parametrize("case", list(GOOD))
def test_a_spec_the_file_allows_gives_the_truths_figures(tmp_path, monkeypatch, case):
    """C5 and C12: the total shown is the truth's; the record holds the exact total, every
    group's exact value and what was left out (C2: always counted)."""
    name, period, filters, group_by = GOOD[case]
    t = truth(name, period, filters, group_by)
    env = CountyEnv(tmp_path, monkeypatch, names=(name,))
    reply = ask_count(env, count(source_json(name)["id"], period, filters, group_by))
    check_county_reply(reply)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert reply.text.startswith(f"I counted {shown(t['total'])} {unit_many(name)}"), reply.text
    (record,) = run_records(reply, env.runs_dir)
    assert has_leaf(record, t["total"]), f"the exact total {t['total']} is not in the record"
    values = list((t["groups"] or {}).values()) + list((t["grid"] or {}).values())
    for value in set(values):
        assert has_leaf(record, value), f"a group's exact value {value} is not in the record"
    for field_name, n in t["left_out"].items():
        if n:
            assert has_leaf(record, n), f"left out ({field_name}: {n}) is not in the record"
    assert has_leaf(record, source_json(name)["id"]), "the spec's source is not in the record"


def test_the_record_holds_the_figures_as_shown(tmp_path, monkeypatch):
    """C5 "The record": the exact figures and the figures as shown. 2025 near a school by
    district has groups of 10, 9, 1, 0, 24 and 31; two are shown as `fewer than 10`."""
    env = CountyEnv(tmp_path, monkeypatch)
    spec = (year(2025), [is_(SCHOOL, True)], ["district"])
    reply = ask_count(env, count(A_ID, *spec))
    (record,) = run_records(reply, env.runs_dir)
    for n in (10, 9, 1, 0, 24, 31, 75):
        assert has_leaf(record, n), n
    strings = [v for v in deep_leaves(record) if isinstance(v, str)]
    assert any("fewer than 10" in s for s in strings), "the figures as shown are not saved"


ANSWERS = {
    # id: (spec, read_as, slots)
    "a year": ((year(2025), [], []), "arrest records in 2025", ["{r1.count}"]),
    "one-way": ((year(2025), [is_(SCHOOL, True)], ["district"]),
                "arrest records within 500 feet of a school in 2025",
                ["{r1.count}", "{r1.groups}"]),
    "two-way": ((year(2024), [], ["district", "gender"]), "arrest records in 2024",
                ["{r1.count}"]),
    "three filters": ((year(2025), [age(18, 21), is_("gender", "female"),
                                    is_("district", "district 3")], []),
                      "arrest records of people aged 18 to 21, recorded as female in district 3 "
                      "in 2025", ["{r1.count}"]),
    "a hidden total": ((year(2025), [is_(SCHOOL, True), is_("district", "district 3")], []),
                       "arrest records in district 3 within 500 feet of a school in 2025",
                       ["{r1.count}"]),
}


@pytest.mark.parametrize("case", list(ANSWERS))
def test_python_answers_a_good_spec_with_read_as_and_slots(tmp_path, monkeypatch, case):
    """C5: {"result_id": "r1", "read_as": "<the count phrase without its number>", "slots":
    ["{r1.count}", "{r1.groups}"]}, `{rN.groups}` only for a one-way breakdown; no value from
    the data (no figure at all)."""
    spec, read_as, slots = ANSWERS[case]
    env = CountyEnv(tmp_path, monkeypatch)
    reply = ask_count(env, count(A_ID, *spec))
    answer = answer_of(env)
    assert answer.get("result_id") == "r1", answer
    assert answer.get("read_as") == read_as, answer
    assert list(answer.get("slots", [])) == slots, answer
    assert figures(json.dumps(answer)) == set(), f"a value from the data: {answer}"
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)


# ---- the error table (C5) -----------------------------------------------------------------

BAD_FIELD = {
    "a field the source lacks (filter)": ("arrests_like", [is_("zone", "zone 1")], []),
    "a field the source lacks (breakdown)": ("arrests_like", [], ["zone"]),
    "the key field as a filter": ("arrests_like", [is_("id", "FIXTURE-A-0001")], []),
    "the key field as a breakdown": ("arrests_like", [], ["id"]),
    "coded: the key field as a filter": ("coded_like", [is_("case_no", "FIXTURE-C-0001")], []),
    "age as a breakdown (only age_band)": ("arrests_like", [], ["age"]),
    "an age filter written with is": ("arrests_like", [{"field": "age", "is": 30}], []),
    "a category filter written with from and to": (
        "arrests_like", [{"field": "district", "from": 1, "to": 3}], []),
    "a flag filter written with in": (
        "arrests_like", [{"field": SCHOOL, "in": ["within 500 feet of a school"]}], []),
    "coded: a flag it does not have": ("coded_like", [], [SCHOOL]),
    "coded: a field of the other source": ("coded_like", [is_("district", "district 3")], []),
}


@pytest.mark.parametrize("case", list(BAD_FIELD))
def test_bad_field(tmp_path, monkeypatch, case):
    """C5 BAD_FIELD: a field the source lacks, a `key` field, or a field used in a way its
    kind does not allow (C3's table). A tool error; nothing counted."""
    name, filters, group_by = BAD_FIELD[case]
    env = CountyEnv(tmp_path, monkeypatch, names=(name,))
    reply = ask_count(env, count(source_json(name)["id"], year(2025), filters, group_by))
    assert_spec_error(env, "BAD_FIELD")
    assert_nothing_counted(env, reply)


BAD_VALUE = {
    "a label the file does not list": ("arrests_like", year(2025), [is_("district", "district 9")]),
    "a raw value, not a label": ("arrests_like", year(2025), [is_("district", "3")]),
    "one listed label and one not": ("arrests_like", year(2025),
                                     [in_("race", "group Alpha", "group Delta")]),
    "coded: a raw spelling, not its label": ("coded_like", year(2025), [is_("race_code", "W")]),
    "an age range the wrong way round": ("arrests_like", year(2025), [age(30, 20)]),
    "a weekday that is not one": ("arrests_like", year(2025), [weekdays("Funday")]),
    "an hour that is not one": ("arrests_like", year(2025), [hours(22, 24)]),
    "dates the wrong way round": ("arrests_like", dates("2025-08-31", "2025-03-01"), []),
    "a date that does not exist": ("arrests_like", dates("2025-02-30", "2025-03-31"), []),
    "months the wrong way round": ("arrests_like", months(2025, 10, 3), []),
    "a month that does not exist": ("arrests_like", months(2025, 1, 13), []),
}


@pytest.mark.parametrize("case", list(BAD_VALUE))
def test_bad_value(tmp_path, monkeypatch, case):
    """C5 BAD_VALUE: a label the file does not list; a range the wrong way round; a period
    that is not a real date range. A tool error; nothing counted."""
    name, period, filters = BAD_VALUE[case]
    env = CountyEnv(tmp_path, monkeypatch, names=(name,))
    reply = ask_count(env, count(source_json(name)["id"], period, filters))
    assert_spec_error(env, "BAD_VALUE")
    assert_nothing_counted(env, reply)


OUT_OF_COVERAGE = {
    "the year before": ("arrests_like", year(2023), ("2024", "2026")),
    "a year after": ("arrests_like", year(2027), ("2024", "2026")),
    "two years before": ("arrests_like", years(2022, 2023), ("2024", "2026")),
    "after the newest record": ("arrests_like", dates("2026-10-01", "2026-10-31"),
                                ("2024", "2026")),
    "coded: before its coverage": ("coded_like", year(2024), ("2025", "2026")),
}


@pytest.mark.parametrize("case", list(OUT_OF_COVERAGE))
def test_out_of_coverage_names_what_is_covered(tmp_path, monkeypatch, case):
    """C5 OUT_OF_COVERAGE: a period wholly outside the copy; the error names what is
    covered (its first and last year are in the answer)."""
    name, period, covered = OUT_OF_COVERAGE[case]
    env = CountyEnv(tmp_path, monkeypatch, names=(name,))
    reply = ask_count(env, count(source_json(name)["id"], period))
    answer = assert_spec_error(env, "OUT_OF_COVERAGE")
    text = json.dumps(answer)
    assert all(y in text for y in covered), f"the error does not name what is covered: {answer}"
    assert_nothing_counted(env, reply)


# ---- under 18: by any wording (C5 NOT_ALLOWED, C8.4, C12) --------------------------------------

NARROW_UNDER_18 = {
    "aged 17": ("arrests_like", age(17, 17)),
    "aged 10 (the youngest usable)": ("arrests_like", age(10, 10)),
    "aged 12": ("arrests_like", age(12, 12)),
    "only `to` at the bottom of usable (age 10 alone)": ("arrests_like", age(None, 10)),
    "5 to 10 (only 10 is usable)": ("arrests_like", age(5, 10)),
    "coded: aged 15": ("coded_like", age(15, 15, CODED_AGE)),
    "coded: only `to` at the bottom of usable (age 12 alone)": ("coded_like",
                                                               age(None, 12, CODED_AGE)),
}


@pytest.mark.parametrize("case", list(NARROW_UNDER_18))
def test_an_age_filter_narrower_than_two_years_below_18_is_not_allowed(tmp_path, monkeypatch,
                                                                       case):
    """C5 and C8.4: NOT_ALLOWED for an age filter narrower than two years that touches any
    age below 18. Nothing is counted."""
    name, flt = NARROW_UNDER_18[case]
    env = CountyEnv(tmp_path, monkeypatch, names=(name,))
    reply = ask_count(env, count(source_json(name)["id"], year(2025), [flt]))
    assert_spec_error(env, "NOT_ALLOWED")
    assert_nothing_counted(env, reply)


OTHER_NARROW_WORDINGS = {
    "a part of a year": ({"field": "age", "from": 16.5, "to": 17.4}, {"NOT_ALLOWED", "BAD_VALUE"}),
    "the age as text": ({"field": "age", "from": "17", "to": "17"}, {"NOT_ALLOWED", "BAD_VALUE"}),
}


@pytest.mark.parametrize("case", list(OTHER_NARROW_WORDINGS))
def test_other_wordings_of_one_age_below_18_count_nothing(tmp_path, monkeypatch, case):
    """C12: no age filter narrower than two years below 18, by any wording of the spec."""
    flt, codes = OTHER_NARROW_WORDINGS[case]
    env = CountyEnv(tmp_path, monkeypatch)
    reply = ask_count(env, count(A_ID, year(2025), [flt]))
    assert answer_of(env).get("error") in codes, answer_of(env)
    assert_nothing_counted(env, reply)


def test_two_age_filters_that_meet_at_one_age_count_nothing(tmp_path, monkeypatch):
    """C5 "at most one per field", and C12 "by any wording": 10 to 17 and 17 to 30 meet at
    17 alone; the spec is refused and nothing is counted."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply = ask_count(env, count(A_ID, year(2025), [age(10, 17), age(17, 30)]))
    assert answer_of(env).get("error") in SPEC_ERRORS, answer_of(env)
    assert_nothing_counted(env, reply)


@pytest.mark.parametrize("bands", [[[10, 13], [14, 17]], [[17, 17]], [[10, 17], [18, 98]]],
                         ids=["two under-18 bands", "one age", "other bands"])
def test_age_bands_other_than_the_files_are_not_allowed(tmp_path, monkeypatch, bands):
    """C5 NOT_ALLOWED: `age_band` with bands other than the file's."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply = ask_count(env, count(A_ID, year(2025), [], [{"field": "age_band", "bands": bands}]))
    assert_spec_error(env, "NOT_ALLOWED")
    assert_nothing_counted(env, reply)


ALLOWED_AGES = {
    "16 to 17 (two years)": (age(16, 17), 2025),
    "17 to 18 (two years)": (age(17, 18), 2025),
    "under 18": (age(None, 17), 2025),
    "aged 18": (age(18, 18), 2025),
    "aged 30": (age(30, 30), 2025),
    "10 to 11 (two years)": (age(10, 11), 2024),
}


@pytest.mark.parametrize("case", list(ALLOWED_AGES))
def test_the_age_filters_next_to_them_are_allowed(tmp_path, monkeypatch, case):
    """C5: only a filter narrower than two years that touches an age below 18 is refused;
    two years under 18, or one age of 18 and over, is counted (with the truth's total)."""
    flt, y = ALLOWED_AGES[case]
    env = CountyEnv(tmp_path, monkeypatch)
    reply = ask_count(env, count(A_ID, year(y), [flt]))
    assert "error" not in answer_of(env), answer_of(env)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    t = truth("arrests_like", year(y), [flt])
    assert reply.text.startswith(f"I counted {shown(t['total'])} arrest records"), reply.text


# ---- TOO_FINE and TOO_MANY ------------------------------------------------------------------

def test_too_fine_names_the_breakdowns_that_would_not_be(tmp_path, monkeypatch):
    """C5 TOO_FINE: 2026 by race has groups of 3, 2 and 125: two of the three groups with a
    record would be hidden. The error names breakdowns that would not be too fine (by
    district and by gender, whose groups are all 20 or more)."""
    t = truth("arrests_like", year(2026), [], ["race"])
    assert too_fine(t["groups"].values())
    for fine in ("district", "gender"):
        assert not too_fine(truth("arrests_like", year(2026), [], [fine])["groups"].values())
    env = CountyEnv(tmp_path, monkeypatch)
    reply = ask_count(env, count(A_ID, year(2026), [], ["race"]))
    answer = assert_spec_error(env, "TOO_FINE")
    text = json.dumps(answer)
    assert "district" in text and "gender" in text, answer
    assert_nothing_counted(env, reply)


def test_too_fine_for_a_two_way_breakdown(tmp_path, monkeypatch):
    """C5 TOO_FINE: 2025 by weekday and hour has 122 groups with a record, all hidden."""
    t = truth("arrests_like", year(2025), [], ["weekday", "hour"])
    assert len(t["grid"]) == 168 and too_fine(t["grid"].values())
    env = CountyEnv(tmp_path, monkeypatch)
    reply = ask_count(env, count(A_ID, year(2025), [], ["weekday", "hour"]))
    assert_spec_error(env, "TOO_FINE")
    assert_nothing_counted(env, reply)


def test_exactly_half_hidden_is_not_too_fine(tmp_path, monkeypatch):
    """C5 TOO_FINE needs MORE than half: 2026 by ethnicity has groups of 5 and 125 (one of
    two hidden)."""
    t = truth("arrests_like", year(2026), [], ["ethnicity"])
    assert dict(t["groups"]) == {"Hispanic": 5, "not Hispanic": 125}
    env = CountyEnv(tmp_path, monkeypatch)
    reply = ask_count(env, count(A_ID, year(2026), [], ["ethnicity"]))
    assert "error" not in answer_of(env), answer_of(env)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)


def test_three_breakdowns_are_too_many(tmp_path, monkeypatch):
    """C5 TOO_MANY: more than two breakdowns."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply = ask_count(env, count(A_ID, year(2024), [], ["district", "gender", SCHOOL]))
    assert_spec_error(env, "TOO_MANY")
    assert_nothing_counted(env, reply)


def test_more_than_400_groups_are_too_many(tmp_path, monkeypatch):
    """C5 TOO_MANY: more than 400 groups. 2024 and 2025 by month and hour is 24 x 24 = 576
    groups; the rows are made so that only two groups have records, 20 each (so the
    breakdown is not also too fine)."""
    rows = made_rows("arrests_like", (20, {"event_date_time": "2024-05-06T10:00:00.000"}),
                     (20, {}))
    t = truth("arrests_like", years(2024, 2025), [], ["month", "hour"], rows=rows)
    assert len(t["grid"]) == 576 and not too_fine(t["grid"].values())
    env = CountyEnv(tmp_path, monkeypatch, rows={"arrests_like": rows})
    reply = ask_count(env, count(A_ID, years(2024, 2025), [], ["month", "hour"]))
    assert_spec_error(env, "TOO_MANY")
    assert_nothing_counted(env, reply)


def test_a_ninth_count_in_the_turn_is_too_many(tmp_path, monkeypatch):
    """C5 TOO_MANY: a ninth `count` in the turn. Eight different counts are made (r1 to
    r8); the ninth gets the error; the turn goes on to its finish."""
    specs = [(year(2024),), (year(2025),), (year(2026),), (years(2024, 2025),),
             (months(2025, 1, 6),), (months(2025, 7, 12),), (dates("2025-03-01", "2025-08-31"),),
             (year(2025), [is_("district", "district 1")]),
             (year(2025), [is_("district", "district 2")])]
    env = CountyEnv(tmp_path, monkeypatch)
    reply = ask_count(env, *[count(A_ID, *spec) for spec in specs])
    for position in range(8):
        assert answer_of(env, position).get("result_id") == f"r{position + 1}", \
            answer_of(env, position)
    assert_spec_error(env, "TOO_MANY", position=8)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert len(reply.run_ids) == 8


# ---- a bad spec is a tool error and the turn goes on ---------------------------------------

def test_after_a_spec_error_the_turn_goes_on(tmp_path, monkeypatch):
    """C5: "A bad spec is a tool error and the turn goes on": the model counts again and the
    turn is answered from the good spec alone."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask(Q_COUNT, Step(count(A_ID, year(2025), [is_("district", "district 9")])),
                    Step(count(A_ID, year(2025), [is_("district", "district 3")])),
                    Step(finish("finding", "I counted {r1.count}.")))
    assert env.model.answer(0).get("error") == "BAD_VALUE"
    assert env.model.answer(1).get("result_id") == "r1"
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert len(reply.run_ids) == 1
    assert reply.text.startswith("I counted 27 arrest records in district 3 in 2025.")


def test_at_most_one_filter_per_field(tmp_path, monkeypatch):
    """C5: `filters`: a list, at most one per field."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply = ask_count(env, count(A_ID, year(2025), [is_("district", "district 3"),
                                                    is_("district", "district 4")]))
    assert answer_of(env).get("error") in SPEC_ERRORS, answer_of(env)
    assert_nothing_counted(env, reply)


# ---- the source (C5, C0) --------------------------------------------------------------------

def test_the_source_may_be_left_out_when_exactly_one_has_a_copy(tmp_path, monkeypatch):
    """C5: `source` may be left out when exactly one county source has a copy (here two
    source files, one copy)."""
    env = CountyEnv(tmp_path, monkeypatch, names=NAMES, copies=("coded_like",))
    reply = ask_count(env, count(LEAVE_OUT, year(2025)))
    check_county_reply(reply)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert reply.text.startswith("I counted 200 intake records in 2025.")


def test_with_two_copies_a_count_with_no_source_asks_which(tmp_path, monkeypatch):
    """C5: otherwise Python ends the turn asking which, with the fixed row NEEDS_SOURCE
    listing the titles."""
    env = CountyEnv(tmp_path, monkeypatch, names=NAMES)
    reply = ask_count(env, count(LEAVE_OUT, year(2025)))
    check_county_reply(reply)
    assert reply.status == "NEEDS_INPUT", (reply.status, reply.reason_code, reply.text)
    assert reply.reason_code in ("NEEDS_SOURCE", "NEEDS_CLARIFICATION"), reply.reason_code
    for name in NAMES:
        assert source_json(name)["title"] in reply.text
    assert reply.run_ids == [] and len(env.model.calls) == 1, "the turn did not end there"


@pytest.mark.parametrize("source", ["FIXTURE:no_such_source", "SYNTHETIC:arrests_v1",
                                    "MOCO:police_arrests"])
def test_a_source_that_cannot_be_counted_counts_nothing(tmp_path, monkeypatch, source):
    """C0: only county sources can be counted: an unknown id, the SYNTHETIC source and a
    source file this agent was not given (here the real arrests file, absent from the test
    sources) are not counted."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply = ask_count(env, count(source, year(2025)))
    assert reply.run_ids == [] and reply.status != "ANSWERED", (reply.status, reply.text)
    assert manifests(env.runs_dir) == []


def test_a_source_with_no_copy_gives_no_copy(tmp_path, monkeypatch):
    """C4: with no current copy, a count on that source ends the turn with NO_COPY, even
    when another source has one."""
    env = CountyEnv(tmp_path, monkeypatch, names=NAMES, copies=("arrests_like",))
    reply = ask_count(env, count(C_ID, year(2025)))
    assert reply.reason_code == "NO_COPY", (reply.status, reply.reason_code, reply.text)
    assert reply.run_ids == []
