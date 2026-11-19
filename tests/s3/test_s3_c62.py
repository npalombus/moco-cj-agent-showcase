"""C62 of docs/S3A-DESIGN.md (D-078): four things the threads showed after C61, and its fifth point
(kit-log/raw/CHAT-BUILDS-check-11.txt: DEFECT 1 with probes P19 and P20, PROOF GAP 1 with probes P18
and P18b). Brief: briefs/S3-R24-A-tests.md. Tests only; red until the planning chat builds C62,
except those that pin what stays (named "Passes today" in their docstrings and in
kit-log/raw/S3-R24-A-notes.txt).

All data is SYNTHETIC: the tests/s3 fixtures, test_s3_c54.py's juvenile-like copy of arrests_like,
and four made-up rows (FIXTURE-R24-...) for a second copy of arrests_like (the copy that "the daily
refresh" brings, dated 20 to 28 September 2026). No real figure is quoted. Every turn goes through
agent.handle_question with the model stand-in. The fixed texts are C62's, written out by hand in
s3support.py (C62_MAKER_WORDS, C62_MAKER_HINT, C62_REFUSAL, C62_PROMPT_SENTENCES).

Readings (also in the notes):
- R24-1 (point 1). "`found` holds the words": the REWRITE answer's `found` (T3: the model's own
  words, lower case, at most five) holds each of the four words the text holds outside the label,
  compared in lower case. "After the codes of today's check": `problems` is today's codes in
  today's order, then MAKER; `do` is, as today, the hint of the first code that has one.
- R24-2 (point 1). "Inside the label ... word for word": the label exactly as model_label gives it
  (it starts with a small "a"). The words inside it pass; the same words anywhere else fail, the
  label of another service included.
- R24-3 (point 2). "Was given in a turn": a count of this turn got the NOT_ALLOWED answer whose
  `why` ends with C61 point 10's sentence. The reply is the new sentence, one space, then today's
  rest of the row (county_can_ask), nothing else.
- R24-4 (point 4). "An about_data finish ... as kind about_data does": EXPLAINED, reply kind
  about_data, the same reply a finish of kind about_data with the same text gets (talk off and on,
  with T3's second try when talk is on).
- R24-5 (point 5a). `days` is a key of each count of the memory record (store.recent_turns): a list
  of two ISO date texts, [the source's coverage_start, the copy's newest record's day].
- R24-6 (point 5c). "A pair of dates": a tuple of two datetime.date (first day, last day).
- R24-7 (point 5b). "A remembered count with no days (stored before C62)": the test takes `days` out
  of the stored record in its own store (agent.db in tmp_path), as a record of before C62 looks.
"""
import json
import re
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

from p1support import THREAD_1, Env, Step, describe, finish, mod
from s3support import (A_ID, C61_EARLIER, C62_MAKER_HINT, C62_MAKER_WORDS, C62_PROMPT_SENTENCES,
                       C62_REFUSAL, C64_PROMPT_SENTENCES, COPY_NOW, NEWEST, Q_ABOUT, Q_COUNT,
                       CountyEnv, about_agent_fixture, count, county_fallback_line, dates,
                       fixture_rows, made_rows, turn_json, year)
from test_s3_c41 import CAN_ASK
from test_s3_c54 import J, call_of, two_sources
from test_s3_c56 import NOTE, World, down, standin
from test_s3_c57 import LABELS, NOTICES_SHOWN, full_notices, model_settings
from test_s3_c61b import C61_PROMPT_LINE, PROMPTS, SYNTHETIC_PROMPTS
from test_s3_c61d import (P05_FIRST, P05_SECOND, assert_answered, assert_refused,
                          assert_refused_turn, p05, turn)
from test_s3_round5 import A, NOT_ALLOWED_ROW, U17, U18, Y25, age, line1, phrase, spec

TESTS = Path(__file__).resolve().parents[1]
for folder in ("t", "s3s2"):
    if str(TESTS / folder) not in sys.path:
        sys.path.insert(0, str(TESTS / folder))

TALK = ["off", "on"]
PASSING = "Happy to help. Ask me for a count whenever you like."
NEMOTRON = "a Nemotron model made by NVIDIA"     # CountyEnv's settings: NVIDIA's default model
ACTIVE_LABEL = "a model served by Anthropic"      # test_s3_c56.World's active service
BACKUP_LABEL = "a model served by NVIDIA"         # test_s3_c56.World's backup
NEW_SENTENCE = f"{C62_REFUSAL} {CAN_ASK[1]}"      # R24-3, one source
OLD_SENTENCE = f"{NOT_ALLOWED_ROW} {CAN_ASK[1]}"


@pytest.fixture(autouse=True)
def _about_agent(tmp_path, monkeypatch):
    about_agent_fixture(tmp_path, monkeypatch)


def talk_env(tmp_path, monkeypatch, **values):
    return CountyEnv(tmp_path, monkeypatch, MOCO_TALK="on", **values)


def lower(words):
    return [str(w).lower() for w in words]


def talk_three_times(env, text, question="who made you?"):
    """C61 point 8: a county talk text that fails gets two REWRITEs, then the fallback."""
    return env.ask(question, Step(finish("talk", text)), Step(finish("talk", text)),
                   Step(finish("talk", text)), Step(finish("talk", PASSING)))


def rewrite(model, step=0):
    """Python's answer to the finish of model step `step`, or None when the turn ended there."""
    return model.answer(step) if len(model.calls) > step + 1 else None


def assert_maker(answer, words, codes=("MAKER",)):
    """R24-1: a REWRITE whose problems are `codes` (MAKER last) and whose `found` holds `words`."""
    assert answer is not None, "the text was sent: no REWRITE"
    assert answer.get("error") == "REWRITE", answer
    assert answer.get("problems") == list(codes), answer
    for word in words:
        assert word.lower() in lower(answer.get("found", [])), (word, answer)


def talk_turn_passes(env, text, question="who made you?"):
    reply = env.ask(question, Step(finish("talk", text)))
    assert (reply.status, reply.reply_style, reply.text) == ("TALKED", "agent", text), \
        (reply.reply_style, reply.draft_failures, reply.text)
    return reply


# ==== point 1: the maker's name =================================================================

