"""Round 4 of Part S: docs/S3S-DESIGN.md S13 (D-061), an analysis with no period, and choosing
the kind. Brief S3S-R4-A. Every figure here is from the SYNTHETIC fixtures (tests/s3s/
fixtures/); none is a Montgomery County figure.

What each group of tests shows, by S13's points:

 1  `analyze` with no period stated, none pending and none kept uses the whole copy (S2's
    window over the source's first day to the copy's newest day: January 2021 to August
    2026, 68 months, for both fixture sources); Python does not ask and does not say the
    period was kept. A pending period, a kept period and a stated period are used as today
    (the kept note as today). `count` with no period still asks. No copy: NO_COPY.
 2  The two county prompts hold the new period line word for word, and not the old line.
 3  The shapes the model sends by mistake: option keys beside `options`; `options` or one
    option as JSON text; a period with only `from` or only `to`. Text that is not JSON is
    refused as today; options both inside and beside `options`: the ones inside.
 4  A before_after whose stated or kept period leaves fewer than 12 full months on a side is
    run on the whole copy; a period long enough is used; any other TOO_LITTLE is unchanged.
 5  The two refusal texts, word for word, each on the request that brings it.
 6  The trend clause of the kind line, word for word, in both prompts.
 7  A bare label as a factor.
 8  `versus` naming the same group as the filters.
 9  USE_ANALYZE: once a turn, for a count with no period in a turn whose question holds an
    analysis word; not otherwise; nothing counted; not a count error.
10  compare and share naming an analysis.
11  The two distribution texts.
12  The kind line: the same line in both prompts, in S13's order, with the yes_no words.
13  A before_after with the date in its period.
14  USE_SHARES: once a turn, only for a trend, only in a turn whose question has a share word.

READINGS (each is in kit-log/raw/S3S-R4-A-notes.txt):
- "The whole copy" is S2's window over the source's first day (coverage_start, 1 January
  2021) to the copy's newest day (14 October 2026): January 2021 to August 2026, September
  2026 being dropped by drop_newest_months, as S2 says ("S2's window rule then takes the full
  months, as today"). The brief's "first and last full months of the fixture" are read as
  these two.
- "Its window names" them: the tool answer's `read_as` holds both month names, job.json
  holds both (as `January 2021`, `2021-01` or `[2021, 1]`), and the used line of S5.4 says
  68 months.
- "Asked" is round 4's check of Part A: NEEDS_INPUT / NEEDS_CLARIFICATION, the model called
  once, nothing counted or run; the turn's stored `missing` says what was asked.
- A tool error's text is its `why`; the code is its `error` (as every tool error today).
- The point 9 and 14 word lists are read exactly as S13 writes them: the phrases "going up or
  down", "which days or hours" and "times of the day or week" whole; "what time(s)" as
  "what time" and "what times". Only those forms are tested (QUESTIONS.md, S3S-R4-A).
- Point 12 replaces point 2's kind line by "the one now in both county prompts" and gives no
  text, so the kind line is not tested word for word: it is the one line holding point 12's
  yes_no words; it holds point 6's trend clause word for word; it is the same in both
  prompts; it names the kinds in point 12's order (QUESTIONS.md, S3S-R4-A).
- Where S13 leaves a case open, both readings are accepted at that one place and the
  question is in briefs/QUESTIONS.md (S3S-R4-A): the kept note when a kept period too short
  for a before_after gives way to the whole copy; the note after a whole-copy analysis; the
  error code of point 11's two hints.
- Questions are checked against stage 1's guard for "not refused" only: in county mode the
  guard's restrictions do not apply (C0), as tests/s3 already rely on.
"""
import json
import re
from functools import lru_cache
from pathlib import Path

import pytest

import s3ssupport as T
from p1support import THREAD_1, THREAD_2, Step, finish, mod
from s3sagent import (EDGES, EDGES_ID, MAIN, MAIN_ID, Q_SHARES, Q_TREND, QUESTION, StatsEnv,
                      analyze, answered, ask_case, assert_estimates, job_folders,
                      result_text, slot_text, slots, write_sources)
from s3support import KEPT_ANY, compare, count, share

REPO = Path(__file__).resolve().parents[2]
PROMPTS = {"plain": REPO / "config" / "agent_prompt_s3.md",
           "talk": REPO / "config" / "agent_prompt_s3_talk.md"}
P5, P6 = T.P5, T.P6
WHOLE = ("January 2021", "August 2026", 68)    # S2 over the whole copy (READING)
FIVE_YEARS = ("January 2021", "December 2025", 60)

# ---- the texts of S13, word for word ----------------------------------------------------------

OLD_LINE = ("- Give source, period and filters exactly as for count, and leave out what the latest "
            "message does not state. The program uses full months only and names them.")
# Changed by briefs/S3-R23-A-tests.md: C60 point 2 of docs/S3A-DESIGN.md puts one sentence into the
# line after "with no period the program uses every month it has." (it was the line without it).
PERIOD_LINE = ("- Give source and filters exactly as for count. Leave the period out unless the "
               "message names one: with no period the program uses every month it has. \"The past "
               "five years\" or \"the last three years\" names one: from the same month that many "
               "years back; call analyze once for it, never twice. Never put the date of a "
               "before_after question in the period. The program uses full months only and names "
               "them.")
TREND_CLAUSE = ('"is it rising", "going up or down", "increasing" is trend, with the filters of '
                'the group the question names;')
YES_NO_WORDS = "with X as the outcome and every factor the question names in one call"
KIND_ORDER = ("shares", "trend", "timing", "distribution", "before_after", "trend_compare",
              "yes_no")
COMPARE_WHY = ('trend_compare: one group in filters and the other in options.versus, one filter '
               'each, for example filters [{"field": "district", "is": "district 3"}] and options '
               '{"versus": [{"field": "district", "is": "district 4"}]}')
SHARES_WHY = ('shares: the part must not filter a field that filters already limit. For "the '
              'share of X among all records" send filters [] and options {"part": [the filters '
              'of X]}')
SAME_GROUP_WHY = "versus is the same group as filters: for the trend of one group use kind trend"
USE_ANALYZE_WHY = ("This question is about change over time, a share, the times of the week, ages "
                   "or what goes with what: use analyze, with the period left out (it uses every "
                   "month). Pick its kind as the instructions say.")
NOT_A_COUNT_WHY = ("compare and share take counts only; an analysis's own slots already say what "
                   "it found: call finish with them")
