"""T0 (with `on`), T1 end to end, T4, T5 and "no figure through talk" of docs/T-DESIGN.md
(T7's fifth, sixth and seventh points).

What this file covers
- T0 with MOCO_TALK=on: the tools are today's (seven, or county mode's eight) and finish
  takes a fourth kind, `talk`; the prompt is config/agent_prompt_talk.md (SYNTHETIC) or
  config/agent_prompt_s3_talk.md with the sources listed after it as today (county).
- T1 end to end with the stand-in model, in both data modes: status TALKED, kind talk,
  style agent, the text sent exactly as written (no data tag, no second line, no kept note
  after an earlier answer), no chart, no run; a finish of any kind in a turn with results
  is a finding.
- T4: the talk turn is saved in its thread with the user's message and the text sent; it
  is shown to the model in the next turn of that thread, within the usual limit; it has no
  run; `details` and the filling of year, group, source, period and filters skip it (also
  when it comes between Python's question and the answer to it); it is not in the request
  log (the `requests` command's turns, A15); the Slack log line's label is `talked`.
- T5: a talk reply in Slack is one post and nothing else; a followed message is answered
  (not `quiet`); `help` and `reset` are unchanged.
- No figure reaches a reply through talk: digits, number words, months and labels (both
  modes), in a talk reply and in a talk sentence of a finding or an about_data text.

READINGS (kit-log/raw/T-A-notes.txt):
- "Skipped by the filling": the filling reads the thread as if the talk turn were not
  there, so the values Python asked about before it are still pending after it.
- "Not written to the request log": the store's refused turns (A15) do not hold it.
- T5's "never preceded or followed by another message": no message of Python's own
  around the reply (it is one post); the "One moment." line, which T5 keeps unchanged, is
  not tested here (when the agent is slow it comes before any reply).
- The reason code of a TALKED reply is not given by the contract and is not checked.
"""
import logging
import re
from datetime import timedelta

import pytest

from p1support import (AGENT_USER, CHANNEL, DETAILS_HEAD, DM_CHANNEL, HELP_LINE, MARK, NOW,
                       ONE_COUNT_TEXT, RESET_LINE, ROOT_TS, THREAD_1, TYPED, FakeModel,
                       FakeSlack, FakeTimer, Step, assert_answered, channel_message,
                       check_no_model_text, compare, count, decline, describe, direct_message,
                       finish, fixed_line1_re, has_leaf, mention, one_count_line, process,
                       prompt_version_pattern, real_agent, run_folders, single_sentence_facts,
                       system_text, thread_block)
from s3support import (AGENT_PROMPT_S3, COUNTY_TOOLS, FALLBACK_LINE_C57, Q_COUNT, SCHOOL,
                       county_fallback_line,
                       SYNTHETIC_TOOLS, CountyEnv, count as county_count, fallback_line_of, is_,
                       year)
from tsupport import (AGENT_PROMPT_S3_TALK, AGENT_PROMPT_TALK, HELLO_TEXT,
                      THANKS_TEXT, assert_talked, county_labels, county_talk_env, finish_kinds,
                      premise_talk, synthetic_labels, talk_env, talk_faults, talk_rules,
                      turn_json)

Q = "How many arrests were recorded each month in 2025 for ages 18 to 25?"
ALL_KINDS = {"finding", "about_data", "background", "talk"}


def hello(env, text=HELLO_TEXT, question="hello", **kw):
    return env.ask(question, Step(finish("talk", text)), **kw)


# ---- T0 with `on`: the tools and the prompt -----------------------------------------------------

def test_on_offers_talk_and_the_talk_prompt_in_synthetic_mode(tmp_path):
    """T0 and T1: the seven tools, finish with a fourth kind `talk`; the system message
    starts with config/agent_prompt_talk.md, and the turn record names that file."""
    env = talk_env(tmp_path)
    reply = hello(env)
    assert env.model.tools_offered(0) == SYNTHETIC_TOOLS
    assert set(finish_kinds(env.model.calls[0]["tools"])) == ALL_KINDS
    prompt = AGENT_PROMPT_TALK.read_text(encoding="utf-8").strip()
    assert system_text(env.model.calls[0]["messages"]).startswith(prompt)
    record = turn_json(reply, env.runs_dir)
    assert prompt_version_pattern(AGENT_PROMPT_TALK).search(str(record["prompt_version"]))


