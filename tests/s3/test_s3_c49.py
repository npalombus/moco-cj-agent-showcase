"""Stage 3 Part A, C49 (docs/S3A-DESIGN.md; D-069): the left-out line stays for a filtered field.
Withdraws C42 point 1 (C10 step 3's line is written for every field of the count that left records
out, whether the count filters on it or breaks down by it) and pins C42 point 2 with its place
(answer 2 to S3-R9-A): the same left-out text of two or more counts is written once, in brackets,
without `For <read_as>: `, where the first of those counts would have written it; C19's naming
applies to the lines that differ. Brief: briefs/S3-R13-A-tests.md. Tests only; the planning chat
builds C49. The finding it answers is DEFECT 3 of kit-log/raw/FABLE-REVIEW-OF-OPUS.md (probe
`filter_district`). All data is SYNTHETIC fixtures; no real figure is quoted. The figures are
worked out by plain counting of the fixture rows (s3support.truth); every line is written out by
hand from C10 and C19.

C49's tests:
- a count filtered by district with records of no district: the line as C10 writes it (C42's test
  that expects none is changed: tests/s3/test_s3_c42.py, listed in kit-log/raw/S3-R13-A-notes.txt);
- a count filtered by an age range with records of no usable age: the line;
- a breakdown by district: as today;
- two counts with the same left-out text: one line, at the first one's place, before a differing
  named line of a later count;
- two with different ones: C19's named lines.

READINGS (also in kit-log/raw/S3-R13-A-notes.txt):
- C49-1. C42's readings C42-2 and C42-6 stand (tests/s3/test_s3_c42.py): "the same text" is the
  line's words with the number as C8 shows it (9 and 3 are both `fewer than 10`); whole replies are
  read with s3support.reply_re.
- C49-2. "Where the first of those counts would have written it": among the reply's left-out lines,
  which run count by count in the reply's order, the once-written line stands at the place of the
  first count that has it; a later count's line of the same text adds nothing.
- C49-3. One count that left records out under two fields (one filtered, one broken down by) writes
  a line for each. C10 does not give their order: both orders are accepted (before C42 the build
  wrote the filter's first).
- C49-4. A reply whose only left-out lines are one count's, with another count or a hidden group
  beside it, names them as C19 does (C42-3's reading, now for a filter's line too).
"""
import re

import pytest

from s3support import (CountyEnv, Q_BREAKDOWN, Q_COMPARE, Q_COUNT, SCHOOL, age,
                       age_left_out_line, assert_reply, in_, is_, left_out_line, made_rows,
                       reply_re, truth, year)
from test_s3_c42 import A, C, ask, expected

Y24, Y25 = year(2024), year(2025)
D2, D3, D5 = (is_("district", f"district {n}") for n in (2, 3, 5))
FEMALE = is_("gender", "female")
STATION_1 = is_("station", "station 1")

# ==== point 1: a filtered field writes its line ==================================================

FILTERED = {
    # id: (source, period, filters, line 1, the line)
    "district 3 in 2025 (9 with no district: the review's filter_district)": (
        A, Y25, [D3], "I counted 27 arrest records in district 3 in 2025.",
        left_out_line(9, "district")),
    "district 2 in 2025 (9 with no district)": (
        A, Y25, [D2], "I counted 35 arrest records in district 2 in 2025.",
        left_out_line(9, "district")),
    "district 3 in 2024 (10 with no district)": (
        A, Y24, [D3], "I counted 45 arrest records in district 3 in 2024.",
        left_out_line(10, "district")),
    "aged 18 to 24 in 2025 (5 with no usable age)": (
        A, Y25, [age(18, 24)], "I counted 52 arrest records of people aged 18 to 24 in 2025.",
        age_left_out_line(5)),
    "aged 18 to 24 in 2024 (10 with no usable age)": (
        A, Y24, [age(18, 24)], "I counted 59 arrest records of people aged 18 to 24 in 2024.",
        age_left_out_line(10)),
    "under 18 in 2025 (5 with no usable age)": (
        A, Y25, [age(None, 17)], "I counted 31 arrest records of people under 18 in 2025.",
        age_left_out_line(5)),
    "female in 2024 (2 with no gender)": (
        A, Y24, [FEMALE], "I counted 121 arrest records of people recorded as female in 2024.",
        left_out_line(2, "gender")),
    "coded: station 1 in 2025 (6 with no station)": (
        C, Y25, [STATION_1], "I counted 60 intake records at station 1 in 2025.",
        left_out_line(6, "station")),
}
LEFT = {  # the truth's figure left out, by case (the premise)
    "district 3 in 2025 (9 with no district: the review's filter_district)": ("district", 9),
    "district 2 in 2025 (9 with no district)": ("district", 9),
    "district 3 in 2024 (10 with no district)": ("district", 10),
    "aged 18 to 24 in 2025 (5 with no usable age)": ("age", 5),
    "aged 18 to 24 in 2024 (10 with no usable age)": ("age", 10),
    "under 18 in 2025 (5 with no usable age)": ("age", 5),
    "female in 2024 (2 with no gender)": ("gender", 2),
    "coded: station 1 in 2025 (6 with no station)": ("station", 6),
}


