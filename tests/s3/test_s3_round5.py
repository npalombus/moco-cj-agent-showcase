"""Stage 3 Part A, round 5: docs/S3A-DESIGN.md C21 ("Under 18, inside one turn", approved by
Nino, D-059), C25 ("The period question when no source is known") and C26 to C28 ("Three
things the live run of 13 November showed"). Brief: briefs/S3A-R5-A-tests.md.

What this file shows, through turns with the model stand-in (the FakeModel of
tests/p1/p1support.py) on the SYNTHETIC fixtures only:

C21. Refused, with NOT_ALLOWED, the age field and C21's `why` word for word: every example C21
     lists as refused, and pairs, triples and a four-count chain of this file's own (the year
     at the top of a range, at the bottom, one range inside the other, the wider count first
     and the narrower first, the year in the middle of three counts, one count refused on its
     own figures by `age_band`, a group of a category or of a flag against a filtered count, a
     period written two ways, another filter the same on both sides). Allowed, answered as
     today: every example C21 lists as allowed, and more (a failed count, a refused count and
     a C5 refusal are not counts of the turn; an identical count is answered twice; a
     breakdown by year next to the same ages, or next to a count of one of its years). The
     refused count counts nothing, saves no record, does not use up one of the turn's eight
     counts, and no figure of it is in the reply, a tool answer, the log, turn.json, the
     stored turn or `details`; the counts before it are answered as usual and the turn ends
     ANSWERED (C5: a bad spec is a tool error and the turn goes on). `compare` and `share`
     work as today on allowed counts and cannot reach a refused one. Across turns nothing
     changes (C8.6).
C25. With three sources and a source kept from the thread (from a turn that asked; from an
     earlier turn with counts; a turn that asked after other counts), `ask_user` with
     missing `period` gets C24's question naming that source only, and the next turn's
     answer is counted from it. With three sources and no source known, C23's source question
     word for word, and the turn is stored as one that asked for the source. A kept source
     with no copy counts as not known. One and two sources: today's text. `ask_user` with
     missing `source` or `other`: as today.
C26. A breakdown that can have one group only is dropped (year inside one calendar year: a
     year, months of a year, two dates; a category or weekday filtered to one value; a flag
     filtered): one count, no {rN.groups} slot, no table, no such breakdown in the saved spec,
     the total of the request without it; `compare` then accepts two such counts; a breakdown
     that can have several groups is kept; of two breakdowns, the other is left.
C27. The three `why` texts word for word, each on the request that brings it; the codes, and
     the `why` of the other refusals of the same kind, as today.
C28. The line word for word, after the kept note and before the left-out lines, in the reply
     and in the fixed rendering, not in `details`; once with two counts and with two
     refusals; not there with no refusal, a refusal for another reason (C21's own among
     them), a count whose ages miss the refused year, or in a later turn.
     Changed by briefs/S3-R9-A-tests.md (C42 point 1 of docs/S3A-DESIGN.md: a left-out line
     only for a field the count breaks down by): the counts here filter by age and break down
     by nothing, so their "no usable age" lines are gone from the expected replies (C21's one
     good count, and every C28 reply). Nothing else in this file changed.
     Changed back by briefs/S3-R13-A-tests.md (C49 of docs/S3A-DESIGN.md withdraws C42 point 1:
     a filtered field writes its left-out line): those lines are expected again, after C28's
     line, as before round 9 (the eight tests are listed in kit-log/raw/S3-R13-A-notes.txt).

Readings (each in kit-log/raw/S3A-R5-A-notes.txt):
- R1. An error answer is {"error": <code>, ...} and other keys may be there (as in the round 1
  tests); C21's answer must carry "field" (the source's age field: `age`, or `age_years` for
  coded_like) and "why" exactly, and no figure.
- R2. "The ages of the total ... with no age filter, every usable age": so all ages against 11
  and over isolates the 10-year-olds by C21's arithmetic, although the all-ages total also
  holds the records with no usable age. C21's rule is applied as written.
- R3. "Nothing is counted or saved for it": no run record and no result; a later count of the
  turn takes the next result id after the last answered one.
- R4. "Before a count is made" and "after C5's own checks": a request that is both too fine
  and refused by C21 may get TOO_FINE or NOT_ALLOWED, and a ninth count that C21 would
  refuse may get TOO_MANY or NOT_ALLOWED; both are accepted (briefs/QUESTIONS.md).
- R5. "The same days as their period (however the period is written)": whether a period cut
  to the copy (2026, through 17 September) has the same days as 1 January to 17 September
  2026, and whether 2023 and 2024 has the same days as 2024 when the copy starts in 2024, is
  not said; both outcomes are accepted (briefs/QUESTIONS.md).
- R6. A group of a breakdown by year is of the kind "the count's filters, by year", not of the
  kind of a count of that year (C21's text), so under 17 in 2024 next to under 18 in 2024
  and 2025 by year is allowed. The notes say what this lets through.
- R7. C25 "a kept source that has no copy": a copy is taken away between turns by removing
  the `current` file in the test's own state folder (tmp_path); the source is then kept by
  the thread and has no copy.
- R8. C25 with three sources offered, exactly one with a copy and nothing in the thread: the
  source may be read as known by C5's rule (one copy) or as not known; both are accepted
  (briefs/QUESTIONS.md).
- R9. C28 "a refusal for another reason": NOT_ALLOWED for bands of the model's own,
  OUT_OF_COVERAGE, TOO_FINE, and C21's own refusal (its ages are not one year: C28 says
  "because its ages were one year under 18 (C8.4)"). C28 when the count that holds the year
  was made BEFORE the refusal ("the reply then holds"): both readings are accepted
  (briefs/QUESTIONS.md).
- R10. C28 "a count whose ages include that year": a count with no age filter has every usable
  age (C21's words), so it includes the year.
- R11. C26: the saved spec (the run record's `spec`) is "the tidied request"; "the same total as
  the request without the breakdown" is checked against plain counting of the fixture.
"""
import calendar
import dataclasses
import json
import logging

import pytest

from p1support import (LEAVE_OUT, MARK, THREAD_1, Step, ask_user, finish, has_leaf, manifests,
                       mod, show_details)
from s3support import (A_ID, C_ID, C64_LINE_A, COPY_NOW, FIXTURES, NAMES, NEWEST, Q_COMPARE,
                       Q_COUNT, Q_FOLLOW, Q_SHARE, SCHOOL, CountyEnv, FakeService, age,
                       age_left_out_line, assert_reply, check_county_reply, compare, copies_root,
                       count, dates, figures, in_, is_, join_and, months, run_records, share,
                       shown, source_re, table_lines, truth, turn_json, weekdays, year, years)

ROUND3 = FIXTURES / "round3"
V_ID = "FIXTURE:visits_like"
IDS = {"arrests_like": A_ID, "coded_like": C_ID, "visits_like": V_ID}
THREE = ("arrests_like", "coded_like", "visits_like")
A, C, V = THREE
AGE_FIELD = {A: "age", C: "age_years"}

# ---- the texts, written out by hand ---------------------------------------------------------------

WHY = "with this count, the figures of this message would give one year of age under 18"  # C21
WHY_TWO_FILTERS = ('at most one filter per field: for several values use "in": [...]; for '
                   'every value use group_by')                                          # C27
WHY_BREAKDOWN = ("only single counts, with no breakdown, are compared: count each one again "
                 "with no group_by")                                                    # C27
WHY_COMPARE_TODAY = "two to eight different counts of this turn"  # today's, unchanged by C27
C28_LINE = "(I don't count a single year of age under 18, so I counted a wider range.)"


def why_one(rid):
    """C27: exactly one id, a count of this turn with one breakdown."""
    return (f"one count is not compared: its {{{rid}.groups}} slot already says which group "
            f"is highest and lowest")


# C24's question per source (as tests/s3/test_s3_round4.py writes it), today's with one and
# with two sources, C23's source question and the other rows (as test_s3_round3.py writes them).
QUESTION = {
    A: ("Which period do you mean? SYNTHETIC fixture arrests (made up for tests) covers 1 "
        "January 2024 to 17 September 2026."),
    C: ("Which period do you mean? SYNTHETIC fixture intake records (made up for tests) covers "
        "1 January 2025 to 20 August 2026."),
    V: ("Which period do you mean? SYNTHETIC fixture visits (made up for tests) covers 1 "
        "January 2025 to 28 June 2026."),
}
QUESTION_TWO_TODAY = (
    "Which period do you mean? SYNTHETIC fixture arrests (made up for tests) covers 1 January "
    "2024 to 17 September 2026; SYNTHETIC fixture intake records (made up for tests) covers "
    "1 January 2025 to 20 August 2026.")
SOURCE_QUESTION_THREE = ("Which source do you mean? I have 3: arrest records, intake records "
                         "and visit records.")
SOURCE_QUESTION_TWO = ("Which source do you mean: SYNTHETIC fixture arrests (made up for tests) "
                       "or SYNTHETIC fixture intake records (made up for tests)?")
