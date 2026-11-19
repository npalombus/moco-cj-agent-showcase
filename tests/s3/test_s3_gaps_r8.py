"""Stage 3 round 8 (brief briefs/S3-R8-A-tests.md): tests for the five PROOF GAPS and DEFECT 1
of kit-log/raw/CHAT-BUILDS-check-3.txt, and for R14 (docs/S3S2-DESIGN.md). Tests only; the
planning chat builds the amendments. All data is SYNTHETIC fixtures; no real figure is quoted.

One group per finding:
- PROOF GAP 1 (C36 point 4, amended; S3-R6-A answer 4): `ask_user` after AGES_NOT_STATED in the
  same turn asks C32's question word for word, with its pending and `missing` "ages" (whatever
  `missing` the model sends), and a reply "18 to 24" is then counted for the period the request
  stated. Only C32's question passes.
- PROOF GAP 2 (C36 point 2, amended; S3-R6-A answer 6): C29's and C30's tool answer comes before
  every other check of `count` and `analyze`: a `count` with no period for a message holding a
  word of C29's list and an analysis word gets NOT_RECORDED, not USE_ANALYZE; also before the
  period question, C32's AGES_NOT_STATED, a bad field, USE_SHARES and a bad kind.
- PROOF GAP 3 (C36 point 2, amended; S3-R6-A answer 3): with two words of C29's list the word
  named is the first in the message's order (each case's list order gives another word).
- PROOF GAP 4 (C39, amended; S3-R7-A answer 3): with three or more sources, one of which has an
  interpreted (free-text) field (tests/s3/fixtures/r8_calls_like.json, used with the two
  fixtures, and with visits_like as a fourth), the short about text has no free-text line; with
  two sources the same field's lines are there (the premise that the fixture shows them).
- PROOF GAP 5 (C40 points 2, 3, 4 and 6): the chart read from `chart.json`: the bars in order,
  each label and value, a hidden group with `value` null, `hidden` true and its label ending
  `(fewer than 10)`; the title, the subtitle and the foot line word for word, the foot line with
  C10's sensitive line exactly when the reply carries it (point 3 as amended); `chart.json`
  beside `chart.png` in the first count's run folder and nowhere else. The picture: a PNG of
  1600 by 1000 (its header), and its pixels the same whatever the hidden value is.
- DEFECT 1: rule 9 of both county prompts word for word as C40 point 5 now gives it.
- R14: the slots line of both county prompts word for word.

Changed by briefs/S3-R13-A-tests.md for C48 (docs/S3A-DESIGN.md: C29's and C30's answer is given
once a turn, to the first count or analyze call; every later call runs as for any message; its
tests are tests/s3/test_s3_c48.py). Three tests, each listed old and new in
kit-log/raw/S3-R13-A-notes.txt: in PROOF GAP 2 the second count with no period and the second
trend now get the hint the message's words give them (USE_ANALYZE, USE_SHARES), and in PROOF GAP 3
the second count is counted. The first call's answer, and what it comes before, are unchanged.

READINGS (also in kit-log/raw/S3-R8-A-notes.txt):
- R8-1. `chart.json` holds the four keys point 6 names and no other; each bar the three keys and
  no other. `value` is the count as a JSON number (point 6: "null for a hidden bar"); the
  thousands commas of point 2 are the picture's, which is not read for text.
- R8-2. The subtitle's date is accepted in the three forms s3support's COPY_DATE_RE accepts
  for a copy's date (the contract does not say how it is written); the day is the copy's.
- R8-3. "The groups' own order (the order of the details table)": the order of the reply's own
  table lines, which is also the truth's order (C6: the file's values in file order).
- R8-4. "Never drawn as a height" is checked on the picture without reading it: two turns whose
  records differ only in the hidden group's value (1 and 9) give the same pixels; a premise
  shows that a shown value one apart does change them. The pixels are the PNG's IDAT data,
  inflated with zlib (stdlib), so metadata chunks do not count.
- R8-5. "When the reply carries C10's sensitive line": the reply's text holds the line
  `These are counts of <unit.many>, not rates, and they show no cause.` as one of its lines.
  The foot line is then `<title>. Recorded <unit.many>, not people. ` and that same line.
- R8-6. PROOF GAP 1: "calls ask_user after it in the same turn" is any `missing` the model
  sends (other, period, source): C36 point 4 names none.
- R8-7. PROOF GAP 2: "every other check" is tested at the checks a message's words or the
  model's request can reach first: S13.9's USE_ANALYZE (count, no period), the period question
  (count, no period), C32 (an age filter the message does not state), a field no source has,
  S13.14's USE_SHARES (analyze trend) and a kind analyze does not have.
"""
import json
import re
import zlib
from pathlib import Path

import pytest

from p1support import (PNG_SIGNATURE, THREAD_1, THREAD_2, Step, ask_user, call, decline,
                       describe, finish, manifests, mod)
from s3support import (A_ID, C_ID, COPY_DATE_RE, COPY_NOW, NAMES, Q_ABOUT, Q_BREAKDOWN,
                       Q_COMPARE, CountyEnv, FakeService, FIXTURES, age, count, is_, is_hidden,
                       made_rows, sensitive_line, too_fine, truth, year)
from test_s3_c36 import NOT_RECORDED_C30, ages_not_stated, no_r, not_recorded_c29
from test_s3_c39 import assert_about, expected
from test_s3_c40 import HEIGHT, WIDTH, counts_turn, png_size
from test_s3_round3 import add_visits, real_files
from test_s3_round5 import Y25, line1, phrase, spec, stored_missing
from test_s3_round5b import (C32_FORMS, FINISH, FIELD_ROW, METRIC_ROW, YOUNG, YOUNG_AGES,
                             ages_question, county_env, nothing_counted)

