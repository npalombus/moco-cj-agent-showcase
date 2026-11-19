"""Brief point 11: the Slack service, the paths that ignore, refuse, limit or fail (design
P1A, A13; design P1 section 11 where A13 says "as in P1").

process_event is called with a FakeSlack, a FakeAgent and a real Store in tmp_path (wrapped
in a SpyStore where what is stored matters). Every call injects a FakeTimer
(p1support.process); nothing fires. A thread is made "followed" by an answered turn through
the real agent (Env.answered), so each ignored event below would be handled but for the one
thing that is wrong with it.

Covered here: step 1 (ignore: nothing posted, stored or logged), step 2 (duplicates, by event
id and by `msg:<channel>:<ts>`), step 3 (authorize, with the new fixed line; a followed
message from someone not approved is ignored in silence), step 7 (the per-person limit, with
the new fixed line), step 10 (the error line) and the log line.

Accepted both ways:
- The per-person limit, "more than MOCO_USER_REQUESTS_PER_MINUTE in the last 60 seconds",
  can be read with or without the request being handled. With a limit of 2, the first two
  in a minute must be answered, the third may be answered or refused, and the fourth must be
  refused.
- A mention's copy as a message event (it holds `<@`) may be labelled `ignored` or
  `duplicate`; either way it is answered once.
- For an unauthorized mention or direct message the store may be asked seen_event (step 2
  comes first) and thread_has_turns (step 1); nothing else.
- The NOT_AUTHORIZED line for a top-level direct message may go to the top level
  (thread_ts None, step 4) or "in the thread" as in P1, at the message's own ts (step 3
  comes before step 4; kit-log/raw/P1A-A-notes.txt).
- A followed message from someone not approved comes after the duplicate check, so
  seen_event may be called for it; "nothing stored" is read as no turn and no request
  recorded (kit-log/raw/P1A-A-notes.txt).
- The traceback of step 10 may be in a record's exc_info or in its message.
- The log line's fields may be written `kind=finding` or with the value quoted.

Cannot check here: the log file itself (var/agent.log may not be touched); only Python's
logging, captured by pytest, is seen. If the build logged some other way, the log tests
would see nothing. Not demanded: that two errors get different references (only the shape).
Not tested, because A13 does not say: a followed message from an approved person in a
channel outside SLACK_ALLOWED_CHANNEL_IDS.
"""
import logging
import re

import pytest

from p1support import (AGENT_USER, CHANNEL, DM_CHANNEL, DM_KEY, ERROR_LINE, FAKE_SECRETS,
                       NOT_AUTHORIZED_LINE, OTHER_CHANNEL, OTHER_TEAM, ROOT_TS, STRANGER, TEAM,
                       THREAD_1, THREAD_2, USER, USER2, WAIT_LINE, Env, FakeAgent, FakeSlack,
                       SpyStore, assert_no_secret, channel_message, direct_message, fake_chart,
                       later, make_reply, make_settings, mention, open_store, process,
                       slack_settings)
from support import SUPPORTED

QUESTION = "Show the monthly arrest trend for 2024."
Q_S1 = SUPPORTED["S1"][0]
IN_THREAD_TS = "1762790500.000300"  # a message inside the thread whose root is ROOT_TS
OTHER_ROOT = THREAD_2.rsplit(":", 1)[1]  # a thread root in CHANNEL with no turns


# ---- local helpers ------------------------------------------------------------------

def setup(tmp_path, reply=None, *, error=None, **settings_values):
    """Settings, a store, a FakeAgent and a FakeSlack that share one ordered log."""
    log = []
    slack = FakeSlack(log)
    agent = FakeAgent(reply if reply is not None else make_reply("ANSWERED"), error=error,
                      log=log)
    return slack_settings(tmp_path, **settings_values), open_store(tmp_path), agent, slack


def followed_env(tmp_path, *thread_keys, **settings_values):
    """An Env (Slack settings) whose store has one answered turn, made through the real
    agent, in each of thread_keys."""
    env = Env(tmp_path, slack=True, **settings_values)
    for key in thread_keys:
        env.answered(Q_S1, (2025, "18_25"), thread_key=key)
    return env


def watch_logs(caplog, level):
    caplog.set_level(level)
    caplog.set_level(level, logger="moco_agent")
    caplog.clear()


