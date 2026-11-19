"""The phrases Python writes: docs/S3A-DESIGN.md C6, and C12's "every phrase of C6 exactly,
including each age fragment, two person filters, a tie, all equal, a period cut to the
copy, `under 1`, and a hidden value in each place". Every expected phrase below is written
out by hand from C6, with the numbers of the truth (s3support.truth, plain counting; each
number was checked against it when the test was written, and the tests that need it check
it again).

What this file covers, through the reply's line 1 (a passing finding is filled with the
phrases: R1's fill, a capital letter at the start of a sentence):
- `{rN.count}`: `<total> <unit> <what> <period>`: no filter; each age fragment (`aged 18
  to 21`, `aged 30 and over`, `under 18`, `aged 21`); one, two and three person filters,
  in file order whatever order the spec gives; a category with two and three labels; a
  place category; a flag, yes and no; weekends, weekdays, other days; hours over midnight
  and in the afternoon; every part at once in C6's order; each kind of period; a period cut
  to the copy (and one that ends on the newest record's day, not cut); the comma from
  1,000; a hidden total (1 and 9) and the totals 0 and 10; the coded fixture's own unit and
  labels.
- `{rN.groups}`: one most and one fewest; a tie for the most; a tie for both; every group
  equal; a fewest of 0 and a fewest that is hidden; every group 0; each kind of dimension
  (district, distance from a school, age band, year, month, day of the week, hour, race,
  station); a comma; the phrase inside a sentence (no capital).
- `{rN.share}`: a flag, an age, a place and two person filters as the part; a whole with
  filters; `under 1`; 100.
- `{rN.compare}`: labels that are years, districts, ages and person categories; a tie;
  all equal; a hidden value (the phrase ends after the lowest value).
- replies.slot_phrases gives these phrases for county results.

Readings taken (kit-log/raw/S3A-A-notes.txt)
- A cut period keeps the words of the period asked for, then ` (through <newest day>, the
  latest in this copy)`: `in 2026 (through 17 September 2026, the latest in this copy)`.
  A period that ends on the newest record's day is not cut.
- The groups of a period cut to the copy are the periods up to the newest record (2026 by
  month is January to September 2026).
- A hidden total takes the unit's `many` (`fewer than 10 arrest records`); with a floor of
  10 a total of 1 is always hidden, so `one` never shows.
- Ties are listed in the order of the groups (file order, or time order), as the months
  sentence lists tied months in calendar order.
- The compare label of a person filter is `people <fragment>` (`people aged 18 to 21`, so
  `people recorded as female`).
- Days named in a weekday filter are written in the order given (the tests give them in
  calendar order).
- slot_phrases(result, registry) for a county result gives a dict keyed by the slot's name
  (`count` and `groups`; `share`; `compare`), as it does today.
"""
import pytest

from p1support import Step, finish, mod
from s3support import (A_ID, C_ID, Q_BREAKDOWN, Q_COMPARE, Q_COUNT, Q_SHARE, SCHOOL, CountyEnv,
                       age, bulk_rows, compare, count, dates, fixture_rows, hours, in_, is_,
                       months, share, truth, weekdays, year, years)

THROUGH_A = " (through 17 September 2026, the latest in this copy)"
THROUGH_C = " (through 20 August 2026, the latest in this copy)"


def assert_line1(reply, expected):
    """Line 1 of the reply is exactly `expected`; what Python adds comes after a space or a
    line break (C10)."""
    text = reply.text
    ok = text == expected or (text.startswith(expected) and text[len(expected)] in " \n")
    assert ok, f"line 1 is not as C6 writes it.\n--- got ---\n{text}\n--- expected ---\n{expected}"