REPO = Path(__file__).resolve().parents[2]
L_ID = "FIXTURE:calls_like"
FLOOR = 10


# ==== PROOF GAP 1: ask_user after AGES_NOT_STATED asks C32's question ===========================

def not_age(filters):
    return [f for f in filters if f.get("field") != "age"]


def assert_c32_asked(env, reply, period, filters, words):
    """C32's question word for word, NEEDS_INPUT and NEEDS_CLARIFICATION, nothing counted, its
    pending (the source, the period stated, the filters other than age) and `missing` "ages"."""
    assert (reply.status, reply.reason_code, reply.text) == \
        ("NEEDS_INPUT", "NEEDS_CLARIFICATION", ages_question(words)), \
        (reply.status, reply.reason_code, reply.text)
    nothing_counted(env, reply)
    assert stored_missing(env) == "ages"
    pending = env.store.recent_turns(THREAD_1, 1)[-1].get("pending")
    assert pending == {"source": A_ID, "period": period, "filters": not_age(filters)}, pending


ASK_USER_MISSING = {"other": list(C32_FORMS),
                    "period": ["young people (the live runs)", "SENIORS in capitals",
                               "a district beside the age filter"],
                    "source": ["young people (the live runs)", "teenagers",
                               "a district beside the age filter"]}
GAP1_CASES = [(case, missing) for missing, cases in ASK_USER_MISSING.items() for case in cases]


@pytest.mark.parametrize("case,missing", GAP1_CASES)
def test_gap1_ask_user_after_ages_not_stated_asks_c32s_question(tmp_path, monkeypatch, case,
                                                                 missing):
    question, filters, words = C32_FORMS[case]
    env = county_env(tmp_path, monkeypatch)
    reply = env.ask(question, Step(count(A_ID, Y25, filters)), Step(ask_user(missing)))
    assert env.model.answer(0) == ages_not_stated(words)
    assert len(env.model.calls) == 2 and reply.model_called is True, \
        (reply.status, reply.reason_code, reply.text)
    assert_c32_asked(env, reply, Y25, filters, words)


Y24 = year(2024)
GAP1_THEN = {
    # id: (the message, the period the request states, the filters the model sends, the words)
    "young people, 2025": (YOUNG, Y25, YOUNG_AGES, "young people"),
    "SENIORS, 2025": (*C32_FORMS["SENIORS in capitals"][:1], Y25,
                      *C32_FORMS["SENIORS in capitals"][1:]),
    "young people in district 3, 2025": (*C32_FORMS["a district beside the age filter"][:1], Y25,
                                         *C32_FORMS["a district beside the age filter"][1:]),
    "young people, 2024": ("How many arrests of young people were there in 2024?", Y24,
                           YOUNG_AGES, "young people"),
}


@pytest.mark.parametrize("case", list(GAP1_THEN))
def test_gap1_then_18_to_24_is_counted_for_the_period_the_request_stated(tmp_path, monkeypatch,
                                                                          case):
    question, period, filters, words = GAP1_THEN[case]
    env = county_env(tmp_path, monkeypatch)
    first = env.ask(question, Step(count(A_ID, period, filters)), Step(ask_user("other")))
    assert_c32_asked(env, first, period, filters, words)
    reply = env.ask("18 to 24", Step(count(filters=[age(18, 24)])), FINISH)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert line1(reply) == \
        f"I counted {phrase(spec(period, [age(18, 24)] + not_age(filters)))}.", reply.text
    assert len(reply.run_ids) == 1 and len(manifests(env.runs_dir)) == 1


# ==== PROOF GAP 2: C29's and C30's answer comes before every other check ========================

GAP2_COUNT_NO_PERIOD = {
    # id: (message with a C29 word and an analysis word, the word, the same without the C29 word)
    "incarceration, change": ("How did incarceration change after the arrests?", "incarceration",
                              "How did arrests change?"),
    "convictions, going up": ("Are convictions going up?", "convictions",
                              "Are arrests going up?"),
    "jail, share": ("What share of arrests ended in jail?", "jail",
                    "What share of arrests were in district 3?"),
    "Probation, over time": ("Probation over time: is it increasing?", "Probation",
                             "Arrests over time: are they increasing?"),
    "sentenced, how old": ("How old were the people sentenced?", "sentenced",
                           "How old were the people arrested?"),
}


def answer_alone(env, question, *calls):
    """Python's answer to the first call of a turn, in another thread of the same agent."""
    env.ask(question, Step(*calls), Step(decline("UNRECOGNIZED_QUESTION")), thread_key=THREAD_2)
    return env.model.answer(0)


@pytest.mark.parametrize("case", list(GAP2_COUNT_NO_PERIOD))
def test_gap2_premise_without_the_word_the_count_gets_use_analyze(tmp_path, monkeypatch, case):
    _, _, twin = GAP2_COUNT_NO_PERIOD[case]
    env = county_env(tmp_path, monkeypatch)
    assert answer_alone(env, twin, count(A_ID)).get("error") == "USE_ANALYZE"