@pytest.mark.parametrize("word", C62_MAKER_WORDS)
def test_p1_each_word_outside_the_label_fails_maker_and_is_not_sent(tmp_path, monkeypatch, word):
    """C62's test: a talk text with each of the four words outside the label fails MAKER (the only
    code: the same text with "Acme" in the word's place is sent), `found` holds the word, the hint
    is the `do`, and after two REWRITEs C61's county fallback is sent; the word is not."""
    env = talk_env(tmp_path / "acme", monkeypatch)
    talk_turn_passes(env, "I was built by the people at Acme.")
    env = talk_env(tmp_path / "word", monkeypatch)
    reply = talk_three_times(env, f"I was built by the people at {word}.")
    answer = rewrite(env.model)
    assert_maker(answer, [word])
    assert answer.get("do") == C62_MAKER_HINT, answer
    assert len(env.model.calls) == 3, "C61 point 8: two REWRITEs, then the fallback"
    assert (reply.status, reply.reply_kind, reply.reply_style) == ("TALKED", "talk", "fallback")
    assert reply.text == county_fallback_line(1), reply.text
    assert "MAKER" in reply.draft_failures, reply.draft_failures
    assert not re.search(rf"\b{word}\b", reply.text, re.I), reply.text
    record = env.store.recent_turns(THREAD_1, 100)[-1]
    assert not re.search(rf"\b{word}\b", str(record.get("sent")), re.I), record.get("sent")
    assert "MAKER" in turn_json(reply, env.runs_dir)["failures"]


@pytest.mark.parametrize("case", list(LABELS), ids=list(LABELS.values()))
def test_p1_inside_the_turns_own_label_it_passes(tmp_path, monkeypatch, case):
    """C62's test: the words inside the exact label of the turn's model pass, for each of C57's
    four labels. Passes today; must still pass."""
    env = talk_env(tmp_path, monkeypatch, **model_settings(*case))
    talk_turn_passes(env, f"I run on {LABELS[case]}. Ask me for a count whenever you like.",
                     "what model do you run on?")


def test_p1_the_backups_turn_has_the_backups_label(tmp_path, monkeypatch):
    """C62's test: in a second try of C56 the turn's model is the backup's. World's active service
    is "a model served by Anthropic" and its backup "a model served by NVIDIA": the backup's label
    passes (sent, with C56's note); the active service's label fails MAKER in the backup's turn."""
    world = World(tmp_path / "own", monkeypatch, "county", MOCO_TALK="on")
    own = f"I run on {BACKUP_LABEL}. Ask me for a count whenever you like."
    reply = world.ask("what model do you run on?", down(), standin(Step(finish("talk", own))))
    assert (reply.status, reply.reply_style) == ("TALKED", "agent"), \
        (reply.reply_style, reply.draft_failures, reply.text)
    assert reply.text == f"{own}\n{NOTE}", reply.text

    world = World(tmp_path / "active", monkeypatch, "county", MOCO_TALK="on")
    active = f"I run on {ACTIVE_LABEL}. Ask me for a count whenever you like."
    backup = standin(Step(finish("talk", active)), Step(finish("talk", active)),
                     Step(finish("talk", active)), Step(finish("talk", PASSING)))
    reply = world.ask("what model do you run on?", down(), backup)
    assert_maker(rewrite(backup), ["Anthropic"])
    assert reply.reply_style == "fallback" and "anthropic" not in reply.text.lower(), reply.text


def test_p1_chatgpt_and_openai_pass(tmp_path, monkeypatch):
    """C62's test: "Other names (ChatGPT, OpenAI) are not looked at." Passes today."""
    env = talk_env(tmp_path, monkeypatch)
    talk_turn_passes(env, "I am not ChatGPT, and OpenAI did not build me.")


ALL_FOUR = "I run on Claude from Anthropic, not on Nemotron from NVIDIA."


@pytest.mark.parametrize("kind", ["finding", "about_data"])
def test_p1_finding_and_about_data_texts_are_not_checked_for_it(tmp_path, monkeypatch, kind):
    """C62's test: a `finding` and an `about_data` text holding all four words outside any label
    are sent as written (style agent). Passes today; must still pass."""
    env = talk_env(tmp_path, monkeypatch)
    if kind == "finding":
        reply = env.ask(Q_COUNT, Step(count(A_ID, year(2025))),
                        Step(finish("finding", f"I counted {{r1.count}}. {ALL_FOUR}")))
        assert reply.status == "ANSWERED", (reply.status, reply.text)
    else:
        reply = env.ask(Q_ABOUT, Step(describe()),
                        Step(finish("about_data", f"Here is what I know. {{f1}}. {ALL_FOUR}")))
        assert reply.status == "EXPLAINED", (reply.status, reply.text)
    assert reply.reply_style == "agent", (reply.draft_failures, reply.text)
    assert ALL_FOUR in reply.text and "MAKER" not in reply.draft_failures, reply.text


def test_p1_the_hint():
    """C62's test: config/talk_rules.json's rewrite_hints holds MAKER's hint, word for word."""
    hints = mod("replies").load_talk_rules()["rewrite_hints"]
    assert hints.get("MAKER") == C62_MAKER_HINT, hints.get("MAKER")


# ---- this session's own tests (point 1) ----------------------------------------------------------

MAKER_FAILS = {"lower case": ("I run on claude, I think.", ["claude"]),
               "capitals": ("My maker is NEMOTRON.", ["nemotron"]),
               "mixed": ("Ask nViDiA or anthropic about it.", ["nvidia", "anthropic"])}
MAKER_PASSES = {"inside a longer word": "My friend Claudette says hello.",
                "another longer word": "The Nemotronic band plays tonight."}


@pytest.mark.parametrize("case", list(MAKER_FAILS) + list(MAKER_PASSES))
def test_own_1_whole_words_and_capitals_not_counting(tmp_path, monkeypatch, case):
    """Own 1 (point 1): "whole words, capitals not counting": the words in any case fail; a longer
    word that holds one of them passes."""
    env = talk_env(tmp_path, monkeypatch)
    if case in MAKER_PASSES:
        talk_turn_passes(env, MAKER_PASSES[case])
        return
    text, words = MAKER_FAILS[case]
    reply = talk_three_times(env, text)
    assert_maker(rewrite(env.model), words)
    assert reply.reply_style == "fallback", reply.text


def test_own_2_maker_comes_after_todays_codes(tmp_path, monkeypatch):
    """Own 2 (point 1): "after the codes of today's check": a text that fails LABEL (a label of the
    fixture, "group Gamma") and holds Claude gives problems [LABEL, MAKER]; `do` is LABEL's hint
    (the first code with one, as today); `found` holds both."""
    env = talk_env(tmp_path, monkeypatch)
    reply = talk_three_times(env, "Claude knows group Gamma.")
    answer = rewrite(env.model)
    assert_maker(answer, ["group gamma", "claude"], codes=("LABEL", "MAKER"))
    assert answer.get("do") == "Do not name a group or a place in your own words.", answer
    assert reply.reply_style == "fallback"


