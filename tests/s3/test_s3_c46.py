"""Stage 3 Part A, C46 (docs/S3A-DESIGN.md): "this year" is today's year. In both county prompts
(config/agent_prompt_s3.md and config/agent_prompt_s3_talk.md), rule 1's sentence `Never guess a
year.` is followed, in the same line, by one sentence; nothing else changes; the SYNTHETIC prompts
do not get it. Brief: briefs/S3-R12-A-tests.md. Tests only; the planning chat makes the change.
No data is read.

C46's tests: the sentence word for word, once, in both county prompts, straight after "Never guess
a year."; not in the SYNTHETIC prompts; the rest of each prompt as before.

READINGS (also in kit-log/raw/S3-R12-A-notes.txt):
- C46-1. "Word for word": point 1's text between its backticks, with its leading space and its
  straight quotation marks and apostrophe, found once in the whole file. "Straight after ... in
  the same line": rule 1's line (the one line starting "1. ") is today's rule 1 (written out here
  by hand, ending "Never guess a year.") with the sentence added at its end, and nothing else.
- C46-2. "Nothing else changes": the file with the sentence taken out from that place only has
  the sha256 of today's file (the files of commit f441244, 2026-11-16, last changed in 82be7c6,
  written here by hand). C40 amendment 2, C41 and C44, which earlier rounds had to put back, are
  built in those files, so nothing else is put back. Passes today; fails if anything else
  changes. Test (e) of tests/s3s2/test_s2_r13.py and C44's test of tests/s3/test_s3_c44.py check
  the same against their older files; both were changed in this round to take the sentence out.
  Changed by briefs/S3-R24-A-tests.md: without_c61() also takes out C62 point 3's two sentences
  at the end of C61's line (the line is taken out whether it ends with them or not).
  Changed by briefs/S3-R28-A-tests.md: without_c61() also takes out C64 point 2's three sentences
  after C62's two (the line is taken out as C61's, C61's and C62's, or C61's, C62's and C64's).
- C46-3. "The SYNTHETIC prompts": agent_prompt_talk, agent_prompt_v2, agent_prompt_v1 and
  system_prompt_v1 (as test_s3_c41.py and test_s3_c44.py list them). system_prompt_v1 has its own
  older wording about "this year" (its rule 6); it is not C46's sentence and is not looked at.
- C46-4. The prompt is sent as it is (T0, C0): a county turn's system message holds rule 1 with
  the sentence, with talk off and on, and today's date (the system message's "Today's date:" line,
  which the sentence relies on); a SYNTHETIC turn's does not hold the sentence.
- C46-5. Point 2's "C7's partial year applies as today" is not a change and is not tested here
  (C7's own tests stand).
"""
import hashlib
from pathlib import Path

import pytest

import p1support as p1
from p1support import Step, decline
from s3support import TODAY_S3, CountyEnv, without_c66, without_c74
from support import SUPPORTED

REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "config"
COUNTY = {"agent_prompt_s3": CONFIG / "agent_prompt_s3.md",
          "agent_prompt_s3_talk": CONFIG / "agent_prompt_s3_talk.md"}
SYNTHETIC = {"agent_prompt_talk": CONFIG / "agent_prompt_talk.md",
             "agent_prompt_v2": CONFIG / "agent_prompt_v2.md",
             "agent_prompt_v1": CONFIG / "agent_prompt_v1.md",
             "system_prompt_v1": CONFIG / "system_prompt_v1.md"}

# ---- C46's sentence, and rule 1 of today, written out by hand -----------------------------------

NEVER = "Never guess a year."
# Point 1, between its backticks: it starts with a space.
SENTENCE = (' "This year" is the year of today\'s date, even before it ends, and "last year" is '
            'the year before it.')
RULE_1_TODAY = (
    "1. A question about how many: call count. Give the source only if more than one is listed "
    "and the message says which; otherwise leave it out. Give the period only if the message "
    "states it; otherwise leave it out and the program fills it in from the thread or asks. "
    "Never guess a year.")
RULE_1_C46 = RULE_1_TODAY + SENTENCE

# C46-2: sha256 of the files of commit f441244 (2026-11-16; last changed in 82be7c6).
TODAY_SHA256 = {
    "agent_prompt_s3": "d017b179b21df664b4630144d49a060ff9877b1c6e21ba14a8eef14565f37b1f",
    "agent_prompt_s3_talk": "5403e0f3a2cdee8f612dd0096a77ed4188275f3d1cb8cdb4748224d81fb9b778",
}