@pytest.mark.parametrize("case", list(GAP2_COUNT_NO_PERIOD))
def test_gap2_count_with_no_period_gets_not_recorded_not_use_analyze(tmp_path, monkeypatch, case):
    """Changed by briefs/S3-R13-A-tests.md (C48; was: both counts answered NOT_RECORDED): the
    first is answered NOT_RECORDED; the second runs as for any message, so the analysis words
    give it S13.9's USE_ANALYZE (as the premise shows for the message without the word)."""
    question, word, _ = GAP2_COUNT_NO_PERIOD[case]
    env = county_env(tmp_path, monkeypatch)
    reply = env.ask(question, Step(count(A_ID)), Step(count(A_ID)),
                    Step(decline("UNSUPPORTED_METRIC")))
    assert env.model.answer(0) == not_recorded_c29(word)
    assert env.model.answer(1).get("error") == "USE_ANALYZE", env.model.answer(1)
    assert (reply.status, reply.reason_code, reply.text) == \
        ("UNSUPPORTED", "UNSUPPORTED_METRIC", METRIC_ROW)
    nothing_counted(env, reply)


def test_gap2_c30_with_an_analysis_word_gets_not_recorded_not_use_analyze(tmp_path, monkeypatch):
    env = county_env(tmp_path, monkeypatch)
    assert answer_alone(env, "Have arrests gone up over time?", count(A_ID)).get("error") == \
        "USE_ANALYZE"
    reply = env.ask("Who was arrested, and has it gone up over time?", Step(count(A_ID)),
                    Step(decline("UNSUPPORTED_FIELD")))
    assert env.model.answer(0) == NOT_RECORDED_C30
    assert (reply.status, reply.reason_code, reply.text) == \
        ("UNSUPPORTED", "UNSUPPORTED_FIELD", FIELD_ROW)
    nothing_counted(env, reply)


def test_gap2_before_the_period_question(tmp_path, monkeypatch):
    """A count with no period and no analysis word: without the word Python asks for the period;
    with it, the count is answered NOT_RECORDED."""
    env = county_env(tmp_path, monkeypatch)
    twin = env.ask("How many arrests were there?", Step(count(A_ID)),
                   Step(decline("UNRECOGNIZED_QUESTION")), thread_key=THREAD_2)
    assert twin.status == "NEEDS_INPUT", (twin.status, twin.reason_code, twin.text)
    reply = env.ask("How many arrests ended in jail?", Step(count(A_ID)),
                    Step(decline("UNSUPPORTED_METRIC")))
    assert env.model.answer(0) == not_recorded_c29("jail")
    assert (reply.status, reply.reason_code, reply.text) == \
        ("UNSUPPORTED", "UNSUPPORTED_METRIC", METRIC_ROW)
    nothing_counted(env, reply)


def test_gap2_before_c32s_ages_not_stated(tmp_path, monkeypatch):
    """A message with a C29 word and an age group in words: NOT_RECORDED, and a turn ended with
    nothing made gets C5's row, not C32's question."""
    env = county_env(tmp_path, monkeypatch)
    assert answer_alone(env, YOUNG, count(A_ID, Y25, YOUNG_AGES)) == \
        ages_not_stated("young people")
    reply = env.ask("How many young people went to jail in 2025?",
                    Step(count(A_ID, Y25, YOUNG_AGES)), FINISH)
    assert env.model.answer(0) == not_recorded_c29("jail")
    assert (reply.status, reply.reason_code, reply.text) == \
        ("UNSUPPORTED", "UNSUPPORTED_METRIC", METRIC_ROW)
    nothing_counted(env, reply)


def test_gap2_before_a_field_no_source_has(tmp_path, monkeypatch):
    env = county_env(tmp_path, monkeypatch)
    bad = [is_("charge", "theft")]
    first = answer_alone(env, "How many theft charges were there in 2025?", count(A_ID, Y25, bad))
    assert first.get("error") not in (None, "NOT_RECORDED"), first
    reply = env.ask("How many theft charges ended in a conviction in 2025?",
                    Step(count(A_ID, Y25, bad)), Step(decline("UNSUPPORTED_METRIC")))
    assert env.model.answer(0) == not_recorded_c29("conviction")
    assert (reply.status, reply.reason_code, reply.text) == \
        ("UNSUPPORTED", "UNSUPPORTED_METRIC", METRIC_ROW)
    nothing_counted(env, reply)


def trend(**extra):
    return call("analyze", {"kind": "trend", "source": A_ID, **extra})


def test_gap2_analyze_before_use_shares(tmp_path, monkeypatch):
    started = no_r(monkeypatch)
    env = county_env(tmp_path, monkeypatch)
    assert answer_alone(env, "What share of arrests were near a school over the years?",
                        trend()).get("error") == "USE_SHARES"
    reply = env.ask("What share of arrests ended in jail over the years?", Step(trend()),
                    Step(trend()), Step(decline("UNSUPPORTED_METRIC")))
    # changed by briefs/S3-R13-A-tests.md (C48; was: both trends answered NOT_RECORDED): the
    # second runs as for any message, so the share words give it S13.14's USE_SHARES (before R)
    assert started == [], "R was started"
    assert env.model.answer(0) == not_recorded_c29("jail")
    assert env.model.answer(1).get("error") == "USE_SHARES", env.model.answer(1)
    assert (reply.status, reply.reason_code, reply.text) == \
        ("UNSUPPORTED", "UNSUPPORTED_METRIC", METRIC_ROW)
    nothing_counted(env, reply)