BY_WHY = ('"by" names the field of the groups whose ages are compared, such as "gender" (a '
          'category or yes-or-no field); leave it out for everyone')
TWO_ON_ONE_FIELD_WHY = ('distribution: to compare the ages of groups send options {"by": '
                        '"<field>"}, for example {"by": "gender"}, and no filter on that field')
USE_SHARES_WHY = ('This question asks about a share: use kind shares, with filters for the whole '
                  '(none for all records) and options {"part": [the filters of the group]}, for '
                  'example options {"part": [{"field": "age", "to": 17}]}.')
TOO_LITTLE_MONTHS = "That needs at least 24 full months of records, and this selection has fewer."
TOO_LITTLE_RECORDS = "That needs at least 100 records in all, and this selection has fewer."

# ---- the questions ----------------------------------------------------------------------------

# Point 9: one question per word or phrase of S13's list (READING above), each with that one
# analysis word, and one with capitals.
ANALYSIS_WORD_QUESTIONS = {
    "rise": "Did arrests rise in district 3?",
    "going up or down": "Are arrests in district 3 going up or down?",
    "increase": "Was there an increase in arrests in district 3?",
    "decrease": "Was there a decrease in arrests in district 3?",
    "trend": "What is the trend for arrests in district 3?",
    "over the years": "How many arrests were there in district 3 over the years?",
    "over time": "How have arrests in district 3 looked over time?",
    "change": "Has there been any change in arrests in district 3?",
    "share": "What share of arrests were in district 3?",
    "proportion": "What proportion of arrests were in district 3?",
    "percentage": "What percentage of arrests were in district 3?",
    "what time": "At what time do arrests happen in district 3?",
    "what times": "What times do arrests happen in district 3?",
    "which days or hours": "On which days or hours are arrests made in district 3?",
    "busiest": "When is district 3 busiest for arrests?",
    "times of the day or week": "What are the times of the day or week for arrests in district 3?",
    "how old": "How old are people arrested in district 3?",
    "ages": "What are the ages of people arrested in district 3?",
    "what goes with": "What goes with an arrest in district 3?",
    "odds": "What are the odds that an arrest in district 3 is near a school?",
    "more likely": "Are arrests in district 3 more likely near a school?",
    "TREND, in capitals": "Is the TREND in district 3 different from district 4?",
}
NO_ANALYSIS_WORD = "How many arrests were there in district 3?"
# Point 14: one question per share word, and one with capitals.
SHARE_WORD_QUESTIONS = {
    "share": "What share of arrests were near a school?",
    "shares": "How have the shares of arrests near a school moved?",
    "proportion": "What proportion of arrests were near a school?",
    "proportions": "How have the proportions near a school developed?",
    "percentage": "What percentage of arrests were near a school?",
    "percentages": "Show me the percentages of arrests near a school.",
    "percent": "What percent of arrests were near a school?",
    "SHARE, in capitals": "Has the SHARE of arrests near a school gone up?",
}
Q_PICK_SOURCE = "The statistics fixture, please."
Q_RISE_AFTER = "Did that rise?"
Q_D3_D4 = "Is the trend in district 3 different from district 4?"
Q_AGES_BY = "How old are people at arrest, by gender?"
Q_AFTER_FEB = "Did arrests change after February 2025?"


def test_r4_questions_are_not_refused_by_the_guard():
    """A premise: stage 1's guard refuses none of this file's questions (READING above)."""
    for q in [*ANALYSIS_WORD_QUESTIONS.values(), NO_ANALYSIS_WORD,
              *SHARE_WORD_QUESTIONS.values(), Q_PICK_SOURCE, Q_RISE_AFTER, Q_D3_D4, Q_AGES_BY,
              Q_AFTER_FEB, *QUESTION.values()]:
        assert mod("guard").screen(q).refuse is None, q


def test_r4_the_word_questions_hold_their_word_and_no_other():
    """A premise, no program code: each point 9 question holds its word as whole words, and
    the point 14 questions hold a share word; NO_ANALYSIS_WORD and Q_TREND hold none."""
    words9 = [w for w in ANALYSIS_WORD_QUESTIONS if "," not in w]
    share_words = ("share", "shares", "proportion", "proportions", "percentage", "percentages",
                   "percent")

    def has(q, w):
        return re.search(rf"(?i)(?<![\w]){re.escape(w)}(?![\w])", q) is not None
    for w, q in ANALYSIS_WORD_QUESTIONS.items():
        assert has(q, w.split(",")[0]), (w, q)
    for q in (NO_ANALYSIS_WORD,):
        assert not any(has(q, w) for w in words9 + ["going up", "going down"]), q
    for w, q in SHARE_WORD_QUESTIONS.items():
        assert has(q, w.split(",")[0]), (w, q)
    for q in (Q_TREND, Q_AFTER_FEB, Q_D3_D4):
        assert not any(has(q, w) for w in share_words), q


# ---- helpers ------------------------------------------------------------------------------------

def no_period(name, **change):
    """The case's analyze arguments with the period left out."""
    args = T.analyze_arguments(name, **change)
    args.pop("period")
    return args


_MONTHS = list(T.MONTH_NAMES)


def names_month(text, month):
    """`January 2021` written as words, as `2021-01`, or as `[2021, 1]` (READING above)."""
    name, year = month.split()
    m = _MONTHS.index(name) + 1
    return (month in text or f"{year}-{m:02d}" in text
            or re.search(rf"\[\s*{year}\s*,\s*{m}\s*\]", text) is not None)


def assert_window(env, reply, answer, window, folder=None):
    """The analysis used `window` (first month, last month, months): its read_as names both
    months, its job.json holds both, and the used line of S5.4 says that many months."""
    first, last, months = window
    assert "result_id" in answer, answer
    read_as = answer["read_as"]
    assert first in read_as and last in read_as, (window, read_as)
    folder = folder or job_folders(env)[-1]
    job = (folder / "job.json").read_text(encoding="utf-8")
    assert names_month(job, first) and names_month(job, last), (window, job[:600])
    assert re.search(rf"\([\d,]+ records over {months} months", reply.text), (window, reply.text)


@lru_cache(maxsize=None)
def _truth(kind, period, filters, options):
    """Recomputed in Python from the fixture rows (s3ssupport, no program code), for a spec
    that is not one of s3ssupport's named cases."""
    c = {"kind": kind, "source": MAIN, "period": json.loads(period),
         "filters": json.loads(filters), "options": json.loads(options)}
    return {"trend": T._truth_trend, "before_after": T._truth_before_after}[kind](c)


