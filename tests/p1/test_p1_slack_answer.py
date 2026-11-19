"""Brief point 11: the Slack service, the paths that answer (design P1A, A13; design P1
section 11 where A13 says "as in P1").

process_event is called with a FakeSlack, a FakeAgent (or, end to end, the real
handle_question with a FakeModel through p1support.real_agent) and a real Store in tmp_path.
Every call injects a FakeTimer (p1support.process), so no real timer starts and nothing
fires unless a test fires it. Slack itself is never reached. A thread is made "followed" by
an answered turn through the real agent (Env.answered).

Covered here: where a mention, a direct message (top level and in a thread) and a followed
message are answered, with which thread key and memory_minutes (A13 steps 1 and 4);
cleaning the text (step 5); help and reset, word for word (step 6); the late "One moment."
(step 8); posting once, `quiet`, the chart upload and its failure, and the label of each
status (step 9); and one run through the real agent. The ignored, duplicate, unauthorized,
limited and failing paths are in test_p1_slack_refuse.py.

Accepted both ways (A13 does not say):
- memory_minutes None may be passed to the agent or left out.
- The timer may be cancelled or not once the agent has answered: only what is posted is
  checked (a timer fired after process_event returned posts nothing).
- When the upload raises, the log record may be at WARNING or above, or one that names the
  upload (kit-log/raw/P1A-A-notes.txt).

Reading taken (kit-log/raw/P1A-A-notes.txt): when the upload raises and the text is posted
instead, the label is the reply's status, `answered` (step 9 handles the failure, so
step 10 is not reached).

Cannot check here: the default start_timer (threading.Timer); whether Slack delivers the
new message events (A13's Slack app settings are Nino's); the log file itself.
Not tested, because A13 does not say: a timer that fires while the agent works on a
followed message whose reply then turns out `quiet`.
"""
import logging
import re
from pathlib import Path

import pytest

from p1support import (USER2, AGENT_USER, CHANNEL, DM_CHANNEL, DM_KEY, HELP_LINE, ONE_COUNT_TEXT, ONE_MOMENT, RESET_LINE, ROOT_TS, STRANGER, TEAM,
                       THREAD_1, THREAD_2, USER, USER2, WAIT_LINE, Env, FakeAgent, FakeModel,
                       FakeSlack,
                       FakeTimer, Step, assert_answered, channel_message, chart_title, count,
                       direct_message, fake_chart, finish, has_number, one_count_line,
                       kept_note, later, make_reply, mention, open_store, process,
                       real_agent, slack_settings)
from support import PNG_SIGNATURE, SUPPORTED, expected_values

QUESTION = "Show the monthly arrest trend for 2024."
Q_S1 = SUPPORTED["S1"][0]
IN_THREAD_TS = "1762790500.000300"  # a message inside the thread whose root is ROOT_TS
DM_THREAD_KEY = f"{TEAM}:{DM_CHANNEL}:{ROOT_TS}"


# ---- local helpers ------------------------------------------------------------------

def setup(tmp_path, reply=None, *, during=None, upload_error=None, **settings_values):
    """Settings, a store, a FakeAgent and a FakeSlack that share one ordered log."""
    log = []
    slack = FakeSlack(log, upload_error=upload_error)
    agent = FakeAgent(reply if reply is not None else make_reply("ANSWERED"), log=log,
                      during=during)
    return slack_settings(tmp_path, **settings_values), open_store(tmp_path), agent, slack


def followed_env(tmp_path, *thread_keys, **settings_values):
    """An Env (Slack settings) whose store has one answered turn, made through the real
    agent, in each of thread_keys."""
    env = Env(tmp_path, slack=True, **settings_values)
    for key in thread_keys:
        env.answered(Q_S1, (2025, "18_25"), thread_key=key)
    return env


def chart_reply(tmp_path):
    return make_reply("ANSWERED", chart_path=fake_chart(tmp_path),
                      chart_title=chart_title(2025, "18_25"), run_ids=["run-test-0001"])


def final_entry(reply, channel, thread_ts):
    """A13 step 9: what the one post of a reply looks like in FakeSlack's log."""
    if reply.chart_path:
        return ("upload", channel, thread_ts, str(reply.chart_path), reply.chart_title,
                reply.text)
    return ("post", channel, thread_ts, reply.text)


def fire_all(timer):
    for handle in list(timer.handles):
        handle.fire()