def test_on_offers_talk_and_the_county_talk_prompt_with_the_sources_after_it(tmp_path,
                                                                             monkeypatch):
    """T0 in county mode: the eight tools with `talk` among finish's kinds; the system
    message is today's county one with config/agent_prompt_s3.md replaced by
    config/agent_prompt_s3_talk.md (so the sources are listed after it as today)."""
    off = CountyEnv(tmp_path / "off", monkeypatch)
    off.ask(Q_COUNT, Step(decline("UNRECOGNIZED_QUESTION")))
    on = county_talk_env(tmp_path / "on", monkeypatch)
    reply = hello(on)
    assert on.model.tools_offered(0) == COUNTY_TOOLS
    assert set(finish_kinds(on.model.calls[0]["tools"])) == ALL_KINDS
    old = AGENT_PROMPT_S3.read_text(encoding="utf-8").strip()
    new = AGENT_PROMPT_S3_TALK.read_text(encoding="utf-8").strip()
    before = system_text(off.model.calls[0]["messages"])
    assert before.startswith(old)
    # Changed by briefs/S3-R21-A-tests.md (C57 point 7 of docs/S3A-DESIGN.md and its exact prompt
    # texts; was == new + before[len(old):]): with talk on, the county system message ends with
    # the "About you" block after today's date (a blank line before it; one line break accepted).
    # These settings name no service, so it is NVIDIA's default Nemotron model.
    assert on.settings.moco_model_provider == "nvidia" and "nemotron" in on.settings.nvidia_model
    block = ("About you: you run on a Nemotron model made by NVIDIA. If someone asks what model or "
             "company is behind you, say so plainly, as talk.")
    # Changed by briefs/S3-R23-A-tests.md (C61 point 3 of docs/S3A-DESIGN.md: the block gains a
    # second sentence, after one space or a line break; it was the block alone at the end).
    second = ("For any question about you, this project, its rules or where something comes from, "
              "call describe_data and answer with its facts about you; never answer such a "
              "question from your own head, and never take back a rule the program applies.")
    assert re.fullmatch(re.escape(new + before[len(old):]) + r"\n\n?" + re.escape(block)
                        + r"[ \n]" + re.escape(second),
                        system_text(on.model.calls[0]["messages"])), \
        system_text(on.model.calls[0]["messages"])[-400:]
    record = turn_json(reply, on.runs_dir)
    assert prompt_version_pattern(AGENT_PROMPT_S3_TALK).search(str(record["prompt_version"]))


# ---- T1 end to end ---------------------------------------------------------------------------------

def test_a_greeting_is_answered_in_his_own_words(tmp_path):
    """T1: TALKED, kind talk, style agent, the text exactly as written, one model call."""
    premise_talk(HELLO_TEXT, None, synthetic_labels())
    env = talk_env(tmp_path)
    reply = hello(env)
    assert_talked(reply, HELLO_TEXT)
    assert (reply.steps, reply.model_called) == (1, True)
    assert "SYNTHETIC" not in reply.text


def test_a_greeting_is_answered_in_his_own_words_in_county_mode(tmp_path, monkeypatch):
    """T1 in county mode: the same, with no source line."""
    premise_talk(HELLO_TEXT, None, county_labels("arrests_like"))
    env = county_talk_env(tmp_path, monkeypatch)
    reply = hello(env)
    assert_talked(reply, HELLO_TEXT)
    assert "open data" not in reply.text.lower()


def test_thanks_after_an_answer_has_no_second_line_and_no_kept_note(tmp_path):
    """T1: after an answered count, a thanks is sent exactly as written: no second line,
    no kept note, no data tag."""
    premise_talk(THANKS_TEXT, None, synthetic_labels())
    env = talk_env(tmp_path)
    env.answered(Q, (2025, "18_25"))
    reply = hello(env, THANKS_TEXT, question="thanks!")
    assert_talked(reply, THANKS_TEXT)


