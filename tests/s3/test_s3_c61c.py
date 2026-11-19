"""C61 Part C of docs/S3A-DESIGN.md (D-076): a second rewrite, and a fallback that helps. Points 8
and 9, with "C61, two additions after the threads" (5: point 9b, a failed about_data text that named
facts is answered with those facts; `replies.facts_rendering(text, facts)`) and the answer to round
21's question 1 (the file has one fallback line, so SYNTHETIC mode gets C57's line). Brief:
briefs/S3-R23-A-tests.md. Tests only; red until the planning chat builds C61 (and C57), except those
that pin what stays.

All data is SYNTHETIC (the tests/s3 fixtures); replies.ABOUT_AGENT points at a fixture copy.

Readings (also in kit-log/raw/S3-R23-A-notes.txt):
- R23-C1. Point 8 is county mode only (C61: "County mode only"): in SYNTHETIC mode a talk text keeps
  T3's one second try.
- R23-C2. "A finish text of kind talk" includes plain text read as talk (T13: plain text is read as
  a finish and gets T3's second try): it gets the third try too, as a PROGRAM NOTE.
- R23-C3. 9b's rendering: `Here is what I know.`, then each fact the failed text named, in the
  order its slots stand in the text, each once, at most four, joined by one space (each fact is a
  sentence of its own, ending in its full stop); then the notices as C57 point 5 has them (a line
  break, then the notices lines or C57's one line), as the fixed about text carries them. "Named"
  is a slot of describe_data's facts ({f1} to {fN}) written in the text; another slot is not a fact.
"""
import pytest

from p1support import THREAD_2, Env, Step, describe, finish, mod
from s3support import (A_ID, C61_ABOUT_FACTS, NAMES, Q_ABOUT, Q_COUNT, CountyEnv,
                       FALLBACK_LINE_C57, about_agent_fixture, count, county_fallback_line,
                       turn_json, year)
from test_s3_c57 import NOTICES_SHOWN, full_notices
from test_s3_round3 import add_visits

LABEL_TEXT = "Most of them were group Gamma."     # fails LABEL (a label of arrests_like)
PASSING = "Happy to help. Ask me for a count whenever you like."
TALK = ["off", "on"]


@pytest.fixture(autouse=True)
def _about_agent(tmp_path, monkeypatch):
    about_agent_fixture(tmp_path, monkeypatch)


def talk_env(tmp_path, monkeypatch, **values):
    return CountyEnv(tmp_path, monkeypatch, MOCO_TALK="on", **values)


def rewrite_at(env, step):
    """Python's answer to the finish call of model step `step`, as the next step saw it."""
    return env.model.answer(step)


def assert_rewrite(answer, code):
    assert answer.get("error") == "REWRITE", answer
    assert code in answer.get("problems", []), answer


# ==== point 8: one more REWRITE for talk ========================================================

def test_c8_three_failing_talk_texts_two_rewrites_then_the_fallback(tmp_path, monkeypatch):
    """C61's test: three failing talk texts: two REWRITEs, then the county fallback; a passing
    fourth text is never asked for."""
    env = talk_env(tmp_path, monkeypatch)
    reply = env.ask("hello", Step(finish("talk", LABEL_TEXT)), Step(finish("talk", LABEL_TEXT)),
                    Step(finish("talk", LABEL_TEXT)), Step(finish("talk", PASSING)))
    assert len(env.model.calls) == 3, len(env.model.calls)
    assert_rewrite(rewrite_at(env, 0), "LABEL")
    assert_rewrite(rewrite_at(env, 1), "LABEL")
    assert (reply.status, reply.reply_kind, reply.reply_style) == ("TALKED", "talk", "fallback")
    assert reply.text == county_fallback_line(1), reply.text
    assert "LABEL" in reply.draft_failures, reply.draft_failures


