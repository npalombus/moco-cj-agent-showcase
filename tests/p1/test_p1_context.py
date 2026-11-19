"""Context: what the model is given at each step (docs/P1A-DESIGN.md A11; brief P1A-A
point 9). Revision 2 (docs/P1A-R2-DESIGN.md R8): the agent prompt is
config/agent_prompt_v2.md, and the passing texts are R1's (fact slots, listed words).

A11 names no build function, so every test runs a turn through agent.handle_question
(p1support.Env, with a FakeModel) and reads what the model was given: model.calls[i]
["messages"] and ["tools"]. Earlier turns are made the same way, in the same Env.

Covered: the system message (the agent prompt, then the DATA block built from the registry,
then the date line, then the restricted line only when the guard restricted the turn); no
thread message without earlier turns; the THREAD SO FAR message (oldest first, the newest
MOCO_THREAD_TURNS_IN_CONTEXT turns, the wording for each kind of turn, ` and said` only for
a turn that stored reply text, no failing text shown, the cuts to 200 and 300 characters, the
8,000-character cap (3,000 before C61, changed by briefs/S3-R23-A-tests.md), no number from the
data, no other thread's turns);
the LATEST MESSAGE; this turn's steps passed back with their tool messages; seven tools, or
five when restricted (names only: another file checks their arguments); prompt_version.

Accepted both ways, because A11 does not say:
- a cut question or reply text may end with a mark such as "..." or not, and may be cut at
  a word break: what is shown must be the start of the text, hold most of it, and hold
  nothing past character 200 (question) or 300 (reply text);
- the wording for an all-ages count: only `counted (2024, ` is checked;
- blank lines in the thread block are skipped (A11 gives its lines, not its spacing);
- the LATEST MESSAGE: the header first, then the question, on a line of its own or not
  (A11.3 says only "and the question");
- a background turn's stored text (A12, "the checked text") may be the model's text alone or
  with A7's fixed prefix and suffix: the test text is whole either way;
- (read one way, kit-log/raw/P1A2-A-notes.txt) an about_data turn's stored text is shown
  with its fact slots unfilled, as a finding's is (A12: "the checked text"; R8: "the stored
  text with its slots unfilled");
- a background turn whose text failed the checks: A7 gives no status, so its thread line may
  be `gave general background` or, when the turn is UNSUPPORTED, `declined (<its code>)`;
- the messages are read in the OpenAI chat format, as now (P1 section 7): an assistant
  message's tool_calls[i].id, .function.name and .function.arguments (the JSON text, or the
  object itself), and a tool message's tool_call_id and content;
- prompt_version as P1's test read it: the file name without .md, up to 3 marks (optionally
  a "sha256" label), then the first 8 hex characters of its sha256 in either case
  (p1support.prompt_version_pattern). A9 gives no key names, so it is looked for anywhere in
  turn.json, inside JSON text too (p1support.deep_leaves).

Cannot check here: what the real model makes of these messages; a prompt file other than
config/agent_prompt_v2.md (A11 names no way to pass one, so P1's "the version follows the
prompt file" test is gone); the direct-message memory window for the thread block (A5,
`memory_minutes`), which this file does not test.
"""
import json
import re
from datetime import date

import pytest

from p1support import (AGENT_PROMPT_MD, ALL_TOOLS, LATEST_HEADER, ONE_COUNT_TEXT,
                       RESTRICTED_CODES, RESTRICTED_LINE, RESTRICTED_TOOLS, THREAD_1, THREAD_2,
                       THREAD_HEADER, TODAY, TYPED, Env, Step, about_text, ask_user,
                       check_no_data_counts, check_tools_hold_no_data, compare, compare_text,
                       count, count_slots, decline, deep_leaves, describe, fact_slots,
                       fill_expect, finish, has_number, latest_index, load_registry,
                       messages_text, months, numbers_in, odd_chars, prompt_version_pattern,
                       registry_copy, registry_metric, registry_source, reply_rules,
                       sentences, show_details, single_sentence_facts, synthetic_fact,
                       system_text, thread_block, turn_record, unlisted_words)
from support import AGE_GROUPS, REFUSED, SUPPORTED

