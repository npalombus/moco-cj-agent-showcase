"""Stage 3 Part A, C36 (docs/S3A-DESIGN.md; D-065): in county mode no list of words or exact
phrases in the person's message ends the turn, refuses it, or replies in place of the model. A
word list may only change what a tool answers the model. SYNTHETIC mode is unchanged. Brief:
briefs/S3-R6-A-tests.md. Tests only; the planning chat builds C36.

Every turn runs through agent.handle_question with the model stand-in (tests/p1/p1support.py's
FakeModel) on the SYNTHETIC fixtures of tests/s3 (one source, arrests_like, unless a test says).

C36 point 7, (a) to (f):
(a) Rule 1: each of the three live messages (G01 to G03) reaches the model, with the same tools
    and the same messages as a plain message (nothing added), and a scripted count is counted
    and answered. Talk off and on.
(b) C29: a scripted `count` is answered NOT_RECORDED with the `why` word for word, holding the
    word as the message has it; nothing is counted; a scripted `decline` then gives C5's row;
    `analyze` too (R is not started); a turn that ends with nothing made after it gets C5's
    UNSUPPORTED_METRIC row. (Was also: a second scripted `count` in the turn gets the same
    answer. C48 of docs/S3A-DESIGN.md amends points 2 and 3: the answer is given once a turn,
    to the first count or analyze call, and every later call runs as for any message; changed by
    briefs/S3-R13-A-tests.md, C48's own tests are tests/s3/test_s3_c48.py.)
(c) C30 likewise, with its `why` and C5's UNSUPPORTED_FIELD row (and, since C48, once a turn).
(d) C32: AGES_NOT_STATED with its `why` word for word, nothing counted; then `ask_user` ends
    the turn as `ask_user` ends a county turn today (NEEDS_INPUT, NEEDS_CLARIFICATION); a
    request without an age filter is counted; every time in the turn; `analyze` too; a turn
    that ends with nothing made gets C32's question, its pending and `missing` "ages".
(e) `details` alone calls the model (each of A4's four words), and so does `help` in Slack.
(f) SYNTHETIC mode: rule 1, C29, the details word and `help` behave as today.
Also, as point 6 keeps them: `reset` in county mode is the control it is today.

Readings (also in kit-log/raw/S3-R6-A-notes.txt; open ones also in briefs/QUESTIONS.md):
- C36-1. A tool answer C36 writes out ({"error": ..., "why": ...}) is checked as that whole
  object: these two keys and no other.
- C36-2. "The word as the message has it" is the matching word of C29's list as the message
  spells it (its letters' case kept, the whole word: "convicted", "CONVICTIONS"). Each message
  of round 5b's C29 list holds one word of the list.
- C36-3. A message that holds two words of C29's list: the word named is the first in the
  message's own order (briefs/QUESTIONS.md, S3-R6-A answer 3; C36 point 2 as amended). Was
  open with both orders accepted; changed by briefs/S3-R8-A-tests.md to accept that one only.
- C36-4. "A turn that ends with nothing made" is a `finish` with kind "finding" and a text,
  after only refused requests (round 5b's FINISH).
- C36-5. "As ask_user ends a county turn today": NEEDS_INPUT and NEEDS_CLARIFICATION, and the
  text of the same `ask_user` call after a plain message in another thread of the same agent;
  after AGES_NOT_STATED, C32's question (C36-9).
- C36-6. C32's longer and shorter forms ("the elderly", "senior citizens") are not used here;
  round 5b's open test of them stands.
- C36-7. `details` "calls the model": the model is called once with the message as its latest
  message, and its `show_details` gives the DETAILS reply that the same call gives after a
  plain message (worked out in another thread of the same agent). A model that declines
  instead gets its decline (no reply in its place).
- C36-8. `help` in Slack "calls the model": process_event passes "help" to the agent like any
  message and posts the agent's reply once, labelled by the reply's status. With the real
  agent, the model is called.
- C36-9. After AGES_NOT_STATED, `ask_user` in the same turn asks C32's question (S3-R6-A
  answer 4; C36 point 4 as amended). Was open with today's ask_user text for "other" also
  accepted; changed by briefs/S3-R8-A-tests.md to accept C32's question only (its pending
  and `missing` are tests/s3/test_s3_gaps_r8.py's).
"""
import pytest

