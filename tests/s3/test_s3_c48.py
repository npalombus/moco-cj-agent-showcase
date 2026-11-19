"""Stage 3 Part A, C48 (docs/S3A-DESIGN.md; D-065, D-069): a word's tool answer is given once a
turn. Amends C36 points 2 and 3: NOT_RECORDED goes to the first `count` or `analyze` call of the
turn, for a message C29's list or C30 matches; every later call of the turn runs as for any
message. Brief: briefs/S3-R13-A-tests.md. Tests only; the planning chat builds C48. The finding it
answers is DEFECT 2 of kit-log/raw/FABLE-REVIEW-OF-OPUS.md (probes `jail_word_count`,
`probation_office`, `names_of` of kit-log/raw/FABLE-REVIEW-probe-turns.py). All data is SYNTHETIC
fixtures; no real figure is quoted.

Every turn runs through agent.handle_question with the model stand-in (tests/p1/p1support.py's
FakeModel) on the SYNTHETIC fixtures of tests/s3 (one source, arrests_like), talk off unless a
test says.

C48's tests:
- the first call gets NOT_RECORDED, the same call sent again is counted, and the turn is ANSWERED
  with that count (the review's three messages, talk off and on);
- a decline after the answer gives the code's row as today;
- nothing made after the answer gives the code's row as today;
- a message matching both gets one answer, C29's;
- `analyze` after the answer runs;
- SYNTHETIC mode and C36 point 4 as before.

READINGS (also in kit-log/raw/S3-R13-A-notes.txt):
- C48-1. "Runs as for any message": the later call gets the answer the same call gets as the first
  call of a turn after a message with no word of C29's list and no C30 question (a twin message, in
  another thread of the same agent), and the turn ends with the reply that twin turn ends with,
  word for word. The twin's words differ only where they must (the outcome word, or C30's
  `who ... arrested`, taken out).
- Changed by briefs/S3-R16-A-tests.md (C53 point 1 withdraws C30's "names of"): the case "names
  of (the review's names_of)" is now "who was arrested (C30)"; the review's names_of message is
  tests/s3/test_s3_c53.py's (it gets no C30 answer).
- C48-2. "The first `count` or `analyze` call of the turn": the first such call, whatever step it
  is in and whatever came before it (a `describe_data` call is neither); with two calls in one
  step, the first of them.
- C48-3. "Once a turn": each turn of a thread gets the answer at its first call again.
- C48-4. "Inside, the first answer still counts as a request refused with its code": a turn ended
  by the model with nothing made gets C5's row for that code (round 5b's METRIC_ROW and FIELD_ROW,
  written out by hand). A later request refused with another code is not tested (which row ends
  that turn is A7's, not C48's).
- C48-5. `analyze` runs: R is started (stats.run_r, wrapped so each start is recorded, then run
  as it is) and the result is the twin's. Where R must not start (C36 point 4, an analyze that
  is answered), `run_r` is replaced by one that fails if called (round 5b's B10), as
  tests/s3/test_s3_c36.py does.
"""
import pytest

import p1support as p1
from p1support import THREAD_2, Step, ask_user, call, decline, describe, finish, mod
from s3support import A_ID, CountyEnv, check_county_reply, count, is_, year, years
from test_s3_c36 import NOT_RECORDED_C30, ages_not_stated, no_r, not_recorded_c29
from test_s3_round5 import Y25, line1, phrase, spec
from test_s3_round5b import (FIELD_ROW, FINISH, METRIC_ROW, YOUNG, YOUNG_AGES, ages_question,
                             nothing_counted)

D3 = is_("district", "district 3")

# id: (the message, the word as the message has it or None for C30, the request, a twin message
#      without the word, the finding)
CASES = {
    "jail (the review's jail_word_count)": (
        "How many arrests were there in 2025? I am writing about jail overcrowding.", "jail",
        count(A_ID, Y25), "How many arrests were there in 2025?", "I counted {r1.count}."),
    "probation (the review's probation_office)": (
        "How many arrests in district 3 in 2025, for a probation office report?", "probation",
        count(A_ID, Y25, [D3]), "How many arrests in district 3 in 2025, for an office report?",
        "I counted {r1.count}."),
    "who was arrested (C30)": (
        "Who was arrested in district 3 in 2025?", None, count(A_ID, Y25, [D3]),
        "How many people were arrested in district 3 in 2025?", "I counted {r1.count}."),
}
BOTH = "Who was arrested and sent to jail in district 3 in 2025?"   # C29's jail, C30's who
BOTH_TWIN = "How many arrests were there in district 3 in 2025?"


def the_answer(word):
    return not_recorded_c29(word) if word else NOT_RECORDED_C30


