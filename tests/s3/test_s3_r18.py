"""Stage 3 Part A, round 18 (brief S3-R18-A): the four broken builds of CHAT-BUILDS-check-8 that
no test caught (M14c; B73, B74, B74b; kit-log/raw/CHAT-BUILDS-check-8.txt, step 4, PROOF GAP 1
and 2). Tests only; the program does not change, so every test here passes on today's program.
All data is SYNTHETIC fixtures; no real figure is quoted.

Every turn runs through agent.handle_question with the model stand-in (tests/p1/p1support.py's
FakeModel) on the SYNTHETIC fixtures of tests/s3, county mode.

C32 answer 3, the other end (docs/S3A-DESIGN.md, after C54): "asked when ANY end is unstated" was
pinned for an unstated `from` only. Here `from` is stated and `to` is not: the check's M14c probe
("older adults over 65", the model's ages 66 to 80) and two messages of this file's own are asked
C32's question, and nothing is counted. The same messages with the model's `from` only are counted
(so the question comes from `to`).

Answer 1 after C50 (C48 point 3: "the row of the last refused request, as A7 does for any turn";
"an analyze as much as a count"), the check's three probes, each with C29 messages and a C30
message, talk on and off:
- B73: the turn's first call an `analyze` that gets the word's answer, then a refused request,
  then no step left (MOCO_MAX_STEPS 2): the turn ends as its twin;
- B74: the word's answer, a refused count, then a refused `analyze`, then a finish: the analyze's
  row;
- B74b: the other order, a refused `analyze` then a refused count, then a finish: the count's row.

READINGS (also in kit-log/raw/S3-R18-A-notes.txt):
- R18-5. As round 15's R15-1 and round 17's R17-1: "the row of the last refused request" is the
  end of a twin turn (another thread of the same agent) whose message has no word of C29's list
  and no C30 question, with the same later requests and the same end. The tests also check the
  code itself (the later refusal's, in turn.json), so a build that changed the twin as well would
  not pass.
- R18-6. As R17-3: at the step limit the turn and its twin end ERROR with MODEL_BAD_OUTPUT's row
  (C50's note as corrected after check 8); the tests pin "as the twin" and "not the first
  answer's row".
- R18-7. The refused `analyze` requests are round 17's two (an unknown kind, BAD_OPTIONS; a trend
  over one year, TOO_LITTLE, with a fixed line of its own); the refused count is round 15's (a
  field no source has, BAD_FIELD). No analyze here reaches R (test_s3_c36.no_r).
"""
import pytest

from p1support import THREAD_2, Step
from s3support import A_ID, age, count, turn_json
from test_s3_c36 import no_r
from test_s3_c41 import env_of
from test_s3_c48 import CASES, the_answer, the_row
from test_s3_r15 import FIELD, LATER as LATER_COUNT
from test_s3_r17 import LATER as LATER_ANALYZE, OPENING, assert_as_the_twin
from test_s3_round5 import Y25, line1, phrase, spec
from test_s3_round5b import FINISH, assert_ages_asked, county_env, not_refused

TALK = ["on", "off"]

# ==== C32 answer 3: `from` stated, `to` not ======================================================

OTHER_END = {
    # id: (message, the ages the model sends, the words as the message has them, its `from` only)
    "older adults over 65, the model's 66 to 80 (the check's M14c probe)":
        ("How many arrests of older adults over 65 were there in 2025?", [age(66, 80)],
         "older adults", [age(66)]),
    "seniors 70 and older, the model's 70 to 90":
        ("How many arrests of seniors 70 and older were there in 2025?", [age(70, 90)],
         "seniors", [age(70)]),
    "teenagers over 12, the model's 13 to 19":
        ("How many teenagers over 12 were arrested in 2025?", [age(13, 19)], "teenagers",
         [age(13)]),
}


@pytest.mark.parametrize("case", list(OTHER_END))
def test_c32_answer_3_from_stated_and_to_not_is_asked(tmp_path, monkeypatch, case):
    """The request is answered AGES_NOT_STATED and the turn asks C32's question word for word;
    nothing is counted; `missing` is `ages`."""
    question, filters, words, _ = OTHER_END[case]
    env = county_env(tmp_path, monkeypatch)
    reply = env.ask(not_refused(question), Step(count(A_ID, Y25, filters)), FINISH)
    assert_ages_asked(env, reply, words)


@pytest.mark.parametrize("case", list(OTHER_END))
def test_c32_answer_3_premise_the_from_alone_is_stated(tmp_path, monkeypatch, case):
    """The same message with the model's `from` only is counted, as today: the question above
    comes from the unstated `to`."""
    question, _, _, from_only = OTHER_END[case]
    env = county_env(tmp_path, monkeypatch)
    reply = env.ask(not_refused(question), Step(count(A_ID, Y25, from_only)), FINISH)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert line1(reply) == f"I counted {phrase(spec(Y25, from_only))}."


# ==== answer 1 after C50 ==========================================================================

BAD_COUNT, COUNT_CODE = LATER_COUNT[FIELD]


def answers_of(env, reply):
    """The answers to the turn's count and analyze calls, from turn.json's steps (as round 17's
    answers_of, without the finish call's own entry)."""
    return [c["answer"] for s in turn_json(reply, env.runs_dir)["steps"] for c in s["tool_calls"]
            if c["name"] in ("count", "analyze")]


def twin_of(env, twin_message, *steps):
    """The twin turn (R18-5): the same later steps after the twin message, in another thread of
    the same agent. Returns (its reply, every tool answer of the turn, from turn.json)."""
    twin = env.ask(twin_message, *steps, thread_key=THREAD_2)
    return twin, answers_of(env, twin)


