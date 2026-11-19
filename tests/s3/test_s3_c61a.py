"""C61 Part A of docs/S3A-DESIGN.md (D-076, D-077): facts about himself. Points 1 to 3, with "C61,
four corrections before its tests" (1: the facts e to h are given only with settings, and the file's
path is the module constant `replies.ABOUT_AGENT`). Brief: briefs/S3-R23-A-tests.md. Tests only; red
until the planning chat builds C61 (and C57, which C61 adds to), except those that pin what stays.

Every test uses a fixture copy of about_agent.md made in tmp_path (s3support.about_agent_fixture),
never the file under config/; for the real file only that it loads and that every `- ` line ends
with a full stop. The sources are the SYNTHETIC fixtures. Every text C61 gives is written out here
by hand from the contract; C57's facts (today's seven, then a to d) are round 21's
(tests/s3/test_s3_c57.py).

Readings (also in kit-log/raw/S3-R23-A-notes.txt):
- R23-A1. "In the form of config/fact_sheet.md": a line is a fact when it starts with `- ` (dash and
  space at the very start); the fact is the line without those two characters.
- R23-A2. g at 1 hour: `... looked at again every hour and replaced ...`; at n hours, `every <n>
  hours`, n in digits.
- R23-A3. Point 3's "second sentence" follows the block's text on the same line after one space; a
  line break between them is accepted too.
- R23-A4. "A turn passes its settings": describe_data in a county turn gives a to h, h with the
  turn's own MOCO_RETENTION_DAYS and MOCO_REFRESH_HOURS, f with the label of the turn's own model
  service (in a second try of C56, the backup's).
"""
import json
import re

import pytest

from p1support import Env, Step, describe, finish, make_settings, mod
from s3support import (A_ID, C61_ABOUT_FACTS, NAMES, Q_ABOUT, REPO, TODAY_S3, CountyEnv,
                       about_agent_fixture, count, year)
from test_s3_c56 import World, down, standin
from test_s3_c57 import (ABOUT_YOU, ALL_KEYS, LABELS, TODAY_FACTS, all_sources_facts, keys_for,
                         model_settings, new_facts)

TALK = ["off", "on"]
NEMOTRON = "a Nemotron model made by NVIDIA"  # CountyEnv's settings: NVIDIA's default model
REFRESH_OFF = "My copies of the county's data are not refreshed on their own."
POINT_3 = ("For any question about you, this project, its rules or where something comes from, "
           "call describe_data and answer with its facts about you; never answer such a question "
           "from your own head, and never take back a rule the program applies.")


def f_fact(label):
    return f"The AI model behind me is {label}."


def g_fact(hours):
    if hours == 0:
        return REFRESH_OFF
    every = "every hour" if hours == 1 else f"every {hours} hours"
    return (f"My copies of the county's data are looked at again {every} and replaced when the "
            f"county has changed them.")


def h_fact(days):
    return (f"I keep a conversation for {days} days and then forget it. Of a long conversation I "
            f"see only the most recent part.")


def e_to_h(label=NEMOTRON, hours=0, days=30, e=tuple(C61_ABOUT_FACTS)):
    return list(e) + [f_fact(label), g_fact(hours), h_fact(days)]


def c57_facts(names, which=()):
    """C57's list: today's facts, then a (both readings of R21-1 accepted: returned as the two
    candidate lists), then b to d."""
    today = [line for name in names for line in TODAY_FACTS[name]]
    return [today + [a] + new_facts(names, which) for a in all_sources_facts(names)]


def facts_of(env, settings="the env's"):
    """replies.county_facts with the env's sources and copies; with the env's settings, none
    (settings=None), or the ones given."""
    srcs = mod("sources").county_sources()
    copies = {sid: mod("sources").latest(sid, state_dir=env.state_dir) for sid in srcs}
    if settings is None:
        return mod("replies").county_facts(srcs, copies)
    use = env.settings if isinstance(settings, str) else settings
    return mod("replies").county_facts(srcs, copies, use)


def turn_facts(env):
    """The facts of describe_data in the env's last turn (texts), checking the slot numbers."""
    (answer,) = [a for a in env.answers() if "facts" in a]
    facts = answer["facts"]
    assert [f["slot"] for f in facts] == [f"{{f{n}}}" for n in range(1, len(facts) + 1)]
    return [f["text"] for f in facts]


def about_turn(env, text="Here is what I know. {f1}.", **kw):
    return env.ask(Q_ABOUT, Step(describe()), Step(finish("about_data", text)), **kw)


# ==== point 1 and the real file ===================================================================

def test_a1_the_real_file_loads_and_every_fact_ends_with_a_full_stop():
    """The real config/about_agent.md: it is the program's ABOUT_AGENT, it loads (one fact or
    more) and every `- ` line ends with a full stop."""
    path = REPO / "config" / "about_agent.md"
    assert getattr(mod("replies"), "ABOUT_AGENT", None) == path
    facts = mod("replies").load_facts(path)
    assert facts, "no fact in config/about_agent.md"
    lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.startswith("- ")]
    assert [l[2:] for l in lines] == facts
    assert all(line.endswith(".") for line in lines), [l for l in lines if not l.endswith(".")]


