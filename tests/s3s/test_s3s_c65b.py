"""C65 point 7 of docs/S3A-DESIGN.md (D-082), the rates that R runs for: a rate's age bands are the
Census's (check 14's DEFECT 1). Brief: briefs/S3-R30-A-tests.md (step 5). The tests that need no R
(the function, a remembered rate, one kept through `reset`) are in tests/s3/test_s3_c65b.py, with
the readings R30-1 to R30-6. Tests only; red until point 7 is built, except those that pin what
stays (named in their docstrings).

Everything is SYNTHETIC: Part S2's rates_like with its made-up Census copies (tests/s3s2), whose own
age bands end with 55 to 98, as police_arrests' do. R really runs (marker needs_r), as in tests/s3s.
"""
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parents[1]
if str(TESTS / "s3s2") not in sys.path:
    sys.path.insert(0, str(TESTS / "s3s2"))

from p1support import (AGENT_USER, FAKE_SECRETS, ROOT_TS, TEAM, USER, USER2, FakeModel,  # noqa: E402
                       FakeSlack, Step, finish, mention, process)
from s3support import NOW_S3, age, year  # noqa: E402
from test_s3_c65b import CENSUS, spy_bands  # noqa: E402
from test_s3s_c65 import (TALK, answered_count, answered_statistic, ask, rate,  # noqa: E402
                          rate_env, rates_count, refused_turn)
from test_s3_c65 import nothing_run, spy_runs  # noqa: E402

Y25 = year(2025)
RATE_BY_BAND = {"by": "age_band", "reference": None}


def count_turn(env, ages, period=Y25):
    return ask(env, "how many arrests in 2025?", rates_count(period, [ages]),
               text="I counted {r1.count}.")


@pytest.mark.needs_r
@pytest.mark.parametrize("talk", TALK)
def test_defect_1_a_rate_by_age_band_then_17_to_64_is_refused(tmp_path, monkeypatch, talk):
    """Check 14's DEFECT 1 as it ran it: "the arrest rate by age band in 2025?" (answered, R run),
    then "how many arrests aged 17 to 64 in 2025?": refused, NOT_ALLOWED with C21's `why` and C61's
    sentence, the reply with C62 point 2's sentence. Talk off and on."""
    env = rate_env(tmp_path, monkeypatch, MOCO_TALK=talk)
    answered_statistic(env, ask(env, "the arrest rate by age band in 2025?", rate(Y25)))
    refused_turn(env, count_turn(env, age(17, 64)))


@pytest.mark.needs_r
@pytest.mark.parametrize("talk", TALK)
def test_17_to_64_then_a_rate_by_age_band_is_refused_before_anything_is_computed(
        tmp_path, monkeypatch, talk):
    """Point 7, "and in the other order": 17 to 64 in 2025 (answered), then a rate by age band of
    2025: refused before anything is computed (no job folder, rates.count not called)."""
    env = rate_env(tmp_path, monkeypatch, MOCO_TALK=talk)
    answered_count(env, count_turn(env, age(17, 64)))
    calls = spy_runs(monkeypatch)
    refused_turn(env, ask(env, "and the arrest rate by age band in 2025?", rate(Y25)))
    nothing_run(env, calls)


@pytest.mark.needs_r
@pytest.mark.parametrize("order", ["rate first", "count first"])
def test_18_to_64_instead_is_answered(tmp_path, monkeypatch, order):
    """Point 7's test, "then 18 to 64 instead: answered", in both orders. Passes today; must still
    pass."""
    env = rate_env(tmp_path, monkeypatch)
    if order == "rate first":
        answered_statistic(env, ask(env, "the arrest rate by age band in 2025?", rate(Y25)))
        answered_count(env, count_turn(env, age(18, 64)))
    else:
        answered_count(env, count_turn(env, age(18, 64)))
        answered_statistic(env, ask(env, "the arrest rate by age band in 2025?", rate(Y25)))


