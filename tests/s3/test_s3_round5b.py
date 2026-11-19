"""Stage 3 Part A, round 5b: docs/S3A-DESIGN.md C25 point 0 and C29 to C35 (D-061), and the
planning chat's answers 3 and 6 to the round 5 tests' questions ("Answers to the round 5 tests'
questions", just before C22). Brief: briefs/S3A-R5b-A-tests.md.

The first round 5 file, tests/s3/test_s3_round5.py, covers C21, C25 points 1 to 3 and C26 to
C28 (its C25 tests that send `ask_user` for the period now send it twice, by C25 point 0);
nothing here tests the same thing again. Every test runs turns through agent.handle_question
with the model stand-in (the FakeModel of tests/p1/p1support.py), on the SYNTHETIC fixtures.

C25.0 The first `ask_user` for the period in a turn gives the model the tool error
      NO_PERIOD_QUESTION with its `why` word for word, and the turn goes on (the model then
      counts with a period, or with none and gets C5's question, or asks again); the second
      in the same turn ends it as points 1 to 3 say (one, two and three sources, and two calls
      in one step); `ask_user` for `source` or `other` ends the turn at once, as today, also
      after the error; the next turn gets the error again.
C29   In county mode each word of the list (each stem, capitalised ones, one inside a longer
      question that also asks for a count) ends the turn UNSUPPORTED / UNSUPPORTED_METRIC with
      C5's fixed row: nothing counted, no run record. (C36, D-065, changed by
      briefs/S3-R6-A-tests.md: the model is called; its count is answered NOT_RECORDED and the
      turn it ends with nothing made gets the row. Was: no model call.) `rate`, `percent`,
      `share` and `proportion` go to the model as today. SYNTHETIC mode: the model is called.
C30   `who` + was / were / got / has been / have been + each of the seven verbs and the live
      run's question end the turn UNSUPPORTED / UNSUPPORTED_FIELD, nothing counted (C36:
      through the model and a NOT_RECORDED tool answer, as C29; was: before the model). "How
      many people were arrested", "who is Jeffrey", "who are you" and (C53 point 1, brief
      S3-R16-A; was with the who forms) "the names of" go to the model. SYNTHETIC mode: the
      model is called.
C31   A breakdown by a field whose `in` filter names every label (or all seven days) gives the
      same answer to the model and the same reply, character for character, as the same
      request with no filter on that field (category, person field, coded labels, weekday,
      another order, two breakdowns, another filter beside it). One label left out, or the
      field not in `group_by`: the filter is kept and its `read_as` names the labels.
C32   The question word for word, quoting the words as the message has them (many word forms,
      capitalised ones); NEEDS_INPUT / NEEDS_CLARIFICATION, nothing counted, no run record,
      `missing` `ages` in the stored turn, for `count` and for `analyze` (R is not started).
      (C36 point 4: the request is answered AGES_NOT_STATED and the turn the model ends with
      nothing made asks the question; was: the turn ended at the request.)
      The next message ("18 to 24") is counted for the period the first request stated, with
      its other filters and C9's kept line. Not asked when the message states the ends (N to
      M, under N, over N, a number), when the thread holds an age range for that source (from
      its last answer, or pending), with no age filter, or with none of the words. SYNTHETIC
      mode unchanged.
C33   The system message of a county turn holds the age line word for word for each fixture's
      age field, holds no `"from": 18`, and with that line put back as it was it is exactly
      today's system message (written out by hand).
C34   A year sent as a filter with no period (`is`; `in` with two years and with one; `from`
      and `to` over one, two, three and 51 years) is counted as the period it gives, with the
      same answer, reply and saved spec as the same request sent with that period, the other
      filters and breakdowns kept; also with a period kept from earlier, and for `analyze`.
      Each case "left as today" is as today.
C35   The `why` word for word for one year at 10 (and at 12, coded_like's lowest), 15, 16 and
      17, sent as `from` and `to` alike and as one end cut by the usable ages; the rest of the
      answer, the row that ends the turn, C21's `why` and the bands refusal unchanged.
Answers 3 and 6 (C21): periods cut to the copy are the same days; groups of `year`, `month`,
      `weekday` and `hour` are of the kind of a count of that period, day or hour.

Readings (each is in kit-log/raw/S3A-R5b-A-notes.txt; open ones also in briefs/QUESTIONS.md):
- B1. A tool error is {"error": <code>, "why": ...}; other keys may be there (round 5's R1),
  except C35, where "nothing else of the answer changes": the answer is today's keys exactly.
- B2. "C5's fixed row for that code" (C29, C30) is county mode's row for UNSUPPORTED_METRIC
  or UNSUPPORTED_FIELD, as a `decline` turn gives it today (C23 answer (a)), written out by hand
  for one source.
- B3. "No run record": no runs/<run id>/manifest.json. "No model call": the FakeModel is never
  called and the reply says model_called False.
- B4. C29 "capitals not counting" and C30's `who`, any case (the live question starts "Who").
  C30's words are tested next to each other only ("who was arrested").
- B5. C31 "the same request without it" is sent in another thread of the same agent, so memory
  plays no part; a filter kept from earlier on that field is an open case (accepted both ways).
- B6. C32 "the words as the message has them": the listed form as the message spells it. Where
  a longer and a shorter form overlap ("the elderly" / "elderly", "senior citizens" /
  "senior"), both are accepted (open).
- B7. C32 "an age filter whose ends the message does not state": both ends unstated, or a
  filter with neither end, is asked; one end stated and one not is open (accepted both ways).
- B8. C32 "a number of one to three digits": the 20 and 25 inside "2025" are not stated.
- B9. C32 with no period in the request: whether the ages or the period is asked first is open
  (accepted both ways); every other C32 test sends a period.
- B10. C32 for `analyze`: R is replaced in the test by a function that fails if called; the
  turn must end before it.
- B11. C33 "otherwise as before": the system message is the prompt file (read at test time),
  the sources block and today's date; the block is written out by hand as today's program
  writes it.
- B12. C34 "at most 51 years": 1976 to 2026 is read; 1975 to 2026 (52 years) is left as today.
  C34 for `analyze` is seen through OUT_OF_COVERAGE (a year filter of 2019), before R.
- B13. C35 "one end cut by the usable ages": `to` 10 with no `from`, and `from` 5 `to` 10.
- B14. Answer 3, "the copy's first day": the source file's coverage_start (C24 answer (a)); in
  the cases used, the fixture's first record (2 January 2024) gives the same days.
- B15. Answer 6, weekday and hour: a group is of the kind of a count filtered to that one day
  ({"in": [day]}) or that one hour ({"from": h, "to": h}).
"""
from datetime import date

import pytest

import p1support as p1
from p1support import LEAVE_OUT, THREAD_1, THREAD_2, Step, ask_user, call, decline, finish, \
    manifests, mod
from s3support import (A_ID, AGENT_PROMPT_S3, C_ID, NAMES, NEWEST, CountyEnv, age,
                       age_left_out_line, assert_reply, count, dates, hours, in_, is_, join_and,
                       months, run_records, source_re, truth, turn_json, weekdays, year,
                       years)
from test_s3_round5 import (A, C, LONG_A, LONG_C, NOT_ALLOWED_ROW, OTHER, QUESTION,
                            QUESTION_TWO_TODAY, SHORT, SOURCE_QUESTION_THREE, SOURCE_QUESTION_TWO,
                            U17, U18, WHY, Y25, asked, assert_counted, assert_not_allowed,
                            assert_result, checked, env_for, kept_by_counts, line1, one_turn,
                            phrase, spec, stored_missing, three_sources)

Q = "How many arrests were there in 2025?"
D3 = is_("district", "district 3")
FINISH = Step(finish("finding", "I counted {r1.count}."))


def county_env(tmp_path, monkeypatch, n=1):
    """One, two or three fixture sources offered, each with a copy."""
    if n == 3:
        return three_sources(tmp_path, monkeypatch)
    return CountyEnv(tmp_path, monkeypatch, names=NAMES[:n])