def one_count(tmp_path, monkeypatch, name, period, filters=(), group_by=(), *, text, rows=None):
    env = CountyEnv(tmp_path, monkeypatch, names=(name,),
                    rows=None if rows is None else {name: rows})
    sid = A_ID if name == "arrests_like" else C_ID
    reply = env.ask(Q_BREAKDOWN if group_by else Q_COUNT,
                    Step(count(sid, period, list(filters), list(group_by))),
                    Step(finish("finding", text)))
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert reply.reply_style == "agent", (reply.draft_failures, reply.text)
    return env, reply


# ---- the count phrase -----------------------------------------------------------------------

COUNT_PHRASES = {
    # id: (fixture, period, filters, the count phrase)
    "no filter": ("arrests_like", year(2025), [], "240 arrest records in 2025"),
    "aged 18 to 21": ("arrests_like", year(2025), [age(18, 21)],
                      "30 arrest records of people aged 18 to 21 in 2025"),
    "aged 30 and over": ("arrests_like", year(2025), [age(30)],
                         "133 arrest records of people aged 30 and over in 2025"),
    "under 18": ("arrests_like", year(2025), [age(None, 17)],
                 "31 arrest records of people under 18 in 2025"),
    "aged 21": ("arrests_like", year(2025), [age(21, 21)],
                "12 arrest records of people aged 21 in 2025"),
    "a person category alone": ("arrests_like", year(2025), [is_("gender", "female")],
                                "100 arrest records of people recorded as female in 2025"),
    "two person filters": ("arrests_like", year(2025), [age(18, 21), is_("gender", "female")],
                           "16 arrest records of people aged 18 to 21, recorded as female in "
                           "2025"),
    "three person filters, given backwards": (
        "arrests_like", year(2025),
        [is_("race", "group Alpha"), is_("gender", "female"), age(18, 21)],
        "fewer than 10 arrest records of people aged 18 to 21, recorded as female, recorded as "
        "group Alpha in 2025"),
    "the contract's example": (
        "arrests_like", year(2025),
        [age(18, 21), is_("gender", "female"), is_("district", "district 3")],
        "fewer than 10 arrest records of people aged 18 to 21, recorded as female in district 3 "
        "in 2025"),
    "a person and a place, given place first": (
        "arrests_like", year(2025), [is_("district", "district 3"), is_("gender", "female")],
        "14 arrest records of people recorded as female in district 3 in 2025"),
    "two labels": ("arrests_like", year(2025), [in_("race", "group Alpha", "group Beta")],
                   "120 arrest records of people recorded as group Alpha and group Beta in 2025"),
    "two districts": ("arrests_like", year(2025), [in_("district", "district 3", "district 4")],
                      "53 arrest records in district 3 and district 4 in 2025"),
    "three districts": ("arrests_like", year(2025),
                        [in_("district", "district 1", "district 2", "district 3")],
                        "98 arrest records in district 1, district 2 and district 3 in 2025"),
    "a flag": ("arrests_like", year(2025), [is_(SCHOOL, True)],
               "76 arrest records within 500 feet of a school in 2025"),
    "a flag, no": ("arrests_like", year(2025), [is_(SCHOOL, False)],
                   "164 arrest records not within 500 feet of a school in 2025"),
    "weekends": ("arrests_like", year(2025), [weekdays("Saturday", "Sunday")],
                 "79 arrest records on weekends in 2025"),
    "weekends, Sunday first": ("arrests_like", year(2025), [weekdays("Sunday", "Saturday")],
                               "79 arrest records on weekends in 2025"),
    "weekdays": ("arrests_like", year(2025),
                 [weekdays("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")],
                 "161 arrest records on weekdays in 2025"),
    "Monday and Friday": ("arrests_like", year(2025), [weekdays("Monday", "Friday")],
                          "68 arrest records on Monday and Friday in 2025"),
    "hours over midnight": ("arrests_like", year(2025), [hours(22, 5)],
                            "84 arrest records between 10 pm and 5 am in 2025"),
    "afternoon hours": ("arrests_like", year(2025), [hours(13, 15)],
                        "30 arrest records between 1 pm and 3 pm in 2025"),
    "every part at once, in C6's order": (
        "arrests_like", year(2025),
        [hours(22, 5), weekdays("Saturday", "Sunday"), is_(SCHOOL, False),
         is_("district", "district 5"), is_("gender", "male"), age(25)],
        "0 arrest records of people aged 25 and over, recorded as male in district 5 not "
        "within 500 feet of a school on weekends between 10 pm and 5 am in 2025"),
    "two years": ("arrests_like", years(2024, 2025), [], "470 arrest records in 2024 and 2025"),
    "months of a year": ("arrests_like", months(2025, 1, 10), [],
                         "200 arrest records from January to October 2025"),
    "a date range": ("arrests_like", dates("2025-03-01", "2025-08-31"), [],
                     "129 arrest records from 1 March 2025 to 31 August 2025"),
    "a year cut to the copy": ("arrests_like", year(2026), [],
                               "130 arrest records in 2026" + THROUGH_A),
    "two years cut to the copy": ("arrests_like", years(2025, 2026), [],
                                  "370 arrest records in 2025 and 2026" + THROUGH_A),
    "months cut to the copy": ("arrests_like", months(2026, 1, 12), [],
                               "130 arrest records from January to December 2026" + THROUGH_A),
    "dates cut to the copy": ("arrests_like", dates("2026-06-01", "2026-12-31"), [],
                              "56 arrest records from 1 June 2026 to 31 December 2026"
                              + THROUGH_A),
    "dates ending on the newest record's day (not cut)": (
        "arrests_like", dates("2026-01-01", "2026-09-17"), [],
        "130 arrest records from 1 January 2026 to 17 September 2026"),
    "a hidden total of 1": ("arrests_like", year(2025),
                            [is_("district", "district 3"), is_(SCHOOL, True)],
                            "fewer than 10 arrest records in district 3 within 500 feet of a "
                            "school in 2025"),
    "a hidden total of 9": ("arrests_like", year(2025),
                            [is_("district", "district 2"), is_(SCHOOL, True)],
                            "fewer than 10 arrest records in district 2 within 500 feet of a "
                            "school in 2025"),
    "a total of 0": ("arrests_like", year(2025), [is_("district", "district 4"), is_(SCHOOL, True)],
                     "0 arrest records in district 4 within 500 feet of a school in 2025"),
    "a total of 10": ("arrests_like", year(2025), [is_("district", "district 1"), is_(SCHOOL, True)],
                      "10 arrest records in district 1 within 500 feet of a school in 2025"),
    "coded: no filter": ("coded_like", year(2025), [], "200 intake records in 2025"),
    "coded: two spellings, one label": ("coded_like", year(2025), [is_("race_code", "group W")],
                                        "90 intake records of people recorded as group W in 2025"),
    "coded: its own wording": ("coded_like", year(2025), [is_("station", "station 3")],
                               "55 intake records at station 3 in 2025"),
    "coded: two person filters in file order": (
        "coded_like", year(2025), [is_("sex", "female"), is_("race_code", "group W")],
        "42 intake records of people recorded as group W, recorded as female in 2025"),
    "coded: under 18": ("coded_like", year(2025), [age(None, 17, "age_years")],
                        "51 intake records of people under 18 in 2025"),
    "coded: a year cut to the copy": ("coded_like", year(2026), [],
                                      "100 intake records in 2026" + THROUGH_C),
}