@pytest.mark.needs_r
def test_a_rate_by_gender_then_17_to_64_is_answered(tmp_path, monkeypatch):
    """Point 7's test, "a rate by gender, then 17 to 64: answered" (its one band is every age).
    Passes today; must still pass."""
    env = rate_env(tmp_path, monkeypatch)
    answered_statistic(env, ask(env, "the arrest rate by gender in 2025?", rate(Y25, "gender")))
    answered_count(env, count_turn(env, age(17, 64)))


@pytest.mark.needs_r
def test_a_rate_by_age_band_then_17_and_over_is_refused(tmp_path, monkeypatch):
    """Point 7: 65 and over is one of the Census's bands, so the rate by age band and 17 and over
    give the 17-year-olds: refused (a build that ends "and over" at 64 would answer). Passes today
    (the source's own last band, 55 to 98, gives the same); must still pass."""
    env = rate_env(tmp_path, monkeypatch)
    answered_statistic(env, ask(env, "the arrest rate by age band in 2025?", rate(Y25)))
    refused_turn(env, count_turn(env, age(17)))


@pytest.mark.needs_r
def test_the_new_rate_is_checked_with_the_census_bands(tmp_path, monkeypatch):
    """Point 7, "for a rate of this message": the rate's own check asks for its figures with the
    Census's bands (spied on shown_figures and shown_bands; each still does its work)."""
    env = rate_env(tmp_path, monkeypatch)
    calls = spy_bands(monkeypatch)
    answered_statistic(env, ask(env, "the arrest rate by age band in 2025?", rate(Y25)))
    rate_calls = [bands for _, options, bands in calls if options == RATE_BY_BAND]
    assert rate_calls, f"premise: the rate was checked: {calls}"
    assert all(b is not None and [tuple(x) for x in b] == CENSUS for b in rate_calls), rate_calls


def slack_turn(env, slack, n, text, *steps):
    env.model = FakeModel(*steps, clock=env.clock)
    replies = []

    def agent(question, thread_key, user_id, memory_minutes=None):
        reply = env.ask(question, model=env.model, thread_key=thread_key, user_id=user_id,
                        memory_minutes=memory_minutes, now=NOW_S3)
        replies.append(reply)
        return reply
    ts = f"1762795{n:03d}.000{n:03d}"
    event = (mention(f"<@{AGENT_USER}> {text}", ts=ROOT_TS, user=USER) if n == 1 else
             mention(f"<@{AGENT_USER}> {text}", ts=ts, thread_ts=ROOT_TS, user=USER))
    label = process(event, settings=env.settings, store=env.store, agent=agent, slack=slack,
                    event_id=f"EvR30{n:06d}", now=NOW_S3)
    return label, (replies[-1] if replies else None)


@pytest.mark.needs_r
def test_a_rate_kept_through_reset_then_17_to_64_is_refused(tmp_path, monkeypatch):
    """Point 7, "for one kept through reset": in one Slack thread, the rate by age band of 2025
    (answered, R run), `reset`, then 17 to 64 in 2025: refused with C62 point 2's sentence."""
    env = rate_env(tmp_path, monkeypatch, **FAKE_SECRETS, SLACK_ALLOWED_TEAM_ID=TEAM,
                   SLACK_ALLOWED_USER_IDS=f"{USER},{USER2}")
    slack = FakeSlack()
    label, reply = slack_turn(env, slack, 1, "the arrest rate by age band in 2025?",
                              Step(rate(Y25)), Step(finish("finding", "I found that.")))
    assert label == "answered", (label, reply and reply.text)
    label, _ = slack_turn(env, slack, 2, "reset")
    assert label == "reset", label
    label, reply = slack_turn(env, slack, 3, "how many aged 17 to 64 in 2025?",
                              Step(rates_count(Y25, [age(17, 64)])),
                              Step(finish("finding", "I counted {r1.count}.")))
    refused_turn(env, reply)