# Changed by briefs/S3-R21-A-tests.md (C57 point 1 of docs/S3A-DESIGN.md; the last sentence was
# 'Say "help" for the list.').
SHORT = ('I can count records from 3 county sources, filter them, break them down, compare '
         'counts and give one as a share of another. Ask "what data do you have?" for the list.')
LONG_A = ("I can count arrest records from SYNTHETIC fixture arrests (made up for tests) for any "
          "period its copy covers, filtered or broken down by age, gender, race, ethnicity, "
          "district, distance from a school, year, month, day of the week and hour, and compare "
          "those counts or give one as a share of another.")
LONG_C = ("I can count intake records from SYNTHETIC fixture intake records (made up for tests) "
          "for any period its copy covers, filtered or broken down by age, race, sex, station, "
          "year, month, day of the week and hour, and compare those counts or give one as a "
          "share of another.")
OTHER = "Could you say a bit more about what you'd like?"
NOT_ALLOWED_ROW = ("I don't count a single year of age under 18; I can count ranges of two years "
                   "or more.")
SOURCE_COUNT_PHRASES = (SHORT, "I have 3:")  # C23's number of sources is not a count (round 3)

# ---- counts and their phrases, written from C6 by hand -----------------------------------------------

UNIT = {A: ("arrest record", "arrest records"), C: ("intake record", "intake records"),
        V: ("visit record", "visit records")}
MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August",
               "September", "October", "November", "December"]
Y25 = year(2025)
U18, U17, U16 = age(None, 17), age(None, 16), age(None, 15)
D3, D4, D6 = (is_("district", f"district {n}") for n in (3, 4, 6))
CODED_AGE = "age_years"


def spec(period, filters=(), group_by=(), name=A):
    return {"name": name, "period": period, "filters": list(filters), "group_by": list(group_by)}


def call_of(s):
    return count(IDS[s["name"]], s["period"], s["filters"], s["group_by"])


def visits_source():
    return json.loads((ROUND3 / "sources" / "visits_like.json").read_text(encoding="utf-8"))


def visits_rows():
    return json.loads((ROUND3 / "rows" / "visits_like.json").read_text(encoding="utf-8"))["rows"]


def total_of(s):
    """The truth's total (plain counting of the fixture rows)."""
    kw = {"src": visits_source(), "rows": visits_rows()} if s["name"] == V else {}
    return truth(s["name"], s["period"], s["filters"], **kw)["total"]


def _age_words(flt):
    low, high = flt.get("from"), flt.get("to")
    if low is not None and high is not None:
        return f"aged {low}" if low == high else f"aged {low} to {high}"
    return f"aged {low} and over" if low is not None else f"under {high + 1}"


def _labels(flt):
    return [flt["is"]] if "is" in flt else list(flt["in"])


def what_words(filters):
    """C6's <what> for the filters these tests use: person fields after `of people ` (the age
    first, then gender and race), then the district or station, then the flag, then days."""
    person, rest = [], []
    for flt in filters:
        if flt["field"] in ("age", CODED_AGE):
            person.insert(0, _age_words(flt))
    for name in ("gender", "race", "sex", "race_code"):
        person += ["recorded as " + join_and(_labels(f)) for f in filters if f["field"] == name]
    rest += ["in " + join_and(_labels(f)) for f in filters if f["field"] == "district"]
    rest += ["at " + join_and(_labels(f)) for f in filters if f["field"] == "station"]
    rest += [("within" if f["is"] else "not within") + " 500 feet of a school"
             for f in filters if f["field"] == SCHOOL]
    rest += ["on " + join_and(f["in"]) for f in filters if f["field"] == "weekday"]
    return " ".join((["of people " + ", ".join(person)] if person else []) + rest)


def period_words(period, name=A):
    def day(text):
        y, m, d = (int(part) for part in text.split("-"))
        return f"{d} {MONTH_NAMES[m - 1]} {y}"
    if "years" in period:
        words, last = "in " + join_and(period["years"]), (period["years"][-1], 12, 31)
    elif "months" in period:
        m = period["months"]
        words = f"from {MONTH_NAMES[m['from'] - 1]} to {MONTH_NAMES[m['to'] - 1]} {period['year']}"
        last = (period["year"], m["to"], calendar.monthrange(period["year"], m["to"])[1])
    elif "year" in period:
        words, last = f"in {period['year']}", (period["year"], 12, 31)
    else:
        words = f"from {day(period['from'])} to {day(period['to'])}"
        last = tuple(int(part) for part in period["to"].split("-"))
    newest = NEWEST.get(name)
    if newest is not None and last > (newest.year, newest.month, newest.day):
        words += f" (through {newest.day} {MONTH_NAMES[newest.month - 1]} {newest.year}, the " \
                 f"latest in this copy)"
    return words


def phrase(s, total=None):
    """C6's count phrase of a count with no breakdown."""
    n = shown(total_of(s) if total is None else total)
    one, many = UNIT[s["name"]]
    what = what_words(s["filters"])
    return f"{n} {one if n == '1' else many}{' ' + what if what else ''} " \
           f"{period_words(s['period'], s['name'])}"


def env_for(tmp_path, monkeypatch, specs):
    names = tuple(n for n in THREE if any(s["name"] == n for s in specs)) or (A,)
    return CountyEnv(tmp_path, monkeypatch, names=names)


def counts_text(n):
    return " ".join(f"I counted {{r{i}.count}}." for i in range(1, n + 1)) or \
        "I counted {r1.count}."


def one_turn(env, specs, answered=None, question=Q_COUNT):
    """One turn: every count in one step, then a finish naming the first `answered` results.
    Returns (reply, Python's answer to each count, in order)."""
    n = len(specs) if answered is None else answered
    reply = env.ask(question, Step(*[call_of(s) for s in specs]),
                    Step(finish("finding", counts_text(n))))
    return reply, [env.model.answer(0, i) for i in range(len(specs))]


def checked(reply):
    """check_county_reply (C1), with C23's number of sources taken out (round 3's reading)."""
    text = reply.text
    for p in SOURCE_COUNT_PHRASES:
        text = text.replace(p, " ")
    check_county_reply(dataclasses.replace(reply, text=text))
    return reply


def assert_result(answer, rid):
    assert answer.get("result_id") == rid and "error" not in answer, (rid, answer)


def assert_not_allowed(answer, field="age"):
    """C21: NOT_ALLOWED, the age field and the `why` word for word; no result, no figure."""
    assert answer.get("error") == "NOT_ALLOWED", answer
    assert answer.get("field") == field, answer
    assert answer.get("why") == WHY, answer
    assert "result_id" not in answer and "slots" not in answer, answer
    assert figures(json.dumps(answer)) == set(), f"a figure in the tool answer: {answer}"


def assert_counted(env, reply, n):
    """n counts answered and saved, no more (R3)."""
    assert len(reply.run_ids) == n, (reply.run_ids, reply.status, reply.text)
    assert len(manifests(env.runs_dir)) == n, "a record was saved for a refused count"
    ids = [r["id"] for r in reply.results if r["kind"] == "count"]
    assert ids == [f"r{i}" for i in range(1, n + 1)], ids


def line1(reply):
    return reply.text.split("\n")[0]


# ---- C21: refused ---------------------------------------------------------------------------------
# Each case: the counts of one turn, in order; every count but the last is answered and the
# last is refused. Source arrests_like (usable ages 10 to 98; bands 10-17, 18-24, ...) unless
# the case names coded_like (usable 12 to 90; bands 12-17, ...). Year 2025 unless said.