# name: (event maker, channel posted to, thread_ts posted to, thread key)
WHERE = {
    "mention_in_a_thread": (
        lambda: mention(f"<@{AGENT_USER}> {QUESTION}", ts=IN_THREAD_TS, thread_ts=ROOT_TS),
        CHANNEL, ROOT_TS, THREAD_1),
    "top_level_direct_message": (lambda: direct_message(QUESTION), DM_CHANNEL, None, DM_KEY),
}


# ---- where each kind of message is answered (A13 steps 1 and 4) ----------------------

@pytest.mark.parametrize("ts, thread_ts, root", [
    (ROOT_TS, None, ROOT_TS),
    ("1762790777.000400", None, "1762790777.000400"),
    (IN_THREAD_TS, ROOT_TS, ROOT_TS),
], ids=["top_level", "top_level_other_ts", "in_a_thread"])
def test_a_mention_is_answered_once_in_its_thread(ts, thread_ts, root, tmp_path):
    """A13 step 4: the root is thread_ts when present, else ts; the key is
    <team>:<channel>:<root>; posts go to that thread; no time limit on memory. Step 9: one
    post_message with reply.text."""
    reply = make_reply("ANSWERED")
    settings, store, agent, slack = setup(tmp_path, reply)
    event = mention(f"<@{AGENT_USER}> {QUESTION}", ts=ts, thread_ts=thread_ts)
    assert process(event, settings=settings, store=store, agent=agent,
                   slack=slack) == "answered"
    assert agent.calls == [(QUESTION, f"{TEAM}:{CHANNEL}:{root}", USER)]
    assert agent.memory_minutes == [None]
    assert slack.posts == [("post", CHANNEL, root, reply.text)]
    assert slack.uploads == []


@pytest.mark.parametrize("text", [
    f"<@{AGENT_USER}> {QUESTION}",
    f"<@{AGENT_USER}>    {QUESTION}   ",
    f"<@{AGENT_USER}|agent> {QUESTION}",
    f"<@{AGENT_USER}> <@UTEST0002> {QUESTION}",
    f"{QUESTION} <@{AGENT_USER}>",
], ids=["leading", "spaces", "with_label", "two_mentions", "trailing"])
def test_every_mention_is_removed_and_the_text_trimmed(text, tmp_path):
    """A13 step 5, as P1 section 11 step 5: remove every <@...> and trim."""
    settings, store, agent, slack = setup(tmp_path)
    process(mention(text), settings=settings, store=store, agent=agent, slack=slack)
    assert agent.calls == [(QUESTION, THREAD_1, USER)]


@pytest.mark.parametrize("value, minutes", [(None, 60), ("15", 15)], ids=["default", "set"])
def test_a_top_level_direct_message_is_answered_at_the_top_level(value, minutes, tmp_path):
    """A13 step 4: a top-level direct message has the key <team>:<channel>:dm, its posts go
    to the top level (thread_ts None), and the agent gets memory_minutes =
    MOCO_DM_MEMORY_MINUTES (A14: default 60)."""
    reply = make_reply("ANSWERED")
    extra = {} if value is None else {"MOCO_DM_MEMORY_MINUTES": value}
    settings, store, agent, slack = setup(tmp_path, reply, **extra)
    event = direct_message(f"  {QUESTION} ", ts="1762790888.000500")
    assert process(event, settings=settings, store=store, agent=agent,
                   slack=slack) == "answered"
    assert agent.calls == [(QUESTION, DM_KEY, USER)]
    assert agent.memory_minutes == [minutes]
    assert slack.posts == [("post", DM_CHANNEL, None, reply.text)]
    assert slack.uploads == []


def test_a_direct_message_in_a_thread_is_answered_in_that_thread(tmp_path):
    """A13 step 4: a direct message with a thread_ts is keyed and answered like a channel
    thread, with no time limit on memory (memory_minutes None)."""
    reply = make_reply("ANSWERED")
    settings, store, agent, slack = setup(tmp_path, reply, MOCO_DM_MEMORY_MINUTES="15")
    event = direct_message(QUESTION, ts=IN_THREAD_TS, thread_ts=ROOT_TS)
    assert process(event, settings=settings, store=store, agent=agent,
                   slack=slack) == "answered"
    assert agent.calls == [(QUESTION, DM_THREAD_KEY, USER)]
    assert agent.memory_minutes == [None]
    assert slack.posts == [("post", DM_CHANNEL, ROOT_TS, reply.text)]