@pytest.mark.parametrize("case", [("nvidia", "nvidia/nemotron-3-ultra-550b-a55b"),
                                  ("anthropic", "claude-haiku-5-5")],
                         ids=["on NVIDIA, Anthropic's label", "on Anthropic, NVIDIA's label"])
def test_own_3_the_label_of_another_service_fails(tmp_path, monkeypatch, case):
    """Own 3 (point 1), R24-2: "inside the label of the turn's own model": the label of the other
    service is no shelter. On Nemotron, "a Claude model made by Anthropic" fails MAKER; on Claude,
    "a Nemotron model made by NVIDIA" does."""
    other = {"nvidia": ("a Claude model made by Anthropic", ["claude", "anthropic"]),
             "anthropic": (NEMOTRON, ["nemotron", "nvidia"])}
    label, words = other[case[0]]
    env = talk_env(tmp_path, monkeypatch, **model_settings(*case))
    reply = talk_three_times(env, f"I run on {label}. Ask me for a count whenever you like.")
    assert_maker(rewrite(env.model), words)
    assert reply.reply_style == "fallback", reply.text


def test_own_3b_the_label_and_the_word_again_outside_it(tmp_path, monkeypatch):
    """Own 3 (point 1), the other half of R24-2: the turn's own label, and the same word once more
    outside it, fails."""
    env = talk_env(tmp_path, monkeypatch)
    reply = talk_three_times(env, f"I run on {NEMOTRON}. Nemotron is a good name.")
    assert_maker(rewrite(env.model), ["nemotron"])
    assert reply.reply_style == "fallback", reply.text


# ==== point 2: the refusal that is about earlier figures =========================================

def test_p2_thread_p14_17_to_18_then_18(tmp_path, monkeypatch):
    """C62's test: thread P14's "17 to 18, then 18": the second is refused with C61's sentence in
    its `why`, and the reply's first sentence is C62's; nothing else of the row changes."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply, answers = turn(env, [spec(Y25, [age(17, 18)])], "how many aged 17 to 18 in 2025?")
    assert_answered(reply, answers)
    reply, (answer,) = turn(env, [spec(Y25, [age(18, 18)])], "just the 18 year olds")
    assert_refused_turn(env, reply, answer, before=1)
    assert reply.text == NEW_SENTENCE, reply.text


def test_p2_thread_p05_under_18_then_10_to_16(tmp_path, monkeypatch):
    """C62's test: thread P05's "under 18, then 10 to 16": the reply is the new sentence and the
    rest of the row."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply, (answer,) = p05(env)
    assert_refused_turn(env, reply, answer, before=1)
    assert reply.text == NEW_SENTENCE, reply.text


@pytest.mark.parametrize("earlier", ["first message", "after a count"])
def test_p2_a_single_age_asked_outright_keeps_the_old_sentence(tmp_path, monkeypatch, earlier):
    """C62's test: "how many 16 year olds were arrested in 2025?" is refused by its own count (no
    C61 sentence), as the first message of a thread and after P05's first message: the old row.
    Passes today; must still pass."""
    env = CountyEnv(tmp_path, monkeypatch)
    if earlier == "after a count":
        reply, answers = turn(env, [spec(Y25, [U18])], P05_FIRST)
        assert_answered(reply, answers)
    reply, (answer,) = turn(env, [spec(Y25, [age(16, 16)])],
                            "how many 16 year olds were arrested in 2025?")
    assert answer.get("error") == "NOT_ALLOWED" and C61_EARLIER not in answer.get("why", ""), answer
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", "NOT_ALLOWED"), reply.text
    assert reply.text == OLD_SENTENCE, reply.text


def test_own_4_kept_as_sent_and_not_used_when_the_turn_goes_on(tmp_path, monkeypatch):
    """Own 4 (point 2), R24-3 with C61 point 4: the refused turn's `sent` and its turn record hold
    the new sentence; a turn whose count got C61's sentence but that then made another count ends
    ANSWERED as today, with neither sentence (only the refusal's text changes)."""
    env = CountyEnv(tmp_path / "refused", monkeypatch)
    reply, (answer,) = p05(env)
    assert reply.text == NEW_SENTENCE, reply.text
    assert env.store.recent_turns(THREAD_1, 100)[-1].get("sent") == NEW_SENTENCE
    assert turn_json(reply, env.runs_dir)["reply"] == NEW_SENTENCE

    env = CountyEnv(tmp_path / "goes on", monkeypatch)
    reply, answers = turn(env, [spec(Y25, [U18])], P05_FIRST)
    assert_answered(reply, answers)
    reply = env.ask(P05_SECOND, Step(*[call_of(spec(Y25, [age(10, 16)])),
                                       call_of(spec(Y25, [age(10, 15)]))]),
                    Step(finish("finding", "I counted {r1.count}.")))
    assert_refused(env.model.answer(0, 0))
    assert reply.status == "ANSWERED", (reply.status, reply.text)
    assert line1(reply) == f"I counted {phrase(spec(Y25, [age(10, 15)]))}.", reply.text
    assert C62_REFUSAL not in reply.text and NOT_ALLOWED_ROW not in reply.text, reply.text


# ==== point 3: two sentences at the end of C61's line ============================================

def prompt_lines(path):
    return path.read_bytes().decode("utf-8").split("\n")


C62_LINE = f"{C61_PROMPT_LINE} {C62_PROMPT_SENTENCES}"
# Added by briefs/S3-R28-A-tests.md: C64 point 2's three sentences follow C62's two (one space).
C64_LINE = f"{C62_LINE} {C64_PROMPT_SENTENCES}"


def test_p3_the_two_sentences_word_for_word_once_in_place():
    """C62's test: in config/agent_prompt_s3_talk.md the line directly after rule 11 is C61's line,
    one space, and the two sentences; they are in the file once. Changed by
    briefs/S3-R28-A-tests.md (C64 point 2): the line goes on with one space and C64's three
    sentences (C64_LINE); it was C62_LINE, ending with the two."""
    lines = prompt_lines(PROMPTS["agent_prompt_s3_talk"])
    eleven = [i for i, line in enumerate(lines) if line.startswith("11. ")]
    assert len(eleven) == 1, "premise: one rule 11"
    assert lines[eleven[0] + 1] == C64_LINE, lines[eleven[0] + 1][-400:]
    assert "\n".join(lines).count(C62_PROMPT_SENTENCES) == 1
    assert "\n".join(lines).count("When someone asks what you answered earlier") == 1


def test_p3_not_in_the_other_county_prompt_nor_the_synthetic_ones():
    """Point 3 is about C61's line, which only the county talk prompt has (C61 correction 2).
    Passes today; must still pass."""
    for name, path in {"agent_prompt_s3": PROMPTS["agent_prompt_s3"],
                       **SYNTHETIC_PROMPTS}.items():
        text = path.read_bytes().decode("utf-8")
        assert "do not point back" not in text and "what you answered earlier" not in text, name