def test_gap2_analyze_before_a_kind_it_does_not_have(tmp_path, monkeypatch):
    started = no_r(monkeypatch)
    env = county_env(tmp_path, monkeypatch)
    forecast = call("analyze", {"kind": "forecast", "source": A_ID})
    first = answer_alone(env, "Can you forecast arrests?", forecast)
    assert first.get("error") not in (None, "NOT_RECORDED"), first
    reply = env.ask("Can you forecast convictions?", Step(forecast),
                    Step(decline("UNSUPPORTED_METRIC")))
    assert started == [], "R was started"
    assert env.model.answer(0) == not_recorded_c29("convictions")
    assert (reply.status, reply.reason_code, reply.text) == \
        ("UNSUPPORTED", "UNSUPPORTED_METRIC", METRIC_ROW)


def test_gap2_analyze_rate_gets_not_recorded(tmp_path, monkeypatch):
    """The live run's question as a rate per resident: NOT_RECORDED before the rate's checks."""
    started = no_r(monkeypatch)
    env = county_env(tmp_path, monkeypatch)
    reply = env.ask("What was the conviction rate per 10,000 residents in 2025?",
                    Step(call("analyze", {"kind": "rate", "source": A_ID, "period": Y25})), FINISH)
    assert started == [], "R was started"
    assert env.model.answer(0) == not_recorded_c29("conviction")
    assert (reply.status, reply.reason_code, reply.text) == \
        ("UNSUPPORTED", "UNSUPPORTED_METRIC", METRIC_ROW)
    nothing_counted(env, reply)


# ==== PROOF GAP 3: the word named is the first in the message's order ===========================

C29_LIST_ORDER = ("convict", "prosecut", "sentenc", "jail", "incarcerat", "imprison", "prison",
                  "recidiv", "acquit", "guilty", "parole", "probation")  # C29 / guard.py, by hand

GAP3 = {
    # id: (message, the first word in the message's order, the first in the list's order)
    "jail before conviction": ("How many arrests in 2025 ended in jail or a conviction?", "jail",
                               "conviction"),
    "probation before prison": ("How many of the 2025 arrests led to probation or prison?",
                                "probation", "prison"),
    "paroled before sentences": ("Were people paroled after their sentences in 2025?", "paroled",
                                 "sentences"),
    "guilty before prosecutions": ("How many were found guilty, and how many prosecutions "
                                   "followed the 2025 arrests?", "guilty", "prosecutions"),
    "Recidivism before incarceration, capitalised": (
        "Recidivism and incarceration after the 2025 arrests?", "Recidivism", "incarceration"),
    "Jail before a conviction, capitalised": ("Jail, then a conviction: how often in 2025?",
                                              "Jail", "conviction"),
    "three words: acquittals, convictions, sentences": (
        "In 2025, how many acquittals, convictions and sentences were there?", "acquittals",
        "convictions"),
}


def list_rank(word):
    return min(i for i, stem in enumerate(C29_LIST_ORDER) if word.lower().startswith(stem))


def test_gap3_premise_each_case_is_ordered_against_the_list():
    for case, (message, first, by_list) in GAP3.items():
        assert message.index(first) < message.index(by_list), case
        assert list_rank(by_list) < list_rank(first), case


@pytest.mark.parametrize("case", list(GAP3))
def test_gap3_the_word_named_is_the_first_in_the_message(tmp_path, monkeypatch, case):
    """Changed by briefs/S3-R13-A-tests.md (C48; was: both counts answered NOT_RECORDED with the
    word, the decline giving C5's row, nothing counted): the first count names the word; the
    second is counted (r1), so the decline after it ends the turn as a decline after a count does
    today (ANSWERED, the fixed rendering; C41-5)."""
    message, first, _ = GAP3[case]
    env = county_env(tmp_path, monkeypatch)
    reply = env.ask(message, Step(count(A_ID, Y25)), Step(count(A_ID, year(2024))),
                    Step(decline("UNSUPPORTED_METRIC")))
    assert env.model.answer(0) == not_recorded_c29(first)
    assert env.model.answer(1).get("result_id") == "r1", env.model.answer(1)
    assert (reply.status, reply.reason_code, reply.reply_style) == \
        ("ANSWERED", None, "fallback"), (reply.status, reply.reason_code, reply.text)
    assert len(reply.run_ids) == 1


def test_gap3_analyze_names_the_first_word_too(tmp_path, monkeypatch):
    started = no_r(monkeypatch)
    env = county_env(tmp_path, monkeypatch)
    reply = env.ask("Did probation or prison go up from 2024 to 2025?",
                    Step(trend(period={"years": [2024, 2025]})),
                    Step(decline("UNSUPPORTED_METRIC")))
    assert started == [], "R was started"
    assert env.model.answer(0) == not_recorded_c29("probation")
    assert (reply.status, reply.reason_code, reply.text) == \
        ("UNSUPPORTED", "UNSUPPORTED_METRIC", METRIC_ROW)


# ==== PROOF GAP 4: no free-text line in the short about text ====================================

CALLS_SOURCE = FIXTURES / "r8_calls_like.json"
CALLS_ROWS = FIXTURES / "r8_calls_like_rows.json"
FREE_TEXT_HEADING = "Grouped by the agent from free text:"


def calls_source():
    return json.loads(CALLS_SOURCE.read_text(encoding="utf-8"))


def add_calls(env, copy=True):
    """Write the free-text fixture into the env's sources folder as calls_like.json and, with
    `copy`, make its copy through the fake transport (as test_s3_round3.add_visits does)."""
    src = calls_source()
    (env.sources_dir / "calls_like.json").write_text(json.dumps(src, indent=2),
                                                     encoding="utf-8")
    if copy:
        rows = json.loads(CALLS_ROWS.read_text(encoding="utf-8"))["rows"]
        mod("sources").fetch(L_ID, state_dir=env.state_dir,
                             transport=FakeService(rows, address=src["address"]), now=COPY_NOW)
    return env