def truth_of(kind, period, filters=(), **options):
    return _truth(kind, json.dumps(period, sort_keys=True), json.dumps(list(filters)),
                  json.dumps(options, sort_keys=True))


def assert_truth(env, t):
    """S9's tolerances, as s3sagent.assert_estimates, for a truth computed here."""
    entries = T.result_estimates(json.loads(result_text(env)))
    for est in t["estimates"]:
        assert T.find_estimate(entries, est, t["kind"]), (
            f"no estimate in result.json matches the truth's {est['name']} {est['estimate']:.5f}"
            f" ({est['low']:.5f} to {est['high']:.5f}); result.json has {entries}")


def no_kept_note(reply):
    assert not KEPT_ANY.search(reply.text), f"S13 point 1: nothing is said to be kept: {reply.text}"
    assert not reply.carried.get("period"), reply.carried


def kept_period_note(reply, *years):
    found = KEPT_ANY.search(reply.text)
    assert found, f"the kept note, as today: {reply.text}"
    assert all(str(y) in found[0] for y in years), (years, found[0])
    assert reply.carried.get("period"), reply.carried


def asked_period(env, reply):
    """Round 4's "asked": a question from Python ends the turn; nothing counted or run."""
    assert (reply.status, reply.reason_code) == ("NEEDS_INPUT", "NEEDS_CLARIFICATION"), \
        (reply.status, reply.reason_code, reply.text)
    assert reply.run_ids == [] and job_folders(env) == []
    assert env.store.recent_turns(THREAD_1, 1)[-1].get("missing") == "period", \
        env.store.recent_turns(THREAD_1, 1)[-1]


def refused(env, step=0, position=0):
    answer = env.model.answer(step, position)
    assert "error" in answer and "result_id" not in answer, answer
    return answer


def two_sources(tmp_path, monkeypatch):
    env = StatsEnv(tmp_path, monkeypatch, names=(MAIN, EDGES))
    assert len(mod("sources").county_sources()) == 2, "premise: two sources, both with a copy"
    return env


def ask_source_with_period(env, period, tool="analyze"):
    """Turn 1 states a period and no source; two sources have a copy, so Python asks for the
    source and keeps the period with the question (pending, C9)."""
    call = analyze({"kind": "trend", "period": period, "filters": []}) if tool == "analyze" \
        else count(period=period)
    reply = env.ask(Q_TREND if tool == "analyze" else "How many arrests were there?", Step(call),
                    Step(finish("finding", "I found that.")))
    assert (reply.status, reply.reason_code) == ("NEEDS_INPUT", "NEEDS_CLARIFICATION"), \
        ("premise: Python asks for the source", reply.status, reply.reason_code, reply.text)
    assert env.store.recent_turns(THREAD_1, 1)[-1].get("missing") == "source"


def count_five_years(env):
    """Turn 1: a count of the main source over the five whole years (the period is kept)."""
    reply = env.ask("How many arrests were there from 2021 to 2025?",
                    Step(count(MAIN_ID, P5)), Step(finish("finding", "I counted {r1.count}.")))
    assert reply.status == "ANSWERED", ("premise", reply.status, reply.reason_code, reply.text)


# ---- point 1: no period means the whole copy ---------------------------------------------------

KIND_CASES = ["trend_all", "compare_school", "timing", "ba_d6", "sh_school", "ages_gender",
              "yn_main"]


@pytest.mark.needs_r
@pytest.mark.parametrize("name", KIND_CASES)
def test_p1_no_period_uses_the_whole_copy(tmp_path, monkeypatch, name):
    """S13 point 1: no period stated, pending or kept: the whole copy, January 2021 to August
    2026; the turn is ANSWERED, no period question is asked, nothing is said to be kept."""
    env = StatsEnv(tmp_path, monkeypatch)
    reply = env.ask(QUESTION[T.case(name)["kind"]], Step(analyze(no_period(name))),
                    Step(finish("finding", slot_text(name))))
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    answered(reply)
    assert len(env.model.calls) == 2, "no question ends the turn"
    assert "Which period" not in reply.text, reply.text
    answer = env.model.answer(0)
    assert answer["result_id"] == "a1" and answer["slots"] == slots(name), answer
    assert_window(env, reply, answer, WHOLE)
    no_kept_note(reply)
    if name == "trend_all":
        assert_estimates(env, "trend_all_p6")
    if name == "ba_d6":
        assert_truth(env, truth_of("before_after", P6, T.district(6), date="2023-07-01"))


@pytest.mark.needs_r
def test_p1_a_pending_period_is_used_as_today(tmp_path, monkeypatch):
    """S13 point 1: a period pending from a turn that asked (here: for the source) is used,
    with the kept note, as today."""
    env = two_sources(tmp_path, monkeypatch)
    ask_source_with_period(env, P5)
    reply = answered(env.ask(Q_PICK_SOURCE, Step(analyze({"kind": "trend", "source": MAIN_ID})),
                             Step(finish("finding", "I found that {a1.trend}."))))
    assert_window(env, reply, env.model.answer(0), FIVE_YEARS)
    kept_period_note(reply, 2021, 2025)
    assert_estimates(env, "trend_all")


@pytest.mark.needs_r
def test_p1_a_kept_period_is_used_as_today(tmp_path, monkeypatch):
    """S13 point 1: the period of the thread's last answer is kept, with the note, as today."""
    env = StatsEnv(tmp_path, monkeypatch)
    count_five_years(env)
    reply = answered(env.ask("And is that going up?",
                             Step(analyze({"kind": "trend", "source": MAIN_ID})),
                             Step(finish("finding", "I found that {a1.trend}."))))
    assert_window(env, reply, env.model.answer(0), FIVE_YEARS)
    kept_period_note(reply, 2021, 2025)
    assert_estimates(env, "trend_all")


@pytest.mark.needs_r
def test_p1_a_stated_period_is_used_as_today(tmp_path, monkeypatch):
    env = StatsEnv(tmp_path, monkeypatch)
    reply = answered(ask_case(env, "trend_all", text="I found that {a1.trend}."))
    assert_window(env, reply, env.model.answer(0), FIVE_YEARS)
    no_kept_note(reply)
    assert_estimates(env, "trend_all")