def not_refused(question):
    """A premise: stage 1's guard does not refuse the question (its rule 1). In county mode
    the guard's restrictions do not apply (C0), so nothing else of the guard is assumed."""
    assert mod("guard").screen(question).refuse is None, question
    return question


def nothing_counted(env, reply, earlier=0):
    """No count in this turn and no run record saved by it (`earlier`: records of earlier
    turns)."""
    assert reply.run_ids == [], (reply.status, reply.reason_code, reply.text)
    assert len(manifests(env.runs_dir)) == earlier, "a run record was saved"


# ---- C25 point 0: the first ask_user for the period goes back to the model -------------------------

WHY_NO_PERIOD = ("Do not ask for the period. Call the tool again with the period left out: "
                 "analyze uses every month; count asks the person itself.")
ASK = "Which periods can I ask about?"


def assert_no_period_question(answer):
    assert answer.get("error") == "NO_PERIOD_QUESTION", answer
    assert answer.get("why") == WHY_NO_PERIOD, answer
    assert "result_id" not in answer, answer


@pytest.mark.parametrize("n", [1, 2, 3], ids=["one source", "two sources", "three sources"])
def test_c25_0_the_first_ask_user_for_the_period_gets_the_tool_error(tmp_path, monkeypatch, n):
    """C25.0: the turn does not end; the model then counts with a period and the turn is
    answered as usual."""
    env = county_env(tmp_path, monkeypatch, n)
    reply = env.ask(ASK, Step(ask_user("period")), Step(count(A_ID, Y25)), FINISH)
    assert_no_period_question(env.model.answer(0))
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert len(env.model.calls) == 3
    assert line1(reply) == f"I counted {phrase(spec(Y25))}."
    checked(reply)


def test_c25_0_then_a_count_with_no_period_gets_c5s_question(tmp_path, monkeypatch):
    """C25.0's `why`: "count asks the person itself": the count with no period ends the turn
    with C5's period question."""
    env = county_env(tmp_path, monkeypatch)
    reply = env.ask(ASK, Step(ask_user("period")), Step(count(A_ID)))
    assert_no_period_question(env.model.answer(0))
    assert asked(env, reply, calls=2) == QUESTION[A]
    assert stored_missing(env) == "period"


@pytest.mark.parametrize("n, keep, expected", [
    (1, False, QUESTION[A]),
    (2, False, QUESTION_TWO_TODAY),
    (3, False, SOURCE_QUESTION_THREE),
    (3, True, QUESTION[C]),
], ids=["one source", "two sources", "three sources, none known", "three sources, one kept"])
def test_c25_0_the_second_ask_user_for_the_period_ends_the_turn(tmp_path, monkeypatch, n, keep,
                                                                expected):
    """C25.0: points 1 to 3 apply from the second time in the turn."""
    env = county_env(tmp_path, monkeypatch, n)
    if keep:
        kept_by_counts(env, C)
    reply = env.ask(ASK, Step(ask_user("period")), Step(ask_user("period")))
    assert_no_period_question(env.model.answer(0))
    assert asked(env, reply, calls=2) == expected


def test_c25_0_two_calls_in_one_step(tmp_path, monkeypatch):
    """C25.0: the first call of the step gets the error and the second, in the same turn,
    ends it. The model sees no answer to either, so the turn record's step log (R6: each call
    with Python's answer, or "ended the turn") shows it."""
    env = county_env(tmp_path, monkeypatch)
    reply = env.ask(ASK, Step(ask_user("period"), ask_user("period")))
    assert asked(env, reply) == QUESTION[A]
    assert stored_missing(env) == "period"
    (step,) = turn_json(reply, env.runs_dir)["steps"]
    first, second = step["tool_calls"]
    assert_no_period_question(first["answer"])
    assert second["answer"] == "ended the turn", step


@pytest.mark.parametrize("n, missing, expected", [
    (2, "source", SOURCE_QUESTION_TWO),
    (2, "other", OTHER + " " + LONG_A + " " + LONG_C),
    (3, "source", SOURCE_QUESTION_THREE),
    (3, "other", OTHER + " " + SHORT),
], ids=["two sources, source", "two sources, other", "three sources, source",
        "three sources, other"])
def test_c25_0_ask_user_for_source_or_other_ends_the_turn_at_once(tmp_path, monkeypatch, n,
                                                                  missing, expected):
    """C25: `ask_user` with missing `source` or `other` is unchanged: no tool error, the first
    call ends the turn."""
    env = county_env(tmp_path, monkeypatch, n)
    reply = env.ask("Hmm.", Step(ask_user(missing)), Step(ask_user(missing)))
    assert asked(env, reply) == expected
    assert stored_missing(env) == missing


def test_c25_0_after_the_error_ask_user_for_the_source_ends_the_turn(tmp_path, monkeypatch):
    env = county_env(tmp_path, monkeypatch, 3)
    reply = env.ask(ASK, Step(ask_user("period")), Step(ask_user("source")))
    assert_no_period_question(env.model.answer(0))
    assert asked(env, reply, calls=2) == SOURCE_QUESTION_THREE
    assert stored_missing(env) == "source"


def test_c25_0_the_next_turn_gets_the_error_again(tmp_path, monkeypatch):
    """C25.0 "the first time in a turn": two turns that ended with the question, a turn that
    was answered, and one more: each starts again with the tool error."""
    env = county_env(tmp_path, monkeypatch)
    for _ in range(2):
        reply = env.ask(ASK, Step(ask_user("period")), Step(ask_user("period")))
        assert_no_period_question(env.model.answer(0))
        assert asked(env, reply, calls=2) == QUESTION[A]
    reply = env.ask("2025, then.", Step(ask_user("period")), Step(count(A_ID, Y25)), FINISH)
    assert_no_period_question(env.model.answer(0))
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    reply = env.ask(ASK, Step(ask_user("period")), Step(ask_user("period")))
    assert_no_period_question(env.model.answer(0))
    assert reply.status == "NEEDS_INPUT" and len(env.model.calls) == 2


# ---- C29: what happens after an arrest ------------------------------------------------------------

METRIC_ROW = ("I can't answer that one: I only count records, so I have nothing on convictions, "
              "sentencing, jail or causes. I've noted it as a request. " + LONG_A)
FIELD_ROW = ("I can't break it down that way: no source I have records it. I've noted it as a "
             "request. " + LONG_A)

C29_ENDS = {
    # id: the message (each holds one word of C29's list and no other)
    "convict* (the live run)": "What was the conviction rate in 2025?",
    "convict* (convicted)": "How many of the people arrested in 2025 were convicted?",
    "prosecut*": "How many arrests in 2025 led to a prosecution?",
    "sentenc*": "What sentences followed the 2025 arrests?",
    "jail*": "How many arrests in 2025 ended in jail?",
    "jail* (jailed)": "How many people were jailed after an arrest in 2025?",
    "incarcerat*": "How did incarceration change after the 2025 arrests?",
    "imprison*": "How many arrested in 2025 were imprisoned?",
    "prison": "How many arrests in 2025 ended in prison?",
    "prisons": "Which prisons took the people arrested in 2025?",
    "recidiv*": "What is the recidivism of people arrested in 2025?",
    "acquit*": "How many of the 2025 arrests ended in an acquittal?",
    "guilty": "How many people arrested in 2025 were found guilty?",
    "parole*": "How many arrests in 2025 were of people on parole?",
    "parole* (paroled)": "How many of those arrested in 2025 had been paroled?",
    "probation": "How many arrests in 2025 were of people on probation?",
    "capitalised: CONVICTIONS": "CONVICTIONS after the 2025 arrests?",
    "capitalised: Jail": "Jail after an arrest in 2025: how often?",
    "capitalised: Probation": "Probation: how many of the 2025 arrests?",
    "inside a longer question that also asks for a count":
        "How many arrests were there in district 3 in 2025, and how many of them ended in a "
        "conviction?",
}