def the_row(word):
    return (("UNSUPPORTED", "UNSUPPORTED_METRIC", METRIC_ROW) if word
            else ("UNSUPPORTED", "UNSUPPORTED_FIELD", FIELD_ROW))


def guard():
    return mod("guard")


def test_premise_the_messages_match_c29_or_c30_and_the_twins_do_not():
    for case, (message, word, _, twin, _) in CASES.items():
        assert guard().outcome_word(message) == word, case
        assert guard().asks_who(message) is (word is None), case
        assert guard().outcome_word(twin) is None and not guard().asks_who(twin), case
    assert guard().outcome_word(BOTH) == "jail" and guard().asks_who(BOTH)
    assert guard().outcome_word(BOTH_TWIN) is None and not guard().asks_who(BOTH_TWIN)


def twin_turn(env, twin, *steps):
    """C48-1: the same steps, as the first calls of a turn, after the twin message."""
    reply = env.ask(twin, *steps, thread_key=THREAD_2)
    return reply, env.model.answer(0)


def assert_like_twin(reply, twin):
    check_county_reply(reply)
    assert (reply.status, reply.reason_code) == ("ANSWERED", None), \
        (reply.status, reply.reason_code, reply.text)
    assert (reply.status, reply.reason_code, reply.text, reply.reply_style) == \
        (twin.status, twin.reason_code, twin.text, twin.reply_style), \
        f"not as the twin turn ends.\n--- got ---\n{reply.text}\n--- twin ---\n{twin.text}"
    assert len(reply.run_ids) == len(twin.run_ids) >= 1


# ==== point 1 and 2: the first call is answered, the same call again is counted =================

@pytest.mark.parametrize("talk", [{}, {"MOCO_TALK": "on"}], ids=["talk off", "talk on"])
@pytest.mark.parametrize("case", list(CASES))
def test_the_first_call_gets_not_recorded_and_the_same_call_again_is_counted(tmp_path, monkeypatch,
                                                                             case, talk):
    message, word, request, twin_message, text = CASES[case]
    env = CountyEnv(tmp_path, monkeypatch, **talk)
    twin, twin_answer = twin_turn(env, twin_message, Step(request), Step(finish("finding", text)))
    assert twin.status == "ANSWERED", "premise: the twin is counted"
    reply = env.ask(message, Step(request), Step(request), Step(finish("finding", text)))
    assert len(env.model.calls) == 3, (reply.status, reply.reason_code, reply.text)
    assert env.model.answer(0) == the_answer(word)
    assert env.model.answer(1) == twin_answer, "point 2: the later call runs as for any message"
    assert env.model.answer(1).get("result_id") == "r1"
    assert_like_twin(reply, twin)


def test_the_review_s_jail_message_line_1(tmp_path, monkeypatch):
    """The review's jail_word_count, read on the fixture: the count of 2025, ANSWERED."""
    message, _, request, _, text = CASES["jail (the review's jail_word_count)"]
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask(message, Step(request), Step(request), Step(finish("finding", text)))
    assert (reply.status, reply.reason_code) == ("ANSWERED", None), reply.text
    assert line1(reply) == f"I counted {phrase(spec(Y25))}.", reply.text
    assert "convictions" not in reply.text, reply.text


def test_two_calls_in_one_step_the_first_is_answered_and_the_second_counted(tmp_path, monkeypatch):
    """C48-2: the first call of the turn is the first of the step."""
    message, word, request, twin_message, text = CASES["jail (the review's jail_word_count)"]
    env = CountyEnv(tmp_path, monkeypatch)
    twin, twin_answer = twin_turn(env, twin_message, Step(request), Step(finish("finding", text)))
    reply = env.ask(message, Step(request, request), Step(finish("finding", text)))
    assert env.model.answer(0, 0) == the_answer(word)
    assert env.model.answer(0, 1) == twin_answer
    assert_like_twin(reply, twin)


def test_the_first_count_after_describe_data_is_the_one_answered(tmp_path, monkeypatch):
    """C48-2: describe_data is not a count or analyze call."""
    message, word, request, _, text = CASES["probation (the review's probation_office)"]
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask(message, Step(describe()), Step(request), Step(request),
                    Step(finish("finding", text)))
    assert "facts" in env.model.answer(0), env.model.answer(0)
    assert env.model.answer(1) == the_answer(word)
    assert env.model.answer(2).get("result_id") == "r1", env.model.answer(2)
    assert (reply.status, reply.reason_code) == ("ANSWERED", None), reply.text
    assert line1(reply) == f"I counted {phrase(spec(Y25, [D3]))}.", reply.text


