"""Stage 3 Part A, round 19 (brief S3-R19-A): the proof gaps of CHAT-BUILDS-check-9 that C55 does
not close (kit-log/raw/CHAT-BUILDS-check-9.txt, step 4, PROOF GAP 1 and 3; its breaks K54-4a,
K54-4b and B80 to B84). Tests only; the program does not change, so every test here passes on
today's program. All data is SYNTHETIC: the fixtures of tests/s3 and rows made for one test in
that test's own copy (ids FIXTURE-R18-... from tests/s3/test_s3_c54.py, FIXTURE-R19-... here); no
real figure is quoted.

C54 point 2, pinned (docs/S3A-DESIGN.md, after C55): "a weekday with no day among them gives no
figure". The two allowed cases C54 point 2 names, and two of this file's own of each kind, through
`counting.one_year_under_18` (False) and through a county turn (both counts answered, the totals
plain counting's):
- a weekday group with no day in the other count (K54-4a gives such a group a figure of no day);
- a weekday the count's own filter leaves out (K54-4b takes the groups from the period's days).

Answer 1 after C50, "for every way a turn can end: the word's answer changes nothing about how
the turn ends, except that it is one more refused request" (after check 9). The check's five
probes, each with C29 messages and a C30 message, talk on and off, each against its twin turn:
- B80: the word's answer, a later AGES_NOT_STATED, then a finish: C32's question, as the twin;
- B81: the same with no step left (MOCO_MAX_STEPS 2): C32's question, as the twin;
- B82: the word's answer, a later refusal, then the model service fails: MODEL_UNAVAILABLE's row;
- B83: the same, then the turn's clock runs out with steps left: MODEL_BAD_OUTPUT's row;
- B84: the same, then a step of plain words and no call: the later refusal's row.

READINGS (also in kit-log/raw/S3-R19-A-notes.txt):
- R19-6. The twin turn as round 15's R15-1 and round 18's R18-5: another thread of the same
  agent, a message with no word of C29's list and no C30 question, the same later steps and the
  same end; the tool answers read from turn.json's steps. For B80 and B81 the twin keeps C32's
  words ("young people"), so its later request is answered AGES_NOT_STATED as the turn's is, and
  the pending request and `missing` are compared too.
- R19-7. B82's "the model service fails" is llm.ModelUnavailable from the stand-in's next call;
  B83's clock is the injected one, 50 seconds a step against MOCO_TURN_SECONDS (90 by default),
  with MOCO_MAX_STEPS (6 by default) not reached; B84's plain words are a step with a text and no
  call (A4 reads it as a finish). The later refusals are round 18's (a count with a field no
  source has, BAD_FIELD; an analyze of an unknown kind, BAD_OPTIONS).
"""
import pytest

from datetime import date

from p1support import THREAD_1, THREAD_2, Step, mod
from s3support import A_ID, CountyEnv, age, count, fixture_rows, truth, weekdays
from test_s3_c36 import no_r
from test_s3_c41 import env_of, stored
from test_s3_c48 import CASES, the_answer, the_row
from test_s3_c54 import (AUG4_8, DAYS, EXTRA, MARCH, MON_FRI, WEEKEND, _on, _r18_rows, _span,
                         dates, one_turn, one_year)
from test_s3_r17 import assert_as_the_twin
from test_s3_r18 import LATER_ANY, answers_of, assert_not_the_first_answers_row
from test_s3_round5 import A, U17, U18, Y25, assert_counted, assert_result, checked, spec
from test_s3_round5b import FINISH, ages_question

TALK = ["on", "off"]

# ==== C54 point 2, pinned ========================================================================


def _r19_rows(*groups):
    """As test_s3_c54._r18_rows, with ids FIXTURE-R19-..."""
    return [{**r, "id": r["id"].replace("FIXTURE-R18-", "FIXTURE-R19-")} for r in
            _r18_rows(*groups)]