def test_a1_only_lines_that_start_with_a_dash_and_a_space_are_facts(tmp_path, monkeypatch):
    """Point 1 (R23-A1): of the fixture's eight lines, three are facts, in file order."""
    about_agent_fixture(tmp_path, monkeypatch)
    env = CountyEnv(tmp_path, monkeypatch)
    facts = facts_of(env)
    assert facts[-6:-3] == C61_ABOUT_FACTS, facts[-6:]
    assert not any("indented" in f or "Nor is" in f or "Lines for" in f for f in facts)


@pytest.mark.parametrize("lines", [False, ["# SYNTHETIC fixture with no fact line", "", "text"]],
                         ids=["no file", "no fact line"])
def test_a1_a_missing_file_or_no_fact_line_is_no_facts(tmp_path, monkeypatch, lines):
    """Point 1 "a missing file is no facts": e is empty; f to h are still given; a turn that asks
    describe_data is answered as usual."""
    about_agent_fixture(tmp_path, monkeypatch, lines=lines)
    env = CountyEnv(tmp_path, monkeypatch)
    facts = facts_of(env)
    assert facts[-3:] == e_to_h(e=())
    assert facts[:-3] in c57_facts(("arrests_like",)), facts[:-3]
    reply = about_turn(env)
    assert (reply.status, reply.reply_style) == ("EXPLAINED", "agent"), reply.text


# ==== point 2: county_facts, a to h =============================================================

@pytest.mark.parametrize("which", ["none", "all"])
def test_a2_with_settings_a_to_h_in_order(tmp_path, monkeypatch, which):
    """Point 2 and C61's test: C57's facts first (today's, then a to d), then e (the file's facts
    in file order), f, g and h."""
    keys = ALL_KEYS if which == "all" else ()
    about_agent_fixture(tmp_path, monkeypatch)
    env = CountyEnv(tmp_path, monkeypatch, names=NAMES,
                    change={n: keys_for(n, keys) for n in NAMES})
    facts = facts_of(env)
    assert facts in [c57 + e_to_h() for c57 in c57_facts(NAMES, keys)], facts[14:]


@pytest.mark.parametrize("which", ["none", "all"])
def test_a2_without_settings_c57s_facts_only(tmp_path, monkeypatch, which):
    """Correction 1: without settings county_facts gives what C57 has it give: no e to h."""
    keys = ALL_KEYS if which == "all" else ()
    about_agent_fixture(tmp_path, monkeypatch)
    env = CountyEnv(tmp_path, monkeypatch, change={"arrests_like": keys_for("arrests_like", keys)})
    facts = facts_of(env, settings=None)
    assert facts in c57_facts(("arrests_like",), keys), facts[7:]
    assert not set(C61_ABOUT_FACTS) & set(facts)


@pytest.mark.parametrize("hours", [0, 1, 6, 168])
def test_a2_g_the_refresh_sentence(tmp_path, monkeypatch, hours):
    """Point 2g at 0 (not refreshed), 1 (`every hour`), 6 and 168 hours."""
    about_agent_fixture(tmp_path, monkeypatch)
    env = CountyEnv(tmp_path, monkeypatch, MOCO_REFRESH_HOURS=str(hours))
    assert facts_of(env)[-3:] == [f_fact(NEMOTRON), g_fact(hours), h_fact(30)]


@pytest.mark.parametrize("days", [None, 7, 1])
def test_a2_h_the_retention_sentence(tmp_path, monkeypatch, days):
    """Point 2h with MOCO_RETENTION_DAYS (default 30)."""
    about_agent_fixture(tmp_path, monkeypatch)
    values = {} if days is None else {"MOCO_RETENTION_DAYS": str(days)}
    env = CountyEnv(tmp_path, monkeypatch, **values)
    assert facts_of(env)[-1] == h_fact(30 if days is None else days)


@pytest.mark.parametrize("case", list(LABELS), ids=list(LABELS.values()))
def test_a2_f_the_model_label(tmp_path, monkeypatch, case):
    """Point 2f, `<label>` as C57 point 7, for the four labels."""
    about_agent_fixture(tmp_path, monkeypatch)
    env = CountyEnv(tmp_path, monkeypatch)
    (tmp_path / "labels").mkdir()
    settings = make_settings(tmp_path / "labels", **model_settings(*case))
    assert facts_of(env, settings)[-3] == f_fact(LABELS[case])