def free_text_lines(src):
    """What C14 shows for the fixture's interpreted field (each part as its own line)."""
    (f,) = [f for f in src["fields"] if f.get("interpreted")]
    return [FREE_TEXT_HEADING, f"{f['dimension']}: {f['coverage']}", src["interpreted_line"]]


ABOUT_THREE_CALLS = ("I work with 3 sources of Montgomery County open data: arrest records, call "
                     "records and intake records. I count records, not people, and I never show "
                     "a single record. Ask about any one of them for its dates and what it can be "
                     "broken down by.")
ABOUT_FOUR_CALLS = ("I work with 4 sources of Montgomery County open data: arrest records, call "
                    "records, intake records and visit records. I count records, not people, and "
                    "I never show a single record. Ask about any one of them for its dates and "
                    "what it can be broken down by.")
THREE_CALLS = ("arrests_like", "calls_like", "coded_like")  # file order
FOUR_CALLS = THREE_CALLS + ("visits_like",)


def test_gap4_premise_the_fixture_loads_and_two_sources_show_its_free_text_lines(tmp_path,
                                                                                 monkeypatch):
    """No check of C39: the fixture is fit to offer, has an interpreted field, and with two
    sources (C39: "as today") the about text carries its C14 lines."""
    assert mod("sources").problems(calls_source()) == []
    env = add_calls(CountyEnv(tmp_path, monkeypatch, names=("arrests_like",)))
    assert set(mod("sources").load_sources()) == {A_ID, L_ID}
    reply = env.ask(Q_ABOUT, Step(finish("about_data", "Here is what I know.")))
    assert reply.status == "EXPLAINED", (reply.status, reply.reason_code, reply.text)
    for line in free_text_lines(calls_source()):
        assert line in reply.text.split("\n"), (line, reply.text)


def no_describe(env):
    return env.ask(Q_ABOUT, Step(finish("about_data", "Here is what I know."))), "fallback"


def failing_check(env):
    return env.ask(Q_ABOUT, Step(describe()), Step(finish("about_data", "Sadly, {f1}."))), \
        "fallback"


GAP4_WAYS = {"no describe_data": no_describe, "a text that fails": failing_check}


def rendering_of_f1(env):
    """C61 addition 5 (point 9b of docs/S3A-DESIGN.md; added by briefs/S3-R23-A-tests.md): a failed
    about_data text that named {f1} is answered `Here is what I know.` and that fact."""
    (answer,) = [a for a in env.answers() if "facts" in a]
    return "Here is what I know. " + answer["facts"][0]["text"]
GAP4_SETS = {
    "three sources": (NAMES, False, ABOUT_THREE_CALLS, THREE_CALLS),
    "four sources": (NAMES, True, ABOUT_FOUR_CALLS, FOUR_CALLS),
}


def assert_no_free_text(reply):
    src = calls_source()
    for line in free_text_lines(src):
        assert line not in reply.text, (line, reply.text)
    assert src["interpreted_line"] not in reply.text
    assert "free text" not in reply.text


@pytest.mark.parametrize("way", list(GAP4_WAYS))
@pytest.mark.parametrize("which", list(GAP4_SETS))
def test_gap4_the_short_about_text_has_no_free_text_line(tmp_path, monkeypatch, which, way):
    names, visits, text, order = GAP4_SETS[which]
    env = add_calls(CountyEnv(tmp_path, monkeypatch, names=names))
    if visits:
        add_visits(env)
    reply, style = GAP4_WAYS[way](env)
    if way == "a text that fails":  # briefs/S3-R23-A-tests.md: C61 addition 5 (it was `text`)
        text = rendering_of_f1(env)
    assert_about(reply, expected(env, text, order), style)
    assert_no_free_text(reply)


def test_gap4_with_the_fixed_reply_style(tmp_path, monkeypatch):
    env = add_calls(CountyEnv(tmp_path, monkeypatch, names=NAMES, MOCO_REPLY_STYLE="fixed"))
    reply = env.ask(Q_ABOUT, Step(describe()), Step(finish("about_data", "{f1}.")))
    assert_about(reply, expected(env, ABOUT_THREE_CALLS, THREE_CALLS), "fixed")
    assert_no_free_text(reply)


def test_gap4_the_free_text_source_without_a_copy(tmp_path, monkeypatch):
    env = add_calls(CountyEnv(tmp_path, monkeypatch, names=NAMES), copy=False)
    reply, style = no_describe(env)
    assert_about(reply, expected(env, ABOUT_THREE_CALLS, THREE_CALLS), style)
    assert_no_free_text(reply)


def test_gap4_the_real_source_files_short_text_has_no_free_text_line(tmp_path, monkeypatch):
    """The real files of config/sources/ read in place (no copy, nothing fetched): at least one
    has an interpreted field (the check names one); the short about text has none of their
    free-text lines."""
    env = real_files(tmp_path, monkeypatch)
    offered = mod("sources").county_sources()
    lines = [s["interpreted_line"] for s in offered.values()
             if any(f.get("interpreted") for f in s["fields"])]
    assert lines, "premise: a real source file has an interpreted field"
    reply, _ = no_describe(env)
    assert reply.status == "EXPLAINED", (reply.status, reply.reason_code, reply.text)
    assert reply.text.startswith(f"I work with {len(offered)} sources of Montgomery County "
                                 f"open data: "), reply.text
    assert FREE_TEXT_HEADING not in reply.text
    for line in lines:
        assert line not in reply.text, line