QUESTION = SUPPORTED["S1"][0]
Q_ALL_AGES = SUPPORTED["S2"][0]
Q_COMPARE = "Compare 2024 and 2025 for people under 18."
LATEST = "And what about the other age groups?"
END = Step(decline("UNSUPPORTED_METRIC"))  # one step that ends the turn and counts nothing
RESTRICTED_QUESTIONS = {"REAL_DATA_NOT_AVAILABLE": REFUSED["U5"][0],  # stage 1's rule 2
                        "UNSUPPORTED_METRIC": REFUSED["U1"][0],       # rule 3
                        "UNSUPPORTED_FIELD": REFUSED["U3"][0]}        # rule 4
COMPARE_TEXT = compare_text("r3")
COMPARE_STEPS = (Step(count(2024, "under_18"), count(2025, "under_18")),
                 Step(compare("r1", "r2")), Step(finish("finding", COMPARE_TEXT)))

# Texts that pass R1's checks: fact slots and listed words only (the background text, A7,
# holds the hedge words it needs and none of reply_rules.json's other lists).
TAIL = "zebrafinch"
LONG_TAIL = "{r1.months}"  # the long finding's last slot, past character 300
LONG_FINDING = ("I counted {r1.count} and here is what I found in the data for you, so that "
                "you have the full count and the total that you asked for, based on the "
                "records in the data for the age group, and here is the summary of the result "
                "with the details that you want to see, as you asked me for the count and the "
                "data that it is based on. " + LONG_TAIL + ".")  # C13 rule 1: was "on: "
# An about_data text whose filled form is four sentences at most either way (notes file).
ABOUT_TEXT = about_text(synthetic_fact(), single_sentence_facts()[0])
ABOUT_FILLED = fill_expect(ABOUT_TEXT, fact_slots())
BACKGROUND_TEXT = ("Arrest counts may change from one season to the next for many reasons, "
                   "such as how often police patrol or how records are kept.")
# Fail the checks, each holding TAIL: WORD (R1, words not on the list) and HEDGE (A7, no
# hedge word).
FAILING_ABOUT = ABOUT_TEXT + f" The {TAIL} file proves nothing."
FAILING_BACKGROUND = ("Arrest counts change over a year for many reasons, such as how police "
                      f"patrol or how records are kept in the {TAIL} file.")
# Fails CHARS (a typed digit, R1), so its turn is a fallback finding.
TYPED_FINDING = f"I counted {{r1.count}}, about {TYPED} in all."


def first_call(env, question=QUESTION, *steps, **kw):
    """Run one turn (by default a single decline step); the messages of its first model call."""
    reply = env.ask(question, *(steps or (END,)), **kw)
    assert env.model.calls, (reply.status, reply.reason_code)
    return env.model.calls[0]["messages"]


def block_lines(messages):
    block = thread_block(messages)
    assert block is not None, "no THREAD SO FAR message"
    return [line.rstrip() for line in block.splitlines() if line.strip()]


def shown_part(quoted):
    """The text inside "...", without a final cut mark."""
    assert len(quoted) >= 2 and quoted[0] == quoted[-1] == '"', quoted
    inner = quoted[1:-1]
    for mark in ("...", "…"):
        inner = inner.removesuffix(mark)
    return inner


def check_latest(message, question):
    """A11.3: one user message, the header, then the question (on a line of its own or not:
    A11.3 does not say)."""
    assert message["role"] == "user"
    content = message["content"]
    assert content.startswith(LATEST_HEADER), content
    assert question in content[len(LATEST_HEADER):], content


def today_line(today):
    return f"Today's date: {today:%Y-%m-%d}"


def system_lines(messages):
    return [line.strip() for line in system_text(messages).splitlines() if line.strip()]


def after_prompt(system):
    prompt = AGENT_PROMPT_MD.read_text(encoding="utf-8").strip()
    assert prompt in system, "the agent prompt's text is not in the system message"
    return system[system.index(prompt) + len(prompt):]


# ---- 1. the system message --------------------------------------------------------------

def test_one_system_message_first_holding_the_agent_prompt(tmp_path):
    """A11.1 and R8: one system message, first, starting with config/agent_prompt_v2.md's
    text."""
    messages = first_call(Env(tmp_path))
    assert messages[0]["role"] == "system"
    after_prompt(system_text(messages))  # system_text: first, and the only system message
    prompt = AGENT_PROMPT_MD.read_text(encoding="utf-8").strip()
    assert system_text(messages).lstrip().startswith(prompt), "text before the agent prompt"


