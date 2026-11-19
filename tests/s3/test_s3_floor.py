"""The floor, in code: docs/S3A-DESIGN.md C8 (applied to every result before any slot is
filled), with C12's "the floor in every place a number can appear, with 0, 1, 9 and 10
each tested" and "totals exact; the hidden line exactly when a group is hidden; left out
counted and said".

The places a number can appear, and where each of 0, 1, 9 and 10 is tested here:
- a total (the count phrase, line 1, the fixed rendering, details): 2025 near a school in
  district 4, 3, 2 and 1 has 0, 1, 9 and 10 records (the designed fixture);
- a group (the table and the groups phrase): 2025 near a school by district has groups of
  10, 9, 1 and 0 (and 24 and 31); rows made for one test give a fewest of 0, 1, 9 and 10
  and a most of 10, and a breakdown whose only group with records is 1 or 9 (too fine);
- a left-out count: 0 (2026 by district), 1 (2025 near a school by district), 9 (2025 by
  district), 10 (2024 by district; 2024 by age band, no usable age);
- a compared value: 10 against 0, 10 against 9, 1 against 0, 9 against 1;
- a share: a part of 0 and of 10 is computed; a part of 1 or 9, or a hidden whole, is
  BAD_SHARE (C8.5: no share from a hidden value);
- details: a hidden total and hidden groups are shown as `fewer than 10`;
- the floor is the source file's: with a floor of 20, values from 1 to 19 are hidden.

Also: totals stay exact (75 with two hidden groups, nothing rounded, no second group hidden),
and the hidden line comes exactly when a group is hidden.

Readings taken (kit-log/raw/S3A-A-notes.txt)
- With another floor the words follow it: `fewer than 20`, and the hidden line says
  `Counts under 20`.
- When a compared value is hidden and so is the other, or the hidden one is the highest,
  the phrase still ends after the lowest value (C6 says so for "any compared value"); it
  then says which hidden value is higher. Noted as a question for the planning chat.
- The hidden line when only a total or a left-out count is hidden: either way (see
  s3support.reply_re).
"""
import re

import pytest

from p1support import Step, finish, has_leaf, numbers_in, show_details
from s3support import (A_ID, Q_BREAKDOWN, Q_COMPARE, Q_COUNT, Q_SHARE, SCHOOL, CountyEnv,
                       age, assert_no_hidden_figure, assert_reply, check_county_reply, compare,
                       count, figures, hidden_line, hours, is_, left_out_line, age_left_out_line,
                       made_rows, run_records, sensitive_line, share, shown, source_json,
                       source_re, table_lines, truth, year)

PAGE = source_json("arrests_like")["page"]


def school_in(district):
    return [is_("district", f"district {district}"), is_(SCHOOL, True)]


def first_line_of(reply, expected):
    text = reply.text
    assert text == expected or (text.startswith(expected) and text[len(expected)] in " \n"), \
        f"line 1 is not {expected!r}:\n{text}"


# ---- a total of 0, 1, 9 and 10 --------------------------------------------------------------

TOTALS = {0: 4, 1: 3, 9: 2, 10: 1}  # the total of 2025 near a school -> its district


@pytest.mark.parametrize("total", [0, 1, 9, 10])
@pytest.mark.parametrize("style", ["agent", "fixed"])
def test_a_total_of_0_1_9_and_10(tmp_path, monkeypatch, total, style):
    """C8.1: a value from 1 to 9 is hidden (`fewer than 10`), 0 is shown as `0`, 10 is shown;
    in line 1 as the model's text fills it and in the fixed rendering (C10). The record keeps
    the exact figure (C5); the reply holds no figure from 1 to 9."""
    district = TOTALS[total]
    spec = (year(2025), school_in(district))
    assert truth("arrests_like", *spec)["total"] == total
    env = CountyEnv(tmp_path, monkeypatch, MOCO_REPLY_STYLE=style)
    reply = env.ask(Q_COUNT, Step(count(A_ID, *spec)),
                    Step(finish("finding", "I counted {r1.count}.")))
    check_county_reply(reply)
    assert reply.status == "ANSWERED" and reply.reply_style == style, (reply.reply_style,
                                                                       reply.text)
    first_line_of(reply, f"I counted {shown(total)} arrest records in district {district} "
                         f"within 500 feet of a school in 2025.")
    (record,) = run_records(reply, env.runs_dir)
    assert has_leaf(record, total), f"the exact total {total} is not in the record"