def test_c8_the_third_text_passing_is_sent(tmp_path, monkeypatch):
    """C61's test: the third passing: sent as written, style agent."""
    env = talk_env(tmp_path, monkeypatch)
    reply = env.ask("hello", Step(finish("talk", LABEL_TEXT)), Step(finish("talk", LABEL_TEXT)),
                    Step(finish("talk", PASSING)))
    assert len(env.model.calls) == 3
    assert (reply.status, reply.reply_style, reply.text) == ("TALKED", "agent", PASSING), \
        (reply.reply_style, reply.draft_failures, reply.text)


def test_c8_a_finding_keeps_one(tmp_path, monkeypatch):
    """C61's test: a `finding` keeps one second try: two failing texts, then the fixed rendering;
    the passing third is never asked for."""
    env = talk_env(tmp_path, monkeypatch)
    bad = "I counted {r1.count}. Most of them were group Gamma."
    reply = env.ask(Q_COUNT, Step(count(A_ID, year(2025))), Step(finish("finding", bad)),
                    Step(finish("finding", bad)), Step(finish("finding", "I counted {r1.count}.")))
    assert len(env.model.calls) == 3, "a third try of a finding was asked for"
    assert (reply.status, reply.reply_style) == ("ANSWERED", "fallback"), reply.text


@pytest.mark.parametrize("steps, calls", [(2, 2), (3, 3)])
def test_c8_t3s_step_condition(tmp_path, monkeypatch, steps, calls):
    """Point 8 "on T3's conditions": with MOCO_MAX_STEPS=2 no step is left after the second
    failure (two calls, the fallback); with 3 the third try comes."""
    env = talk_env(tmp_path, monkeypatch, MOCO_MAX_STEPS=str(steps))
    reply = env.ask("hello", Step(finish("talk", LABEL_TEXT)), Step(finish("talk", LABEL_TEXT)),
                    Step(finish("talk", PASSING)))
    assert len(env.model.calls) == calls
    assert reply.reply_style == ("fallback" if calls == 2 else "agent"), reply.text


@pytest.mark.parametrize("seconds, calls", [(42.5, 3), (43.0, 2)], ids=["5 s left", "4 s left"])
def test_c8_t3s_five_seconds(tmp_path, monkeypatch, seconds, calls):
    """Point 8 "five seconds left": each model call takes `seconds` of the turn's 90; at the second
    failure 5 seconds are left (the third try comes) or 4 (it does not)."""
    env = talk_env(tmp_path, monkeypatch)
    reply = env.ask("hello", Step(finish("talk", LABEL_TEXT)), Step(finish("talk", LABEL_TEXT)),
                    Step(finish("talk", PASSING)), seconds=seconds)
    assert len(env.model.calls) == calls, len(env.model.calls)
    assert reply.reply_style == ("agent" if calls == 3 else "fallback"), reply.text


def test_c8_synthetic_mode_keeps_one(tmp_path):
    """R23-C1: in SYNTHETIC mode a talk text keeps T3's one second try. Passes today; must still
    pass."""
    env = Env(tmp_path, MOCO_TALK="on")
    failing = "Ask me about ages 26 to 40, it is easy."
    reply = env.ask("hello", Step(finish("talk", failing)), Step(finish("talk", failing)),
                    Step(finish("talk", PASSING)))
    assert len(env.model.calls) == 2 and reply.reply_style == "fallback", reply.text


def test_own_c1_plain_text_read_as_talk_gets_the_third_try(tmp_path, monkeypatch):
    """Own (Part C), R23-C2: three plain texts that fail: two PROGRAM NOTEs (T13), then the
    fallback."""
    env = talk_env(tmp_path, monkeypatch)
    reply = env.ask("hello", Step(text=LABEL_TEXT), Step(text=LABEL_TEXT), Step(text=LABEL_TEXT),
                    Step(text=PASSING))
    assert len(env.model.calls) == 3, len(env.model.calls)
    notes = [m for m in env.model.calls[2]["messages"] if m.get("role") == "user"
             and str(m.get("content")).startswith("PROGRAM NOTE (not from the person).")]
    assert len(notes) == 2, notes
    assert reply.text == county_fallback_line(1), reply.text


