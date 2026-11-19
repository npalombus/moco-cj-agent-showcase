"""The reply in county mode: docs/S3A-DESIGN.md C10 (line 1, then what Python adds, in its
order), C6's last paragraph (`{rN.groups}` and `{rN.share}` follow R1's rules for a slot;
`{rN.groups}` comes straight after its own `{rN.count}`), C13 for county slots, and C12's
"the hidden line exactly when a group is hidden; left out counted and said; the sensitive
line exactly when C10 says" and "R1's check accepts and refuses the new slots as it does
the old ones".

What this file covers
- The order of the parts: line 1; the table (one line per group, `<label>: <n>`, at most
  12) or `The full table is in the details.` (13 groups or more, or a two-way breakdown);
  the kept note; the left-out line; the hidden line; the sensitive line; the source line,
  every part at once and each alone.
- The source line: the first answer of a thread names the source's title, the copy's date
  and the unit (`A count is of <unit many>, not people.`); later answers carry
  `(County open data, copy of <date>.)`; on both fixtures.
- The sensitive line exactly when the spec filters or breaks down by a sensitive field
  (gender, race, ethnicity; coded race and sex), and not for age, a place or a flag.
- The hidden line exactly when a group is hidden, also when the table is in the details.
- The fixed rendering (a text that fails the check, or MOCO_REPLY_STYLE=fixed): `I counted
  <count phrase>.` then ` <Groups phrase>.` per result, then the share and compare phrases
  as sentences; nothing the model wrote is in it.
- R1's one check with C6's slots and C13: texts that pass, and texts that fail with exactly
  one code (SLOT, GLUE, CHARS, WORD, SHAPE) for `{rN.groups}`, `{rN.share}` and
  `{rN.compare}`, checked directly (replies.check_finding on a county turn's results) and
  end to end.

Readings taken (kit-log/raw/S3A-A-notes.txt)
- The parts Python adds are joined by one space, one line break or one blank line; the
  table starts on a new line (s3support.reply_re).
- County results offer `{rN.count}` (and `{rN.groups}` for a one-way breakdown), `{rN.share}`
  and `{rN.compare}`; `{rN.months}` is not offered in county mode (C5's slots list).
- In the fixed rendering a share or compare sentence that starts with a letter may take a
  capital or not (as P1's reading for render_fixed's compare sentence); the tests use ones
  that start with a number.
"""
import pytest

from p1support import (LEAVE_OUT, MARK, R1_CODES, Step, finish, mod, odd_chars, unlisted_words)
from s3support import (A_ID, C_ID, Q_BREAKDOWN, Q_COMPARE, Q_COUNT, Q_FOLLOW, SCHOOL,
                       CountyEnv, age, assert_reply, check_county_reply, compare,
                       count, dates, hidden_line, in_, is_, left_out_line, sensitive_line,
                       share, source_json, source_re, table_lines, truth, year)

PAGE_A = source_json("arrests_like")["page"]
SENSITIVE_A = sensitive_line("arrest records")
TEXT = "I counted {r1.count}."
TEXT_GROUPS = "I counted {r1.count}. {r1.groups}."


def answer(env, spec, text=TEXT, question=Q_BREAKDOWN, sid=A_ID, **kw):
    reply = env.ask(question, Step(count(sid, *spec)), Step(finish("finding", text)), **kw)
    check_county_reply(reply)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    return reply


# ---- the parts and their order ---------------------------------------------------------------