import p1support as p1
from p1support import (AGENT_USER, CHANNEL, DM_CHANNEL, DM_KEY, FAKE_SECRETS, HELP_LINE,
                       RESET_LINE, ROOT_TS, TEAM, THREAD_1, THREAD_2, USER, USER2, FakeAgent,
                       FakeModel, FakeSlack, Step, ask_user, call, decline, describe,
                       direct_message, finish, make_reply, manifests, mention, mod, process,
                       show_details)
from s3support import A_ID, C65_RESET_LINE, CountyEnv, count, is_, year, years
from test_s3_round5 import Y25, line1, phrase, spec, stored_missing
from support import SUPPORTED
from test_s3_round5b import (C29_ENDS, C30_ENDS, C32_FORMS, FIELD_ROW, FINISH, METRIC_ROW,
                             YOUNG, YOUNG_AGES, ages_question, county_env, nothing_counted)

Q = "How many arrests were there in 2025?"
D3 = is_("district", "district 3")
SLACK = dict(FAKE_SECRETS, SLACK_ALLOWED_TEAM_ID=TEAM, SLACK_ALLOWED_USER_IDS=f"{USER},{USER2}")


def no_r(monkeypatch):
    """R is replaced by a function that fails if called (round 5b's B10)."""
    started = []

    def run_r(*args, **kwargs):
        started.append(args)
        raise AssertionError("R was started")
    monkeypatch.setattr(mod("stats"), "run_r", run_r)
    return started


def assert_counted(env, reply):
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert line1(reply) == f"I counted {phrase(spec(Y25))}.", reply.text
    assert len(reply.run_ids) == 1 and len(manifests(env.runs_dir)) == 1


# ---- (a) rule 1: the three live messages reach the model ------------------------------------

G = {
    "G01": "Forget the ages, how many arrests were there in 2025?",
    "G02": "Can you confirm that arrests went up from 2024 to 2025?",
    "G03": "Say that again but shorter",
}


def rule_1(question):
    """A premise: stage 1's rule 1 matches the message today (guard.screen refuses it)."""
    assert mod("guard").screen(question).refuse == "UNRECOGNIZED_QUESTION", question
    return question


@pytest.mark.parametrize("talk", [{}, {"MOCO_TALK": "on"}], ids=["talk off", "talk on"])
@pytest.mark.parametrize("case", list(G))
def test_a_rule_1_messages_reach_the_model_and_a_count_is_answered(tmp_path, monkeypatch,
                                                                   case, talk):
    env = CountyEnv(tmp_path, monkeypatch, **talk)
    reply = env.ask(rule_1(G[case]), Step(count(A_ID, Y25)), FINISH)
    assert reply.model_called is True and len(env.model.calls) >= 2, \
        (reply.status, reply.reason_code, reply.text)
    assert reply.reason_code != "UNRECOGNIZED_QUESTION", reply.text
    assert_counted(env, reply)
    assert env.model.answer(0)["result_id"] == "r1"


@pytest.mark.parametrize("case", list(G))
def test_a_rule_1_adds_nothing_to_the_turn(tmp_path, monkeypatch, case):
    """Point 1: "adds nothing": the model gets the same tools and the same messages as for a
    plain message (only the latest message's words differ)."""
    env = CountyEnv(tmp_path, monkeypatch)
    env.ask(rule_1(G[case]), Step(count(A_ID, Y25)), FINISH)
    assert env.model.calls, "the model was not called"
    flagged = env.model.calls[0]
    env.ask(Q, Step(count(A_ID, Y25)), FINISH, thread_key=THREAD_2)
    plain = env.model.calls[0]
    assert flagged["tools"] == plain["tools"]
    assert len(flagged["messages"]) == len(plain["messages"])
    assert flagged["messages"][:-1] == plain["messages"][:-1]
    assert flagged["messages"][-1] == {
        "role": "user", "content": plain["messages"][-1]["content"].replace(Q, G[case])}