@pytest.mark.parametrize("total", [0, 1, 9, 10])
def test_details_show_a_total_as_shown(tmp_path, monkeypatch, total):
    """C8.1: the floor covers details too: a total of 1 or 9 is `fewer than 10` there."""
    spec = (year(2025), school_in(TOTALS[total]))
    env = CountyEnv(tmp_path, monkeypatch)
    env.ask(Q_COUNT, Step(count(A_ID, *spec)), Step(finish("finding", "I counted {r1.count}.")))
    # C36 point 5 (S3-R6-A): `details` goes to the model, which calls show_details
    details = env.ask("details", Step(show_details()))
    check_county_reply(details)
    assert details.status == "DETAILS", (details.status, details.reason_code, details.text)
    if 1 <= total <= 9:
        assert "fewer than 10" in details.text
    else:
        assert total in figures(details.text)
    assert_no_hidden_figure(details.text, "details")


# ---- groups of 0, 1, 9 and 10 ------------------------------------------------------------------

def test_a_breakdown_with_groups_of_0_1_9_and_10(tmp_path, monkeypatch):
    """C8.1, C8.2, C10: 2025 near a school by district: the groups 10, 9, 1, 0, 24 and 31
    are listed as 10, fewer than 10, fewer than 10, 0, 24 and 31; the total stays exact (75:
    nothing rounded, no second group hidden); one record with no district is left out and
    said as `fewer than 10`; the hidden line is added."""
    spec = (year(2025), [is_(SCHOOL, True)], ["district"])
    t = truth("arrests_like", *spec)
    assert list(t["groups"].values()) == [10, 9, 1, 0, 24, 31] and t["total"] == 75
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask(Q_BREAKDOWN, Step(count(A_ID, *spec)),
                    Step(finish("finding", "I counted {r1.count}. {r1.groups}.")))
    check_county_reply(reply)
    line1 = ("I counted 75 arrest records within 500 feet of a school in 2025 with a district "
             "recorded. By district, district 6 had the most (31) and district 4 the fewest (0).")
    table = ["district 1: 10", "district 2: fewer than 10", "district 3: fewer than 10",
             "district 4: 0", "district 5: 24", "district 6: 31"]
    assert table == table_lines(t["groups"])
    assert_reply(reply.text, line1, table=table,
                 left_out=["(fewer than 10 had no district recorded and are not included.)"],
                 hidden=hidden_line(PAGE), source=source_re("arrests_like"))


def gender_rows(female, male=30):
    """2025: `male` male records and `female` female ones (made rows; one more in 2026)."""
    return made_rows("arrests_like", (male, {}), (female, {"gender": "Female"}))


@pytest.mark.parametrize("female", [0, 1, 9, 10])
def test_a_fewest_of_0_1_9_and_10(tmp_path, monkeypatch, female):
    """C8 in the groups phrase and the table: 2025 by gender, 30 male and 0, 1, 9 or 10
    female. The hidden line comes exactly when a group is hidden (1 and 9); the sensitive
    line, because gender is a sensitive field (C10.5)."""
    rows = gender_rows(female)
    t = truth("arrests_like", year(2025), [], ["gender"], rows=rows)
    assert dict(t["groups"]) == {"female": female, "male": 30}
    env = CountyEnv(tmp_path, monkeypatch, rows={"arrests_like": rows})
    reply = env.ask(Q_BREAKDOWN, Step(count(A_ID, year(2025), [], ["gender"])),
                    Step(finish("finding", "I counted {r1.count}. {r1.groups}.")))
    check_county_reply(reply)
    line1 = (f"I counted {30 + female} arrest records in 2025. By gender, male had the most "
             f"(30) and female the fewest ({shown(female)}).")
    assert_reply(reply.text, line1, table=[f"female: {shown(female)}", "male: 30"],
                 hidden=hidden_line(PAGE) if 1 <= female <= 9 else None,
                 sensitive=sensitive_line("arrest records"), source=source_re("arrests_like"))


