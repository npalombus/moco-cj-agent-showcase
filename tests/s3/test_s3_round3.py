"""Stage 3 Part A, round 3: docs/S3A-DESIGN.md C23 ("With three or more sources, 'what I can
do' is short") and its "What the round 3 tests must show":

1. With the two fixture sources (and with each alone), the three texts are exactly what they
   are today: the sentence that ends a refusal, `help`, and the question Python asks when
   the source is missing. Written out by hand; these tests pass on today's program.
2. With three sources (the two fixtures and a third made-up one in tests/s3/fixtures/round3/,
   made by make_round3_fixture.py), each of the three new texts exactly, written out by hand
   from C23.
3. One refusal of every row that carries the sentence ends with the short form.
4. With the thirteen real source FILES loaded (config/sources/ read where it is: no copy, no
   network), no refusal text is longer than 400 characters. Lengths only: nothing from those
   files is quoted here, and a failure shows only a length and a reason code.
And C23's last rule: `about the data` does not change with three sources. (C39, changed by
briefs/S3-R7-A-tests.md: with three or more sources the about text is C39's short one; its own
tests are tests/s3/test_s3_c39.py.)

C36 point 5 (D-065; changed by briefs/S3-R6-A-tests.md): `help` in county mode goes to the agent
like any message, so the help tests check that the agent's reply is posted; HELP_TODAY and
HELP_THREE are kept as written, for reference, and no longer reach Slack.

Readings (each in kit-log/raw/S3A-R3-A-notes.txt):
- "every row of C5's table that carries it": C5's table is the count tool's error table; the
  rows that end with the "what I can do" sentence are A7's fixed rows as county mode words
  them (docs/P1A-DESIGN.md A7; C5's errors among them when every count of a turn failed).
  Taken as: every county row whose text ends with the sentence today. The rows a turn can
  end on are reached through a turn; six that no turn ends on today (an error of share or
  compare comes after a count that worked, INVALID_ARGUMENTS is not made in county mode, and
  a refused analysis ends with its own line) are checked through replies.county_text, the
  function that words county rows today.
- <n> is written in digits (`3`), as Python writes every other number (C6).
- "in file order": the order load_sources gives (files sorted by name). The third fixture's
  file name sorts last, so it is also the order the files were written.
- <place> in help's example is not defined in C23: taken as today's help takes it (the first
  source's first category that is not a person field: `district` for arrests_like).
- <n> counts the sources offered (the source files that load), not the copies.
- C1: no count from 1 to 9 stands as a figure. The number of sources is not a count from the
  data, but s3support's figure check would read a `3` as one, so it is run with C23's
  source-count phrases taken out.
"""
import dataclasses
import importlib.util
import json

import pytest

from p1support import (AGENT_USER, LEAVE_OUT, FakeAgent, FakeSlack, Step, ask_user, call,
                       decline, finish, load_registry, make_reply, mention, mod, process,
                       slack_settings)
from s3support import (A_ID, C_ID, COPY_NOW, FIXTURES, NAMES, Q_ABOUT, Q_COUNT, REAL_SOURCES,
                       CountyEnv, FakeService, age, check_county_reply, count, is_,
                       source_json, use_sources, year)

ROUND3 = FIXTURES / "round3"
V_ID = "FIXTURE:visits_like"


def visits_source():
    return json.loads((ROUND3 / "sources" / "visits_like.json").read_text(encoding="utf-8"))


def visits_rows():
    return json.loads((ROUND3 / "rows" / "visits_like.json").read_text(encoding="utf-8"))["rows"]


# ---- the texts, written out by hand ----------------------------------------------------------

# Today's "what I can do" sentence, one per source (C11 as built; C23: kept for one or two).
LONG_A = ("I can count arrest records from SYNTHETIC fixture arrests (made up for tests) for any "
          "period its copy covers, filtered or broken down by age, gender, race, ethnicity, "
          "district, distance from a school, year, month, day of the week and hour, and compare "
          "those counts or give one as a share of another.")
LONG_C = ("I can count intake records from SYNTHETIC fixture intake records (made up for tests) "
          "for any period its copy covers, filtered or broken down by age, race, sex, station, "
          "year, month, day of the week and hour, and compare those counts or give one as a "
          "share of another.")
LONG_V = ("I can count visit records from SYNTHETIC fixture visits (made up for tests) for any "
          "period its copy covers, filtered or broken down by area, year, month, day of the "
          "week and hour, and compare those counts or give one as a share of another.")