REFUSED = {
    "C21: under 17 after under 18 (the 17-year-olds)": [spec(Y25, [U18]), spec(Y25, [U17])],
    "the narrower first: under 18 after under 17": [spec(Y25, [U17]), spec(Y25, [U18])],
    "C21: 11 and over after all ages (the 10-year-olds)": [spec(Y25), spec(Y25, [age(11)])],
    "the narrower first: all ages after 11 and over": [spec(Y25, [age(11)]), spec(Y25)],
    "one range inside the other, the year at its bottom: 13 to 15 after 12 to 15":
        [spec(Y25, [age(12, 15)]), spec(Y25, [age(13, 15)])],
    "one range inside the other, the year at its top: 12 to 14 after 12 to 15":
        [spec(Y25, [age(12, 15)]), spec(Y25, [age(12, 14)])],
    "16 and over after 17 and over (16)": [spec(Y25, [age(17)]), spec(Y25, [age(16)])],
    "a range across 18: 18 to 30 after 17 to 30 (17)":
        [spec(Y25, [age(17, 30)]), spec(Y25, [age(18, 30)])],
    "C21: 14 to 15 after 10 to 16 and 10 to 13 (16, from three counts)":
        [spec(Y25, [age(10, 16)]), spec(Y25, [age(10, 13)]), spec(Y25, [age(14, 15)])],
    "three counts, another order: 10 to 16 after 10 to 13 and 14 to 15":
        [spec(Y25, [age(10, 13)]), spec(Y25, [age(14, 15)]), spec(Y25, [age(10, 16)])],
    "three counts, another order: 10 to 13 after 14 to 15 and 10 to 16":
        [spec(Y25, [age(14, 15)]), spec(Y25, [age(10, 16)]), spec(Y25, [age(10, 13)])],
    "three counts, the year in the middle: 15 to 17 after 10 to 17 and 10 to 13 (14)":
        [spec(Y25, [age(10, 17)]), spec(Y25, [age(10, 13)]), spec(Y25, [age(15, 17)])],
    "four counts, no three of which give one year (16)":
        [spec(Y25, [age(13, 15)]), spec(Y25, [age(10, 12)]), spec(Y25, [age(10, 20)]),
         spec(Y25, [age(17, 20)])],
    "hidden figures count too: under 17 after under 18, both in district 4":
        [spec(Y25, [U18, D4]), spec(Y25, [U17, D4])],
    "C21: 17 to 20 by age band, on its own (the band 10 to 17 cut to 17)":
        [spec(Y25, [age(17, 20)], ["age_band"])],
    "17 and over by age band, on its own": [spec(Y25, [age(17)], ["age_band"])],
    "17 and over by age band and gender, on its own (two cells of 17 alone)":
        [spec(Y25, [age(17)], ["age_band", "gender"])],
    "a band of a breakdown against a narrower count: under 17 after all ages by age band":
        [spec(Y25, [], ["age_band"]), spec(Y25, [U17])],
    "C21: female aged 10 to 17 after 10 to 16 by gender":
        [spec(Y25, [age(10, 16)], ["gender"]), spec(Y25, [age(10, 17), is_("gender", "female")])],
    "the filtered count first: 10 to 16 by gender after female aged 10 to 17":
        [spec(Y25, [age(10, 17), is_("gender", "female")]), spec(Y25, [age(10, 16)], ["gender"])],
    "a flag group: within 500 feet of a school aged 10 to 17 after 10 to 16 by that flag":
        [spec(Y25, [age(10, 16)], [SCHOOL]), spec(Y25, [age(10, 17), is_(SCHOOL, True)])],
    "a flag group, the no side: not within 500 feet aged 10 to 17 after 10 to 16 by that flag":
        [spec(Y25, [age(10, 16)], [SCHOOL]), spec(Y25, [age(10, 17), is_(SCHOOL, False)])],
    "a category the count filters: group Alpha, all ages, after 11 and over in Alpha and Beta "
    "by race": [spec(Y25, [age(11), in_("race", "group Alpha", "group Beta")], ["race"]),
                spec(Y25, [is_("race", "group Alpha")])],
    "the period written two ways: under 17 from 1 January to 31 December 2025 after under 18 "
    "in 2025": [spec(Y25, [U18]), spec(dates("2025-01-01", "2025-12-31"), [U17])],
    "the period written two ways: under 17 in months 1 to 12 of 2025 after under 18 in 2025":
        [spec(Y25, [U18]), spec(months(2025, 1, 12), [U17])],
    "two years written two ways: 1 January 2024 to 31 December 2025 and 2024 and 2025":
        [spec(years(2024, 2025), [U18]), spec(dates("2024-01-01", "2025-12-31"), [U17])],
    "another filter the same on both sides: district 6":
        [spec(Y25, [U18, D6]), spec(Y25, [U17, D6])],
    "the same filter written two ways: is and in": [spec(Y25, [U18, D6]),
                                                    spec(Y25, [U17, in_("district", "district 6")])],
    "two filters the same on both sides, given in another order":
        [spec(Y25, [U18, D6, is_(SCHOOL, False)]), spec(Y25, [is_(SCHOOL, False), U17, D6])],
    "coded: 13 and over after all ages (12, the youngest usable)":
        [spec(Y25, name=C), spec(Y25, [age(13, None, CODED_AGE)], name=C)],
    "coded: 17 to 20 by age band, on its own (the band 12 to 17 cut to 17)":
        [spec(Y25, [age(17, 20, CODED_AGE)], ["age_band"], name=C)],
    # Answer 6 (S3A-DESIGN): a group of a breakdown by year is of the kind of a count of that
    # year. This case was test_c21_allowed[... (R6)] and is now refused.
    "answer 6 (was R6): under 17 in 2024 after under 18 by year for 2024 and 2025":
        [spec(years(2024, 2025), [U18], ["year"]), spec(year(2024), [U17])],
    # C52 point 4 (S3A-DESIGN; brief S3-R16-A): a left-out figure is a figure. These three were
    # test_c21_allowed[...] cases of the same names and are now refused: the left-out lines of
    # the two counts (district, or race) are of one kind and differ by one year of age.
    "C21: the same ages in another district (another kind)": [spec(Y25, [U18, D3]),
                                                              spec(Y25, [U17, D4])],
    "one district against two (another kind)":
        [spec(Y25, [U18, D3]), spec(Y25, [U17, in_("district", "district 3", "district 4")])],
    "a label the filter leaves out gives no figure: group Gamma after Alpha and Beta by race":
        [spec(Y25, [age(11), in_("race", "group Alpha", "group Beta")], ["race"]),
         spec(Y25, [is_("race", "group Gamma")])],
}


@pytest.mark.parametrize("case", list(REFUSED))
def test_c21_refused(tmp_path, monkeypatch, case):
    """C21: the last count of the case is answered NOT_ALLOWED, field: the age field, `why`
    word for word; the counts before it are answered with results; nothing is counted or
    saved for the refused one."""
    specs = REFUSED[case]
    env = env_for(tmp_path, monkeypatch, specs)
    reply, answers = one_turn(env, specs, answered=len(specs) - 1)
    for i, answer in enumerate(answers[:-1], 1):
        assert_result(answer, f"r{i}")
    assert_not_allowed(answers[-1], AGE_FIELD[specs[-1]["name"]])
    assert_counted(env, reply, len(specs) - 1)
    checked(reply)
    if len(specs) == 1:  # refused on its own figures: A7's row of the error (C5)
        assert reply.reason_code == "NOT_ALLOWED", (reply.status, reply.reason_code, reply.text)
    else:
        assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)


def test_c21_refused_in_a_later_step_of_the_turn(tmp_path, monkeypatch):
    """C21: "the figures of the turn's counts so far": a count of an earlier step counts."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask(Q_COUNT, Step(call_of(spec(Y25, [U18]))), Step(call_of(spec(Y25, [U17]))),
                    Step(finish("finding", "I counted {r1.count}.")))
    assert_result(env.model.answer(0), "r1")
    assert_not_allowed(env.model.answer(1))
    assert_counted(env, reply, 1)


def test_c21_a_refused_count_is_not_a_count_of_the_turn(tmp_path, monkeypatch):
    """C21 and R3: under 16 after under 18 and a refused under 17 is allowed (16 and 17 are two
    years): the refused under 17 is not one of the turn's counts, and the next result is r2."""
    specs = [spec(Y25, [U18]), spec(Y25, [U17]), spec(Y25, [U16])]
    env = CountyEnv(tmp_path, monkeypatch)
    reply, answers = one_turn(env, specs, answered=2)
    assert_result(answers[0], "r1")
    assert_not_allowed(answers[1])
    assert_result(answers[2], "r2")
    assert_counted(env, reply, 2)
    assert line1(reply) == f"I counted {phrase(specs[0])}. I counted {phrase(specs[2])}."


def test_c21_an_identical_count_after_a_refusal_is_answered(tmp_path, monkeypatch):
    """C21: the check comes after the reuse of an identical count of the turn."""
    specs = [spec(Y25, [U18]), spec(Y25, [U17]), spec(Y25, [U18])]
    env = CountyEnv(tmp_path, monkeypatch)
    reply, answers = one_turn(env, specs, answered=1)
    assert_result(answers[0], "r1")
    assert_not_allowed(answers[1])
    assert_result(answers[2], "r1")
    assert_counted(env, reply, 1)


