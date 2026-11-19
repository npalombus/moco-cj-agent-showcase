"""C61 Part D of docs/S3A-DESIGN.md (D-076): C21 over the thread. Points 10 and 11, with "C61, four
corrections before its tests" (point 4 there: the remembered turns that count are those that ended
ANSWERED). Brief: briefs/S3-R23-A-tests.md. Tests only; red until the planning chat builds C61,
except those that pin what stays (named in their docstrings and in kit-log/raw/S3-R23-A-notes.txt).

Every count here is of the SYNTHETIC fixtures (tests/s3/fixtures/, and test_s3_c54.py's
juvenile-like copy of arrests_like made in tmp_path). The turns go through agent.handle_question
with the model stand-in (CountyEnv), each turn of a thread one message.

Readings (also in the notes):
- R23-D1. "Asked of this turn's counts of the source together with the counts of the same source in
  the thread's remembered turns, as if all were made in this turn": the refusal is C21's own (code
  NOT_ALLOWED, field the age field, nothing counted or saved, no count used up), and its `why` is
  C21's `why` with point 10's sentence after it when the earlier turns are what makes the answer
  yes, and C21's `why` alone when this turn's own counts already make it yes.
- R23-D2. "The remembered turns" are the turns `_Turn.run` reads (the store's turns of the thread,
  within the memory window when there is one), not the newest MOCO_THREAD_TURNS_IN_CONTEXT turns
  the model is shown.
- R23-D3. A turn whose only count is refused ends as C21 has it today: the NOT_ALLOWED row
  (round 5's NOT_ALLOWED_ROW), status UNSUPPORTED, reason NOT_ALLOWED.
"""
import json
from datetime import timedelta

import pytest

from p1support import LEAVE_OUT, THREAD_1, THREAD_2, Step, ask_user, finish, manifests
from s3support import (C61_EARLIER, C62_REFUSAL, NOW_S3, CountyEnv, age, count, figures,
                       is_, year)
from test_s3_c54 import J, SIDS, call_of, two_sources
from test_s3_round5 import (A, AGE_FIELD, C, IDS, NOT_ALLOWED_ROW, U16, U17, U18, WHY, Y25,
                            counts_text, line1, phrase, spec)

WHY_THREAD = WHY + C61_EARLIER

# The two messages of thread P05 (kit-log/raw/THREADS-2026-11-17.txt), on the fixture.
P05_FIRST = "ok how many people under 18 were arrested in 2025?"
P05_SECOND = "and how many aged 10 to 16 in 2025?"


def turn(env, specs, question, **kw):
    """One message: every count of `specs` in one step, then a finish naming the counts made.
    Returns (reply, Python's answer to each count, in order)."""
    reply = env.ask(question, Step(*[call_of(s) for s in specs]),
                    Step(finish("finding", counts_text(len(specs)))), **kw)
    return reply, [env.model.answer(0, i) for i in range(len(specs))]


def assert_answered(reply, answers):
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    for i, answer in enumerate(answers, 1):
        assert answer.get("result_id") == f"r{i}" and "error" not in answer, (i, answer)


def assert_refused(answer, why=WHY_THREAD, field="age"):
    """C21's refusal, with point 10's `why`: NOT_ALLOWED, the age field, no result, no figure."""
    assert answer.get("error") == "NOT_ALLOWED", answer
    assert answer.get("field") == field, answer
    assert answer.get("why") == why, answer
    assert "result_id" not in answer and "slots" not in answer, answer
    assert figures(json.dumps(answer)) == set(), f"a figure in the tool answer: {answer}"


def assert_refused_turn(env, reply, answer, before, why=WHY_THREAD, field="age"):
    """R23-D3: the turn's one count refused: the NOT_ALLOWED row, nothing counted or saved.
    Changed by briefs/S3-R24-A-tests.md (C62 point 2): when the `why` holds C61 point 10's
    sentence, the row's first sentence is C62's (s3support.C62_REFUSAL) in place of the
    NOT_ALLOWED row's; it was `startswith(NOT_ALLOWED_ROW)` for every `why`."""
    assert_refused(answer, why, field)
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", "NOT_ALLOWED"), \
        (reply.status, reply.reason_code, reply.text)
    first = C62_REFUSAL if why.endswith(C61_EARLIER) else NOT_ALLOWED_ROW
    assert reply.text.startswith(first), reply.text
    assert reply.run_ids == [] and reply.results == [], reply.results
    assert len(manifests(env.runs_dir)) == before, "a record was saved for the refused count"