@pytest.mark.parametrize("case", list(C29_ENDS))
def test_c29_a_word_of_the_list_is_a_tool_answer_then_the_row(tmp_path, monkeypatch, case):
    """C29 as C36 point 2 makes it (docs/S3A-DESIGN.md; changed by briefs/S3-R6-A-tests.md,
    was test_c29_a_word_of_the_list_ends_the_turn_before_the_model): the model is called, its
    count is answered NOT_RECORDED (the `why` word for word is tests/s3/test_s3_c36.py's), and
    the turn, ended with nothing made, gets C5's row."""
    question = not_refused(C29_ENDS[case])
    env = county_env(tmp_path, monkeypatch)
    reply = env.ask(question, Step(count(A_ID, Y25)), FINISH)
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", "UNSUPPORTED_METRIC"), \
        (reply.status, reply.reason_code, reply.text)
    assert reply.text == METRIC_ROW
    assert len(env.model.calls) == 2 and reply.model_called is True, "the model was not called"
    assert env.model.answer(0).get("error") == "NOT_RECORDED", env.model.answer(0)
    nothing_counted(env, reply)


C29_GOES_ON = {
    "rate": "What was the arrest rate in 2025?",
    "percent": "What percent of the 2025 arrests were near a school?",
    "share": "What share of the 2025 arrests were in district 3?",
    "proportion": "What proportion of the 2025 arrests were of women?",
}


@pytest.mark.parametrize("case", list(C29_GOES_ON))
def test_c29_rate_percent_share_and_proportion_go_to_the_model(tmp_path, monkeypatch, case):
    """C29: shares are answered today and rates per resident are Part S2's."""
    question = not_refused(C29_GOES_ON[case])
    env = county_env(tmp_path, monkeypatch)
    reply = env.ask(question, Step(count(A_ID, Y25)), FINISH)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert len(env.model.calls) == 2
    assert line1(reply) == f"I counted {phrase(spec(Y25))}."


# ---- C30: who a person was --------------------------------------------------------------------------

C30_LINKS = ("was", "were", "got", "has been", "have been")
C30_VERBS = ("arrested", "cited", "stopped", "searched", "charged", "detained", "picked up")
C30_ENDS = {f"who {link} {verb}": f"Who {link} {verb} in district 3 in 2025?"
            for link in C30_LINKS for verb in C30_VERBS}
C30_ENDS.update({
    "the live run's question": "Who was arrested on Georgia Avenue last night?",
    "inside a longer question": "In district 3 in 2025, who got arrested, and how many were there?",
})
# C53 point 1 (docs/S3A-DESIGN.md; brief S3-R16-A) withdraws C30's "names of": these two were
# C30_ENDS cases (test_c30_who_was_arrested_is_a_tool_answer_then_the_row[...]) and now go to the
# model (test_c30_other_questions_go_to_the_model).
NAMES_OF = {
    "the names of": "What are the names of the people arrested in district 3 in 2025?",
    "the names of, another wording": "Give me the names of everyone stopped in 2025.",
}


@pytest.mark.parametrize("case", list(C30_ENDS))
def test_c30_who_was_arrested_is_a_tool_answer_then_the_row(tmp_path, monkeypatch, case):
    """C30 as C36 point 3 makes it (changed by briefs/S3-R6-A-tests.md, was
    test_c30_who_was_arrested_ends_the_turn_before_the_model): the model is called, its count is
    answered NOT_RECORDED, and the turn, ended with nothing made, gets C5's row."""
    question = not_refused(C30_ENDS[case])
    env = county_env(tmp_path, monkeypatch)
    reply = env.ask(question, Step(count(A_ID, Y25, [D3])), FINISH)
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", "UNSUPPORTED_FIELD"), \
        (reply.status, reply.reason_code, reply.text)
    assert reply.text == FIELD_ROW
    assert len(env.model.calls) == 2 and reply.model_called is True, "the model was not called"
    assert env.model.answer(0).get("error") == "NOT_RECORDED", env.model.answer(0)
    nothing_counted(env, reply)


@pytest.mark.parametrize("question, steps", [
    ("How many people were arrested in 2025?", [Step(count(A_ID, Y25)), FINISH]),
    ("Who is Jeffrey?", [Step(decline("UNRECOGNIZED_QUESTION"))]),
    ("Who are you?", [Step(decline("UNRECOGNIZED_QUESTION"))]),
    (NAMES_OF["the names of"], [Step(count(A_ID, Y25, [D3])), FINISH]),
    (NAMES_OF["the names of, another wording"], [Step(count(A_ID, Y25)), FINISH]),
], ids=["how many people were arrested", "who is Jeffrey", "who are you",
        "C53: the names of", "C53: the names of, another wording"])
def test_c30_other_questions_go_to_the_model(tmp_path, monkeypatch, question, steps):
    """Changed by briefs/S3-R16-A-tests.md (C53 point 1): the two "names of" questions were
    test_c30_who_was_arrested_is_a_tool_answer_then_the_row cases; they now go to the model and
    its count is counted."""
    env = county_env(tmp_path, monkeypatch)
    reply = env.ask(not_refused(question), *steps)
    assert len(env.model.calls) == len(steps), (reply.status, reply.reason_code, reply.text)
    assert reply.reason_code != "UNSUPPORTED_FIELD", reply.text
    if len(steps) == 2:
        assert env.model.answer(0).get("result_id") == "r1", env.model.answer(0)
        assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)


# ---- C29, C30 and C32 in SYNTHETIC mode: nothing changes --------------------------------------------

YOUNG = "How many arrests of young people were there in 2025?"  # the live runs (C32)
SYNTHETIC_QUESTIONS = {
    **{f"C29 {k}": v for k, v in C29_ENDS.items()},
    **{f"C30 {k}": {**C30_ENDS, **NAMES_OF}[k] for k in (
        "who was arrested", "who have been picked up", "the live run's question",
        "the names of")},
}


@pytest.mark.parametrize("case", list(SYNTHETIC_QUESTIONS))
def test_synthetic_mode_c29_and_c30_questions_go_to_the_model(tmp_path, case):
    """C29, C30: in SYNTHETIC mode the model is called as today (it declines here)."""
    question = not_refused(SYNTHETIC_QUESTIONS[case])
    code = "UNSUPPORTED_METRIC" if case.startswith("C29") else "UNSUPPORTED_FIELD"
    env = p1.Env(tmp_path)
    reply = env.ask(question, Step(decline(code)))
    assert len(env.model.calls) == 1 and reply.model_called is True, (reply.status, reply.text)
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", code)


def test_synthetic_mode_c32_words_change_nothing(tmp_path):
    """C32: in SYNTHETIC mode "young people" changes nothing: the same steps give the same
    reply as a question without the words."""
    texts, env = [], p1.Env(tmp_path)
    for question, thread in ((YOUNG, THREAD_1), (Q, THREAD_2)):
        reply = env.ask(question, Step(p1.count(2025, "18_25")),
                        Step(finish("finding", p1.ONE_COUNT_TEXT)), thread_key=thread)
        assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
        texts.append(reply.text)
    assert texts[0] == texts[1]


# ---- C31: a filter naming every value of a field the request also breaks down by ------------------

DISTRICTS = [f"district {n}" for n in range(1, 7)]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
GROUPS_TEXT = "I counted {r1.count}. {r1.groups}."

C31_SAME = {
    # id: (source, period, filters sent, filters without the one on that field, group_by)
    "every district, by district": (A, Y25, [in_("district", *DISTRICTS)], [], ["district"]),
    "every district in another order": (A, Y25, [in_("district", *reversed(DISTRICTS))], [],
                                        ["district"]),
    "every district beside another filter": (A, Y25, [is_("gender", "female"),
                                                      in_("district", *DISTRICTS)],
                                             [is_("gender", "female")], ["district"]),
    "every gender, by gender (a person field)": (A, Y25, [in_("gender", "female", "male")], [],
                                                 ["gender"]),
    "every race, by race": (A, Y25, [in_("race", "group Alpha", "group Beta", "group Gamma")],
                            [], ["race"]),
    "coded: every station (labels of two raw values)": (
        C, Y25, [in_("station", "station 1", "station 2", "station 3")], [], ["station"]),
    "all seven days, by weekday": (A, Y25, [weekdays(*DAYS)], [], ["weekday"]),
    "all seven days, Sunday first": (A, Y25, [weekdays(*([DAYS[-1]] + DAYS[:-1]))], [],
                                     ["weekday"]),
    "every district, by district and gender": (A, Y25, [in_("district", *DISTRICTS)], [],
                                               ["district", "gender"]),
    "every district, by gender and district": (A, Y25, [in_("district", *DISTRICTS)], [],
                                               ["gender", "district"]),
    "both fields of two breakdowns": (A, Y25, [in_("district", *DISTRICTS),
                                               in_("gender", "female", "male")], [],
                                      ["district", "gender"]),
}