def text_of(path):
    return path.read_bytes().decode("utf-8")


def rule_1(name):
    # S3A C74 (D-091, the planning chat): C74's sentence in rule 1 of the talk prompt is taken out
    found = [line for line in without_c74(text_of(COUNTY[name])).split("\n")
             if line.startswith("1. ")]
    assert len(found) == 1, f"{name}: {len(found)} lines start with '1. '"
    return found[0]


def test_premise_the_sentence_is_one_sentence_with_a_leading_space():
    assert SENTENCE.startswith(' "This year"') and SENTENCE.endswith(".")
    assert p1.sentences(SENTENCE) == [SENTENCE.strip()]


@pytest.mark.parametrize("name", list(COUNTY))
def test_premise_never_guess_a_year_is_once_in_each_county_prompt_and_ends_rule_1(name):
    assert text_of(COUNTY[name]).count(NEVER) == 1, name
    assert rule_1(name) in (RULE_1_TODAY, RULE_1_C46), rule_1(name)


@pytest.mark.parametrize("name", list(COUNTY))
def test_the_sentence_word_for_word_once_straight_after_never_guess_a_year(name):
    text = text_of(COUNTY[name])
    assert text.count(SENTENCE) == 1, f"{name}: C46's sentence is not in the file once"
    assert text.count(NEVER + SENTENCE) == 1, f"{name}: the sentence is not straight after NEVER"


@pytest.mark.parametrize("name", list(COUNTY))
def test_rule_1_is_todays_with_the_sentence_at_its_end(name):
    """C46-1: in the same line, and nothing else in rule 1 changed."""
    assert rule_1(name) == RULE_1_C46, rule_1(name)


@pytest.mark.parametrize("name", list(SYNTHETIC))
def test_the_sentence_is_not_in_the_synthetic_prompts(name):
    text = text_of(SYNTHETIC[name])
    assert SENTENCE.strip() not in text, name
    assert "is the year of today's date" not in text and "even before it ends" not in text, name


# C61 point 7 with "C61, two additions after the threads" point 6 (docs/S3A-DESIGN.md), written out
# by hand; added by briefs/S3-R23-A-tests.md. In the county talk prompt only (correction 2), one
# line directly after the line that begins "11. ".
C61_LINE = (
    'THREAD SO FAR also shows what you said ("You said:"). Stay consistent with it: never deny or '
    "change something you said unless it was wrong, and then say so once. You may point back to a "
    'figure you gave ("the figure I gave for district 4"), but never write, add, subtract or judge '
    "a figure yourself: figures come only from this turn's slots. If the thread says earlier "
    "messages are not shown, say that you only see the recent part when someone asks about them. "
    "Before you decline, or say that you do not know something about the data or about yourself, "
    "call describe_data and read its facts: decline only when no fact answers the question.")


# C62 point 3 (docs/S3A-DESIGN.md), written out by hand; added by briefs/S3-R24-A-tests.md: two
# sentences at the end of C61's line (after one space), in the county talk prompt only.
C62_SENTENCES = (
    "When someone asks which of several figures you gave is the highest or lowest, or what the "
    "difference is, do not point back: count them again in one count with a breakdown, or count "
    "each and call compare, and let the slots say it. When someone asks what you answered "
    "earlier, make the same count again and give it.")


# C64 point 2 (docs/S3A-DESIGN.md), written out by hand; added by briefs/S3-R28-A-tests.md: three
# sentences at the end of C61's line, after C62's two (one space before), county talk prompt only.
C64_SENTENCES = (
    "When THREAD SO FAR says that earlier messages are not shown, you do not know how the "
    "conversation began. Never call a message, a question or a count the first, also when you "
    "count it again: call it the earliest one still shown to you. When asked for the first one, "
    "or for everything said or counted so far, say in your text that the start of the "
    "conversation is no longer shown to you, and go by what is shown.")


def without_c61(text):
    """The text with C61's line taken out from its place only (straight after rule 11). Changed by
    briefs/S3-R24-A-tests.md: C62 point 3's two sentences at the end of that line are taken out
    with it (the line is C61's alone before C62, C61's and C62's after). Changed by
    briefs/S3-R28-A-tests.md: so are C64 point 2's three sentences after C62's two (the line is
    C61's, C62's and C64's after C64)."""
    lines = text.split("\n")
    eleven = [i for i, line in enumerate(lines) if line.startswith("11. ")]
    if len(eleven) == 1 and eleven[0] + 1 < len(lines) and \
            lines[eleven[0] + 1] in (C61_LINE, f"{C61_LINE} {C62_SENTENCES}",
                                     f"{C61_LINE} {C62_SENTENCES} {C64_SENTENCES}"):
        del lines[eleven[0] + 1]
    return "\n".join(lines)