def p05(env, thread_key=THREAD_1, now=None, memory_minutes=None):
    """P05's two messages: under 18 in 2025, then aged 10 to 16 in 2025."""
    first, answers = turn(env, [spec(Y25, [U18])], P05_FIRST, thread_key=thread_key, now=now,
                          memory_minutes=memory_minutes)
    assert_answered(first, answers)
    later = None if now is None else now + timedelta(hours=2)
    return turn(env, [spec(Y25, [age(10, 16)])], P05_SECOND, thread_key=thread_key, now=later,
                memory_minutes=memory_minutes)


# ==== C61's examples ============================================================================

def test_d_p05_in_one_thread_the_second_is_not_allowed_with_the_sentence(tmp_path, monkeypatch):
    """C61's test: the two messages of thread P05 in one thread: the second NOT_ALLOWED, the `why`
    C21's with the added sentence; nothing counted for it."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply, (answer,) = p05(env)
    assert_refused_turn(env, reply, answer, before=1)


def test_d_p05_in_two_threads_both_are_answered(tmp_path, monkeypatch):
    """C61's test (point 11): the same two in two threads are both answered."""
    env = CountyEnv(tmp_path, monkeypatch)
    first, answers = turn(env, [spec(Y25, [U18])], P05_FIRST, thread_key=THREAD_1)
    assert_answered(first, answers)
    second, answers = turn(env, [spec(Y25, [age(10, 16)])], P05_SECOND, thread_key=THREAD_2)
    assert_answered(second, answers)
    assert line1(second) == f"I counted {phrase(spec(Y25, [age(10, 16)]))}.", second.text


@pytest.mark.parametrize("order", ["arrests first", "intake records first"])
def test_d_two_sources_are_both_answered(tmp_path, monkeypatch, order):
    """C61's test with C54 point 4: under 18 of one source, then aged 10 to 16 (12 to 16 for the
    intake records, whose usable ages start at 12) of the other, in one thread: both answered."""
    env = CountyEnv(tmp_path, monkeypatch, names=(A, C))
    a_u18, c_12_16 = spec(Y25, [U18]), spec(Y25, [age(12, 16, AGE_FIELD[C])], name=C)
    c_u18, a_10_16 = spec(Y25, [age(None, 17, AGE_FIELD[C])], name=C), spec(Y25, [age(10, 16)])
    pair = [a_u18, c_12_16] if order == "arrests first" else [c_u18, a_10_16]
    for s, question in zip(pair, (P05_FIRST, P05_SECOND)):
        reply, answers = turn(env, [s], question)
        assert_answered(reply, answers)
        assert reply.results[0]["spec"]["source"] == IDS[s["name"]]


def test_d_the_earlier_turn_outside_the_remembered_turns_is_answered(tmp_path, monkeypatch):
    """C61's test (point 11, a DM's memory minutes): the first message two hours before the
    second, with a memory of 60 minutes.
    Changed by briefs/S3-R29-A-tests.md: C65 point 5 takes back C61 point 11's limit "a direct
    message's memory minutes" (the check reads the turns before the memory minutes too), so the
    second is now refused with C61's sentence, nothing counted. It was `assert_answered`. The
    name is kept so that C65 point 5's reference to this test still finds it."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply, (answer,) = p05(env, now=NOW_S3, memory_minutes=60)
    assert_refused_turn(env, reply, answer, before=1)


def test_d_the_same_thread_within_the_memory_window_is_refused(tmp_path, monkeypatch):
    """The other side of the test above: 30 minutes apart, the memory of 60 minutes holds the
    first message, so the second is refused."""
    env = CountyEnv(tmp_path, monkeypatch)
    first, answers = turn(env, [spec(Y25, [U18])], P05_FIRST, now=NOW_S3, memory_minutes=60)
    assert_answered(first, answers)
    reply, (answer,) = turn(env, [spec(Y25, [age(10, 16)])], P05_SECOND,
                            now=NOW_S3 + timedelta(minutes=30), memory_minutes=60)
    assert_refused_turn(env, reply, answer, before=1)


THREAD_REFUSED = {
    # C21's own examples, each count in a message of its own.
    "under 17 after under 18": [[spec(Y25, [U18])], [spec(Y25, [U17])]],
    "under 18 after under 17": [[spec(Y25, [U17])], [spec(Y25, [U18])]],
    "11 and over after all ages": [[spec(Y25)], [spec(Y25, [age(11)])]],
    "female aged 10 to 17 after 10 to 16 by gender":
        [[spec(Y25, [age(10, 16)], ["gender"])],
         [spec(Y25, [age(10, 17), is_("gender", "female")])]],
}


@pytest.mark.parametrize("case", list(THREAD_REFUSED))
def test_d_c21s_examples_across_two_messages_of_one_thread(tmp_path, monkeypatch, case):
    """Point 10 with C21's examples: what C21 refuses in one message is refused across two
    messages of one thread, with the sentence."""
    env = CountyEnv(tmp_path, monkeypatch)
    (first,), (second,) = THREAD_REFUSED[case]
    reply, answers = turn(env, [first], "first message")
    assert_answered(reply, answers)
    reply, (answer,) = turn(env, [second], "second message")
    assert_refused_turn(env, reply, answer, before=1)


def test_d_the_refused_count_uses_up_no_count_and_the_turn_goes_on(tmp_path, monkeypatch):
    """Point 10 "as if all were made in this turn", C21 as today: after the refused count the
    same message's next count (aged 10 to 15, two years from under 18) is answered as r1."""
    env = CountyEnv(tmp_path, monkeypatch)
    first, answers = turn(env, [spec(Y25, [U18])], P05_FIRST)
    assert_answered(first, answers)
    reply = env.ask(P05_SECOND, Step(call_of(spec(Y25, [age(10, 16)])),
                                     call_of(spec(Y25, [U16]))),
                    Step(finish("finding", "I counted {r1.count}.")))
    assert_refused(env.model.answer(0, 0))
    assert env.model.answer(0, 1).get("result_id") == "r1", env.model.answer(0, 1)
    assert reply.status == "ANSWERED" and len(reply.run_ids) == 1, (reply.status, reply.text)
    assert line1(reply) == f"I counted {phrase(spec(Y25, [U16]))}.", reply.text


