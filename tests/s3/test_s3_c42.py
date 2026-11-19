"""Stage 3 Part A, C42 (docs/S3A-DESIGN.md): a left-out line that says nothing is not written.
Brief: briefs/S3-R9-A-tests.md. Tests only; the planning chat builds C42. All data is SYNTHETIC
fixtures; no real figure is quoted. The figures are worked out by plain counting of the fixture
rows (s3support.truth), as the other county tests do; every phrase is written out by hand.

C42's tests:
- point 1: a count filtered by district with records of no district has no left-out line, and
  the figure is in details; the same for a filter on age, on a person field, on the coded
  fixture's station and on a flag; with a breakdown beside the filter, only the breakdown's
  line is written;
- a breakdown by district: the line as today (and by age band, gender, station; and a field
  both filtered and broken down by, which is broken down by);
- point 2: two counts with the same left-out text: one line, in brackets, no `For <read_as>: `
  (the same shown number, also when two different figures both show as `fewer than 10`);
  two counts with different ones: C19's named lines as today; three counts, two the same and
  one different: the same one once in brackets and the other named; the live run's N28 (two
  counts filtered by district): no left-out line at all;
- point 3: the hidden line, the sensitive line and the source line as today (each reply is
  checked whole).

Changed by briefs/S3-R13-A-tests.md for C49 (docs/S3A-DESIGN.md: C42 point 1 is withdrawn, C10
step 3's line is written for a filtered field too; C42 point 2 and its place are pinned; C49's own
tests are tests/s3/test_s3_c49.py). Five tests, each listed old and new in
kit-log/raw/S3-R13-A-notes.txt: the filter-only count, the flag filter, the filter beside a
breakdown, the live run's N28 and C42-3's case now expect the filter's line (said once where two
counts have the same text). C42-1 and C42-3 below are readings of the withdrawn point 1.

READINGS (also in kit-log/raw/S3-R9-A-notes.txt; the open ones also in briefs/QUESTIONS.md):
- C42-1. "A field the count breaks down by": a field named in `group_by`, with `age_band`
  standing for the source's age field. A field that is both filtered and broken down by is
  broken down by (its line is written).
- C42-2. "The same left-out text (same field, same shown number)": the line's words as C10
  writes them, with the number as C8 shows it; so 9 and 3 left out (both `fewer than 10`) are
  the same text.
- C42-3. Point 1 comes first: a count's left-out figure for a filter-only field writes no line,
  so it is not one of point 2's two lines. A reply whose only left-out line is one count's,
  with another count or a hidden group beside it, names it as C19 does today.
- C42-4. (open, briefs/QUESTIONS.md S3-R9-A question 2) With three counts, two lines the same
  and one different, where the one bracketed line stands among the named ones is not given:
  both orders are accepted (the block sits where C10 puts left-out lines).
- C42-5. (open, question 3) Point 2 is about "one reply"; `details` "still shows every left-out
  figure, as today". When two counts of a details text have the same left-out figure, the line
  at least once is required (each count's own line, or one line, accepted).
- C42-6. A reply's lines are as s3support.reply_re reads C10 (one space, one line break or one
  blank line between the parts Python adds); the hidden line when only a total or a left-out
  count is hidden is accepted either way (s3support's reading), as in the other county tests.
"""
import re

import pytest

from p1support import Step, finish, show_details
from s3support import (A_ID, C_ID, SCHOOL, CountyEnv, Q_BREAKDOWN, Q_COMPARE, Q_COUNT,
                       age, age_left_out_line, assert_reply, check_county_reply, count,
                       hidden_line, in_, is_, is_hidden, left_out_line, made_rows, reply_re,
                       sensitive_line, source_json, source_re, table_lines, too_fine, truth,
                       year)

A, C = "arrests_like", "coded_like"
SID = {A: A_ID, C: C_ID}
Y24, Y25 = year(2024), year(2025)
D2, D3, D5 = (is_("district", f"district {n}") for n in (2, 3, 5))
FEMALE, MALE = is_("gender", "female"), is_("gender", "male")
STATION_1 = is_("station", "station 1")


def counted(n):
    return " ".join(f"I counted {{r{i}.count}}." for i in range(1, n + 1))


def ask(env, question, specs, **kw):
    """One turn: the counts of `specs` [(name, period, filters, group_by)] in one step, then a
    finding with each count slot in its own sentence (it passes R1: the style is agent)."""
    reply = env.ask(question, Step(*[count(SID[name], period, filters, group_by)
                                     for name, period, filters, group_by in specs]),
                    Step(finish("finding", counted(len(specs)))), **kw)
    check_county_reply(reply)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    return reply


