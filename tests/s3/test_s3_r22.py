"""Stage 3 round 22 (briefs/S3-R22-A-tests.md): tests for the three PROOF GAPs of
kit-log/raw/CHAT-BUILDS-check-10.txt. Each test passes on today's program; each gap's tests fail
on the break the check names (brief step 4; kit-log/raw/S3-R22-A-notes.txt). The program does not
change. All data is SYNTHETIC: the fixtures of tests/s3 and round 19's made rows
(FIXTURE-R19-...); no real figure is quoted.

- PROOF GAP 1 (C55 point 1 with the answer to S3-R19-A's question; break C55-5): an end at the
  usable limit that the message states is a stated end. The check's D1 ("young people aged 10 to
  98", the model's 10 to 98) and D2 ("aged 10 and over", the model's `from` 10) are counted, for
  `count` and `analyze`, on both sources (coded_like's limits are 12 and 90, so there "aged 12 to
  90" and "aged 12 and over").
- PROOF GAP 2 (C55 for an `analyze` of kind `rate`; break C55-8): the check's R1 and R3 are not
  answered AGES_NOT_STATED; they reach the rate's own checks exactly as the same request after a
  message with no word of C32's list (on the fixture, a BAD_OPTIONS answer: the fixture source is
  not marked for rates). R2 and R4 are asked.
- PROOF GAP 3 (C32 answer 3 with C55; break PIN-2): an end one off in the wrong direction is not
  stated. The check's D3 ("over 65", the model's `from` 64) and D4 ("under 18", `to` 19) are
  asked, and two of this file's own, the other end stated: "aged 18 to 24" with `from` 17 (one
  below the number) and with `to` 25 (one above it).

Every turn runs through agent.handle_question with the model stand-in, county mode, talk on and
talk off. "Counted" and "asked" are as tests/s3/test_s3_c55.py has them (its docstring, R19-1).
"""
import pytest

from p1support import THREAD_2, Step, call, finish
from s3support import A_ID, C_ID, CountyEnv, NAMES, age, count
from test_s3_c36 import no_r
from test_s3_c48 import r_starts
from test_s3_c55 import HIGH, LOW, CODED_HIGH, CODED_LOW, P, TALK, TREND_TEXT, _trend_rows
from test_s3_round5 import Y25, line1, phrase, spec
from test_s3_round5b import FINISH, assert_ages_asked, not_refused

A, C = NAMES
DIST_TEXT = "Here it is. {a1.ages}."


def env_of(tmp_path, monkeypatch, talk, trend_rows=False):
    rows = {A: _trend_rows()} if trend_rows else None
    return CountyEnv(tmp_path, monkeypatch, names=NAMES, rows=rows, MOCO_TALK=talk)


def assert_as_the_twin(env, twin_message, message, request, finish_step):
    """The same request after a message with no word of C32's list (the twin, another thread),
    then the turn: no AGES_NOT_STATED, and the same tool answer, saved specs and reply."""
    twin = env.ask(twin_message, Step(request), finish_step, thread_key=THREAD_2)
    twin_answer = env.model.answer(0)
    reply = env.ask(not_refused(message), Step(request), finish_step)
    answer = env.model.answer(0)
    assert answer.get("error") != "AGES_NOT_STATED", answer
    assert answer == twin_answer, (answer, twin_answer)
    assert len(env.model.calls) == 2
    assert (reply.status, reply.reason_code, reply.text) == \
        (twin.status, twin.reason_code, twin.text), (reply.status, reply.reason_code, reply.text)
    assert [(r["kind"], r["spec"]) for r in reply.results] == \
        [(r["kind"], r["spec"]) for r in twin.results]
    return twin, reply


# ==== PROOF GAP 1: a stated end at the limit is a stated end: counted ===========================

# id: (source, the words between "of" and the period/verb, the model's age filter)
STATED_AT_LIMIT = {
    "D1 arrests_like: aged 10 to 98, the model's 10 to 98":
        (A_ID, "young people aged 10 to 98", age(LOW, HIGH)),
    "D2 arrests_like: aged 10 and over, the model's from 10":
        (A_ID, "young people aged 10 and over", age(LOW)),
    "D1 coded_like: aged 12 to 90, the model's 12 to 90":
        (C_ID, "young people aged 12 to 90", age(CODED_LOW, CODED_HIGH, "age_years")),
    "D2 coded_like: aged 12 and over, the model's from 12":
        (C_ID, "young people aged 12 and over", age(CODED_LOW, None, "age_years")),
}


def gap1_turn(tool, sid, words, flt):
    """(twin message, message, request, finish). `analyze` is a trend over 2024 and 2025 on
    arrests_like (round 19's rows) and a distribution over 2025 on coded_like (its copy starts
    in 2025: too few months for a trend)."""
    unit = "arrests" if sid == A_ID else "intake records"
    if tool == "count":
        return (f"How many {unit} were there in 2025?",
                f"How many {unit} of {words} were there in 2025?", count(sid, Y25, [flt]), FINISH)
    if sid == A_ID:
        return ("Did arrests go up from 2024 to 2025?",
                f"Did arrests of {words} go up from 2024 to 2025?",
                call("analyze", {"kind": "trend", "source": sid, "period": P, "filters": [flt]}),
                Step(finish("finding", TREND_TEXT)))
    return ("How were the ages of the intake records spread in 2025?",
            f"How were the ages of the intake records of {words} spread in 2025?",
            call("analyze", {"kind": "distribution", "source": sid, "period": Y25,
                             "filters": [flt]}),
            Step(finish("finding", DIST_TEXT)))