@pytest.mark.parametrize("case", list(COUNT_PHRASES))
def test_the_count_phrase(tmp_path, monkeypatch, case):
    """C6 `{rN.count}`: `<total> <unit> <what> <period>`, parts separated by one space."""
    name, period, filters, phrase = COUNT_PHRASES[case]
    t = truth(name, period, filters)
    expected_total = phrase.split(" arrest records")[0].split(" intake records")[0]
    shown_total = "fewer than 10" if 1 <= t["total"] <= 9 else f"{t['total']:,}"
    assert expected_total == shown_total, f"the test's own total is not the truth's: {t}"
    env, reply = one_count(tmp_path, monkeypatch, name, period, filters,
                           text="I counted {r1.count}.")
    assert_line1(reply, f"I counted {phrase}.")


def test_a_total_from_1000_has_a_comma(tmp_path, monkeypatch):
    """C6: numbers have a comma from 1,000 up. 1,000 more made-up rows in 2025."""
    rows = fixture_rows("arrests_like") + bulk_rows("arrests_like", 1000)
    assert truth("arrests_like", year(2025), rows=rows)["total"] == 1240
    env, reply = one_count(tmp_path, monkeypatch, "arrests_like", year(2025),
                           text="I counted {r1.count}.", rows=rows)
    assert_line1(reply, "I counted 1,240 arrest records in 2025.")