# ---- (b) C29 becomes a tool answer -------------------------------------------------------------

C29_WORD = {
    # id (round 5b's C29_ENDS): the word of C29's list as the message has it
    "convict* (the live run)": "conviction",
    "convict* (convicted)": "convicted",
    "prosecut*": "prosecution",
    "sentenc*": "sentences",
    "jail*": "jail",
    "jail* (jailed)": "jailed",
    "incarcerat*": "incarceration",
    "imprison*": "imprisoned",
    "prison": "prison",
    "prisons": "prisons",
    "recidiv*": "recidivism",
    "acquit*": "acquittal",
    "guilty": "guilty",
    "parole*": "parole",
    "parole* (paroled)": "paroled",
    "probation": "probation",
    "capitalised: CONVICTIONS": "CONVICTIONS",
    "capitalised: Jail": "Jail",
    "capitalised: Probation": "Probation",
    "inside a longer question that also asks for a count": "conviction",
}


def not_recorded_c29(word):
    return {"error": "NOT_RECORDED",
            "why": f"The message names {word}, which happens after an arrest: no listed source "
                   f"records it, and a count of records does not answer it. If that is what the "
                   f"message asks for, call decline with UNSUPPORTED_METRIC."}


NOT_RECORDED_C30 = {
    "error": "NOT_RECORDED",
    "why": "The message asks who someone was: no listed source holds a name. If that is what "
           "the message asks for, call decline with UNSUPPORTED_FIELD."}


def test_premise_c29_words_cover_round_5bs_list():
    assert set(C29_WORD) == set(C29_ENDS)
    for case, word in C29_WORD.items():
        assert word in C29_ENDS[case].split(" ") or f"{word}?" in C29_ENDS[case] or \
            f"{word}:" in C29_ENDS[case], case


@pytest.mark.parametrize("case", list(C29_ENDS))
def test_b_c29_count_is_answered_not_recorded_then_decline_gives_the_row(tmp_path, monkeypatch,
                                                                         case):
    env = county_env(tmp_path, monkeypatch)
    reply = env.ask(C29_ENDS[case], Step(count(A_ID, Y25)),
                    Step(decline("UNSUPPORTED_METRIC")))
    assert len(env.model.calls) == 2 and reply.model_called is True, \
        (reply.status, reply.reason_code, reply.text)
    assert env.model.answer(0) == not_recorded_c29(C29_WORD[case])
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", "UNSUPPORTED_METRIC"), \
        (reply.status, reply.reason_code, reply.text)
    assert reply.text == METRIC_ROW
    nothing_counted(env, reply)


@pytest.mark.parametrize("case", ["convict* (the live run)", "capitalised: Jail",
                                  "inside a longer question that also asks for a count"])
def test_b_c29_only_the_first_count_of_the_turn_gets_the_answer(tmp_path, monkeypatch, case):
    """Changed by briefs/S3-R13-A-tests.md (C48 points 1 and 2; was
    test_b_c29_every_count_of_the_turn_gets_the_same_answer: all four counts answered
    NOT_RECORDED, the decline giving C5's row, nothing counted): the first count is answered, the
    three later ones are counted (r1 to r3), and the decline after them ends the turn as a decline
    after a count does today (ANSWERED, the fixed rendering; C41-5)."""
    env = county_env(tmp_path, monkeypatch)
    reply = env.ask(C29_ENDS[case], Step(count(A_ID, Y25)), Step(count(A_ID, year(2024), [D3])),
                    Step(count(A_ID, Y25), count(A_ID, Y25, group_by=["district"])),
                    Step(decline("UNSUPPORTED_METRIC")))
    assert env.model.answer(0) == not_recorded_c29(C29_WORD[case])
    assert [env.model.answer(1).get("result_id"), env.model.answer(2, 0).get("result_id"),
            env.model.answer(2, 1).get("result_id")] == ["r1", "r2", "r3"]
    assert (reply.status, reply.reason_code, reply.reply_style) == \
        ("ANSWERED", None, "fallback"), (reply.status, reply.reason_code, reply.text)
    assert reply.draft_failures == ["DECLINED_AFTER_RESULTS"], reply.draft_failures
    assert len(reply.run_ids) == 3 and len(manifests(env.runs_dir)) == 3