def sensitive(name, specs):
    """C10.5: a count of the reply filters or breaks down by a field marked sensitive."""
    fields = {f["name"]: f for f in source_json(name)["fields"]}
    used = [flt["field"] for _, _, filters, _ in specs for flt in filters] + \
        [by for _, _, _, group_by in specs for by in group_by]
    return any(fields.get(n, {}).get("sensitive") for n in used)


def expected(name, specs, line1, left, rows=None, first=True):
    """The whole reply as C10 lays it out, from the truth: each count's table (a one-way
    breakdown), then `left` (the left-out lines), the hidden line (always when a group is
    hidden; either way when only a left-out figure is: C42-6), the sensitive line, the source
    line."""
    truths = [truth(n, p, f, g, rows=rows) for n, p, f, g in specs]
    table = [line for t in truths if t["groups"] for line in table_lines(t["groups"])]
    groups_hidden = any(is_hidden(v) for t in truths if t["groups"] for v in t["groups"].values())
    left_hidden = any(is_hidden(v) for t in truths for v in t["left_out"].values())
    page = source_json(name)["page"]
    return dict(table=table or None, left_out=left,
                hidden=hidden_line(page) if groups_hidden else None,
                hidden_optional=page if (left_hidden and not groups_hidden) else None,
                sensitive=sensitive_line(source_json(name)["unit"]["many"])
                if sensitive(name, specs) else None,
                source=source_re(name, first=first))


# ==== point 1: a field used only as a filter gets no left-out line ===============================

FILTER_ONLY = {
    # id: (source, period, filters, line 1, (field, figure left out), the line details shows)
    "district 3 in 2025 (9 with no district)": (
        A, Y25, [D3], "I counted 27 arrest records in district 3 in 2025.", ("district", 9),
        left_out_line(9, "district")),
    "district 3 in 2024 (10 with no district)": (
        A, Y24, [D3], "I counted 45 arrest records in district 3 in 2024.", ("district", 10),
        left_out_line(10, "district")),
    "people aged 18 to 24 in 2025 (5 with no usable age)": (
        A, Y25, [age(18, 24)], "I counted 52 arrest records of people aged 18 to 24 in 2025.",
        ("age", 5), age_left_out_line(5)),
    "female in 2024 (2 with no gender)": (
        A, Y24, [FEMALE], "I counted 121 arrest records of people recorded as female in 2024.",
        ("gender", 2), left_out_line(2, "gender")),
    "coded: station 1 in 2025 (6 with no station)": (
        C, Y25, [STATION_1], "I counted 60 intake records at station 1 in 2025.", ("station", 6),
        left_out_line(6, "station")),
}


@pytest.mark.parametrize("case", list(FILTER_ONLY))
def test_premise_the_filtered_counts_leave_records_out(case):
    name, period, filters, _, (field, n), _ = FILTER_ONLY[case]
    t = truth(name, period, filters)
    assert t["left_out"] == {field: n} and n > 0, t["left_out"]


@pytest.mark.parametrize("style", ["agent", "fixed"])
@pytest.mark.parametrize("case", list(FILTER_ONLY))
def test_point_1_withdrawn_a_filter_only_field_writes_its_left_out_line(tmp_path, monkeypatch,
                                                                       case, style):
    """Changed by briefs/S3-R13-A-tests.md (C49 point 1; was
    test_point_1_a_filter_only_field_gets_no_left_out_line: "not included" not in the reply, no
    left-out line): the line as C10 writes it."""
    name, period, filters, line1, _, line = FILTER_ONLY[case]
    env = CountyEnv(tmp_path, monkeypatch, names=(name,), MOCO_REPLY_STYLE=style)
    specs = [(name, period, filters, [])]
    reply = ask(env, Q_COUNT, specs)
    assert reply.reply_style == style, (reply.reply_style, reply.draft_failures)
    assert_reply(reply.text, line1, **expected(name, specs, line1, [line]))


@pytest.mark.parametrize("case", list(FILTER_ONLY))
def test_point_1_details_still_show_the_figure(tmp_path, monkeypatch, case):
    name, period, filters, _, _, line = FILTER_ONLY[case]
    env = CountyEnv(tmp_path, monkeypatch, names=(name,))
    ask(env, Q_COUNT, [(name, period, filters, [])])
    details = env.ask("details", Step(show_details()))
    check_county_reply(details)
    assert (details.status, details.reason_code) == ("DETAILS", None), details.text
    assert line in details.text.split("\n"), details.text