def test_the_data_block_from_the_registry_follows_the_prompt(tmp_path):
    """A11.1, "then the DATA block built from the registry as now" (P1 section 7): checked in
    the part between the prompt's text and the date line, since the prompt itself may hold
    some of the same words."""
    rest = after_prompt(system_text(first_call(Env(tmp_path))))
    assert "Today's date:" in rest
    data = rest[:rest.index("Today's date:")]
    source, metric = registry_source(), registry_metric()
    assert source["id"] in data
    assert "SYNTHETIC" in data.replace(source["id"], ""), "the word SYNTHETIC, not only in the id"
    assert source["coverage"]["start"] in data and source["coverage"]["end"] in data
    lines = data.splitlines()
    for code, wording in source["age_groups"].items():
        assert any(code in line and wording in line for line in lines), code
    assert metric["unit"] in data
    for item in metric["is_not"]:
        assert item in data, item


def test_the_data_block_follows_the_registry_file(tmp_path):
    """A11.1: a registry copy with new age wordings gives a system message with them."""
    new_wording = {code: f"test wording {i} for this age group"
                   for i, code in enumerate(AGE_GROUPS)}

    def change(data):
        data["approved_sources"][0]["age_groups"] = new_wording
    registry = load_registry(registry_copy(tmp_path, change))
    system = system_text(first_call(Env(tmp_path, registry=registry)))
    for code, wording in new_wording.items():
        assert code in system and wording in system, code


@pytest.mark.parametrize("today", [TODAY, date(2027, 3, 4)], ids=str)
def test_the_date_line_ends_an_unrestricted_system_message(today, tmp_path):
    """A11.1: `Today's date: <date>` (YYYY-MM-DD, as P1) comes last when the turn is not
    restricted, and the restricted line is absent."""
    messages = first_call(Env(tmp_path), today=today)
    assert system_lines(messages)[-1] == today_line(today)
    assert RESTRICTED_LINE not in system_text(messages)


@pytest.mark.parametrize("code", RESTRICTED_CODES)
def test_a_restricted_turn_adds_the_restricted_line_after_the_date(code, tmp_path):
    """A11.1 and A2: when stage 1's rule 2, 3 or 4 matches, the restricted line follows the
    date line."""
    messages = first_call(Env(tmp_path), RESTRICTED_QUESTIONS[code], Step(decline(code)))
    assert system_lines(messages)[-2:] == [today_line(TODAY), RESTRICTED_LINE]


# ---- 2 and 3. the thread block and the latest message -----------------------------------

def test_with_no_earlier_turn_the_messages_are_system_then_latest(tmp_path):
    """A11.2 and A11.3: no THREAD SO FAR message when the thread has no earlier turn."""
    messages = first_call(Env(tmp_path))
    assert [m["role"] for m in messages] == ["system", "user"]
    assert thread_block(messages) is None
    check_latest(messages[1], QUESTION)


def test_earlier_turns_give_one_thread_message_between_system_and_latest(tmp_path):
    """A11.2: one user message, its first line the header, then two lines per turn."""
    env = Env(tmp_path)
    env.ask(QUESTION, END)
    messages = first_call(env, LATEST)
    assert [m["role"] for m in messages] == ["system", "user", "user"]
    assert messages[1]["content"] == thread_block(messages)
    assert latest_index(messages) == 2
    check_latest(messages[2], LATEST)
    assert block_lines(messages) == [THREAD_HEADER, f'User: "{QUESTION}"',
                                     "You: declined (UNSUPPORTED_METRIC)"]


# Changed by briefs/S3-R23-A-tests.md (C61 point 5 of docs/S3A-DESIGN.md, with its correction 3:
# the default of MOCO_THREAD_TURNS_IN_CONTEXT is 10 in both modes; it was 6, and the case was
# (None, 8, 6), "default_6"): four more words, so twelve earlier turns, ten shown.
WORDS = ["aardvark", "buffalo", "chinchilla", "dingo", "echidna", "flamingo", "gazelle",
         "hedgehog", "ibis", "jackal", "kiwi", "lemur"]


@pytest.mark.parametrize("setting, earlier, shown", [(2, 5, 2), (3, 5, 3), (None, 12, 10)],
                         ids=["2", "3", "default_10"])