def moco_records(caplog):
    return [r for r in caplog.records if r.name.startswith("moco_agent")]


def _without(event, key):
    event.pop(key)
    return event


# ---- ignored events (step 1) -----------------------------------------------------------

# Each would be handled in a store whose thread THREAD_1 has turns, but for one thing.
IGNORED = {
    "bot_id_on_a_mention": mention(f"<@{AGENT_USER}> {QUESTION}", bot_id="BTEST0001"),
    "bot_id_on_a_direct_message": direct_message(QUESTION, bot_id="BTEST0001"),
    "bot_id_in_a_followed_thread": channel_message(QUESTION, bot_id="BTEST0001"),
    "subtype_message_changed": direct_message(QUESTION, subtype="message_changed"),
    "subtype_bot_message": mention(f"<@{AGENT_USER}> {QUESTION}", subtype="bot_message"),
    "subtype_in_a_followed_thread": channel_message(QUESTION, subtype="thread_broadcast"),
    "no_user": _without(mention(f"<@{AGENT_USER}> {QUESTION}"), "user"),
    "user_is_none": mention(f"<@{AGENT_USER}> {QUESTION}", user=None),
    "no_user_in_a_followed_thread": _without(channel_message(QUESTION), "user"),
    "no_text": _without(mention(f"<@{AGENT_USER}> {QUESTION}"), "text"),
    "empty_text": mention(""),
    "empty_text_in_a_followed_thread": channel_message(""),
    "other_type": {"type": "reaction_added", "user": USER, "text": QUESTION,
                   "channel": CHANNEL, "ts": ROOT_TS},
    "message_without_channel_type": _without(direct_message(QUESTION), "channel_type"),
    "mpim_message": direct_message(QUESTION, channel_type="mpim"),
    "mpim_message_in_a_thread": direct_message(QUESTION, channel_type="mpim",
                                               ts=IN_THREAD_TS, thread_ts=ROOT_TS),
    "top_level_channel_message": channel_message(QUESTION, ts=ROOT_TS, thread_ts=None),
    "top_level_group_message": channel_message(QUESTION, ts=ROOT_TS, thread_ts=None,
                                               channel_type="group"),
    "channel_message_in_a_thread_with_no_turns": channel_message(QUESTION,
                                                                 thread_ts=OTHER_ROOT),
    "group_message_in_a_thread_with_no_turns": channel_message(
        QUESTION, thread_ts=OTHER_ROOT, channel_type="group"),
    "same_root_in_another_channel": channel_message(QUESTION, channel=OTHER_CHANNEL),
    "channel_message_mentioning_the_agent": channel_message(f"<@{AGENT_USER}> {QUESTION}"),
    "channel_message_mentioning_someone_else": channel_message(f"<@{USER2}> what do you think?"),
    "group_message_with_a_mention_at_the_end": channel_message(
        f"{QUESTION} <@{AGENT_USER}>", channel_type="group"),
}


@pytest.mark.parametrize("name", IGNORED)
def test_an_ignored_event_posts_stores_and_logs_nothing(name, tmp_path, caplog):
    """A13 step 1: post nothing, store nothing, log nothing; label `ignored`. The store
    may only be asked thread_has_turns (to tell a followed message); seen_event (step 2)
    would record the event, so it is not called."""
    env = followed_env(tmp_path, THREAD_1)
    watch_logs(caplog, logging.DEBUG)
    spy, slack, agent = SpyStore(env.store), FakeSlack(), FakeAgent(None)
    assert process(dict(IGNORED[name]), settings=env.settings, store=spy, agent=agent,
                   slack=slack) == "ignored"
    assert slack.log == []
    assert agent.calls == []
    assert set(spy.used) <= {"thread_has_turns"}, spy.used
    assert moco_records(caplog) == [], [r.getMessage() for r in moco_records(caplog)]


# ---- duplicates (step 2) ---------------------------------------------------------------

def test_the_same_event_delivered_twice_is_answered_once(tmp_path):
    """A13 step 2: store.seen_event(event_id) is true -> post nothing; label `duplicate`."""
    settings, store, agent, slack = setup(tmp_path)
    event = mention(f"<@{AGENT_USER}> {QUESTION}")
    assert process(event, settings=settings, store=store, agent=agent, slack=slack,
                   event_id="EvTEST000201") == "answered"
    log_after_first = list(slack.log)
    assert process(dict(event), settings=settings, store=store, agent=agent, slack=slack,
                   event_id="EvTEST000201", now=later(1)) == "duplicate"
    assert slack.log == log_after_first
    assert len(agent.calls) == 1


