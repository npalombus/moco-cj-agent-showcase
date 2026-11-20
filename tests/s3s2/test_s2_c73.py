"""S3A C73 and C74 (D-091), written by the planning chat (no separate tests session, D-091).

C73: a rate is for the whole county, so a district filter kept from earlier (and not named in
the rate call) is left out of the rate, and the reply says so, instead of refusing. Seen in the
rehearsal of 20 November: "same but without district 8", then a rate by gender, was refused once
in two runs. A district named in the call is still refused (R10 point 7).

C74: the talk prompt tells the model never to ask which source (the program uses the last
answer's source, or asks itself). Seen in the rehearsal: "compare district 2 and district 3 in
2025" made the model ask which source, twice."""
from pathlib import Path

import pytest

import s2support as T
from p1support import Step, call, finish
from s2agent import RATES, RATES_ID, S2Env, ask_rate
from s3sagent import job_folders

from moco_agent import replies

DISTRICT_3 = {"field": "district", "in": ["district 3"]}
LINE = replies.whole_county_line(["district 3"])


CONFIG = Path(__file__).resolve().parents[2] / "config"


def text_of(name):
    return (CONFIG / name).read_text(encoding="utf-8")


def _count_district_3(env):
    reply = env.ask("How many arrests were there in district 3 in 2025?",
                    Step(call("count", {"source": RATES_ID, "period": {"year": 2025},
                                        "filters": [DISTRICT_3]})),
                    Step(finish("finding", "I counted {r1.count}.")))
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    return reply


def test_the_line_names_the_district_and_the_reason():
    assert LINE == ("(A rate is for the whole county, because the Census does not count residents "
                    "by police district, so I did not keep district 3 from earlier.)")


@pytest.mark.needs_r
def test_a_district_kept_from_earlier_is_left_out_of_a_rate(tmp_path, monkeypatch):
    env = S2Env(tmp_path, monkeypatch, names=(RATES,))
    _count_district_3(env)
    reply = ask_rate(env, arguments=T.analyze_arguments("all_re_2025"), text="I found that.",
                     question="and per 10,000 residents?")
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert LINE in reply.text, reply.text
    assert "I kept district 3" not in reply.text, reply.text
    assert len(job_folders(env)) == 1, "the rate was run once"


def test_a_district_named_in_the_rate_call_is_still_refused(tmp_path, monkeypatch):
    env = S2Env(tmp_path, monkeypatch, names=(RATES,))
    _count_district_3(env)
    reply = ask_rate(env, arguments=T.analyze_arguments("all_re_2025", filters=[DISTRICT_3]),
                     question="and per 10,000 residents in district 3?")
    assert reply.status != "ANSWERED", (reply.status, reply.text)
    assert T.REFUSE["in_district"] in reply.text, reply.text
    assert LINE not in reply.text
    assert job_folders(env) == []


def test_c74_the_talk_prompt_says_never_to_ask_which_source():
    from s3support import C74_SENTENCE
    text = text_of("agent_prompt_s3_talk.md")
    rule_1 = [line for line in text.split("\n") if line.startswith("1. ")]
    assert len(rule_1) == 1 and rule_1[0].count(C74_SENTENCE) == 1, rule_1
    assert C74_SENTENCE not in text_of("agent_prompt_s3.md"), "the talk prompt only, as C70"