# ==== PROOF GAP 5: what the chart shows (chart.json, point 6) ===================================

def chart_record(env, reply):
    """C40 points 4 and 6: chart.png and chart.json side by side in the first count's run
    folder, and in no other run folder of the turn; the record read."""
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert reply.chart_path, f"no chart (C40 point 1): {reply.text}"
    folder = (Path(env.runs_dir) / reply.run_ids[0]).resolve()
    assert Path(reply.chart_path).resolve() == folder / "chart.png", reply.chart_path
    assert png_size(reply.chart_path) == (WIDTH, HEIGHT)
    beside = folder / "chart.json"
    assert beside.is_file(), "no chart.json beside chart.png (C40 point 6)"
    for run_id in reply.run_ids[1:]:
        other = Path(env.runs_dir) / run_id
        assert not (other / "chart.png").exists() and not (other / "chart.json").exists(), run_id
    record = json.loads(beside.read_text(encoding="utf-8"))
    assert set(record) == {"title", "subtitle", "foot", "bars"}, sorted(record)
    for bar in record["bars"]:
        assert set(bar) == {"label", "value", "hidden"}, bar
    return record


def bar(label, n):
    """Point 2 and 6: a shown bar, or a hidden one (value null, label `<label> (fewer than
    10)`)."""
    if is_hidden(n):
        return {"label": f"{label} (fewer than {FLOOR})", "value": None, "hidden": True}
    return {"label": label, "value": n, "hidden": False}


def table_order(reply, labels):
    """The labels of the reply's own table lines (`<label>: <value>`), in the reply's order."""
    return [line.split(": ")[0] for line in reply.text.split("\n")
            if ": " in line and line.split(": ")[0] in labels]


def foot(src, sensitive):
    base = f"{src['title']}. Recorded {src['unit']['many']}, not people."
    return f"{base} {sensitive_line(src['unit']['many'])}" if sensitive else base


def assert_subtitle(record):
    assert re.fullmatch(r"Copy of the county's data of " + COPY_DATE_RE + r"\.",
                        record["subtitle"]), record["subtitle"]


def carries_sensitive_line(reply, src):
    return sensitive_line(src["unit"]["many"]) in reply.text.split("\n")


# The one-way breakdowns of the fixture rows (truth), each with its title (point 3, by hand) and
# whether C10's sensitive line belongs in the reply (a count by or about race, ethnicity or
# gender; coded_like's sex field is marked sensitive as gender is).
FEMALE = is_("gender", "female")
BREAKDOWNS = {
    # id: (source name, filters, the breakdown field, title, sensitive)
    "district": ("arrests_like", [], "district", "Arrest records in 2025, by district", False),
    "gender": ("arrests_like", [], "gender", "Arrest records in 2025, by gender", True),
    "race": ("arrests_like", [], "race", "Arrest records in 2025, by race", True),
    "ethnicity": ("arrests_like", [], "ethnicity", "Arrest records in 2025, by ethnicity", True),
    "district, filtered to female (about gender)": (
        "arrests_like", [FEMALE], "district", None, True),
    "coded_like by station": ("coded_like", [], "station", "Intake records in 2025, by station",
                              False),
    "coded_like by sex": ("coded_like", [], "sex", "Intake records in 2025, by sex", True),
}
SID = {"arrests_like": A_ID, "coded_like": C_ID}


def test_gap5_premise_the_breakdowns_are_drawn_cases():
    """Each breakdown has two or more groups, none 0 (0 is not tested: R8-3), and is not too
    fine; the no-chart premise of C40 point 1 does not apply."""
    for case, (name, filters, by, _, _) in BREAKDOWNS.items():
        groups = truth(name, year(2025), filters, [by])["groups"]
        assert len(groups) >= 2 and 0 not in groups.values(), (case, dict(groups))
        assert not too_fine(list(groups.values())), case


def breakdown_turn(tmp_path, monkeypatch, case):
    name, filters, by, title, sensitive = BREAKDOWNS[case]
    env = CountyEnv(tmp_path, monkeypatch, names=NAMES)
    reply = counts_turn(env, Q_BREAKDOWN, count(SID[name], year(2025), filters, [by]),
                        text="I counted {r1.count}. {r1.groups}.")
    if title is None:  # point 3: the count's read_as, first letter capital, then `, by <dim>`
        read_as = env.answers()[0]["read_as"]
        title = f"{read_as[:1].upper()}{read_as[1:]}, by {by}"
    groups = truth(name, year(2025), filters, [by])["groups"]
    return env, reply, env.source(name), title, sensitive, groups


@pytest.mark.parametrize("case", list(BREAKDOWNS))
def test_gap5_a_breakdowns_chart_json_title_subtitle_and_bars(tmp_path, monkeypatch, case):
    env, reply, src, title, _, groups = breakdown_turn(tmp_path, monkeypatch, case)
    record = chart_record(env, reply)
    assert record["title"] == title == reply.chart_title, (record["title"], reply.chart_title)
    assert_subtitle(record)
    assert table_order(reply, list(groups)) == list(groups), reply.text
    assert record["bars"] == [bar(label, n) for label, n in groups.items()], record["bars"]