def ask_in(env, question, request, thread_key, text="I counted {r1.count}."):
    reply = env.ask(question, Step(request), Step(finish("finding", text)),
                    thread_key=thread_key)
    return reply, env.model.answer(0)


@pytest.mark.parametrize("case", list(C31_SAME))
def test_c31_every_label_and_a_breakdown_by_it_is_the_request_without_the_filter(
        tmp_path, monkeypatch, case):
    """C31: the count, its groups, its left-out line and its read_as are those of the same
    request without the filter: the same answer to the model, the same reply character for
    character, the same saved figures."""
    name, period, sent, without, group_by = C31_SAME[case]
    sid = {A: A_ID, C: C_ID}[name]
    env = CountyEnv(tmp_path, monkeypatch, names=(name,))
    text = GROUPS_TEXT if len(group_by) == 1 else "I counted {r1.count}."
    got, got_answer = ask_in(env, Q, count(sid, period, sent, group_by), THREAD_1, text)
    want, want_answer = ask_in(env, Q, count(sid, period, without, group_by), THREAD_2, text)
    assert want.status == "ANSWERED", (want.status, want.reason_code, want.text)
    assert got_answer == want_answer
    assert got.text == want.text, f"--- with the filter ---\n{got.text}\n--- without ---\n{want.text}"
    (got_record,), (want_record,) = run_records(got, env.runs_dir), run_records(want, env.runs_dir)
    assert got_record["computed_values"] == want_record["computed_values"]


def read_as_of(env, request):
    reply, answer = ask_in(env, Q, request, THREAD_1)
    assert "result_id" in answer, answer
    return answer["read_as"]


C31_KEPT = {
    # id: (filters, group_by, read_as) -- the filter is kept, as today
    "one district left out, by district": (
        [in_("district", *DISTRICTS[:5])], ["district"],
        "arrest records in district 1, district 2, district 3, district 4 and district 5 in 2025"),
    "six days, by weekday": (
        [weekdays(*DAYS[:6])], ["weekday"],
        "arrest records on Monday, Tuesday, Wednesday, Thursday, Friday and Saturday in 2025"),
    "every district, no breakdown": (
        [in_("district", *DISTRICTS)], [],
        "arrest records in " + join_and(DISTRICTS) + " in 2025"),
    "every district, by gender": (
        [in_("district", *DISTRICTS)], ["gender"],
        "arrest records in " + join_and(DISTRICTS) + " in 2025"),
    "every gender, by district": (
        [in_("gender", "female", "male")], ["district"],
        "arrest records of people recorded as female and male in 2025"),
}


@pytest.mark.parametrize("case", list(C31_KEPT))
def test_c31_some_labels_or_another_breakdown_keeps_the_filter(tmp_path, monkeypatch, case):
    filters, group_by, expected = C31_KEPT[case]
    env = CountyEnv(tmp_path, monkeypatch)
    assert read_as_of(env, count(A_ID, Y25, filters, group_by)) == expected


def test_c31_open_a_filter_kept_from_earlier_on_that_field(tmp_path, monkeypatch):
    """B5 (open): district 3 kept from the last answer, then every district by district. Read
    one way, the stated filter replaces the kept one (C9) and is then dropped: all districts,
    by district. Read the other way, "as if that filter were not sent" brings district 3 back
    from memory, and C26 then drops the breakdown. Both are accepted."""
    env = CountyEnv(tmp_path, monkeypatch)
    first, _ = ask_in(env, Q, count(A_ID, Y25, [D3]), THREAD_1)
    assert first.status == "ANSWERED"
    reply = env.ask("Show me 2025 arrests by police district.",
                    Step(count(A_ID, Y25, [in_("district", *DISTRICTS)], ["district"])),
                    Step(finish("finding", "I counted {r1.count}.")))
    answer = env.model.answer(0)
    assert answer.get("read_as") in ("arrest records in 2025",
                                     "arrest records in district 3 in 2025"), answer
    if answer["read_as"] == "arrest records in 2025":
        assert answer["slots"] == ["{r1.count}", "{r1.groups}"], answer
    else:
        assert answer["slots"] == ["{r1.count}"], answer
    assert reply.status == "ANSWERED"


# ---- C32: an age group in words with no ages ----------------------------------------------------------

def ages_question(words):
    return f'Which ages do you mean by "{words}"? Say a range of ages and I\'ll count it.'


YOUNG_AGES, OLD_AGES, TEEN_AGES = [age(18, 21)], [age(65)], [age(13, 19)]
C32_FORMS = {
    # id: (message, the age filter the model sends, the words as the message has them)
    "young people (the live runs)": (YOUNG, YOUNG_AGES, "young people"),
    "Young people, capitalised": ("Young people: how many arrests in 2025?", YOUNG_AGES,
                                  "Young people"),
    "young persons": ("How many young persons were arrested in 2025?", YOUNG_AGES,
                      "young persons"),
    "young adults": ("How many arrests of young adults were there in 2025?", YOUNG_AGES,
                     "young adults"),
    "young men": ("How many young men were arrested in 2025?", YOUNG_AGES, "young men"),
    "young women": ("How many young women were arrested in 2025?", YOUNG_AGES, "young women"),
    "young folks": ("How many young folks were arrested in 2025?", YOUNG_AGES, "young folks"),
    "young ones": ("How many young ones were arrested in 2025?", YOUNG_AGES, "young ones"),
    "younger people": ("How many arrests of younger people in 2025?", YOUNG_AGES,
                       "younger people"),
    "Younger adults, capitalised": ("Younger adults: how many arrests in 2025?", YOUNG_AGES,
                                    "Younger adults"),
    "youth": ("How many youth were arrested in 2025?", YOUNG_AGES, "youth"),
    "youths": ("How many youths were arrested in 2025?", YOUNG_AGES, "youths"),
    "the young": ("How many arrests of the young were there in 2025?", YOUNG_AGES, "the young"),
    "old people": ("How many old people were arrested in 2025?", OLD_AGES, "old people"),
    "older persons": ("How many older persons were arrested in 2025?", OLD_AGES,
                      "older persons"),
    "older adults": ("How many arrests of older adults were there in 2025?", OLD_AGES,
                     "older adults"),
    "older men": ("How many older men were arrested in 2025?", OLD_AGES, "older men"),
    "old women": ("How many old women were arrested in 2025?", OLD_AGES, "old women"),
    "old folks": ("How many old folks were arrested in 2025?", OLD_AGES, "old folks"),
    "elderly": ("How many elderly were arrested in 2025?", OLD_AGES, "elderly"),
    "seniors": ("How many seniors were arrested in 2025?", OLD_AGES, "seniors"),
    "senior": ("How many senior arrests were there in 2025?", OLD_AGES, "senior"),
    "SENIORS in capitals": ("HOW MANY SENIORS WERE ARRESTED IN 2025?", OLD_AGES, "SENIORS"),
    "teens": ("How many teens were arrested in 2025?", TEEN_AGES, "teens"),
    "teenager": ("How many times was a teenager arrested in 2025?", TEEN_AGES, "teenager"),
    "teenagers": ("How many teenagers were arrested in 2025?", TEEN_AGES, "teenagers"),
    "Teenagers, capitalised": ("Teenagers arrested in 2025: how many?", TEEN_AGES,
                               "Teenagers"),
    "the ends inside a four-digit year are not stated (B8)": (YOUNG, [age(20, 25)],
                                                              "young people"),
    "a filter with neither end is not stated": (YOUNG, [{"field": "age"}], "young people"),
    "a district beside the age filter": (
        "How many arrests of young people were there in district 3 in 2025?",
        [age(18, 21), D3], "young people"),
}