@pytest.mark.needs_r
def test_p1_after_a_whole_copy_analysis_the_next_one_uses_the_same_months(tmp_path,
                                                                          monkeypatch):
    """S13 point 1 twice in a thread: after an analysis of the whole copy, an analysis with no
    period uses the same months. Whether the period of a whole-copy analysis is then "kept"
    (and said so) S13 does not say: either is accepted (QUESTIONS.md, S3S-R4-A)."""
    env = StatsEnv(tmp_path, monkeypatch)
    first = answered(env.ask(Q_TREND, Step(analyze(no_period("trend_all"))),
                             Step(finish("finding", "I found that {a1.trend}."))))
    assert_window(env, first, env.model.answer(0), WHOLE)
    reply = answered(env.ask("And in district 3?", Step(analyze(no_period("trend_d3"))),
                             Step(finish("finding", "I found that {a1.trend}."))))
    assert_window(env, reply, env.model.answer(0), WHOLE)


def test_p1_count_with_no_period_still_asks(tmp_path, monkeypatch):
    """S13 point 1: `count` does not change: with no period it asks (and its question has no
    analysis word, so point 9 does not apply)."""
    env = StatsEnv(tmp_path, monkeypatch)
    reply = env.ask(NO_ANALYSIS_WORD, Step(count(MAIN_ID, filters=T.district(3))),
                    Step(finish("finding", "I counted {r1.count}.")))
    asked_period(env, reply)
    assert len(env.model.calls) == 1


def test_p1_no_copy_is_no_copy(tmp_path, monkeypatch):
    """S13 point 1 with C4: a source with no copy gives NO_COPY, as today; nothing is run."""
    env = StatsEnv(tmp_path, monkeypatch, names=(MAIN,))
    write_sources(env.sources_dir, (EDGES,))
    assert mod("sources").latest(EDGES_ID, state_dir=env.state_dir) is None, "premise"
    reply = env.ask(Q_TREND, Step(analyze({"kind": "trend", "source": EDGES_ID})),
                    Step(finish("finding", "I found that {a1.trend}.")))
    assert reply.reason_code == "NO_COPY", (reply.status, reply.reason_code, reply.text)
    assert reply.status != "ANSWERED" and job_folders(env) == []


# ---- points 2, 6 and 12: the two county prompts -------------------------------------------------

def _lines(key):
    return [line.rstrip() for line in PROMPTS[key].read_text(encoding="utf-8").splitlines()]


def kind_line(key):
    found = [line for line in _lines(key) if YES_NO_WORDS in line]
    assert len(found) == 1, (f"S13 point 12: one kind line holding {YES_NO_WORDS!r} in "
                             f"{PROMPTS[key].name}; found {len(found)}")
    return found[0]


@pytest.mark.parametrize("key", list(PROMPTS))
def test_p2_the_period_line_word_for_word(key):
    assert PERIOD_LINE in _lines(key), f"S13 point 2: the period line, in {PROMPTS[key].name}"


@pytest.mark.parametrize("key", list(PROMPTS))
def test_p2_the_old_line_is_gone(key):
    text = PROMPTS[key].read_text(encoding="utf-8")
    assert OLD_LINE not in text, PROMPTS[key].name
    assert "Give source, period and filters exactly as for count" not in text, PROMPTS[key].name


@pytest.mark.parametrize("key", list(PROMPTS))
def test_p6_the_trend_clause_word_for_word(key):
    assert TREND_CLAUSE in kind_line(key), (key, kind_line(key))


def test_p12_the_kind_line_is_the_same_in_both_prompts():
    assert kind_line("plain") == kind_line("talk")


def _position(line, kind):
    found = (re.search(rf"\bis {kind}\b", line) or re.search(rf"\b{kind}\b", line)
             or (re.search(re.escape(YES_NO_WORDS), line) if kind == "yes_no" else None))
    assert found, (kind, line)
    return found.start()


@pytest.mark.parametrize("key", list(PROMPTS))
def test_p12_the_kind_line_names_the_kinds_in_order(key):
    """S13 point 12: shares first, then trend, timing, distribution, before_after,
    trend_compare and yes_no (READING: each kind's place is where the line says "is <kind>",
    else its first mention)."""
    line = kind_line(key)
    places = [_position(line, kind) for kind in KIND_ORDER]
    assert places == sorted(places), list(zip(KIND_ORDER, places))


# ---- point 3: the shapes the model sends by mistake ---------------------------------------------

_RIGHT = {}


def right_answer(tmp_path, monkeypatch, name):
    """The tool answer to the case in its right shape (once per run of the tests)."""
    if name not in _RIGHT:
        env = StatsEnv(tmp_path / "right", monkeypatch)
        answered(ask_case(env, name))
        _RIGHT[name] = env.model.answer(0)
    return _RIGHT[name]


def beside(name, *, options=None, text=()):
    """The case's options sent beside `options`; `options` itself then `options` (left out
    when None); the keys in `text` sent as JSON text."""
    args = T.analyze_arguments(name)
    args.update({k: json.dumps(v) if k in text else v for k, v in args.pop("options").items()})
    if options is not None:
        args["options"] = options
    return args


def as_text(name, *keys):
    """The case's `options` as JSON text (no keys), or the options `keys` each as JSON text."""
    args = T.analyze_arguments(name)
    if not keys:
        args["options"] = json.dumps(args["options"])
    else:
        args["options"] = {k: json.dumps(v) if k in keys else v
                           for k, v in args["options"].items()}
    return args


SHAPES = {
    "yes_no options beside, none given": ("yn_main", beside("yn_main")),
    "yes_no options beside, options empty": ("yn_main", beside("yn_main", options={})),
    "trend_compare versus beside": ("compare_school", beside("compare_school")),
    "before_after date beside": ("ba_d6", beside("ba_d6")),
    "shares part beside": ("sh_school", beside("sh_school")),
    "distribution by beside": ("ages_gender", beside("ages_gender")),
    "yes_no options as JSON text": ("yn_main", as_text("yn_main")),
    "trend_compare options as JSON text": ("compare_school", as_text("compare_school")),
    "yes_no factors and controls as JSON text": ("yn_main",
                                                 as_text("yn_main", "factors", "controls")),
    "trend_compare versus as JSON text": ("compare_school", as_text("compare_school", "versus")),
    "shares part as JSON text": ("sh_school", as_text("sh_school", "part")),
    "yes_no beside, as JSON text (seen six times)": (
        "yn_main", beside("yn_main", text=("factors", "controls"))),
}