def test_the_count_phrase_takes_a_capital_at_the_start_of_a_sentence(tmp_path, monkeypatch):
    """R1's fill, unchanged: a slot that starts a sentence gets a capital first letter (here
    the hidden total's `fewer`)."""
    env, reply = one_count(tmp_path, monkeypatch, "arrests_like", year(2025),
                           [is_("district", "district 3"), is_(SCHOOL, True)],
                           text="{r1.count}.")
    assert_line1(reply, "Fewer than 10 arrest records in district 3 within 500 feet of a school "
                        "in 2025.")


# ---- the groups phrase ---------------------------------------------------------------------------

GROUPS_PHRASES = {
    # id: (fixture, period, filters, group_by, the count phrase, the groups phrase)
    "a tie for the most": (
        "arrests_like", year(2024), [], ["district"],
        "220 arrest records in 2024 with a district recorded",
        "by district, district 2 and district 3 had the most (45 each) and district 6 the "
        "fewest (20)"),
    "a tie for both": (
        "arrests_like", year(2026), [], ["district"], "130 arrest records in 2026" + THROUGH_A,
        "by district, district 1 and district 2 had the most (25 each) and district 3, "
        "district 4, district 5 and district 6 the fewest (20 each)"),
    "every group equal": (
        "arrests_like", year(2026), [], ["gender"], "130 arrest records in 2026" + THROUGH_A,
        "by gender, every group had the same count (65)"),
    "a fewest of 0": (
        "arrests_like", year(2025), [is_(SCHOOL, True)], ["district"],
        "75 arrest records within 500 feet of a school in 2025 with a district recorded",
        "by district, district 6 had the most (31) and district 4 the fewest (0)"),
    "a hidden fewest": (
        "arrests_like", year(2026), [], ["ethnicity"], "130 arrest records in 2026" + THROUGH_A,
        "by ethnicity, not Hispanic had the most (125) and Hispanic the fewest (fewer than 10)"),
    "every group 0": (
        "arrests_like", year(2025), [is_("district", "district 4"), is_(SCHOOL, True)], ["gender"],
        "0 arrest records in district 4 within 500 feet of a school in 2025",
        "by gender, every group had the same count (0)"),
    "a flag": (
        "arrests_like", year(2025), [], [SCHOOL], "240 arrest records in 2025",
        "by distance from a school, not within 500 feet of a school had the most (164) and "
        "within 500 feet of a school the fewest (76)"),
    "age bands": (
        "arrests_like", year(2025), [], ["age_band"],
        "235 arrest records in 2025 with a usable age",
        "by age band, ages 18 to 24 had the most (52) and ages 45 to 54 the fewest (24)"),
    "years": (
        "arrests_like", years(2024, 2025), [], ["year"], "470 arrest records in 2024 and 2025",
        "by year, 2025 had the most (240) and 2024 the fewest (230)"),
    "months": (
        "arrests_like", year(2025), [], ["month"], "240 arrest records in 2025",
        "by month, July 2025 had the most (30) and February 2025 the fewest (12)"),
    "months of a year cut to the copy": (
        "arrests_like", year(2026), [], ["month"], "130 arrest records in 2026" + THROUGH_A,
        "by month, July 2026 had the most (26) and September 2026 the fewest (fewer than 10)"),
    "days of the week": (
        "arrests_like", year(2025), [], ["weekday"], "240 arrest records in 2025",
        "by day of the week, Saturday had the most (45) and Tuesday the fewest (25)"),
    "hours": (
        "arrests_like", year(2025), [], ["hour"], "240 arrest records in 2025",
        "by hour, 10 pm had the most (25) and 5 am the fewest (0)"),
    "coded: two spellings in one group, a tie": (
        "coded_like", year(2025), [], ["race_code"], "200 intake records in 2025",
        "by race, group W and group B had the most (90 each) and group U the fewest (20)"),
    "coded: stations": (
        "coded_like", year(2025), [], ["station"],
        "194 intake records in 2025 with a station recorded",
        "by station, station 2 had the most (79) and station 3 the fewest (55)"),
}


