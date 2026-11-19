"""Stage 3 Part A, round 15 (brief S3-R15-A): the two answers after C50 of docs/S3A-DESIGN.md
("C48 to C50, answers to S3-R13-A's three questions", 16 Nov 23:50 EST), which no test pinned
(CHAT-BUILDS-check-6, PROOF GAP 1; its breaks B23 and B34). Tests only; the program does not
change, so every test here passes on today's program. All data is SYNTHETIC fixtures; no real
figure is quoted.

Every turn runs through agent.handle_question with the model stand-in (tests/p1/p1support.py's
FakeModel) on the SYNTHETIC fixtures of tests/s3, county mode, MOCO_TALK on unless a test says.

Answer 1 (C48 point 3): C29's answer to the first count (NOT_RECORDED), then a count refused for
another reason, then nothing made: the turn ends with the row of the LATER refusal, its code
the reply's and the record's reason code, not the row of NOT_RECORDED's code.
Answer 2 (C50 point 1): a failing own-words try (decline or ask_user), the REWRITE, then a finish
that fails its first try and passes its second: the turn's `failures` hold the own-words try's
codes and none of the finish's first-try codes, which are in `first_failures` (T3).

READINGS (also in kit-log/raw/S3-R15-A-notes.txt):
- R15-1. "The row of the last refused request, as A7 does for any turn": the turn ends exactly as
  a twin turn ends (another thread of the same agent) whose message has no word of C29's list
  and no C30 question, with the same refused request and the same end: the same status, reason
  code and text, word for word. A premise checks that the twin ends with the later refusal's
  code and that its row is not NOT_RECORDED's.
- R15-2. "A field no source has" is a filter on `charge`, which the fixture source does not
  have (C5's BAD_FIELD, as tests/s3/test_s3_c48.py sends it). The other kinds of refusal, each
  its own test: a year the copy does not cover (OUT_OF_COVERAGE), a label the field does not
  have (BAD_VALUE), one year of age under 18 (NOT_ALLOWED), three breakdowns (TOO_MANY).
- R15-3. "Nothing made" is the model's finish with no result (A7's row). The same holds when no
  step is left (MOCO_MAX_STEPS): the turn ends as the twin turn ends (the C29 answer's row only
  when that answer is the last refused request, C36); one test.
- R15-4. "The turn's failures" are the reply's `draft_failures` and the turn record's
  `failures` (and its `draft_failures`, the same list), as tests/s3/test_s3_c50.py reads them;
  `first_failures` is the turn record's field (T3).
"""
import sys
from pathlib import Path

import pytest

from p1support import THREAD_2, Step, finish
from s3support import A_ID, age, count, is_, turn_json, year
from test_s3_c41 import DECLINED, ask_with, decline_with, env_of, failures_of, labels_of
from test_s3_c43 import FAULTS, rewrite_of
from test_s3_c48 import CASES, the_answer, the_row
from test_s3_round5 import Y25, line1, phrase, spec
from test_s3_round5b import FINISH, METRIC_ROW, nothing_counted

TESTS = Path(__file__).resolve().parents[1]
if str(TESTS / "t") not in sys.path:
    sys.path.insert(0, str(TESTS / "t"))

from tsupport import HELLO_TEXT, premise_talk  # noqa: E402

JAIL = "jail (the review's jail_word_count)"
LATER = {  # R15-2: id: (a request refused for its own reason, its code)
    "a field no source has": (count(A_ID, Y25, [is_("charge", "theft")]), "BAD_FIELD"),
    "a year the copy does not cover": (count(A_ID, year(2019)), "OUT_OF_COVERAGE"),
    "a label the field does not have": (count(A_ID, Y25, [is_("district", "district 99")]),
                                        "BAD_VALUE"),
    "one year of age under 18": (count(A_ID, Y25, [age(17, 17)]), "NOT_ALLOWED"),
    "three breakdowns": (count(A_ID, Y25, [], ["district", "gender", "race"]), "TOO_MANY"),
}
FIELD = "a field no source has"


def twin_ends(env, twin_message, *steps):
    """R15-1: the same steps after the twin message, in another thread of the same agent."""
    twin = env.ask(twin_message, *steps, thread_key=THREAD_2)
    return twin, env.model.answer(0)