def test_p3_the_line_is_sent_with_talk_on(tmp_path, monkeypatch):
    """Point 3: a county turn with talk on is sent the line with the two sentences, once, after
    rule 11. Changed by briefs/S3-R28-A-tests.md (C64 point 2): the line ends with C64's three
    sentences after the two (C64_LINE); it was C62_LINE."""
    env = talk_env(tmp_path, monkeypatch)
    env.ask("hello", Step(finish("talk", PASSING)))
    system = env.model.calls[0]["messages"][0]["content"].split("\n")
    assert system.count(C64_LINE) == 1, [line[-200:] for line in system if "THREAD SO FAR" in line]
    assert system[system.index(C64_LINE) - 1].startswith("11. ")


def _hash_modules():
    import test_s2_r13
    import test_s3_c44
    import test_s3_c46
    return {"test_s3_c44": (test_s3_c44, "text_of"), "test_s3_c46": (test_s3_c46, "text_of"),
            "test_s2_r13": (test_s2_r13, "prompt")}


@pytest.mark.parametrize("module_name", ["test_s3_c44", "test_s3_c46", "test_s2_r13"])
def test_p3_the_prompt_hash_tests_take_them_out(monkeypatch, module_name):
    """C62's test "the prompt hash tests take them out": each prompt hash test, given the county
    talk prompt as C62 makes it (today's file with the two sentences at the end of C61's line),
    still finds today's sha256; given the two sentences anywhere else, it does not. The prompt is
    made in memory; no file is read but today's. Changed by briefs/S3-R28-A-tests.md (C64 point
    2): the line after rule 11 is made from whatever it is in the file (C61's line alone, with
    C62's two sentences, or with C64's three after them): as C62 makes it, and as C64 makes it,
    the hash is today's; with C62's two sentences elsewhere it is not. Before, the file's line was
    taken as C61's or C62's only, and a line with C64's sentences found no hash. Not changed by
    briefs/S3-R30-A-tests.md: with C66 built, today's file holds C66 point 2's sentences at the end
    of the line after rule 10, and the three modules' restored() now take them out
    (s3support.without_c66), so these three cases turn back with them."""
    import hashlib
    module, reader = _hash_modules()[module_name]
    real = getattr(module, reader)
    path = PROMPTS["agent_prompt_s3_talk"]
    today = path.read_bytes().decode("utf-8")
    assert today.count(C61_PROMPT_LINE) == 1, "premise: C61's line is in the file"
    (line_now,) = [line for line in today.split("\n") if line.startswith(C61_PROMPT_LINE)]
    as_c62 = today.replace(line_now, C62_LINE)
    as_c64 = today.replace(line_now, C64_LINE)
    elsewhere = today.replace(line_now, C61_PROMPT_LINE).replace(
        "\n11. ", f"\n{C62_PROMPT_SENTENCES}\n11. ", 1)
    for text, same in ((as_c62, True), (as_c64, True), (elsewhere, False)):
        def fake(arg, text=text):
            name = arg if isinstance(arg, str) else Path(arg).stem
            return text if name == "agent_prompt_s3_talk" else real(arg)
        monkeypatch.setattr(module, reader, fake)
        digest = hashlib.sha256(module.restored("agent_prompt_s3_talk").encode("utf-8")).hexdigest()
        assert (digest == module.TODAY_SHA256["agent_prompt_s3_talk"]) is same, (module_name, same)


# ==== point 4: the wrong kind of ending after describe_data ======================================

DISTRICTS = "what are the police districts in montgomery county"  # thread P10's message


def describe_then(env, kind, text, question=DISTRICTS):
    """describe_data, then a finish of `kind` (twice, for T3's second try when talk is on)."""
    return env.ask(question, Step(describe()), Step(finish(kind, text)), Step(finish(kind, text)))


def facts_of(env):
    (answer,) = [a for a in env.answers() if "facts" in a]
    return [f["text"] for f in answer["facts"]]


@pytest.mark.parametrize("talk", TALK)
def test_p4_a_finding_that_names_facts_and_fails_gets_9bs_reply(tmp_path, monkeypatch, talk):
    """C62's test: describe_data, then finish `finding` with a text that names {f3} and {f1} and
    fails (WORD): C61 addition 5's reply, `Here is what I know.` and the two facts in that order,
    then the notices in full; EXPLAINED, kind about_data, style fallback."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk)
    reply = describe_then(env, "finding", "Here is what I know. {f3}. {f1} zqx.")
    facts = facts_of(env)
    assert (reply.status, reply.reason_code, reply.reply_kind, reply.reply_style) == \
        ("EXPLAINED", None, "about_data", "fallback"), (reply.status, reply.reason_code, reply.text)
    assert reply.text == f"Here is what I know. {facts[2]} {facts[0]}\n" + "\n".join(
        full_notices(env, ("arrests_like",))), reply.text
    assert "WORD" in reply.draft_failures, reply.draft_failures


@pytest.mark.parametrize("talk", TALK)
def test_p4_a_finding_that_passes_is_sent_as_about_data(tmp_path, monkeypatch, talk):
    """C62's test: a passing text is sent, kind about_data: the same reply a finish of kind
    about_data with the same text gets in a thread of its own (R24-4)."""
    text = "Here is what I know. {f1}."
    twin = CountyEnv(tmp_path / "twin", monkeypatch, MOCO_TALK=talk)
    expected = describe_then(twin, "about_data", text)
    assert (expected.reply_style, expected.reply_kind) == ("agent", "about_data"), expected.text
    env = CountyEnv(tmp_path / "env", monkeypatch, MOCO_TALK=talk)
    reply = describe_then(env, "finding", text)
    assert (reply.status, reply.reason_code, reply.reply_kind, reply.reply_style) == \
        ("EXPLAINED", None, "about_data", "agent"), (reply.status, reply.reason_code, reply.text)
    assert reply.text == expected.text, reply.text
    assert reply.text.startswith(f"Here is what I know. {facts_of(env)[0]}\n"), reply.text


@pytest.mark.parametrize("talk", TALK)
def test_p4_a_finding_that_names_no_fact_and_fails_gets_the_fixed_about_text(tmp_path,
                                                                            monkeypatch, talk):
    """C62's test: a failing text that names no fact ({r1.count} is not a fact): the fixed about
    text, then the notices; EXPLAINED, kind about_data, style fallback."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk)
    reply = describe_then(env, "finding", "Here is what I know: {r1.count}.")
    srcs = mod("sources").county_sources()
    copies = {sid: mod("sources").latest(sid, state_dir=env.state_dir) for sid in srcs}
    fixed = mod("replies").county_about_text(srcs, copies)
    assert (reply.status, reply.reply_kind, reply.reply_style) == \
        ("EXPLAINED", "about_data", "fallback"), (reply.status, reply.reason_code, reply.text)
    assert reply.text == fixed + "\n" + "\n".join(full_notices(env, ("arrests_like",))), \
        reply.text