@pytest.mark.parametrize("bad, code", [
    (spec(Y25, [U17, is_("district", "district 99")]), "BAD_VALUE"),
    (spec(Y25, [U17], ["no_such_breakdown"]), "BAD_FIELD"),
    (spec(year(2019), [U17]), "OUT_OF_COVERAGE"),
], ids=["a label the file does not list", "an unknown breakdown", "a period outside the copy"])
def test_c21_comes_after_c5s_own_checks(tmp_path, monkeypatch, bad, code):
    """C21: "The check comes after C5's own checks": a bad spec gets C5's own error."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply, answers = one_turn(env, [spec(Y25, [U18]), bad], answered=1)
    assert_result(answers[0], "r1")
    assert answers[1].get("error") == code, answers[1]
    assert_counted(env, reply, 1)


def test_c21_the_refused_count_does_not_use_up_one_of_the_turns_counts(tmp_path, monkeypatch):
    """C21: "it does not use up one of the turn's counts": after a refusal, eight counts are
    still answered (C5: a ninth is TOO_MANY)."""
    others = [spec(Y25, [U18, is_("district", f"district {n}")]) for n in range(1, 7)]
    specs = ([spec(Y25, [U18]), spec(Y25, [U17])] + others + [spec(year(2024), [U18])]
             + [spec(year(2026), [U18])])
    env = CountyEnv(tmp_path, monkeypatch)
    reply, answers = one_turn(env, specs, answered=1)
    assert_result(answers[0], "r1")
    assert_not_allowed(answers[1])
    for i, answer in enumerate(answers[2:9], 2):
        assert_result(answer, f"r{i}")
    assert answers[9].get("error") == "TOO_MANY", answers[9]
    assert_counted(env, reply, 8)


def test_c21_no_figure_of_the_refused_count_anywhere(tmp_path, monkeypatch, caplog):
    """C21 "Nothing is counted or saved for it" and the brief: no figure of the refused count
    (under 17 in 2025, 28 records by plain counting) in the reply, the tool answer, the log,
    turn.json, the stored turn or `details`; only the count before it is there."""
    caplog.set_level(logging.DEBUG)
    caplog.set_level(logging.DEBUG, logger="moco_agent")
    first, refused = spec(Y25, [U18]), spec(Y25, [U17])
    hidden_total = total_of(refused)
    assert (hidden_total, total_of(first)) == (28, 31), "premise: the fixture's figures"
    env = CountyEnv(tmp_path, monkeypatch)
    reply, answers = one_turn(env, [first, refused], answered=1)
    assert_not_allowed(answers[1])
    # C36 point 5 (S3-R6-A): `details` goes to the model, which calls show_details
    details = env.ask("details", Step(show_details()))
    logged = caplog.text + "\n".join(r.getMessage() for r in caplog.records)
    for where, text in (("reply", reply.text), ("details", details.text), ("log", logged)):
        assert hidden_total not in figures(text), f"the refused count's figure is in the {where}"
    record = turn_json(reply, env.runs_dir)
    stored = env.store.recent_turns(THREAD_1, 10)[0]
    for where, data in (("turn.json", record), ("stored turn", stored)):
        assert not has_leaf(data, hidden_total), f"the refused count's figure is in the {where}"
        assert [r["id"] for r in data["results"]] == ["r1"], data["results"]
    assert [r["total"] for r in reply.results] == [31]


def test_c21_the_turn_ends_as_with_one_good_count(tmp_path, monkeypatch):
    """C5: a bad spec is a tool error and the turn goes on; the count before it is answered as
    usual: the model's line, the source line, and no line of C28 (the refusal was C21's, not
    one year asked: R9). Changed by briefs/S3-R9-A-tests.md: no left-out line (C42 point 1:
    the age is a filter only); was `(fewer than 10 had no usable age and are not included.)`.
    Changed back by briefs/S3-R13-A-tests.md (C49): the line again.
    Changed by briefs/S3-R28-A-tests.md (C64 point 3a): a count refused by C21's check beside a
    count made: the reply holds C64's line a (s3support.C64_LINE_A) directly after line 1 (no
    kept or widened line here), before the left-out line; it had no such line."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply, _ = one_turn(env, [spec(Y25, [U18]), spec(Y25, [U17])], answered=1)
    assert (reply.status, reply.reply_style) == ("ANSWERED", "agent"), \
        (reply.status, reply.draft_failures, reply.text)
    assert_reply(reply.text, "I counted 31 arrest records of people under 18 in 2025.",
                 left_out=[C64_LINE_A, age_left_out_line(5)], source=source_re(A))
    checked(reply)


def test_c21_compare_cannot_reach_a_refused_count(tmp_path, monkeypatch):
    """C21 "compare and share need no rule of their own: they only use counts of the turn":
    the refused count has no result, so a compare naming it is not made and no difference
    of the two (the 17-year-olds) is written."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask(Q_COMPARE, Step(call_of(spec(Y25, [U18])), call_of(spec(Y25, [U17]))),
                    Step(compare("r1", "r2")), Step(finish("finding", "I counted {r1.count}.")))
    assert_not_allowed(env.model.answer(0, 1))
    assert env.model.answer(1).get("error") == "BAD_COMPARE", env.model.answer(1)
    assert "difference" not in reply.text and 3 not in figures(reply.text), reply.text
    assert [r["kind"] for r in reply.results] == ["count"]


# ---- C21: open cases (R4, R5): both outcomes accepted ------------------------------------------------

def assert_refused_or(answer, codes, field="age"):
    """Either C21's refusal or one of `codes` (each a spec error that counts nothing)."""
    if answer.get("error") == "NOT_ALLOWED":
        assert_not_allowed(answer, field)
    else:
        assert answer.get("error") in codes, answer


def test_c21_open_a_count_that_is_too_fine_and_refused(tmp_path, monkeypatch):
    """R4, answered (S3A-DESIGN, answer 1): under 17 by district after under 18 is too fine
    and refused by C21: NOT_ALLOWED (C21 is checked before the count is made)."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply, answers = one_turn(env, [spec(Y25, [U18]), spec(Y25, [U17], ["district"])],
                              answered=1)
    assert_not_allowed(answers[1])
    assert_counted(env, reply, 1)


def test_c21_open_a_ninth_count_that_c21_would_refuse(tmp_path, monkeypatch):
    """R4, answered (S3A-DESIGN, answer 2): eight counts made; a ninth that C21 refuses gets
    NOT_ALLOWED (checked before the limit)."""
    eight = [spec(Y25, [U18])] + [spec(Y25, [U18, is_("district", f"district {n}")])
                                  for n in range(1, 7)] + [spec(year(2024), [U18])]
    env = CountyEnv(tmp_path, monkeypatch)
    reply, answers = one_turn(env, eight + [spec(Y25, [U17])], answered=1)
    assert_not_allowed(answers[8])
    assert_counted(env, reply, 8)


@pytest.mark.parametrize("first, second", [
    (spec(year(2026), [U18]), spec(dates("2026-01-01", "2026-09-17"), [U17])),
    (spec(years(2023, 2024), [U18]), spec(year(2024), [U17])),
], ids=["a period cut to the copy", "a period that starts before the copy"])
def test_c21_open_the_same_records_under_two_periods(tmp_path, monkeypatch, first, second):
    """R5, answered (S3A-DESIGN, answer 3): each period is cut to the copy's first day and
    newest day before C21 compares them, so the two are the same days and C21 refuses the
    second."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply, answers = one_turn(env, [first, second], answered=1)
    assert_result(answers[0], "r1")
    assert_not_allowed(answers[1])
    assert_counted(env, reply, 1)


# ---- C21: allowed, answered as today ---------------------------------------------------------------

ALLOWED = {
    "C21: under 18 and 18 to 24": [spec(Y25, [U18]), spec(Y25, [age(18, 24)])],
    "C21: under 18 and under 16 (two years)": [spec(Y25, [U18]), spec(Y25, [U16])],
    "C21: 18 to 21 and 19 to 21 (the year is 18)": [spec(Y25, [age(18, 21)]),
                                                     spec(Y25, [age(19, 21)])],
    "10 to 18 and under 18 (the year is 18)": [spec(Y25, [age(10, 18)]), spec(Y25, [U18])],
    "C21: the same ages in another year (another kind)": [spec(Y25, [U18]),
                                                          spec(year(2024), [U17])],
    # C52 point 4 (brief S3-R16-A): the three cases "C21: the same ages in another district
    # (another kind)", "one district against two (another kind)" and "a label the filter leaves
    # out gives no figure: group Gamma after Alpha and Beta by race" moved to REFUSED; each is
    # replaced here by a case that keeps what it meant to show.
    "C21: the same ages in two districts (another kind)": [spec(Y25, [U18, D3]),
                                                           spec(Y25, [U18, D4])],
    "a filter on one side only (another kind)": [spec(Y25, [U18]), spec(Y25, [U17, D6])],
    "one district against two, two years apart (another kind)":
        [spec(Y25, [U18, D3]), spec(Y25, [U16, in_("district", "district 3", "district 4")])],
    "another source (another kind)": [spec(Y25, [U18]),
                                      spec(Y25, [age(None, 16, CODED_AGE)], name=C)],
    "a label the filter leaves out gives no figure: Gamma under 18 after Alpha and Beta by band":
        [spec(years(2024, 2025), [age(11), in_("race", "group Alpha", "group Beta")],
              ["race", "age_band"]),
         spec(years(2024, 2025), [U18, is_("race", "group Gamma")])],
    "a breakdown by year next to the same ages without it":
        [spec(years(2024, 2025), [U18], ["year"]), spec(years(2024, 2025), [U18])],
    "15 to 20 by age band, on its own (the band 10 to 17 cut to 15 to 17)":
        [spec(Y25, [age(15, 20)], ["age_band"])],
}


