"""C37 of docs/S3A-DESIGN.md (D-061): in Slack, silence after a decline only when other people
share the thread. Brief: briefs/S3-R6-A-tests.md. Tests only; the planning chat builds C37.

In `slack_app.process_event`, a `followed` message whose turn ends UNSUPPORTED with
UNRECOGNIZED_QUESTION stays silent only when the thread's saved turns (before this one) hold
more than one `user_id`. Otherwise the reply is posted as for any other turn.

Every test calls process_event (through p1support.process, with a FakeTimer) with a real Store
in tmp_path and a FakeSlack. The earlier turns of the thread are made through the real agent
(p1support.Env.answered), each with its own `user_id`. The followed message's turn is made by a
FakeAgent (the reply is given) or by the real agent with the model stand-in declining.

C37's three cases:
1. A followed thread whose turns are from one person: the decline is posted (one post, label
   `refused`). Also when that one person is someone else than the writer of the followed
   message, and when the real agent saves the new turn (which then makes two people).
2. A followed thread with turns from two people: silent, as today (label `quiet`, nothing posted,
   the agent did run).
3. A mention or a direct message: posted as today, with one or two people in the thread.

Readings (also in kit-log/raw/S3-R6-A-notes.txt):
- C37-1. "The thread's saved turns (before this one)" are the turns the store holds for the
  thread's key when the event arrives; the turn the agent saves for this message is not one of
  them. So a second person's first message in a one-person thread is posted (case 1, the real
  agent), and that person's next message there is silent.
- C37-2. "Posted as for any other turn": one post_message in the thread with the reply's text;
  the label is the reply's status label, `refused`.
- C37-3. The rule is the same in both data modes (C37 names none); the tests run in SYNTHETIC
  mode, the mode of tests/p1.
"""
import pytest

from p1support import (AGENT_USER, CHANNEL, DM_CHANNEL, ROOT_TS, THREAD_1, USER, USER2, Env,
                       FakeAgent, FakeModel, FakeSlack, Step, assert_fixed, channel_message,
                       decline, direct_message, later, make_reply, mention, process, real_agent)
from support import SUPPORTED

Q_S1 = SUPPORTED["S1"][0]
WEATHER = "whats the weather today?"  # Nino's Slack thread of 14 Nov 11:06 EST
IN_THREAD_TS = "1762790500.000300"
DECLINED = {"status": "UNSUPPORTED", "reason_code": "UNRECOGNIZED_QUESTION"}


def thread_of(tmp_path, *users):
    """A Slack Env whose thread THREAD_1 holds one answered turn per user, in order."""
    env = Env(tmp_path, slack=True)
    for user in users:
        env.answered(Q_S1, (2025, "18_25"), thread_key=THREAD_1, user_id=user)
    held = {t["user_id"] for t in env.store.recent_turns(THREAD_1, 50)}
    assert held == set(users), "premise: the thread's saved turns are by these people"
    return env


def followed(env, agent, user=USER, text=WEATHER, n=0):
    """A followed message in THREAD_1; `n` makes its ts and event id its own."""
    slack = FakeSlack()
    label = process(channel_message(text, user=user, ts=f"1762790600.00{n:04d}"),
                    settings=env.settings, store=env.store, agent=agent, slack=slack,
                    event_id=f"EvC37{n:07d}", now=later(60 * n))
    return label, slack


# ---- 1. one person in the thread: the decline is posted -------------------------------------

@pytest.mark.parametrize("earlier, writer", [
    ((USER,), USER),
    ((USER, USER), USER),
    ((USER2,), USER2),
], ids=["one turn of the writer", "two turns of the writer", "the other approved person"])
def test_one_person_in_the_thread_the_decline_is_posted(tmp_path, earlier, writer):
    env = thread_of(tmp_path, *earlier)
    reply = make_reply(**DECLINED, text="I couldn't read that as a question I can answer.")
    agent = FakeAgent(reply)
    label, slack = followed(env, agent, user=writer)
    assert agent.calls == [(WEATHER, THREAD_1, writer)]
    assert label == "refused"
    assert slack.log == [("post", CHANNEL, ROOT_TS, reply.text)]


def test_one_other_person_in_the_thread_the_decline_is_posted(tmp_path):
    """C37-1: the saved turns before this one hold one user_id (USER's), so USER2's first
    followed message there is posted."""
    env = thread_of(tmp_path, USER)
    reply = make_reply(**DECLINED)
    label, slack = followed(env, FakeAgent(reply), user=USER2)
    assert label == "refused"
    assert slack.log == [("post", CHANNEL, ROOT_TS, reply.text)]