@pytest.mark.needs_r
@pytest.mark.parametrize("label", list(SHAPES))
def test_p3_each_shape_gives_the_same_analysis(tmp_path, monkeypatch, label):
    """S13 point 3: read as what it means, before C9's filling: the same read_as, slots and
    estimates as the right shape."""
    name, args = SHAPES[label]
    right = right_answer(tmp_path, monkeypatch, name)
    env = StatsEnv(tmp_path / "shape", monkeypatch)
    reply = env.ask(QUESTION[T.case(name)["kind"]], Step(analyze(args)),
                    Step(finish("finding", slot_text(name))))
    answered(reply)
    answer = env.model.answer(0)
    assert (answer.get("read_as"), answer.get("slots")) == (right["read_as"], right["slots"]), \
        (label, answer, right)
    if T.truth(name)["estimates"]:
        assert_estimates(env, name)


@pytest.mark.needs_r
def test_p3_options_inside_and_beside_the_inside_ones_are_used(tmp_path, monkeypatch):
    name = "yn_main"
    right = right_answer(tmp_path, monkeypatch, name)
    env = StatsEnv(tmp_path / "shape", monkeypatch)
    args = T.analyze_arguments(name)
    args.update(outcome=T.WEAPON, factors=[T.SHIFT_B], controls=[])
    answered(env.ask(QUESTION["yes_no"], Step(analyze(args)),
                     Step(finish("finding", slot_text(name)))))
    answer = env.model.answer(0)
    assert (answer["read_as"], answer["slots"]) == (right["read_as"], right["slots"]), answer
    assert_estimates(env, name)


@pytest.mark.needs_r
@pytest.mark.parametrize("period", [{"from": "2022-01-01"}, {"to": "2024-12-31"}],
                         ids=["only from", "only to"])
def test_p3_a_period_with_one_end_is_no_period(tmp_path, monkeypatch, period):
    """S13 point 3 then point 1: the whole copy."""
    env = StatsEnv(tmp_path, monkeypatch)
    args = T.analyze_arguments("trend_all", period=period)
    reply = answered(env.ask(Q_TREND, Step(analyze(args)),
                             Step(finish("finding", "I found that {a1.trend}."))))
    assert_window(env, reply, env.model.answer(0), WHOLE)
    no_kept_note(reply)
    assert_estimates(env, "trend_all_p6")


NOT_JSON = {
    "options as words": ("yn_main", lambda a: a.update(
        options="outcome adjacent_to_school, factors weapon")),
    "options starting with { but not JSON": ("yn_main", lambda a: a.update(
        options="{outcome: adjacent_to_school, factors: [weapon]}")),
    "factors starting with [ but not JSON": ("yn_main", lambda a: a["options"].update(
        factors="[weapon, female")),
    "versus as words": ("compare_school", lambda a: a["options"].update(
        versus="not near a school")),
}


@pytest.mark.parametrize("label", list(NOT_JSON))
def test_p3_text_that_is_not_json_is_refused_as_today(tmp_path, monkeypatch, label):
    name, change = NOT_JSON[label]
    env = StatsEnv(tmp_path, monkeypatch)
    args = T.analyze_arguments(name)
    args["options"] = dict(args["options"])
    change(args)
    env.ask(QUESTION[T.case(name)["kind"]], Step(analyze(args)),
            Step(finish("finding", "I found that.")))
    assert refused(env)["error"] == "BAD_OPTIONS", (label, env.model.answer(0))
    assert job_folders(env) == []


# ---- point 4: a before_after too short on a side runs on the whole copy -------------------------

def _ba(date_text, period, filters=None):
    args = T.analyze_arguments("ba_d2", period=period)
    if filters is not None:
        args["filters"] = filters
    args["options"] = {"date": date_text}
    return args


@pytest.mark.needs_r
@pytest.mark.parametrize("when,period", [
    ("2025-02-01", P5),                                     # 11 months from it on in P5
    ("2022-06-01", {"from": "2022-01-01", "to": "2025-12-31"}),  # 5 months before it
], ids=["short after", "short before"])
def test_p4_a_side_too_short_runs_on_the_whole_copy(tmp_path, monkeypatch, when, period):
    """S13 point 4: run on the whole copy instead, as if no period had been given; the reply
    names the months used."""
    env = StatsEnv(tmp_path, monkeypatch)
    reply = answered(env.ask(Q_AFTER_FEB, Step(analyze(_ba(when, period))),
                             Step(finish("finding", "{a1.step}. {a1.bend}."))))
    answer = env.model.answer(0)
    assert_window(env, reply, answer, WHOLE)
    month = T.month_text((int(when[:4]), int(when[5:7])))
    assert month in answer["read_as"], (month, answer["read_as"])
    no_kept_note(reply)
    assert_truth(env, truth_of("before_after", P6, T.district(2), date=when))


@pytest.mark.needs_r
def test_p4_a_period_long_enough_is_used(tmp_path, monkeypatch):
    """S13 point 4: 18 months before July 2023 and 30 from it on: the stated period stands."""
    period = {"from": "2022-01-01", "to": "2025-12-31"}
    env = StatsEnv(tmp_path, monkeypatch)
    reply = answered(env.ask(Q_AFTER_FEB, Step(analyze(_ba("2023-07-01", period,
                                                          T.district(6)))),
                             Step(finish("finding", "{a1.step}. {a1.bend}."))))
    assert_window(env, reply, env.model.answer(0), ("January 2022", "December 2025", 48))
    assert_truth(env, truth_of("before_after", period, T.district(6), date="2023-07-01"))


@pytest.mark.needs_r
def test_p4_a_kept_period_too_short_runs_on_the_whole_copy(tmp_path, monkeypatch):
    """S13 point 4, "stated (or kept)": the kept five years leave 11 months from February 2025
    on, so the whole copy is used. S13 answer 2 (S3S-DESIGN; pinned by brief S3-R16-A, was open:
    either accepted): a kept period that the before_after did not use is NOT said to be kept:
    no kept note, and the reply does not carry the period."""
    env = StatsEnv(tmp_path, monkeypatch)
    count_five_years(env)
    args = _ba("2025-02-01", P5)
    args.pop("period")
    reply = answered(env.ask(Q_AFTER_FEB, Step(analyze(args)),
                             Step(finish("finding", "{a1.step}. {a1.bend}."))))
    assert_window(env, reply, env.model.answer(0), WHOLE)
    assert_truth(env, truth_of("before_after", P6, T.district(2), date="2025-02-01"))
    no_kept_note(reply)