@pytest.mark.parametrize("text", [f"<@{AGENT_USER}> {QUESTION}", f"{QUESTION} <@{USER2}>"],
                         ids=["agent", "someone_else"])
def test_a_direct_message_holding_a_mention_is_handled(text, tmp_path):
    """A13 step 1: the "no <@" rule is for a followed message only; a direct message holding
    a mention is handled, and step 5 removes the mention."""
    settings, store, agent, slack = setup(tmp_path)
    assert process(direct_message(text), settings=settings, store=store, agent=agent,
                   slack=slack) == "answered"
    assert agent.calls == [(QUESTION, DM_KEY, USER)]
    assert slack.posts == [("post", DM_CHANNEL, None, agent.reply.text)]


@pytest.mark.parametrize("channel_type", ["channel", "group"])
def test_a_followed_message_is_handled_without_a_mention(channel_type, tmp_path):
    """A13 step 1, followed: a channel or group message in a thread the agent already has
    turns for, with no <@, is handled; step 4: in that thread, no time limit on memory."""
    env = followed_env(tmp_path, THREAD_1)
    reply = make_reply("ANSWERED")
    slack, agent = FakeSlack(), FakeAgent(reply)
    event = channel_message("  and what about 2024?  ", channel_type=channel_type)
    assert process(event, settings=env.settings, store=env.store, agent=agent,
                   slack=slack) == "answered"
    assert agent.calls == [("and what about 2024?", THREAD_1, USER)]
    assert agent.memory_minutes == [None]
    assert slack.log == [("post", CHANNEL, ROOT_TS, reply.text)]


# ---- posting once and the labels (A13 step 9) ----------------------------------------

@pytest.mark.parametrize("status, reason_code, label", [
    ("ANSWERED", None, "answered"),
    ("EXPLAINED", None, "explained"),
    ("DETAILS", None, "details"),
    ("UNSUPPORTED", "UNSUPPORTED_FIELD", "refused"),
    ("UNSUPPORTED", "NO_PREVIOUS_ANSWER", "refused"),
    ("NEEDS_INPUT", "NEEDS_CLARIFICATION", "needs_input"),
    ("ERROR", "MODEL_UNAVAILABLE", "error"),
], ids=["answered", "explained", "details", "refused_field", "refused_no_previous",
        "needs_input", "error_reply"])
def test_each_reply_is_one_post_and_its_label(status, reason_code, label, tmp_path):
    """A13: the labels; step 9: a reply without chart_path is exactly one post_message
    with reply.text (an ERROR reply's own text too, not the error line of step 10)."""
    reply = make_reply(status, reason_code=reason_code)
    settings, store, agent, slack = setup(tmp_path, reply)
    assert process(mention(f"<@{AGENT_USER}> {QUESTION}"), settings=settings, store=store,
                   agent=agent, slack=slack) == label
    assert slack.posts == [("post", CHANNEL, ROOT_TS, reply.text)]
    assert slack.uploads == []


UNRECOGNIZED = {"status": "UNSUPPORTED", "reason_code": "UNRECOGNIZED_QUESTION"}
CHATTER_TEXT = "thanks, that is interesting"


@pytest.mark.parametrize("channel_type", ["channel", "group"])
def test_chatter_in_a_followed_thread_posts_nothing(channel_type, tmp_path):
    """A13 step 9: a followed message whose reply is UNSUPPORTED / UNRECOGNIZED_QUESTION
    posts nothing; label `quiet`. The agent did run. C37 (planning chat, 14 Nov, S3-R6-A
    question 1): silent only when other people share the thread, so the thread holds a turn of
    a second person too."""
    env = followed_env(tmp_path, THREAD_1)
    env.answered(Q_S1, (2025, "18_25"), thread_key=THREAD_1, user_id=USER2)
    slack, agent = FakeSlack(), FakeAgent(make_reply(**UNRECOGNIZED))
    event = channel_message(CHATTER_TEXT, channel_type=channel_type)
    assert process(event, settings=env.settings, store=env.store, agent=agent,
                   slack=slack) == "quiet"
    assert agent.calls == [(CHATTER_TEXT, THREAD_1, USER)]
    assert slack.log == []


