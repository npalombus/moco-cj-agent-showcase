"""S3A C67 (D-092): a statistic whose kept period is too short is run on every month.

Written by the planning chat (no separate tests session, D-092), from C67's "Tests" line. Seen
again on the live code on 20 November (Nino's Slack test): after a count of 2025, "did arrests
change after January 2024?" and "are arrests of women rising faster than arrests of men?" both
ended "That needs at least 24 full months of records"."""
import re

import pytest

import s3ssupport as T
from p1support import Step, finish
from s3sagent import MAIN_ID, StatsEnv, analyze, answered
from s3support import KEPT_ANY, count

Y2025 = {"from": "2025-01-01", "to": "2025-12-31"}
TOO_SHORT = "That needs at least 24 full months"


def _count_one_year(env):
    reply = env.ask("How many arrests were there in 2025?", Step(count(MAIN_ID, Y2025)),
                    Step(finish("finding", "I counted {r1.count}.")))
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)


KINDS = [
    ("trend", {"kind": "trend", "source": MAIN_ID}, "{a1.trend}."),
    ("before_after", {"kind": "before_after", "source": MAIN_ID,
                      "options": {"date": "2024-01-01"}}, "{a1.step}. {a1.bend}."),
    ("trend_compare", {"kind": "trend_compare", "source": MAIN_ID,
                       "filters": [T.FEMALE], "options": {"versus": [T.is_("gender", "male")]}},
     "{a1.difference}."),
]


@pytest.mark.needs_r
@pytest.mark.parametrize("name,args,text", KINDS, ids=[k[0] for k in KINDS])
def test_after_a_count_of_one_year_a_statistic_runs_on_every_month(tmp_path, monkeypatch, name,
                                                                   args, text):
    env = StatsEnv(tmp_path, monkeypatch)
    _count_one_year(env)
    reply = answered(env.ask("and is that changing?", Step(analyze(args)),
                             Step(finish("finding", text))))
    assert TOO_SHORT not in reply.text, reply.text
    assert not KEPT_ANY.search(reply.text), "the kept year is not named as kept: " + reply.text
    assert not (reply.carried or {}).get("period"), reply.carried


@pytest.mark.needs_r
def test_a_period_the_message_states_is_never_widened(tmp_path, monkeypatch):
    env = StatsEnv(tmp_path, monkeypatch)
    reply = env.ask("Is the trend in 2025 going up?",
                    Step(analyze({"kind": "trend", "source": MAIN_ID, "period": Y2025})),
                    Step(finish("finding", "{a1.trend}.")))
    assert reply.status != "ANSWERED", (reply.status, reply.text)
    assert re.search(r"at least 24 full months", reply.text), reply.text


@pytest.mark.needs_r
def test_a_kept_period_long_enough_is_still_used_and_said(tmp_path, monkeypatch):
    env = StatsEnv(tmp_path, monkeypatch)
    first = env.ask("How many arrests were there from 2021 to 2025?",
                    Step(count(MAIN_ID, T.P5)), Step(finish("finding", "I counted {r1.count}.")))
    assert first.status == "ANSWERED", (first.status, first.text)
    reply = answered(env.ask("And is that going up?",
                             Step(analyze({"kind": "trend", "source": MAIN_ID})),
                             Step(finish("finding", "I found that {a1.trend}."))))
    assert KEPT_ANY.search(reply.text), reply.text
    assert reply.carried.get("period"), reply.carried