def test_p4_another_too_little_is_unchanged_for_a_trend(tmp_path, monkeypatch):
    """S13 point 4 is for before_after only: a trend over 23 months is refused as today."""
    env = StatsEnv(tmp_path, monkeypatch)
    reply = env.ask(Q_TREND, Step(analyze(T.analyze_arguments("trend_23"))),
                    Step(finish("finding", "I found that.")))
    assert refused(env)["error"] == "TOO_LITTLE"
    assert reply.reason_code == "TOO_LITTLE" and TOO_LITTLE_MONTHS in reply.text, reply.text
    assert job_folders(env) == []


def test_p4_another_too_little_is_unchanged_for_a_before_after(tmp_path, monkeypatch):
    """S13 point 4: a before_after with 12 months on each side but 24 records in all is
    refused for too few records, as today (the whole copy, 303 records, is not tried)."""
    env = StatsEnv(tmp_path, monkeypatch, names=(EDGES,))
    args = {"kind": "before_after", "source": EDGES_ID,
            "period": {"from": "2021-01-01", "to": "2022-12-31"}, "filters": T.batch("Q2"),
            "options": {"date": "2022-01-01"}}
    reply = env.ask(Q_AFTER_FEB, Step(analyze(args)), Step(finish("finding", "I found that.")))
    assert refused(env)["error"] == "TOO_LITTLE"
    assert reply.reason_code == "TOO_LITTLE" and TOO_LITTLE_RECORDS in reply.text, reply.text
    assert job_folders(env) == []


def test_p4_the_q2_premise_by_counting():
    """No program code: Q2 has 24 records in 2021 and 2022 and 303 in all."""
    rows = [r for r in T.fixture_rows(EDGES) if r.get("batch") == "Q2"]
    assert len(rows) == 303
    assert sum(r["event_date_time"][:4] in ("2021", "2022") for r in rows) == 24


# ---- point 5: the two refusals that say what to do ----------------------------------------------

@pytest.mark.parametrize("options", [None, {"versus": T.district(5)}],
                         ids=["no options", "with versus"])
def test_p5_trend_compare_with_two_filters_on_one_field(tmp_path, monkeypatch, options):
    """S13 point 5: the why word for word; the code as today (BAD_FIELD: one filter a field)."""
    env = StatsEnv(tmp_path, monkeypatch)
    args = {"kind": "trend_compare", "source": MAIN_ID, "period": P5,
            "filters": T.district(3) + T.district(4)}
    if options:
        args["options"] = options
    env.ask(Q_D3_D4, Step(analyze(args)), Step(finish("finding", "I found that.")))
    answer = refused(env)
    assert answer == {**answer, "error": "BAD_FIELD", "why": COMPARE_WHY}, answer
    assert job_folders(env) == []


def test_p5_the_compare_text_is_not_on_a_count(tmp_path, monkeypatch):
    """S13 point 5, "on the request that brings it": a count with two filters on one field
    keeps today's code, and neither new text."""
    env = StatsEnv(tmp_path, monkeypatch)
    env.ask(NO_ANALYSIS_WORD, Step(count(MAIN_ID, P5, T.district(3) + T.district(4))),
            Step(finish("finding", "I counted {r1.count}.")))
    answer = refused(env)
    assert answer["error"] == "BAD_FIELD", answer
    assert answer.get("why") not in (COMPARE_WHY, TWO_ON_ONE_FIELD_WHY), answer


@pytest.mark.parametrize("filters,part", [
    (T.district(3), T.district(3)),
    ([T.is_(T.SCHOOL, True)], [T.is_(T.SCHOOL, False)]),
], ids=["the same filter", "the same field"])
def test_p5_shares_whose_part_filters_a_limited_field(tmp_path, monkeypatch, filters, part):
    env = StatsEnv(tmp_path, monkeypatch)
    args = {"kind": "shares", "source": MAIN_ID, "period": P5, "filters": filters,
            "options": {"part": part}}
    env.ask(Q_SHARES, Step(analyze(args)), Step(finish("finding", "I found that.")))
    answer = refused(env)
    assert answer == {**answer, "error": "BAD_OPTIONS", "why": SHARES_WHY}, answer
    assert job_folders(env) == []


# ---- point 7: a bare label as a factor ----------------------------------------------------------

@pytest.mark.needs_r
@pytest.mark.parametrize("factors", [
    [T.WEAPON, "female", T.SHIFT_B],
    [T.WEAPON, "FEMALE", "Shift b"],
], ids=["female", "capitals"])
def test_p7_a_label_one_field_has_is_read(tmp_path, monkeypatch, factors):
    right = right_answer(tmp_path, monkeypatch, "yn_main")
    env = StatsEnv(tmp_path / "label", monkeypatch)
    args = T.analyze_arguments("yn_main")
    args["options"] = dict(args["options"], factors=factors)
    answered(env.ask(QUESTION["yes_no"], Step(analyze(args)),
                     Step(finish("finding", slot_text("yn_main")))))
    answer = env.model.answer(0)
    assert (answer["read_as"], answer["slots"]) == (right["read_as"], right["slots"]), answer
    assert_estimates(env, "yn_main")


def _female_shift(src):
    """Two category fields with the label "female" (capitals not counting): the shift field's
    label of B made "Female" (in memory, this test's own source file)."""
    (shift,) = [f for f in src["fields"] if f["name"] == "shift"]
    shift["values"]["B"] = "Female"


@pytest.mark.parametrize("label,change", [("purple", None), ("female", _female_shift)],
                         ids=["no field", "two fields"])
def test_p7_a_label_no_field_or_two_fields_have_is_refused(tmp_path, monkeypatch, label,
                                                          change):
    env = StatsEnv(tmp_path, monkeypatch, change={MAIN: change} if change else None)
    args = T.analyze_arguments("yn_main")
    args["options"] = dict(args["options"], factors=[T.WEAPON, label])
    env.ask(QUESTION["yes_no"], Step(analyze(args)), Step(finish("finding", "I found that.")))
    assert refused(env)["error"] == "BAD_OPTIONS", env.model.answer(0)
    assert job_folders(env) == []


# ---- point 8: versus the same group as filters -------------------------------------------------