@pytest.mark.parametrize("case", list(BREAKDOWNS))
def test_gap5_a_breakdowns_foot_line_word_for_word(tmp_path, monkeypatch, case):
    """Point 3 as amended: the foot line, then C10's sensitive line when the reply has it."""
    env, reply, src, _, sensitive, _ = breakdown_turn(tmp_path, monkeypatch, case)
    assert carries_sensitive_line(reply, src) is sensitive, reply.text
    assert chart_record(env, reply)["foot"] == foot(src, sensitive)


HIDDEN_ROWS = {
    # id: (made_rows groups, the breakdown field, title, sensitive)
    "a hidden female group": (((30, {}), (5, {"gender": "Female"})), "gender",
                              "Arrest records in 2025, by gender", True),
    "a hidden district among five shown": (
        ((12, {"district": "1"}), (12, {"district": "2"}), (4, {"district": "3"}),
         (12, {"district": "4"}), (30, {}), (12, {"district": "6"})), "district",
        "Arrest records in 2025, by district", False),
}


def hidden_turn(tmp_path, monkeypatch, case):
    groups_made, by, title, sensitive = HIDDEN_ROWS[case]
    rows = made_rows("arrests_like", *groups_made)
    env = CountyEnv(tmp_path, monkeypatch, rows={"arrests_like": rows})
    reply = counts_turn(env, Q_BREAKDOWN, count(A_ID, year(2025), [], [by]),
                        text="I counted {r1.count}. {r1.groups}.")
    groups = truth("arrests_like", year(2025), [], [by], rows=rows)["groups"]
    return env, reply, title, sensitive, groups


@pytest.mark.parametrize("case", list(HIDDEN_ROWS))
def test_gap5_a_hidden_groups_bar_value_null_hidden_true_fewer_than_10(tmp_path, monkeypatch,
                                                                       case):
    env, reply, title, _, groups = hidden_turn(tmp_path, monkeypatch, case)
    assert any(is_hidden(n) for n in groups.values()) and not too_fine(list(groups.values()))
    assert 0 not in groups.values(), "premise: no 0 group (QUESTIONS.md, S3-R8-A question 1)"
    record = chart_record(env, reply)
    assert record["title"] == title
    assert_subtitle(record)
    assert record["bars"] == [bar(label, n) for label, n in groups.items()], record["bars"]
    (hidden,) = [b for b in record["bars"] if b["hidden"]]
    assert hidden["value"] is None and hidden["label"].endswith(f" (fewer than {FLOOR})")
    assert json.dumps(record).count(f"(fewer than {FLOOR})") == 1


@pytest.mark.parametrize("case", list(HIDDEN_ROWS))
def test_gap5_a_hidden_groups_foot_line(tmp_path, monkeypatch, case):
    env, reply, _, sensitive, _ = hidden_turn(tmp_path, monkeypatch, case)
    src = env.source("arrests_like")
    assert carries_sensitive_line(reply, src) is sensitive, reply.text
    assert chart_record(env, reply)["foot"] == foot(src, sensitive)


def png_pixels(path):
    """R8-4: the PNG's image data (its IDAT chunks, inflated), without its metadata."""
    data = Path(path).read_bytes()
    assert data[:8] == PNG_SIGNATURE, path
    pos, idat = 8, b""
    while pos < len(data):
        size, kind = int.from_bytes(data[pos:pos + 4], "big"), data[pos + 4:pos + 8]
        if kind == b"IDAT":
            idat += data[pos + 8:pos + 8 + size]
        pos += 12 + size
    return zlib.decompress(idat)


def gender_chart(tmp_path, monkeypatch, male, female):
    rows = made_rows("arrests_like", (male, {}), (female, {"gender": "Female"}))
    env = CountyEnv(tmp_path, monkeypatch, rows={"arrests_like": rows})
    reply = counts_turn(env, Q_BREAKDOWN, count(A_ID, year(2025), [], ["gender"]),
                        text="I counted {r1.count}. {r1.groups}.")
    chart_record(env, reply)
    return png_pixels(reply.chart_path)


def test_gap5_premise_a_shown_value_one_apart_changes_the_picture(tmp_path, monkeypatch):
    assert gender_chart(tmp_path / "a", monkeypatch, 30, 5) != \
        gender_chart(tmp_path / "b", monkeypatch, 31, 5)


def test_gap5_the_hidden_value_is_never_drawn_as_a_height(tmp_path, monkeypatch):
    """Point 2: two turns whose records differ only in the hidden group's value (1 and 9) draw
    the same picture."""
    assert gender_chart(tmp_path / "one", monkeypatch, 30, 1) == \
        gender_chart(tmp_path / "nine", monkeypatch, 30, 9)


COUNTS = {
    # id: (the counts' filters, all of 2025 unless a period is given, title, sensitive)
    "2024 and 2025": ([([], year(2024)), ([], Y25)], "Arrest records compared", False),
    "district 3, 4 and 6": ([([is_("district", f"district {n}")], Y25) for n in (3, 4, 6)],
                            "Arrest records compared", False),
    "female and male (about gender)": ([([FEMALE], Y25), ([is_("gender", "male")], Y25)],
                                       "Arrest records compared", True),
}


