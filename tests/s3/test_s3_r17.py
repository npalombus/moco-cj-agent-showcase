"""Stage 3 Part A, round 17 (brief S3-R17-A): answer 1 after C50 of docs/S3A-DESIGN.md for a
later ANALYZE ("After CHAT-BUILDS-check-6b": answer 1 holds for any later refused request, an
`analyze` as much as a count; C48 points 1 and 2 name both). Check 6b's B55 (a build that ends
with the first answer's row when the later refused request is an analyze) passed every test.
Tests only; the program does not change, so every test here passes on today's program. All data
is SYNTHETIC fixtures; no real figure is quoted.

Every turn runs through agent.handle_question with the model stand-in (tests/p1/p1support.py's
FakeModel) on the SYNTHETIC fixtures of tests/s3, county mode, talk on and talk off. No analyze
here reaches R: each is refused (or answered NOT_RECORDED) before R, and stats.run_r is replaced
by one that fails if called (test_s3_c36.no_r).

READINGS (also in kit-log/raw/S3-R17-A-notes.txt):
- R17-1. As round 15's R15-1: "the row of the last refused request" is the end of a twin turn
  (another thread of the same agent) whose message has no word of C29's list and no C30
  question, with the same later request and the same end: the same status, reason code and text,
  word for word, in the reply and in turn.json (`status`, `reason_code`, `reply`).
- R17-2. "An analyze refused for another reason": an unknown kind (BAD_OPTIONS, the S1 kind
  check) and, with a fixed line of its own (S3S S10 answer 10), a trend over one year of the
  fixture (TOO_LITTLE, rule `months`). The twin's TOO_LITTLE reply holds the refusal's own line.
- R17-3. "By the step limit" (MOCO_MAX_STEPS 2, agent.py's no-step-left path): as round 15's
  R15-3, the turn ends as the twin turn ends. On today's program that end is the step limit's
  own (ERROR, MODEL_BAD_OUTPUT's row, failures empty) for the twin and the turn
  alike, not the analyze refusal's code: see briefs/QUESTIONS.md (S3-R17-A). The tests pin "as
  the twin" and that it is not the first answer's row; the tool answers are read from turn.json's
  steps, since no later step shows the model the last one.
- R17-4. "The first call an analyze": the turn's first call is a trend that gets NOT_RECORDED
  (C48 point 1); the later refused request is a count with a field no source has (BAD_FIELD,
  round 15's LATER).
"""
import pytest

from p1support import Step, call
from s3support import A_ID, turn_json, years
from test_s3_c36 import no_r
from test_s3_c41 import env_of
from test_s3_c48 import CASES, the_answer, the_row
from test_s3_r15 import FIELD, LATER as LATER_COUNT, twin_ends
from test_s3_round5 import Y25
from test_s3_round5b import FINISH, nothing_counted

TALK = ["on", "off"]


def analyze(kind, period):
    return call("analyze", {"kind": kind, "source": A_ID, "period": period})


LATER = {  # R17-2: id: (an analyze refused for its own reason, its code, a fixed line of its own)
    "an unknown kind": (analyze("wobble", years(2024, 2025)), "BAD_OPTIONS", False),
    "a trend over one year": (analyze("trend", Y25), "TOO_LITTLE", True),
}
OPENING = analyze("trend", years(2024, 2025))  # R17-4: answered NOT_RECORDED, never run


def premise_twin(twin, twin_answer, code, own_line, word):
    assert twin_answer.get("error") == code, twin_answer
    assert twin.reason_code == code, (twin.status, twin.reason_code, twin.text)
    assert twin.text != the_row(word)[2], "premise: the two rows differ"
    if own_line:
        assert twin_answer["why"] in twin.text, "premise: the refusal's own line"


def answers_of(env, reply):
    """Every tool answer of the turn, from turn.json's steps (the model sees no answer of the
    last step when no step is left)."""
    return [c["answer"] for s in turn_json(reply, env.runs_dir)["steps"] for c in s["tool_calls"]]


def assert_as_the_twin(env, reply, twin):
    assert (reply.status, reply.reason_code, reply.text) == (twin.status, twin.reason_code,
                                                             twin.text), \
        f"not the later refusal's end.\n--- got ---\n{reply.reason_code}: {reply.text}\n" \
        f"--- the twin ---\n{twin.reason_code}: {twin.text}"
    record = turn_json(reply, env.runs_dir)
    assert (record["status"], record["reason_code"], record["reply"]) == \
        (twin.status, twin.reason_code, twin.text), (record["status"], record["reason_code"])
    nothing_counted(env, reply)