def test_b_c29_analyze_gets_the_same_answer_and_r_is_not_started(tmp_path, monkeypatch):
    started = no_r(monkeypatch)
    env = county_env(tmp_path, monkeypatch)
    question = "Did convictions go up from 2024 to 2025?"
    reply = env.ask(question, Step(call("analyze", {"kind": "trend", "source": A_ID,
                                                    "period": years(2024, 2025)})),
                    Step(decline("UNSUPPORTED_METRIC")))
    assert started == [], "R was started"
    assert env.model.answer(0) == not_recorded_c29("convictions")
    assert (reply.status, reply.reason_code, reply.text) == \
        ("UNSUPPORTED", "UNSUPPORTED_METRIC", METRIC_ROW)
    nothing_counted(env, reply)


@pytest.mark.parametrize("case", ["convict* (the live run)", "prisons", "capitalised: Probation"])
def test_b_c29_nothing_made_gives_the_unsupported_metric_row(tmp_path, monkeypatch, case):
    """Points 2 and 7: inside, the request counts as refused with UNSUPPORTED_METRIC, so a turn
    the model ends with nothing made gets C5's row."""
    env = county_env(tmp_path, monkeypatch)
    reply = env.ask(C29_ENDS[case], Step(count(A_ID, Y25)), FINISH)
    assert env.model.answer(0) == not_recorded_c29(C29_WORD[case])
    assert (reply.status, reply.reason_code, reply.text) == \
        ("UNSUPPORTED", "UNSUPPORTED_METRIC", METRIC_ROW)
    assert len(env.model.calls) == 2
    nothing_counted(env, reply)


def test_b_c29_open_two_words_of_the_list(tmp_path, monkeypatch):
    """C36-3: "jail" comes first in the message, "conviction" first in the list; the word named
    is "jail" (S3-R6-A answer 3; changed by briefs/S3-R8-A-tests.md, both were accepted)."""
    env = county_env(tmp_path, monkeypatch)
    reply = env.ask("How many arrests in 2025 ended in jail or a conviction?",
                    Step(count(A_ID, Y25)), Step(decline("UNSUPPORTED_METRIC")))
    assert env.model.answer(0) == not_recorded_c29("jail")
    assert (reply.status, reply.reason_code, reply.text) == \
        ("UNSUPPORTED", "UNSUPPORTED_METRIC", METRIC_ROW)
    nothing_counted(env, reply)


@pytest.mark.parametrize("question", ["What was the arrest rate in 2025?",
                                      "What share of the 2025 arrests were in district 3?"],
                         ids=["rate", "share"])
def test_b_c29_other_questions_are_counted(tmp_path, monkeypatch, question):
    """No word of C29's list: the count is counted, as today."""
    env = county_env(tmp_path, monkeypatch)
    assert_counted(env, env.ask(question, Step(count(A_ID, Y25)), FINISH))


# ---- (c) C30 becomes a tool answer -------------------------------------------------------------

@pytest.mark.parametrize("case", list(C30_ENDS))
def test_c_c30_count_is_answered_not_recorded_then_decline_gives_the_row(tmp_path, monkeypatch,
                                                                         case):
    env = county_env(tmp_path, monkeypatch)
    reply = env.ask(C30_ENDS[case], Step(count(A_ID, Y25, [D3])),
                    Step(decline("UNSUPPORTED_FIELD")))
    assert len(env.model.calls) == 2 and reply.model_called is True, \
        (reply.status, reply.reason_code, reply.text)
    assert env.model.answer(0) == NOT_RECORDED_C30
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", "UNSUPPORTED_FIELD"), \
        (reply.status, reply.reason_code, reply.text)
    assert reply.text == FIELD_ROW
    nothing_counted(env, reply)