ROWS = {
    "4 to 8 August": EXTRA["4 to 8 August"],
    # 10 aged 15 on each of 1 to 7 March 2025, and 2 aged 17 on 1 and 2 March
    "1 to 7 March": _r19_rows(*[_on(d, 10, 15) for d in _span("2025-03-01", "2025-03-07")],
                              _on("2025-03-01", 2, 17), _on("2025-03-02", 2, 17)),
}
AUG4_10 = dates("2025-08-04", "2025-08-10")
AUGUST = {"year": 2025, "months": {"from": 8, "to": 8}}

ALLOWED = {
    # C54 point 2, pinned: its own two cases
    "pinned: by weekday from 4 to 8 August 2025, then under 17 by weekday on 9 and 10 August":
        ([spec(AUG4_8, [U18], ["weekday"]),
          spec(dates("2025-08-09", "2025-08-10"), [U17], ["weekday"])], "4 to 8 August"),
    "pinned: August 2025 on Monday to Friday by weekday, then under 17 on its Saturdays":
        ([spec(AUGUST, [U18, MON_FRI], ["weekday"]),
          spec(AUGUST, [U17, weekdays("Saturday")])], "4 to 8 August"),
    # this file's own: a weekday group with no day in the other count
    "no day in the other: by weekday on 1 and 2 March 2025, then under 17 by weekday 3 to 7 March":
        ([spec(dates("2025-03-01", "2025-03-02"), [U18], ["weekday"]),
          spec(dates("2025-03-03", "2025-03-07"), [U17], ["weekday"])], "1 to 7 March"),
    # 4 to 10 August 2025 on Monday to Wednesday by weekday, then under 17 on Thursday and
    # Friday by weekday: each count's groups of the other's weekdays hold no day
    "no day in the other: 4 to 10 August, Mon-Wed by weekday, then Thu and Fri by weekday":
        ([spec(AUG4_10, [U18, weekdays(*DAYS[:3])], ["weekday"]),
          spec(AUG4_10, [U17, weekdays("Thursday", "Friday")], ["weekday"])], "4 to 8 August"),
    # this file's own: a weekday the count's own filter leaves out
    "left out by the filter: the weekends of March 2025 by weekday, then under 17 its Mondays":
        ([spec(MARCH, [U18, WEEKEND], ["weekday"]),
          spec(MARCH, [U17, weekdays("Monday")])], "1 to 7 March"),
    "left out by the filter: 4 to 10 August, Mon-Wed by weekday, then under 17 on 7 August":
        ([spec(AUG4_10, [U18, weekdays(*DAYS[:3])], ["weekday"]),
          spec(dates("2025-08-07", "2025-08-07"), [U17])], "4 to 8 August"),
}


def rows_of(extra):
    return fixture_rows(A) + ROWS[extra]


@pytest.mark.parametrize("case", list(ALLOWED))
def test_c54_point_2_pinned_allowed(tmp_path, monkeypatch, case):
    specs, extra = ALLOWED[case]
    env = CountyEnv(tmp_path, monkeypatch, rows={A: rows_of(extra)})
    assert not one_year(env, specs), "counting.one_year_under_18 must be False"
    reply, answers = one_turn(env, specs)
    for i, answer in enumerate(answers, 1):
        assert_result(answer, f"r{i}")
    assert_counted(env, reply, len(specs))
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert [r["total"] for r in reply.results if r["kind"] == "count"] == \
        [truth(A, s["period"], s["filters"], s["group_by"], rows=rows_of(extra))["total"]
         for s in specs]
    checked(reply)