LONG_PART = "for any period its copy covers"  # in every long sentence, in no short text

ENDS_TODAY = {
    ("arrests_like",): " " + LONG_A,
    ("coded_like",): " " + LONG_C,
    ("arrests_like", "coded_like"): " " + LONG_A + " " + LONG_C,
}

HELP_TODAY = {
    ("arrests_like",): (
        'I count records in county open data. I can count arrest records from SYNTHETIC '
        'fixture arrests (made up for tests) for any period its copy covers, filtered or broken '
        'down by age, gender, race, ethnicity, district, distance from a school, year, month, '
        'day of the week and hour, and compare those counts or give one as a share of another. '
        'Ask in your own words. For example: "How many arrest records were there last year, by '
        'district?" Then follow up, for example "and the year before?". I never show a single '
        'record. Say "details" for the full breakdown of my last answer, or "reset" to make me '
        'forget this conversation.'),
    ("coded_like",): (
        'I count records in county open data. I can count intake records from SYNTHETIC '
        'fixture intake records (made up for tests) for any period its copy covers, filtered '
        'or broken down by age, race, sex, station, year, month, day of the week and hour, and '
        'compare those counts or give one as a share of another. Ask in your own words. For '
        'example: "How many intake records were there last year, by station?" Then follow up, '
        'for example "and the year before?". I never show a single record. Say "details" for '
        'the full breakdown of my last answer, or "reset" to make me forget this '
        'conversation.'),
    ("arrests_like", "coded_like"): (
        'I count records in county open data. I can count arrest records from SYNTHETIC '
        'fixture arrests (made up for tests) for any period its copy covers, filtered or broken '
        'down by age, gender, race, ethnicity, district, distance from a school, year, month, '
        'day of the week and hour, and compare those counts or give one as a share of another. '
        'I can count intake records from SYNTHETIC fixture intake records (made up for tests) '
        'for any period its copy covers, filtered or broken down by age, race, sex, station, '
        'year, month, day of the week and hour, and compare those counts or give one as a share '
        'of another. Ask in your own words. For example: "How many arrest records were there '
        'last year, by district?" Then follow up, for example "and the year before?". I never '
        'show a single record. Say "details" for the full breakdown of my last answer, or '
        '"reset" to make me forget this conversation.'),
}

QUESTION_TODAY = ("Which source do you mean: SYNTHETIC fixture arrests (made up for tests) or "
                  "SYNTHETIC fixture intake records (made up for tests)?")

# C23, with three sources.
# Changed by briefs/S3-R21-A-tests.md (C57 point 1 of docs/S3A-DESIGN.md; the last sentence was
# 'Say "help" for the list.').
SHORT = ('I can count records from 3 county sources, filter them, break them down, compare '
         'counts and give one as a share of another. Ask "what data do you have?" for the list.')
HELP_THREE = (
    'I count records in county open data. I have 3 sources: arrest records, intake records '
    'and visit records. Ask in your own words. For example: "How many arrest records were '
    'there last year, by district?" Then follow up, for example "and the year before?". Ask '
    '"what data do you have?" for what each source covers and how it can be broken down. I '
    'never show a single record. Say "details" for the full breakdown of my last answer, or '
    '"reset" to make me forget this conversation.')
QUESTION_THREE = ("Which source do you mean? I have 3: arrest records, intake records and visit "
                  "records.")
SOURCE_COUNT_PHRASES = (SHORT, "I have 3 sources:", "I have 3:")
LIMIT = 400


# ---- setting up ------------------------------------------------------------------------------

def add_visits(env, copy=True):
    """Write the third source file into the env's sources folder and, with `copy`, make its
    copy through the fake transport (as CountyEnv does for the two older fixtures)."""
    src = visits_source()
    (env.sources_dir / "visits_like.json").write_text(json.dumps(src, indent=2),
                                                      encoding="utf-8")
    if copy:
        service = FakeService(visits_rows(), address=src["address"])
        mod("sources").fetch(V_ID, state_dir=env.state_dir, transport=service, now=COPY_NOW)
    return env


def three_sources(tmp_path, monkeypatch):
    """The two fixtures and the third, each with a copy."""
    return add_visits(CountyEnv(tmp_path, monkeypatch, names=NAMES))


def real_files(tmp_path, monkeypatch):
    """A county-mode agent offered the thirteen real source files, read in place from
    config/sources/: no copy is made and nothing is fetched."""
    env = CountyEnv(tmp_path, monkeypatch, names=())
    use_sources(monkeypatch, REAL_SOURCES)
    assert len(mod("sources").county_sources()) >= 3, "premise: three or more real files load"
    return env