def assert_ends_as_the_twin(env, reply, twin, code):
    assert (reply.status, reply.reason_code, reply.text) == (twin.status, twin.reason_code,
                                                             twin.text), \
        f"not the later refusal's row.\n--- got ---\n{reply.reason_code}: {reply.text}\n" \
        f"--- the row of {code} ---\n{twin.reason_code}: {twin.text}"
    record = turn_json(reply, env.runs_dir)
    assert (record["status"], record["reason_code"]) == (twin.status, code), \
        (record["status"], record["reason_code"])
    nothing_counted(env, reply)


# ==== answer 1: a later refusal, then nothing made: the later refusal's row ======================

@pytest.mark.parametrize("talk", ["on", "off"])
@pytest.mark.parametrize("case", list(CASES))
def test_answer_1_a_field_no_source_has_then_nothing_made_ends_with_its_row(tmp_path, monkeypatch,
                                                                           case, talk):
    message, word, request, twin_message, _ = CASES[case]
    bad, code = LATER[FIELD]
    env = env_of(tmp_path, monkeypatch, 1, MOCO_TALK=talk)
    twin, twin_answer = twin_ends(env, twin_message, Step(bad), FINISH)
    assert twin_answer.get("error") == code, twin_answer
    assert (twin.status, twin.reason_code) == ("UNSUPPORTED", code), "premise: A7's row"
    assert twin.text != the_row(word)[2], "premise: the two rows differ"
    reply = env.ask(message, Step(request), Step(bad), FINISH)
    assert len(env.model.calls) == 3, (reply.status, reply.reason_code, reply.text)
    assert env.model.answer(0) == the_answer(word), "premise: C29's or C30's answer first"
    assert env.model.answer(1) == twin_answer, "premise: the later request is refused as always"
    assert (reply.status, reply.reason_code, reply.text) != the_row(word), \
        "the first answer's row, not the later refusal's (answer 1)"
    assert_ends_as_the_twin(env, reply, twin, code)


@pytest.mark.parametrize("kind", [k for k in LATER if k != FIELD])
def test_answer_1_another_kind_of_refusal_then_nothing_made_ends_with_its_row(tmp_path,
                                                                             monkeypatch, kind):
    message, word, request, twin_message, _ = CASES[JAIL]
    bad, code = LATER[kind]
    env = env_of(tmp_path, monkeypatch, 1)
    twin, twin_answer = twin_ends(env, twin_message, Step(bad), FINISH)
    assert twin_answer.get("error") == code, twin_answer
    assert twin.reason_code == code and twin.text != METRIC_ROW, (twin.reason_code, twin.text)
    reply = env.ask(message, Step(request), Step(bad), FINISH)
    assert env.model.answer(0) == the_answer(word)
    assert env.model.answer(1) == twin_answer
    assert reply.text != METRIC_ROW and reply.reason_code != "UNSUPPORTED_METRIC", reply.text
    assert_ends_as_the_twin(env, reply, twin, code)


def test_answer_1_the_last_of_several_later_refusals_gives_the_row(tmp_path, monkeypatch):
    """Two later refusals of two kinds: the row of the last one (A7)."""
    message, word, request, twin_message, _ = CASES[JAIL]
    (first, _), (last, code) = LATER[FIELD], LATER["a year the copy does not cover"]
    env = env_of(tmp_path, monkeypatch, 1)
    twin, _ = twin_ends(env, twin_message, Step(first), Step(last), FINISH)
    assert twin.reason_code == code, (twin.reason_code, twin.text)
    reply = env.ask(message, Step(request), Step(first), Step(last), FINISH)
    assert env.model.answer(0) == the_answer(word)
    assert_ends_as_the_twin(env, reply, twin, code)


def test_answer_1_with_no_step_left_the_turn_ends_as_the_twin(tmp_path, monkeypatch):
    """R15-3: C29's answer, a later refusal, and no step left (MOCO_MAX_STEPS 2): as the twin
    turn with the same refusal last (A7), not the C29 answer's row."""
    message, word, request, twin_message, _ = CASES[JAIL]
    bad, code = LATER[FIELD]
    env = env_of(tmp_path, monkeypatch, 1, MOCO_MAX_STEPS=2)
    twin, _ = twin_ends(env, twin_message, Step(bad), Step(bad), FINISH)
    assert len(env.model.calls) == 2, "premise: the step limit ends the twin"
    assert twin.text != METRIC_ROW, twin.text
    reply = env.ask(message, Step(request), Step(bad), FINISH)
    assert len(env.model.calls) == 2
    assert env.model.answer(0) == the_answer(word)
    assert (reply.status, reply.reason_code, reply.text) == (twin.status, twin.reason_code,
                                                             twin.text), reply.text
    assert turn_json(reply, env.runs_dir)["reason_code"] == twin.reason_code
    nothing_counted(env, reply)


