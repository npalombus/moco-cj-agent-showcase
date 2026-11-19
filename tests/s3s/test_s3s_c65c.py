"""C65 point 8 of docs/S3A-DESIGN.md (D-082), the distributions that R runs for: the age chart's bars
are figures. Brief: briefs/S3-R31-A-tests.md (step 3). The tests that need no R (the function, a
distribution refused before R runs, a remembered one, one kept through `reset`, point 9) are in
tests/s3/test_s3_c65c.py, with the readings R31-1 to R31-8. Tests only; red until point 8 is built,
except those that pin what stays (named in their docstrings).

Everything is SYNTHETIC: the Part S fixture stats_like with test_s3s_c65.py's YOUTH_ROWS (two records
in three aged 10 to 16, made up for these tests). R really runs (marker needs_r), as in tests/s3s.
"""
import pytest

from p1support import Step, finish
from s3support import age
from test_s3_c61d import assert_refused
from test_s3_c65 import WHY, nothing_run, spy_runs
from test_s3s_c65 import (TALK, WHOLE, Y25, analyze, answered_count, answered_statistic, ask,
                          count_call, refused_turn, stats_env)
from test_s3_round5 import U18

A10_16 = age(10, 16)
F = {"field": "gender", "is": "female"}


@pytest.mark.needs_r
@pytest.mark.parametrize("filters", [[], [U18], [age(16, 17)]],
                         ids=["every age", "under 18", "ages 16 to 17"])
def test_p8_a_distribution_on_its_own_is_given(tmp_path, monkeypatch, filters):
    """Point 8's test: a distribution of every age, of under 18, of ages 16 to 17, on its own and
    over the whole copy: answered, R run. Passes today; must still pass."""
    env = stats_env(tmp_path, monkeypatch)
    answered_statistic(env, ask(env, "how old are the people arrested?",
                                analyze("distribution", WHOLE, filters)))


@pytest.mark.needs_r
def test_p8_a_distribution_of_10_to_16_is_refused_before_r_runs(tmp_path, monkeypatch):
    """Point 8's test: a distribution of ages 10 to 16 on its own: NOT_ALLOWED with C21's `why` alone,
    nothing computed (no job folder; prepare, run_r, write_job not called)."""
    env = stats_env(tmp_path, monkeypatch)
    calls = spy_runs(monkeypatch)
    reply = ask(env, "how old are the people arrested aged 10 to 16?",
                analyze("distribution", WHOLE, [A10_16]))
    refused_turn(env, reply, why=WHY)
    nothing_run(env, calls)


@pytest.mark.needs_r
@pytest.mark.parametrize("talk", TALK)
def test_p8_the_ages_of_everyone_then_counts(tmp_path, monkeypatch, talk):
    """Point 8's tests, with R: "how old are the people arrested?" (the distribution of every age over
    the whole copy, answered); then ages 10 to 16 in 2025: refused with C62 point 2's sentence;
    under 18 instead: answered; then ages 17 to 18: answered; and 19 and over after them: refused
    with the sentence. Talk off and on."""
    env = stats_env(tmp_path, monkeypatch, MOCO_TALK=talk)
    answered_statistic(env, ask(env, "how old are the people arrested?",
                                analyze("distribution", WHOLE)))
    for question, filters, refused in [("and aged 10 to 16 in 2025?", [A10_16], True),
                                       ("and under 18 in 2025?", [U18], False),
                                       ("and aged 17 to 18 in 2025?", [age(17, 18)], False),
                                       ("and 19 and over in 2025?", [age(19)], True)]:
        reply = ask(env, question, count_call(Y25, filters), text="I counted {r1.count}.")
        if refused:
            refused_turn(env, reply)
        else:
            answered_count(env, reply)


@pytest.mark.needs_r
def test_p8_every_age_by_gender_then_female_10_to_16(tmp_path, monkeypatch):
    """Own (R31-2): the distribution of every age by gender (answered, R run), then female aged 10 to
    16 in 2025: refused with the sentence (the female bars of 10 to 17, less it, are the female
    17-year-olds)."""
    env = stats_env(tmp_path, monkeypatch)
    answered_statistic(env, ask(env, "how old are the men and women arrested?",
                                analyze("distribution", WHOLE, [], {"by": "gender"})))
    reply = ask(env, "and females aged 10 to 16 in 2025?", count_call(Y25, [A10_16, F]),
                text="I counted {r1.count}.")
    refused_turn(env, reply)


@pytest.mark.needs_r
def test_p8_a_distribution_and_a_count_in_one_message(tmp_path, monkeypatch):
    """Point 8 with point 2b, "a distribution of this message": the distribution of every age and
    then 10 to 16 in 2025 in one message: the distribution answered, the count refused with C21's
    `why` alone (the cause is this message's figures); the turn ANSWERED."""
    env = stats_env(tmp_path, monkeypatch)
    reply = env.ask("how old are they, and how many aged 10 to 16 in 2025?",
                    *ask_steps(analyze("distribution", WHOLE), count_call(Y25, [A10_16])))
    assert str(env.model.answer(0).get("result_id")).startswith("a"), env.model.answer(0)
    assert_refused(env.model.answer(1), why=WHY)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)


def ask_steps(*calls):
    return [Step(c) for c in calls] + [Step(finish("finding", "I found that."))]