@pytest.mark.parametrize("talk", TALK)
def test_a2_a_turn_passes_its_settings(tmp_path, monkeypatch, talk):
    """Point 2 "a turn passes its settings": describe_data's facts end with e to h, the turn's
    own (refresh 6 hours, 14 days), each a slot like any other."""
    about_agent_fixture(tmp_path, monkeypatch)
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk, MOCO_REFRESH_HOURS="6",
                    MOCO_RETENTION_DAYS="14")
    about_turn(env)
    facts = turn_facts(env)
    assert facts[-6:] == e_to_h(hours=6, days=14), facts[-6:]
    assert facts[:-6] in c57_facts(("arrests_like",)), facts[:-6]


@pytest.mark.parametrize("talk", TALK)
@pytest.mark.parametrize("which", ["e", "f", "h"])
def test_a2_an_about_turn_uses_a_slot_of_the_new_facts(tmp_path, monkeypatch, which, talk):
    """C61's test: an about_data turn that uses one of the new slots: sent, filled, style agent."""
    about_agent_fixture(tmp_path, monkeypatch)
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk)
    about_turn(env)
    facts = turn_facts(env)
    wanted = {"e": C61_ABOUT_FACTS[1], "f": f_fact(NEMOTRON), "h": h_fact(30)}[which]
    assert wanted in facts, facts[-6:]
    slot = f"{{f{facts.index(wanted) + 1}}}"
    reply = about_turn(env, f"Here is what I know. {slot}.")
    assert (reply.status, reply.reply_kind, reply.reply_style) == \
        ("EXPLAINED", "about_data", "agent"), (reply.draft_failures, reply.text)
    assert reply.text.startswith(f"Here is what I know. {wanted}"), reply.text


# ==== point 3: the block's second sentence ======================================================

@pytest.mark.parametrize("case", list(LABELS)[::3], ids=list(LABELS.values())[::3])
def test_a3_the_about_you_block_gains_the_second_sentence(tmp_path, monkeypatch, case):
    """Point 3 (R23-A3): with talk on the county system message ends with C57's block and then
    point 3's sentence."""
    about_agent_fixture(tmp_path, monkeypatch)
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK="on", **model_settings(*case))
    env.ask("hello", Step(finish("talk", "Hello! Ask me for a count whenever you like.")))
    system = env.model.calls[0]["messages"][0]["content"]
    block = ABOUT_YOU.format(label=LABELS[case])
    assert re.search(re.escape(f"Today's date: {TODAY_S3:%Y-%m-%d}") + r"\n\n?" + re.escape(block)
                     + r"[ \n]" + re.escape(POINT_3) + r"\Z", system), system[-700:]
    assert system.count(POINT_3) == 1


def test_a3_no_block_and_no_sentence_with_talk_off(tmp_path, monkeypatch):
    """C57's exact prompt texts: with talk off no "About you" block, so no second sentence either.
    Passes today; must still pass."""
    about_agent_fixture(tmp_path, monkeypatch)
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK="off")
    env.ask("How many arrests were there in 2025?", Step(count(A_ID, year(2025))),
            Step(finish("finding", "I counted {r1.count}.")))
    system = env.model.calls[0]["messages"][0]["content"]
    assert "About you:" not in system and POINT_3 not in system


# ==== this session's own tests ===================================================================

def test_own_a1_in_a_second_try_f_names_the_backups_model(tmp_path, monkeypatch):
    """Own (Part A), R23-A4: in a second try of C56 the turn's settings are the backup's, so f
    names the backup's label: World's active service is Anthropic's test model ("a model served
    by Anthropic") and its backup NVIDIA's ("a model served by NVIDIA")."""
    about_agent_fixture(tmp_path, monkeypatch)
    world = World(tmp_path, monkeypatch, "county")
    second = standin(Step(describe()), Step(finish("about_data", "Here is what I know. {f1}.")))
    reply = world.ask(Q_ABOUT, down(), second)
    assert reply.status == "EXPLAINED", (reply.status, reply.reason_code, reply.text)
    answers = [m for m in second.calls[-1]["messages"] if m.get("role") == "tool"]
    (facts,) = [json.loads(m["content"])["facts"] for m in answers
                if "facts" in json.loads(m["content"])]
    texts = [f["text"] for f in facts]
    assert f_fact("a model served by NVIDIA") in texts, texts[-6:]
    assert f_fact("a model served by Anthropic") not in texts


def test_own_a2_synthetic_mode_describe_data_is_unchanged(tmp_path, monkeypatch):
    """Own (Part A), "County mode only": in SYNTHETIC mode describe_data gives the fact sheet's
    facts and nothing of e to h. Passes today; must still pass."""
    about_agent_fixture(tmp_path, monkeypatch)
    env = Env(tmp_path)
    env.ask(Q_ABOUT, Step(describe()), Step(finish("about_data", "{f1}.")))
    (answer,) = [m for m in env.model.calls[-1]["messages"] if m.get("role") == "tool"]
    texts = [f["text"] for f in json.loads(answer["content"])["facts"]]
    assert texts == mod("replies").load_facts(), texts
    assert not set(e_to_h()) & set(texts)