@pytest.mark.parametrize("talk", TALK)
def test_p4_with_a_result_kind_finding_is_as_today(tmp_path, monkeypatch, talk):
    """C62's test: describe_data, a count, then finish `finding`: ANSWERED, the finding as today.
    Passes today; must still pass."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk)
    reply = env.ask(Q_COUNT, Step(describe()), Step(count(A_ID, year(2025))),
                    Step(finish("finding", "I counted {r1.count}.")))
    assert (reply.status, reply.reply_kind, reply.reply_style) == ("ANSWERED", "finding", "agent"),\
        (reply.status, reply.reason_code, reply.text)
    assert line1(reply) == f"I counted {phrase(spec(Y25))}.", reply.text


@pytest.mark.parametrize("talk", TALK)
def test_p4_with_a_count_error_kind_finding_is_as_today(tmp_path, monkeypatch, talk):
    """C62's test: describe_data, a count refused (16 alone: NOT_ALLOWED), then finish `finding`
    that names a fact: the NOT_ALLOWED row as today. Passes today; must still pass."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk)
    reply = env.ask("how many 16 year olds were arrested in 2025?", Step(describe()),
                    Step(count(A_ID, year(2025), [age(16, 16)])),
                    Step(finish("finding", "Here is what I know. {f1}.")))
    assert env.model.answer(1).get("error") == "NOT_ALLOWED", env.model.answer(1)
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", "NOT_ALLOWED"), reply.text
    assert reply.text == OLD_SENTENCE, reply.text


def test_own_5_it_goes_through_county_about(tmp_path, monkeypatch):
    """Own 5 (point 4): "it goes through county_about", so C57 point 5 holds: the turn's memory
    record says about_data and "notices": "full", and the next about reply of the thread (a finish
    of kind finding after describe_data again) carries C57's one line instead of the notices."""
    env = CountyEnv(tmp_path, monkeypatch)
    first = describe_then(env, "finding", "Here is what I know. {f1}.")
    assert first.reply_kind == "about_data", (first.status, first.reason_code, first.text)
    record = env.store.recent_turns(THREAD_1, 100)[-1]
    assert (record["status"], record.get("reply_kind"), record.get("notices")) == \
        ("EXPLAINED", "about_data", "full"), record
    second = describe_then(env, "finding", "Here is what I know. {f2}.", question=Q_ABOUT)
    assert second.status == "EXPLAINED" and second.text.endswith("\n" + NOTICES_SHOWN), \
        (second.status, second.reason_code, second.text)


# ==== point 5: an earlier count keeps the days of its own copy ===================================

COPY_B_DAYS = ("2026-09-20", "2026-09-23", "2026-09-25", "2026-09-28")
NEWEST_B = date(2026, 9, 28)
FIRST_DAY = date(2024, 1, 1)                     # arrests_like's coverage_start
NEWEST_A = NEWEST["arrests_like"]                # 17 September 2026
Y26 = year(2026)
TO_17_SEP = dates("2026-01-01", "2026-09-17")


def copy_b_rows():
    """The fixture's rows and four SYNTHETIC rows of 20 to 28 September 2026 (ages 15, 17, 30
    and 45), as a refresh would bring them."""
    rows = made_rows(A, *[(1, {"event_date_time": f"{d}T10:00:00.000", "age": str(a)})
                          for d, a in zip(COPY_B_DAYS, (15, 17, 30, 45))], prefix="FIXTURE-R24-")
    return fixture_rows(A) + [r for r in rows if not r["id"].endswith("ANCHOR")]


def refresh(env):
    """Copy B becomes the current copy (the daily refresh between two messages)."""
    before = mod("sources").latest(A_ID, state_dir=env.state_dir)
    assert before.newest_day == NEWEST_A, "premise: copy A ends on 17 September 2026"
    made = env.fetch(A, rows=copy_b_rows(), now=COPY_NOW + timedelta(minutes=30))
    assert made.newest_day == NEWEST_B, made.newest_day
    assert mod("sources").latest(A_ID, state_dir=env.state_dir).newest_day == NEWEST_B


def forget_days(env):
    """R24-7: the stored records of the thread as before C62 (no `days` in a count)."""
    db = sqlite3.connect(env.tmp_path / "agent.db")
    try:
        for row_id, text in db.execute("SELECT id, record FROM agent_turns").fetchall():
            record = json.loads(text)
            for r in record.get("results") or []:
                r.pop("days", None)
            db.execute("UPDATE agent_turns SET record = ? WHERE id = ?",
                       (json.dumps(record), row_id))
        db.commit()
    finally:
        db.close()
    stored = [r for t in env.store.recent_turns(THREAD_1, 100) for r in t.get("results") or []]
    assert stored and not any("days" in r for r in stored), stored


def under_18_in_2026(env):
    reply, answers = turn(env, [spec(Y26, [U18])], "how many under 18 in 2026?")
    assert_answered(reply, answers)
    return reply


def test_p5_p19_the_copy_changed_under_17_to_the_old_last_day_is_refused(tmp_path, monkeypatch):
    """Point 5 b, the check's probe P19: under 18 in 2026 counted on copy A (to 17 September), copy
    B comes, then under 17 from 1 January to 17 September 2026: the earlier count is read with its
    own days, so the 17-year-olds of those days would follow: refused with C61's sentence."""
    env = CountyEnv(tmp_path, monkeypatch)
    under_18_in_2026(env)
    refresh(env)
    reply, (answer,) = turn(env, [spec(TO_17_SEP, [U17])], "and under 17 to 17 September 2026?")
    assert_refused_turn(env, reply, answer, before=1)


def test_p5_p20_the_copy_changed_under_17_in_2026_is_answered(tmp_path, monkeypatch):
    """Point 5 b, the check's probe P20: the same first message and copy B, then under 17 in 2026
    (now to 28 September): the two counts cover different days and give no single year:
    answered."""
    env = CountyEnv(tmp_path, monkeypatch)
    under_18_in_2026(env)
    refresh(env)
    reply, answers = turn(env, [spec(Y26, [U17])], "and under 17 in 2026?")
    assert_answered(reply, answers)


