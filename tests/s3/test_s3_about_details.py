"""About the data, details and help in county mode: docs/S3A-DESIGN.md C11, with C10's
"given in details only" table and C8's "This covers ... details" (A10's rule of which turn
details describe still holds).

What this file covers
- describe_data (C11): the answer is R2's shape ({"facts": [{"slot": "{f1}", "text": ...},
  ...]}); its lines are generated from the source files: for each source its title, what
  one record is, the period its copy covers, each field in plain words and the floor; a
  changed source file changes them; the synthetic fact sheet is not used.
- about_data answers (C11): an EXPLAINED reply that passes the check is filled from the
  facts, and every about_data answer (passing, failing, or with no describe_data) carries
  the source's notices word for word and the fixed line that the agent is a university
  course project and not a county service.
- details (C11, C10, C8): after a county answer, `details` gives a DETAILS reply that
  carries the notices and the course line, the total and the table as shown (a hidden
  value as "fewer than 10", never as its figure), for a one-way table, a table too long
  for the reply, and a two-way one; no row.
- help and the "what I can do" sentence (C11): generated from the source files, so they
  are not stage 2's synthetic wording and they change with the files. (C36 point 5, changed
  by briefs/S3-R6-A-tests.md: `help` and `details` now go to the model in county mode; the
  help tests check that the agent's reply is posted, the details tests script show_details.)

Readings taken (kit-log/raw/S3A-A-notes.txt)
- The course-project line's wording is not given: checked as holding "university course
  project" (any letter case). The notices are checked word for word.
- The facts are checked for what C11 lists, leniently: the title; the unit or the row
  meaning ("what one record is"); the first and last year of the copy; each non-key
  field by its dimension (or "age"); the floor as the number 10. "What cannot be asked" and
  "what is left out" are not checked (C11 gives no words for them).
- details' layout is not given: its text is checked for what it must hold and must not
  hold, not for line shapes. Hours are written as C6 writes them ("10 pm").
- help's and the "what I can do" sentence's wording is not given: checked as differing
  from stage 2's and naming each source's title or unit.

Not checked: about_data with more than one source's notices (which source's notices then
is not said); DATA_TAG in county mode (not said).
"""
import re

import pytest

from p1support import (AGENT_USER, HELP_LINE, THREAD_2, FakeAgent, FakeSlack, Step, can_ask,
                       decline, describe, fact_lines, finish, make_reply, mention, numbers_in,
                       process, show_details, slack_settings)
from s3support import (A_ID, C_ID, Q_ABOUT, Q_BREAKDOWN, Q_COUNT, SCHOOL, CountyEnv,
                       assert_no_hidden_figure, assert_no_row, check_county_reply, count,
                       fixture_rows, is_, shown, source_json, truth, year)

COURSE = re.compile(r"university course project", re.IGNORECASE)


def facts_of(env):
    """The describe_data answer of the last turn (the first tool answer)."""
    (answer,) = [a for a in env.answers() if "facts" in a]
    return answer["facts"]


def about_turn(env, text):
    return env.ask(Q_ABOUT, Step(describe()), Step(finish("about_data", text)))


def assert_notices(text, *names, env):
    for name in names:
        for notice in env.source(name)["notices"]:
            assert notice in text, f"a notice of {name} is not in the reply word for word"
    assert COURSE.search(text), "no line saying the agent is a university course project"


# ---- describe_data -----------------------------------------------------------------------

def test_describe_data_gives_fact_slots_in_r2s_shape(tmp_path, monkeypatch):
    """C11 with R2: {"facts": [{"slot": "{f1}", "text": <line>}, ...]}, numbered from 1."""
    env = CountyEnv(tmp_path, monkeypatch)
    about_turn(env, "Here is what I know. {f1}.")
    facts = facts_of(env)
    assert facts and all(set(f) >= {"slot", "text"} for f in facts)
    assert [f["slot"] for f in facts] == [f"{{f{n}}}" for n in range(1, len(facts) + 1)]
    assert all(isinstance(f["text"], str) and f["text"].strip() for f in facts)