SCHOOL_ROWS = ((30, {SCHOOL: "1"}), (40, {SCHOOL: "0"}), (12, {SCHOOL: None}))


def test_point_1_a_flag_filter_with_records_of_no_value(tmp_path, monkeypatch):
    """Made rows: 30 near a school, 40 not, 12 with no value; the count near a school. Changed by
    briefs/S3-R13-A-tests.md (C49 point 1; was: no left-out line): the line, and details as
    before."""
    rows = made_rows(A, *SCHOOL_ROWS)
    specs = [(A, Y25, [is_(SCHOOL, True)], [])]
    t = truth(A, Y25, [is_(SCHOOL, True)], rows=rows)
    assert (t["total"], t["left_out"]) == (30, {SCHOOL: 12})
    env = CountyEnv(tmp_path, monkeypatch, rows={A: rows})
    reply = ask(env, Q_COUNT, specs)
    line1 = "I counted 30 arrest records within 500 feet of a school in 2025."
    line = left_out_line(12, "distance from a school")
    assert_reply(reply.text, line1, **expected(A, specs, line1, [line], rows=rows))
    details = env.ask("details", Step(show_details()))
    assert line in details.text.split("\n"), details.text


# ==== a breakdown: the line as today; with a filter beside it, only the breakdown's ============

BREAKDOWNS = {
    # id: (source, period, filters, group_by, line 1, the left-out lines)
    "2025 by district (9 with no district)": (
        A, Y25, [], ["district"], "I counted 231 arrest records in 2025 with a district recorded.",
        [left_out_line(9, "district")]),
    "2024 by district (10 with no district)": (
        A, Y24, [], ["district"], "I counted 220 arrest records in 2024 with a district recorded.",
        [left_out_line(10, "district")]),
    "2025 by age band (5 with no usable age)": (
        A, Y25, [], ["age_band"], "I counted 235 arrest records in 2025 with a usable age.",
        [age_left_out_line(5)]),
    "2024 by gender (2 with no gender)": (
        A, Y24, [], ["gender"], "I counted 228 arrest records in 2024 with a gender recorded.",
        [left_out_line(2, "gender")]),
    "coded: 2025 by station (6 with no station)": (
        C, Y25, [], ["station"], "I counted 194 intake records in 2025 with a station recorded.",
        [left_out_line(6, "station")]),
    "district 3 and district 4, by district (C42-1: filtered and broken down by)": (
        A, Y25, [in_("district", "district 3", "district 4")], ["district"],
        "I counted 53 arrest records in district 3 and district 4 in 2025 with a district "
        "recorded.", [left_out_line(9, "district")]),
}
BESIDE = {
    # id: (source, period, filters, group_by, line 1, the line kept, today's lines)
    "aged 18 to 24 by district, 2025 (5 with no usable age, 3 with no district)": (
        A, Y25, [age(18, 24)], ["district"],
        "I counted 49 arrest records of people aged 18 to 24 in 2025 with a district recorded.",
        [left_out_line(3, "district")], [age_left_out_line(5), left_out_line(3, "district")]),
    "district 3 by gender, 2024 (10 with no district, 1 with no gender)": (
        A, Y24, [D3], ["gender"],
        "I counted 44 arrest records in district 3 in 2024 with a gender recorded.",
        [left_out_line(1, "gender")], [left_out_line(10, "district"), left_out_line(1, "gender")]),
}


def test_premise_the_breakdowns_leave_records_out_and_are_not_too_fine():
    for case, (name, period, filters, group_by, *_) in {**BREAKDOWNS, **BESIDE}.items():
        t = truth(name, period, filters, group_by)
        assert any(t["left_out"].values()), case
        assert len(t["groups"]) >= 2 and not too_fine(list(t["groups"].values())), case
    t = truth(A, Y25, [age(18, 24)], ["district"])
    assert t["left_out"] == {"age": 5, "district": 3}, t["left_out"]
    assert truth(A, Y24, [D3], ["gender"])["left_out"] == {"district": 10, "gender": 1}