@pytest.mark.parametrize("case", list(COUNTS))
def test_gap5_two_or_more_counts_chart_json(tmp_path, monkeypatch, case):
    """Point 2: one bar per count in the order made, labelled with the count's read_as, its
    total as the value; point 3: the title, the subtitle and the foot line."""
    made, title, sensitive = COUNTS[case]
    env = CountyEnv(tmp_path, monkeypatch)
    reply = counts_turn(env, Q_COMPARE, *[count(A_ID, p, f) for f, p in made],
                        text=" ".join(f"I counted {{r{i}.count}}." for i in range(1, len(made) + 1)))
    read_as = [a["read_as"] for a in env.answers() if "result_id" in a]
    assert len(read_as) == len(made)
    record = chart_record(env, reply)
    assert record["title"] == title == reply.chart_title
    assert_subtitle(record)
    totals = [truth("arrests_like", p, f)["total"] for f, p in made]
    assert record["bars"] == [bar(label, n) for label, n in zip(read_as, totals)], record["bars"]
    src = env.source("arrests_like")
    assert carries_sensitive_line(reply, src) is sensitive, reply.text
    assert record["foot"] == foot(src, sensitive)


def test_gap5_two_counts_one_hidden(tmp_path, monkeypatch):
    rows = made_rows("arrests_like", (4, {"district": "3"}), (30, {}))
    env = CountyEnv(tmp_path, monkeypatch, rows={"arrests_like": rows})
    reply = counts_turn(env, Q_COMPARE, count(A_ID, Y25, [is_("district", "district 3")]),
                        count(A_ID, Y25, [is_("district", "district 5")]),
                        text="I counted {r1.count}. I counted {r2.count}.")
    first, second = [a["read_as"] for a in env.answers() if "result_id" in a]
    assert first == "arrest records in district 3 in 2025", first
    record = chart_record(env, reply)
    assert record["bars"] == [
        {"label": f"{first} (fewer than {FLOOR})", "value": None, "hidden": True},
        {"label": second, "value": 30, "hidden": False}], record["bars"]


@pytest.mark.parametrize("calls", [
    [count(A_ID, Y25)],
    [count(A_ID, Y25, [], ["district", "gender"])],
], ids=["one plain count", "a two-way breakdown"])
def test_gap5_no_chart_no_chart_json(tmp_path, monkeypatch, calls):
    env = CountyEnv(tmp_path, monkeypatch)
    reply = counts_turn(env, Q_BREAKDOWN, *calls)
    assert reply.status == "ANSWERED" and reply.chart_path is None, reply.text
    assert list(Path(env.runs_dir).glob("*/chart.json")) == []
    assert list(Path(env.runs_dir).glob("*/chart.png")) == []


# ==== DEFECT 1 and R14: the county prompts ======================================================

PROMPTS = {"agent_prompt_s3": REPO / "config" / "agent_prompt_s3.md",
           "agent_prompt_s3_talk": REPO / "config" / "agent_prompt_s3_talk.md"}


def prompt_lines(name):
    return PROMPTS[name].read_bytes().decode("utf-8").split("\n")


RULE9_START = ("9. If the user wants more about an answer you already sent, or says yes to your "
               "offer of details, call show_details.")
# C40 point 5 as amended on 14 Nov after CHAT-BUILDS-check-3 (DEFECT 1), written out by hand.
# Changed by briefs/S3-R10-A-tests.md to C40 amendment 2 point c (after CHAT-BUILDS-check-4); the
# words before ended "as the only count of the reply, and it comes with a chart."
RULE9_AMENDED = RULE9_START + (
    " If the person asks for a chart or graph of an answer: for change over time call analyze "
    "with kind trend, whose chart shows every month and the trend; for anything else count it "
    "again with one breakdown that shows it, as the only count or analysis of the reply, and "
    "when that breakdown has two or more groups it comes with a chart.")
# C40 point 5's first words, which promised a chart for any count of two or more groups.
RULE9_FIRST = RULE9_START + (
    " If the person asks for a chart or graph of an answer: for change over time call analyze "
    "with kind trend, whose chart shows every month and the trend; for anything else count it "
    "again with the breakdown that shows it, and a count with two or more groups comes with a "
    "chart.")


@pytest.mark.parametrize("name", list(PROMPTS))
def test_defect1_rule_9_word_for_word_as_c40_point_5_amended(name):
    found = prompt_lines(name)
    assert found.count(RULE9_AMENDED) == 1, f"C40 point 5's amended rule 9 is not in {name} once"
    assert RULE9_FIRST not in found, f"rule 9's first C40 words are still in {name}"
    assert sum(line.startswith("9. ") for line in found) == 1


# R14 (docs/S3S2-DESIGN.md), written out by hand.
R14_SLOTS = (
    '- The slots: with no breakdown {a1.rate}; with one, {a1.rate.1}, {a1.rate.2} and so on, one '
    'per group shown, and {a1.ratio.2} and so on, each comparing that group with the reference '
    'group. Use only the slots the tool answer lists, each in its own sentence. The rate slots '
    'already say "per 10,000 residents" and the year: write no number, unit or year of your own, '
    'not even in a lead-in.')
R13_SLOTS = (
    '- The slots: with no breakdown {a1.rate}; with one, {a1.rate.1}, {a1.rate.2} and so on, one '
    'per group shown, and {a1.ratio.2} and so on, each comparing that group with the reference '
    'group. Use only the slots the tool answer lists, each in its own sentence, at most four. '
    'Each slot already says "per 10,000 residents" and the year: write no number, unit or year '
    'of your own, not even in a lead-in.')


@pytest.mark.parametrize("name", list(PROMPTS))
def test_r14_the_slots_line_word_for_word(name):
    found = prompt_lines(name)
    assert found.count(R14_SLOTS) == 1, f"R14's slots line is not in {name} once"
    assert R13_SLOTS not in found, f"R13's slots line is still in {name}"
    assert sum(line.startswith("- The slots: with no breakdown {a1.rate};") for line in found) == 1