@pytest.mark.parametrize("case", list(CASES))
def test_a_later_call_with_another_request_runs_as_for_any_message(tmp_path, monkeypatch, case):
    """Point 2: a later request that is refused for its own reason gets that reason, not
    NOT_RECORDED (a field no source has); then a decline gives the code's row (point 3)."""
    message, word, request, twin_message, _ = CASES[case]
    bad = count(A_ID, Y25, [is_("charge", "theft")])
    env = CountyEnv(tmp_path, monkeypatch)
    _, twin_answer = twin_turn(env, twin_message, Step(bad),
                               Step(decline("UNRECOGNIZED_QUESTION")))
    assert twin_answer.get("error") not in (None, "NOT_RECORDED"), twin_answer
    code = "UNSUPPORTED_METRIC" if word else "UNSUPPORTED_FIELD"
    reply = env.ask(message, Step(request), Step(bad), Step(decline(code)))
    assert env.model.answer(0) == the_answer(word)
    assert env.model.answer(1) == twin_answer
    assert (reply.status, reply.reason_code, reply.text) == the_row(word)
    nothing_counted(env, reply)


def test_once_a_turn_the_next_turn_gets_the_answer_again(tmp_path, monkeypatch):
    """C48-3: each turn's first call is answered."""
    message, word, request, _, text = CASES["jail (the review's jail_word_count)"]
    env = CountyEnv(tmp_path, monkeypatch)
    first = env.ask(message, Step(request), Step(request), Step(finish("finding", text)))
    assert first.status == "ANSWERED", (first.status, first.reason_code, first.text)
    reply = env.ask("And how many ended in jail in 2024?", Step(count(A_ID, year(2024))),
                    Step(count(A_ID, year(2024))), Step(finish("finding", text)))
    assert env.model.answer(0) == not_recorded_c29("jail")
    assert env.model.answer(1).get("result_id") == "r1", env.model.answer(1)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)


# ==== point 3: inside, the first answer is a request refused with its code ======================

@pytest.mark.parametrize("talk", [{}, {"MOCO_TALK": "on"}], ids=["talk off", "talk on"])
@pytest.mark.parametrize("case", list(CASES))
def test_a_decline_after_the_answer_gives_the_codes_row_as_today(tmp_path, monkeypatch, case,
                                                                 talk):
    message, word, request, _, _ = CASES[case]
    code = "UNSUPPORTED_METRIC" if word else "UNSUPPORTED_FIELD"
    env = CountyEnv(tmp_path, monkeypatch, **talk)
    reply = env.ask(message, Step(request), Step(decline(code)))
    assert env.model.answer(0) == the_answer(word)
    assert (reply.status, reply.reason_code, reply.text) == the_row(word)
    assert reply.reply_style == "fixed"
    nothing_counted(env, reply)


@pytest.mark.parametrize("case", list(CASES))
def test_nothing_made_after_the_answer_gives_the_codes_row_as_today(tmp_path, monkeypatch, case):
    """C48-4: the model ends the turn with a finding and nothing made."""
    message, word, request, _, _ = CASES[case]
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask(message, Step(request), FINISH)
    assert len(env.model.calls) == 2
    assert env.model.answer(0) == the_answer(word)
    assert (reply.status, reply.reason_code, reply.text) == the_row(word)
    nothing_counted(env, reply)


# ==== point 1: one answer a turn in all, C29's first ============================================

def test_a_message_matching_both_gets_one_answer_c29s(tmp_path, monkeypatch):
    request = count(A_ID, Y25, [D3])
    env = CountyEnv(tmp_path, monkeypatch)
    twin, twin_answer = twin_turn(env, BOTH_TWIN, Step(request), FINISH)
    reply = env.ask(BOTH, Step(request), Step(request), FINISH)
    assert env.model.answer(0) == not_recorded_c29("jail")
    assert env.model.answer(1) == twin_answer, "C30's answer is not given after C29's"
    assert_like_twin(reply, twin)


def test_a_message_matching_both_nothing_made_gets_c29s_row(tmp_path, monkeypatch):
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask(BOTH, Step(count(A_ID, Y25, [D3])), FINISH)
    assert env.model.answer(0) == not_recorded_c29("jail")
    assert (reply.status, reply.reason_code, reply.text) == \
        ("UNSUPPORTED", "UNSUPPORTED_METRIC", METRIC_ROW)
    nothing_counted(env, reply)


# ==== point 2: analyze after the answer runs ====================================================

TREND = call("analyze", {"kind": "trend", "source": A_ID, "period": years(2024, 2025)})
TREND_TEXT = "Here it is. {a1.trend}."
JAIL_TREND = "Did arrests go up from 2024 to 2025? I am writing about jail overcrowding."
TREND_TWIN = "Did arrests go up from 2024 to 2025?"