@pytest.mark.parametrize("case", list(GROUPS_PHRASES))
def test_the_groups_phrase(tmp_path, monkeypatch, case):
    """C6 `{rN.groups}`: `by <dimension>, <top> had the most (<n>) and <bottom> the fewest
    (<n>)`; ties as the months sentence writes them; all equal: `by <dimension>, every
    group had the same count (<n>)`. Groups are every value the file lists (or every period
    in the range), including those with 0. A capital after a sentence end (R1's fill)."""
    name, period, filters, group_by, count_phrase, groups_phrase = GROUPS_PHRASES[case]
    t = truth(name, period, filters, group_by)
    assert count_phrase.startswith(f"{t['total']:,} "), (count_phrase, t["total"])
    env, reply = one_count(tmp_path, monkeypatch, name, period, filters, group_by,
                           text="I counted {r1.count}. {r1.groups}.")
    assert_line1(reply, f"I counted {count_phrase}. {groups_phrase[0].upper()}{groups_phrase[1:]}.")


def test_the_groups_phrase_inside_a_sentence_and_with_a_comma(tmp_path, monkeypatch):
    """C6: a comma from 1,000 up in the groups phrase too; inside a sentence the phrase is
    used as written (no capital). 1,000 more made-up rows in district 5 in 2025."""
    rows = fixture_rows("arrests_like") + bulk_rows("arrests_like", 1000)
    t = truth("arrests_like", year(2025), [], ["district"], rows=rows)
    assert t["total"] == 1231 and t["groups"]["district 5"] == 1050
    env, reply = one_count(tmp_path, monkeypatch, "arrests_like", year(2025), [], ["district"],
                           text="I counted {r1.count}, and {r1.groups}.", rows=rows)
    assert_line1(reply, "I counted 1,231 arrest records in 2025 with a district recorded, and by "
                        "district, district 5 had the most (1,050) and district 4 the fewest "
                        "(26).")


# ---- the share phrase -----------------------------------------------------------------------------

SHARE_PHRASES = {
    # id: (whole spec, part spec, the share phrase); both specs (period, filters)
    "a flag": ((year(2025), []), (year(2025), [is_(SCHOOL, True)]),
               "32% of the 240 arrest records in 2025 were within 500 feet of a school"),
    "an age": ((year(2025), []), (year(2025), [age(None, 17)]),
               "13% of the 240 arrest records in 2025 were of people under 18"),
    "a place": ((year(2025), []), (year(2025), [is_("district", "district 3")]),
                "11% of the 240 arrest records in 2025 were in district 3"),
    "two person filters": ((year(2025), []),
                           (year(2025), [age(18, 21), is_("gender", "female")]),
                           "7% of the 240 arrest records in 2025 were of people aged 18 to 21, "
                           "recorded as female"),
    "a whole with a filter": ((year(2025), [is_(SCHOOL, True)]),
                              (year(2025), [is_(SCHOOL, True), is_("district", "district 1")]),
                              "13% of the 76 arrest records within 500 feet of a school in 2025 "
                              "were in district 1"),
    "100": ((year(2025), []), (year(2025), [in_("gender", "female", "male")]), None),
}