@pytest.mark.parametrize("groups, phrase", [
    ({"female": 10, "male": 10}, "by gender, every group had the same count (10)"),
    ({"female": 10, "male": 0}, "by gender, female had the most (10) and male the fewest (0)"),
], ids=["all equal at 10", "a most of 10 and a fewest of 0"])
def test_a_most_of_10(tmp_path, monkeypatch, groups, phrase):
    """C8: 10 is shown wherever it stands, the most included."""
    rows = made_rows("arrests_like", (groups["male"], {}), (groups["female"], {"gender": "Female"}))
    assert dict(truth("arrests_like", year(2025), [], ["gender"], rows=rows)["groups"]) == groups
    env = CountyEnv(tmp_path, monkeypatch, rows={"arrests_like": rows})
    reply = env.ask(Q_BREAKDOWN, Step(count(A_ID, year(2025), [], ["gender"])),
                    Step(finish("finding", "I counted {r1.count}. {r1.groups}.")))
    check_county_reply(reply)
    total = sum(groups.values())
    first_line_of(reply, f"I counted {total} arrest records in 2025. {phrase[0].upper()}"
                         f"{phrase[1:]}.")


@pytest.mark.parametrize("female", [1, 9])
def test_a_breakdown_whose_only_group_is_hidden_is_too_fine(tmp_path, monkeypatch, female):
    """C5 TOO_FINE with C8: when the only group with a record holds 1 or 9 (the other 0),
    every group with a record would be hidden: the most is never a hidden figure."""
    rows = made_rows("arrests_like", (female, {"gender": "Female"}))
    env = CountyEnv(tmp_path, monkeypatch, rows={"arrests_like": rows})
    reply = env.ask(Q_BREAKDOWN, Step(count(A_ID, year(2025), [], ["gender"])),
                    Step(finish("finding", "I counted {r1.count}.")))
    assert env.model.answer(0).get("error") == "TOO_FINE", env.model.answer(0)
    assert reply.run_ids == []


# ---- left out: 0, 1, 9 and 10 --------------------------------------------------------------

LEFT_OUT = {
    # id: (period, filters, group_by, line1, the left-out line or None, hidden line)
    "0 (2026 by district)": (
        year(2026), [], ["district"],
        "I counted 130 arrest records in 2026 (through 17 September 2026, the latest in this "
        "copy).", None, None),
    "1 (2025 near a school by district)": (
        year(2025), [is_(SCHOOL, True)], ["district"],
        "I counted 75 arrest records within 500 feet of a school in 2025 with a district "
        "recorded.", left_out_line(1, "district"), "always"),
    "9 (2025 by district)": (
        year(2025), [], ["district"], "I counted 231 arrest records in 2025 with a district "
        "recorded.",
        left_out_line(9, "district"), "optional"),
    "10 (2024 by district)": (
        year(2024), [], ["district"], "I counted 220 arrest records in 2024 with a district "
        "recorded.",
        left_out_line(10, "district"), None),
    "10 with no usable age (2024 by age band)": (
        year(2024), [], ["age_band"], "I counted 220 arrest records in 2024 with a usable "
        "age.",
        age_left_out_line(10), None),
    "5 with no usable age (2025 by age band)": (
        year(2025), [], ["age_band"], "I counted 235 arrest records in 2025 with a usable "
        "age.",
        age_left_out_line(5), "optional"),
    "0 with no usable age (2026 by age band)": (
        year(2026), [], ["age_band"],
        "I counted 130 arrest records in 2026 (through 17 September 2026, the latest in this "
        "copy).", None, None),
}