@pytest.mark.parametrize("kind", ["talk", "about_data", "background"])
def test_a_finish_of_any_kind_in_a_turn_with_results_is_a_finding(tmp_path, kind):
    """T1: in a turn that has results, a finish of any kind is a finding, as today."""
    env = talk_env(tmp_path, MOCO_BACKGROUND="on")
    assert env.settings.moco_talk == "on"
    reply = env.ask(Q, Step(count(2025, "18_25")), Step(finish(kind, ONE_COUNT_TEXT)))
    assert (reply.status, reply.reply_kind, reply.reply_style) == \
        ("ANSWERED", "finding", "agent"), (reply.status, reply.reply_kind, reply.text)
    assert_answered(reply.text, re.escape(one_count_line(2025, "18_25")), first=True)


# ---- T4: records, context, details, filling, the request log -------------------------------------

def test_a_talk_turn_is_saved_in_its_thread(tmp_path):
    """T4: saved in the thread like any other turn, with the user's message and the text he
    sent; it has no run."""
    env = talk_env(tmp_path)
    reply = hello(env)
    assert_talked(reply, HELLO_TEXT)
    (saved,) = env.store.recent_turns(THREAD_1, 10)
    assert (saved["question"], saved["status"]) == ("hello", "TALKED")
    assert has_leaf(saved, HELLO_TEXT), saved
    assert run_folders(env.runs_dir) == []


def test_the_next_turn_is_shown_the_talk_turn(tmp_path):
    """T4: the talk turn is shown to the model in later turns of that thread: the user's
    message and the text he sent."""
    env = talk_env(tmp_path)
    assert_talked(hello(env), HELLO_TEXT)
    env.ask(Q, Step(count(2025, "18_25")), Step(finish("finding", ONE_COUNT_TEXT)))
    block = thread_block(env.model.calls[0]["messages"])
    assert block is not None and '"hello"' in block and HELLO_TEXT in block, block


def test_talk_turns_are_shown_within_the_usual_limit(tmp_path):
    """T4: "within the usual limit": with MOCO_THREAD_TURNS_IN_CONTEXT=1 only the newest
    earlier turn is shown."""
    env = talk_env(tmp_path, MOCO_THREAD_TURNS_IN_CONTEXT=1)
    assert_talked(hello(env), HELLO_TEXT)
    assert_talked(hello(env, THANKS_TEXT, question="thanks"), THANKS_TEXT)
    hello(env, question="good morning")
    block = thread_block(env.model.calls[0]["messages"])
    assert block is not None and THANKS_TEXT in block and HELLO_TEXT not in block, block


def test_details_skips_a_talk_turn(tmp_path):
    """T4: `details` gives the details of the last answer, not of the talk turn after it."""
    env = talk_env(tmp_path)
    answered = env.answered(Q, (2025, "18_25"))
    assert_talked(hello(env, THANKS_TEXT, question="thanks"), THANKS_TEXT)
    reply = env.ask("details")
    assert reply.status == "DETAILS", (reply.status, reply.reason_code, reply.text)
    assert reply.text.startswith(DETAILS_HEAD)
    assert answered.run_ids[0] in reply.text


def test_filling_skips_a_talk_turn_after_an_answer(tmp_path):
    """T4: a follow-up after a talk turn keeps the age group of the answer before it."""
    env = talk_env(tmp_path)
    env.answered(Q, (2025, "18_25"))
    assert_talked(hello(env, THANKS_TEXT, question="thanks"), THANKS_TEXT)
    reply = env.ask("what about 2024?", Step(count(2024)), Step(finish("finding", ONE_COUNT_TEXT)))
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert reply.results[0]["age_group"] == "18_25" and reply.carried["age_group"] is True


def test_filling_skips_a_talk_turn_between_a_question_and_its_answer(tmp_path):
    """T4 (READING: the talk turn is skipped, so what Python asked about is still
    pending): Python asks which year for ages 18 to 25; the user says thanks; then "2025"
    is counted for ages 18 to 25."""
    env = talk_env(tmp_path)
    env.pending("How many arrests for ages 18 to 25?", age_group="18_25")
    assert_talked(hello(env, THANKS_TEXT, question="thanks"), THANKS_TEXT)
    reply = env.ask("2025", Step(count(2025)), Step(finish("finding", ONE_COUNT_TEXT)))
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert reply.results[0]["age_group"] == "18_25" and reply.carried["age_group"] is True