AGENT_HELP_REPLY = "The agent's own reply to help (SYNTHETIC test data)."  # C36 point 5


def help_text(env, tmp_path):
    """`help` in county mode, through Slack (as tests/s3/test_s3_about_details.py asks it).
    Changed by briefs/S3-R6-A-tests.md (C36 point 5, D-065; was: Python posted C11's and C23's
    help and the agent was not called): `help` goes to the agent like any message, and the
    agent's reply is what is posted."""
    settings = slack_settings(tmp_path, MOCO_DATA="county", MOCO_STATE_DIR=str(env.state_dir))
    slack = FakeSlack()
    agent = FakeAgent(make_reply("EXPLAINED", text=AGENT_HELP_REPLY))
    label = process(mention(f"<@{AGENT_USER}> help"), settings=settings, store=env.store,
                    agent=agent, slack=slack)
    assert label == "explained" and [c[0] for c in agent.calls] == ["help"], (label, agent.calls)
    (post,) = slack.posts
    return post[3]


def checked(reply):
    """check_county_reply, with C23's source-count phrases taken out first (see the readings)."""
    text = reply.text
    for phrase in SOURCE_COUNT_PHRASES:
        text = text.replace(phrase, " ")
    check_county_reply(dataclasses.replace(reply, text=text))
    return reply


def ended_by_count(*calls):
    """Every count of the turn fails, then the model finishes: the row of that error (A7)."""
    return [Step(*calls), Step(finish("finding", "I counted {r1.count}."))]


# The rows that carry the sentence and that a turn can end on: the stand-in model's steps and
# the reason code the turn ends with. The counts are of arrests_like, which every env here has.
ROWS = {
    "UNRECOGNIZED_QUESTION": (lambda: [Step(decline("UNRECOGNIZED_QUESTION"))],
                              "UNRECOGNIZED_QUESTION"),
    "UNSUPPORTED_METRIC": (lambda: [Step(decline("UNSUPPORTED_METRIC"))],
                           "UNSUPPORTED_METRIC"),
    "UNSUPPORTED_FIELD": (lambda: [Step(decline("UNSUPPORTED_FIELD"))], "UNSUPPORTED_FIELD"),
    "REAL_DATA_NOT_AVAILABLE": (lambda: [Step(decline("REAL_DATA_NOT_AVAILABLE"))],
                                "REAL_DATA_NOT_AVAILABLE"),
    "NEEDS_CLARIFICATION other": (lambda: [Step(ask_user("other"))], "NEEDS_CLARIFICATION"),
    "BACKGROUND_OFF": (lambda: [Step(finish("background", "Some general background."))],
                       "BACKGROUND_OFF"),
    "OUT_OF_COVERAGE": (lambda: ended_by_count(count(A_ID, year(2019))), "OUT_OF_COVERAGE"),
    "NOT_ALLOWED": (lambda: ended_by_count(count(A_ID, year(2025), [age(17, 17)])),
                    "NOT_ALLOWED"),
    "TOO_FINE": (lambda: ended_by_count(count(A_ID, year(2026), [], ["race"])), "TOO_FINE"),
    "BAD_FIELD": (lambda: ended_by_count(count(A_ID, year(2025), [is_("no_such_field", "x")])),
                  "BAD_FIELD"),
    "BAD_VALUE": (lambda: ended_by_count(count(A_ID, year(2025),
                                               [is_("district", "district 99")])),
                  "BAD_VALUE"),
    "TOO_MANY": (lambda: ended_by_count(count(A_ID, year(2025), [],
                                              ["district", "gender", "race"])), "TOO_MANY"),
    "BAD_OPTIONS": (lambda: ended_by_count(call("analyze", {"kind": "no_such_kind",
                                                            "source": A_ID,
                                                            "period": year(2025)})),
                    "BAD_OPTIONS"),
}

# The rows that carry the sentence today and that no turn ends on (see the readings).
ROWS_NO_TURN = ("BAD_SHARE", "BAD_COMPARE", "MIXED_SOURCES", "PARTIAL_YEAR",
                "INVALID_ARGUMENTS", "TOO_LITTLE")


def refusal(env, row):
    steps, code = ROWS[row]
    reply = env.ask(Q_COUNT, *steps())
    assert reply.reason_code == code, (row, reply.status, reply.reason_code, reply.text)
    assert reply.run_ids == [], "a refusal counts nothing"
    return reply