@pytest.mark.parametrize("case", list(FILTERED))
def test_premise_the_filtered_counts_leave_records_out(case):
    name, period, filters, _, _ = FILTERED[case]
    field, n = LEFT[case]
    assert truth(name, period, filters)["left_out"] == {field: n}


@pytest.mark.parametrize("style", ["agent", "fixed"])
@pytest.mark.parametrize("case", list(FILTERED))
def test_a_filtered_field_with_records_of_no_value_writes_the_line(tmp_path, monkeypatch, case,
                                                                    style):
    name, period, filters, line1, line = FILTERED[case]
    env = CountyEnv(tmp_path, monkeypatch, names=(name,), MOCO_REPLY_STYLE=style)
    specs = [(name, period, filters, [])]
    reply = ask(env, Q_COUNT, specs)
    assert reply.reply_style == style, (reply.reply_style, reply.draft_failures)
    assert reply.text.split("\n").count(line) == 1, reply.text
    assert_reply(reply.text, line1, **expected(name, specs, line1, [line]))


def test_a_flag_filter_with_records_of_no_value_writes_the_line(tmp_path, monkeypatch):
    """Made rows: 30 near a school, 40 not, 12 with no value; the count near a school."""
    rows = made_rows(A, (30, {SCHOOL: "1"}), (40, {SCHOOL: "0"}), (12, {SCHOOL: None}))
    specs = [(A, Y25, [is_(SCHOOL, True)], [])]
    assert truth(A, Y25, [is_(SCHOOL, True)], rows=rows)["left_out"] == {SCHOOL: 12}
    env = CountyEnv(tmp_path, monkeypatch, rows={A: rows})
    reply = ask(env, Q_COUNT, specs)
    line1 = "I counted 30 arrest records within 500 feet of a school in 2025."
    line = left_out_line(12, "distance from a school")
    assert_reply(reply.text, line1, **expected(A, specs, line1, [line], rows=rows))


TWO_FIELDS = {
    # id: (period, filters, group_by, line 1, the filter's line, the breakdown's line)
    "aged 18 to 24 by district, 2025 (5 with no usable age, 3 with no district)": (
        Y25, [age(18, 24)], ["district"],
        "I counted 49 arrest records of people aged 18 to 24 in 2025 with a district recorded.",
        age_left_out_line(5), left_out_line(3, "district")),
    "district 3 by gender, 2024 (10 with no district, 1 with no gender)": (
        Y24, [D3], ["gender"],
        "I counted 44 arrest records in district 3 in 2024 with a gender recorded.",
        left_out_line(10, "district"), left_out_line(1, "gender")),
}


@pytest.mark.parametrize("case", list(TWO_FIELDS))
def test_a_filter_and_a_breakdown_each_write_their_line(tmp_path, monkeypatch, case):
    """C49-3: one count, a line for each field (either order)."""
    period, filters, group_by, line1, filtered, broken = TWO_FIELDS[case]
    env = CountyEnv(tmp_path, monkeypatch)
    specs = [(A, period, filters, group_by)]
    reply = ask(env, Q_BREAKDOWN, specs)
    patterns = [reply_re(line1, **expected(A, specs, line1, block))
                for block in ([filtered, broken], [broken, filtered])]
    assert any(re.fullmatch(p, reply.text) for p in patterns), \
        f"not the expected county reply (either order).\n--- got ---\n{reply.text}"