def share_turn(tmp_path, monkeypatch, whole, part, text="Here is what I found: {r3.share}.",
               rows=None):
    env = CountyEnv(tmp_path, monkeypatch, rows=None if rows is None else {"arrests_like": rows})
    reply = env.ask(Q_SHARE, Step(count(A_ID, *whole), count(A_ID, *part)),
                    Step(share("r2", "r1")), Step(finish("finding", text)))
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert reply.reply_style == "agent", (reply.draft_failures, reply.text)
    return env, reply


@pytest.mark.parametrize("case", [c for c in SHARE_PHRASES if SHARE_PHRASES[c][2]])
def test_the_share_phrase(tmp_path, monkeypatch, case):
    """C6 `{rN.share}`: `<p>% of the <whole's count phrase> were <part>`, `<part>` the
    `<what>` of the filters the part adds; `<p>` the nearest whole number."""
    whole, part, phrase = SHARE_PHRASES[case]
    w, p = truth("arrests_like", *whole)["total"], truth("arrests_like", *part)["total"]
    assert phrase.startswith(f"{round(100 * p / w)}% of the {w} "), (phrase, p, w)
    env, reply = share_turn(tmp_path, monkeypatch, whole, part)
    assert_line1(reply, f"Here is what I found: {phrase}.")


def test_a_share_of_100(tmp_path, monkeypatch):
    """C6: every record of 2025 is recorded as female or male: 100%."""
    whole, part, _ = SHARE_PHRASES["100"]
    assert truth("arrests_like", *whole)["total"] == truth("arrests_like", *part)["total"] == 240
    env, reply = share_turn(tmp_path, monkeypatch, whole, part)
    assert_line1(reply, "Here is what I found: 100% of the 240 arrest records in 2025 were of "
                        "people recorded as female and male.")


def test_a_share_above_0_and_below_half_a_percent_is_under_1(tmp_path, monkeypatch):
    """C6: above 0 and below 0.5 it is written `under 1`. 2,000 more made-up rows in 2025
    (none near a school, none in district 1): 10 of 2,240 is about 0.45 in 100. As the first
    thing of the text it takes a capital (R1's fill)."""
    rows = fixture_rows("arrests_like") + bulk_rows("arrests_like", 2000)
    whole = (year(2025), [])
    part = (year(2025), [is_("district", "district 1"), is_(SCHOOL, True)])
    assert truth("arrests_like", *whole, rows=rows)["total"] == 2240
    assert truth("arrests_like", *part, rows=rows)["total"] == 10
    env, reply = share_turn(tmp_path, monkeypatch, whole, part, text="{r3.share}.", rows=rows)
    assert_line1(reply, "Under 1% of the 2,240 arrest records in 2025 were in district 1 within "
                        "500 feet of a school.")


# ---- the compare phrase ------------------------------------------------------------------------------

COMPARE_PHRASES = {
    # id: (spec 1, spec 2, the compare phrase); specs (period, filters)
    "years": ((year(2024), []), (year(2025), []),
              "2025 had the highest count (240) and 2024 the lowest (230), a difference of 10"),
    "districts": ((year(2024), [is_("district", "district 3")]),
                  (year(2024), [is_("district", "district 4")]),
                  "district 3 had the highest count (45) and district 4 the lowest (35), a "
                  "difference of 10"),
    "ages": ((year(2025), [age(18, 21)]), (year(2025), [age(30)]),
             "people aged 30 and over had the highest count (133) and people aged 18 to 21 the "
             "lowest (30), a difference of 103"),
    "all equal": ((year(2026), [is_("gender", "female")]), (year(2026), [is_("gender", "male")]),
                  "the counts were the same (65) for people recorded as female and people "
                  "recorded as male"),
    "a hidden value": ((year(2025), [is_("district", "district 1"), is_(SCHOOL, True)]),
                       (year(2025), [is_("district", "district 2"), is_(SCHOOL, True)]),
                       "district 1 had the highest count (10) and district 2 the lowest (fewer "
                       "than 10)"),
}


