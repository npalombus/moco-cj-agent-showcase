"""T0 of docs/T-DESIGN.md, and T7's first point: MOCO_TALK unset or `off` leaves everything as
it is today, in both data modes; `on` and `off` are its only values.

What this file covers
- The setting: `off` by default, `on` and `off` read from the environment and from the
  private file, any other value a ConfigError that names the KEY (as A14 and C0 do for
  their settings).
- With MOCO_TALK unset and with `off` (each test runs both ways):
  - three SYNTHETIC turns end to end are exactly what tests/s3/fixtures/synthetic_today.json
    recorded from the program before stage 3: every reply field, and every message and
    tool the model was given (so the tools offered, the prompt file and one finding);
  - one about_data and one decline give today's replies, written out by hand from A7 and
    R1 (p1support);
  - the finish tool offers today's three kinds, and a finish of kind `talk` is not obeyed
    (A3: a BAD_CALL);
  - T2's own passing example fails today's check (WORD) and is answered at once with the
    fixed rendering: no second try;
  - county mode offers its eight tools with today's three kinds of finish, and its system
    message starts with config/agent_prompt_s3.md.

READING: the setting is read like the others (A14): attribute settings.moco_talk. Each
"as today" test first checks that the setting reads `off`, so it fails until the setting
exists (brief T-A step 5: every new test fails until the build), and must pass after it.
"""
import json
import re

import pytest

from p1support import (AGENT_PROMPT_MD, DATA_TAG, ONE_COUNT_TEXT, Env, Step, about_text, count,
                       decline, describe, fact_slots, fill_expect, finish, fixed_line1_re,
                       make_settings, mod, prompt_version_pattern, single_sentence_facts,
                       system_text, assert_answered, assert_fixed)
from s3support import (AGENT_PROMPT_S3, A_ID, COUNTY_TOOLS, Q_COUNT, SYNTHETIC_TODAY,
                       SYNTHETIC_TOOLS, CountyEnv, count as county_count,
                       synthetic_three_turns, year)
from tsupport import HELLO_TEXT, finish_kinds, turn_json

TODAY_KINDS = ["finding", "about_data", "background"]
UNSET_OR_OFF = [pytest.param({}, id="unset"), pytest.param({"MOCO_TALK": "off"}, id="off")]
MIXED_EXAMPLE = "Here you go. I counted {r1.count}. {r1.months}. Want it compared with another year?"


def setting_is_off(tmp_path, values):
    """The premise of every "as today" test: the setting exists and reads `off`."""
    assert make_settings(tmp_path, **values).moco_talk == "off"


# ---- the setting (T0) --------------------------------------------------------------------------

def test_moco_talk_is_off_by_default(tmp_path):
    """T0: `off` (the default)."""
    assert make_settings(tmp_path).moco_talk == "off"


@pytest.mark.parametrize("value", ["off", "on"])
def test_moco_talk_is_read_from_the_environment_and_the_private_file(tmp_path, value):
    """T0: `off` or `on`; like every setting, the private file is read and the environment
    wins (P1 section 4)."""
    assert make_settings(tmp_path, MOCO_TALK=value).moco_talk == value
    assert make_settings(tmp_path, file_text=f"MOCO_TALK={value}\n").moco_talk == value
    other = "on" if value == "off" else "off"
    assert make_settings(tmp_path, file_text=f"MOCO_TALK={other}\n",
                         MOCO_TALK=value).moco_talk == value


@pytest.mark.parametrize("where", ["environ", "file"])
@pytest.mark.parametrize("bad", ["yes", "true", "talk"])
def test_another_value_is_a_config_error_naming_the_key(tmp_path, bad, where):
    """T0: any other value is a ConfigError naming the key (never the value)."""
    config = mod("config")
    with pytest.raises(config.ConfigError) as caught:
        if where == "environ":
            make_settings(tmp_path, MOCO_TALK=bad)
        else:
            make_settings(tmp_path, file_text=f"MOCO_TALK={bad}\n")
    message = str(caught.value)
    assert "MOCO_TALK" in message
    assert bad not in message.replace("MOCO_TALK", "")


# ---- SYNTHETIC mode exactly as today ---------------------------------------------------------------

@pytest.mark.parametrize("values", UNSET_OR_OFF)
def test_three_turns_are_exactly_as_today(tmp_path, values):
    """T0 and T7: a finding, a compared finding and `details` give exactly the replies, the
    messages and the tools (finish with today's three kinds) that the program gave before
    stage 3, as recorded in tests/s3/fixtures/synthetic_today.json."""
    setting_is_off(tmp_path, values)
    today = json.loads(SYNTHETIC_TODAY.read_text(encoding="utf-8"))["turns"]
    now = synthetic_three_turns(tmp_path, **values)
    assert len(now) == len(today) == 3
    for n, (a, b) in enumerate(zip(now, today), 1):
        assert a["question"] == b["question"]
        assert a["reply"] == b["reply"], f"turn {n}: the reply differs from today's"
        assert len(a["model_calls"]) == len(b["model_calls"]), f"turn {n}: model calls"
        for k, (x, y) in enumerate(zip(a["model_calls"], b["model_calls"])):
            assert x["tools"] == y["tools"], f"turn {n}, call {k}: the tools differ"
            assert x["messages"] == y["messages"], f"turn {n}, call {k}: the messages differ"