def test_a_plain_count_is_line_1_and_the_first_source_line(tmp_path, monkeypatch):
    """C10: with nothing else to add, line 1 then the source line; the first answer of a
    thread names the source's title, the copy's date and its unit (C1)."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply = answer(env, (year(2025),), question=Q_COUNT)
    assert (reply.reply_kind, reply.reply_style) == ("finding", "agent")
    assert_reply(reply.text, "I counted 240 arrest records in 2025.",
                 source=source_re("arrests_like", first=True))


def test_a_later_answer_carries_the_short_source_line(tmp_path, monkeypatch):
    """C10.6 with C18: later answers of the thread: `(<title>, county open data, copy of
    <date>.)`."""
    env = CountyEnv(tmp_path, monkeypatch)
    answer(env, (year(2025),), question=Q_COUNT)
    reply = answer(env, (year(2024),), question=Q_FOLLOW)
    assert_reply(reply.text, "I counted 230 arrest records in 2024.",
                 source=source_re("arrests_like", first=False))


def test_every_part_at_once_in_its_order(tmp_path, monkeypatch):
    """C10: line 1, the table, the kept note, the left-out line, the hidden line, the
    sensitive line, the source line. 2025 kept; group Alpha by district: 16, 9, 7, 4, 14 and
    14 (three of six hidden: not more than half), one record with no district."""
    spec = (year(2025), [is_("race", "group Alpha")], ["district"])
    t = truth("arrests_like", *spec)
    assert list(t["groups"].values()) == [16, 9, 7, 4, 14, 14]
    assert t["left_out"] == {"race": 0, "district": 1}
    env = CountyEnv(tmp_path, monkeypatch)
    answer(env, (year(2025),), question=Q_COUNT)
    reply = answer(env, (LEAVE_OUT, [is_("race", "group Alpha")], ["district"]),
                   text=TEXT_GROUPS, question=Q_FOLLOW)
    line1 = ("I counted 64 arrest records of people recorded as group Alpha in 2025 with a "
             "district recorded. By district, district 1 had the most (16) and district 2, "
             "district 3 and district 4 the fewest (fewer than 10 each).")
    assert_reply(reply.text, line1,
                 table=["district 1: 16", "district 2: fewer than 10", "district 3: fewer than 10",
                        "district 4: fewer than 10", "district 5: 14", "district 6: 14"],
                 kept="(I kept 2025 from earlier.)",
                 left_out=["(fewer than 10 had no district recorded and are not included.)"],
                 hidden=hidden_line(PAGE_A), sensitive=SENSITIVE_A,
                 source=source_re("arrests_like", first=False))


def test_the_coded_fixture_speaks_of_its_own_unit_and_title(tmp_path, monkeypatch):
    """C10 with C3: the unit and the title come from the source file: `intake records`,
    in line 1, the sensitive line and the source line; its labels and dimension in the
    table and the left-out line."""
    spec = (year(2025), [is_("race_code", "group W")], ["station"])
    t = truth("coded_like", *spec)
    assert dict(t["groups"]) == {"station 1": 27, "station 2": 33, "station 3": 27}
    env = CountyEnv(tmp_path, monkeypatch, names=("coded_like",))
    reply = answer(env, spec, sid=C_ID)
    assert_reply(reply.text, "I counted 87 intake records of people recorded as group W in 2025 "
                             "with a station recorded.",
                 table=["station 1: 27", "station 2: 33", "station 3: 27"],
                 left_out=[left_out_line(3, "station")],
                 hidden_optional=source_json("coded_like")["page"],
                 sensitive=sensitive_line("intake records"),
                 source=source_re("coded_like", first=True))


# ---- the table: at most 12 lines -------------------------------------------------------------------

def test_twelve_groups_are_listed(tmp_path, monkeypatch):
    """C10.1: one line per group, at most 12 lines: 2025 by month."""
    t = truth("arrests_like", year(2025), [], ["month"])
    assert len(t["groups"]) == 12 and min(t["groups"].values()) >= 10
    env = CountyEnv(tmp_path, monkeypatch)
    reply = answer(env, (year(2025), [], ["month"]))
    assert_reply(reply.text, "I counted 240 arrest records in 2025.",
                 table=table_lines(t["groups"]), source=source_re("arrests_like"))
    assert "January 2025: 19" in reply.text and "July 2025: 30" in reply.text


def test_thirteen_groups_are_in_the_details_only(tmp_path, monkeypatch):
    """C10.1: a longer table is given in details only, with `The full table is in the
    details.`: January 2025 to January 2026 by month."""
    spec = (dates("2025-01-01", "2026-01-31"), [], ["month"])
    t = truth("arrests_like", *spec)
    assert len(t["groups"]) == 13 and min(t["groups"].values()) >= 10
    env = CountyEnv(tmp_path, monkeypatch)
    reply = answer(env, spec)
    assert_reply(reply.text, "I counted 257 arrest records from 1 January 2025 to 31 January "
                             "2026.", full_table=True, source=source_re("arrests_like"))
    assert "January 2025:" not in reply.text


def test_a_long_table_with_hidden_groups_still_gets_the_hidden_line(tmp_path, monkeypatch):
    """C10.1 and C8.2: 2025 by hour (24 groups, five of them 9) is in the details only, and
    the hidden line comes because a group is hidden."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply = answer(env, (year(2025), [], ["hour"]))
    assert_reply(reply.text, "I counted 240 arrest records in 2025.", full_table=True,
                 hidden=hidden_line(PAGE_A), source=source_re("arrests_like"))