@pytest.mark.parametrize("case", list(ALLOWED))
def test_c21_allowed(tmp_path, monkeypatch, case):
    """C21's allowed examples and more: every count is answered with a result, as today; line
    1 holds each count phrase with the truth's total."""
    specs = ALLOWED[case]
    env = env_for(tmp_path, monkeypatch, specs)
    reply, answers = one_turn(env, specs)
    for i, answer in enumerate(answers, 1):
        assert_result(answer, f"r{i}")
    assert_counted(env, reply, len(specs))
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    if not any(s["group_by"] for s in specs):
        assert line1(reply) == " ".join(f"I counted {phrase(s)}." for s in specs)
    checked(reply)


def test_c21_allowed_an_identical_count_is_answered_twice(tmp_path, monkeypatch):
    env = CountyEnv(tmp_path, monkeypatch)
    reply, answers = one_turn(env, [spec(Y25, [U18]), spec(Y25, [U18])], answered=1)
    assert_result(answers[0], "r1")
    assert_result(answers[1], "r1")
    assert_counted(env, reply, 1)


def test_c21_allowed_a_count_that_failed_is_not_a_count_of_the_turn(tmp_path, monkeypatch):
    """Under 18 by district in 2025 is too fine; under 17 after it is answered."""
    failed, then = spec(Y25, [U18], ["district"]), spec(Y25, [U17])
    env = CountyEnv(tmp_path, monkeypatch)
    reply, answers = one_turn(env, [failed, then], answered=1)
    assert answers[0].get("error") == "TOO_FINE", answers[0]
    assert_result(answers[1], "r1")
    assert_counted(env, reply, 1)
    assert line1(reply) == f"I counted {phrase(then)}."


def test_c21_allowed_a_c5_refusal_is_not_a_count_of_the_turn(tmp_path, monkeypatch):
    """C5's own NOT_ALLOWED (17 alone) counts nothing; under 17 after it is answered."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply, answers = one_turn(env, [spec(Y25, [age(17, 17)]), spec(Y25, [U17])], answered=1)
    assert answers[0].get("error") == "NOT_ALLOWED" and answers[0].get("field") == "age", \
        answers[0]
    assert_result(answers[1], "r1")
    assert_counted(env, reply, 1)


def test_c21_allowed_compare_works_as_today(tmp_path, monkeypatch):
    """C21: compare needs no rule of its own; on two allowed counts it is as today."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask(Q_COMPARE, Step(call_of(spec(Y25, [U18])), call_of(spec(Y25, [age(18, 24)]))),
                    Step(compare("r1", "r2")),
                    Step(finish("finding", "Here is the comparison: {r3.compare}.")))
    assert_result(env.model.answer(1), "r3")
    assert reply.reply_style == "agent", reply.draft_failures
    assert line1(reply) == ("Here is the comparison: people aged 18 to 24 had the highest count "
                            "(52) and people under 18 the lowest (31), a difference of 21.")
    checked(reply)


def test_c21_allowed_share_works_as_today(tmp_path, monkeypatch):
    """C21: share needs no rule of its own; the part (under 18) of the whole (all ages)."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask(Q_SHARE, Step(call_of(spec(Y25)), call_of(spec(Y25, [U18]))),
                    Step(share("r2", "r1")),
                    Step(finish("finding", "Here is what I found: {r3.share}.")))
    assert_result(env.model.answer(1), "r3")
    assert reply.reply_style == "agent", reply.draft_failures
    assert line1(reply) == ("Here is what I found: 13% of the 240 arrest records in 2025 were "
                            "of people under 18.")
    checked(reply)


# ---- C21: across turns nothing changes (C8.6) --------------------------------------------------------

ACROSS = {
    "under 18, then under 17": [[spec(Y25, [U18])], [spec(Y25, [U17])]],
    "under 17, then under 18": [[spec(Y25, [U17])], [spec(Y25, [U18])]],
    "all ages, then 11 and over": [[spec(Y25)], [spec(Y25, [age(11)])]],
    "10 to 16 and 10 to 13, then 14 to 15": [[spec(Y25, [age(10, 16)]), spec(Y25, [age(10, 13)])],
                                             [spec(Y25, [age(14, 15)])]],
    "10 to 16 by gender, then female aged 10 to 17":
        [[spec(Y25, [age(10, 16)], ["gender"])], [spec(Y25, [age(10, 17), is_("gender", "female")])]],
}


# Changed by briefs/S3-R23-A-tests.md (C61 point 10 of docs/S3A-DESIGN.md, C21 over the thread; it
# was test_c21_across_turns_both_are_answered, C21's "What this does not do": the same counts asked
# in two messages were both answered). In one thread the second message's count is now refused,
# with C21's `why` and C61 point 10's sentence; in two threads both are still answered
# (tests/s3/test_s3_c61d.py).
WHY_THREAD = WHY + " Counts given earlier in this conversation are taken into account."  # C61 10


@pytest.mark.parametrize("case", list(ACROSS))
def test_c21_across_turns_in_one_thread_the_second_is_not_allowed(tmp_path, monkeypatch, case):
    """C61 point 10: the first message is answered; the second message's count is NOT_ALLOWED,
    the age field, C21's `why` with the sentence, nothing counted or saved for it."""
    env = CountyEnv(tmp_path, monkeypatch)
    first, second = ACROSS[case]
    reply, answers = one_turn(env, first, question=Q_COUNT)
    for i, answer in enumerate(answers, 1):
        assert_result(answer, f"r{i}")
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert len(reply.run_ids) == len(first)
    if not any(s["group_by"] for s in first):
        assert line1(reply) == " ".join(f"I counted {phrase(s)}." for s in first)
    assert len(second) == 1, "premise: one count in the second message"
    reply, (answer,) = one_turn(env, second, answered=0, question=Q_FOLLOW)
    assert answer.get("error") == "NOT_ALLOWED" and answer.get("field") == "age", answer
    assert answer.get("why") == WHY_THREAD, answer
    assert "result_id" not in answer and figures(json.dumps(answer)) == set(), answer
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", "NOT_ALLOWED"), reply.text
    assert reply.run_ids == [] and len(manifests(env.runs_dir)) == len(first)


# ---- C25: the period question when no source is known ----------------------------------------------

def add_visits(env, copy=True):
    """Round 3's third source file in the env's sources folder and, with `copy`, its copy
    made through the fake transport (as test_s3_round4.py does)."""
    src = visits_source()
    (env.sources_dir / "visits_like.json").write_text(json.dumps(src, indent=2),
                                                      encoding="utf-8")
    if copy:
        mod("sources").fetch(V_ID, state_dir=env.state_dir,
                             transport=FakeService(visits_rows(), address=src["address"]),
                             now=COPY_NOW)
    return env


def three_sources(tmp_path, monkeypatch, copies=THREE):
    """The three fixture sources offered; `copies` says which have a copy."""
    env = CountyEnv(tmp_path, monkeypatch, names=NAMES, copies=[n for n in NAMES if n in copies])
    add_visits(env, copy=V in copies)
    assert list(mod("sources").county_sources()) == [A_ID, C_ID, V_ID], "premise: three"
    for name in THREE:
        has_copy = mod("sources").latest(IDS[name], state_dir=env.state_dir) is not None
        assert has_copy is (name in copies), f"premise: {name} has a copy: {name in copies}"
    return env


def take_copy_away(env, name):
    """R7: the source keeps its file and loses its copy (the test's own state folder only)."""
    (copies_root(env.state_dir, name) / "current").unlink()
    assert mod("sources").latest(IDS[name], state_dir=env.state_dir) is None, "premise: no copy"


def asked(env, reply, calls=1):
    """The turn ended with a question from Python (round 4's check): NEEDS_INPUT, nothing
    counted, the model called once (`calls` times when the turn went on before the question:
    C25 point 0)."""
    assert (reply.status, reply.reason_code) == ("NEEDS_INPUT", "NEEDS_CLARIFICATION"), \
        (reply.status, reply.reason_code, reply.text)
    assert reply.run_ids == [], "a question counts nothing"
    assert len(env.model.calls) == calls, "the turn ends with the question"
    checked(reply)
    return reply.text


def model_asks_period(env, question="Which periods can I ask about?"):
    """A turn where the model stand-in calls ask_user with missing `period`. C25 point 0 (brief
    S3A-R5b-A): the first such call of a turn gets the tool error NO_PERIOD_QUESTION and the
    turn goes on, so the stand-in sends it once more; the second ends the turn (points 1 to 3)
    with the model called twice."""
    return asked(env, env.ask(question, Step(ask_user("period")), Step(ask_user("period"))),
                 calls=2)


def stored_missing(env):
    return env.store.recent_turns(THREAD_1, 1)[-1].get("missing")


ANSWER_YEAR = {A: 2024, C: 2025, V: 2025}  # a year each source's copy covers in full
TWO_YEARS = {A: (2024, 2025), C: (2025, 2026), V: (2025, 2026)}