def test_own_c2_about_data_keeps_one(tmp_path, monkeypatch):
    """Own (Part C), "other kinds keep one": an about_data text that fails twice ends the turn
    (9b's rendering of the fact it named); the passing third is never asked for."""
    env = talk_env(tmp_path, monkeypatch)
    bad = "I have 3 facts. {f1}."
    reply = env.ask(Q_ABOUT, Step(describe()), Step(finish("about_data", bad)),
                    Step(finish("about_data", bad)),
                    Step(finish("about_data", "Here is what I know. {f1}.")))
    assert len(env.model.calls) == 3, "a third try of an about_data text was asked for"
    assert (reply.status, reply.reply_style) == ("EXPLAINED", "fallback"), reply.text


# ==== point 9: the county fallback ==============================================================

@pytest.mark.parametrize("n", [1, 2, 3])
def test_c9_the_county_fallback_with_one_two_and_three_sources(tmp_path, monkeypatch, n):
    """Point 9: `I can't put that in words I can back up. ` and then county_can_ask's sentence
    (the full one per source for one and two sources; C57 point 1's short one for three)."""
    env = talk_env(tmp_path, monkeypatch, names=NAMES[:min(n, 2)])
    if n == 3:
        add_visits(env)
    reply = env.ask("hello", Step(finish("talk", LABEL_TEXT)))
    assert (reply.status, reply.reply_style) == ("TALKED", "fallback"), reply.text
    assert reply.text == county_fallback_line(n), reply.text


def test_c9_synthetic_mode_gets_c57s_line(tmp_path):
    """Point 9 "C57 point 6's text stays the stage 1 line", with the answer to round 21's
    question 1: in SYNTHETIC mode the fallback is config/talk_rules.json's line, C57's."""
    env = Env(tmp_path, MOCO_TALK="on")
    failing = "Ask me about ages 26 to 40, it is easy."
    reply = env.ask("hello", Step(finish("talk", failing)))
    assert (reply.status, reply.reply_style) == ("TALKED", "fallback"), reply.text
    assert reply.text == FALLBACK_LINE_C57, reply.text


# ==== point 9b (addition 5): a failed about text that named facts ================================

def about_facts(env):
    (answer,) = [a for a in env.answers() if "facts" in a]
    return [f["text"] for f in answer["facts"]]


def ask_about(env, text):
    """Talk off: one text; talk on: the same failing text twice (T3's second try)."""
    steps = [Step(describe()), Step(finish("about_data", text))]
    if env.settings.moco_talk == "on":
        steps.append(Step(finish("about_data", text)))
    return env.ask(Q_ABOUT, *steps)


def rendering(facts, picks):
    return "Here is what I know. " + " ".join(facts[n - 1] for n in picks)