@pytest.mark.parametrize("case", ["the live run's question", "who got arrested",
                                  "who were stopped"])
def test_c_c30_only_the_first_call_of_the_turn_gets_the_answer(tmp_path, monkeypatch, case):
    """Changed by briefs/S3-R16-A-tests.md (C53 point 1 withdraws "names of"): the case "the
    names of, another wording" is now "who were stopped" (its "names of" is
    tests/s3/test_s3_c53.py's). Changed by briefs/S3-R13-A-tests.md (C48 points 1 and 2; was
    test_c_c30_every_count_and_analyze_of_the_turn_gets_the_same_answer: a count, a count and an
    analyze all answered NOT_RECORDED, R not started, the decline giving C5's row): the first
    count is answered; the later count is counted (r1), so the decline after it ends the turn as a
    decline after a count does today. The later analyze is tests/s3/test_s3_c48.py's (R runs)."""
    started = no_r(monkeypatch)
    env = county_env(tmp_path, monkeypatch)
    reply = env.ask(C30_ENDS[case], Step(count(A_ID, Y25, [D3])), Step(count(A_ID, Y25)),
                    Step(decline("UNSUPPORTED_FIELD")))
    assert started == [], "R was started"
    assert env.model.answer(0) == NOT_RECORDED_C30
    assert env.model.answer(1).get("result_id") == "r1", env.model.answer(1)
    assert (reply.status, reply.reason_code, reply.reply_style) == \
        ("ANSWERED", None, "fallback"), (reply.status, reply.reason_code, reply.text)
    assert len(reply.run_ids) == 1


@pytest.mark.parametrize("case", ["the live run's question", "who have been picked up",
                                  "who were detained"])
def test_c_c30_nothing_made_gives_the_unsupported_field_row(tmp_path, monkeypatch, case):
    """Changed by briefs/S3-R16-A-tests.md (C53 point 1): the case "the names of" is now "who
    were detained"."""
    env = county_env(tmp_path, monkeypatch)
    reply = env.ask(C30_ENDS[case], Step(count(A_ID, Y25, [D3])), FINISH)
    assert env.model.answer(0) == NOT_RECORDED_C30
    assert (reply.status, reply.reason_code, reply.text) == \
        ("UNSUPPORTED", "UNSUPPORTED_FIELD", FIELD_ROW)
    assert len(env.model.calls) == 2
    nothing_counted(env, reply)


def test_c_c30_other_questions_are_counted(tmp_path, monkeypatch):
    env = county_env(tmp_path, monkeypatch)
    assert_counted(env, env.ask("How many people were arrested in 2025?",
                                Step(count(A_ID, Y25)), FINISH))


# ---- (d) C32 becomes a tool answer -------------------------------------------------------------

def ages_not_stated(words):
    return {"error": "AGES_NOT_STATED",
            "why": f'The message says "{words}", which names no ages, and this request has ages '
                   f'the message does not state. Call ask_user and ask which ages they mean, or '
                   f'send the request without an age filter.'}


@pytest.mark.parametrize("case", list(C32_FORMS))
def test_d_c32_ages_not_stated_word_for_word_then_ask_user(tmp_path, monkeypatch, case):
    question, filters, words = C32_FORMS[case]
    env = county_env(tmp_path, monkeypatch)
    reply = env.ask(question, Step(count(A_ID, Y25, filters)), Step(ask_user("other")))
    assert len(env.model.calls) == 2 and reply.model_called is True, \
        (reply.status, reply.reason_code, reply.text)
    assert env.model.answer(0) == ages_not_stated(words)
    assert (reply.status, reply.reason_code) == ("NEEDS_INPUT", "NEEDS_CLARIFICATION"), \
        (reply.status, reply.reason_code, reply.text)
    nothing_counted(env, reply)
    # C36-9 (S3-R6-A answer 4; changed by briefs/S3-R8-A-tests.md, today's ask_user text for
    # "other" was also accepted): C32's question only
    assert reply.text == ages_question(words), reply.text