def test_a_two_way_breakdown_is_in_the_details_only(tmp_path, monkeypatch):
    """C10.1: a two-way breakdown is given in details only. 2026 by district and gender has
    three groups hidden (7, 6, 9): the hidden line; gender: the sensitive line."""
    t = truth("arrests_like", year(2026), [], ["district", "gender"])
    assert sorted(n for n in t["grid"].values() if n < 10) == [6, 7, 9]
    env = CountyEnv(tmp_path, monkeypatch)
    reply = answer(env, (year(2026), [], ["district", "gender"]))
    assert_reply(reply.text, "I counted 130 arrest records in 2026 (through 17 September 2026, "
                             "the latest in this copy).", full_table=True,
                 hidden=hidden_line(PAGE_A), sensitive=SENSITIVE_A,
                 source=source_re("arrests_like"))
    assert "district 1:" not in reply.text


# ---- the sensitive line: exactly when C10 says -----------------------------------------------------

SENSITIVE = {
    # id: (fixture, filters, group_by, the line is there)
    "a gender filter": ("arrests_like", [is_("gender", "female")], [], True),
    "an ethnicity filter": ("arrests_like", [is_("ethnicity", "Hispanic")], [], True),
    "by race": ("arrests_like", [], ["race"], True),
    "by gender and district": ("arrests_like", [], ["district", "gender"], True),
    "an age filter": ("arrests_like", [age(18, 21)], [], False),
    "by age band": ("arrests_like", [], ["age_band"], False),
    "a district filter": ("arrests_like", [in_("district", "district 3", "district 4")], [],
                          False),
    "by flag": ("arrests_like", [], [SCHOOL], False),
    "by month": ("arrests_like", [], ["month"], False),
    "coded: a race filter": ("coded_like", [is_("race_code", "group B")], [], True),
    "coded: by sex": ("coded_like", [], ["sex"], True),
    "coded: by station": ("coded_like", [], ["station"], False),
}


@pytest.mark.parametrize("case", list(SENSITIVE))
def test_the_sensitive_line_exactly_when_a_sensitive_field_is_used(tmp_path, monkeypatch, case):
    """C10.5: `These are counts of <unit many>, not rates, and they show no cause.` when the
    spec filters or breaks down by a `sensitive` field, and only then."""
    name, filters, group_by, there = SENSITIVE[case]
    env = CountyEnv(tmp_path, monkeypatch, names=(name,))
    reply = answer(env, (year(2025), filters, group_by), sid=source_json(name)["id"])
    line = sensitive_line(source_json(name)["unit"]["many"])
    assert (line in reply.text) is there, reply.text
    assert reply.text.count("not rates") == (1 if there else 0)


def test_no_hidden_line_when_no_group_is_hidden(tmp_path, monkeypatch):
    """C12: the hidden line exactly when a group is hidden: 2024 by district (groups 20 to
    45, ten left out) has none."""
    env = CountyEnv(tmp_path, monkeypatch)
    t = truth("arrests_like", year(2024), [], ["district"])
    reply = answer(env, (year(2024), [], ["district"]))
    assert_reply(reply.text, "I counted 220 arrest records in 2024 with a district recorded.",
                 table=table_lines(t["groups"]), left_out=[left_out_line(10, "district")],
                 source=source_re("arrests_like"))
    assert "not shown here" not in reply.text


# ---- the fixed rendering (C10) -----------------------------------------------------------------------

def test_the_fixed_rendering_of_a_breakdown(tmp_path, monkeypatch):
    """C10: when the check fails, `I counted <count phrase>.` then ` <Groups phrase>.`; the
    rest as before; nothing the model wrote reaches the reply."""
    env = CountyEnv(tmp_path, monkeypatch)
    spec = (year(2025), [is_(SCHOOL, True)], ["district"])
    reply = env.ask(Q_BREAKDOWN, Step(count(A_ID, *spec)),
                    Step(finish("finding", f"I counted {{r1.count}} {MARK}.")))
    check_county_reply(reply)
    assert reply.reply_style == "fallback" and "WORD" in reply.draft_failures, \
        (reply.reply_style, reply.draft_failures)
    t = truth("arrests_like", *spec)
    assert_reply(reply.text, "I counted 75 arrest records within 500 feet of a school in 2025 "
                             "with a district recorded. By district, district 6 had the most "
                             "(31) and district 4 the fewest (0).",
                 table=table_lines(t["groups"]), left_out=[left_out_line(1, "district")],
                 hidden=hidden_line(PAGE_A), source=source_re("arrests_like"))
    assert MARK not in reply.text