@pytest.mark.parametrize("second", ["under 17 in 2026", "under 17 to 17 September"])
def test_p5_the_same_pair_with_no_change_of_copy_is_refused_as_c61_has_it(tmp_path, monkeypatch,
                                                                         second):
    """Point 5's test: P19's and P20's second messages with no change of copy: both refused with
    C61's sentence, as C61 has it. Passes today; must still pass."""
    env = CountyEnv(tmp_path, monkeypatch)
    under_18_in_2026(env)
    period = Y26 if second == "under 17 in 2026" else TO_17_SEP
    reply, (answer,) = turn(env, [spec(period, [U17])], f"and {second}?")
    assert_refused(answer)
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", "NOT_ALLOWED"), reply.text


@pytest.mark.parametrize("second, refused", [("under 17 in 2026", True),
                                             ("under 17 to 17 September", False)])
def test_p5_a_remembered_count_with_no_days_is_read_with_this_turns_copy(tmp_path, monkeypatch,
                                                                         second, refused):
    """Point 5 b: a remembered count with no `days` (R24-7) is read with this turn's copy, as
    today: after copy B, under 17 in 2026 is refused and under 17 to 17 September answered.
    Passes today; must still pass."""
    env = CountyEnv(tmp_path, monkeypatch)
    under_18_in_2026(env)
    forget_days(env)
    refresh(env)
    period = Y26 if second == "under 17 in 2026" else TO_17_SEP
    reply, answers = turn(env, [spec(period, [U17])], f"and {second}?")
    if refused:
        assert_refused(answers[0])
        assert (reply.status, reply.reason_code) == ("UNSUPPORTED", "NOT_ALLOWED"), reply.text
    else:
        assert_answered(reply, answers)


def test_p5a_a_remembered_count_holds_the_days_of_its_copy(tmp_path, monkeypatch):
    """Point 5 a (R24-5): each count of the memory record holds `days`, the first and last day its
    copy covered when it was counted, as two ISO dates: copy A's for the first message, copy B's
    for the second."""
    env = CountyEnv(tmp_path, monkeypatch)
    under_18_in_2026(env)
    refresh(env)
    reply, answers = turn(env, [spec(Y26, [U17])], "and under 17 in 2026?")
    turns = env.store.recent_turns(THREAD_1, 100)
    days = [[r.get("days") for r in t["results"] if r["kind"] == "count"] for t in turns]
    assert days == [[[FIRST_DAY.isoformat(), NEWEST_A.isoformat()]],
                    [[FIRST_DAY.isoformat(), NEWEST_B.isoformat()]]], days


def checked(env, period, filters):
    srcs = mod("sources").county_sources()
    copy = mod("sources").latest(A_ID, state_dir=env.state_dir)
    raw = {"source": A_ID, "period": period, "filters": list(filters), "group_by": []}
    return srcs[A_ID], copy, mod("counting").check_spec(srcs[A_ID], copy, raw)


DAYS_A, DAYS_B = (FIRST_DAY, NEWEST_A), (FIRST_DAY, NEWEST_B)
DAYS_CASES = {  # (the second spec, days): one year of age under 18 follows
    "no days: both read with copy B": ("2026", None, True),
    "each entry None: as no days": ("2026", [None, None], True),
    "the first with copy A's days (P20)": ("2026", [DAYS_A, None], False),
    "both with copy A's days": ("2026", [DAYS_A, DAYS_A], True),
    "both with copy B's days, given": ("2026", [DAYS_B, DAYS_B], True),
    "P19: the first with copy A's days, the second to 17 September": ("to 17 Sep", [DAYS_A, None],
                                                                       True),
    "P19 today: no days": ("to 17 Sep", None, False),
}


@pytest.mark.parametrize("case", list(DAYS_CASES))
def test_p5c_one_year_under_18_with_days(tmp_path, monkeypatch, case):
    """Point 5 c: counting.one_year_under_18(source, specs, copy, days), with copy B: `days` a list
    as long as `specs`, each entry None (the copy) or a pair of dates (R24-6). Under 18 in 2026,
    then under 17 in 2026 or to 17 September."""
    env = CountyEnv(tmp_path, monkeypatch)
    refresh(env)
    second, days, expected = DAYS_CASES[case]
    source, copy, first = checked(env, Y26, [U18])
    _, _, other = checked(env, Y26 if second == "2026" else TO_17_SEP, [U17])
    check = mod("counting").one_year_under_18
    kwargs = {} if days is None else {"days": days}
    assert check(source, [first, other], copy, **kwargs) is expected, case


def test_p5_p18_another_sources_earlier_count_is_never_read_into_this_sources_check(
        tmp_path, monkeypatch):
    """Point 5, PROOF GAP 1, the check's probe P18 (P18b is its first two messages on the break
    K61D-2): arrests aged 17 to 18 in 2025, then juvenile records in 2025 (usable ages 10 to 17),
    then juvenile records aged 10 to 16 in 2025: answered, answered, refused with C61's sentence.
    Read with the juvenile ages, the arrests count would be the single year 17 and refuse the
    second message. Passes today; fails on K61D-2 (kit-log/raw/S3-R24-A-breaks.txt)."""
    env = two_sources(tmp_path, monkeypatch)
    for s, question in ((spec(Y25, [age(17, 18)]), "arrests aged 17 to 18 in 2025"),
                        (spec(Y25, [], name=J), "juvenile records in 2025")):
        reply, answers = turn(env, [s], question)
        assert_answered(reply, answers)
    reply, (answer,) = turn(env, [spec(Y25, [age(10, 16)], name=J)], "juvenile aged 10 to 16")
    assert_refused(answer)
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", "NOT_ALLOWED"), reply.text


def test_own_6_each_count_with_its_own_copys_days_in_either_order(tmp_path, monkeypatch):
    """Own 6 (point 5 b): P20 the other way round. Under 17 in 2026 on copy A, copy B comes, then
    under 18 in 2026 (to 28 September): different days, answered. Then under 17 in 2026 again, on
    copy B: with the second message's count (same copy, same days) it gives the 17-year-olds:
    refused with C61's sentence."""
    env = CountyEnv(tmp_path, monkeypatch)
    reply, answers = turn(env, [spec(Y26, [U17])], "how many under 17 in 2026?")
    assert_answered(reply, answers)
    refresh(env)
    reply, answers = turn(env, [spec(Y26, [U18])], "and under 18 in 2026?")
    assert_answered(reply, answers)
    reply, (answer,) = turn(env, [spec(Y26, [U17])], "and under 17 in 2026 again?")
    assert_refused_turn(env, reply, answer, before=2)


# ==== county mode only ===========================================================================