# ==== this session's own tests (C61's words decide them; its examples do not name them) =========

def test_own_d1_a_breakdown_in_one_message_and_a_range_in_the_next(tmp_path, monkeypatch):
    """Own 1 (Part D): 2025 by age band (its band 10 to 17 is a figure), then aged 10 to 16 in
    2025: the band less the range is the 17-year-olds; refused with the sentence."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply, answers = turn(env, [spec(Y25, [], ["age_band"])], "2025 by age band")
    assert_answered(reply, answers)
    reply, (answer,) = turn(env, [spec(Y25, [age(10, 16)])], P05_SECOND)
    assert_refused_turn(env, reply, answer, before=1)


def test_own_d2_two_sources_whose_age_fields_share_a_name_are_not_mixed(tmp_path, monkeypatch):
    """Own 2 (Part D), C54 point 4 over the thread: test_s3_c54.py's juvenile-like source (its age
    field is also `age`, usable 10 to 17). Juvenile records aged 14 to 17, then arrests aged 14 to
    16: answered (one source each; read as one source they would give the 17-year-olds). Then
    juvenile records aged 14 to 16: refused with the sentence (the juvenile count of the first
    message); the arrests count between them changes nothing."""
    env = two_sources(tmp_path, monkeypatch)
    for s, question in ((spec(Y25, [age(14, 17)], name=J), "juvenile records aged 14 to 17"),
                        (spec(Y25, [age(14, 16)]), "arrests aged 14 to 16")):
        reply, answers = turn(env, [s], question)
        assert_answered(reply, answers)
        assert reply.results[0]["spec"]["source"] == SIDS[s["name"]]
    reply, (answer,) = turn(env, [spec(Y25, [age(14, 16)], name=J)], "juvenile aged 14 to 16")
    assert_refused_turn(env, reply, answer, before=2)


def test_own_d3_a_count_kept_from_a_question_back(tmp_path, monkeypatch):
    """Own 3 (Part D): "how many aged 10 to 16?" with no period: Python asks (NEEDS_INPUT) and
    keeps the filter; "2025" makes that count (C9's pending request); then under 18 in 2025 is
    refused with the sentence: the count kept from the question back is a count of the thread."""
    env = CountyEnv(tmp_path, monkeypatch)
    asked = env.ask("how many aged 10 to 16?", Step(count(IDS[A], LEAVE_OUT, [age(10, 16)])),
                    Step(finish("finding", "I counted {r1.count}.")))
    assert asked.status == "NEEDS_INPUT", (asked.status, asked.reason_code, asked.text)
    kept = env.ask("2025", Step(count(IDS[A], year(2025))),
                   Step(finish("finding", "I counted {r1.count}.")))
    assert kept.status == "ANSWERED", (kept.status, kept.reason_code, kept.text)
    assert kept.results[0]["spec"]["filters"] == [age(10, 16)], kept.results[0]["spec"]
    reply, (answer,) = turn(env, [spec(Y25, [U18])], P05_FIRST)
    assert_refused_turn(env, reply, answer, before=1)


def test_own_d4_a_period_kept_by_c9_from_the_message_before(tmp_path, monkeypatch):
    """Own 4 (Part D): under 18 in 2025, then "and aged 10 to 16?" with the period left out (C9
    keeps 2025): refused with the sentence."""
    env = CountyEnv(tmp_path, monkeypatch)
    first, answers = turn(env, [spec(Y25, [U18])], P05_FIRST)
    assert_answered(first, answers)
    reply = env.ask("and aged 10 to 16?", Step(count(IDS[A], LEAVE_OUT, [age(10, 16)])),
                    Step(finish("finding", "I counted {r1.count}.")))
    assert_refused_turn(env, reply, env.model.answer(0, 0), before=1)


def test_own_d5_only_turns_that_ended_answered_count(tmp_path, monkeypatch):
    """Own 5 (Part D), correction 4: a message whose count of under 18 was made but whose turn
    ended asking the person (NEEDS_INPUT: its figure was never sent) does not count; aged 10 to
    16 next is answered."""
    env = CountyEnv(tmp_path, monkeypatch)
    asked = env.ask(P05_FIRST, Step(call_of(spec(Y25, [U18]))), Step(ask_user("other")))
    assert asked.status == "NEEDS_INPUT", (asked.status, asked.reason_code, asked.text)
    assert "31" not in asked.text, "premise: the count's figure was not sent"
    reply, answers = turn(env, [spec(Y25, [age(10, 16)])], P05_SECOND)
    assert_answered(reply, answers)


def test_own_d6_the_store_not_the_block_the_model_is_shown(tmp_path, monkeypatch):
    """Own 6 (Part D), R23-D2: with MOCO_THREAD_TURNS_IN_CONTEXT=1 the model is shown the message
    before only; under 18 in 2025 two messages back still counts: aged 10 to 16 is refused."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_THREAD_TURNS_IN_CONTEXT="1")
    for specs, question in (([spec(Y25, [U18])], P05_FIRST),
                            ([spec(year(2024))], "and all of 2024?")):
        reply, answers = turn(env, specs, question)
        assert_answered(reply, answers)
    reply, (answer,) = turn(env, [spec(Y25, [age(10, 16)])], P05_SECOND)
    assert_refused_turn(env, reply, answer, before=2)


def test_own_d7_a_refused_count_of_an_earlier_message_is_no_count(tmp_path, monkeypatch):
    """Own 7 (Part D): under 18; then under 17, refused; then under 16 (ages 10 to 15) is
    answered: 16 and 17 are two years, and the refused count was never made."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply, answers = turn(env, [spec(Y25, [U18])], P05_FIRST)
    assert_answered(reply, answers)
    reply, (answer,) = turn(env, [spec(Y25, [U17])], "and under 17?")
    assert_refused_turn(env, reply, answer, before=1)
    reply, answers = turn(env, [spec(Y25, [U16])], "and under 16?")
    assert_answered(reply, answers)


def test_own_d8_three_messages_c21s_three_count_example(tmp_path, monkeypatch):
    """Own 8 (Part D): C21's "14 to 15 after 10 to 16 and 10 to 13 (the 16-year-olds, from three
    counts)", one count a message: the third message is refused with the sentence."""
    env = CountyEnv(tmp_path, monkeypatch)
    for s in (spec(Y25, [age(10, 16)]), spec(Y25, [age(10, 13)])):
        reply, answers = turn(env, [s], "a message")
        assert_answered(reply, answers)
    reply, (answer,) = turn(env, [spec(Y25, [age(14, 15)])], "and 14 to 15?")
    assert_refused_turn(env, reply, answer, before=2)