def test_c54_point_2_premises():
    """The dates' weekdays by the calendar; the made rows are SYNTHETIC, new ids, and before the
    copy's newest record; no weekday breakdown here is too fine on its rows (more than half of
    its groups with records under 10)."""
    assert [date(2025, 3, d).strftime("%A") for d in (1, 2, 3, 7)] == \
        ["Saturday", "Sunday", "Monday", "Friday"]
    assert [date(2025, 8, d).strftime("%A") for d in (4, 7, 9, 10)] == \
        ["Monday", "Thursday", "Saturday", "Sunday"]
    made = ROWS["1 to 7 March"]
    assert all(r["id"].startswith("FIXTURE-R19-") and r["data_class"] == "SYNTHETIC"
               for r in made)
    assert not {r["id"] for r in made} & {r["id"] for r in fixture_rows(A) + EXTRA[
        "4 to 8 August"]}
    for specs, extra in ALLOWED.values():
        for s in specs:
            if s["group_by"]:
                groups = [n for n in truth(A, s["period"], s["filters"], s["group_by"],
                                           rows=rows_of(extra))["groups"].values() if n]
                assert 2 * sum(1 for n in groups if n < 10) <= len(groups), (s, groups)


# ==== answer 1 after C50: every way a turn can end ===============================================

BAD_COUNT, COUNT_CODE = LATER_ANY["a count refused (a field no source has)"]
YOUNG_AGES = [age(18, 21)]
YOUNG_TWIN = "How many young people were arrested in 2025?"
WITH_AGES = {
    # id: (message, the word as the message has it or None for C30, the request that gets the
    #      word's answer, the twin message (C32's words kept, R19-6), the words C32 quotes)
    "jail, with young people (C29)": ("How many young people went to jail in 2025?", "jail",
                                      count(A_ID, Y25), YOUNG_TWIN, "young people"),
    "probation, with older adults (C29)": (
        "How many older adults were put on probation in 2025?", "probation", count(A_ID, Y25),
        "How many older adults were arrested in 2025?", "older adults"),
    "who was arrested, among young people (C30)": (
        "Who was arrested among young people in 2025?", None, count(A_ID, Y25), YOUNG_TWIN,
        "young people"),
}
LATER_AGES = count(A_ID, Y25, YOUNG_AGES)


def assert_asked_as_the_twin(env, reply, twin, words):
    assert (twin.status, twin.reason_code, twin.text) == \
        ("NEEDS_INPUT", "NEEDS_CLARIFICATION", ages_question(words)), \
        ("premise: the twin asks C32's question", twin.status, twin.text)
    for word in ("jail", None):  # neither C29's row nor C30's
        assert_not_the_first_answers_row(reply, word)
    assert_as_the_twin(env, reply, twin)
    assert stored(env, THREAD_1) == stored(env, THREAD_2), "not C32's pending and missing"


# ---- B80: a later AGES_NOT_STATED, then a finish ------------------------------------------------

@pytest.mark.parametrize("talk", TALK)
@pytest.mark.parametrize("case", list(WITH_AGES))
def test_answer_1_b80_a_later_ages_not_stated_then_a_finish_asks_c32s_question(
        tmp_path, monkeypatch, case, talk):
    message, word, request, twin_message, words = WITH_AGES[case]
    env = env_of(tmp_path, monkeypatch, 1, MOCO_TALK=talk)
    twin = env.ask(twin_message, Step(LATER_AGES), FINISH, thread_key=THREAD_2)
    twin_answers = answers_of(env, twin)
    assert [a.get("error") for a in twin_answers] == ["AGES_NOT_STATED"], twin_answers
    reply = env.ask(message, Step(request), Step(LATER_AGES), FINISH)
    assert len(env.model.calls) == 3, (reply.status, reply.reason_code, reply.text)
    assert answers_of(env, reply) == [the_answer(word)] + twin_answers, \
        "premise: C29's or C30's answer, then AGES_NOT_STATED as always"
    assert_asked_as_the_twin(env, reply, twin, words)


# ---- B81: the same, with no step left ------------------------------------------------------------