def test_own_7_synthetic_mode_is_untouched(tmp_path):
    """Own 7: C62 is county mode only ("Why: ... County mode only"). In SYNTHETIC mode a talk text
    that names Anthropic is sent as today, and a finish of kind finding after describe_data with no
    count still ends UNRECOGNIZED_QUESTION. Passes today; must still pass."""
    for folder in ("talk", "finding"):
        (tmp_path / folder).mkdir()
    env = Env(tmp_path / "talk", MOCO_TALK="on")
    text = "I was made by Anthropic. Ask me for a count whenever you like."
    reply = env.ask("who made you?", Step(finish("talk", text)))
    assert (reply.status, reply.reply_style, reply.text) == ("TALKED", "agent", text), \
        (reply.draft_failures, reply.text)
    env = Env(tmp_path / "finding")
    reply = env.ask("what data do you have?", Step(describe()),
                    Step(finish("finding", "Here is what I know. {f1}.")))
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", "UNRECOGNIZED_QUESTION"), \
        (reply.status, reply.reason_code, reply.text)


# ==== round 25 (briefs/S3-R25-A-tests.md): two of the planning chat's answers to S3-R24-A ========
# Answer 3: every text sent as talk is checked for MAKER, a plain text read as talk included (T1,
# T13). Answer 2: a `days` entry of two ISO date texts (the memory record's form, 5a) is taken by
# counting.one_year_under_18 and means what two datetime.date mean.

NOTE_HEAD = "PROGRAM NOTE (not from the person). Your reply was not sent. "  # T13


def notes(model):
    """T13: the REWRITE objects Python gave as PROGRAM NOTEs, in order (the last call's messages
    hold every earlier one)."""
    return [json.loads(m["content"][len(NOTE_HEAD):]) for m in model.calls[-1]["messages"]
            if m.get("role") == "user" and str(m.get("content")).startswith(NOTE_HEAD)]


def plain_talk_is_sent(env, text, question="who made you?"):
    reply = env.ask(question, Step(text=text))
    assert (reply.status, reply.reply_kind, reply.reply_style, reply.text) == \
        ("TALKED", "talk", "agent", text), (reply.reply_style, reply.draft_failures, reply.text)
    assert len(env.model.calls) == 1, "a passing plain text got a PROGRAM NOTE"
    return reply


@pytest.mark.parametrize("word", C62_MAKER_WORDS)
def test_r25_a_plain_text_read_as_talk_with_a_word_outside_the_label_fails_maker(
        tmp_path, monkeypatch, word):
    """Answer 3: with talk on in county mode, a plain text with no tool call (read as talk, T1)
    that holds a maker's word outside the turn's own label fails MAKER and is not sent. The same
    text with "Acme" in the word's place is sent, so MAKER is the only code; each of the two
    PROGRAM NOTEs (T13, C61 point 8's third try) has problems [MAKER], `found` the word and the
    hint as `do`; then C61's county fallback is sent, and the word is neither sent nor kept."""
    acme = talk_env(tmp_path / "acme", monkeypatch)
    plain_talk_is_sent(acme, "I was built by the people at Acme.")
    env = talk_env(tmp_path / "word", monkeypatch)
    text = f"I was built by the people at {word}."
    reply = env.ask("who made you?", Step(text=text), Step(text=text), Step(text=text),
                    Step(text=PASSING))
    assert len(env.model.calls) == 3, "C61 point 8: two notes, then the fallback"
    given = notes(env.model)
    assert len(given) == 2, given
    for answer in given:
        assert_maker(answer, [word])
        assert answer.get("do") == C62_MAKER_HINT, answer
    assert (reply.status, reply.reply_kind, reply.reply_style) == ("TALKED", "talk", "fallback")
    assert reply.text == county_fallback_line(1), reply.text
    assert "MAKER" in reply.draft_failures, reply.draft_failures
    assert not re.search(rf"\b{word}\b", reply.text, re.I), reply.text
    record = env.store.recent_turns(THREAD_1, 100)[-1]
    assert not re.search(rf"\b{word}\b", str(record.get("sent")), re.I), record.get("sent")
    assert "MAKER" in turn_json(reply, env.runs_dir)["failures"]


@pytest.mark.parametrize("case", list(LABELS), ids=list(LABELS.values()))
def test_r25_a_plain_text_with_the_words_only_inside_the_exact_label_is_sent(tmp_path,
                                                                             monkeypatch, case):
    """Answer 3: the same plain text with the words only inside the exact label of the turn's own
    model (each of C57's four labels) passes and is sent as written, with no PROGRAM NOTE."""
    env = talk_env(tmp_path, monkeypatch, **model_settings(*case))
    plain_talk_is_sent(env, f"I run on {LABELS[case]}. Ask me for a count whenever you like.",
                       "what model do you run on?")


def test_r25_a_plain_text_in_synthetic_mode_is_not_checked_for_maker(tmp_path):
    """Answer 3 with "County mode only": in SYNTHETIC mode with talk on, a plain text that names
    all four words is read as talk and sent as written, with no PROGRAM NOTE."""
    env = Env(tmp_path, MOCO_TALK="on")
    text = f"{ALL_FOUR} Ask me for a count whenever you like."
    reply = env.ask("who made you?", Step(text=text), Step(text=PASSING))
    assert (reply.status, reply.reply_kind, reply.reply_style, reply.text) == \
        ("TALKED", "talk", "agent", text), (reply.draft_failures, reply.text)
    assert len(env.model.calls) == 1 and not notes(env.model), "it got a PROGRAM NOTE"
    assert "MAKER" not in reply.draft_failures, reply.draft_failures


ISO_DAYS_A = [d.isoformat() for d in DAYS_A]     # copy A's days as the memory record holds them
ISO_CASES = {"allows (P20: under 17 in 2026)": ("2026", False),
             "refuses (P19: under 17 to 17 September)": ("to 17 Sep", True)}


@pytest.mark.parametrize("case", list(ISO_CASES))
def test_r25_one_year_under_18_takes_a_days_entry_of_two_iso_date_texts(tmp_path, monkeypatch,
                                                                       case):
    """Answer 2: with copy B, under 18 in 2026 counted on copy A, then under 17: a `days` entry of
    two ISO date texts (5a's form) gives what the same entry as two datetime.date gives, for a
    pair that is allowed and a pair that is refused."""
    env = CountyEnv(tmp_path, monkeypatch)
    refresh(env)
    second, expected = ISO_CASES[case]
    source, copy, first = checked(env, Y26, [U18])
    _, _, other = checked(env, Y26 if second == "2026" else TO_17_SEP, [U17])
    check = mod("counting").one_year_under_18
    as_dates = check(source, [first, other], copy, days=[DAYS_A, None])
    assert as_dates is expected, "premise: the entry as two datetime.date"
    as_texts = check(source, [first, other], copy, days=[ISO_DAYS_A, None])
    assert as_texts is as_dates, (case, ISO_DAYS_A)