def test_moco_reply_style_fixed_never_uses_the_text(tmp_path, monkeypatch):
    """R1 with C10: MOCO_REPLY_STYLE=fixed gives the fixed rendering, style `fixed`."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_REPLY_STYLE="fixed")
    reply = answer(env, (year(2026), [], ["gender"]), text=TEXT_GROUPS)
    assert reply.reply_style == "fixed"
    assert_reply(reply.text, "I counted 130 arrest records in 2026 (through 17 September 2026, "
                             "the latest in this copy). By gender, every group had the same "
                             "count (65).",
                 table=["female: 65", "male: 65"], sensitive=SENSITIVE_A,
                 source=source_re("arrests_like"))


@pytest.mark.parametrize("case", ["two counts", "a compare", "a share"])
def test_the_fixed_rendering_of_several_results(tmp_path, monkeypatch, case):
    """C10: per result `I counted <count phrase>.`, then the share and compare phrases as
    sentences."""
    env = CountyEnv(tmp_path, monkeypatch)
    if case == "two counts":
        steps = [Step(count(A_ID, year(2024)), count(A_ID, year(2025)))]
        line1 = "I counted 230 arrest records in 2024. I counted 240 arrest records in 2025."
    elif case == "a compare":
        steps = [Step(count(A_ID, year(2024)), count(A_ID, year(2025))),
                 Step(compare("r1", "r2"))]
        line1 = ("I counted 230 arrest records in 2024. I counted 240 arrest records in 2025. "
                 "2025 had the highest count (240) and 2024 the lowest (230), a difference of "
                 "10.")
    else:
        steps = [Step(count(A_ID, year(2025)), count(A_ID, year(2025), [is_(SCHOOL, True)])),
                 Step(share("r2", "r1"))]
        line1 = ("I counted 240 arrest records in 2025. I counted 76 arrest records within 500 "
                 "feet of a school in 2025. 32% of the 240 arrest records in 2025 were within "
                 "500 feet of a school.")
    reply = env.ask(Q_COMPARE, *steps, Step(finish("finding", f"I counted {MARK} {{r1.count}}.")))
    check_county_reply(reply)
    assert reply.reply_style == "fallback", reply.draft_failures
    assert_reply(reply.text, line1, source=source_re("arrests_like"))


# ---- R1's check with the new slots (C6, C12, C13) ----------------------------------------------------

def turn_results(tmp_path, monkeypatch, kind):
    """reply.results of one county turn: `breakdown`: r1 2025 near a school by district (a
    one-way breakdown), r2 2025 (a single count); `share`: r1 2025, r2 2025 near a school,
    r3 the share of r2 in r1; `compare`: r1 2024, r2 2025, r3 their compare."""
    env = CountyEnv(tmp_path / kind, monkeypatch)
    if kind == "breakdown":
        steps = [Step(count(A_ID, year(2025), [is_(SCHOOL, True)], ["district"]),
                      count(A_ID, year(2025)))]
    elif kind == "share":
        steps = [Step(count(A_ID, year(2025)), count(A_ID, year(2025), [is_(SCHOOL, True)])),
                 Step(share("r2", "r1"))]
    else:
        steps = [Step(count(A_ID, year(2024)), count(A_ID, year(2025))), Step(compare("r1", "r2"))]
    reply = env.ask(Q_COMPARE, *steps, Step(finish("finding", TEXT)))
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert len(reply.results) == (2 if kind == "breakdown" else 3), reply.results
    return reply.results


PASSING = [
    ("breakdown", "I counted {r1.count}. {r1.groups}."),
    ("breakdown", "I counted {r1.count} and {r1.groups}."),
    ("breakdown", "I counted {r1.count}, and {r1.groups}."),
    ("breakdown", "{r1.count}. {r1.groups}. I also counted {r2.count}."),
    ("share", "Here is what I found: {r3.share}."),
    ("share", "I counted {r1.count} and {r2.count}. {r3.share}."),
    ("compare", "Here is the comparison: {r3.compare}."),
    ("compare", "I counted {r1.count} and {r2.count}. Here is the comparison: {r3.compare}."),
]

FAILING = [
    # (turn, code, text)
    ("breakdown", "SLOT", "{r1.groups}."),
    ("breakdown", "SLOT", "I counted {r2.count}. {r1.groups}."),
    ("breakdown", "SLOT", "I counted {r2.count}. {r2.groups}."),
    ("breakdown", "SLOT", "I counted {r1.count}. {r1.months}."),
    ("breakdown", "SLOT", "I counted {r1.total}."),
    ("breakdown", "SLOT", "I counted {r1.count}. {r1.count}."),
    ("breakdown", "SLOT", "{f1}."),
    ("share", "SLOT", "Here is what I found: {r1.share}."),
    ("breakdown", "GLUE", "I counted {r1.count}{r1.groups}."),
    ("breakdown", "GLUE", "I counted {r1.count} {r1.groups}."),
    ("breakdown", "GLUE", "I counted {r1.count}, so {r1.groups}."),
    ("breakdown", "GLUE", "I counted {r1.count} as {r2.count}."),
    ("share", "GLUE", "Here is what I found:{r3.share}."),
    ("share", "GLUE", "{r1.count} of the {r2.count}."),
    ("compare", "GLUE", "Here is the comparison: {r3.compare}, so {r1.count}."),
    ("breakdown", "CHARS", "I counted {r1.count} ."),
    ("breakdown", "CHARS", "I counted {r1.count} (2)."),
    ("share", "CHARS", "Here is what I found: {r3.share} %."),
    ("breakdown", "WORD", "I counted {r1.count} in the district."),
    ("share", "WORD", "Here is the share: {r3.share}."),
    ("share", "WORD", "Here is the rate: {r3.share}."),
    ("compare", "WORD", "Here is the change: {r3.compare}."),
    ("breakdown", "SHAPE", "I counted {r1.count}. {r1.groups}. That is it. Thanks. Thank you."),
]


def premise(code, text):
    """The text fails for one reason only: its words are listed and its marks allowed,
    except the word (WORD) or the mark (CHARS) it is about."""
    if code != "WORD":
        assert not unlisted_words(text), (text, unlisted_words(text))
    if code != "CHARS":
        assert not odd_chars(text), (text, odd_chars(text))


@pytest.mark.parametrize("kind, text", PASSING)
def test_r1s_check_accepts_the_new_slots(tmp_path, monkeypatch, kind, text):
    """C6 and C12: `{rN.groups}` straight after its own count, `{rN.share}` and
    `{rN.compare}` pass R1's one check like the old slots."""
    premise(None, text)
    replies = mod("replies")
    results = turn_results(tmp_path, monkeypatch, kind)
    assert replies.check_finding(text, results, replies.load_words()) == [], text