@pytest.mark.parametrize("case", list(BREAKDOWNS))
def test_a_breakdowns_left_out_line_is_as_today(tmp_path, monkeypatch, case):
    name, period, filters, group_by, line1, left = BREAKDOWNS[case]
    env = CountyEnv(tmp_path, monkeypatch, names=(name,))
    specs = [(name, period, filters, group_by)]
    reply = ask(env, Q_BREAKDOWN, specs)
    assert_reply(reply.text, line1, **expected(name, specs, line1, left))


@pytest.mark.parametrize("case", list(BESIDE))
def test_point_1_withdrawn_with_a_filter_beside_the_breakdown_both_lines(tmp_path, monkeypatch,
                                                                         case):
    """Changed by briefs/S3-R13-A-tests.md (C49 point 1; was
    test_point_1_with_a_filter_beside_the_breakdown_only_the_breakdowns_line: the breakdown's
    line only): the filter's line and the breakdown's, in either order (C49-3 of
    tests/s3/test_s3_c49.py); details as before."""
    name, period, filters, group_by, line1, _, both = BESIDE[case]
    env = CountyEnv(tmp_path, monkeypatch, names=(name,))
    specs = [(name, period, filters, group_by)]
    reply = ask(env, Q_BREAKDOWN, specs)
    patterns = [reply_re(line1, **expected(name, specs, line1, block))
                for block in (both, both[::-1])]
    assert any(re.fullmatch(p, reply.text) for p in patterns), \
        f"not the expected county reply (either order).\n--- got ---\n{reply.text}"
    details = env.ask("details", Step(show_details()))
    details_lines = details.text.split("\n")
    for line in BESIDE[case][6]:  # point 1: details show every figure, as today
        assert line in details_lines, (line, details.text)


# ==== point 2: two or more counts ================================================================

DISTRICT_ROWS = ((30, {"district": "1"}), (30, {"district": "2", "gender": "Female"}),
                 (12, {"district": None}))  # the base row is male; the 12 too
SAME = {
    # id: (made rows or None, the counts, line 1, the one line)
    "2025 by district and female 2025 by district (9 and 3: fewer than 10 each)": (
        None, [(A, Y25, [], ["district"]), (A, Y25, [FEMALE], ["district"])],
        "I counted 231 arrest records in 2025 with a district recorded. I counted 97 arrest "
        "records of people recorded as female in 2025 with a district recorded.",
        left_out_line(9, "district")),
    "made rows: 12 with no district in both": (
        DISTRICT_ROWS, [(A, Y25, [], ["district"]), (A, Y25, [MALE], ["district"])],
        "I counted 60 arrest records in 2025 with a district recorded. I counted 30 arrest "
        "records of people recorded as male in 2025 with a district recorded.",
        left_out_line(12, "district")),
}


def test_premise_the_same_texts():
    t1, t2 = (truth(*s) for s in SAME["2025 by district and female 2025 by district (9 and 3: "
                                      "fewer than 10 each)"][1])
    assert (t1["left_out"]["district"], t2["left_out"]["district"]) == (9, 3)
    rows = made_rows(A, *DISTRICT_ROWS)
    t1, t2 = (truth(*s, rows=rows) for s in SAME["made rows: 12 with no district in both"][1])
    assert (t1["total"], t2["total"]) == (60, 30)
    assert (t1["left_out"]["district"], t2["left_out"]["district"]) == (12, 12)


@pytest.mark.parametrize("case", list(SAME))
def test_point_2_two_counts_with_the_same_left_out_text_write_one_line(tmp_path, monkeypatch,
                                                                        case):
    made, specs, line1, line = SAME[case]
    rows = made_rows(A, *made) if made else None
    env = CountyEnv(tmp_path, monkeypatch, rows={A: rows} if rows else None)
    reply = ask(env, Q_BREAKDOWN, specs)
    assert reply.text.split("\n").count(line) == 1, reply.text
    assert "For arrest records" not in reply.text, reply.text
    assert_reply(reply.text, line1, **expected(A, specs, line1, [line], rows=rows))