def assert_not_the_first_answers_row(reply, word):
    assert (reply.reason_code, reply.text) != the_row(word)[1:], \
        "the first answer's row, not the later refusal's (answer 1)"


# ---- B74: a refused count, then a refused analyze, then a finish: the analyze's row --------------

@pytest.mark.parametrize("talk", TALK)
@pytest.mark.parametrize("later", list(LATER_ANALYZE))
@pytest.mark.parametrize("case", list(CASES))
def test_answer_1_b74_a_count_then_an_analyze_refused_ends_with_the_analyzes_row(
        tmp_path, monkeypatch, case, later, talk):
    message, word, request, twin_message, _ = CASES[case]
    bad_analyze, code, own_line = LATER_ANALYZE[later]
    started = no_r(monkeypatch)
    env = env_of(tmp_path, monkeypatch, 1, MOCO_TALK=talk)
    twin, twin_answers = twin_of(env, twin_message, Step(BAD_COUNT), Step(bad_analyze), FINISH)
    assert [a.get("error") for a in twin_answers] == [COUNT_CODE, code], twin_answers
    assert (twin.reason_code, turn_json(twin, env.runs_dir)["reason_code"]) == (code, code), \
        "premise: the twin ends with the last refusal's row (A7)"
    assert twin.text != the_row(word)[2], "premise: the two rows differ"
    if own_line:
        assert twin_answers[-1]["why"] in twin.text, "premise: the refusal's own line"
    reply = env.ask(message, Step(request), Step(BAD_COUNT), Step(bad_analyze), FINISH)
    assert len(env.model.calls) == 4, (reply.status, reply.reason_code, reply.text)
    assert answers_of(env, reply) == [the_answer(word)] + twin_answers, \
        "premise: C29's or C30's answer, then the count and the analyze refused as always"
    assert started == []
    assert_not_the_first_answers_row(reply, word)
    assert turn_json(reply, env.runs_dir)["reason_code"] == code, "the analyze's code"
    assert_as_the_twin(env, reply, twin)


# ---- B74b: the other order, a refused analyze then a refused count: the count's row -------------

@pytest.mark.parametrize("talk", TALK)
@pytest.mark.parametrize("later", list(LATER_ANALYZE))
@pytest.mark.parametrize("case", list(CASES))
def test_answer_1_b74b_an_analyze_then_a_count_refused_ends_with_the_counts_row(
        tmp_path, monkeypatch, case, later, talk):
    message, word, request, twin_message, _ = CASES[case]
    bad_analyze, code, own_line = LATER_ANALYZE[later]
    started = no_r(monkeypatch)
    env = env_of(tmp_path, monkeypatch, 1, MOCO_TALK=talk)
    twin, twin_answers = twin_of(env, twin_message, Step(bad_analyze), Step(BAD_COUNT), FINISH)
    assert [a.get("error") for a in twin_answers] == [code, COUNT_CODE], twin_answers
    assert (twin.reason_code, turn_json(twin, env.runs_dir)["reason_code"]) == \
        (COUNT_CODE, COUNT_CODE), "premise: the twin ends with the last refusal's row (A7)"
    assert twin.text != the_row(word)[2], "premise: the two rows differ"
    if own_line:
        assert twin_answers[0]["why"] not in twin.text, "premise: not the analyze's own line"
    reply = env.ask(message, Step(request), Step(bad_analyze), Step(BAD_COUNT), FINISH)
    assert len(env.model.calls) == 4, (reply.status, reply.reason_code, reply.text)
    assert answers_of(env, reply) == [the_answer(word)] + twin_answers
    assert started == []
    assert_not_the_first_answers_row(reply, word)
    assert turn_json(reply, env.runs_dir)["reason_code"] == COUNT_CODE, "the count's code"
    assert_as_the_twin(env, reply, twin)


# ---- B73: the first call an analyze answered, a later refusal, no step left: as the twin --------

LATER_ANY = {  # id: (a request refused for its own reason, its code)
    "a count refused (a field no source has)": (BAD_COUNT, COUNT_CODE),
    "an analyze refused (an unknown kind)": LATER_ANALYZE["an unknown kind"][:2],
}


@pytest.mark.parametrize("talk", TALK)
@pytest.mark.parametrize("later", list(LATER_ANY))
@pytest.mark.parametrize("case", list(CASES))
def test_answer_1_b73_an_analyze_answered_then_a_refusal_and_no_step_left_ends_as_the_twin(
        tmp_path, monkeypatch, case, later, talk):
    """MOCO_MAX_STEPS 2: the first call an analyze (a trend) that gets the word's answer, then a
    refused request, then no step left (R18-6)."""
    message, word, _, twin_message, _ = CASES[case]
    bad, code = LATER_ANY[later]
    started = no_r(monkeypatch)
    env = env_of(tmp_path, monkeypatch, 1, MOCO_TALK=talk, MOCO_MAX_STEPS=2)
    twin, twin_answers = twin_of(env, twin_message, Step(bad), Step(bad), FINISH)
    assert len(env.model.calls) == 2, "premise: the step limit ends the twin"
    assert [a.get("error") for a in twin_answers] == [code, code], twin_answers
    assert twin.text != the_row(word)[2], "premise: the two rows differ"
    reply = env.ask(message, Step(OPENING), Step(bad), FINISH)
    assert len(env.model.calls) == 2
    assert answers_of(env, reply) == [the_answer(word), twin_answers[-1]], \
        "premise: the analyze gets C29's or C30's answer, then the request is refused as always"
    assert started == [], "R was started for the answered analyze"
    assert_not_the_first_answers_row(reply, word)
    assert_as_the_twin(env, reply, twin)