def test_only_the_newest_n_turns_oldest_first(setting, earlier, shown, tmp_path):
    """A11.2 and A14: the newest MOCO_THREAD_TURNS_IN_CONTEXT turns (default 10 since C61, was
    6), oldest first."""
    values = {} if setting is None else {"MOCO_THREAD_TURNS_IN_CONTEXT": setting}
    env = Env(tmp_path, **values)
    questions = [f"Could you count the arrests for the {word} file?" for word in WORDS[:earlier]]
    for question in questions:
        env.ask(question, END)
    lines = block_lines(first_call(env, LATEST))
    assert lines[0] == THREAD_HEADER
    assert lines[1::2] == [f'User: "{q}"' for q in questions[-shown:]]
    assert lines[2::2] == ["You: declined (UNSUPPORTED_METRIC)"] * shown


def test_an_earlier_question_is_cut_to_200_characters(tmp_path):
    """A11.2: `User: "<question, cut to 200 characters>"`."""
    head = "How many arrests were recorded "
    question = head + ("word " * 40)[:200 - len(head)] + "TAILMARKER and more words after it"
    assert question.index("TAILMARKER") == 200
    env = Env(tmp_path)
    env.ask(question, END)
    messages = first_call(env, LATEST)
    line = block_lines(messages)[1]
    assert line.startswith("User: "), line
    shown = shown_part(line.removeprefix("User: "))
    assert 150 <= len(shown) <= 200 and question.startswith(shown), shown
    assert "TAILMARKER" not in thread_block(messages)


def _counted(env):
    env.answered(QUESTION, (2025, "18_25"))
    return QUESTION


def _compared(env):
    env.answered(Q_COMPARE, (2024, "under_18"), (2025, "under_18"), compared=True)
    return Q_COMPARE


def _explained(env):
    question = "What is this data?"
    reply = env.ask(question, Step(describe()), Step(finish("about_data", ABOUT_TEXT)))
    assert reply.status == "EXPLAINED", (reply.status, reply.reason_code)
    return question


def _background(env):
    hedges = reply_rules()["hedge_words"]
    assert "may" in hedges and "often" in hedges  # the hedge the text relies on
    question = "Why do arrest counts go up and down over a year?"
    reply = env.ask(question, Step(finish("background", BACKGROUND_TEXT)))
    assert reply.status == "EXPLAINED", (reply.status, reply.reason_code)
    return question


def _details(env):
    env.answered(QUESTION, (2025, "18_25"))
    question = "Can I see the breakdown behind that answer?"
    reply = env.ask(question, Step(show_details()))
    assert reply.status == "DETAILS", (reply.status, reply.reason_code)
    return question


def _asked_year(env):
    question = "How many arrests were there for ages 18 to 25?"
    reply = env.ask(question, Step(ask_user("year")))
    assert reply.status == "NEEDS_INPUT", (reply.status, reply.reason_code)
    return question


def _declined(env):
    question = "What happened after these arrests?"
    reply = env.ask(question, END)
    assert reply.status == "UNSUPPORTED", (reply.status, reply.reason_code)
    return question


# The last item is what ` and said: "..."` must hold (A12's stored text, R8 slots
# unfilled), or None when A12 stores nothing for that kind of turn. ABOUT_TEXT is short,
# so it is whole. BACKGROUND_TEXT is 127 characters, 211 with A7's fixed prefix and suffix:
# whole either way.
WORDINGS = [
    ("counted (2025, 18_25)", _counted, {}, ONE_COUNT_TEXT),
    ("counted (2024, under_18), (2025, under_18) and compared them", _compared, {},
     COMPARE_TEXT),
    ("explained the data", _explained, {}, ABOUT_TEXT),
    ("gave general background", _background, {"MOCO_BACKGROUND": "on"}, BACKGROUND_TEXT),
    ("showed details", _details, {}, None),
    ("asked which year", _asked_year, {}, None),
    ("declined (UNSUPPORTED_METRIC)", _declined, {}, None),
]


@pytest.mark.parametrize("wording, setup, settings, said", WORDINGS,
                         ids=["count", "compare", "about_data", "background", "details",
                              "ask_year", "decline"])