def r_starts(monkeypatch):
    """C48-5: every start of R is recorded, then R runs as it is."""
    stats = mod("stats")
    real, started = stats.run_r, []

    def run_r(*args, **kwargs):
        started.append(args[1] if len(args) > 1 else kwargs.get("kind"))
        return real(*args, **kwargs)
    monkeypatch.setattr(stats, "run_r", run_r)
    return started


@pytest.mark.parametrize("first", ["count", "analyze"])
def test_analyze_after_the_answer_runs(tmp_path, monkeypatch, first):
    started = r_starts(monkeypatch)
    env = CountyEnv(tmp_path, monkeypatch)
    twin, twin_answer = twin_turn(env, TREND_TWIN, Step(TREND), Step(finish("finding", TREND_TEXT)))
    assert started == ["trend"] and twin.status == "ANSWERED", "premise: the twin's R runs"
    opening = count(A_ID, Y25) if first == "count" else TREND
    reply = env.ask(JAIL_TREND, Step(opening), Step(TREND), Step(finish("finding", TREND_TEXT)))
    assert env.model.answer(0) == not_recorded_c29("jail")
    assert started == ["trend", "trend"], "R was not started for the later analyze"
    assert env.model.answer(1) == twin_answer
    assert (reply.status, reply.reason_code, reply.text) == (twin.status, twin.reason_code,
                                                             twin.text), reply.text


def test_after_an_analyze_answered_a_count_is_counted(tmp_path, monkeypatch):
    started = no_r(monkeypatch)
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask(JAIL_TREND, Step(TREND), Step(count(A_ID, Y25)), FINISH)
    assert started == [], "R was started for the answered analyze"
    assert env.model.answer(0) == not_recorded_c29("jail")
    assert env.model.answer(1).get("result_id") == "r1", env.model.answer(1)
    assert (reply.status, reply.reason_code) == ("ANSWERED", None), reply.text
    assert line1(reply) == f"I counted {phrase(spec(Y25))}.", reply.text


# ==== point 4 and SYNTHETIC mode: as before =====================================================

def test_c36_point_4_ages_not_stated_is_still_every_time(tmp_path, monkeypatch):
    started = no_r(monkeypatch)
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask(YOUNG, Step(count(A_ID, Y25, YOUNG_AGES)),
                    Step(count(A_ID, year(2024), YOUNG_AGES)),
                    Step(call("analyze", {"kind": "trend", "source": A_ID,
                                          "period": years(2024, 2025), "filters": YOUNG_AGES})),
                    Step(ask_user("other")))
    assert started == []
    assert [env.model.answer(i) for i in range(3)] == [ages_not_stated("young people")] * 3
    assert (reply.status, reply.reason_code, reply.text) == \
        ("NEEDS_INPUT", "NEEDS_CLARIFICATION", ages_question("young people"))
    nothing_counted(env, reply)


def test_after_c29s_answer_c32s_answer_comes_every_time(tmp_path, monkeypatch):
    """A message with a word of C29's list and an age group in words: the first request is
    answered NOT_RECORDED (C36's order, kept); each later one with ages the message does not
    state gets AGES_NOT_STATED (point 4, every time); then ask_user asks C32's question."""
    question = "How many young people went to jail in 2025?"
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask(question, Step(count(A_ID, Y25, YOUNG_AGES)),
                    Step(count(A_ID, Y25, YOUNG_AGES)), Step(count(A_ID, Y25, YOUNG_AGES)),
                    Step(ask_user("other")))
    assert env.model.answer(0) == not_recorded_c29("jail")
    assert [env.model.answer(1), env.model.answer(2)] == [ages_not_stated("young people")] * 2
    assert (reply.status, reply.reason_code, reply.text) == \
        ("NEEDS_INPUT", "NEEDS_CLARIFICATION", ages_question("young people"))
    nothing_counted(env, reply)


@pytest.mark.parametrize("talk", ["off", "on"])
def test_synthetic_mode_as_before(tmp_path, talk):
    """In SYNTHETIC mode C36's tool answers are not given (its point 7 (f)); with C48 no call of
    the turn gets one either: the model is called at every step and no answer is NOT_RECORDED."""
    env = p1.Env(tmp_path, MOCO_TALK=talk)
    reply = env.ask("How many arrests in 2025 ended in jail?", Step(p1.count(2025, "all")),
                    Step(p1.count(2024, "all")), Step(decline("UNSUPPORTED_METRIC")))
    assert reply.model_called is True and len(env.model.calls) == 3, (reply.status, reply.text)
    answers = [env.model.answer(0), env.model.answer(1)]
    assert all(a.get("error") not in ("NOT_RECORDED", "AGES_NOT_STATED") for a in answers), \
        answers
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", "UNSUPPORTED_METRIC")