def test_a_seen_event_id_is_a_duplicate_even_for_another_message(tmp_path):
    """A13 step 2: the event id alone makes a duplicate."""
    settings, store, agent, slack = setup(tmp_path)
    assert process(mention(f"<@{AGENT_USER}> {QUESTION}"), settings=settings, store=store,
                   agent=agent, slack=slack, event_id="EvTEST000202") == "answered"
    log_after_first = list(slack.log)
    other = mention(f"<@{AGENT_USER}> {QUESTION}", ts="1762790111.000700")
    assert process(other, settings=settings, store=store, agent=agent, slack=slack,
                   event_id="EvTEST000202", now=later(1)) == "duplicate"
    assert slack.log == log_after_first
    assert len(agent.calls) == 1


def test_a_message_already_handled_is_a_duplicate(tmp_path):
    """A13 step 2: store.seen_event("msg:<channel>:<ts>") is true -> post nothing."""
    settings, store, agent, slack = setup(tmp_path)
    store.seen_event(f"msg:{CHANNEL}:{IN_THREAD_TS}")
    event = mention(f"<@{AGENT_USER}> {QUESTION}", ts=IN_THREAD_TS, thread_ts=ROOT_TS)
    assert process(event, settings=settings, store=store, agent=agent, slack=slack,
                   event_id="EvTEST000203") == "duplicate"
    assert slack.log == []


def test_a_followed_message_then_its_mention_copy_is_answered_once(tmp_path):
    """A13 step 2: the same message (same channel and ts) arriving as a followed message
    and then as a mention, with different event ids, is answered once; the second is a
    duplicate."""
    env = followed_env(tmp_path, THREAD_1)
    log = []
    slack, agent = FakeSlack(log), FakeAgent(make_reply("ANSWERED"), log=log)
    first = process(channel_message("and for 2024?", ts=IN_THREAD_TS), settings=env.settings,
                    store=env.store, agent=agent, slack=slack, event_id="EvTEST000211")
    second = process(mention(f"<@{AGENT_USER}> and for 2024?", ts=IN_THREAD_TS,
                             thread_ts=ROOT_TS),
                     settings=env.settings, store=env.store, agent=agent, slack=slack,
                     event_id="EvTEST000212", now=later(1))
    assert (first, second) == ("answered", "duplicate")
    assert len(agent.calls) == 1
    assert len(slack.posts) == 1


def test_a_mention_then_its_message_copy_is_answered_once(tmp_path):
    """A13 steps 1 and 2: the message-event copy of a mention holds `<@`, so it is ignored
    (or found a duplicate); either way the mention is answered once."""
    env = followed_env(tmp_path, THREAD_1)
    log = []
    slack, agent = FakeSlack(log), FakeAgent(make_reply("ANSWERED"), log=log)
    text = f"<@{AGENT_USER}> and for 2024?"
    first = process(mention(text, ts=IN_THREAD_TS, thread_ts=ROOT_TS), settings=env.settings,
                    store=env.store, agent=agent, slack=slack, event_id="EvTEST000221")
    second = process(channel_message(text, ts=IN_THREAD_TS), settings=env.settings,
                     store=env.store, agent=agent, slack=slack, event_id="EvTEST000222",
                     now=later(1))
    assert first == "answered"
    assert second in ("ignored", "duplicate")
    assert len(agent.calls) == 1
    assert len(slack.posts) == 1


# ---- authorization (step 3) ------------------------------------------------------------

# A top-level direct message's line may go to the top level or to its own ts (module
# docstring): both are accepted for it.
TOP_LEVEL_DM = (None, ROOT_TS)