def test_each_kind_of_turn_has_its_wording(wording, setup, settings, said, tmp_path):
    """A11.2, A12 and R8: what the agent did, in A11's own words, then ` and said: "..."`
    when the turn stored reply text (an agent-style finding, about_data, background) and
    not otherwise."""
    assert len(ABOUT_FILLED) < 300 and len(sentences(ABOUT_FILLED)) <= 4
    env = Env(tmp_path, **settings)
    question = setup(env)
    messages = first_call(env, LATEST)
    lines = block_lines(messages)
    assert lines[-2] == f'User: "{question}"'
    if said is None:
        assert lines[-1] == f"You: {wording}", lines[-1]
    else:
        assert lines[-1].startswith(f'You: {wording} and said: "'), lines[-1]
        assert f'and said: "{said}' in lines[-1], lines[-1]
    check_no_data_counts(thread_block(messages))


def test_an_all_ages_count_shows_its_year(tmp_path):
    """A11.2 gives no wording for an all-ages count (notes file): only `counted (2024, `."""
    env = Env(tmp_path)
    env.answered(Q_ALL_AGES, (2024, None))
    lines = block_lines(first_call(env, LATEST))
    assert lines[-2] == f'User: "{Q_ALL_AGES}"'
    assert lines[-1].startswith("You: counted (2024, "), lines[-1]


def test_an_agent_style_finding_is_shown_with_its_text_unfilled(tmp_path):
    """A11.2, A12 and R8: ` and said: "<text>"` holds the model's text as given, slots
    unfilled."""
    env = Env(tmp_path)
    reply = env.answered(QUESTION, (2025, "18_25"))
    assert reply.reply_style == "agent", reply.draft_failures
    lines = block_lines(first_call(env, LATEST))
    assert lines[-1] == f'You: counted (2025, 18_25) and said: "{ONE_COUNT_TEXT}"'


def test_the_text_said_is_cut_to_300_characters(tmp_path):
    """A11.2: `and said: "<that text, cut to 300 characters>"`. The long finding passes
    R1's check (listed words, two sentences, at most 600 characters once filled), and its
    last slot starts past character 300."""
    assert LONG_FINDING.index(LONG_TAIL) >= 300
    assert not unlisted_words(LONG_FINDING) and not odd_chars(LONG_FINDING)
    assert len(fill_expect(LONG_FINDING, count_slots("r1", 2025, "18_25"))) <= 600
    env = Env(tmp_path)
    reply = env.answered(QUESTION, (2025, "18_25"), text=LONG_FINDING)
    assert reply.reply_style == "agent", reply.draft_failures
    messages = first_call(env, LATEST)
    line = block_lines(messages)[-1]
    prefix = "You: counted (2025, 18_25) and said: "
    assert line.startswith(prefix), line
    said = shown_part(line.removeprefix(prefix))
    assert 250 <= len(said) <= 300 and LONG_FINDING.startswith(said), said
    assert LONG_TAIL not in thread_block(messages)


def test_a_finding_that_failed_the_checks_is_shown_without_its_text(tmp_path):
    """A12 and answer A3: a text that failed the checks is not stored, so no ` and said`;
    the number it typed reaches no message."""
    env = Env(tmp_path)
    reply = env.answered(QUESTION, (2025, "18_25"), text=TYPED_FINDING)
    assert reply.reply_style == "fallback", (reply.reply_style, reply.draft_failures)
    messages = first_call(env, LATEST)
    assert block_lines(messages)[-1] == "You: counted (2025, 18_25)"
    assert " and said" not in thread_block(messages)
    assert not has_number(TYPED, messages_text(messages))


@pytest.mark.parametrize("kind, question, text, settings, wording", [
    ("about_data", "What is this data?", FAILING_ABOUT, {}, "explained the data"),
    ("background", "Why do arrest counts go up and down over a year?", FAILING_BACKGROUND,
     {"MOCO_BACKGROUND": "on"}, "gave general background"),
], ids=["about_data", "background"])
def test_an_explanation_that_failed_the_checks_is_shown_without_its_text(
        kind, question, text, settings, wording, tmp_path):
    """A12 and answer A3: a failing about_data text (R1, WORD), or a failing background
    text with MOCO_BACKGROUND on (A7, HEDGE), is not stored, so the next turn shows no
    ` and said` and none of the text reaches the model."""
    rules = reply_rules()
    if kind == "about_data":
        assert TAIL in unlisted_words(text)
    else:
        words = re.findall(r"[a-z]+", text.lower())
        phrases = {" ".join(words[i:i + n]) for n in (1, 2) for i in range(len(words) - n + 1)}
        assert not phrases & set(rules["hedge_words"]), phrases & set(rules["hedge_words"])
    env = Env(tmp_path, **settings)
    steps = [Step(describe())] if kind == "about_data" else []
    reply = env.ask(question, *steps, Step(finish(kind, text)))
    assert reply.reply_style == "fallback", (reply.status, reply.reply_style)
    messages = first_call(env, LATEST)
    allowed = {f"You: {wording}"}
    if kind == "background" and reply.status == "UNSUPPORTED":
        allowed.add(f"You: declined ({reply.reason_code})")  # A7 gives no status here
    assert block_lines(messages)[-1] in allowed, block_lines(messages)[-1]
    assert TAIL not in messages_text(messages)