@pytest.mark.parametrize("talk", TALK)
@pytest.mark.parametrize("case", list(WITH_AGES))
def test_answer_1_b81_a_later_ages_not_stated_and_no_step_left_asks_c32s_question(
        tmp_path, monkeypatch, case, talk):
    message, word, request, twin_message, words = WITH_AGES[case]
    env = env_of(tmp_path, monkeypatch, 1, MOCO_TALK=talk, MOCO_MAX_STEPS=2)
    twin = env.ask(twin_message, Step(LATER_AGES), Step(LATER_AGES), FINISH,
                   thread_key=THREAD_2)
    assert len(env.model.calls) == 2, "premise: the step limit ends the twin"
    twin_answers = answers_of(env, twin)
    assert [a.get("error") for a in twin_answers] == ["AGES_NOT_STATED"] * 2, twin_answers
    reply = env.ask(message, Step(request), Step(LATER_AGES), FINISH)
    assert len(env.model.calls) == 2
    assert answers_of(env, reply) == [the_answer(word), twin_answers[-1]]
    assert_asked_as_the_twin(env, reply, twin, words)


# ---- B82 to B84: a later refusal, then the service fails, the clock runs out, plain words -------

def model_down():
    return mod("llm").ModelUnavailable("SYNTHETIC: the model service is down for this test")


PLAIN = Step(text="I could not find that in the records.")
ENDS = {
    # id: (the turn's later steps after the refusal, keyword arguments of the ask for the twin and
    #      the turn, the twin's end as (status, reason code) or None for the refusal's own, the
    #      model calls of the twin and of the turn)
    "B82 the model service fails": ([], lambda n: {"error": model_down(), "fail_at": n},
                                    ("ERROR", "MODEL_UNAVAILABLE"), (2, 3)),
    "B83 the clock runs out with steps left": ([], lambda n: {"seconds": 50.0},
                                               ("ERROR", "MODEL_BAD_OUTPUT"), (2, 2)),
    "B84 a step of plain words and no call": ([PLAIN], lambda n: {}, None, (2, 3)),
}


@pytest.mark.parametrize("talk", TALK)
@pytest.mark.parametrize("end", list(ENDS))
@pytest.mark.parametrize("later", list(LATER_ANY))
@pytest.mark.parametrize("case", list(CASES))
def test_answer_1_a_later_refusal_then_the_turn_ends_another_way_ends_as_the_twin(
        tmp_path, monkeypatch, case, later, end, talk):
    message, word, request, twin_message, _ = CASES[case]
    bad, code = LATER_ANY[later]
    after, kw, twin_end, (twin_calls, turn_calls) = ENDS[end]
    started = no_r(monkeypatch)
    env = env_of(tmp_path, monkeypatch, 1, MOCO_TALK=talk)
    assert env.settings.moco_max_steps > 2 and env.settings.moco_turn_seconds == 90, \
        "premise: the limits are their defaults"
    twin_steps = [Step(bad)] + ([Step(bad)] if end.startswith("B83") else []) + after
    twin = env.ask(twin_message, *twin_steps, FINISH, thread_key=THREAD_2, **kw(1))
    assert len(env.model.calls) == twin_calls, "premise: the twin ends that way"
    twin_answers = answers_of(env, twin)
    assert {a.get("error") for a in twin_answers} == {code}, twin_answers
    assert (twin.status, twin.reason_code) == (twin_end or (twin.status, code)), \
        ("premise: the twin's end", twin.status, twin.reason_code, twin.text)
    assert twin.text != the_row(word)[2], "premise: the two rows differ"
    reply = env.ask(message, Step(request), Step(bad), *after, FINISH, **kw(2))
    assert len(env.model.calls) == turn_calls, (reply.status, reply.reason_code, reply.text)
    assert answers_of(env, reply) == [the_answer(word), twin_answers[0]], \
        "premise: C29's or C30's answer, then the later request refused as always"
    assert started == []
    assert_not_the_first_answers_row(reply, word)
    assert_as_the_twin(env, reply, twin)