def test_own_d9_this_messages_own_counts_keep_c21s_why(tmp_path, monkeypatch):
    """Own 9 (Part D), R23-D1: the sentence only "when the earlier turns' counts are what makes
    the answer yes". After an earlier message about 2024, under 18 and then under 17 in 2025 in one
    message: the second is refused with C21's `why` alone."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply, answers = turn(env, [spec(year(2024))], "all of 2024")
    assert_answered(reply, answers)
    reply = env.ask(P05_FIRST, Step(call_of(spec(Y25, [U18])), call_of(spec(Y25, [U17]))),
                    Step(finish("finding", "I counted {r1.count}.")))
    assert env.model.answer(0, 0).get("result_id") == "r1"
    assert_refused(env.model.answer(0, 1), why=WHY)
    assert reply.status == "ANSWERED", (reply.status, reply.text)


def test_own_d10_the_same_question_again_is_answered(tmp_path, monkeypatch):
    """Own 10 (Part D): under 18 in 2025 asked twice in one thread: the same figure gives no
    single year, so the second is answered (C21's "an identical count", over the thread). Also
    passes on today's program, and must still pass after C61."""
    env = CountyEnv(tmp_path, monkeypatch)
    for question in (P05_FIRST, "say that again: under 18 in 2025?"):
        reply, answers = turn(env, [spec(Y25, [U18])], question)
        assert_answered(reply, answers)