# "C57, the exact prompt texts" and C60 (docs/S3A-DESIGN.md), written out by hand (as
# tests/s3s2/test_s2_r13.py has them); added by briefs/S3-R23-A-tests.md.
START_LINE = ('- Start with "Here is what I know." and nothing else before the slots. Never write '
              'a fact in your own words. Write it all on one line.')
C57_LINE = ('- For a question about which sources or what data there is, use the fact that names '
            'every source. For what a field means or where the records come from, use the fact '
            'that says so.')
RULE12_TODAY = "a question about you or about what you can do"
RULE12_C57 = "a question about you (what you are, what model you run on) or about what you can do"
RULE3_END = "never make one count per group yourself."
C60_RULE3 = (' When the message asks for a figure for two or more years it names ("how many in '
             '2024 and 2025"), make one count over those years with group_by year, so each year '
             'gets its own figure.')
ANALYZE_ANCHOR = "with no period the program uses every month it has."
C60_ANALYZE = (' "The past five years" or "the last three years" names one: from the same month '
               'that many years back; call analyze once for it, never twice.')


def without_c57_c60_c61(name, text):
    """C57's line and (talk prompt) rule 12, C60's two sentences and (talk prompt) C61's line
    taken out, each from its place only."""
    if name == "agent_prompt_s3_talk":
        text = without_c61(text).replace(RULE12_C57, RULE12_TODAY)
    text = text.replace(f"{START_LINE}\n{C57_LINE}\n", f"{START_LINE}\n")
    text = text.replace(RULE3_END + C60_RULE3, RULE3_END)
    return text.replace(ANALYZE_ANCHOR + C60_ANALYZE, ANALYZE_ANCHOR)


def restored(name):
    """C46-2: the sentence taken out from its place only. Changed by briefs/S3-R23-A-tests.md:
    C57's line and rule 12 change (talk prompt), C60's two sentences and C61's line after rule 11
    (talk prompt) are taken out too, each from its place only. Changed by
    briefs/S3-R30-A-tests.md (C66 point 2): in the county talk prompt, C66's two sentences at the
    end of C41's line (the line after rule 10) are taken out too, from that place only
    (s3support.without_c66); before, nothing was taken out there."""
    text = text_of(COUNTY[name]).replace(NEVER + SENTENCE, NEVER, 1)
    if name == "agent_prompt_s3_talk":
        text = without_c66(text)
    return without_c57_c60_c61(name, text)


@pytest.mark.parametrize("name", list(COUNTY))
def test_the_rest_of_each_prompt_as_before(name):
    text = restored(name)
    assert SENTENCE not in text and "even before it ends" not in text, \
        f"C46's sentence is in {name} somewhere else as well"
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert digest == TODAY_SHA256[name], f"{name} without C46's sentence is not today's file"


# ---- C46-4: the sentence is sent -----------------------------------------------------------------

@pytest.mark.parametrize("talk", ["off", "on"])
def test_a_county_turn_is_sent_rule_1_with_the_sentence_and_todays_date(tmp_path, monkeypatch,
                                                                       talk):
    env = CountyEnv(tmp_path, monkeypatch, MOCO_TALK=talk)
    env.ask("How many arrests were there this year?", Step(decline("UNRECOGNIZED_QUESTION")))
    system = env.model.calls[0]["messages"][0]
    assert system["role"] == "system"
    sent = without_c74(system["content"]).split("\n")  # S3A C74 (D-091)
    assert sent.count(RULE_1_C46) == 1, f"talk {talk}: rule 1 with C46's sentence was not sent"
    assert system["content"].count(SENTENCE) == 1
    assert f"Today's date: {TODAY_S3:%Y-%m-%d}" in sent, "premise: the date is given"


@pytest.mark.parametrize("talk", ["off", "on"])
def test_a_synthetic_turn_is_not_sent_the_sentence(tmp_path, talk):
    env = p1.Env(tmp_path, MOCO_TALK=talk)
    env.ask(SUPPORTED["S1"][0], Step(decline("UNSUPPORTED_FIELD")))
    assert env.model.calls, "premise: the model was called"
    content = env.model.calls[0]["messages"][0]["content"]
    assert SENTENCE.strip() not in content and "even before it ends" not in content