@pytest.mark.parametrize("name", ["arrests_like", "coded_like"])
def test_the_facts_are_generated_from_the_source_file(tmp_path, monkeypatch, name):
    """C11: for each source its title, what one record is, the period its copy covers, each
    field in plain words, and the floor."""
    env = CountyEnv(tmp_path, monkeypatch, names=(name,))
    about_turn(env, "Here is what I know. {f1}.")
    text = " ".join(f["text"] for f in facts_of(env))
    src = source_json(name)
    assert src["title"] in text
    assert any(w in text for w in (src["unit"]["many"], src["unit"]["one"], src["row_meaning"]))
    first, last = {"arrests_like": ("2024", "2026"), "coded_like": ("2025", "2026")}[name]
    assert first in text and last in text, "the period the copy covers"
    for f in src["fields"]:
        if f["kind"] in ("category", "flag"):
            assert f["dimension"] in text, f"the field {f['name']} in plain words"
        if f["kind"] == "age":
            assert "age" in text.lower()
    assert src["floor"] in numbers_in(text), "the floor"
    assert_no_row(text, fixture_rows(name), "facts")


def test_the_facts_follow_a_changed_source_file(tmp_path, monkeypatch):
    """C11 "generated from the source files": a changed title is the title in the facts."""
    def change(data):
        data["title"] = "SYNTHETIC fixture zebra arrests"
    env = CountyEnv(tmp_path, monkeypatch, change={"arrests_like": change})
    about_turn(env, "Here is what I know. {f1}.")
    text = " ".join(f["text"] for f in facts_of(env))
    assert "SYNTHETIC fixture zebra arrests" in text
    assert source_json("arrests_like")["title"] not in text


def test_the_facts_cover_each_source(tmp_path, monkeypatch):
    """C11: "for each source"."""
    env = CountyEnv(tmp_path, monkeypatch, names=("arrests_like", "coded_like"))
    about_turn(env, "Here is what I know. {f1}.")
    text = " ".join(f["text"] for f in facts_of(env))
    for name in ("arrests_like", "coded_like"):
        assert source_json(name)["title"] in text


def test_the_synthetic_fact_sheet_is_not_used_in_county_mode(tmp_path, monkeypatch):
    """C0 and C11: county mode's facts come from the source files, not config/fact_sheet.md
    (whose lines describe the SYNTHETIC test data)."""
    env = CountyEnv(tmp_path, monkeypatch)
    about_turn(env, "Here is what I know. {f1}.")
    texts = [f["text"] for f in facts_of(env)]
    synthetic = [line for line in fact_lines() if "SYNTHETIC" in line or "2024 and 2025" in line]
    assert synthetic and not [line for line in synthetic if line in texts]


# ---- about_data answers ------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["arrests_like", "coded_like"])
def test_a_passing_about_text_is_filled_and_carries_the_notices(tmp_path, monkeypatch, name):
    """C11 and R1: the text passes, its fact slot is filled (a capital at the start, the
    line without its final full stop), status EXPLAINED, style agent; the reply carries
    the source's notices word for word and the course-project line.
    Changed by briefs/S3-R26-A-tests.md (C63): "{f1}." is a plain facts text, so it is sent as
    C63's rendering (`Here is what I know.` and the fact), unchecked; it was the fact filled
    alone. R1's fill is kept alive with a text that is not plain ("Here is the data. {f1}.", in
    a second thread so its notices are in full too)."""
    env = CountyEnv(tmp_path, monkeypatch, names=(name,))
    reply = about_turn(env, "{f1}.")
    check_county_reply(reply)
    assert (reply.status, reply.reply_kind, reply.reply_style) == \
        ("EXPLAINED", "about_data", "agent"), (reply.status, reply.reply_style, reply.text)
    full = facts_of(env)[0]["text"]
    assert reply.text.startswith(f"Here is what I know. {full}\n"), reply.text
    assert_notices(reply.text, name, env=env)
    reply = env.ask(Q_ABOUT, Step(describe()),
                    Step(finish("about_data", "Here is the data. {f1}.")), thread_key=THREAD_2)
    check_county_reply(reply)
    assert (reply.status, reply.reply_kind, reply.reply_style) == \
        ("EXPLAINED", "about_data", "agent"), (reply.status, reply.reply_style, reply.text)
    line = full[:-1] if full.endswith(".") else full
    assert reply.text.startswith("Here is the data. " + line[:1].upper() + line[1:] + ".")
    assert_notices(reply.text, name, env=env)