# ==== a later analyze refused, then a finish with nothing made ==================================

@pytest.mark.parametrize("talk", TALK)
@pytest.mark.parametrize("later", list(LATER))
@pytest.mark.parametrize("case", list(CASES))
def test_answer_1_a_later_analyze_refused_then_nothing_made_ends_with_its_row(
        tmp_path, monkeypatch, case, later, talk):
    message, word, request, twin_message, _ = CASES[case]
    bad, code, own_line = LATER[later]
    started = no_r(monkeypatch)
    env = env_of(tmp_path, monkeypatch, 1, MOCO_TALK=talk)
    twin, twin_answer = twin_ends(env, twin_message, Step(bad), FINISH)
    premise_twin(twin, twin_answer, code, own_line, word)
    reply = env.ask(message, Step(request), Step(bad), FINISH)
    assert len(env.model.calls) == 3, (reply.status, reply.reason_code, reply.text)
    assert env.model.answer(0) == the_answer(word), "premise: C29's or C30's answer first"
    assert env.model.answer(1) == twin_answer, "premise: the analyze is refused as always"
    assert started == []
    assert (reply.reason_code, reply.text) != the_row(word)[1:], \
        "the first answer's row, not the later analyze refusal's (answer 1)"
    assert turn_json(reply, env.runs_dir)["reason_code"] == code
    assert_as_the_twin(env, reply, twin)


# ==== the same, ending at the step limit ========================================================

@pytest.mark.parametrize("talk", TALK)
@pytest.mark.parametrize("later", list(LATER))
@pytest.mark.parametrize("case", list(CASES))
def test_answer_1_a_later_analyze_refused_and_no_step_left_ends_as_the_twin(
        tmp_path, monkeypatch, case, later, talk):
    """R17-3: MOCO_MAX_STEPS 2: the answered count, the refused analyze, no step left."""
    message, word, request, twin_message, _ = CASES[case]
    bad, code, _ = LATER[later]
    started = no_r(monkeypatch)
    env = env_of(tmp_path, monkeypatch, 1, MOCO_TALK=talk, MOCO_MAX_STEPS=2)
    twin, twin_answer = twin_ends(env, twin_message, Step(bad), Step(bad), FINISH)
    assert len(env.model.calls) == 2, "premise: the step limit ends the twin"
    assert twin_answer.get("error") == code, twin_answer
    assert answers_of(env, twin) == [twin_answer] * 2
    assert twin.text != the_row(word)[2], "premise: the two rows differ"
    reply = env.ask(message, Step(request), Step(bad), FINISH)
    assert len(env.model.calls) == 2
    assert answers_of(env, reply) == [the_answer(word), twin_answer], \
        "premise: C29's or C30's answer, then the analyze refused as always"
    assert started == []
    assert (reply.reason_code, reply.text) != the_row(word)[1:], "the first answer's row"
    assert_as_the_twin(env, reply, twin)


# ==== the first call an analyze answered, the later refused request a count =====================

@pytest.mark.parametrize("talk", TALK)
@pytest.mark.parametrize("case", list(CASES))
def test_answer_1_an_analyze_answered_then_a_count_refused_ends_with_its_row(
        tmp_path, monkeypatch, case, talk):
    """R17-4."""
    message, word, _, twin_message, _ = CASES[case]
    bad, code = LATER_COUNT[FIELD]
    started = no_r(monkeypatch)
    env = env_of(tmp_path, monkeypatch, 1, MOCO_TALK=talk)
    twin, twin_answer = twin_ends(env, twin_message, Step(bad), FINISH)
    premise_twin(twin, twin_answer, code, False, word)
    reply = env.ask(message, Step(OPENING), Step(bad), FINISH)
    assert len(env.model.calls) == 3, (reply.status, reply.reason_code, reply.text)
    assert env.model.answer(0) == the_answer(word), "premise: the analyze is answered"
    assert env.model.answer(1) == twin_answer
    assert started == [], "R was started for the answered analyze"
    assert (reply.reason_code, reply.text) != the_row(word)[1:], "the first answer's row"
    assert turn_json(reply, env.runs_dir)["reason_code"] == code
    assert_as_the_twin(env, reply, twin)