def test_county_filling_skips_a_talk_turn(tmp_path, monkeypatch):
    """T4 in county mode: the period and the filter of the last answer are kept across a
    talk turn."""
    env = county_talk_env(tmp_path, monkeypatch)
    first = env.ask(Q_COUNT, Step(county_count(period=year(2025), filters=[is_(SCHOOL, True)])),
                    Step(finish("finding", "I counted {r1.count}.")))
    assert first.status == "ANSWERED", first.text
    assert_talked(hello(env, THANKS_TEXT, question="thanks"), THANKS_TEXT)
    reply = env.ask("and again?", Step(county_count()), Step(finish("finding", "I counted {r1.count}.")))
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert reply.carried["period"] is True and reply.carried["filters"] is True, reply.carried
    assert reply.text.startswith("I counted 76 arrest records within 500 feet of a school in "
                                 "2025."), reply.text


def test_county_filling_skips_a_talk_turn_between_a_question_and_its_answer(tmp_path,
                                                                           monkeypatch):
    """T4 in county mode: Python asks for the period of a count near a school; a talk turn;
    then the period is given and the filter is still pending."""
    env = county_talk_env(tmp_path, monkeypatch)
    asked = env.ask("How many arrests near a school?",
                    Step(county_count(filters=[is_(SCHOOL, True)])))
    assert asked.status == "NEEDS_INPUT", asked.text
    assert_talked(hello(env, THANKS_TEXT, question="thanks"), THANKS_TEXT)
    reply = env.ask("2025", Step(county_count(period=year(2025))),
                    Step(finish("finding", "I counted {r1.count}.")))
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert reply.carried["filters"] is True, reply.carried
    assert reply.text.startswith("I counted 76 arrest records within 500 feet of a school in "
                                 "2025."), reply.text


def test_a_talk_turn_is_not_in_the_request_log(tmp_path):
    """T4: not written to the request log (the turns the `requests` command lists, A15). A
    declined question beside it is."""
    env = talk_env(tmp_path)
    assert_talked(hello(env), HELLO_TEXT)
    env.ask("How many arrests were there by race?", Step(decline("UNSUPPORTED_FIELD")))
    refused = env.store.refused_turns(30, now=NOW + timedelta(hours=1))
    assert [t["question"] for t in refused] == ["How many arrests were there by race?"]


# ---- T5: Slack -------------------------------------------------------------------------------------

@pytest.mark.parametrize("where", ["mention", "direct"])
def test_a_talk_reply_in_slack_is_one_post_and_nothing_else(tmp_path, where, caplog):
    """T5: a talk reply is one plain post, never preceded or followed by another message of
    his (the agent answers in time: the FakeTimer never fires); T4: the label is `talked`,
    and the log line holds neither the message nor the reply."""
    caplog.set_level(logging.INFO, logger="moco_agent")
    env = talk_env(tmp_path, slack=True)
    env.model = FakeModel(Step(finish("talk", HELLO_TEXT)), clock=env.clock)
    slack = FakeSlack()
    event = (mention(f"<@{AGENT_USER}> hello there") if where == "mention"
             else direct_message("hello there"))
    label = process(event, settings=env.settings, store=env.store, agent=real_agent(env),
                    slack=slack, start_timer=FakeTimer())
    assert label == "talked"
    channel, thread_ts = (CHANNEL, ROOT_TS) if where == "mention" else (DM_CHANNEL, None)
    assert slack.log == [("post", channel, thread_ts, HELLO_TEXT)]
    logged = [r.getMessage() for r in caplog.records if r.name.startswith("moco_agent")]
    assert any("talked" in line for line in logged), logged
    assert not any(HELLO_TEXT in line or "hello there" in line for line in logged), logged


def test_a_followed_message_gets_its_talk_reply(tmp_path):
    """T5 with A13: a thanks in a followed thread, with no mention, is answered with one
    post (it is not `quiet`)."""
    env = talk_env(tmp_path, slack=True)
    env.answered(Q, (2025, "18_25"))
    env.model = FakeModel(Step(finish("talk", THANKS_TEXT)), clock=env.clock)
    slack = FakeSlack()
    label = process(channel_message("thanks!"), settings=env.settings, store=env.store,
                    agent=real_agent(env), slack=slack)
    assert label == "talked"
    assert slack.log == [("post", CHANNEL, ROOT_TS, THANKS_TEXT)]