def kept_by_a_question(env, name):
    """Turn 1 names the source and no period: Python asks C24's question (pending source)."""
    reply = env.ask(Q_COUNT, Step(count(IDS[name])), Step(finish("finding", "I counted {r1.count}.")))
    assert asked(env, reply) == QUESTION[name], "premise: C24's question"


def kept_by_counts(env, name):
    """Turn 1 counts the source in two years: the source is kept and no one period is."""
    first, second = TWO_YEARS[name]
    reply = env.ask(Q_COUNT, Step(count(IDS[name], year(first)), count(IDS[name], year(second))),
                    Step(finish("finding", "I counted {r1.count} and {r2.count}.")))
    assert reply.status == "ANSWERED" and len(reply.run_ids) == 2, (reply.status, reply.text)


def the_answer_is_counted_from(env, name):
    """The next turn answers with a year only; the model counts it with no source; it is
    counted from `name`."""
    y = ANSWER_YEAR[name]
    reply = env.ask(str(y), Step(count(LEAVE_OUT, year(y))),
                    Step(finish("finding", "I counted {r1.count}.")))
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    (record,) = run_records(reply, env.runs_dir)
    assert record["spec"]["source"] == IDS[name], record["spec"]
    assert line1(reply) == f"I counted {phrase(spec(year(y), name=name))}."


@pytest.mark.parametrize("name", THREE)
def test_c25_three_sources_the_source_of_the_turn_that_asked(tmp_path, monkeypatch, name):
    """C25.1: the source of the turn that asked (its pending request): C24's question naming
    that source only, kept with the question, so the next answer is counted from it."""
    env = three_sources(tmp_path, monkeypatch)
    kept_by_a_question(env, name)
    assert model_asks_period(env) == QUESTION[name]
    the_answer_is_counted_from(env, name)


@pytest.mark.parametrize("name", THREE)
def test_c25_three_sources_the_source_of_an_earlier_turn_with_counts(tmp_path, monkeypatch,
                                                                     name):
    """C25.1: else the one source of the most recent earlier turn with counts (C9)."""
    env = three_sources(tmp_path, monkeypatch)
    kept_by_counts(env, name)
    assert model_asks_period(env) == QUESTION[name]
    the_answer_is_counted_from(env, name)


def test_c25_the_turn_that_asked_comes_before_earlier_counts(tmp_path, monkeypatch):
    """C25.1: the pending request's source first, "else" the last answer's: counts of
    arrests_like, then a question about visits_like, then the model asks for the period."""
    env = three_sources(tmp_path, monkeypatch)
    kept_by_counts(env, A)
    kept_by_a_question(env, V)
    assert model_asks_period(env) == QUESTION[V]
    the_answer_is_counted_from(env, V)


def test_c25_three_sources_no_source_known_asks_for_the_source(tmp_path, monkeypatch):
    """C25.2: nothing in the thread: C23's source question word for word, the turn stored as
    one that asked for the source; once the source is named, the period is asked by C5's own
    rule (C24's question), and the answer is counted from it."""
    env = three_sources(tmp_path, monkeypatch)
    assert model_asks_period(env) == SOURCE_QUESTION_THREE
    assert stored_missing(env) == "source"
    reply = env.ask("The visits.", Step(count(V_ID)), Step(finish("finding", "I counted {r1.count}.")))
    assert asked(env, reply) == QUESTION[V]
    the_answer_is_counted_from(env, V)


def test_c25_three_sources_an_earlier_turn_with_two_sources_keeps_none(tmp_path, monkeypatch):
    """C25.2 with C9: the last answer counted two sources, so no one source is kept."""
    env = three_sources(tmp_path, monkeypatch)
    reply = env.ask(Q_COUNT, Step(count(A_ID, Y25), count(C_ID, Y25)),
                    Step(finish("finding", "I counted {r1.count} and {r2.count}.")))
    assert reply.status == "ANSWERED", (reply.status, reply.text)
    assert model_asks_period(env) == SOURCE_QUESTION_THREE
    assert stored_missing(env) == "source"


@pytest.mark.parametrize("keep", [kept_by_a_question, kept_by_counts],
                         ids=["kept by a question", "kept by counts"])
def test_c25_a_kept_source_with_no_copy_is_not_known(tmp_path, monkeypatch, keep):
    """C25 (the brief): a kept source that has no copy counts as not known (R7)."""
    env = three_sources(tmp_path, monkeypatch)
    keep(env, V)
    take_copy_away(env, V)
    assert model_asks_period(env) == SOURCE_QUESTION_THREE
    assert stored_missing(env) == "source"


def test_c25_open_three_sources_offered_and_one_copy(tmp_path, monkeypatch):
    """R8, answered (S3A-DESIGN, answer 4): three offered, only arrests_like has a copy,
    nothing in the thread: the source with the copy is known (C5), so C24's question naming
    it."""
    env = three_sources(tmp_path, monkeypatch, copies=(A,))
    assert model_asks_period(env) == QUESTION[A]


@pytest.mark.parametrize("keep", [None, kept_by_a_question, kept_by_counts],
                         ids=["nothing kept", "kept by a question", "kept by counts"])
def test_c25_one_source_todays_question(tmp_path, monkeypatch, keep):
    """C25.3: with one source offered nothing changes."""
    env = CountyEnv(tmp_path, monkeypatch, names=(A,))
    if keep:
        keep(env, A)
    assert model_asks_period(env) == QUESTION[A]


@pytest.mark.parametrize("keep", [None, kept_by_a_question, kept_by_counts],
                         ids=["nothing kept", "kept by a question", "kept by counts"])
def test_c25_two_sources_todays_question(tmp_path, monkeypatch, keep):
    """C25.3: with two sources offered nothing changes: both clauses, whatever is kept."""
    env = CountyEnv(tmp_path, monkeypatch, names=NAMES)
    if keep is kept_by_a_question:  # today's question with two sources names both
        reply = env.ask(Q_COUNT, Step(count(C_ID)), Step(finish("finding", "I counted {r1.count}.")))
        assert asked(env, reply) == QUESTION_TWO_TODAY
    elif keep:
        keep(env, C)
    assert model_asks_period(env) == QUESTION_TWO_TODAY


@pytest.mark.parametrize("names, missing, expected", [
    (THREE, "source", SOURCE_QUESTION_THREE),
    (THREE, "other", OTHER + " " + SHORT),
    (NAMES, "source", SOURCE_QUESTION_TWO),
    (NAMES, "other", OTHER + " " + LONG_A + " " + LONG_C),
], ids=["three sources, source", "three sources, other", "two sources, source",
        "two sources, other"])
def test_c25_ask_user_for_source_or_other_is_as_today(tmp_path, monkeypatch, names, missing,
                                                      expected):
    env = three_sources(tmp_path, monkeypatch) if names == THREE else \
        CountyEnv(tmp_path, monkeypatch, names=names)
    reply = env.ask("Hmm.", Step(ask_user(missing)))
    assert asked(env, reply) == expected
    assert stored_missing(env) == missing


def test_c25_ask_user_for_the_source_with_a_kept_source_is_as_today(tmp_path, monkeypatch):
    """C25: `ask_user` with missing `source` is unchanged, even with a source kept."""
    env = three_sources(tmp_path, monkeypatch)
    kept_by_counts(env, V)
    assert asked(env, env.ask("Hmm.", Step(ask_user("source")))) == SOURCE_QUESTION_THREE


# ---- C26: a breakdown that can only have one group is dropped -----------------------------------------

DROPPED = {
    # id: (spec with the breakdown, the breakdown's group labels that must not be a table line)
    "year: a year": (spec(Y25, [], ["year"]), ["2025"]),
    "year: months of one year": (spec(months(2025, 1, 6), [], ["year"]), ["2025"]),
    "year: two dates inside one year": (spec(dates("2025-03-01", "2025-08-31"), [], ["year"]),
                                        ["2025"]),
    "year: a year cut to the copy": (spec(year(2026), [], ["year"]), ["2026"]),
    "a category filtered with is": (spec(Y25, [D3], ["district"]), ["district 3"]),
    "a category filtered with in, one value": (spec(Y25, [in_("district", "district 3")],
                                                    ["district"]), ["district 3"]),
    "a person category": (spec(Y25, [is_("gender", "female")], ["gender"]), ["female"]),
    "a category of two raw values for one label (coded)":
        (spec(Y25, [is_("station", "station 3")], ["station"], name=C), ["station 3"]),
    "weekday filtered to one day": (spec(Y25, [weekdays("Saturday")], ["weekday"]),
                                    ["Saturday"]),
    "a flag filtered yes": (spec(Y25, [is_(SCHOOL, True)], [SCHOOL]),
                            ["within 500 feet of a school"]),
    "a flag filtered no": (spec(Y25, [is_(SCHOOL, False)], [SCHOOL]),
                           ["not within 500 feet of a school"]),
    "two breakdowns, both dropped": (spec(Y25, [D3], ["year", "district"]), ["2025",
                                                                            "district 3"]),
}