@pytest.mark.parametrize("kind, code, text", FAILING)
def test_r1s_check_refuses_the_new_slots_with_exactly_one_code(tmp_path, monkeypatch, kind, code,
                                                               text):
    """C6, C12 and C13: a misplaced, unknown, glued or repeated slot, a slot joined by more
    than `and`, a private-use character, a digit, an unlisted word, five sentences: each
    fails with exactly its code."""
    premise(code, text)
    replies = mod("replies")
    results = turn_results(tmp_path, monkeypatch, kind)
    got = replies.check_finding(text, results, replies.load_words())
    assert isinstance(got, list) and set(got) <= R1_CODES, got
    assert set(got) == {code}, (text, got)


@pytest.mark.parametrize("text, code", [
    ("{r1.count} of the {r2.count}.", "GLUE"),
    ("I counted {r1.count} .", "CHARS"),
    ("{r1.groups}.", "SLOT"),
])
def test_a_refused_text_end_to_end_gives_the_fixed_rendering(tmp_path, monkeypatch, text, code):
    """C10 and C13 end to end: the finding fails, the fixed rendering is sent, style
    fallback, the code in draft_failures, and none of the model's own text in the reply."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask(Q_BREAKDOWN, Step(count(A_ID, year(2025), [is_(SCHOOL, True)], ["district"]),
                                      count(A_ID, year(2025))),
                    Step(finish("finding", text)))
    check_county_reply(reply)
    assert reply.reply_style == "fallback" and code in reply.draft_failures, \
        (reply.reply_style, reply.draft_failures)
    assert reply.text.startswith("I counted 75 arrest records within 500 feet of a school in "
                                 "2025 with a district recorded. By district, district 6 had the "
                                 "most (31) and district 4 the fewest (0). I counted 240 arrest "
                                 "records in 2025."), reply.text
    assert " of the 240" not in reply.text
    assert not any("" <= ch <= "" for ch in reply.text)
