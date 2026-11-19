"""Stage 3 Part A, round 4: docs/S3A-DESIGN.md C24 ("With three or more sources, the question
about the period names one source") and its "What the round 4 tests must show":

1. With the two fixture sources the question Python asks when the period is missing is
   today's text (and with each fixture alone). Written out by hand; these pass today.
2. With three sources (the two fixtures and round 3's made-up third one in
   tests/s3/fixtures/round3/), the question for each of the three in turn, written out by
   hand, naming that source only.
3. The same when the source was kept from an earlier turn of the thread.
4. With the thirteen real source FILES (config/sources/ read where it is) and a made-up copy
   of each that holds dates only (no row from the county, no network), the question is
   under 200 characters for every source. Lengths only: nothing from those files is quoted
   here, and a failure shows only a status, a reason code and a length.
And C24's "If that source has no copy, the turn does not get this far (it ends with
`NO_COPY`), as today".

Every question is reached through a turn: the model stand-in asks for a count with a source
(or with the source left out, to be kept from earlier) and no period. Each test checks the
status and reason code the turn ended with first (NEEDS_INPUT / NEEDS_CLARIFICATION, as
tests/s3/test_s3_filling.py has it), then that nothing was counted and the turn ended with
the question, then the text.

Readings (each in kit-log/raw/S3A-R4-A-notes.txt):
- "<its copy's first day>": C24 also says "the clause exactly as today's question writes it
  for that source", and today's clause starts at the source file's coverage_start (the first
  day of the period the copy covers, as C11 and about the data word it), not at the copy's
  first record. So arrests_like reads `1 January 2024`, not the 2 January of its first row.
- "sources offered": C23's answer (c), the files that load and pass C20, whether or not each
  has a copy. So three files with two copies take the new form.
- "the source was kept from an earlier turn of the thread": both ways a source is kept
  today are checked: from the last answer (two counts of different years, so the period is
  not one and is not kept) and from a turn that ended with this same question (pending).
- The made-up copies of the real files are made through sources.fetch and the fake
  transport, so they are made the way every copy is. The service rows hold every listed
  field (the fake transport refuses a `$select` of a column it has not got) but every value
  is empty except the time field, which holds made-up dates. The newest is 30 September
  2026: two digits and the longest month name, so the copy's last day is written at its
  longest.
"""
import json
from datetime import date

import pytest

from p1support import LEAVE_OUT, Step, finish, mod
from s3support import (A_ID, C_ID, COPY_NOW, FIXTURES, NAMES, Q_COUNT, Q_FOLLOW, REAL_SOURCES,
                       CountyEnv, FakeService, check_county_reply, count, read_copy_rows,
                       use_sources, year)

ROUND3 = FIXTURES / "round3"
V_ID = "FIXTURE:visits_like"
IDS = {"arrests_like": A_ID, "coded_like": C_ID, "visits_like": V_ID}
THREE = ("arrests_like", "coded_like", "visits_like")

# ---- the questions, written out by hand -------------------------------------------------------
# The fixtures' titles, coverage_start and newest record: arrests_like 1 January 2024 to
# 17 September 2026; coded_like 1 January 2025 to 20 August 2026; visits_like 1 January 2025
# to 28 June 2026.

QUESTION = {
    "arrests_like": ("Which period do you mean? SYNTHETIC fixture arrests (made up for tests) "
                     "covers 1 January 2024 to 17 September 2026."),
    "coded_like": ("Which period do you mean? SYNTHETIC fixture intake records (made up for "
                   "tests) covers 1 January 2025 to 20 August 2026."),
    "visits_like": ("Which period do you mean? SYNTHETIC fixture visits (made up for tests) "
                    "covers 1 January 2025 to 28 June 2026."),
}
# Today, with the two fixtures and a copy of each: one clause per source with a copy.
QUESTION_TWO_TODAY = (
    "Which period do you mean? SYNTHETIC fixture arrests (made up for tests) covers 1 January "
    "2024 to 17 September 2026; SYNTHETIC fixture intake records (made up for tests) covers "
    "1 January 2025 to 20 August 2026.")
NO_COPY_TEXT = ("I don't have a saved copy of that source yet, so nothing was counted. "
                "Whoever runs this agent needs to fetch it.")
PERIOD_START = "Which period do you mean? "
LIMIT = 200
TEXT = "I counted {r1.count}."

# Two counts of different years for each source, so its last answer keeps the source and no
# one period (C9 with A5's base: "its year, if those counts share exactly one").
TWO_YEARS = {"arrests_like": (2024, 2025), "coded_like": (2025, 2026),
             "visits_like": (2025, 2026)}


# ---- setting up -------------------------------------------------------------------------------

