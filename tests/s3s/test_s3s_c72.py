"""S3A C72 (D-090): an analysis whose remembered period is the whole copy says nothing was kept.

Seen on the live code on 19 November 2026: a second statistic in a thread, after one over the
whole copy, said "(I kept from 1 January 2021 to 18 November 2026 from earlier.)" though no
period was ever given. Written by the planning chat (no separate tests session, D-090)."""
import pytest

import s3ssupport as T
from p1support import Step, finish
from s3sagent import MAIN_ID, Q_TREND, StatsEnv, analyze, answered
from s3support import KEPT_ANY, count


@pytest.mark.needs_r
def test_a_second_statistic_after_one_over_the_whole_copy_keeps_nothing(tmp_path, monkeypatch):
    env = StatsEnv(tmp_path, monkeypatch)
    first = answered(env.ask(Q_TREND, Step(analyze({"kind": "trend", "source": MAIN_ID})),
                             Step(finish("finding", "{a1.trend}."))))
    assert not KEPT_ANY.search(first.text), first.text
    second = answered(env.ask("and when in the week?",
                              Step(analyze({"kind": "timing", "source": MAIN_ID})),
                              Step(finish("finding", "{a1.timing}."))))
    assert not KEPT_ANY.search(second.text), second.text
    assert not (second.carried or {}).get("period"), second.carried


@pytest.mark.needs_r
def test_a_period_from_a_count_is_still_kept(tmp_path, monkeypatch):
    """What stays: a count over 2021 to 2025, then a trend with no period: the count's period is
    kept and said (test_s3s_analyze_spec.py's case, with filters left out)."""
    env = StatsEnv(tmp_path, monkeypatch)
    first = env.ask("How many arrests were there from 2021 to 2025?",
                    Step(count(MAIN_ID, T.P5)), Step(finish("finding", "I counted {r1.count}.")))
    assert first.status == "ANSWERED", (first.status, first.reason_code, first.text)
    reply = answered(env.ask("And is that going up?",
                             Step(analyze({"kind": "trend", "source": MAIN_ID})),
                             Step(finish("finding", "I found that {a1.trend}."))))
    assert KEPT_ANY.search(reply.text), reply.text
    assert reply.carried.get("period"), reply.carried