# ==== round 27 (briefs/S3-R27-A-tests.md): check 12's PROOF GAP 1, and the answer after check 12 ==
# Step 3, PROOF GAP 1 of kit-log/raw/CHAT-BUILDS-check-12.txt (point 2): a turn refused by C21 on
# its OWN counts, with nothing of the thread as the cause, keeps the old first sentence (the
# check's probes Q08a and Q08b); its break M3 (the new sentence for every refusal of C21's check)
# passed the whole suite. Where the thread's earlier count IS the cause, the new sentence is
# already pinned by test_p2_thread_p05_under_18_then_10_to_16 and test_p2_thread_p14_17_to_18_
# then_18 above. Step 4, "C62, one more answer, after CHAT-BUILDS-check-12" (point 1): the label
# is the label too with a capital first letter; any other capital, or a word missing, and its
# maker's words count as outside it.

C21_WHY = "with this count, the figures of this message would give one year of age under 18"
BAND_17_TO_20 = spec(Y25, [age(17, 20)], ["age_band"])   # C21's own example: the band 10 to 17
Q08 = "how many aged 17 to 20 were arrested in 2025, by age band?"


@pytest.mark.parametrize("talk", TALK)
@pytest.mark.parametrize("earlier", ["first message (Q08a)", "after 18 to 24 (Q08b)"])
def test_r27_refused_on_its_own_counts_keeps_the_old_sentence(tmp_path, monkeypatch, earlier,
                                                              talk):
    """PROOF GAP 1 (C62 point 2): 17 to 20 by age band in 2025 is refused by C21 on its own counts
    (the band 10 to 17 cut to 17), with C21's `why` alone: as a thread's first message (Q08a), and
    after an answered count that is not the cause, 18 to 24 in 2025 (Q08b). The reply is the old
    first sentence and the rest of the row, word for word, never C62's sentence; `sent` and the
    turn record hold the same. Fails on check 12's break M3 (kit-log/raw/S3-R27-A-breaks.txt)."""
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk)
    before = 0
    if earlier.startswith("after"):
        reply, answers = turn(env, [spec(Y25, [age(18, 24)])], "how many aged 18 to 24 in 2025?")
        assert_answered(reply, answers)
        before = 1
    reply, (answer,) = turn(env, [BAND_17_TO_20], Q08)
    assert_refused_turn(env, reply, answer, before=before, why=C21_WHY)
    assert reply.text == OLD_SENTENCE, reply.text
    assert C62_REFUSAL not in reply.text, reply.text
    assert env.store.recent_turns(THREAD_1, 100)[-1].get("sent") == OLD_SENTENCE
    assert turn_json(reply, env.runs_dir)["reply"] == OLD_SENTENCE


def capital(label):
    return label[:1].upper() + label[1:]


def other_capital(label, word):
    """The label with a capital first letter and `word` of it written with a capital too."""
    return " ".join(w.capitalize() if w == word else w for w in capital(label).split(" "))


def left_out(label, n):
    """The label with a capital first letter and its word number n (from 0) left out."""
    words = label.split(" ")
    return capital(" ".join(words[:n] + words[n + 1:]))


def makers_of(text):
    return [w for w in C62_MAKER_WORDS if re.search(rf"\b{w}\b", text, re.I)]


CASES = list(LABELS)
CASE_IDS = list(LABELS.values())


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_r27_the_label_with_a_capital_first_letter_is_sent(tmp_path, monkeypatch, case):
    """The answer after check 12 (its reading 2, probe Q03): with talk on in county mode, a talk text
    that begins a sentence with the turn's own label, its first letter a capital ("A Claude model
    made by Anthropic runs me."), is sent as written, for each of C57's four labels; the second
    text has it at the start of its second sentence. Fails on the wrong build "the capital form not
    sheltered" (kit-log/raw/S3-R27-A-breaks.txt)."""
    label = capital(LABELS[case])
    for n, text in enumerate([f"{label} runs me.",
                              f"Ask me for a count whenever you like. {label} runs me."]):
        env = talk_env(tmp_path / str(n), monkeypatch, **model_settings(*case))
        talk_turn_passes(env, text, "what model do you run on?")


def label_variants(label):
    """Variants of the label that are not the label: another capital inside it, or a word left
    out (the first word; the word before "by")."""
    by = label.split(" ").index("by")
    return {"Model with a capital": other_capital(label, "model"),
            "By with a capital": other_capital(label, "by"),
            "the first word left out": left_out(label, 0),
            f"{label.split(' ')[by - 1]} left out": left_out(label, by - 1)}


VARIANTS = [(case, name) for case in CASES for name in label_variants(LABELS[case])]


@pytest.mark.parametrize("case, name", VARIANTS,
                         ids=[f"{LABELS[c]}: {n}" for c, n in VARIANTS])
def test_r27_another_capital_or_a_word_left_out_fails_maker(tmp_path, monkeypatch, case, name):
    """The answer after check 12: "Nothing else of it may differ: any other capital, or a word
    missing, and its maker's words count as outside the label": the turn's own label with another
    capital inside it, or with a word left out, at the start of a sentence fails MAKER (the only
    code), `found` holds its maker's words, and C61's county fallback is sent."""
    text = f"{label_variants(LABELS[case])[name]} runs me."
    assert text != f"{capital(LABELS[case])} runs me.", "premise: not the label"
    env = talk_env(tmp_path, monkeypatch, **model_settings(*case))
    reply = talk_three_times(env, text, "what model do you run on?")
    assert_maker(rewrite(env.model), makers_of(text))
    assert (reply.reply_style, reply.text) == ("fallback", county_fallback_line(1)), reply.text


OTHERS = [(case, other) for case in CASES for other in CASES if other != case]


@pytest.mark.parametrize("case, other", OTHERS,
                         ids=[f"on {LABELS[c]}: {capital(LABELS[o])}" for c, o in OTHERS])
def test_r27_another_models_label_with_a_capital_first_letter_fails_maker(tmp_path, monkeypatch,
                                                                         case, other):
    """The answer after check 12, with R24-2: the capital first letter shelters only the turn's own
    label. The label of another service (or of the same service's other model), its first letter a
    capital, at the start of a sentence fails MAKER (the only code), and the fallback is sent."""
    text = f"{capital(LABELS[other])} runs me."
    env = talk_env(tmp_path, monkeypatch, **model_settings(*case))
    reply = talk_three_times(env, text, "what model do you run on?")
    assert_maker(rewrite(env.model), makers_of(text))
    assert (reply.reply_style, reply.text) == ("fallback", county_fallback_line(1)), reply.text