def assert_ages_asked(env, reply, words, calls=2, earlier=0):
    """C32: NEEDS_INPUT, NEEDS_CLARIFICATION, the question word for word, nothing counted, no
    run record, `missing` `ages` in the stored turn. Changed by briefs/S3-R6-A-tests.md (C36
    point 4; was calls=1, the turn ending at the request): the request is answered
    AGES_NOT_STATED and the model goes on; the turn it ends with nothing made (each caller's
    second step, a finish) asks C32's question as today. The `why` word for word is
    tests/s3/test_s3_c36.py's."""
    assert (reply.status, reply.reason_code) == ("NEEDS_INPUT", "NEEDS_CLARIFICATION"), \
        (reply.status, reply.reason_code, reply.text)
    expected = [ages_question(w) for w in ([words] if isinstance(words, str) else words)]
    assert reply.text in expected, reply.text
    assert len(env.model.calls) == calls
    assert env.model.answer(0).get("error") == "AGES_NOT_STATED", env.model.answer(0)
    nothing_counted(env, reply, earlier)
    assert stored_missing(env) == "ages"
    checked(reply)


@pytest.mark.parametrize("case", list(C32_FORMS))
def test_c32_the_words_and_an_age_filter_the_message_does_not_state(tmp_path, monkeypatch,
                                                                    case):
    question, filters, words = C32_FORMS[case]
    env = county_env(tmp_path, monkeypatch)
    reply = env.ask(not_refused(question), Step(count(A_ID, Y25, filters)), FINISH)
    assert_ages_asked(env, reply, words)


@pytest.mark.parametrize("question, words", [
    ("How many arrests of the elderly were there in 2025?", ("the elderly", "elderly")),
    ("How many senior citizens were arrested in 2025?", ("senior citizens", "senior")),
], ids=["the elderly", "senior citizens"])
def test_c32_open_a_longer_and_a_shorter_form(tmp_path, monkeypatch, question, words):
    """B6 (open): the message holds a listed form inside a longer listed form."""
    env = county_env(tmp_path, monkeypatch)
    reply = env.ask(not_refused(question), Step(count(A_ID, Y25, OLD_AGES)), FINISH)
    assert_ages_asked(env, reply, words)


def test_c32_analyze_is_asked_before_r_is_started(tmp_path, monkeypatch):
    """C32: an `analyze` request with an age filter the message does not state: the same
    question, and the turn ends before R is started (B10)."""
    started = []

    def run_r(*args, **kwargs):
        started.append(args)
        raise AssertionError("R was started")
    monkeypatch.setattr(mod("stats"), "run_r", run_r)
    env = county_env(tmp_path, monkeypatch)
    reply = env.ask(not_refused("Are arrests of young people going up?"),
                    Step(call("analyze", {"kind": "trend", "source": A_ID,
                                          "period": years(2024, 2025), "filters": YOUNG_AGES})),
                    Step(finish("finding", "{a1.trend}.")))
    assert started == [], "R was started"
    assert_ages_asked(env, reply, "young people")


C32_COUNTED = {
    # id: (message, the age filter the model sends) -- counted, as today
    "N to M": ("How many arrests of young people aged 18 to 24 were there in 2025?",
               [age(18, 24)]),
    "under N states to N-1": ("How many arrests of young people under 25 were there in 2025?",
                              [age(None, 24)]),
    "over N states from N+1": ("How many arrests of older adults over 65 were there in 2025?",
                               [age(66)]),
    "a number": ("How many arrests of seniors 70 and older were there in 2025?", [age(70)]),
    "two numbers, teens": ("How many arrests of teens aged 13 to 19 in 2025?", [age(13, 19)]),
    "no age filter": (YOUNG, []),
    "none of the words, a made-up age filter": (Q, [age(18, 21)]),
}


@pytest.mark.parametrize("case", list(C32_COUNTED))
def test_c32_not_asked(tmp_path, monkeypatch, case):
    question, filters = C32_COUNTED[case]
    env = county_env(tmp_path, monkeypatch)
    reply = env.ask(not_refused(question), Step(count(A_ID, Y25, filters)), FINISH)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert line1(reply) == f"I counted {phrase(spec(Y25, filters))}."
    assert len(run_records(reply, env.runs_dir)) == 1


def test_c32_open_one_end_stated_and_one_not(tmp_path, monkeypatch):
    """B7, answered (answer 3 to the round 5b tests, S3A-DESIGN; pinned by brief S3-R16-A, was
    open: asked, or counted as today): "young people under 25" states `to` 24, and the model's
    `from` 18 is not stated. C32 asks when ANY end is unstated: the request is answered
    AGES_NOT_STATED and the turn asks C32's question; nothing is counted."""
    env = county_env(tmp_path, monkeypatch)
    question = "How many arrests of young people under 25 were there in 2025?"
    reply = env.ask(question, Step(count(A_ID, Y25, [age(18, 24)])), FINISH)
    assert_ages_asked(env, reply, "young people")


def test_c32_not_asked_when_the_last_answer_holds_an_age_range(tmp_path, monkeypatch):
    env = county_env(tmp_path, monkeypatch)
    first = env.ask("How many arrests of people aged 18 to 24 were there in 2024?",
                    Step(count(A_ID, year(2024), [age(18, 24)])), FINISH)
    assert first.status == "ANSWERED"
    reply = env.ask("And young people in 2025?", Step(count(A_ID, Y25, [age(18, 24)])), FINISH)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert line1(reply) == f"I counted {phrase(spec(Y25, [age(18, 24)]))}."


def test_c32_not_asked_when_the_pending_request_holds_an_age_range(tmp_path, monkeypatch):
    env = county_env(tmp_path, monkeypatch)
    first = env.ask("How many arrests of people aged 18 to 24?",
                    Step(count(A_ID, LEAVE_OUT, [age(18, 24)])), FINISH)
    assert (first.status, first.text) == ("NEEDS_INPUT", QUESTION[A]), "premise: C5's question"
    reply = env.ask("Young people in 2025.", Step(count(A_ID, Y25, [age(18, 24)])), FINISH)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert line1(reply) == f"I counted {phrase(spec(Y25, [age(18, 24)]))}."


def test_c32_an_age_range_of_another_source_does_not_count(tmp_path, monkeypatch):
    """C32 "for that source": the thread's age range is of coded_like; the request is of
    arrests_like."""
    env = county_env(tmp_path, monkeypatch, 2)
    first = env.ask("How many intake records of people aged 18 to 29 in 2025?",
                    Step(count(C_ID, Y25, [age(18, 29, "age_years")])), FINISH)
    assert first.status == "ANSWERED"
    reply = env.ask("And young people in the arrests of 2025?",
                    Step(count(A_ID, Y25, YOUNG_AGES)), FINISH)
    assert_ages_asked(env, reply, "young people", earlier=1)


def test_c32_the_answer_is_counted_for_the_period_the_request_stated(tmp_path, monkeypatch):
    """C32: the turn saves the source, the period and the other filters; "18 to 24" with no
    period is counted for 2025, with C9's kept line, and not asked again. Changed by
    briefs/S3-R9-A-tests.md: no left-out line (C42 point 1 of docs/S3A-DESIGN.md: the age is a
    filter only); was `(<n> had no usable age and are not included.)`. Changed back by
    briefs/S3-R13-A-tests.md (C49 withdraws C42 point 1): the line, as before round 9."""
    env = county_env(tmp_path, monkeypatch)
    assert_ages_asked(env, env.ask(YOUNG, Step(count(A_ID, Y25, YOUNG_AGES)), FINISH),
                      "young people")
    reply = env.ask("18 to 24", Step(count(LEAVE_OUT, LEAVE_OUT, [age(18, 24)])), FINISH)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    counted = spec(Y25, [age(18, 24)])
    left = truth(A, Y25, [age(18, 24)])["left_out"]["age"]
    assert left > 0, "premise: some are left out"
    assert_reply(reply.text, f"I counted {phrase(counted)}.", kept="(I kept 2025 from earlier.)",
                 left_out=[age_left_out_line(left)], source=source_re(A))
    (record,) = run_records(reply, env.runs_dir)
    assert record["spec"]["period"] == Y25 and record["spec"]["source"] == A_ID