@pytest.mark.parametrize("how", ["failing_text", "no_describe_data"])
def test_every_about_data_answer_carries_the_notices(tmp_path, monkeypatch, how):
    """C11: "about_data answers carry the source's notices word for word, and the fixed
    line ...": also the fixed ABOUT reply (A7, R1: a text that fails the check, or no
    describe_data this turn). Nothing the model wrote is in it."""
    env = CountyEnv(tmp_path, monkeypatch)
    if how == "failing_text":
        reply = about_turn(env, "Here is zqx. {f1}.")
    else:
        reply = env.ask(Q_ABOUT, Step(finish("about_data", "Here is zqx.")))
    check_county_reply(reply)
    assert (reply.status, reply.reply_kind, reply.reply_style) == \
        ("EXPLAINED", "about_data", "fallback"), (reply.status, reply.reply_style, reply.text)
    assert "zqx" not in reply.text
    assert_notices(reply.text, "arrests_like", env=env)


# ---- details -------------------------------------------------------------------------------------

def answered_then_details(env, spec):
    reply = env.ask(Q_BREAKDOWN, Step(count(A_ID, *spec)),
                    Step(finish("finding", "I counted {r1.count}.")))
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    details = env.ask("details", Step(show_details()))
    check_county_reply(details)
    assert (details.status, details.reason_code) == ("DETAILS", None), details.text
    # Changed by briefs/S3-R6-A-tests.md (C36 point 5; was model_called False, "A4 step 2:
    # Python answers `details`"): in county mode the model gets it and calls show_details.
    assert details.model_called is True
    return reply, details


def test_details_of_a_breakdown_carry_the_table_as_shown_and_the_notices(tmp_path,
                                                                         monkeypatch):
    """C11, C8: details carry the notices and the course line, the total and every group as
    shown: 2025 near a school by district has groups of 10, 9, 1, 0, 24 and 31 (total 75)."""
    env = CountyEnv(tmp_path, monkeypatch)
    spec = (year(2025), [is_(SCHOOL, True)], ["district"])
    t = truth("arrests_like", *spec)
    assert dict(t["groups"]) == {"district 1": 10, "district 2": 9, "district 3": 1,
                                 "district 4": 0, "district 5": 24, "district 6": 31}
    reply, details = answered_then_details(env, spec)
    text = details.text
    assert_notices(text, "arrests_like", env=env)
    for label in t["groups"]:
        assert label in text, label
    assert "fewer than 10" in text
    assert {t["total"], 10, 24, 31} <= numbers_in(text)
    assert_no_hidden_figure(text, "details")
    assert_no_row(text, fixture_rows("arrests_like"), "details")


def test_details_hold_a_table_too_long_for_the_reply(tmp_path, monkeypatch):
    """C10: a breakdown of more than 12 groups is given in details only. 2025 by hour has
    24 groups: 10 pm the most (25), five hours with 9 (hidden), 5 am with 0."""
    env = CountyEnv(tmp_path, monkeypatch)
    spec = (year(2025), [], ["hour"])
    t = truth("arrests_like", *spec)
    assert t["groups"][22] == 25 and t["groups"][5] == 0
    assert sorted(h for h, n in t["groups"].items() if n == 9) == [18, 19, 20, 21, 23]
    reply, details = answered_then_details(env, spec)
    assert "The full table is in the details." in reply.text
    text = details.text
    for hour in (1, 4, 6, 11, 13, 22, 23):
        label = f"{hour} am" if hour < 12 else f"{hour - 12} pm"
        assert label in text, label
    assert "fewer than 10" in text and 25 in numbers_in(text)
    assert_no_hidden_figure(text, "details")
    assert_notices(text, "arrests_like", env=env)