BREAKDOWNS = {
    # id: (period, filters, group_by, line 1, the line)
    "2025 by district (9 with no district)": (
        Y25, [], ["district"], "I counted 231 arrest records in 2025 with a district recorded.",
        left_out_line(9, "district")),
    "district 3 and district 4, by district (filtered and broken down by)": (
        Y25, [in_("district", "district 3", "district 4")], ["district"],
        "I counted 53 arrest records in district 3 and district 4 in 2025 with a district "
        "recorded.", left_out_line(9, "district")),
}


@pytest.mark.parametrize("case", list(BREAKDOWNS))
def test_a_breakdown_by_district_is_as_today(tmp_path, monkeypatch, case):
    period, filters, group_by, line1, line = BREAKDOWNS[case]
    env = CountyEnv(tmp_path, monkeypatch)
    specs = [(A, period, filters, group_by)]
    reply = ask(env, Q_BREAKDOWN, specs)
    assert_reply(reply.text, line1, **expected(A, specs, line1, [line]))


# ==== point 2: the same text once, at the first one's place ======================================

SAME_ONCE = left_out_line(9, "district")   # `(fewer than 10 had no district recorded ...)`


def test_the_live_run_n28_two_counts_filtered_by_district_one_line(tmp_path, monkeypatch):
    """N28 of live round 13: district 2 and district 5 in 2025, 9 with no district for each: the
    line once, in brackets, unnamed (was: no line, C42 point 1; before C42: two named lines)."""
    specs = [(A, Y25, [D2], []), (A, Y25, [D5], [])]
    assert [truth(*s)["left_out"] for s in specs] == [{"district": 9}] * 2
    env = CountyEnv(tmp_path, monkeypatch)
    reply = ask(env, Q_COMPARE, specs)
    line1 = ("I counted 35 arrest records in district 2 in 2025. I counted 50 arrest records in "
             "district 5 in 2025.")
    assert reply.text.split("\n").count(SAME_ONCE) == 1, reply.text
    assert "For arrest records" not in reply.text, reply.text
    assert_reply(reply.text, line1, **expected(A, specs, line1, [SAME_ONCE]))


def test_two_age_filters_with_the_same_text_one_line(tmp_path, monkeypatch):
    """Under 18 and 18 to 24 in 2025, 5 with no usable age each: the age line once."""
    specs = [(A, Y25, [age(None, 17)], []), (A, Y25, [age(18, 24)], [])]
    assert [truth(*s)["left_out"] for s in specs] == [{"age": 5}] * 2
    env = CountyEnv(tmp_path, monkeypatch)
    reply = ask(env, Q_COMPARE, specs)
    line1 = ("I counted 31 arrest records of people under 18 in 2025. I counted 52 arrest records "
             "of people aged 18 to 24 in 2025.")
    assert_reply(reply.text, line1, **expected(A, specs, line1, [age_left_out_line(5)]))


ORDERED = {
    # id: (the counts, line 1, the left-out lines in order)
    "the same two first, then a differing later count (the contract's case)": (
        [(A, Y25, [D2], []), (A, Y25, [D5], []), (A, Y24, [D3], [])],
        "I counted 35 arrest records in district 2 in 2025. I counted 50 arrest records in "
        "district 5 in 2025. I counted 45 arrest records in district 3 in 2024.",
        [SAME_ONCE,
         "For arrest records in district 3 in 2024: 10 had no district recorded and are not "
         "included."]),
    "a differing first count, then the same two": (
        [(A, Y24, [D3], []), (A, Y25, [D2], []), (A, Y25, [D5], [])],
        "I counted 45 arrest records in district 3 in 2024. I counted 35 arrest records in "
        "district 2 in 2025. I counted 50 arrest records in district 5 in 2025.",
        ["For arrest records in district 3 in 2024: 10 had no district recorded and are not "
         "included.", SAME_ONCE]),
    "the same two around a differing one": (
        [(A, Y25, [D2], []), (A, Y24, [D3], []), (A, Y25, [D5], [])],
        "I counted 35 arrest records in district 2 in 2025. I counted 45 arrest records in "
        "district 3 in 2024. I counted 50 arrest records in district 5 in 2025.",
        [SAME_ONCE,
         "For arrest records in district 3 in 2024: 10 had no district recorded and are not "
         "included."]),
    "a filter's figure and a breakdown's of the same text, then a differing one": (
        [(A, Y25, [D3], []), (A, Y25, [], ["district"]), (A, Y24, [], ["district"])],
        "I counted 27 arrest records in district 3 in 2025. I counted 231 arrest records in "
        "2025 with a district recorded. I counted 220 arrest records in 2024 with a district "
        "recorded.",
        [SAME_ONCE,
         "For arrest records in 2024: 10 had no district recorded and are not included."]),
}