@pytest.mark.parametrize("filters,versus", [
    ([T.is_(T.SCHOOL, True)], [T.is_(T.SCHOOL, True)]),
    (T.district(3) + [T.FEMALE], [T.FEMALE] + T.district(3)),
], ids=["one filter", "two filters in another order"])
def test_p8_versus_the_same_group(tmp_path, monkeypatch, filters, versus):
    env = StatsEnv(tmp_path, monkeypatch)
    args = {"kind": "trend_compare", "source": MAIN_ID, "period": P5, "filters": filters,
            "options": {"versus": versus}}
    env.ask(Q_D3_D4, Step(analyze(args)), Step(finish("finding", "I found that.")))
    answer = refused(env)
    assert answer == {**answer, "error": "BAD_OPTIONS", "why": SAME_GROUP_WHY}, answer
    assert job_folders(env) == []


# ---- point 9: USE_ANALYZE -------------------------------------------------------------------------

def _use_analyze(answer):
    assert answer == {**answer, "error": "USE_ANALYZE", "why": USE_ANALYZE_WHY}, answer


@pytest.mark.parametrize("word", list(ANALYSIS_WORD_QUESTIONS))
def test_p9_a_count_with_no_period_and_an_analysis_word(tmp_path, monkeypatch, word):
    """S13 point 9: the tool error, and the turn goes on; nothing counted; the error is not a
    count error, so a turn that then finishes with nothing ends exactly as the same turn with
    no count call at all (in another thread of the same agent)."""
    env = StatsEnv(tmp_path, monkeypatch)
    question = ANALYSIS_WORD_QUESTIONS[word]
    reply = env.ask(question, Step(count(MAIN_ID, filters=T.district(3))),
                    Step(finish("finding", "I found that.")))
    _use_analyze(env.model.answer(0))
    assert len(env.model.calls) == 2, "the turn goes on after USE_ANALYZE"
    assert reply.run_ids == [] and reply.results == [] and job_folders(env) == []
    assert reply.reason_code != "USE_ANALYZE", (reply.status, reply.reason_code, reply.text)
    plain = env.ask(question, Step(finish("finding", "I found that.")), thread_key=THREAD_2)
    assert (reply.status, reply.reason_code, reply.text) == \
        (plain.status, plain.reason_code, plain.text)


@pytest.mark.needs_r
def test_p9_then_analyze_answers(tmp_path, monkeypatch):
    """S13 point 9 as meant: the hint, then analyze with the period left out (point 1)."""
    env = StatsEnv(tmp_path, monkeypatch)
    reply = answered(env.ask(ANALYSIS_WORD_QUESTIONS["trend"],
                             Step(count(MAIN_ID, filters=T.district(3))),
                             Step(analyze(no_period("trend_d3"))),
                             Step(finish("finding", "I found that {a1.trend}."))))
    _use_analyze(env.model.answer(0))
    assert_window(env, reply, env.model.answer(1), WHOLE)
    assert reply.run_ids == [] and [r["id"] for r in reply.results] == ["a1"]


def test_p9_a_second_count_in_the_turn_asks_for_the_period(tmp_path, monkeypatch):
    env = StatsEnv(tmp_path, monkeypatch)
    reply = env.ask(ANALYSIS_WORD_QUESTIONS["trend"], Step(count(MAIN_ID, filters=T.district(3))),
                    Step(count(MAIN_ID, filters=T.district(3))),
                    Step(finish("finding", "I counted {r1.count}.")))
    _use_analyze(env.model.answer(0))
    assert (reply.status, reply.reason_code) == ("NEEDS_INPUT", "NEEDS_CLARIFICATION"), \
        (reply.status, reply.reason_code, reply.text)
    assert len(env.model.calls) == 2 and reply.run_ids == []
    assert env.store.recent_turns(THREAD_1, 1)[-1].get("missing") == "period"


def test_p9_not_for_a_question_with_no_analysis_word(tmp_path, monkeypatch):
    env = StatsEnv(tmp_path, monkeypatch)
    reply = env.ask(NO_ANALYSIS_WORD, Step(count(MAIN_ID, filters=T.district(3))),
                    Step(finish("finding", "I counted {r1.count}.")))
    asked_period(env, reply)


def test_p9_not_for_a_count_with_a_period(tmp_path, monkeypatch):
    env = StatsEnv(tmp_path, monkeypatch)
    reply = env.ask(ANALYSIS_WORD_QUESTIONS["trend"],
                    Step(count(MAIN_ID, P5, T.district(3))),
                    Step(finish("finding", "I counted {r1.count}.")))
    assert env.model.answer(0).get("result_id") == "r1", env.model.answer(0)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)


def test_p9_not_when_a_period_is_kept(tmp_path, monkeypatch):
    env = StatsEnv(tmp_path, monkeypatch)
    count_five_years(env)
    reply = env.ask(Q_RISE_AFTER, Step(count(MAIN_ID, filters=T.district(3))),
                    Step(finish("finding", "I counted {r1.count}.")))
    assert env.model.answer(0).get("result_id") == "r1", env.model.answer(0)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    kept_period_note(reply, 2021, 2025)


def test_p9_not_when_a_period_is_pending(tmp_path, monkeypatch):
    env = two_sources(tmp_path, monkeypatch)
    ask_source_with_period(env, P5, tool="count")
    reply = env.ask("The statistics fixture: did it rise?",
                    Step(count(MAIN_ID, filters=T.district(3))),
                    Step(finish("finding", "I counted {r1.count}.")))
    assert env.model.answer(0).get("result_id") == "r1", env.model.answer(0)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)


# ---- point 10: compare and share take counts only -----------------------------------------------

@pytest.mark.needs_r
def test_p10_compare_and_share_naming_an_analysis(tmp_path, monkeypatch):
    env = StatsEnv(tmp_path, monkeypatch)
    reply = env.ask(Q_TREND, Step(count(MAIN_ID, P5)), Step(analyze(T.analyze_arguments(
        "trend_all"))), Step(compare("r1", "a1"), share("a1", "r1"), share("r1", "a1"),
                             compare("r1", "r9")),
                    Step(finish("finding", "I found that {a1.trend}.")))
    assert env.model.answer(1)["result_id"] == "a1", "premise: a1 is an analysis"
    for position, code in ((0, "BAD_COMPARE"), (1, "BAD_SHARE"), (2, "BAD_SHARE")):
        answer = env.model.answer(2, position)
        assert answer == {**answer, "error": code, "why": NOT_A_COUNT_WHY}, (position, answer)
    unknown = env.model.answer(2, 3)
    assert unknown["error"] == "BAD_COMPARE" and unknown.get("why") != NOT_A_COUNT_WHY, unknown
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)


# ---- point 11: the two distribution texts -------------------------------------------------------