def add_visits(env, copy=True):
    """Write round 3's third source file into the env's sources folder and, with `copy`, make
    its copy through the fake transport (as test_s3_round3.py does)."""
    src = json.loads((ROUND3 / "sources" / "visits_like.json").read_text(encoding="utf-8"))
    (env.sources_dir / "visits_like.json").write_text(json.dumps(src, indent=2),
                                                      encoding="utf-8")
    if copy:
        rows = json.loads((ROUND3 / "rows" / "visits_like.json").read_text(
            encoding="utf-8"))["rows"]
        mod("sources").fetch(V_ID, state_dir=env.state_dir,
                             transport=FakeService(rows, address=src["address"]), now=COPY_NOW)
    return env


def three_sources(tmp_path, monkeypatch, copies=THREE):
    """The three fixture sources offered; `copies` says which of them have a copy."""
    env = CountyEnv(tmp_path, monkeypatch, names=NAMES,
                    copies=[n for n in NAMES if n in copies])
    add_visits(env, copy="visits_like" in copies)
    offered = mod("sources").county_sources()
    assert list(offered) == [A_ID, C_ID, V_ID], "premise: three sources offered, in file order"
    for name in THREE:
        has_copy = mod("sources").latest(IDS[name], state_dir=env.state_dir) is not None
        assert has_copy is (name in copies), f"premise: {name} has a copy: {name in copies}"
    return env


def ask_period(env, source=LEAVE_OUT, question=Q_COUNT):
    """A turn whose count names `source` (or leaves it out) and no period."""
    return env.ask(question, Step(count(source)), Step(finish("finding", TEXT)))


def asked(env, reply):
    """The turn ended with a question from Python: the reason code first, then nothing was
    counted and the model was called once (the finish was never reached)."""
    assert (reply.status, reply.reason_code) == ("NEEDS_INPUT", "NEEDS_CLARIFICATION"), \
        (reply.status, reply.reason_code, reply.text)
    assert reply.run_ids == [], "a question counts nothing"
    assert len(env.model.calls) == 1, "the turn ends with the question"
    check_county_reply(reply)
    return reply.text


def kept_from_answer(env, name):
    """Turn 1 counts `name` in two different years and answers; the source is then kept and
    the period is not. Turn 2 leaves both out."""
    first, second = TWO_YEARS[name]
    answer = env.ask(Q_COUNT, Step(count(IDS[name], year(first)), count(IDS[name], year(second))),
                     Step(finish("finding", "I counted {r1.count} and {r2.count}.")))
    assert answer.status == "ANSWERED", (answer.status, answer.reason_code, answer.text)
    assert len(answer.run_ids) == 2
    return ask_period(env, question=Q_FOLLOW)


def kept_from_question(env, name):
    """Turn 1 names `name` and no period, so Python asks; turn 2 leaves both out, so the
    source is the one turn 1 saved (pending) and Python asks again."""
    assert asked(env, ask_period(env, IDS[name])) == expected_for(env, name)
    return ask_period(env, question="Those, please.")


def expected_for(env, name):
    """What the question is in this env: with three sources offered, C24's; else today's."""
    if len(mod("sources").county_sources()) >= 3:
        return QUESTION[name]
    return QUESTION_TWO_TODAY if len(env.names) == 2 else QUESTION[name]


# ---- one or two sources: exactly as today -----------------------------------------------------

@pytest.mark.parametrize("name", NAMES)
def test_with_one_source_the_question_is_as_today(tmp_path, monkeypatch, name):
    env = CountyEnv(tmp_path, monkeypatch, names=(name,))
    assert asked(env, ask_period(env, IDS[name])) == QUESTION[name]


@pytest.mark.parametrize("name", NAMES)
def test_with_two_sources_the_question_is_as_today(tmp_path, monkeypatch, name):
    """Whichever of the two sources the model names, today's question has both clauses."""
    env = CountyEnv(tmp_path, monkeypatch, names=NAMES)
    assert asked(env, ask_period(env, IDS[name])) == QUESTION_TWO_TODAY


@pytest.mark.parametrize("keep", [kept_from_answer, kept_from_question],
                         ids=["kept from the last answer", "kept from the question"])
def test_with_two_sources_a_kept_source_gets_todays_question(tmp_path, monkeypatch, keep):
    env = CountyEnv(tmp_path, monkeypatch, names=NAMES)
    assert asked(env, keep(env, "coded_like")) == QUESTION_TWO_TODAY


def test_with_two_sources_and_one_copy_the_question_is_as_today(tmp_path, monkeypatch):
    """Today the question lists the sources that have a copy: here the one."""
    env = CountyEnv(tmp_path, monkeypatch, names=NAMES, copies=("arrests_like",))
    assert asked(env, ask_period(env, A_ID)) == QUESTION["arrests_like"]


# ---- three sources: the question names the one source -----------------------------------------