def test_details_hold_a_two_way_table(tmp_path, monkeypatch):
    """C10: a two-way breakdown is given in details only; details show it as shown."""
    env = CountyEnv(tmp_path, monkeypatch)
    spec = (year(2024), [], ["district", "gender"])
    t = truth("arrests_like", *spec)
    reply, details = answered_then_details(env, spec)
    assert "The full table is in the details." in reply.text
    text = details.text
    for (district, gender), n in t["grid"].items():
        assert district in text and gender in text
    shown_values = {shown(n) for n in t["grid"].values()}
    for value in shown_values - {"fewer than 10"}:
        assert int(value.replace(",", "")) in numbers_in(text), value
    if "fewer than 10" in shown_values:
        assert "fewer than 10" in text
    assert_no_hidden_figure(text, "details")


def test_details_with_no_earlier_answer(tmp_path, monkeypatch):
    """A10, unchanged in county mode: no earlier turn with results gives NO_PREVIOUS_ANSWER.
    (C36 point 5, S3-R6-A: `details` goes to the model, which calls show_details.)"""
    env = CountyEnv(tmp_path, monkeypatch)
    reply = env.ask("details", Step(show_details()))
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", "NO_PREVIOUS_ANSWER")


# ---- help and what I can do -------------------------------------------------------------------

AGENT_HELP_REPLY = "The agent's own reply to help (SYNTHETIC test data)."  # C36 point 5


def county_help(tmp_path, monkeypatch, name):
    """Changed by briefs/S3-R6-A-tests.md (C36 point 5, D-065; was: Python posted C11's help
    and the agent was not called): `help` goes to the agent like any message."""
    env = CountyEnv(tmp_path, monkeypatch, names=(name,))
    settings = slack_settings(tmp_path, MOCO_DATA="county", MOCO_STATE_DIR=str(env.state_dir))
    slack = FakeSlack()
    agent = FakeAgent(make_reply("EXPLAINED", text=AGENT_HELP_REPLY))
    label = process(mention(f"<@{AGENT_USER}> help"), settings=settings, store=env.store,
                    agent=agent, slack=slack)
    assert label == "explained" and [c[0] for c in agent.calls] == ["help"], (label, agent.calls)
    (post,) = slack.posts
    return post[3]


def test_help_goes_to_the_agent_with_each_source_file(tmp_path, monkeypatch):
    """Changed by briefs/S3-R6-A-tests.md (C36 point 5; was
    test_help_is_generated_from_the_source_files, C11): in county mode `help` is not
    answered from the source files or with stage 2's synthetic HELP; the agent's reply is
    posted, whichever source file is loaded."""
    a = county_help(tmp_path / "a", monkeypatch, "arrests_like")
    c = county_help(tmp_path / "c", monkeypatch, "coded_like")
    assert a == c == AGENT_HELP_REPLY and a != HELP_LINE


def test_the_what_i_can_do_sentence_is_generated_from_the_source_files(tmp_path, monkeypatch):
    """C11: the "what I can do" sentence (A7's CAN_ASK) in county mode comes from the
    source files: a declined turn does not carry stage 2's synthetic sentence and names
    the source."""
    env = CountyEnv(tmp_path, monkeypatch, names=("coded_like",))
    reply = env.ask(Q_COUNT, Step(decline("UNRECOGNIZED_QUESTION")))
    check_county_reply(reply)
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", "UNRECOGNIZED_QUESTION")
    assert can_ask() not in reply.text
    src = source_json("coded_like")
    assert src["title"] in reply.text or src["unit"]["many"] in reply.text, reply.text