UNAUTHORIZED = {
    # name: (event, team_id, settings overrides, thread_ts values the line may go to)
    "wrong_workspace": (mention(f"<@{AGENT_USER}> {QUESTION}"), OTHER_TEAM, {}, (ROOT_TS,)),
    "unapproved_person": (mention(f"<@{AGENT_USER}> {QUESTION}", user=STRANGER), TEAM, {},
                          (ROOT_TS,)),
    "channel_outside_the_list": (mention(f"<@{AGENT_USER}> {QUESTION}"), TEAM,
                                 {"SLACK_ALLOWED_CHANNEL_IDS": OTHER_CHANNEL}, (ROOT_TS,)),
    "direct_message_from_unapproved_person": (direct_message(QUESTION, user=STRANGER), TEAM,
                                              {}, TOP_LEVEL_DM),
    "direct_message_to_the_wrong_workspace": (direct_message(QUESTION), OTHER_TEAM, {},
                                              TOP_LEVEL_DM),
    "in_a_thread_from_unapproved_person": (
        mention(f"<@{AGENT_USER}> {QUESTION}", user=STRANGER, ts=IN_THREAD_TS,
                thread_ts=ROOT_TS), TEAM, {}, (ROOT_TS,)),
    "direct_message_in_a_thread_from_unapproved_person": (
        direct_message(QUESTION, user=STRANGER, ts=IN_THREAD_TS, thread_ts=ROOT_TS), TEAM, {},
        (ROOT_TS,)),
}


@pytest.mark.parametrize("name", UNAUTHORIZED)
def test_unauthorized_gets_one_fixed_line_where_the_reply_would_go(name, tmp_path):
    """A13 step 3, as P1: the one workspace, an approved person, an allowed channel (or a
    direct message). Otherwise ONE line, NOT_AUTHORIZED word for word, in the thread (for a
    top-level direct message, the top level or its own ts: module docstring), and nothing
    else: no agent call, no memory read or written."""
    event, team_id, overrides, allowed = UNAUTHORIZED[name]
    settings, store, agent, slack = setup(tmp_path, **overrides)
    spy = SpyStore(store)
    assert process(dict(event), settings=settings, store=spy, agent=agent, slack=slack,
                   team_id=team_id) == "unauthorized"
    assert len(slack.log) == 1, slack.log
    kind, channel, thread_ts, text = slack.log[0]
    assert (kind, channel, text) == ("post", event["channel"], NOT_AUTHORIZED_LINE)
    assert thread_ts in allowed, thread_ts
    assert agent.calls == []
    assert set(spy.used) <= {"seen_event", "thread_has_turns"}, f"memory was used: {spy.used}"


@pytest.mark.parametrize("settings_values", [
    {"SLACK_ALLOWED_TEAM_ID": ""},
    {"SLACK_ALLOWED_USER_IDS": ""},
], ids=["no_allowed_workspace", "no_approved_people"])
def test_with_nothing_approved_nobody_is_answered(settings_values, tmp_path):
    """A13 step 3, as P1: fail closed."""
    values = dict(FAKE_SECRETS, SLACK_ALLOWED_TEAM_ID=TEAM, SLACK_ALLOWED_USER_IDS=USER)
    values.update(settings_values)
    settings = make_settings(tmp_path, **values)
    slack, agent = FakeSlack(), FakeAgent(make_reply("ANSWERED"))
    assert process(mention(f"<@{AGENT_USER}> {QUESTION}"), settings=settings,
                   store=open_store(tmp_path), agent=agent, slack=slack) == "unauthorized"
    assert slack.log == [("post", CHANNEL, ROOT_TS, NOT_AUTHORIZED_LINE)]
    assert agent.calls == []


def test_an_unauthorized_reset_resets_nothing(tmp_path):
    """A13 step 3 comes before the commands of step 6."""
    env = followed_env(tmp_path, THREAD_1)
    slack, agent = FakeSlack(), FakeAgent(None)
    event = mention(f"<@{AGENT_USER}> reset", user=STRANGER, ts=IN_THREAD_TS,
                    thread_ts=ROOT_TS)
    assert process(event, settings=env.settings, store=env.store, agent=agent,
                   slack=slack) == "unauthorized"
    assert slack.log == [("post", CHANNEL, ROOT_TS, NOT_AUTHORIZED_LINE)]
    assert env.store.thread_has_turns(THREAD_1)


def test_a_channel_in_the_list_is_answered(tmp_path):
    """A13 step 3, as P1."""
    settings, store, agent, slack = setup(
        tmp_path, SLACK_ALLOWED_CHANNEL_IDS=f"{OTHER_CHANNEL},{CHANNEL}")
    assert process(mention(f"<@{AGENT_USER}> {QUESTION}"), settings=settings, store=store,
                   agent=agent, slack=slack) == "answered"
    assert len(agent.calls) == 1