@pytest.mark.parametrize("word, line", [("help", HELP_LINE), ("reset", RESET_LINE)])
def test_help_and_reset_are_unchanged_with_talk_on(tmp_path, word, line):
    """T5: `help` and `reset` are unchanged: their fixed line, no model call."""
    env = talk_env(tmp_path, slack=True)
    assert env.settings.moco_talk == "on"
    env.model = FakeModel(Step(finish("talk", HELLO_TEXT)), clock=env.clock)
    slack = FakeSlack()
    label = process(mention(f"<@{AGENT_USER}> {word}"), settings=env.settings, store=env.store,
                    agent=real_agent(env), slack=slack)
    assert label == word
    assert slack.log == [("post", CHANNEL, ROOT_TS, line)]
    assert env.model.calls == []


# ---- no figure through talk ---------------------------------------------------------------------

FIGURES = [
    ("digits", f"I counted {TYPED} of them, {MARK}.", "synthetic"),
    ("number words", f"There were twelve hundred of them, {MARK}.", "synthetic"),
    ("months", f"Most of them came in March, {MARK}.", "synthetic"),
    ("labels", f"Ask me about ages 26 to 40, {MARK}.", "synthetic"),
    ("county labels", f"Most of them were group Gamma, {MARK}.", "county"),
]


@pytest.mark.parametrize("name, text, mode", FIGURES, ids=[f[0] for f in FIGURES])
def test_no_figure_reaches_a_talk_reply(tmp_path, monkeypatch, name, text, mode):
    """T7: a talk text that holds a digit, a number word, a month or a label fails twice
    and the fallback line is sent; nothing of the model's text reaches the reply."""
    labels = synthetic_labels() if mode == "synthetic" else county_labels("arrests_like")
    assert talk_faults(text, labels) & {"NUMBER", "LABEL"}, text
    env = talk_env(tmp_path) if mode == "synthetic" else county_talk_env(tmp_path, monkeypatch)
    reply = env.ask("hello", Step(finish("talk", text)), Step(finish("talk", text)))
    # Changed by briefs/S3-R21-A-tests.md (C57 point 6 of docs/S3A-DESIGN.md; was today's line in
    # both): the file's line is C57's; the reply is C57's line in county mode and today's or
    # C57's in SYNTHETIC mode (s3support.fallback_lines; a question in briefs/QUESTIONS.md).
    assert talk_rules()["fallback_line"] == FALLBACK_LINE_C57
    # Changed by briefs/S3-R23-A-tests.md (C61 point 9: in county mode the line is C61's; it was
    # fallback_line_of(reply.text, county=True), C57's line, in county mode).
    assert_talked(reply, county_fallback_line(1) if mode == "county"
                  else fallback_line_of(reply.text, county=False), style="fallback")
    check_no_model_text(reply.text)
    assert not re.search(r"\d", reply.text)
    for word in ("twelve", "hundred", "march", "26", "gamma"):
        assert word not in reply.text.lower()


@pytest.mark.parametrize("kind, before, text", [
    ("finding", (Step(count(2025, "18_25")),),
     f"I counted {{r1.count}}. That is {TYPED} more than March, {MARK}."),
    ("finding", (Step(count(2024, "under_18"), count(2025, "under_18")),
                 Step(compare("r1", "r2"))),
     f"Here is the comparison: {{r3.compare}}. Ages 26 to 40 had twelve hundred, {MARK}."),
    ("about_data", (Step(describe()),),
     f"Here is what I know about {TYPED} records in March, {MARK}. {{f{single_sentence_facts()[0]}}}."),
], ids=["finding-count", "finding-compare", "about_data"])
def test_no_figure_reaches_a_reply_through_a_talk_sentence(tmp_path, kind, before, text):
    """T7: a talk sentence with a figure in a finding or an about_data text fails twice and
    the turn falls back to Python's own text; the model's figure and words are not sent."""
    env = talk_env(tmp_path)
    reply = env.ask("Tell me about it.", *before, Step(finish(kind, text)),
                    Step(finish(kind, text)))
    assert reply.reply_style == "fallback", (reply.status, reply.reply_style, reply.text)
    assert len(env.model.calls) == len(before) + 2, "no second try was given"
    check_no_model_text(reply.text)
    if kind == "finding" and len(before) == 1:
        assert_answered(reply.text, fixed_line1_re([(2025, "18_25")]), first=True)
    assert "twelve hundred" not in reply.text.lower()