def test_point_1_and_2_the_live_run_n28_two_counts_filtered_by_district(tmp_path, monkeypatch):
    """N28: district 2 and district 5 in 2025 (9 with no district for each): details show the
    figure (C42-5). Changed by briefs/S3-R13-A-tests.md (C49: was no left-out line at all, point
    1): the same text once, in brackets, unnamed (point 2)."""
    specs = [(A, Y25, [D2], []), (A, Y25, [D5], [])]
    assert [truth(*s)["left_out"] for s in specs] == [{"district": 9}] * 2
    env = CountyEnv(tmp_path, monkeypatch)
    reply = ask(env, Q_COMPARE, specs)
    line1 = ("I counted 35 arrest records in district 2 in 2025. I counted 50 arrest records in "
             "district 5 in 2025.")
    line = left_out_line(9, "district")
    assert reply.text.split("\n").count(line) == 1, reply.text
    assert "For arrest records" not in reply.text, reply.text
    assert_reply(reply.text, line1, **expected(A, specs, line1, [line]))
    details = env.ask("details", Step(show_details()))
    assert left_out_line(9, "district") in details.text.split("\n"), details.text


DIFFERENT = {
    # id: (the counts, line 1, the named lines in order)
    "2025 and 2024 by district (fewer than 10, and 10)": (
        [(A, Y25, [], ["district"]), (A, Y24, [], ["district"])],
        "I counted 231 arrest records in 2025 with a district recorded. I counted 220 arrest "
        "records in 2024 with a district recorded.",
        ["For arrest records in 2025: fewer than 10 had no district recorded and are not "
         "included.",
         "For arrest records in 2024: 10 had no district recorded and are not included."]),
    "2024 by district and by gender (10, and 2)": (
        [(A, Y24, [], ["district"]), (A, Y24, [], ["gender"])],
        "I counted 220 arrest records in 2024 with a district recorded. I counted 228 arrest "
        "records in 2024 with a gender recorded.",
        ["For arrest records in 2024: 10 had no district recorded and are not included.",
         "For arrest records in 2024: fewer than 10 had no gender recorded and are not "
         "included."]),
}


@pytest.mark.parametrize("case", list(DIFFERENT))
def test_point_2_two_counts_with_different_ones_are_named_as_today(tmp_path, monkeypatch, case):
    specs, line1, named = DIFFERENT[case]
    env = CountyEnv(tmp_path, monkeypatch)
    reply = ask(env, Q_BREAKDOWN, specs)
    assert_reply(reply.text, line1, **expected(A, specs, line1, named))


def test_point_2_three_counts_two_the_same_one_different(tmp_path, monkeypatch):
    """The same text (9 and 3, both fewer than 10) once in brackets; the other (10) named.
    C42-4: either order."""
    specs = [(A, Y25, [], ["district"]), (A, Y25, [FEMALE], ["district"]),
             (A, Y24, [], ["district"])]
    assert [truth(*s)["left_out"]["district"] for s in specs] == [9, 3, 10]
    env = CountyEnv(tmp_path, monkeypatch)
    reply = ask(env, Q_BREAKDOWN, specs)
    line1 = ("I counted 231 arrest records in 2025 with a district recorded. I counted 97 arrest "
             "records of people recorded as female in 2025 with a district recorded. I counted "
             "220 arrest records in 2024 with a district recorded.")
    same = left_out_line(9, "district")
    other = "For arrest records in 2024: 10 had no district recorded and are not included."
    patterns = [reply_re(line1, **expected(A, specs, line1, block))
                for block in ([same, other], [other, same])]
    assert any(re.fullmatch(p, reply.text) for p in patterns), \
        f"not the expected county reply (either order).\n--- got ---\n{reply.text}"
    assert "For arrest records in 2025" not in reply.text
    assert "For arrest records of people recorded as female" not in reply.text


def test_c42_3_withdrawn_a_filter_only_figure_is_a_twin(tmp_path, monkeypatch):
    """r1 is filtered by district (9 with no district); r2 breaks down by district (1 with no
    district, hidden groups). Both figures show as fewer than 10. Changed by
    briefs/S3-R13-A-tests.md (C49; was test_c42_3_a_filter_only_figure_is_no_twin_and_the_other_
    line_is_named: r1 wrote no line, so r2's was named): both write the same text, so it is
    written once, in brackets, unnamed (point 2)."""
    specs = [(A, Y25, [D3], []), (A, Y25, [is_(SCHOOL, True)], ["district"])]
    assert [truth(*s)["left_out"]["district"] for s in specs] == [9, 1]
    env = CountyEnv(tmp_path, monkeypatch)
    reply = ask(env, Q_BREAKDOWN, specs)
    line1 = ("I counted 27 arrest records in district 3 in 2025. I counted 75 arrest records "
             "within 500 feet of a school in 2025 with a district recorded.")
    assert_reply(reply.text, line1, **expected(A, specs, line1, [left_out_line(9, "district")]))
    assert "For arrest records" not in reply.text, reply.text