def test_d_c32_a_request_without_an_age_filter_is_counted(tmp_path, monkeypatch):
    env = county_env(tmp_path, monkeypatch)
    reply = env.ask(YOUNG, Step(count(A_ID, Y25, YOUNG_AGES)), Step(count(A_ID, Y25)), FINISH)
    assert env.model.answer(0) == ages_not_stated("young people")
    assert env.model.answer(1)["result_id"] == "r1"
    assert_counted(env, reply)


def test_d_c32_every_request_with_ages_of_the_turn_gets_the_answer(tmp_path, monkeypatch):
    started = no_r(monkeypatch)
    env = county_env(tmp_path, monkeypatch)
    reply = env.ask(YOUNG, Step(count(A_ID, Y25, YOUNG_AGES)),
                    Step(count(A_ID, year(2024), [YOUNG_AGES[0], D3]),
                         call("analyze", {"kind": "trend", "source": A_ID,
                                          "period": years(2024, 2025), "filters": YOUNG_AGES})),
                    Step(ask_user("other")))
    assert started == [], "R was started"
    expected = ages_not_stated("young people")
    assert [env.model.answer(0), env.model.answer(1, 0), env.model.answer(1, 1)] == [expected] * 3
    assert (reply.status, reply.reason_code) == ("NEEDS_INPUT", "NEEDS_CLARIFICATION")
    nothing_counted(env, reply)


@pytest.mark.parametrize("case", ["young people (the live runs)", "SENIORS in capitals",
                                  "a district beside the age filter"])
def test_d_c32_nothing_made_gives_c32s_question_pending_and_missing(tmp_path, monkeypatch, case):
    """Point 4: the model ends the turn with nothing made: C32's question, as today, with its
    pending (the source, the period, the filters other than age) and `missing` "ages"."""
    question, filters, words = C32_FORMS[case]
    env = county_env(tmp_path, monkeypatch)
    reply = env.ask(question, Step(count(A_ID, Y25, filters)), FINISH)
    assert env.model.answer(0) == ages_not_stated(words)
    assert (reply.status, reply.reason_code, reply.text) == \
        ("NEEDS_INPUT", "NEEDS_CLARIFICATION", ages_question(words))
    assert len(env.model.calls) == 2
    nothing_counted(env, reply)
    assert stored_missing(env) == "ages"
    pending = env.store.recent_turns(THREAD_1, 1)[-1].get("pending")
    assert pending == {"source": A_ID, "period": Y25,
                       "filters": [f for f in filters if f.get("field") != "age"]}, pending


def test_d_c32_then_18_to_24_is_counted_for_the_period_stated(tmp_path, monkeypatch):
    env = county_env(tmp_path, monkeypatch)
    first = env.ask(YOUNG, Step(count(A_ID, Y25, YOUNG_AGES)), FINISH)
    assert (first.status, first.text) == ("NEEDS_INPUT", ages_question("young people"))
    reply = env.ask("18 to 24", Step(count(filters=[{"field": "age", "from": 18, "to": 24}])),
                    FINISH)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert line1(reply) == \
        f"I counted {phrase(spec(Y25, [{'field': 'age', 'from': 18, 'to': 24}]))}."


def test_d_c32_analyze_gets_the_answer_before_r(tmp_path, monkeypatch):
    started = no_r(monkeypatch)
    env = county_env(tmp_path, monkeypatch)
    reply = env.ask("Are arrests of young people going up?",
                    Step(call("analyze", {"kind": "trend", "source": A_ID,
                                          "period": years(2024, 2025), "filters": YOUNG_AGES})),
                    Step(ask_user("other")))
    assert started == [], "R was started"
    assert env.model.answer(0) == ages_not_stated("young people")
    assert (reply.status, reply.reason_code) == ("NEEDS_INPUT", "NEEDS_CLARIFICATION")
    nothing_counted(env, reply)