@pytest.mark.parametrize("talk", TALK)
def test_c9b_the_facts_it_named_in_its_order(tmp_path, monkeypatch, talk):
    """Addition 5: a text naming {f3} and then {f1} that fails (WORD in a fact sentence): `Here is
    what I know.`, the two facts in that order, then the notices in full (the thread's first);
    style fallback, the failures on record."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk)
    reply = ask_about(env, "Here is what I know. {f3}. {f1} zqx.")
    facts = about_facts(env)
    assert (reply.status, reply.reply_kind, reply.reply_style) == \
        ("EXPLAINED", "about_data", "fallback"), reply.text
    assert reply.text == rendering(facts, [3, 1]) + "\n" + "\n".join(
        full_notices(env, ("arrests_like",))), reply.text
    assert "WORD" in reply.draft_failures, reply.draft_failures
    assert "WORD" in turn_json(reply, env.runs_dir)["draft_failures"]


@pytest.mark.parametrize("talk", TALK)
def test_c9b_at_most_four_each_once_in_its_order(tmp_path, monkeypatch, talk):
    """Addition 5 "at most four, in its order, each once": {f2} {f1} {f2} {f5} {f3} {f4} names
    f2, f1, f5 and f3.
    Changed by briefs/S3-R26-A-tests.md (C63): the text is a plain facts text, so it is not
    checked and the same four facts are sent with style agent (it was style fallback). 9b's
    rendering is kept alive with a text that is not plain, one word of its own ("zqx", in a second
    thread): it fails and gets the same four facts, style fallback, as before."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk)
    reply = ask_about(env, "{f2}. {f1}. {f2}. {f5}. {f3}. {f4}.")
    facts = about_facts(env)
    assert (reply.reply_style, list(reply.draft_failures)) == ("agent", []), reply.text
    assert reply.text.split("\n")[0] == rendering(facts, [2, 1, 5, 3]), reply.text
    steps = [Step(describe())] + [Step(finish("about_data", "{f2}. {f1}. {f2}. {f5}. {f3}. "
                                                            "{f4} zqx."))] * 2
    reply = env.ask(Q_ABOUT, *steps, thread_key=THREAD_2)
    assert reply.reply_style == "fallback" and reply.draft_failures, reply.text
    assert reply.text.split("\n")[0] == rendering(facts, [2, 1, 5, 3]), reply.text


@pytest.mark.parametrize("talk", TALK)
def test_c9b_the_notices_short_on_a_second_about_reply(tmp_path, monkeypatch, talk):
    """Addition 5, "then the notices as point 5 of C57 has them": after an about reply with them
    in full, the rendering ends with C57's one line."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk)
    first = env.ask(Q_ABOUT, Step(describe()),
                    Step(finish("about_data", "Here is what I know. {f1}.")))
    assert first.reply_style == "agent", first.text
    reply = ask_about(env, "Here is what I know. {f2} zqx.")
    assert reply.text == rendering(about_facts(env), [2]) + "\n" + NOTICES_SHOWN, reply.text


@pytest.mark.parametrize("talk", TALK)
def test_c9b_a_new_fact_named(tmp_path, monkeypatch, talk):
    """Addition 5 with Part A: a failed text that named a fact of about_agent.md (e) gives it."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk)
    env.ask(Q_ABOUT, Step(describe()), Step(finish("about_data", "Here is what I know. {f1}.")))
    facts = about_facts(env)
    n = facts.index(C61_ABOUT_FACTS[0]) + 1
    reply = ask_about(env, f"I have 3 facts. {{f{n}}}.")
    assert reply.text.split("\n")[0] == f"Here is what I know. {C61_ABOUT_FACTS[0]}", reply.text


@pytest.mark.parametrize("talk", TALK)
def test_c9b_no_fact_named_is_the_fixed_about_text(tmp_path, monkeypatch, talk):
    """Addition 5 "with no fact named it is the fixed about text as today": a failing text with no
    slot of a fact ({r1.count} is not one). Passes today; must still pass."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk)
    reply = ask_about(env, "Here is what I know: {r1.count}.")
    srcs = mod("sources").county_sources()
    copies = {sid: mod("sources").latest(sid, state_dir=env.state_dir) for sid in srcs}
    fixed = mod("replies").county_about_text(srcs, copies)
    assert reply.reply_style == "fallback" and reply.text.startswith(fixed + "\n"), reply.text
    assert "Here is what I know." not in reply.text


def test_c9b_facts_rendering(tmp_path, monkeypatch):
    """Addition 5's function: replies.facts_rendering(text, facts), the rendering of R23-C3 (the
    notices are the turn's)."""
    facts = ["SYNTHETIC first fixture fact.", "SYNTHETIC second fixture fact.",
             "SYNTHETIC third fixture fact."]
    render = mod("replies").facts_rendering
    assert render("Here is zqx. {f3}. {f1}. {f3}.", facts) == \
        "Here is what I know. SYNTHETIC third fixture fact. SYNTHETIC first fixture fact."