@pytest.mark.parametrize("name", ["mention_in_the_thread", "top_level_direct_message"])
def test_the_same_chatter_to_a_mention_or_a_direct_message_is_posted(name, tmp_path):
    """A13 step 9: `quiet` is only for a followed message. The same reply to a mention or a
    direct message is posted; label `refused`."""
    env = followed_env(tmp_path, THREAD_1)
    reply = make_reply(**UNRECOGNIZED)
    slack, agent = FakeSlack(), FakeAgent(reply)
    event, where = {
        "mention_in_the_thread": (mention(f"<@{AGENT_USER}> {CHATTER_TEXT}", ts=IN_THREAD_TS,
                                          thread_ts=ROOT_TS), (CHANNEL, ROOT_TS)),
        "top_level_direct_message": (direct_message(CHATTER_TEXT), (DM_CHANNEL, None)),
    }[name]
    assert process(event, settings=env.settings, store=env.store, agent=agent,
                   slack=slack) == "refused"
    assert slack.log == [("post", *where, reply.text)]


@pytest.mark.parametrize("code", ["UNSUPPORTED_FIELD", "OUT_OF_COVERAGE"])
def test_a_followed_message_refused_for_another_reason_is_posted(code, tmp_path):
    """A13 step 9: only UNSUPPORTED / UNRECOGNIZED_QUESTION is quiet; any other refusal of a
    followed message is posted in the thread; label `refused`."""
    env = followed_env(tmp_path, THREAD_1)
    reply = make_reply("UNSUPPORTED", reason_code=code)
    slack, agent = FakeSlack(), FakeAgent(reply)
    assert process(channel_message("how many by race?"), settings=env.settings,
                   store=env.store, agent=agent, slack=slack) == "refused"
    assert slack.log == [("post", CHANNEL, ROOT_TS, reply.text)]


@pytest.mark.parametrize("where", WHERE)
def test_a_reply_with_a_chart_is_one_upload_carrying_the_text(where, tmp_path):
    """A13 step 9: a reply with chart_path gives exactly one upload_file(channel,
    thread_ts, path, title=reply.chart_title, comment=reply.text) and no post_message."""
    make_event, channel, thread_ts, _ = WHERE[where]
    reply = chart_reply(tmp_path)
    settings, store, agent, slack = setup(tmp_path, reply)
    assert process(make_event(), settings=settings, store=store, agent=agent,
                   slack=slack) == "answered"
    assert slack.posts == []
    assert slack.uploads == [("upload", channel, thread_ts, str(reply.chart_path),
                              reply.chart_title, reply.text)]


def test_when_the_upload_fails_the_text_is_posted_and_logged(tmp_path, caplog):
    """A13 step 9: if the upload raises, the text is posted with post_message and the
    failure is written to the log (accepted: a record at WARNING or above, or one naming
    the upload). Nothing of the error is posted."""
    caplog.set_level(logging.DEBUG)
    caplog.set_level(logging.DEBUG, logger="moco_agent")
    reply = chart_reply(tmp_path)
    settings, store, agent, slack = setup(
        tmp_path, reply, upload_error=RuntimeError("upload refused: zebra-quartz"))
    event = mention(f"<@{AGENT_USER}> {QUESTION}", ts=IN_THREAD_TS, thread_ts=ROOT_TS)
    assert process(event, settings=settings, store=store, agent=agent,
                   slack=slack) == "answered"
    upload = ("upload", CHANNEL, ROOT_TS, str(reply.chart_path), reply.chart_title, reply.text)
    assert slack.uploads == [upload]
    assert slack.posts == [("post", CHANNEL, ROOT_TS, reply.text)]
    assert slack.log.index(upload) < slack.log.index(slack.posts[0])
    records = [r for r in caplog.records if r.name.startswith("moco_agent")]
    assert any(r.levelno >= logging.WARNING or "upload" in r.getMessage().lower()
               for r in records), [r.getMessage() for r in records]


# ---- commands (A13 step 6) ------------------------------------------------------------

# name: (event maker, channel, thread_ts). Ids never differ only by letter case (this
# Mac's disk treats such folder names as one).
HELP_EVENTS = {
    "lower": (lambda: mention(f"<@{AGENT_USER}> help"), CHANNEL, ROOT_TS),
    "upper": (lambda: mention(f"<@{AGENT_USER}> HELP"), CHANNEL, ROOT_TS),
    "mixed_with_spaces": (lambda: mention(f"<@{AGENT_USER}>  Help  "), CHANNEL, ROOT_TS),
    "in_a_thread": (lambda: mention(f"<@{AGENT_USER}> help", ts=IN_THREAD_TS,
                                    thread_ts=ROOT_TS), CHANNEL, ROOT_TS),
    "top_level_direct_message": (lambda: direct_message("help"), DM_CHANNEL, None),
    "direct_message_in_a_thread": (lambda: direct_message("hElP", ts=IN_THREAD_TS,
                                                          thread_ts=ROOT_TS),
                                   DM_CHANNEL, ROOT_TS),
}