@pytest.mark.parametrize("name", THREE)
def test_with_three_sources_the_question_names_the_source_asked(tmp_path, monkeypatch, name):
    env = three_sources(tmp_path, monkeypatch)
    assert asked(env, ask_period(env, IDS[name])) == QUESTION[name]


@pytest.mark.parametrize("name", THREE)
def test_with_three_sources_a_source_kept_from_the_last_answer(tmp_path, monkeypatch, name):
    env = three_sources(tmp_path, monkeypatch)
    assert asked(env, kept_from_answer(env, name)) == QUESTION[name]


@pytest.mark.parametrize("name", THREE)
def test_with_three_sources_a_source_kept_from_the_question(tmp_path, monkeypatch, name):
    env = three_sources(tmp_path, monkeypatch)
    assert asked(env, kept_from_question(env, name)) == QUESTION[name]


@pytest.mark.parametrize("name", ["arrests_like", "coded_like"])
def test_three_sources_offered_two_copies_the_question_names_the_source_asked(
        tmp_path, monkeypatch, name):
    """C23 (c): the sources offered are the files that load, whether or not each has a copy;
    three are offered, so the question names the one asked (today: both with a copy)."""
    env = three_sources(tmp_path, monkeypatch, copies=("arrests_like", "coded_like"))
    assert asked(env, ask_period(env, IDS[name])) == QUESTION[name]


def test_with_three_sources_a_source_with_no_copy_ends_with_no_copy(tmp_path, monkeypatch):
    """C24: "If that source has no copy, the turn does not get this far (it ends with
    `NO_COPY`), as today"."""
    env = three_sources(tmp_path, monkeypatch, copies=("arrests_like", "coded_like"))
    reply = ask_period(env, V_ID)
    assert reply.reason_code == "NO_COPY", (reply.status, reply.reason_code, reply.text)
    assert reply.run_ids == []
    assert reply.text == NO_COPY_TEXT
    assert PERIOD_START.strip() not in reply.text


# ---- the thirteen real source files: lengths only ---------------------------------------------

REAL_FILES = sorted(p.stem for p in REAL_SOURCES.glob("*.json"))
MADE_UP_TIMES = ("2025-01-15T12:00:00.000", "2026-09-30T12:00:00.000")  # made up, dates only


def made_up_copy(src, state_dir):
    """A copy of a real source made through sources.fetch from made-up rows: every listed field
    is there and empty, and the time field holds a made-up date. Returns the copy's rows."""
    keep = [f["name"] for f in src["fields"]]
    keep += [src["time_field"]] if src["time_field"] not in keep else []
    rows = [{**{name: "" for name in keep}, src["time_field"]: when} for when in MADE_UP_TIMES]
    made = mod("sources").fetch(src["id"], state_dir=state_dir,
                                transport=FakeService(rows, address=src["address"]),
                                now=COPY_NOW)
    assert made is not None and made.newest_day == date(2026, 9, 30), "premise: the copy"
    copy_rows = read_copy_rows(made.folder)
    only_dates = all(value in ("", *MADE_UP_TIMES) for row in copy_rows for value in row.values())
    assert len(copy_rows) == len(MADE_UP_TIMES) and only_dates, "premise: dates only"


def real_files_with_copies(tmp_path, monkeypatch):
    """A county-mode agent offered the real source files, read in place from config/sources/,
    each with a made-up copy in tmp_path. Returns (env, {file name: source id})."""
    env = CountyEnv(tmp_path, monkeypatch, names=())
    use_sources(monkeypatch, REAL_SOURCES)
    offered = mod("sources").county_sources()
    ids = {}
    for stem in REAL_FILES:
        src = json.loads((REAL_SOURCES / f"{stem}.json").read_text(encoding="utf-8"))
        assert src["id"] in offered, f"premise: {stem}.json is offered"
        made_up_copy(src, env.state_dir)
        ids[stem] = src["id"]
    assert len(offered) >= 3, "premise: three or more real files are offered"
    return env, ids


@pytest.mark.parametrize("stem", REAL_FILES)
def test_with_the_real_files_the_period_question_is_under_200(tmp_path, monkeypatch, stem):
    env, ids = real_files_with_copies(tmp_path, monkeypatch)
    reply = ask_period(env, ids[stem])
    # Measured first, so that a failure shows a status, a reason code and a length, no text.
    status, code, n = reply.status, reply.reason_code, len(reply.text)
    asks_period = reply.text.startswith(PERIOD_START)
    counted, calls = len(reply.run_ids), len(env.model.calls)
    assert (status, code) == ("NEEDS_INPUT", "NEEDS_CLARIFICATION"), (status, code, n)
    assert counted == 0 and calls == 1, (code, counted, calls)
    assert asks_period, (code, n)
    assert n < LIMIT, (code, n)