@pytest.mark.parametrize("values", UNSET_OR_OFF)
def test_the_tools_and_the_prompt_file_are_todays(tmp_path, values):
    """T0: the seven tools, finish with today's three kinds and no `talk`, the system message
    starting with config/agent_prompt_v2.md, and the turn record naming that file."""
    setting_is_off(tmp_path, values)
    env = Env(tmp_path, **values)
    reply = env.ask("How many arrests were recorded each month in 2025 for ages 18 to 25?",
                    Step(count(2025, "18_25")), Step(finish("finding", ONE_COUNT_TEXT)))
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert env.model.tools_offered(0) == SYNTHETIC_TOOLS
    assert finish_kinds(env.model.calls[0]["tools"]) == TODAY_KINDS
    prompt = AGENT_PROMPT_MD.read_text(encoding="utf-8").strip()
    assert system_text(env.model.calls[0]["messages"]).startswith(prompt)
    record = turn_json(reply, env.runs_dir)
    assert prompt_version_pattern(AGENT_PROMPT_MD).search(str(record["prompt_version"]))


@pytest.mark.parametrize("values", UNSET_OR_OFF)
def test_one_about_data_is_as_today(tmp_path, values):
    """T0 with R1: after describe_data, a passing about_data text is filled, with DATA_TAG
    added when it lacks SYNTHETIC; EXPLAINED, kind about_data, style agent."""
    setting_is_off(tmp_path, values)
    text = about_text(single_sentence_facts()[0])
    filled = fill_expect(text, fact_slots())
    assert "SYNTHETIC" not in filled
    env = Env(tmp_path, **values)
    reply = env.ask("What data do you have?", Step(describe()), Step(finish("about_data", text)))
    assert (reply.status, reply.reply_kind, reply.reply_style) == \
        ("EXPLAINED", "about_data", "agent"), (reply.status, reply.reply_style, reply.text)
    assert re.fullmatch(re.escape(filled) + "[ \n]" + re.escape(DATA_TAG), reply.text), reply.text


@pytest.mark.parametrize("values", UNSET_OR_OFF)
def test_one_decline_is_as_today(tmp_path, values):
    """T0 with A7: decline gives its row word for word, UNSUPPORTED with its code."""
    setting_is_off(tmp_path, values)
    env = Env(tmp_path, **values)
    reply = env.ask("How many arrests were there in Bethesda?", Step(decline("UNSUPPORTED_FIELD")))
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", "UNSUPPORTED_FIELD")
    assert_fixed(reply.text, "UNSUPPORTED_FIELD")


@pytest.mark.parametrize("values", UNSET_OR_OFF)
def test_a_finish_of_kind_talk_is_not_obeyed(tmp_path, values):
    """T0: with `off` the finish tool is today's, so a finish of kind `talk` is a bad call
    (A3: {"error": "BAD_CALL"}, the turn goes on) and its text is never sent."""
    setting_is_off(tmp_path, values)
    env = Env(tmp_path, **values)
    reply = env.ask("hello", Step(finish("talk", HELLO_TEXT)),
                    Step(decline("UNRECOGNIZED_QUESTION")))
    assert env.model.answer(0) == {"error": "BAD_CALL"}
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", "UNRECOGNIZED_QUESTION")
    assert HELLO_TEXT not in reply.text
    assert_fixed(reply.text, "UNRECOGNIZED_QUESTION")


@pytest.mark.parametrize("values", UNSET_OR_OFF)
def test_a_finding_with_sentences_of_its_own_fails_as_today(tmp_path, values):
    """T0: every check as today. T2's passing example holds words that are not on R1's list
    ("go", "compared", "another", "year"), so today it fails WORD, and the turn ends at once
    with the fixed rendering, style fallback: no REWRITE, no second finish."""
    setting_is_off(tmp_path, values)
    env = Env(tmp_path, **values)
    reply = env.ask("How many arrests were recorded each month in 2025 for ages 18 to 25?",
                    Step(count(2025, "18_25")), Step(finish("finding", MIXED_EXAMPLE)),
                    Step(finish("finding", ONE_COUNT_TEXT)))
    assert len(env.model.calls) == 2, "a second finish was asked for"
    assert (reply.status, reply.reply_style) == ("ANSWERED", "fallback"), reply.reply_style
    assert "WORD" in reply.draft_failures, reply.draft_failures
    assert_answered(reply.text, fixed_line1_re([(2025, "18_25")]), first=True)


# ---- county mode exactly as today ---------------------------------------------------------------

@pytest.mark.parametrize("values", UNSET_OR_OFF)
def test_county_mode_offers_todays_tools_and_prompt(tmp_path, monkeypatch, values):
    """T0 in county mode: the eight tools of C0, finish with today's three kinds, the system
    message starting with config/agent_prompt_s3.md, and the turn record naming it."""
    setting_is_off(tmp_path, values)
    env = CountyEnv(tmp_path, monkeypatch, **values)
    reply = env.ask(Q_COUNT, Step(county_count(A_ID, year(2025))),
                    Step(finish("finding", "I counted {r1.count}.")))
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert env.model.tools_offered(0) == COUNTY_TOOLS
    assert finish_kinds(env.model.calls[0]["tools"]) == TODAY_KINDS
    prompt = AGENT_PROMPT_S3.read_text(encoding="utf-8").strip()
    assert system_text(env.model.calls[0]["messages"]).startswith(prompt)
    record = turn_json(reply, env.runs_dir)
    assert prompt_version_pattern(AGENT_PROMPT_S3).search(str(record["prompt_version"]))