@pytest.mark.parametrize("case", list(LEFT_OUT))
def test_left_out_is_counted_and_said_as_shown(tmp_path, monkeypatch, case):
    """C2, C8.1 and C10.3: left out is always counted and said when anything was: `(<n> had
    no <dimension> recorded and are not included.)` or `(<n> had no usable age and are not
    included.)`, n as C8 shows it (1 and 9 hidden; 0 says nothing)."""
    period, filters, group_by, line1, left_line, hidden = LEFT_OUT[case]
    t = truth("arrests_like", period, filters, group_by)
    used = t["left_out"]["district" if "district" in group_by else "age"]
    assert (left_line is None) == (used == 0)
    groups_hidden = any(1 <= n <= 9 for n in t["groups"].values())
    assert groups_hidden == (hidden == "always")
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask(Q_BREAKDOWN, Step(count(A_ID, period, filters, group_by)),
                    Step(finish("finding", "I counted {r1.count}.")))
    check_county_reply(reply)
    assert_reply(reply.text, line1, table=table_lines(t["groups"]),
                 left_out=[left_line] if left_line else [],
                 hidden=hidden_line(PAGE) if hidden == "always" else None,
                 hidden_optional=PAGE if hidden == "optional" else None,
                 source=source_re("arrests_like"))


# ---- compared values: 0, 1, 9 and 10 ---------------------------------------------------------

COMPARES = {
    "10 and 0": (1, 4, "district 1 had the highest count (10) and district 4 the lowest (0), a "
                       "difference of 10"),
    "10 and 9": (1, 2, "district 1 had the highest count (10) and district 2 the lowest (fewer "
                       "than 10)"),
    "1 and 0": (3, 4, "district 3 had fewer than 10 and district 4 had 0"),
    "9 and 1": (2, 3, "the counts for district 2 and district 3 were each fewer than 10"),
}


@pytest.mark.parametrize("case", list(COMPARES))
def test_compared_values_of_0_1_9_and_10(tmp_path, monkeypatch, case):
    """C6 and C8.5: no difference is computed from a hidden value: when any compared value
    is hidden the phrase ends after the lowest value; 10 and 0 are shown."""
    one, two, phrase = COMPARES[case]
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask(Q_COMPARE, Step(count(A_ID, year(2025), school_in(one)),
                                    count(A_ID, year(2025), school_in(two))),
                    Step(compare("r1", "r2")),
                    Step(finish("finding", "Here is the comparison: {r3.compare}.")))
    check_county_reply(reply)
    assert reply.reply_style == "agent", (reply.draft_failures, reply.text)
    first_line_of(reply, f"Here is the comparison: {phrase}.")
    if "fewer than 10" in phrase:
        assert "difference" not in reply.text


# ---- shares: 0 and 10 computed; 1, 9 and a hidden whole refused -------------------------------

def share_turn(env, whole, part):
    return env.ask(Q_SHARE, Step(count(A_ID, *whole), count(A_ID, *part)),
                   Step(share("r2", "r1")),
                   Step(finish("finding", "Here is what I found: {r3.share}.")))


@pytest.mark.parametrize("whole, part, phrase", [
    ((year(2025), [is_(SCHOOL, True)]), (year(2025), school_in(4)),
     "0% of the 76 arrest records within 500 feet of a school in 2025 were in district 4"),
    ((year(2025), [is_(SCHOOL, True)]), (year(2025), school_in(1)),
     "13% of the 76 arrest records within 500 feet of a school in 2025 were in district 1"),
    ((year(2025), school_in(1)), (year(2025), school_in(1) + [age(None, 17)]),
     "0% of the 10 arrest records in district 1 within 500 feet of a school in 2025 were of "
     "people under 18"),
], ids=["a part of 0", "a part of 10", "a whole of 10, a part of 0"])
def test_a_share_with_0_or_10(tmp_path, monkeypatch, whole, part, phrase):
    """C7 and C8: 0 and 10 are not hidden, so the share is computed."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply = share_turn(env, whole, part)
    check_county_reply(reply)
    assert reply.reply_style == "agent", (reply.draft_failures, reply.text)
    first_line_of(reply, f"Here is what I found: {phrase}.")


@pytest.mark.parametrize("whole, part", [
    ((year(2025), [is_(SCHOOL, True)]), (year(2025), school_in(2))),
    ((year(2025), [is_(SCHOOL, True)]), (year(2025), school_in(3))),
    ((year(2025), school_in(2)), (year(2025), school_in(2) + [hours(5, 5)])),
], ids=["a part of 9", "a part of 1", "a whole of 9"])
def test_no_share_from_a_hidden_value(tmp_path, monkeypatch, whole, part):
    """C7 and C8.5: neither value hidden, else BAD_SHARE; no percentage reaches the reply."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply = share_turn(env, whole, part)
    assert env.model.answer(1).get("error") == "BAD_SHARE", env.model.answer(1)
    assert "%" not in reply.text
    assert_no_hidden_figure(reply.text, "reply")