def test_a_direct_message_from_an_approved_person_is_allowed_with_a_channel_list(tmp_path):
    """A13 step 3, as P1: a direct message is allowed whatever the channel list."""
    settings, store, agent, slack = setup(tmp_path, SLACK_ALLOWED_CHANNEL_IDS=OTHER_CHANNEL)
    assert process(direct_message(QUESTION), settings=settings, store=store, agent=agent,
                   slack=slack) == "answered"
    assert agent.calls == [(QUESTION, DM_KEY, USER)]


@pytest.mark.parametrize("channel_type", ["channel", "group"])
def test_a_followed_message_from_someone_not_approved_is_ignored_in_silence(
        channel_type, tmp_path, caplog):
    """A13 step 3: a followed message from someone not approved is ignored in silence;
    label `ignored`. Nothing posted or logged, no agent call, no turn and no request
    recorded (seen_event, step 2, may have run)."""
    env = followed_env(tmp_path, THREAD_1)
    turns_before = len(env.store.recent_turns(THREAD_1, 50))
    watch_logs(caplog, logging.DEBUG)
    spy, slack, agent = SpyStore(env.store), FakeSlack(), FakeAgent(make_reply("ANSWERED"))
    event = channel_message(QUESTION, user=STRANGER, channel_type=channel_type)
    assert process(event, settings=env.settings, store=spy, agent=agent,
                   slack=slack) == "ignored"
    assert slack.log == []
    assert agent.calls == []
    assert set(spy.used) <= {"thread_has_turns", "seen_event"}, spy.used
    assert moco_records(caplog) == [], [r.getMessage() for r in moco_records(caplog)]
    assert env.store.user_requests_since(STRANGER, later(-3600)) == 0
    assert len(env.store.recent_turns(THREAD_1, 50)) == turns_before


# ---- the per-person limit (step 7) ------------------------------------------------------

def test_over_the_per_person_limit_one_fixed_line_and_no_agent(tmp_path):
    """A13 step 7, as P1, with WAIT word for word (both readings: module docstring)."""
    settings, store, agent, slack = setup(tmp_path, MOCO_USER_REQUESTS_PER_MINUTE="2")

    def ask(i, seconds, user=USER):
        event = mention(f"<@{AGENT_USER}> {QUESTION}", user=user, ts=f"17627900{i:02d}.000100")
        return process(event, settings=settings, store=store, agent=agent, slack=slack,
                       event_id=f"EvTEST0003{i:02d}", now=later(seconds))

    assert ask(1, 0) == "answered"
    assert ask(2, 1) == "answered"
    assert ask(3, 2) in ("answered", "rate_limited")  # see the module docstring
    calls_before, posts_before = len(agent.calls), len(slack.posts)
    assert ask(4, 3) == "rate_limited"
    assert slack.posts[posts_before:] == [("post", CHANNEL, "1762790004.000100", WAIT_LINE)]
    assert len(agent.calls) == calls_before

    assert ask(5, 4, user=USER2) == "answered"  # another person is not limited
    assert ask(6, 70) == "answered"             # a minute later, room again


# ---- when the agent raises (step 10) -------------------------------------------------

@pytest.mark.parametrize("event, where", [
    (mention(f"<@{AGENT_USER}> {QUESTION}", ts=IN_THREAD_TS, thread_ts=ROOT_TS),
     (CHANNEL, ROOT_TS)),
    (direct_message(QUESTION), (DM_CHANNEL, None)),
], ids=["mention_in_a_thread", "top_level_direct_message"])
def test_an_agent_that_raises_gets_one_error_line_with_a_reference(event, where, tmp_path,
                                                                    caplog):
    """A13 step 10, as P1 with the new wording: ONE line, `... (ref <8 characters>)`,
    where the reply would go; never a traceback or the error's text. The traceback goes
    to the log."""
    watch_logs(caplog, logging.DEBUG)
    error = RuntimeError("boom: zebra-quartz internal detail")
    settings, store, agent, slack = setup(tmp_path, error=error)
    assert process(dict(event), settings=settings, store=store, agent=agent,
                   slack=slack) == "error"
    assert len(agent.calls) == 1
    assert slack.uploads == []
    assert len(slack.posts) == 1, slack.posts
    _, channel, thread_ts, text = slack.posts[0]
    assert (channel, thread_ts) == where
    assert ERROR_LINE.fullmatch(text), text
    for leak in ("Traceback", "RuntimeError", "zebra-quartz", "boom", 'File "'):
        assert leak not in text, f"{leak!r} was posted"
    assert any(r.exc_info or "Traceback" in r.getMessage() for r in moco_records(caplog)), \
        "no traceback in the log"