def test_c32_the_answer_keeps_the_other_filters(tmp_path, monkeypatch):
    env = county_env(tmp_path, monkeypatch)
    first = env.ask("How many arrests of young people were there in district 3 in 2025?",
                    Step(count(A_ID, Y25, [age(18, 21), D3])), FINISH)
    assert_ages_asked(env, first, "young people")
    reply = env.ask("18 to 24", Step(count(LEAVE_OUT, LEAVE_OUT, [age(18, 24)])), FINISH)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert line1(reply) == f"I counted {phrase(spec(Y25, [age(18, 24), D3]))}."
    assert "(I kept 2025 and district 3 from earlier.)" in reply.text, reply.text


def test_c32_the_answer_is_counted_from_the_source_of_the_request(tmp_path, monkeypatch):
    """With two sources, the source too is kept with the question."""
    env = county_env(tmp_path, monkeypatch, 2)
    assert_ages_asked(env, env.ask(YOUNG, Step(count(A_ID, Y25, YOUNG_AGES)), FINISH),
                      "young people")
    reply = env.ask("18 to 24", Step(count(LEAVE_OUT, LEAVE_OUT, [age(18, 24)])), FINISH)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    (record,) = run_records(reply, env.runs_dir)
    assert (record["spec"]["source"], record["spec"]["period"]) == (A_ID, Y25)


def test_c32_open_a_request_with_no_period(tmp_path, monkeypatch):
    """B9, answered (answer 4 to the round 5b tests, S3A-DESIGN; pinned by brief S3-R16-A, was
    open: the ages question or the period question first): no period in the request and none
    in the thread: C32 is checked before the period, so the ages are asked first; "18 to 24"
    then gets the period question (the request stated none)."""
    env = county_env(tmp_path, monkeypatch)
    first = env.ask("How many arrests of young people were there?",
                    Step(count(A_ID, LEAVE_OUT, YOUNG_AGES)), FINISH)
    assert first.status == "NEEDS_INPUT", (first.status, first.text)
    assert first.text != QUESTION[A], "answer 4: the ages are asked before the period"
    assert_ages_asked(env, first, "young people")
    reply = env.ask("18 to 24", Step(count(LEAVE_OUT, LEAVE_OUT, [age(18, 24)])), FINISH)
    assert (reply.status, reply.text) == ("NEEDS_INPUT", QUESTION[A]), reply.text


# ---- C33: the age example in the instructions --------------------------------------------------------

def old_age_line(f, low, high):
    return (f'  - {f}: an age range, {{"field": "{f}", "from": 18, "to": 21}}; either end may '
            f'be left out (whole years, {low} to {high}).')


def new_age_line(f, low, high):
    return (f'  - {f}: an age range, {{"field": "{f}", "from": <first age>, "to": <last age>}}, '
            f'only with the ages the message names; either end may be left out (whole years, '
            f'{low} to {high}).')


AGE_LINES = {A: ("age", 10, 98), C: ("age_years", 12, 90)}
WEEKDAY_LINE = '  - weekday: {"field": "weekday", "in": ["Saturday", "Sunday"]}.'
HOUR_LINE = '  - hour: {"field": "hour", "from": 22, "to": 5} (0 to 23; may run past midnight).'
BLOCK_TODAY = {  # today's lines for each fixture, written out by hand (B11)
    A: [
        '- Source "FIXTURE:arrests_like": SYNTHETIC fixture arrests (made up for tests). One '
        'record is one made-up arrest; a count is of arrest records, not people, charges, cases, '
        'convictions, sentences, a rate.',
        "  Copy of 12 November 2026, covering 1 January 2024 to 17 September 2026.",
        "  Filters (at most one per field):",
        old_age_line(*AGE_LINES[A]),
        '  - gender (a person field): {"field": "gender", "is": "<label>"} or "in": [labels]. '
        'Labels: female; male.',
        '  - race (a person field): {"field": "race", "is": "<label>"} or "in": [labels]. '
        'Labels: group Alpha; group Beta; group Gamma.',
        '  - ethnicity (a person field): {"field": "ethnicity", "is": "<label>"} or "in": '
        '[labels]. Labels: Hispanic; not Hispanic.',
        '  - district: {"field": "district", "is": "<label>"} or "in": [labels]. Labels: '
        'district 1; district 2; district 3; district 4; district 5; district 6.',
        '  - adjacent_to_school: {"field": "adjacent_to_school", "is": true} means within 500 '
        'feet of a school; false means not within 500 feet of a school.',
        WEEKDAY_LINE, HOUR_LINE,
        "  Breakdowns (group_by, one or two): gender, race, ethnicity, district, "
        "adjacent_to_school, age_band, year, month, weekday, hour.",
    ],
    C: [
        '- Source "FIXTURE:coded_like": SYNTHETIC fixture intake records (made up for tests). '
        'One record is one made-up intake; a count is of intake records, not people, charges, '
        'cases, a rate.',
        "  Copy of 12 November 2026, covering 1 January 2025 to 20 August 2026.",
        "  Filters (at most one per field):",
        old_age_line(*AGE_LINES[C]),
        '  - race_code (a person field): {"field": "race_code", "is": "<label>"} or "in": '
        '[labels]. Labels: group W; group B; group U.',
        '  - sex (a person field): {"field": "sex", "is": "<label>"} or "in": [labels]. '
        'Labels: female; male.',
        '  - station: {"field": "station", "is": "<label>"} or "in": [labels]. Labels: '
        'station 1; station 2; station 3.',
        WEEKDAY_LINE, HOUR_LINE,
        "  Breakdowns (group_by, one or two): race_code, sex, station, age_band, year, month, "
        "weekday, hour.",
    ],
}
PERIODS_LINE = ('Periods: {"year": 2025}, {"years": [2024, 2025]}, {"year": 2025, "months": '
                '{"from": 1, "to": 10}}, or {"from": "2025-03-01", "to": "2025-08-31"}.')


def system_today(names):
    prompt = AGENT_PROMPT_S3.read_text(encoding="utf-8").strip()
    block = "\n".join(["Sources (from the approved source files; the only data there is)"]
                      + [line for name in names for line in BLOCK_TODAY[name]] + [PERIODS_LINE])
    return "\n\n".join([prompt, block, "Today's date: 2026-11-12"])


def county_system(env, sid=A_ID):
    reply = env.ask(Q, Step(count(sid, Y25)), FINISH)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    messages = env.model.calls[0]["messages"]
    assert messages[0]["role"] == "system", messages[0]
    return messages[0]["content"]


@pytest.mark.parametrize("names", [(A,), (C,), NAMES], ids=["arrests_like", "coded_like", "both"])
def test_c33_the_age_line_word_for_word(tmp_path, monkeypatch, names):
    env = CountyEnv(tmp_path, monkeypatch, names=names)
    system = county_system(env, C_ID if names == (C,) else A_ID)
    lines = system.split("\n")
    for name in names:
        assert new_age_line(*AGE_LINES[name]) in lines, system
    assert '"from": 18' not in system


@pytest.mark.parametrize("names", [(A,), NAMES], ids=["arrests_like", "both"])
def test_c33_nothing_else_of_the_system_message_changes(tmp_path, monkeypatch, names):
    """C33 "No other line changes": with the age line put back as it was, the system message
    is today's, character for character."""
    env = CountyEnv(tmp_path, monkeypatch, names=names)
    system = county_system(env)
    for name in names:
        system = system.replace(new_age_line(*AGE_LINES[name]), old_age_line(*AGE_LINES[name]))
    assert system == system_today(names)


# ---- C34: a year sent as a filter ---------------------------------------------------------------------