@pytest.mark.parametrize("name", HELP_EVENTS)
def test_help_posts_the_fixed_help_line_and_calls_no_agent(name, tmp_path):
    """A13 step 6: exactly `help` (any letter case) posts HELP word for word, where the
    reply would go (the top level for a top-level direct message), and calls no agent."""
    make_event, channel, thread_ts = HELP_EVENTS[name]
    settings, store, agent, slack = setup(tmp_path)
    assert process(make_event(), settings=settings, store=store, agent=agent,
                   slack=slack) == "help"
    assert agent.calls == []
    assert slack.log == [("post", channel, thread_ts, HELP_LINE)]


def test_more_than_help_goes_to_the_agent(tmp_path):
    """A13 step 6: only exactly `help` is the command."""
    settings, store, agent, slack = setup(tmp_path)
    assert process(mention(f"<@{AGENT_USER}> help please"), settings=settings, store=store,
                   agent=agent, slack=slack) == "answered"
    assert agent.calls == [("help please", THREAD_1, USER)]


def test_reset_clears_this_thread_only_and_calls_no_agent(tmp_path):
    """A13 step 6: exactly `reset` (any letter case) clears this key's turns
    (store.reset_thread), posts RESET_DONE word for word, and calls no agent."""
    env = followed_env(tmp_path, THREAD_1, THREAD_2)
    slack, agent = FakeSlack(), FakeAgent(None)
    event = mention(f"<@{AGENT_USER}> Reset", ts="1762790600.000600", thread_ts=ROOT_TS)
    assert process(event, settings=env.settings, store=env.store, agent=agent,
                   slack=slack) == "reset"
    assert agent.calls == []
    assert slack.log == [("post", CHANNEL, ROOT_TS, RESET_LINE)]
    assert not env.store.thread_has_turns(THREAD_1)
    assert env.store.thread_has_turns(THREAD_2)


def test_reset_as_a_followed_message_clears_the_thread(tmp_path):
    """A13 step 6 applies to every handled message, a followed one too: `reset` with no
    mention, in a thread the agent has turns for, clears it and calls no agent."""
    env = followed_env(tmp_path, THREAD_1)
    slack, agent = FakeSlack(), FakeAgent(None)
    assert process(channel_message("Reset"), settings=env.settings, store=env.store,
                   agent=agent, slack=slack) == "reset"
    assert agent.calls == []
    assert slack.log == [("post", CHANNEL, ROOT_TS, RESET_LINE)]
    assert not env.store.thread_has_turns(THREAD_1)


def test_reset_in_a_top_level_direct_message_clears_that_conversation_only(tmp_path):
    """A13 steps 4 and 6: a top-level direct message's key is <team>:<channel>:dm; reset
    clears that key only and posts at the top level."""
    env = followed_env(tmp_path, DM_KEY, DM_THREAD_KEY)
    slack, agent = FakeSlack(), FakeAgent(None)
    assert process(direct_message("RESET"), settings=env.settings, store=env.store,
                   agent=agent, slack=slack) == "reset"
    assert agent.calls == []
    assert slack.log == [("post", DM_CHANNEL, None, RESET_LINE)]
    assert not env.store.thread_has_turns(DM_KEY)
    assert env.store.thread_has_turns(DM_THREAD_KEY)


# ---- the late acknowledgement (A13 step 8) ----------------------------------------------

@pytest.mark.parametrize("value, seconds", [(None, 3), ("7", 7)], ids=["default", "set"])
def test_the_timer_gets_the_ack_seconds_and_a_function(value, seconds, tmp_path):
    """A13 step 8: start_timer(seconds, function) with MOCO_ACK_AFTER_SECONDS (A14:
    default 3)."""
    extra = {} if value is None else {"MOCO_ACK_AFTER_SECONDS": value}
    settings, store, agent, slack = setup(tmp_path, **extra)
    timer = FakeTimer()
    assert process(mention(f"<@{AGENT_USER}> {QUESTION}"), settings=settings, store=store,
                   agent=agent, slack=slack, start_timer=timer) == "answered"
    assert len(timer.handles) == 1
    assert timer.handles[0].seconds == seconds
    assert callable(timer.handles[0].function)