@pytest.mark.parametrize("case", list(COMPARE_PHRASES))
def test_the_compare_phrase(tmp_path, monkeypatch, case):
    """C6 `{rN.compare}`: as R1 writes it, each result's label the part of its count phrase
    on which the compared specs differ; with a hidden value the phrase ends after the lowest
    value and states no difference."""
    one, two, phrase = COMPARE_PHRASES[case]
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask(Q_COMPARE, Step(count(A_ID, *one), count(A_ID, *two)),
                    Step(compare("r1", "r2")),
                    Step(finish("finding", "Here is the comparison: {r3.compare}.")))
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert reply.reply_style == "agent", (reply.draft_failures, reply.text)
    assert_line1(reply, f"Here is the comparison: {phrase}.")


def test_the_compare_phrase_with_a_tie_and_a_capital(tmp_path, monkeypatch):
    """C6 with A6's ties: labels that tie are joined; at the start of the text the phrase
    takes a capital. 2026: district 1 and district 2 have 25 each, district 3 has 20."""
    specs = [(year(2026), [is_("district", f"district {d}")]) for d in (1, 2, 3)]
    assert [truth("arrests_like", *s)["total"] for s in specs] == [25, 25, 20]
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask(Q_COMPARE, Step(*[count(A_ID, *s) for s in specs]),
                    Step(compare("r1", "r2", "r3")),
                    Step(finish("finding", "{r4.compare}.")))
    assert reply.reply_style == "agent", (reply.draft_failures, reply.text)
    assert_line1(reply, "District 1 and district 2 had the highest count (25) and district 3 "
                        "the lowest (20), a difference of 5.")


# ---- replies.slot_phrases (C6) -----------------------------------------------------------------

def test_slot_phrases_gives_the_phrases_of_county_results(tmp_path, monkeypatch):
    """C6: `replies.slot_phrases` gives these for county results: the count and groups
    phrases of a one-way breakdown, the count phrase alone of a single count, the share
    phrase and the compare phrase."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask(Q_SHARE, Step(count(A_ID, year(2025), [], ["district"]),
                                  count(A_ID, year(2025), [is_(SCHOOL, True)], ["district"])),
                    Step(count(A_ID, year(2025)), count(A_ID, year(2025), [is_(SCHOOL, True)]),
                         count(A_ID, year(2024))),
                    Step(share("r4", "r3"), compare("r5", "r3")),
                    Step(finish("finding", "I counted {r1.count}. {r1.groups}.")))
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert len(reply.results) == 7, reply.results
    replies = mod("replies")
    phrases = [replies.slot_phrases(result, env.registry) for result in reply.results]
    assert phrases == [
        {"count": "231 arrest records in 2025 with a district recorded",
         "groups": "by district, district 6 had the most (57) and district 4 the fewest (26)"},
        {"count": "75 arrest records within 500 feet of a school in 2025 with a district "
                  "recorded",
         "groups": "by district, district 6 had the most (31) and district 4 the fewest (0)"},
        {"count": "240 arrest records in 2025"},
        {"count": "76 arrest records within 500 feet of a school in 2025"},
        {"count": "230 arrest records in 2024"},
        {"share": "32% of the 240 arrest records in 2025 were within 500 feet of a school"},
        {"compare": "2025 had the highest count (240) and 2024 the lowest (230), a difference "
                    "of 10"},
    ]