def test_the_thread_block_is_at_most_8000_characters_newest_kept(tmp_path):
    """A11.2: the block is capped and the newest turns are kept. Changed by
    briefs/S3-R23-A-tests.md (C61 point 5 of docs/S3A-DESIGN.md, with its correction 3:
    THREAD_BLOCK_MAX is 8,000 in both modes; it was test_the_thread_block_is_at_most_3000_
    characters_newest_kept, with fifteen turns, MOCO_THREAD_TURNS_IN_CONTEXT=20, at most 3,000
    characters and at least four turns shown). Forty turns with 200-character questions and
    passing about_data texts are more than 8,000 characters. Each turn takes at least 250
    characters (a 208-character User line and a You line) and at most about 550 (a You line
    with at most 300 characters said), so at least fourteen whole turns fit and forty cannot;
    and at most twelve would fit in 3,000."""
    env = Env(tmp_path, MOCO_THREAD_TURNS_IN_CONTEXT=50)
    tags = [f"turnmark{i:02d}x" for i in range(40)]
    for tag in tags:
        question = (f"Arrests question {tag} " + "word " * 50)[:200]
        reply = env.ask(question, Step(describe()), Step(finish("about_data", ABOUT_TEXT)))
        assert reply.status == "EXPLAINED", (reply.status, reply.reason_code)
    messages = first_call(env, LATEST)
    block = thread_block(messages)
    assert len(block) <= 8000, len(block)
    assert block_lines(messages)[0] == THREAD_HEADER
    shown = [tag in block for tag in tags]
    assert shown[-1], "the newest turn was dropped"
    assert sum(shown) >= 14, "fewer turns kept than fit in 8,000 characters"
    assert not all(shown), "forty such turns cannot fit in 8,000 characters"
    assert shown == sorted(shown), "the turns kept are not the newest"


def test_no_number_from_the_data_reaches_the_model(tmp_path):
    """A11.2 and A0: after two answered turns (a count, and two counts compared), no total,
    difference or monthly count of theirs is in the block, no total from the data is in any
    message of the next turn, and their replies are not there either."""
    env = Env(tmp_path)
    earlier = [env.answered(QUESTION, (2025, "18_25")),
               env.answered(Q_COMPARE, (2024, "under_18"), (2025, "under_18"), compared=True)]
    question = "And for ages 26 to 40?"
    env.ask(question, Step(count(2025, "26_40")), Step(finish("finding", ONE_COUNT_TEXT)))
    block = thread_block(env.model.calls[0]["messages"])
    assert block is not None and "counted (2025, 18_25)" in block and "compared them" in block

    counted = [(2025, "18_25"), (2024, "under_18"), (2025, "under_18")]
    totals = [sum(months(y, g)) for y, g in counted]
    for recorded in env.model.calls:
        text = messages_text(recorded["messages"])
        check_no_data_counts(text)
        for total in totals:
            assert not has_number(total, text), total
        for reply in earlier:
            assert reply.text.splitlines()[0] not in text
    check_tools_hold_no_data(env.model)

    # In the block: neither the difference nor a monthly count (from 10 up; a number the
    # user typed in a question shown there is the user's, not the data's).
    typed = numbers_in(" ".join([QUESTION, Q_COMPARE]))
    from_data = {abs(totals[1] - totals[2])} | {n for y, g in counted for n in months(y, g)
                                                 if n >= 10}
    assert not (from_data - typed) & numbers_in(block), (from_data - typed) & numbers_in(block)