@pytest.mark.parametrize("chart", [False, True], ids=["text", "chart"])
@pytest.mark.parametrize("where", WHERE)
def test_one_moment_is_posted_once_before_the_reply_when_the_agent_is_slow(where, chart,
                                                                          tmp_path):
    """A13 step 8: when the timer fires while the agent works, `One moment.` is posted
    once, in the same place as the reply, and before it."""
    make_event, channel, thread_ts, key = WHERE[where]
    timer = FakeTimer()
    reply = chart_reply(tmp_path) if chart else make_reply("ANSWERED")
    settings, store, agent, slack = setup(tmp_path, reply, during=lambda: fire_all(timer))
    assert process(make_event(), settings=settings, store=store, agent=agent, slack=slack,
                   start_timer=timer) == "answered"
    assert slack.log == [("agent", QUESTION, key, USER),
                         ("post", channel, thread_ts, ONE_MOMENT),
                         final_entry(reply, channel, thread_ts)]


@pytest.mark.parametrize("where", WHERE)
def test_no_one_moment_when_the_agent_answers_in_time(where, tmp_path):
    """A13 step 8: the line is posted only if the agent has not answered in time; a timer
    that never fires posts nothing."""
    make_event, channel, thread_ts, key = WHERE[where]
    timer = FakeTimer()
    reply = make_reply("ANSWERED")
    settings, store, agent, slack = setup(tmp_path, reply)
    assert process(make_event(), settings=settings, store=store, agent=agent, slack=slack,
                   start_timer=timer) == "answered"
    assert slack.log == [("agent", QUESTION, key, USER), final_entry(reply, channel, thread_ts)]


@pytest.mark.parametrize("chart", [False, True], ids=["text", "chart"])
@pytest.mark.parametrize("where", WHERE)
def test_a_timer_that_fires_after_the_reply_posts_nothing(where, chart, tmp_path):
    """A13 step 8: never after the reply. A timer that fires once process_event has
    returned (a real one can fire at the moment it is cancelled) posts nothing more."""
    make_event, channel, thread_ts, key = WHERE[where]
    timer = FakeTimer()
    reply = chart_reply(tmp_path) if chart else make_reply("ANSWERED")
    settings, store, agent, slack = setup(tmp_path, reply)
    assert process(make_event(), settings=settings, store=store, agent=agent, slack=slack,
                   start_timer=timer) == "answered"
    fire_all(timer)
    assert slack.log == [("agent", QUESTION, key, USER), final_entry(reply, channel, thread_ts)]


@pytest.mark.parametrize("where", WHERE)
def test_with_the_ack_at_zero_one_moment_is_posted_at_once_before_the_agent(where, tmp_path):
    """A13 step 8: at 0 the line is posted at once, before the agent is called, and once
    (any timer started is fired while the agent works and again after the reply)."""
    make_event, channel, thread_ts, key = WHERE[where]
    timer = FakeTimer()
    reply = make_reply("ANSWERED")
    settings, store, agent, slack = setup(tmp_path, reply, during=lambda: fire_all(timer),
                                          MOCO_ACK_AFTER_SECONDS="0")
    assert process(make_event(), settings=settings, store=store, agent=agent, slack=slack,
                   start_timer=timer) == "answered"
    fire_all(timer)
    assert slack.log == [("post", channel, thread_ts, ONE_MOMENT),
                         ("agent", QUESTION, key, USER),
                         final_entry(reply, channel, thread_ts)]


NO_ACK = {
    "help": lambda: mention(f"<@{AGENT_USER}> help"),
    "reset": lambda: mention(f"<@{AGENT_USER}> reset"),
    "unauthorized": lambda: mention(f"<@{AGENT_USER}> {QUESTION}", user=STRANGER),
    "ignored": lambda: mention(f"<@{AGENT_USER}> {QUESTION}", bot_id="BTEST0001"),
}