def year_filter(**ends):
    return {"field": "year", **{"is" if k == "is_" else k: v for k, v in ends.items()}}


C34_READ = {
    # id: (the year filter, the period it gives)
    "is a year": (year_filter(is_=2024), year(2024)),
    "in two years, given out of order and one twice": (year_filter(**{"in": [2025, 2024, 2025]}),
                                                      years(2024, 2025)),
    "in one year": (year_filter(**{"in": [2025]}), Y25),
    "from and to over two years": (year_filter(**{"from": 2024, "to": 2025}), years(2024, 2025)),
    "from and to over one year (the live runs)": (year_filter(**{"from": 2024, "to": 2024}),
                                                  year(2024)),
    "from and to over three years, the last cut to the copy": (
        year_filter(**{"from": 2024, "to": 2026}), years(2024, 2025, 2026)),
    "from and to over 51 years (B12)": (year_filter(**{"from": 1976, "to": 2026}),
                                        {"years": list(range(1976, 2027))}),
}


def assert_same_turn(env, question, sent, expected):
    """C34: the request with the year filter and no period, and the same request sent with that
    period and no year filter, in another thread: the same answer to the model, the same reply,
    the same saved spec."""
    got, got_answer = ask_in(env, question, sent, THREAD_1)
    want, want_answer = ask_in(env, question, expected, THREAD_2)
    assert want.status == "ANSWERED", (want.status, want.reason_code, want.text)
    assert got_answer == want_answer
    assert got.text == want.text, f"--- the year filter ---\n{got.text}\n--- the period ---\n{want.text}"
    (got_record,), (want_record,) = run_records(got, env.runs_dir), run_records(want, env.runs_dir)
    assert got_record["spec"] == want_record["spec"]
    return got


@pytest.mark.parametrize("case", list(C34_READ))
def test_c34_a_year_filter_with_no_period_is_the_period(tmp_path, monkeypatch, case):
    """C34, with another filter beside the year filter (it is kept)."""
    flt, period = C34_READ[case]
    env = county_env(tmp_path, monkeypatch)
    assert_same_turn(env, "How many arrests in district 3?", count(A_ID, LEAVE_OUT, [flt, D3]),
                     count(A_ID, period, [D3]))


def test_c34_the_live_run_by_race_and_district(tmp_path, monkeypatch):
    """C34's live case: "2024 arrests by race and district." sent as a year filter from 2024 to
    2024, with two breakdowns."""
    env = county_env(tmp_path, monkeypatch)
    assert_same_turn(env, "2024 arrests by race and district.",
                     count(A_ID, LEAVE_OUT, [year_filter(**{"from": 2024, "to": 2024})],
                           ["race", "district"]),
                     count(A_ID, year(2024), [], ["race", "district"]))


def test_c34_the_year_filter_after_another_filter_and_with_a_breakdown(tmp_path, monkeypatch):
    env = county_env(tmp_path, monkeypatch)
    assert_same_turn(env, "Arrests of women by district in 2025?",
                     count(A_ID, LEAVE_OUT, [is_("gender", "female"), year_filter(is_=2025)],
                           ["district"]),
                     count(A_ID, Y25, [is_("gender", "female")], ["district"]))


def test_c34_with_a_period_kept_from_earlier(tmp_path, monkeypatch):
    """C34 reads the request's own period: with 2025 kept from the last answer, a year filter
    of 2024 and no period is counted for 2024, as "and 2024?" sent with that period is, and
    nothing is said to be kept."""
    env = county_env(tmp_path, monkeypatch)
    for thread in (THREAD_1, THREAD_2):
        ask_in(env, Q, count(A_ID, Y25), thread)
    got, got_answer = ask_in(env, "And 2024?", count(LEAVE_OUT, LEAVE_OUT,
                                                    [year_filter(is_=2024)]), THREAD_1)
    want, want_answer = ask_in(env, "And 2024?", count(LEAVE_OUT, year(2024)), THREAD_2)
    assert want.status == "ANSWERED" and "(I kept" not in want.text, want.text
    assert got_answer == want_answer
    assert got.text == want.text


def test_c34_analyze(tmp_path, monkeypatch):
    """C34 for `analyze` (B12): a year filter of 2019 and no period is read as the period 2019,
    so the request is OUT_OF_COVERAGE, as the same request sent with that period is; R is not
    started."""
    def run_r(*args, **kwargs):
        raise AssertionError("R was started")
    monkeypatch.setattr(mod("stats"), "run_r", run_r)
    env = county_env(tmp_path, monkeypatch)
    answers = []
    for sent, thread in (({"filters": [year_filter(is_=2019)]}, THREAD_1),
                         ({"period": year(2019), "filters": []}, THREAD_2)):
        env.ask("Is there a trend in 2019?",
                Step(call("analyze", {"kind": "trend", "source": A_ID, **sent})),
                Step(finish("finding", "{a1.trend}.")), thread_key=thread)
        answers.append(env.model.answer(0))
    assert answers[0] == answers[1]
    assert answers[0].get("error") == "OUT_OF_COVERAGE", answers[0]


C34_TODAY = {
    # id: the filters sent with no period -- left as today: C5's period question
    "two year filters": [year_filter(is_=2024), year_filter(is_=2025)],
    "a value that is not a year (a word)": [year_filter(is_="last year")],
    "a value that is not a year (in a list)": [year_filter(**{"in": [2024, "next"]})],
    "from after to": [year_filter(**{"from": 2025, "to": 2024})],
    "only from": [year_filter(**{"from": 2024})],
    "only to": [year_filter(**{"to": 2025})],
    "a year before 1900": [year_filter(is_=1899)],
    "a year after 2100": [year_filter(is_=2101)],
    "from and to over 52 years (B12)": [year_filter(**{"from": 1975, "to": 2026})],
}


@pytest.mark.parametrize("case", list(C34_TODAY))
def test_c34_left_as_today_with_no_period(tmp_path, monkeypatch, case):
    env = county_env(tmp_path, monkeypatch)
    reply = env.ask(Q, Step(count(A_ID, LEAVE_OUT, C34_TODAY[case])), FINISH)
    assert asked(env, reply) == QUESTION[A]
    assert stored_missing(env) == "period"


@pytest.mark.parametrize("flt", [year_filter(is_=2024), year_filter(**{"from": 2024, "to": 2024})],
                         ids=["is", "from and to"])
def test_c34_left_as_today_with_a_period_also_sent(tmp_path, monkeypatch, flt):
    """C34: with a period, the year filter is refused as today (BAD_FIELD); the period is not
    replaced by the filter."""
    env = county_env(tmp_path, monkeypatch)
    reply = env.ask(Q, Step(count(A_ID, Y25, [flt])), FINISH)
    answer = env.model.answer(0)
    assert answer.get("error") == "BAD_FIELD" and answer.get("field") == "year", answer
    assert reply.status != "ANSWERED", (reply.status, reply.text)
    nothing_counted(env, reply)


# ---- C35: the refusal of one year of age under 18 names a range --------------------------------------

def c35_why(a, b):
    return f"under 18, an age range must cover at least two years, such as {a} to {b}"


C35_CASES = {
    # id: (source, the age filter, the range the why names)
    "10, the lowest usable age, from and to": (A, age(10, 10), (10, 11)),
    "15, from and to": (A, age(15, 15), (15, 16)),
    "16, from and to": (A, age(16, 16), (16, 17)),
    "17, from and to": (A, age(17, 17), (16, 17)),
    "10, to only, cut by the usable ages (B13)": (A, age(None, 10), (10, 11)),
    "10, from 5 to 10, cut by the usable ages (B13)": (A, age(5, 10), (10, 11)),
    "coded: 12, its lowest usable age, from and to": (C, age(12, 12, "age_years"), (12, 13)),
    "coded: 12, to only, cut by the usable ages": (C, age(None, 12, "age_years"), (12, 13)),
    "coded: 16, from and to": (C, age(16, 16, "age_years"), (16, 17)),
    "coded: 17, from and to": (C, age(17, 17, "age_years"), (16, 17)),
}