def county_row(code, sources):
    return mod("replies").county_text(code, sources, {}, load_registry())


# ---- the third fixture ----------------------------------------------------------------------

def test_the_third_fixture_is_plainly_made_up_and_has_its_own_unit_words():
    src, rows = visits_source(), visits_rows()
    assert src["id"] == V_ID and src["id"].startswith("FIXTURE:")
    assert "SYNTHETIC" in src["title"] and "SYNTHETIC" in src["publisher"]
    assert all("SYNTHETIC" in notice for notice in src["notices"])
    assert src["address"].startswith("https://fixture.invalid/")
    assert src["page"].startswith("https://fixture.invalid/")
    assert rows and all(r["id"].startswith("FIXTURE-") and r["data_class"] == "SYNTHETIC"
                        for r in rows)
    assert len({r["id"] for r in rows}) == len(rows)
    others = {source_json(name)["unit"]["many"] for name in NAMES}
    assert src["unit"]["many"] not in others and src["unit"]["one"] not in others
    assert set(mod("sources").load_sources(ROUND3 / "sources")) == {V_ID}


def test_the_third_fixture_is_what_its_script_makes():
    """The fixed seed: the script's source and rows are the files (nothing is written)."""
    spec = importlib.util.spec_from_file_location("make_round3_fixture",
                                                  FIXTURES / "make_round3_fixture.py")
    maker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(maker)
    assert maker.VISITS_LIKE == visits_source()
    assert maker.make_rows() == visits_rows()


def test_three_sources_premise(tmp_path, monkeypatch):
    """The three-source env offers the three sources, in this order, each with a copy."""
    env = three_sources(tmp_path, monkeypatch)
    assert list(mod("sources").county_sources()) == [A_ID, C_ID, V_ID]
    assert mod("sources").latest(V_ID, state_dir=env.state_dir) is not None


# ---- one or two sources: exactly as today ----------------------------------------------------

@pytest.mark.parametrize("names", list(HELP_TODAY), ids=" and ".join)
def test_help_with_one_or_two_sources_goes_to_the_agent(tmp_path, monkeypatch, names):
    """Changed by briefs/S3-R6-A-tests.md (C36 point 5; was ..._is_as_today, HELP_TODAY word
    for word): the agent's reply is posted, not C11's help."""
    env = CountyEnv(tmp_path, monkeypatch, names=names)
    text = help_text(env, tmp_path)
    assert text == AGENT_HELP_REPLY and text != HELP_TODAY[names]


def test_the_source_question_with_two_sources_is_as_today(tmp_path, monkeypatch):
    env = CountyEnv(tmp_path, monkeypatch, names=NAMES)
    reply = env.ask(Q_COUNT, Step(count(LEAVE_OUT, year(2025))),
                    Step(finish("finding", "I counted {r1.count}.")))
    checked(reply)
    assert reply.status == "NEEDS_INPUT", (reply.status, reply.reason_code, reply.text)
    assert reply.text == QUESTION_TODAY
    assert len(env.model.calls) == 1, "the turn ends with the question"


@pytest.mark.parametrize("row", list(ROWS))
def test_a_refusal_with_two_sources_ends_as_today(tmp_path, monkeypatch, row):
    env = CountyEnv(tmp_path, monkeypatch, names=NAMES)
    reply = checked(refusal(env, row))
    assert reply.text.endswith(ENDS_TODAY[NAMES]), reply.text
    assert SHORT not in reply.text


@pytest.mark.parametrize("names", [("arrests_like",), ("coded_like",)], ids=" and ".join)
def test_a_refusal_with_one_source_ends_as_today(tmp_path, monkeypatch, names):
    env = CountyEnv(tmp_path, monkeypatch, names=names)
    reply = checked(refusal(env, "UNRECOGNIZED_QUESTION"))
    assert reply.text.endswith(ENDS_TODAY[names]), reply.text
    assert SHORT not in reply.text


# ---- three sources: the three new texts ------------------------------------------------------

def test_help_with_three_sources_goes_to_the_agent(tmp_path, monkeypatch):
    """Changed by briefs/S3-R6-A-tests.md (C36 point 5; was test_help_with_three_sources,
    HELP_THREE word for word): the agent's reply is posted, not C23's help."""
    env = three_sources(tmp_path, monkeypatch)
    text = help_text(env, tmp_path)
    assert text == AGENT_HELP_REPLY and text != HELP_THREE