@pytest.mark.parametrize("by", ["age", "colour", "female"])
def test_p11_by_that_is_not_a_category_or_yes_or_no_field(tmp_path, monkeypatch, by):
    """S13 point 11: the why word for word (the code is not said: any error; READING)."""
    env = StatsEnv(tmp_path, monkeypatch)
    args = T.analyze_arguments("ages", options={"by": by})
    env.ask(Q_AGES_BY, Step(analyze(args)), Step(finish("finding", "I found that.")))
    assert refused(env).get("why") == BY_WHY, env.model.answer(0)
    assert job_folders(env) == []


def test_p11_distribution_with_two_filters_on_one_field(tmp_path, monkeypatch):
    env = StatsEnv(tmp_path, monkeypatch)
    args = T.analyze_arguments("ages", filters=[T.FEMALE, T.is_("gender", "male")])
    env.ask(Q_AGES_BY, Step(analyze(args)), Step(finish("finding", "I found that.")))
    assert refused(env).get("why") == TWO_ON_ONE_FIELD_WHY, env.model.answer(0)
    assert job_folders(env) == []


# ---- point 13: the date of a before_after in its period -----------------------------------------

@pytest.mark.needs_r
@pytest.mark.parametrize("period", [{"from": "2023-07-15"}, {"date": "2023-07-01"}],
                         ids=["from", "date"])
def test_p13_the_date_in_the_period(tmp_path, monkeypatch, period):
    """S13 point 13: that day's month is the date, and there is no period (the whole copy)."""
    env = StatsEnv(tmp_path, monkeypatch)
    args = T.analyze_arguments("ba_d6", period=period)
    args.pop("options")
    reply = answered(env.ask(Q_AFTER_FEB, Step(analyze(args)),
                             Step(finish("finding", "{a1.step}. {a1.bend}."))))
    answer = env.model.answer(0)
    assert_window(env, reply, answer, WHOLE)
    assert "July 2023" in answer["read_as"], answer["read_as"]
    assert_truth(env, truth_of("before_after", P6, T.district(6), date="2023-07-01"))


@pytest.mark.needs_r
def test_p13_with_options_date_the_period_is_kept(tmp_path, monkeypatch):
    env = StatsEnv(tmp_path, monkeypatch)
    reply = answered(ask_case(env, "ba_d6", text="{a1.step}. {a1.bend}."))
    assert_window(env, reply, env.model.answer(0), FIVE_YEARS)
    assert_estimates(env, "ba_d6")


@pytest.mark.needs_r
def test_p13_with_options_date_a_period_with_only_from_is_no_period(tmp_path, monkeypatch):
    """S13 points 13 and 3 together: point 13 needs no options.date; with one, a period with
    only `from` is no period (point 3), so the whole copy, and the date is options.date."""
    env = StatsEnv(tmp_path, monkeypatch)
    args = T.analyze_arguments("ba_d6", period={"from": "2022-01-15"})
    reply = answered(env.ask(Q_AFTER_FEB, Step(analyze(args)),
                             Step(finish("finding", "{a1.step}. {a1.bend}."))))
    answer = env.model.answer(0)
    assert_window(env, reply, answer, WHOLE)
    assert "July 2023" in answer["read_as"] and "January 2022" not in answer["read_as"], answer
    assert_truth(env, truth_of("before_after", P6, T.district(6), date="2023-07-01"))


# ---- point 14: USE_SHARES ------------------------------------------------------------------------

def _use_shares(answer):
    assert answer == {**answer, "error": "USE_SHARES", "why": USE_SHARES_WHY}, answer


@pytest.mark.parametrize("word", list(SHARE_WORD_QUESTIONS))
def test_p14_a_trend_in_a_turn_with_a_share_word(tmp_path, monkeypatch, word):
    env = StatsEnv(tmp_path, monkeypatch)
    env.ask(SHARE_WORD_QUESTIONS[word], Step(analyze(T.analyze_arguments("trend_all"))),
            Step(finish("finding", "I found that.")))
    _use_shares(env.model.answer(0))
    assert len(env.model.calls) == 2, "the turn goes on"
    assert job_folders(env) == [], "nothing runs"


@pytest.mark.needs_r
def test_p14_once_a_turn_the_second_trend_runs(tmp_path, monkeypatch):
    env = StatsEnv(tmp_path, monkeypatch)
    reply = answered(env.ask(SHARE_WORD_QUESTIONS["share"],
                             Step(analyze(T.analyze_arguments("trend_all"))),
                             Step(analyze(T.analyze_arguments("trend_all"))),
                             Step(finish("finding", "I found that {a1.trend}."))))
    _use_shares(env.model.answer(0))
    assert env.model.answer(1)["result_id"] == "a1", env.model.answer(1)
    assert len(job_folders(env)) == 1
    assert_estimates(env, "trend_all")
    assert reply.status == "ANSWERED"


@pytest.mark.needs_r
def test_p14_then_shares_runs(tmp_path, monkeypatch):
    """S13 point 14 as meant: the hint, then kind shares runs (it is never hinted)."""
    env = StatsEnv(tmp_path, monkeypatch)
    answered(env.ask(SHARE_WORD_QUESTIONS["share"], Step(analyze(T.analyze_arguments("trend_all"))),
                     Step(analyze(T.analyze_arguments("sh_school"))),
                     Step(finish("finding", slot_text("sh_school")))))
    _use_shares(env.model.answer(0))
    assert env.model.answer(1)["result_id"] == "a1"
    assert_estimates(env, "sh_school")


@pytest.mark.needs_r
@pytest.mark.parametrize("name", ["compare_school", "timing"])
def test_p14_only_for_a_trend(tmp_path, monkeypatch, name):
    env = StatsEnv(tmp_path, monkeypatch)
    answered(env.ask(SHARE_WORD_QUESTIONS["share"], Step(analyze(T.analyze_arguments(name))),
                     Step(finish("finding", slot_text(name)))))
    assert env.model.answer(0)["result_id"] == "a1", env.model.answer(0)


@pytest.mark.needs_r
def test_p14_not_in_a_turn_with_no_share_word(tmp_path, monkeypatch):
    env = StatsEnv(tmp_path, monkeypatch)
    answered(env.ask(Q_TREND, Step(analyze(T.analyze_arguments("trend_all"))),
                     Step(finish("finding", "I found that {a1.trend}."))))
    assert env.model.answer(0)["result_id"] == "a1", env.model.answer(0)
    assert_estimates(env, "trend_all")
