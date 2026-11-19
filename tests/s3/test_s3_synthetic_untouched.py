"""Synthetic mode stays exactly as it is: docs/S3A-DESIGN.md C0 and C12's first bullet, and
brief S3A-A step 7 ("with MOCO_DATA unset the tools offered, the prompt file and three
end-to-end turns are exactly as today"). Also C0's other side: what county mode offers, and
C4's new settings.

What this file covers
- Three turns end to end (s3support.synthetic_three_turns: a count with a passing finding,
  two counts compared, then `details`) give exactly what tests/s3/fixtures/
  synthetic_today.json recorded from the program before stage 3 (commit 5233ceb): every
  reply field, and every message and tool the model was given. With MOCO_DATA unset, and
  with MOCO_DATA=synthetic.
- With MOCO_DATA unset: the seven stage 2 tools are offered and the system message starts
  with config/agent_prompt_v2.md (R8); a `count` call (county mode's tool) is not obeyed.
- MOCO_DATA and MOCO_STATE_DIR as settings (C0, C4): synthetic by default, county when set,
  and var/ of the project as the default state folder.
- County mode (C0): the eight tools (count, share, compare, describe_data, ask_user,
  show_details, decline, finish; no count_arrests), the prompt config/agent_prompt_s3.md,
  a count_arrests call not obeyed, and no synthetic data or synthetic line in a county
  answer.

Readings taken (kit-log/raw/S3A-A-notes.txt)
- The settings are read like A14's: attribute settings.moco_data and settings.moco_state_dir;
  a MOCO_DATA value other than synthetic or county is a ConfigError that names the KEY
  (A14's rule for a setting with listed values).
- "Not obeyed": the call gets {"error": "BAD_CALL"} (A3, a tool not offered) and nothing is
  counted from the other mode's data.

Expected to pass today: the golden comparisons and the synthetic tools and prompt (they
describe today's behaviour; they must still pass after the build). Everything about
MOCO_DATA, MOCO_STATE_DIR and county mode fails until the build.
"""
import json
from pathlib import Path

import pytest

from p1support import (AGENT_PROMPT_MD, LINE2_FIRST, LINE2_LATER, ONE_COUNT_TEXT, Env, Step,
                       count as count_arrests, finish, make_settings, manifests, mod,
                       prompt_version_pattern, system_text, tool_messages)
from s3support import (AGENT_PROMPT_S3, A_ID, COUNTY_TOOLS, Q_COUNT, REPO, SYNTHETIC_TODAY,
                       SYNTHETIC_TOOLS, CountyEnv, count, synthetic_three_turns, turn_json, year)


def golden():
    return json.loads(SYNTHETIC_TODAY.read_text(encoding="utf-8"))["turns"]


def assert_same_as_today(turns):
    """Turn by turn, so a difference says where it is."""
    today = golden()
    assert len(turns) == len(today) == 3
    for n, (now, then) in enumerate(zip(turns, today), 1):
        assert now["question"] == then["question"]
        assert now["reply"] == then["reply"], f"turn {n}: the reply differs from today's"
        assert len(now["model_calls"]) == len(then["model_calls"]), f"turn {n}: model calls"
        for k, (a, b) in enumerate(zip(now["model_calls"], then["model_calls"])):
            assert a["tools"] == b["tools"], f"turn {n}, model call {k}: the tools differ"
            assert a["messages"] == b["messages"], f"turn {n}, model call {k}: the messages differ"


# ---- exactly as today ------------------------------------------------------------------------

def test_the_recording_is_of_three_synthetic_turns():
    """A premise: the recording holds the three turns, answered as stage 2 answers them."""
    today = golden()
    assert [t["reply"]["status"] for t in today] == ["ANSWERED", "ANSWERED", "DETAILS"]
    assert [t["reply"]["reply_style"] for t in today] == ["agent", "agent", "fixed"]
    assert "SYNTHETIC" in today[0]["reply"]["text"] and LINE2_FIRST in today[0]["reply"]["text"]
    assert today[1]["reply"]["text"].endswith(LINE2_LATER)
    assert today[2]["model_calls"] == []  # `details` is answered by Python (A4 step 2)


def test_three_turns_with_moco_data_unset_are_exactly_as_today(tmp_path):
    """C0: `synthetic` (the default): everything behaves exactly as today."""
    assert_same_as_today(synthetic_three_turns(tmp_path))


def test_three_turns_with_moco_data_synthetic_are_exactly_as_today(tmp_path):
    """C0: MOCO_DATA=synthetic is the same as leaving it unset."""
    assert_same_as_today(synthetic_three_turns(tmp_path, MOCO_DATA="synthetic"))


@pytest.mark.parametrize("value", [None, "synthetic"])
def test_synthetic_mode_offers_the_seven_stage_2_tools_and_the_v2_prompt(tmp_path, value):
    """C0 and R8: with MOCO_DATA unset or synthetic, the tools are A3's seven and the system
    message starts with config/agent_prompt_v2.md; the turn record names that prompt."""
    env = Env(tmp_path) if value is None else Env(tmp_path, MOCO_DATA=value)
    reply = env.ask("How many arrests were recorded each month in 2025 for ages 18 to 25?",
                    Step(count_arrests(2025, "18_25")), Step(finish("finding", ONE_COUNT_TEXT)))
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert env.model.tools_offered(0) == SYNTHETIC_TOOLS
    prompt = AGENT_PROMPT_MD.read_text(encoding="utf-8").strip()
    assert system_text(env.model.calls[0]["messages"]).startswith(prompt)
    record = json.loads((env.runs_dir / reply.turn_id / "turn.json").read_text(encoding="utf-8"))
    assert prompt_version_pattern(AGENT_PROMPT_MD).search(str(record["prompt_version"]))