def test_answer_1_premise_when_the_answer_is_the_only_refusal_its_row_stands(tmp_path, monkeypatch):
    """C48 point 3 as tests/s3/test_s3_c48.py has it, talk on: with no later refusal, the C29
    answer's row (so the tests above tell the two apart)."""
    message, word, request, _, _ = CASES[JAIL]
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(message, Step(request), FINISH)
    assert (reply.status, reply.reason_code, reply.text) == the_row(word)
    assert turn_json(reply, env.runs_dir)["reason_code"] == "UNSUPPORTED_METRIC"


# ==== answer 2: T3's first-try codes stay in first_failures ======================================

OWN = "NUMBER"            # the own-words try's code (FAULTS["NUMBER"])
TALK_FIRST = "CLAIM"      # a talk finish's first try (FAULTS["CLAIM"]): differs from OWN
FINDING_FIRST = "JUDGE"   # a finding's first try (T2's example): differs from OWN
JUDGED = "I counted {r1.count}. That is a lot."
COUNTED = "I counted {r1.count}."


def test_premise_the_texts_fail_with_the_codes_named():
    labels = labels_of(1)
    premise_talk(FAULTS[OWN][0], OWN, labels)
    premise_talk(FAULTS[TALK_FIRST][0], TALK_FIRST, labels)
    premise_talk(HELLO_TEXT, None, labels)
    assert len({OWN, TALK_FIRST, FINDING_FIRST}) == 3


def own_try(tool):
    text = FAULTS[OWN][0]
    return decline_with("UNSUPPORTED_METRIC", text) if tool == "decline" else \
        ask_with("other", text)


def assert_failures_and_first_failures(env, reply, first):
    assert failures_of(env, reply) == ([OWN], [OWN]), \
        "the turn's failures are the own-words try's codes, without the finish's first try's"
    record = turn_json(reply, env.runs_dir)
    assert record["draft_failures"] == [OWN], record["draft_failures"]
    assert record["first_failures"] == [first], record["first_failures"]
    assert first not in reply.draft_failures and first not in record["failures"]


@pytest.mark.parametrize("tool", ["decline", "ask_user"])
def test_answer_2_rewrite_then_a_talk_text_that_passes_on_its_second_try(tmp_path, monkeypatch,
                                                                         tool):
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(DECLINED["UNSUPPORTED_METRIC"], Step(own_try(tool)),
                    Step(finish("talk", FAULTS[TALK_FIRST][0])), Step(finish("talk", HELLO_TEXT)))
    assert rewrite_of(env, 0)["problems"] == [OWN]
    assert rewrite_of(env, 1)["problems"] == [TALK_FIRST], "premise: T3's first try failed"
    assert len(env.model.calls) == 3
    assert (reply.status, reply.reply_kind, reply.reply_style, reply.text) == \
        ("TALKED", "talk", "agent", HELLO_TEXT), (reply.status, reply.reply_style, reply.text)
    assert_failures_and_first_failures(env, reply, TALK_FIRST)


@pytest.mark.parametrize("tool", ["decline", "ask_user"])
def test_answer_2_rewrite_then_a_count_and_a_finding_that_passes_on_its_second_try(
        tmp_path, monkeypatch, tool):
    env = env_of(tmp_path, monkeypatch, 1)
    reply = env.ask(DECLINED["UNSUPPORTED_METRIC"], Step(own_try(tool)), Step(count(A_ID, Y25)),
                    Step(finish("finding", JUDGED)), Step(finish("finding", COUNTED)))
    assert rewrite_of(env, 0)["problems"] == [OWN]
    assert rewrite_of(env, 2)["problems"] == [FINDING_FIRST], "premise: T3's first try failed"
    assert len(env.model.calls) == 4
    assert (reply.status, reply.reason_code, reply.reply_style) == ("ANSWERED", None, "agent"), \
        (reply.status, reply.reason_code, reply.reply_style, reply.text)
    assert line1(reply) == f"I counted {phrase(spec(Y25))}.", reply.text
    assert_failures_and_first_failures(env, reply, FINDING_FIRST)