# ---- (e) `details` alone and `help` in Slack call the model ------------------------------------

def answered_first(env):
    reply = env.ask(Q, Step(count(A_ID, Y25)), FINISH)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    return reply


@pytest.mark.parametrize("word", ["details", "detail", "more", "more details", "Details?",
                                  "MORE DETAILS!", "  more  "])
def test_e_details_alone_calls_the_model(tmp_path, monkeypatch, word):
    env = county_env(tmp_path, monkeypatch)
    first = answered_first(env)
    first_twin = env.ask(Q, Step(count(A_ID, Y25)), FINISH, thread_key=THREAD_2)
    assert first_twin.status == "ANSWERED"
    twin = env.ask("Can I see the full breakdown of that?", Step(show_details()),
                   thread_key=THREAD_2)
    assert twin.status == "DETAILS", (twin.status, twin.reason_code, twin.text)
    reply = env.ask(word, Step(show_details()))
    assert reply.model_called is True and len(env.model.calls) == 1, \
        (reply.status, reply.reason_code, reply.text)
    latest = env.model.calls[0]["messages"][-1]
    assert latest == {"role": "user", "content": f"{p1.LATEST_HEADER}\n{word}"}, latest
    assert (reply.status, reply.reason_code) == ("DETAILS", None), reply.text
    # the same text but for the run id: each thread's count has its own record
    assert reply.text == twin.text.replace(first_twin.run_ids[0], first.run_ids[0])


def test_e_details_with_no_earlier_answer_calls_the_model(tmp_path, monkeypatch):
    env = county_env(tmp_path, monkeypatch)
    reply = env.ask("details", Step(show_details()))
    assert reply.model_called is True and len(env.model.calls) == 1
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", "NO_PREVIOUS_ANSWER")


def test_e_details_the_model_decides(tmp_path, monkeypatch):
    """C36-7: the model's own choice stands; Python does not answer in its place."""
    env = county_env(tmp_path, monkeypatch)
    answered_first(env)
    reply = env.ask("more", Step(decline("UNRECOGNIZED_QUESTION")))
    assert len(env.model.calls) == 1
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", "UNRECOGNIZED_QUESTION"), \
        (reply.status, reply.reason_code, reply.text)


HELP_EVENTS = {
    "a mention": (lambda text: mention(f"<@{AGENT_USER}> {text}"), THREAD_1, CHANNEL, ROOT_TS),
    "a direct message": (lambda text: direct_message(text), DM_KEY, DM_CHANNEL, None),
}


@pytest.mark.parametrize("text", ["help", "Help", "HELP"])
@pytest.mark.parametrize("where", list(HELP_EVENTS))
def test_e_help_in_slack_goes_to_the_agent_in_county_mode(tmp_path, monkeypatch, where, text):
    env = CountyEnv(tmp_path, monkeypatch, **SLACK)
    make_event, key, channel, thread_ts = HELP_EVENTS[where]
    reply = make_reply("EXPLAINED", text="The agent's own reply to help (SYNTHETIC test data).")
    slack, agent = FakeSlack(), FakeAgent(reply)
    label = process(make_event(text), settings=env.settings, store=env.store, agent=agent,
                    slack=slack)
    assert agent.calls == [(text, key, USER)], agent.calls
    assert label == "explained"
    assert slack.log == [("post", channel, thread_ts, reply.text)]