# ---- the log line --------------------------------------------------------------------

@pytest.mark.parametrize("kind, style, steps, failures", [
    ("finding", "fallback", 3, ["NUMBER", "CLAIM"]),
    ("about_data", "agent", 2, []),
], ids=["finding_fallback", "about_agent"])
def test_the_log_line_adds_kind_style_steps_and_the_failure_codes(kind, style, steps,
                                                                  failures, tmp_path, caplog):
    """A13: the log line adds kind=, style=, steps= and the reply's failure codes."""
    watch_logs(caplog, logging.INFO)
    reply = make_reply("ANSWERED" if kind == "finding" else "EXPLAINED", reply_kind=kind,
                       reply_style=style, steps=steps, draft_failures=failures)
    settings, store, agent, slack = setup(tmp_path, reply)
    process(mention(f"<@{AGENT_USER}> {QUESTION}"), settings=settings, store=store,
            agent=agent, slack=slack, event_id="EvTEST000401")
    lines = [r.getMessage() for r in moco_records(caplog)]
    wanted = [rf"\bkind=\W?{kind}\b", rf"\bstyle=\W?{style}\b", rf"\bsteps=\W?{steps}\b",
              *[rf"\b{code}\b" for code in failures]]
    assert any(all(re.search(p, line) for p in wanted) for line in lines), lines


def test_the_log_holds_no_text_and_no_secret(tmp_path, caplog):
    """A13: still no text in the log line: never the question or the reply, on any path
    (answered, quiet, a failed upload, the agent raising, unauthorized); and never a
    secret (A0)."""
    env = followed_env(tmp_path, THREAD_1)
    watch_logs(caplog, logging.DEBUG)
    questions = ["How many arrests in 2025 for the quokka-lantern group?",
                 "thanks, quokka-lantern is fine",
                 "Monthly arrests for the quokka-lantern chart?",
                 "Count quokka-lantern again, please?",
                 "Is quokka-lantern allowed?"]
    reply_text = "Here is the otter-velvet reply. (SYNTHETIC test data, not real county figures.)"
    answered = make_reply("ANSWERED", text=reply_text)
    quiet = make_reply("UNSUPPORTED", reason_code="UNRECOGNIZED_QUESTION", text=reply_text)
    charted = make_reply("ANSWERED", text=reply_text, chart_path=fake_chart(tmp_path),
                         chart_title="otter-velvet chart (SYNTHETIC test data)")
    runs = [
        (mention(f"<@{AGENT_USER}> {questions[0]}", ts="1762790101.000100"),
         FakeAgent(answered), FakeSlack()),
        (channel_message(questions[1], ts="1762790102.000100"), FakeAgent(quiet),
         FakeSlack()),
        (mention(f"<@{AGENT_USER}> {questions[2]}", ts="1762790103.000100"),
         FakeAgent(charted), FakeSlack(upload_error=RuntimeError("upload refused"))),
        (mention(f"<@{AGENT_USER}> {questions[3]}", ts="1762790104.000100"),
         FakeAgent(error=RuntimeError("boom")), FakeSlack()),
        (mention(f"<@{AGENT_USER}> {questions[4]}", user=STRANGER, ts="1762790105.000100"),
         FakeAgent(answered), FakeSlack()),
    ]
    for i, (event, agent, slack) in enumerate(runs):
        process(event, settings=env.settings, store=env.store, agent=agent, slack=slack,
                event_id=f"EvTEST00050{i}", now=later(i))
    logged = caplog.text + "".join(str(r.args) for r in caplog.records)
    assert_no_secret(logged)
    for question in questions:
        assert question not in logged, "a question is in the log"
    assert "quokka-lantern" not in logged, "question text is in the log"
    assert "otter-velvet" not in logged, "reply text is in the log"