@pytest.mark.parametrize("ack", [None, "0"], ids=["default", "zero"])
@pytest.mark.parametrize("label", NO_ACK)
def test_no_one_moment_for_commands_unauthorized_or_ignored_events(label, ack, tmp_path):
    """A13: step 8 comes after steps 1, 3 and 6, so help, reset, an unauthorized and an
    ignored event never get `One moment.`, whatever the setting and whatever fires."""
    extra = {} if ack is None else {"MOCO_ACK_AFTER_SECONDS": ack}
    settings, store, agent, slack = setup(tmp_path, **extra)
    timer = FakeTimer()
    assert process(NO_ACK[label](), settings=settings, store=store, agent=agent, slack=slack,
                   start_timer=timer) == label
    fire_all(timer)
    assert ONE_MOMENT not in [post[3] for post in slack.posts]
    assert agent.calls == []


def test_no_one_moment_when_rate_limited_with_the_ack_at_zero(tmp_path):
    """A13: step 8 comes after step 7, so a refused request gets WAIT only, even at 0."""
    settings, store, agent, slack = setup(tmp_path, MOCO_ACK_AFTER_SECONDS="0",
                                          MOCO_USER_REQUESTS_PER_MINUTE="1")
    # Two earlier requests against a limit of 1: refused under either reading of "more
    # than" (with or without this request counted).
    store.record_user_request(USER, later(-2))
    store.record_user_request(USER, later(-1))
    timer = FakeTimer()
    assert process(mention(f"<@{AGENT_USER}> {QUESTION}"), settings=settings, store=store,
                   agent=agent, slack=slack, start_timer=timer) == "rate_limited"
    fire_all(timer)
    assert slack.log == [("post", CHANNEL, ROOT_TS, WAIT_LINE)]


def test_no_one_moment_for_a_duplicate_with_the_ack_at_zero(tmp_path):
    """A13: step 8 comes after step 2, so a duplicate posts nothing, even at 0."""
    settings, store, agent, slack = setup(tmp_path, MOCO_ACK_AFTER_SECONDS="0")
    store.seen_event("EvTEST000001")  # the event id process() sends
    timer = FakeTimer()
    assert process(mention(f"<@{AGENT_USER}> {QUESTION}"), settings=settings, store=store,
                   agent=agent, slack=slack, event_id="EvTEST000001",
                   start_timer=timer) == "duplicate"
    fire_all(timer)
    assert slack.log == []


# ---- end to end with the real agent (A13 with A4, A7) ---------------------------------

def test_slack_to_the_real_agent_end_to_end(tmp_path):
    """A mention answered through the real handle_question with a FakeModel: one upload
    whose comment is the reply (ONE_COUNT_TEXT filled with R1's phrases from the truth
    file, line 2 for a first answer) and whose title is A4's chart title, and no post. Then
    a followed message in that thread, with no mention, answered for the kept year (A5,
    A7)."""
    env = Env(tmp_path, slack=True)
    agent, slack = real_agent(env), FakeSlack()

    year, group = 2025, "18_25"
    total = expected_values(year, group)["total"]
    env.model = FakeModel(Step(count(year, group)), Step(finish("finding", ONE_COUNT_TEXT)),
                          clock=env.clock)
    assert process(mention(f"<@{AGENT_USER}> {Q_S1}"), settings=env.settings,
                   store=env.store, agent=agent, slack=slack,
                   event_id="EvTEST000101") == "answered"
    assert slack.posts == []
    (upload,) = slack.uploads
    _, channel, thread_ts, path, title, comment = upload
    assert (channel, thread_ts) == (CHANNEL, ROOT_TS)
    assert title == chart_title(year, group)
    assert Path(path).read_bytes().startswith(PNG_SIGNATURE)
    assert has_number(total, comment), comment
    assert_answered(comment, re.escape(one_count_line(year, group)), first=True)

    total_2 = expected_values(year, "under_18")["total"]
    env.model = FakeModel(Step(count(None, "under_18")),
                          Step(finish("finding", ONE_COUNT_TEXT)), clock=env.clock)
    follow_up = channel_message("and for people under 18?", ts="1762790300.000200")
    assert process(follow_up, settings=env.settings, store=env.store, agent=agent,
                   slack=slack, event_id="EvTEST000102", now=later(20)) == "answered"
    assert slack.posts == []
    assert len(slack.uploads) == 2
    _, channel, thread_ts, path, title, comment = slack.uploads[1]
    assert (channel, thread_ts) == (CHANNEL, ROOT_TS)
    assert title == chart_title(year, "under_18")
    assert has_number(total_2, comment), comment
    assert_answered(comment, re.escape(one_count_line(year, "under_18")),
                    kept=kept_note(year), first=False)