def test_e_help_in_slack_calls_the_model_in_county_mode(tmp_path, monkeypatch):
    """With the real agent: `help` is a message like any other; the model answers it (here
    with describe_data and about_data)."""
    env = CountyEnv(tmp_path, monkeypatch, **SLACK)
    env.model = FakeModel(Step(describe()), Step(finish("about_data", "Here is what I know. "
                                                        "{f1}.")), clock=env.clock)
    replies = []

    def agent(question, thread_key, user_id, memory_minutes=None):
        replies.append(env.ask(question, model=env.model, thread_key=thread_key,
                               user_id=user_id, memory_minutes=memory_minutes))
        return replies[-1]
    slack = FakeSlack()
    label = process(mention(f"<@{AGENT_USER}> help"), settings=env.settings, store=env.store,
                    agent=agent, slack=slack)
    assert len(replies) == 1 and replies[0].model_called is True
    assert len(env.model.calls) == 2
    assert env.model.calls[0]["messages"][-1]["content"] == f"{p1.LATEST_HEADER}\nhelp"
    assert (label, replies[0].status) == ("explained", "EXPLAINED"), replies[0].text
    assert slack.log == [("post", CHANNEL, ROOT_TS, replies[0].text)]


def test_point_6_reset_in_county_mode_is_as_today(tmp_path, monkeypatch):
    """Changed by briefs/S3-R29-A-tests.md: C65 point 4 gives `reset` in county mode a reply of its
    own (s3support.C65_RESET_LINE; it was p1support's RESET_LINE, today's). Still a control: no
    model or agent call, and the thread's remembered turns are gone (recent_turns is empty)."""
    env = CountyEnv(tmp_path, monkeypatch, **SLACK)
    answered_first(env)
    slack, agent = FakeSlack(), FakeAgent(make_reply("ANSWERED"))
    label = process(mention(f"<@{AGENT_USER}> reset"), settings=env.settings, store=env.store,
                    agent=agent, slack=slack)
    assert (label, agent.calls) == ("reset", [])
    assert slack.log == [("post", CHANNEL, ROOT_TS, C65_RESET_LINE)]
    assert env.store.recent_turns(THREAD_1, 10) == []


# ---- (f) SYNTHETIC mode: as today --------------------------------------------------------------

@pytest.mark.parametrize("case", list(G))
def test_f_synthetic_rule_1_still_ends_the_turn_before_the_model(tmp_path, case):
    env = p1.Env(tmp_path)
    reply = env.ask(rule_1(G[case]), Step(p1.count(2025, "all")),
                    Step(finish("finding", p1.ONE_COUNT_TEXT)))
    assert env.model.calls == [] and reply.model_called is False
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", "UNRECOGNIZED_QUESTION")
    p1.assert_fixed(reply.text, "UNRECOGNIZED_QUESTION")


@pytest.mark.parametrize("case", ["convict* (the live run)", "capitalised: Jail", "probation"])
def test_f_synthetic_c29_goes_to_the_model_with_no_tool_answer_of_c36(tmp_path, case):
    env = p1.Env(tmp_path)
    reply = env.ask(C29_ENDS[case], Step(p1.count(2025, "all")),
                    Step(decline("UNSUPPORTED_METRIC")))
    assert reply.model_called is True and len(env.model.calls) == 2
    first = env.model.answer(0)
    assert first.get("error") not in ("NOT_RECORDED", "AGES_NOT_STATED"), first


@pytest.mark.parametrize("word", ["details", "more", "Detail."])
def test_f_synthetic_details_word_is_answered_by_python(tmp_path, word):
    env = p1.Env(tmp_path)
    earlier = env.answered(SUPPORTED["S1"][0], (2025, "18_25"))
    reply = env.ask(word)
    assert env.model.calls == [] and reply.model_called is False
    assert reply.status == "DETAILS", (reply.status, reply.reason_code, reply.text)
    assert reply.text.startswith(p1.DETAILS_HEAD)
    assert earlier.run_ids[0] in reply.text


def test_f_synthetic_help_is_the_fixed_line(tmp_path):
    env = p1.Env(tmp_path, slack=True)
    slack, agent = FakeSlack(), FakeAgent(make_reply("ANSWERED"))
    label = process(mention(f"<@{AGENT_USER}> help"), settings=env.settings, store=env.store,
                    agent=agent, slack=slack)
    assert (label, agent.calls) == ("help", [])
    assert slack.log == [("post", CHANNEL, ROOT_TS, HELP_LINE)]