# ---- details with hidden groups -----------------------------------------------------------------

def test_details_of_a_breakdown_hide_1_and_9_and_show_0_and_10(tmp_path, monkeypatch):
    """C8.1: the floor covers tables and details: the groups 1 and 9, and the one record
    left out, are `fewer than 10` in details; 0, 10, 24, 31 and the total 75 are shown."""
    env = CountyEnv(tmp_path, monkeypatch)
    env.ask(Q_BREAKDOWN, Step(count(A_ID, year(2025), [is_(SCHOOL, True)], ["district"])),
            Step(finish("finding", "I counted {r1.count}.")))
    # C36 point 5 (S3-R6-A): `details` goes to the model, which calls show_details
    details = env.ask("details", Step(show_details()))
    check_county_reply(details)
    assert details.status == "DETAILS", (details.status, details.reason_code, details.text)
    assert "fewer than 10" in details.text
    assert {0, 10, 24, 31, 75} <= figures(details.text)
    assert_no_hidden_figure(details.text, "details")


# ---- the floor is the source file's (C8.1) -----------------------------------------------------

def floor_20(data):
    data["floor"] = 20


def test_with_a_floor_of_20_values_from_1_to_19_are_hidden(tmp_path, monkeypatch):
    """C8.1: the floor is the source file's `floor`. With 20, 2025 by month has January
    (19), February (12) and March (19) hidden; the rest (20 and 30) shown; the total exact."""
    t = truth("arrests_like", year(2025), [], ["month"])
    env = CountyEnv(tmp_path, monkeypatch, change={"arrests_like": floor_20})
    reply = env.ask(Q_BREAKDOWN, Step(count(A_ID, year(2025), [], ["month"])),
                    Step(finish("finding", "I counted {r1.count}. {r1.groups}.")))
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    line1 = ("I counted 240 arrest records in 2025. By month, July 2025 had the most (30) and "
             "January 2025, February 2025 and March 2025 the fewest (fewer than 20 each).")
    table = [f"{label}: {shown(n, 20)}" for label, n in t["groups"].items()]
    assert table[:3] == ["January 2025: fewer than 20", "February 2025: fewer than 20",
                         "March 2025: fewer than 20"]
    hidden = re.compile(re.escape("Counts under 20 are not shown here; the county's open data "
                                  f"has every record: {PAGE}."))
    assert_reply(reply.text, line1, table=table, hidden=hidden, source=source_re("arrests_like"))
    assert not [n for n in figures(reply.text) if 1 <= n <= 19], reply.text


def test_with_a_floor_of_20_a_total_of_10_is_hidden(tmp_path, monkeypatch):
    """C8.1 with the file's floor of 20: a total of 10 is `fewer than 20`."""
    env = CountyEnv(tmp_path, monkeypatch, change={"arrests_like": floor_20})
    reply = env.ask(Q_COUNT, Step(count(A_ID, year(2025), school_in(1))),
                    Step(finish("finding", "I counted {r1.count}.")))
    first_line_of(reply, "I counted fewer than 20 arrest records in district 1 within 500 feet "
                         "of a school in 2025.")
    assert 10 not in numbers_in(reply.text.split("\n")[0])


def test_with_a_floor_of_20_a_breakdown_can_become_too_fine(tmp_path, monkeypatch):
    """C5 TOO_FINE with the file's floor: 2025 near a school by district (10, 9, 1, 0, 24,
    31) is allowed with 10 and too fine with 20 (three of five groups with records hidden)."""
    env = CountyEnv(tmp_path, monkeypatch, change={"arrests_like": floor_20})
    reply = env.ask(Q_BREAKDOWN, Step(count(A_ID, year(2025), [is_(SCHOOL, True)], ["district"])),
                    Step(finish("finding", "I counted {r1.count}.")))
    assert env.model.answer(0).get("error") == "TOO_FINE", env.model.answer(0)
    assert reply.run_ids == []