def test_synthetic_mode_does_not_obey_a_county_count(tmp_path):
    """C0: `count` is county mode's tool; in synthetic mode it is not offered, so a call to
    it is a BAD_CALL (A3) and nothing is counted."""
    env = Env(tmp_path)
    reply = env.ask("How many arrests were recorded each month in 2025 for ages 18 to 25?",
                    Step(count(A_ID, year(2025))), Step(finish("finding", "I counted {r1.count}.")))
    assert env.model.answer(0) == {"error": "BAD_CALL"}
    assert reply.results == [] and reply.run_ids == []
    assert reply.status != "ANSWERED"


# ---- the settings (C0, C4) ------------------------------------------------------------------

def test_moco_data_is_synthetic_by_default(tmp_path):
    """C0: MOCO_DATA is `synthetic` (the default) or `county`."""
    assert make_settings(tmp_path).moco_data == "synthetic"


@pytest.mark.parametrize("value", ["synthetic", "county"])
def test_moco_data_is_read(tmp_path, value):
    assert make_settings(tmp_path, MOCO_DATA=value).moco_data == value


def test_moco_data_from_the_private_file_too(tmp_path):
    """As every setting (P1 section 4): the private file is read, the environment wins."""
    assert make_settings(tmp_path, file_text="MOCO_DATA=county\n").moco_data == "county"
    assert make_settings(tmp_path, file_text="MOCO_DATA=county\n",
                         MOCO_DATA="synthetic").moco_data == "synthetic"


@pytest.mark.parametrize("value", ["real", "both"])
def test_another_moco_data_value_is_a_config_error_naming_the_key(tmp_path, value):
    """READING (A14's rule for a setting with listed values): a value outside `synthetic`
    and `county` is a ConfigError that names the KEY, never the value."""
    config = mod("config")
    with pytest.raises(config.ConfigError) as caught:
        make_settings(tmp_path, MOCO_DATA=value)
    assert "MOCO_DATA" in str(caught.value)
    assert value not in str(caught.value).replace("MOCO_DATA", "")


def test_moco_state_dir_defaults_to_the_projects_var(tmp_path):
    """C4: MOCO_STATE_DIR (default: the project's var/)."""
    settings = make_settings(tmp_path)
    assert Path(settings.moco_state_dir).resolve() == (REPO / "var").resolve()


def test_moco_state_dir_is_read(tmp_path):
    state = tmp_path / "somewhere" / "state"
    assert Path(make_settings(tmp_path, MOCO_STATE_DIR=str(state)).moco_state_dir) == state


# ---- county mode's side of C0 ----------------------------------------------------------------

def county_turn(tmp_path, monkeypatch):
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask(Q_COUNT, Step(count(A_ID, year(2025))),
                    Step(finish("finding", "I counted {r1.count}.")))
    return env, reply


def test_county_mode_offers_the_eight_county_tools(tmp_path, monkeypatch):
    """C0: count, share, compare, describe_data, ask_user, show_details, decline, finish (no
    count_arrests)."""
    env, reply = county_turn(tmp_path, monkeypatch)
    for n in range(len(env.model.calls)):
        assert env.model.tools_offered(n) == COUNTY_TOOLS


def test_county_mode_uses_the_s3_prompt(tmp_path, monkeypatch):
    """C0: the prompt is config/agent_prompt_s3.md; the turn record names it with the first
    8 hex of its sha256 (A11)."""
    env, reply = county_turn(tmp_path, monkeypatch)
    assert AGENT_PROMPT_S3.is_file(), "config/agent_prompt_s3.md is missing"
    prompt = AGENT_PROMPT_S3.read_text(encoding="utf-8").strip()
    assert prompt, "the county prompt is empty"
    assert system_text(env.model.calls[0]["messages"]).startswith(prompt)
    assert prompt_version_pattern(AGENT_PROMPT_S3).search(
        str(turn_json(reply, env.runs_dir)["prompt_version"]))


def test_county_mode_does_not_obey_count_arrests(tmp_path, monkeypatch):
    """C0: no count_arrests in county mode: a call to it is a BAD_CALL (A3), and the
    SYNTHETIC data is not counted (no stage 1 run of the synthetic skill is made)."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask(Q_COUNT, Step(count_arrests(2025, "18_25")),
                    Step(finish("finding", ONE_COUNT_TEXT)))
    assert env.model.answer(0) == {"error": "BAD_CALL"}
    assert reply.results == [] and reply.status != "ANSWERED"
    assert not [m for m in manifests(env.runs_dir) if m.get("data_class") == "SYNTHETIC"]


def test_a_county_answer_holds_no_synthetic_line(tmp_path, monkeypatch):
    """C0: real and made-up data never meet in one turn: a county answer carries none of
    the synthetic data's fixed lines (A7's line 2), and no stage 1 SYNTHETIC run is made."""
    env, reply = county_turn(tmp_path, monkeypatch)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert LINE2_FIRST not in reply.text and LINE2_LATER not in reply.text
    assert "SYNTHETIC (made-up) test data" not in reply.text
    assert not [m for m in manifests(env.runs_dir) if m.get("data_class") == "SYNTHETIC"]
    for message in tool_messages(env.model.calls[-1]["messages"]):
        assert "SYNTHETIC:arrests_v1" not in message["content"]