@pytest.mark.parametrize("case", list(DROPPED))
def test_c26_a_breakdown_with_one_possible_group_gives_a_single_count(tmp_path, monkeypatch,
                                                                       case):
    """C26: an ordinary single count: no {r1.groups} slot, no table, the tidied request (the
    saved spec) has no such breakdown, the same total and phrase as without it."""
    s, labels = DROPPED[case]
    env = env_for(tmp_path, monkeypatch, [s])
    reply, (answer,) = one_turn(env, [s])
    assert_result(answer, "r1")
    assert answer.get("slots") == ["{r1.count}"], answer
    (record,) = run_records(reply, env.runs_dir)
    assert record["spec"]["group_by"] == [], record["spec"]
    without = dict(s, group_by=[])
    assert record["computed_values"]["total"] == total_of(without)
    assert reply.results[0]["groups"] is None and reply.results[0]["grid"] is None
    assert line1(reply) == f"I counted {phrase(without)}."
    for label in labels:
        assert f"\n{label}: " not in reply.text, reply.text
    checked(reply)


KEPT = {
    "years 2024 and 2025 by year": (spec(years(2024, 2025), [], ["year"]), ["year"]),
    "two dates across two years by year": (spec(dates("2024-12-01", "2025-01-31"), [], ["year"]),
                                           ["year"]),
    "a category filtered to two values": (spec(Y25, [in_("district", "district 3",
                                                          "district 4")], ["district"]),
                                          ["district"]),
    "a category not filtered": (spec(Y25, [], ["district"]), ["district"]),
    "weekday filtered to two days": (spec(Y25, [weekdays("Saturday", "Sunday")], ["weekday"]),
                                     ["weekday"]),
    "two breakdowns, the year dropped, district left": (spec(Y25, [], ["year", "district"]),
                                                       ["district"]),
    "two breakdowns, district dropped, gender left": (spec(Y25, [D3], ["district", "gender"]),
                                                      ["gender"]),
}


@pytest.mark.parametrize("case", list(KEPT))
def test_c26_a_breakdown_that_can_have_several_groups_is_kept(tmp_path, monkeypatch, case):
    """C26: only a breakdown fixed to one value is dropped; the others are kept as today (a
    one-way breakdown offers {r1.groups} and its table)."""
    s, kept = KEPT[case]
    env = env_for(tmp_path, monkeypatch, [s])
    reply, (answer,) = one_turn(env, [s])
    assert_result(answer, "r1")
    assert answer.get("slots") == ["{r1.count}", "{r1.groups}"], answer
    (record,) = run_records(reply, env.runs_dir)
    assert record["spec"]["group_by"] == kept, record["spec"]
    groups = truth(s["name"], s["period"], s["filters"], kept)["groups"]
    assert [g[-1] for g in reply.results[0]["groups"]] == list(groups.values())
    for line in table_lines(groups):
        assert f"\n{line}" in reply.text, (line, reply.text)


@pytest.mark.parametrize("first, second, expected", [
    (spec(year(2024), [], ["year"]), spec(Y25, [], ["year"]),
     "2025 had the highest count (240) and 2024 the lowest (230), a difference of 10"),
    (spec(Y25, [is_("district", "district 1")], ["district"]), spec(Y25, [D6], ["district"]),
     "district 6 had the highest count (57) and district 1 the lowest (36), a difference of 21"),
], ids=["2024 by year and 2025 by year", "district 1 and district 6, each by district"])
def test_c26_compare_accepts_two_such_counts(tmp_path, monkeypatch, first, second, expected):
    """C26: "compare 2024 with 2025" counted each year "by year"; compare is then made."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask(Q_COMPARE, Step(call_of(first), call_of(second)), Step(compare("r1", "r2")),
                    Step(finish("finding", "Here is the comparison: {r3.compare}.")))
    assert_result(env.model.answer(1), "r3")
    assert line1(reply) == f"Here is the comparison: {expected}."
    checked(reply)


# ---- C27: three refusals say what to do instead -----------------------------------------------------

@pytest.mark.parametrize("filters, name", [
    ([D3, D4], "district"),
    ([is_("gender", "female"), is_("gender", "male")], "gender"),
    ([age(18, 21), age(30, 40)], "age"),
    ([weekdays("Saturday"), weekdays("Sunday")], "weekday"),
], ids=["district", "gender", "age", "weekday"])
def test_c27_two_filters_on_one_field(tmp_path, monkeypatch, filters, name):
    env = CountyEnv(tmp_path, monkeypatch)
    reply, (answer,) = one_turn(env, [spec(Y25, filters)], answered=0)
    assert answer.get("error") == "BAD_FIELD" and answer.get("field") == name, answer
    assert answer.get("why") == WHY_TWO_FILTERS, answer
    assert reply.run_ids == []


def test_c27_other_bad_field_refusals_keep_their_why(tmp_path, monkeypatch):
    """C27 changes only the `why` of two filters on one field (C17's stays as today)."""
    env = CountyEnv(tmp_path, monkeypatch)
    _, (answer,) = one_turn(env, [spec(years(2024, 2025), [], ["year", "month"])], answered=0)
    assert answer.get("error") == "BAD_FIELD", answer
    assert answer.get("why") == "month already names the year: use month alone", answer


def compare_answer(env, counts, ids):
    env.ask(Q_COMPARE, Step(*[call_of(s) for s in counts]), Step(compare(*ids)),
            Step(finish("finding", "I counted {r1.count}.")))
    return env.model.answer(1)


BY_DISTRICT, ALL_2024 = spec(Y25, [], ["district"]), spec(year(2024))


@pytest.mark.parametrize("counts, ids", [
    ([BY_DISTRICT, ALL_2024], ("r1", "r2")),
    ([ALL_2024, BY_DISTRICT], ("r1", "r2")),
    ([ALL_2024, BY_DISTRICT, spec(Y25)], ("r1", "r3", "r2")),
], ids=["the first has a breakdown", "the second has a breakdown", "one of three"])
def test_c27_compare_with_a_breakdown_among_the_ids(tmp_path, monkeypatch, counts, ids):
    env = CountyEnv(tmp_path, monkeypatch)
    answer = compare_answer(env, counts, ids)
    assert answer.get("error") == "BAD_COMPARE", answer
    assert answer.get("why") == WHY_BREAKDOWN, answer


@pytest.mark.parametrize("counts, rid", [([BY_DISTRICT], "r1"), ([ALL_2024, BY_DISTRICT], "r2")],
                         ids=["r1", "r2"])
def test_c27_compare_of_exactly_one_count_with_one_breakdown(tmp_path, monkeypatch, counts, rid):
    env = CountyEnv(tmp_path, monkeypatch)
    answer = compare_answer(env, counts, (rid,))
    assert answer.get("error") == "BAD_COMPARE", answer
    assert answer.get("why") == why_one(rid), answer


@pytest.mark.parametrize("counts, ids, code, why", [
    ([ALL_2024], ("r1",), "BAD_COMPARE", WHY_COMPARE_TODAY),
    ([ALL_2024, spec(Y25)], ("r1", "r9"), "BAD_COMPARE", WHY_COMPARE_TODAY),
    ([ALL_2024, spec(Y25)], ("r1", "r1"), "BAD_COMPARE", WHY_COMPARE_TODAY),
], ids=["one id of a single count", "an unknown id", "the same id twice"])
def test_c27_other_compare_refusals_are_as_today(tmp_path, monkeypatch, counts, ids, code, why):
    env = CountyEnv(tmp_path, monkeypatch)
    answer = compare_answer(env, counts, ids)
    assert answer.get("error") == code and answer.get("why") == why, answer


def test_c27_mixed_sources_is_as_today(tmp_path, monkeypatch):
    env = CountyEnv(tmp_path, monkeypatch, names=NAMES)
    answer = compare_answer(env, [spec(Y25), spec(Y25, name=C)], ("r1", "r2"))
    assert answer.get("error") == "MIXED_SOURCES", answer


# ---- C28: a single year under 18, answered with a wider range, says so --------------------------------

def widened_turn(env, refused, counted, text=None, question=Q_COUNT):
    """One turn: each refused count, then each counted one, in one step; the model's line
    names every result."""
    specs = list(refused) + list(counted)
    reply = env.ask(question, Step(*[call_of(s) for s in specs]),
                    Step(finish("finding", text or counts_text(len(counted)))))
    return reply, [env.model.answer(0, i) for i in range(len(specs))]


def test_c28_the_line_and_its_place(tmp_path, monkeypatch):
    """C28: 17 alone is refused (C5, C8.4); under 18 is counted: the line comes after line 1
    and before the left-out line, word for word."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply, answers = widened_turn(env, [spec(Y25, [age(17, 17)])], [spec(Y25, [U18])])
    assert answers[0].get("error") == "NOT_ALLOWED"
    assert reply.reply_style == "agent", reply.draft_failures
    assert_reply(reply.text, "I counted 31 arrest records of people under 18 in 2025.",
                 left_out=[C28_LINE, age_left_out_line(5)], source=source_re(A))
    assert reply.text.count(C28_LINE) == 1
    checked(reply)


def test_c28_as_in_the_live_run_16_then_15_to_17(tmp_path, monkeypatch):
    """C28 as seen live: one year asked (16), refused, a wider range counted (here 15 to 17)."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply, _ = widened_turn(env, [spec(Y25, [age(16, 16)])], [spec(Y25, [age(15, 17)])])
    assert_reply(reply.text, "I counted 11 arrest records of people aged 15 to 17 in 2025.",
                 left_out=[C28_LINE, age_left_out_line(5)], source=source_re(A))


def test_c28_after_the_kept_note(tmp_path, monkeypatch):
    """C28: "after the kept note and before the left-out lines"."""
    env = CountyEnv(tmp_path, monkeypatch)
    first = env.ask(Q_COUNT, Step(count(A_ID, Y25)), Step(finish("finding", "I counted {r1.count}.")))
    assert first.status == "ANSWERED"
    reply = env.ask("And 16-year-olds?", Step(count(LEAVE_OUT, LEAVE_OUT, [age(16, 16)])),
                    Step(count(LEAVE_OUT, LEAVE_OUT, [age(15, 17)])),
                    Step(finish("finding", "I counted {r1.count}.")))
    assert env.model.answer(0).get("error") == "NOT_ALLOWED", env.model.answer(0)
    assert_reply(reply.text, "I counted 11 arrest records of people aged 15 to 17 in 2025.",
                 kept="(I kept 2025 from earlier.)",
                 left_out=[C28_LINE, age_left_out_line(5)], source=source_re(A, first=False))


def test_c28_in_the_fixed_rendering_and_not_in_details(tmp_path, monkeypatch):
    """C28: the line is in the fixed rendering too (the model's text fails the check);
    `details` does not repeat it."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply, _ = widened_turn(env, [spec(Y25, [age(17, 17)])], [spec(Y25, [U18])],
                            text=f"I counted {{r1.count}} {MARK}.")
    assert reply.reply_style == "fallback", (reply.reply_style, reply.draft_failures)
    assert_reply(reply.text, "I counted 31 arrest records of people under 18 in 2025.",
                 left_out=[C28_LINE, age_left_out_line(5)], source=source_re(A))
    # C36 point 5 (S3-R6-A): `details` goes to the model, which calls show_details
    details = env.ask("details", Step(show_details()))
    assert details.status == "DETAILS", (details.status, details.reason_code)
    assert C28_LINE not in details.text and "wider range" not in details.text, details.text


def test_c28_once_with_two_such_counts(tmp_path, monkeypatch):
    """C28 "Once per answer": two counts hold the refused year; the line once, then each
    count's left-out line (C19: named, with no brackets, in a reply with two counts). Changed by
    briefs/S3-R9-A-tests.md (C42 point 1: no left-out line) and changed back by
    briefs/S3-R13-A-tests.md (C49): the two named lines again (10 and fewer than 10 differ)."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply, _ = widened_turn(env, [spec(Y25, [age(17, 17)])],
                            [spec(year(2024), [U18]), spec(Y25, [U18])],
                            text="I counted {r1.count} and {r2.count}.")
    assert_reply(reply.text, "I counted 24 arrest records of people under 18 in 2024 and 31 "
                             "arrest records of people under 18 in 2025.",
                 left_out=[C28_LINE,
                           "For arrest records of people under 18 in 2024: 10 had no usable age "
                           "and are not included.",
                           "For arrest records of people under 18 in 2025: fewer than 10 had no "
                           "usable age and are not included."],
                 source=source_re(A))