def test_another_threads_turns_never_appear(tmp_path):
    """A11.2 (P1 section 7): the turns are this thread's only."""
    env = Env(tmp_path)
    env.ask("Could you count the arrests for the buffalo file?", END, thread_key=THREAD_2)
    messages = first_call(env, "Could you count the arrests for the aardvark file?",
                          thread_key=THREAD_1)
    assert thread_block(messages) is None
    assert "buffalo" not in messages_text(messages)
    messages = first_call(env, LATEST, thread_key=THREAD_1)
    assert "aardvark" in thread_block(messages)
    assert "buffalo" not in messages_text(messages)


# ---- 4. this turn's steps --------------------------------------------------------------

def _tool_call(entry):
    function = entry["function"]
    arguments = function["arguments"]
    return (entry["id"], function["name"],
            json.loads(arguments) if isinstance(arguments, str) else arguments)


def test_each_step_sees_the_earlier_steps_and_their_tool_messages(tmp_path):
    """A11.4: after the LATEST MESSAGE, for each earlier step, its assistant message with its
    tool calls (the model's ids, names and arguments), then one tool message per call with
    tool_call_id equal to that id and Python's JSON answer, in order. The second step sees
    the first step's; the third sees both."""
    env = Env(tmp_path)
    env.ask(Q_COMPARE, *COMPARE_STEPS)
    assert len(env.model.calls) == len(COMPARE_STEPS)
    for k, recorded in enumerate(env.model.calls):
        messages = recorded["messages"]
        assert all(m["role"] in ("system", "user", "assistant", "tool") for m in messages)
        after = messages[latest_index(messages) + 1:]
        position = 0
        for step in range(k):
            assistant = after[position]
            position += 1
            assert assistant["role"] == "assistant", assistant
            wanted = [(f"call_{step}_{i}", name, arguments)
                      for i, (name, arguments) in enumerate(COMPARE_STEPS[step].calls)]
            assert [_tool_call(entry) for entry in assistant["tool_calls"]] == wanted
            for call_id, _, _ in wanted:
                tool = after[position]
                position += 1
                assert tool["role"] == "tool" and tool["tool_call_id"] == call_id, tool
                assert isinstance(json.loads(tool["content"]), dict), tool["content"]
        assert position == len(after), f"step {k} was given more than the earlier steps"


# ---- the tools offered ------------------------------------------------------------------

def test_an_unrestricted_turn_is_offered_the_seven_tools(tmp_path):
    """A11 and A3: the seven tools, at every step (names only), and no restricted line."""
    env = Env(tmp_path)
    env.ask(Q_COMPARE, *COMPARE_STEPS)
    assert env.model.calls
    for i, recorded in enumerate(env.model.calls):
        assert len(recorded["tools"]) == 7
        assert env.model.tools_offered(i) == ALL_TOOLS
        assert RESTRICTED_LINE not in system_text(recorded["messages"]), i


@pytest.mark.parametrize("code", RESTRICTED_CODES)
def test_a_restricted_turn_is_offered_five_tools(code, tmp_path):
    """A11 and A2: no count_arrests and no compare when the guard restricted the turn, and
    the restricted line after the date line, at every step."""
    env = Env(tmp_path)
    env.ask(RESTRICTED_QUESTIONS[code], Step(describe()), Step(decline(code)))
    assert env.model.calls
    for i, recorded in enumerate(env.model.calls):
        assert len(recorded["tools"]) == 5
        assert env.model.tools_offered(i) == RESTRICTED_TOOLS
        assert system_lines(recorded["messages"])[-2:] == [today_line(TODAY), RESTRICTED_LINE]


# ---- prompt_version ---------------------------------------------------------------------

def test_the_prompt_version_is_the_prompt_file_name_and_8_hex_of_its_sha256(tmp_path):
    """A11 ("as now"), A9 and R8: the turn record holds the prompt version of
    config/agent_prompt_v2.md."""
    env = Env(tmp_path)
    reply = env.ask(QUESTION, END)
    pattern = prompt_version_pattern(AGENT_PROMPT_MD)
    record = turn_record(reply, env.runs_dir)
    assert any(isinstance(value, str) and pattern.fullmatch(value)
               for value in deep_leaves(record)), \
        "no prompt version for config/agent_prompt_v2.md in turn.json"