def test_the_source_question_with_three_sources(tmp_path, monkeypatch):
    env = three_sources(tmp_path, monkeypatch)
    reply = env.ask(Q_COUNT, Step(count(LEAVE_OUT, year(2025))),
                    Step(finish("finding", "I counted {r1.count}.")))
    checked(reply)
    assert reply.status == "NEEDS_INPUT", (reply.status, reply.reason_code, reply.text)
    assert reply.text == QUESTION_THREE
    assert len(env.model.calls) == 1, "the turn ends with the question"


@pytest.mark.parametrize("row", list(ROWS))
def test_a_refusal_with_three_sources_ends_with_the_short_form(tmp_path, monkeypatch, row):
    env = three_sources(tmp_path, monkeypatch)
    reply = checked(refusal(env, row))
    assert reply.text.endswith(" " + SHORT), reply.text
    assert reply.text.count(SHORT) == 1 and LONG_PART not in reply.text, reply.text


@pytest.mark.parametrize("code", ROWS_NO_TURN)
def test_a_row_no_turn_ends_on_has_the_short_form_with_three_sources(tmp_path, monkeypatch,
                                                                     code):
    env = three_sources(tmp_path, monkeypatch)
    text = county_row(code, mod("sources").county_sources())
    assert text.endswith(" " + SHORT), text
    assert LONG_PART not in text, text


ABOUT_THREE_C39 = ("I work with 3 sources of Montgomery County open data: arrest records, "
                   "intake records and visit records. I count records, not people, and I never "
                   "show a single record. Ask about any one of them for its dates and what it "
                   "can be broken down by.")  # C39, written out by hand


def test_about_the_data_with_three_sources_is_c39s_short_text(tmp_path, monkeypatch):
    """Changed by briefs/S3-R7-A-tests.md (C39; was
    test_about_the_data_with_three_sources_does_not_change: C23 kept the full list, every
    source's long sentence). With three sources the fixed about reply (no describe_data here)
    is C39's short text, then the notices; no long sentence and not C23's short refusal
    sentence."""
    env = three_sources(tmp_path, monkeypatch)
    reply = env.ask(Q_ABOUT, Step(finish("about_data", "Here is what I know.")))
    assert reply.status == "EXPLAINED", (reply.status, reply.reason_code, reply.text)
    assert reply.text.split("\n")[0] == ABOUT_THREE_C39, reply.text
    for sentence in (LONG_A, LONG_C, LONG_V):
        assert sentence not in reply.text, reply.text
    assert SHORT not in reply.text


# ---- the thirteen real source files: lengths only --------------------------------------------

REAL_TURNS = {
    **{row: ROWS[row][0] for row in ("UNRECOGNIZED_QUESTION", "UNSUPPORTED_METRIC",
                                     "UNSUPPORTED_FIELD", "REAL_DATA_NOT_AVAILABLE",
                                     "NEEDS_CLARIFICATION other", "BACKGROUND_OFF")},
    "a finish with nothing made": lambda: [Step(finish("finding", "I counted nothing."))],
    "a count of a source not offered": lambda: ended_by_count(
        count("FIXTURE:no_such_source", year(2025))),
    "an analysis of no known kind": lambda: ended_by_count(
        call("analyze", {"kind": "no_such_kind", "period": year(2025)})),
}


@pytest.mark.parametrize("case", list(REAL_TURNS))
def test_with_the_real_files_no_refusal_is_longer_than_400(tmp_path, monkeypatch, case):
    """With no copy, only the rows that need no copy can end a turn; each is checked here."""
    env = real_files(tmp_path, monkeypatch)
    reply = env.ask(Q_COUNT, *REAL_TURNS[case]())
    n = len(reply.text)  # measured first, so a failure shows a length and no text
    assert n <= LIMIT, (case, reply.reason_code, n)


@pytest.mark.parametrize("code", [ROWS[row][1] for row in ROWS if row != "NEEDS_CLARIFICATION "
                                  "other"] + ["NEEDS_other"] + list(ROWS_NO_TURN))
def test_with_the_real_files_no_row_with_the_sentence_is_longer_than_400(tmp_path, monkeypatch,
                                                                       code):
    """Every row that carries the sentence, worded for the real files (the rows a count error
    ends on need a copy to end a turn, so they are read from replies.county_text)."""
    real_files(tmp_path, monkeypatch)
    n = len(county_row(code, mod("sources").county_sources()))  # a length, never the text
    assert n <= LIMIT, (code, n)