def test_c28_once_with_two_such_refusals(tmp_path, monkeypatch):
    env = CountyEnv(tmp_path, monkeypatch)
    reply, _ = widened_turn(env, [spec(Y25, [age(16, 16)]), spec(Y25, [age(17, 17)])],
                            [spec(Y25, [U18])])
    assert reply.text.count(C28_LINE) == 1, reply.text
    assert_reply(reply.text, "I counted 31 arrest records of people under 18 in 2025.",
                 left_out=[C28_LINE, age_left_out_line(5)], source=source_re(A))


def test_c28_a_count_of_every_age_includes_the_year(tmp_path, monkeypatch):
    """R10: a count with no age filter has every usable age, so it holds the refused year."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply, _ = widened_turn(env, [spec(Y25, [age(17, 17)])], [spec(Y25)])
    assert_reply(reply.text, "I counted 240 arrest records in 2025.", left_out=[C28_LINE],
                 source=source_re(A))


def test_c28_coded_source(tmp_path, monkeypatch):
    """C28 on the other fixture (its age field is age_years)."""
    env = CountyEnv(tmp_path, monkeypatch, names=(C,))
    reply, answers = widened_turn(env, [spec(Y25, [age(15, 15, CODED_AGE)], name=C)],
                                  [spec(Y25, [age(None, 16, CODED_AGE)], name=C)])
    assert answers[0].get("error") == "NOT_ALLOWED", answers[0]
    assert_reply(reply.text, "I counted 41 intake records of people under 17 in 2025.",
                 left_out=[C28_LINE], source=source_re(C))


OWN_BANDS = [{"field": "age_band", "bands": [[10, 13], [14, 17]]}]
NO_LINE = {
    # id: the counts of one turn, in order (at least one is answered)
    "no count of the turn was refused": [call_of(spec(Y25, [U18]))],
    "the refusal was C21's (its ages are not one year)": [call_of(spec(Y25, [U18])),
                                                          call_of(spec(Y25, [U17]))],
    "the refusal was for bands of the model's own": [count(A_ID, Y25, [U18], OWN_BANDS),
                                                     call_of(spec(Y25, [U18]))],
    "the refusal was OUT_OF_COVERAGE": [call_of(spec(year(2019), [U18])),
                                        call_of(spec(Y25, [U18]))],
    "the refusal was TOO_FINE": [call_of(spec(Y25, [U18], ["district"])),
                                 call_of(spec(Y25, [U18]))],
    "the counted ages miss the refused year (17, then 18 to 24)":
        [call_of(spec(Y25, [age(17, 17)])), call_of(spec(Y25, [age(18, 24)]))],
    "the counted ages miss the refused year (16, then under 16)":
        [call_of(spec(Y25, [age(16, 16)])), call_of(spec(Y25, [U16]))],
}


@pytest.mark.parametrize("case", list(NO_LINE))
def test_c28_no_line(tmp_path, monkeypatch, case):
    """C28's line is not there when no single year under 18 was refused, or when no count of
    the reply holds the refused year (R9)."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask(Q_COUNT, Step(*NO_LINE[case]), Step(finish("finding", "I counted {r1.count}.")))
    assert reply.status == "ANSWERED" and reply.run_ids, (reply.status, reply.reason_code,
                                                          reply.text)
    assert C28_LINE not in reply.text and "wider range" not in reply.text, reply.text


def test_c28_not_in_a_later_turn(tmp_path, monkeypatch):
    """C28 "in this turn": the turn after the line has none."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply, _ = widened_turn(env, [spec(Y25, [age(17, 17)])], [spec(Y25, [U18])])
    assert C28_LINE in reply.text
    later, _ = widened_turn(env, [], [spec(year(2024), [U18])], question=Q_FOLLOW)
    assert later.status == "ANSWERED" and C28_LINE not in later.text, later.text


def test_c28_not_after_a_turn_that_only_refused(tmp_path, monkeypatch):
    """C28 "in this turn": a turn that only refused 17, then a turn that counts under 18."""
    env = CountyEnv(tmp_path, monkeypatch)
    refused, _ = widened_turn(env, [spec(Y25, [age(17, 17)])], [])
    assert refused.reason_code == "NOT_ALLOWED", (refused.status, refused.reason_code)
    assert refused.text.startswith(NOT_ALLOWED_ROW), refused.text
    later, _ = widened_turn(env, [], [spec(Y25, [U18])], question=Q_FOLLOW)
    assert later.status == "ANSWERED" and C28_LINE not in later.text, later.text


def test_c28_open_the_count_made_before_the_refusal(tmp_path, monkeypatch):
    """R9, answered (S3A-DESIGN, answer 5): under 18 counted first, then 17 alone refused;
    "the reply then holds" a count with 17, whatever the order, so the line is added (after
    line 1, before the left-out line)."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask(Q_COUNT, Step(call_of(spec(Y25, [U18])), call_of(spec(Y25, [age(17, 17)]))),
                    Step(finish("finding", "I counted {r1.count}.")))
    assert env.model.answer(0, 1).get("error") == "NOT_ALLOWED"
    assert_reply(reply.text, "I counted 31 arrest records of people under 18 in 2025.",
                 left_out=[C28_LINE, age_left_out_line(5)], source=source_re(A))