@pytest.mark.parametrize("case", list(C35_CASES))
def test_c35_the_why_names_a_range(tmp_path, monkeypatch, case):
    """C35: the `why` word for word; nothing else of the answer changes (B1); the turn that
    ends on it ends with the NOT_ALLOWED row as today."""
    name, flt, (a, b) = C35_CASES[case]
    env = CountyEnv(tmp_path, monkeypatch, names=(name,))
    reply = env.ask(Q, Step(count({A: A_ID, C: C_ID}[name], Y25, [flt])), FINISH)
    assert env.model.answer(0) == {"error": "NOT_ALLOWED", "field": flt["field"],
                                   "why": c35_why(a, b)}
    assert reply.reason_code == "NOT_ALLOWED", (reply.status, reply.reason_code, reply.text)
    assert reply.text.startswith(NOT_ALLOWED_ROW), reply.text
    nothing_counted(env, reply)


def test_c35_c21s_why_is_unchanged(tmp_path, monkeypatch):
    """C35 "C21's own why is unchanged": under 17 after under 18 is refused with C21's why."""
    env = county_env(tmp_path, monkeypatch)
    reply, answers = one_turn(env, [spec(Y25, [U18]), spec(Y25, [U17])], answered=1)
    assert answers[1] == {"error": "NOT_ALLOWED", "field": "age", "why": WHY}, answers[1]
    assert_counted(env, reply, 1)


def test_c35_the_bands_refusal_is_unchanged(tmp_path, monkeypatch):
    """C35 changes one `why` only: NOT_ALLOWED for bands of the model's own keeps its own."""
    env = county_env(tmp_path, monkeypatch)
    env.ask(Q, Step(count(A_ID, Y25, [], [{"field": "age_band", "bands": [[10, 13], [14, 17]]}])),
            FINISH)
    assert env.model.answer(0) == {"error": "NOT_ALLOWED", "field": "age_band",
                                   "why": "age bands are the source's own"}


# ---- C21, answers 3 and 6 ------------------------------------------------------------------------------

ALL = []  # no age filter: every usable age
A11 = [age(11)]
ANSWER_REFUSED = {
    # answer 6: a group of year, month, weekday or hour is of the kind of a count of it
    "year: by year for 2024 and 2025, then 11 and over in 2025":
        [spec(years(2024, 2025), ALL, ["year"]), spec(Y25, A11)],
    "year, the narrower count first": [spec(Y25, A11), spec(years(2024, 2025), ALL, ["year"])],
    "year with a district: by year in district 3, then 11 and over in district 3 in 2025":
        [spec(years(2024, 2025), [D3], ["year"]), spec(Y25, [age(11), D3])],
    "year and district: a cell against 11 and over in district 3 in 2025":
        [spec(years(2024, 2025), ALL, ["year", "district"]), spec(Y25, [age(11), D3])],
    "month: by month in 2025, then 11 and over in months 3 to 3 of 2025":
        [spec(Y25, ALL, ["month"]), spec(months(2025, 3, 3), A11)],
    "month: by month in 2025, then 11 and over from 1 to 31 March 2025":
        [spec(Y25, ALL, ["month"]), spec(dates("2025-03-01", "2025-03-31"), A11)],
    "weekday: by weekday in 2025, then 11 and over on Saturdays in 2025":
        [spec(Y25, ALL, ["weekday"]), spec(Y25, [age(11), weekdays("Saturday")])],
    "weekday, the narrower count first":
        [spec(Y25, [age(11), weekdays("Sunday")]), spec(Y25, ALL, ["weekday"])],
    "hour: by hour in 2024 and 2025, then 11 and over at 10 pm":
        [spec(years(2024, 2025), ALL, ["hour"]), spec(years(2024, 2025), [age(11), hours(22, 22)])],
    "under 18 by year (both years), then under 17 in 2025":
        [spec(years(2024, 2025), [U18], ["year"]), spec(Y25, [U17])],
    # answer 3: each period is cut to the copy's first and newest day before they are compared
    "2026, then months 1 to 9 of 2026 (both cut to 17 September)":
        [spec(year(2026), [U18]), spec(months(2026, 1, 9), [U17])],
    "1 January to 31 December 2026, then 1 January to 30 September 2026":
        [spec(dates("2026-01-01", "2026-12-31"), [U18]), spec(dates("2026-01-01", "2026-09-30"), [U17])],
    "1 July 2023 to 31 December 2024, then 2024":
        [spec(dates("2023-07-01", "2024-12-31"), [U18]), spec(year(2024), [U17])],
    "2023 and 2024, then 1 January to 31 December 2024":
        [spec(years(2023, 2024), [U18]), spec(dates("2024-01-01", "2024-12-31"), [U17])],
    "answers 3 and 6: by year for 2025 and 2026, then 11 and over up to the copy's newest day":
        [spec(years(2025, 2026), ALL, ["year"]), spec(dates("2026-01-01", "2026-09-17"), A11)],
    "coded: 2026, then 1 January to 20 August 2026 (its copy's newest day)":
        [spec(year(2026), [age(None, 17, "age_years")], name=C),
         spec(dates("2026-01-01", "2026-08-20"), [age(None, 16, "age_years")], name=C)],
}


@pytest.mark.parametrize("case", list(ANSWER_REFUSED))
def test_c21_answers_3_and_6_refused(tmp_path, monkeypatch, case):
    """The last count is refused by C21 (NOT_ALLOWED, C21's `why`); the counts before it are
    answered; the turn is answered."""
    specs = ANSWER_REFUSED[case]
    env = env_for(tmp_path, monkeypatch, specs)
    reply, answers = one_turn(env, specs, answered=len(specs) - 1)
    for i, answer in enumerate(answers[:-1], 1):
        assert_result(answer, f"r{i}")
    assert_not_allowed(answers[-1], {A: "age", C: "age_years"}[specs[-1]["name"]])
    assert_counted(env, reply, len(specs) - 1)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)


ANSWER_ALLOWED = {
    "month: by month in 2025, then 11 and over in March 2024 (another period)":
        [spec(Y25, ALL, ["month"]), spec(months(2024, 3, 3), A11)],
    "weekday: by weekday in 2025, then 11 and over on Saturdays in 2024":
        [spec(Y25, ALL, ["weekday"]), spec(year(2024), [age(11), weekdays("Saturday")])],
    "hour: by hour in 2024 and 2025, then 11 and over at 10 pm in 2025 (other days)":
        [spec(years(2024, 2025), ALL, ["hour"]), spec(Y25, [age(11), hours(22, 22)])],
    "year: by year for 2024 and 2025, then 18 and over in 2025 (eight years)":
        [spec(years(2024, 2025), ALL, ["year"]), spec(Y25, [age(18)])],
    "answer 3: 2026, then 1 January to 16 September 2026 (one day of the copy apart)":
        [spec(year(2026), [U18]), spec(dates("2026-01-01", "2026-09-16"), [U17])],
}


@pytest.mark.parametrize("case", list(ANSWER_ALLOWED))
def test_c21_answers_3_and_6_allowed(tmp_path, monkeypatch, case):
    specs = ANSWER_ALLOWED[case]
    env = env_for(tmp_path, monkeypatch, specs)
    reply, answers = one_turn(env, specs)
    for i, answer in enumerate(answers, 1):
        assert_result(answer, f"r{i}")
    assert_counted(env, reply, len(specs))
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)


def test_premises_of_this_file():
    """The fixture figures these tests lean on (plain counting): no breakdown used above is
    too fine, and the copies end where the tests say."""
    for name, period, by in ((A, Y25, "month"), (A, Y25, "weekday"), (A, years(2024, 2025), "hour"),
                             (A, years(2024, 2025), "year"), (A, years(2025, 2026), "year"),
                             (A, Y25, "district"), (C, Y25, "station")):
        values = list(truth(name, period, [], [by])["groups"].values())
        assert not [n for n in values if 1 <= n <= 9], (name, period, by, values)
    assert (NEWEST[A], NEWEST[C]) == (date(2026, 9, 17), date(2026, 8, 20))