def test_one_person_with_the_real_agent_the_saved_turn_is_not_before_this_one(tmp_path):
    """C37-1, end to end: the model declines USER2's message; the agent saves that turn, so the
    thread then holds two people, but before this one it held one: posted. The next decline in
    the thread is silent."""
    env = thread_of(tmp_path, USER)
    env.model = FakeModel(Step(decline("UNRECOGNIZED_QUESTION")), clock=env.clock)
    label, slack = followed(env, real_agent(env), user=USER2)
    assert env.model.calls, "the model was not called"
    assert label == "refused"
    ((kind, channel, thread_ts, text),) = slack.log
    assert (kind, channel, thread_ts) == ("post", CHANNEL, ROOT_TS)
    turns = env.store.recent_turns(THREAD_1, 50)
    assert {t["user_id"] for t in turns} == {USER, USER2}
    assert (turns[-1]["status"], turns[-1]["reason_code"]) == ("UNSUPPORTED",
                                                               "UNRECOGNIZED_QUESTION")
    assert_fixed(text, "UNRECOGNIZED_QUESTION")  # the decline's row, SYNTHETIC mode
    env.model = FakeModel(Step(decline("UNRECOGNIZED_QUESTION")), clock=env.clock)
    label, slack = followed(env, real_agent(env), user=USER, text="and the weather tomorrow?",
                            n=1)
    assert (label, slack.log) == ("quiet", [])


# ---- 2. two people in the thread: silent, as today ------------------------------------------

@pytest.mark.parametrize("earlier, writer", [
    ((USER, USER2), USER),
    ((USER, USER2), USER2),
    ((USER2, USER, USER), USER),
], ids=["writer first", "writer second", "three turns, two people"])
def test_two_people_in_the_thread_stays_silent(tmp_path, earlier, writer):
    env = thread_of(tmp_path, *earlier)
    agent = FakeAgent(make_reply(**DECLINED))
    label, slack = followed(env, agent, user=writer)
    assert agent.calls == [(WEATHER, THREAD_1, writer)], "the agent did not run"
    assert label == "quiet"
    assert slack.log == []


def test_two_people_in_the_thread_with_the_real_agent_stays_silent(tmp_path):
    env = thread_of(tmp_path, USER, USER2)
    env.model = FakeModel(Step(decline("UNRECOGNIZED_QUESTION")), clock=env.clock)
    label, slack = followed(env, real_agent(env))
    assert env.model.calls, "the model was not called"
    assert (label, slack.log) == ("quiet", [])


@pytest.mark.parametrize("users", [(USER,), (USER, USER2)], ids=["one person", "two people"])
@pytest.mark.parametrize("code", ["UNSUPPORTED_FIELD", "UNSUPPORTED_METRIC"])
def test_another_refusal_of_a_followed_message_is_posted_as_today(tmp_path, users, code):
    """Nothing else in A13 changes: only UNRECOGNIZED_QUESTION can be silent."""
    env = thread_of(tmp_path, *users)
    reply = make_reply("UNSUPPORTED", reason_code=code)
    label, slack = followed(env, FakeAgent(reply))
    assert label == "refused"
    assert slack.log == [("post", CHANNEL, ROOT_TS, reply.text)]


# ---- 3. a mention or a direct message: posted as today -----------------------------------------

@pytest.mark.parametrize("users", [(USER,), (USER, USER2)], ids=["one person", "two people"])
@pytest.mark.parametrize("name", ["a mention in the thread", "a direct message"])
def test_a_mention_or_a_direct_message_is_posted_as_today(tmp_path, users, name):
    env = thread_of(tmp_path, *users)
    reply = make_reply(**DECLINED)
    event, where = {
        "a mention in the thread": (mention(f"<@{AGENT_USER}> {WEATHER}", ts=IN_THREAD_TS,
                                            thread_ts=ROOT_TS), (CHANNEL, ROOT_TS)),
        "a direct message": (direct_message(WEATHER), (DM_CHANNEL, None)),
    }[name]
    slack, agent = FakeSlack(), FakeAgent(reply)
    label = process(event, settings=env.settings, store=env.store, agent=agent, slack=slack)
    assert len(agent.calls) == 1
    assert label == "refused"
    assert slack.log == [("post", *where, reply.text)]