def test_premise_the_ordered_cases():
    figures = {case: [truth(*s)["left_out"]["district"] for s in specs]
               for case, (specs, _, _) in ORDERED.items()}
    assert list(figures.values()) == [[9, 9, 10], [10, 9, 9], [9, 10, 9], [9, 9, 10]], figures


@pytest.mark.parametrize("case", list(ORDERED))
def test_the_same_text_once_at_the_first_ones_place_and_the_differing_one_named(tmp_path,
                                                                                monkeypatch,
                                                                                case):
    specs, line1, lines = ORDERED[case]
    env = CountyEnv(tmp_path, monkeypatch)
    reply = ask(env, Q_COMPARE, specs)
    assert reply.text.split("\n").count(SAME_ONCE) == 1, reply.text
    assert "For arrest records in district 2" not in reply.text
    assert "For arrest records in district 5" not in reply.text
    assert_reply(reply.text, line1, **expected(A, specs, line1, lines))


def test_a_filters_figure_is_a_twin_of_a_breakdowns(tmp_path, monkeypatch):
    """r1 filtered by district 3 (9 with no district), r2 near a school by district (1 with no
    district, hidden groups): both `fewer than 10`, so one line, unnamed (was C42-3's named line
    of r2 alone)."""
    specs = [(A, Y25, [D3], []), (A, Y25, [is_(SCHOOL, True)], ["district"])]
    assert [truth(*s)["left_out"] for s in specs] == [{"district": 9},
                                                      {SCHOOL: 0, "district": 1}]
    env = CountyEnv(tmp_path, monkeypatch)
    reply = ask(env, Q_BREAKDOWN, specs)
    line1 = ("I counted 27 arrest records in district 3 in 2025. I counted 75 arrest records "
             "within 500 feet of a school in 2025 with a district recorded.")
    assert "For arrest records" not in reply.text, reply.text
    assert_reply(reply.text, line1, **expected(A, specs, line1, [SAME_ONCE]))


DIFFERENT = {
    # id: (the counts, line 1, the named lines in order)
    "district 3 in 2025 and in 2024 (fewer than 10, and 10)": (
        [(A, Y25, [D3], []), (A, Y24, [D3], [])],
        "I counted 27 arrest records in district 3 in 2025. I counted 45 arrest records in "
        "district 3 in 2024.",
        ["For arrest records in district 3 in 2025: fewer than 10 had no district recorded and "
         "are not included.",
         "For arrest records in district 3 in 2024: 10 had no district recorded and are not "
         "included."]),
    "aged 18 to 24 in 2024 and in 2025 (10, and fewer than 10)": (
        [(A, Y24, [age(18, 24)], []), (A, Y25, [age(18, 24)], [])],
        "I counted 59 arrest records of people aged 18 to 24 in 2024. I counted 52 arrest records "
        "of people aged 18 to 24 in 2025.",
        ["For arrest records of people aged 18 to 24 in 2024: 10 had no usable age and are not "
         "included.",
         "For arrest records of people aged 18 to 24 in 2025: fewer than 10 had no usable age "
         "and are not included."]),
    "a filter's line and a breakdown's of another field (district, and gender)": (
        [(A, Y24, [D3], []), (A, Y24, [], ["gender"])],
        "I counted 45 arrest records in district 3 in 2024. I counted 228 arrest records in 2024 "
        "with a gender recorded.",
        ["For arrest records in district 3 in 2024: 10 had no district recorded and are not "
         "included.",
         "For arrest records in 2024: fewer than 10 had no gender recorded and are not "
         "included."]),
}


@pytest.mark.parametrize("case", list(DIFFERENT))
def test_two_counts_with_different_lines_are_named_as_c19_names_them(tmp_path, monkeypatch, case):
    specs, line1, named = DIFFERENT[case]
    env = CountyEnv(tmp_path, monkeypatch)
    reply = ask(env, Q_COMPARE, specs)
    assert_reply(reply.text, line1, **expected(A, specs, line1, named))