@pytest.mark.parametrize("talk", TALK)
@pytest.mark.parametrize("tool", ["count", "analyze"])
@pytest.mark.parametrize("case", list(STATED_AT_LIMIT))
def test_gap1_a_stated_end_at_the_limit_is_counted(tmp_path, monkeypatch, case, tool, talk):
    sid, words, flt = STATED_AT_LIMIT[case]
    started = r_starts(monkeypatch)
    env = env_of(tmp_path, monkeypatch, talk, trend_rows=(tool == "analyze" and sid == A_ID))
    twin_message, message, request, finish_step = gap1_turn(tool, sid, words, flt)
    twin, reply = assert_as_the_twin(env, twin_message, message, request, finish_step)
    assert (twin.status, twin.reason_code) == ("ANSWERED", None), \
        ("premise: the twin is answered", twin.status, twin.reason_code, twin.text)
    assert len(reply.results) == 1 and reply.results[0]["spec"]["filters"] == [flt], \
        ("not counted with the model's ages", reply.results)
    if tool == "analyze":
        kind = "trend" if sid == A_ID else "distribution"
        assert started == [kind, kind], ("R was not started for each", started)
    if (tool, sid) == ("count", A_ID) and "to" in flt:
        assert line1(reply) == f"I counted {phrase(spec(Y25, [flt]))}.", reply.text


# ==== PROOF GAP 2: C55 for an `analyze` of kind `rate` ==========================================

RATE_TWIN = "What is the arrest rate per resident in 2025?"


def rate_request(flt):
    return call("analyze", {"kind": "rate", "source": A_ID, "period": Y25, "filters": [flt]})


RATE_NOT_ASKED = {
    "R1 older adults over 65, the model's 66 to 98": (
        "What is the arrest rate per resident of older adults over 65 in 2025?", age(66, HIGH)),
    "R3 young people under 25, the model's 10 to 24": (
        "What is the arrest rate per resident of young people under 25 in 2025?", age(LOW, 24)),
}

RATE_ASKED = {
    "R2 older adults over 65, the model's 66 to 80": (
        "What is the arrest rate per resident of older adults over 65 in 2025?", age(66, 80),
        "older adults"),
    "R4 young people, the model's 10 to 98": (
        "What is the arrest rate per resident of young people in 2025?", age(LOW, HIGH),
        "young people"),
}


@pytest.mark.parametrize("talk", TALK)
@pytest.mark.parametrize("case", list(RATE_NOT_ASKED))
def test_gap2_a_rate_with_an_unstated_end_at_the_limit_is_not_asked(tmp_path, monkeypatch, case,
                                                                    talk):
    message, flt = RATE_NOT_ASKED[case]
    started = no_r(monkeypatch)
    env = env_of(tmp_path, monkeypatch, talk)
    twin, reply = assert_as_the_twin(env, RATE_TWIN, message, rate_request(flt), FINISH)
    assert env.model.answer(0).get("error") == "BAD_OPTIONS", \
        ("premise: the rate's own answer on the fixture", env.model.answer(0))
    assert reply.status != "NEEDS_INPUT", (reply.status, reply.reason_code, reply.text)
    assert started == [], "R was started"


@pytest.mark.parametrize("talk", TALK)
@pytest.mark.parametrize("case", list(RATE_ASKED))
def test_gap2_a_rate_with_an_end_left_unstated_is_asked(tmp_path, monkeypatch, case, talk):
    message, flt, words = RATE_ASKED[case]
    started = no_r(monkeypatch)
    env = env_of(tmp_path, monkeypatch, talk)
    reply = env.ask(not_refused(message), Step(rate_request(flt)), FINISH)
    assert started == [], "R was started"
    assert_ages_asked(env, reply, words)


# ==== PROOF GAP 3: an end one off in the wrong direction is not stated: asked ===================

# id: (the words, the model's age filter, the words C32's question quotes). arrests_like.
ONE_OFF = {
    "D3 older adults over 65, the model's 64 to 98 (`from` one below 65)":
        ("older adults over 65", age(64, HIGH), "older adults"),
    "D4 young people under 18, the model's 10 to 19 (`to` one above 18)":
        ("young people under 18", age(LOW, 19), "young people"),
    "young people aged 18 to 24, the model's 17 to 24 (`from` one below 18)":
        ("young people aged 18 to 24", age(17, 24), "young people"),
    "young people aged 18 to 24, the model's 18 to 25 (`to` one above 24)":
        ("young people aged 18 to 24", age(18, 25), "young people"),
}


@pytest.mark.parametrize("talk", TALK)
@pytest.mark.parametrize("tool", ["count", "analyze"])
@pytest.mark.parametrize("case", list(ONE_OFF))
def test_gap3_an_end_one_off_the_wrong_way_is_asked(tmp_path, monkeypatch, case, tool, talk):
    words, flt, quoted = ONE_OFF[case]
    started = no_r(monkeypatch)
    env = env_of(tmp_path, monkeypatch, talk, trend_rows=(tool == "analyze"))
    _, message, request, finish_step = gap1_turn(tool, A_ID, words, flt)
    reply = env.ask(not_refused(message), Step(request), finish_step)
    assert started == [], "R was started"
    assert_ages_asked(env, reply, quoted)
