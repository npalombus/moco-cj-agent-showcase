"""C60 of docs/S3A-DESIGN.md: two sentences in the county prompts, tried live. Brief:
briefs/S3-R21-A-tests.md (the part added 17 Nov 15:37 EST). Tests only; the planning chat edits
config/agent_prompt_s3.md and config/agent_prompt_s3_talk.md. Red until then.

C60's test "each sentence is in each prompt once, in its place" is here; its other test (the
hash tests take C57's line, rule 12's change and C60's two sentences out before they compare)
is tests/s3s2/test_s2_r13.py, changed by this brief.

Readings (also in kit-log/raw/S3-R21-A-notes.txt):
- R21-C60-1. "After X, one more sentence": in the same line, X, one space, the sentence; the
  line goes on after it as today (C46's sentence is read the same way in test_s2_r13.py).
- R21-C60-2. The sentences are copied from the contract by hand, with its straight quotes.
"""
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PROMPTS = {"agent_prompt_s3": REPO / "config" / "agent_prompt_s3.md",
           "agent_prompt_s3_talk": REPO / "config" / "agent_prompt_s3_talk.md"}

RULE3_END = "never make one count per group yourself."
C60_RULE3 = ('When the message asks for a figure for two or more years it names ("how many in 2024 '
             'and 2025"), make one count over those years with group_by year, so each year gets '
             'its own figure.')
ANALYZE_ANCHOR = "with no period the program uses every month it has."
C60_ANALYZE = ('"The past five years" or "the last three years" names one: from the same month '
               'that many years back; call analyze once for it, never twice.')


def text(name):
    return PROMPTS[name].read_bytes().decode("utf-8")


def line_starting(name, start):
    (line,) = [line for line in text(name).split("\n") if line.startswith(start)]
    return line


@pytest.mark.parametrize("name", list(PROMPTS))
def test_the_rule_3_sentence_once_in_its_place(name):
    """C60 point 1: rule 3, after "never make one count per group yourself."."""
    assert text(name).count(C60_RULE3) == 1, f"C60's rule 3 sentence is not in {name} once"
    rule3 = line_starting(name, "3. ")
    assert f"{RULE3_END} {C60_RULE3}" in rule3, rule3


@pytest.mark.parametrize("name", list(PROMPTS))
def test_the_analyze_sentence_once_in_its_place(name):
    """C60 point 2: under "How to use analyze", after "with no period the program uses every
    month it has."."""
    assert text(name).count(C60_ANALYZE) == 1, f"C60's analyze sentence is not in {name} once"
    head = text(name).split("\nHow to use analyze (statistics)\n", 1)
    assert len(head) == 2, "premise: the heading"
    section = head[1].lstrip("\n").split("\n\n", 1)[0]  # its lines, up to the next blank line
    assert section.startswith("- A question about change"), "premise: the section"
    assert f"{ANALYZE_ANCHOR} {C60_ANALYZE}" in section, section[:600]


@pytest.mark.parametrize("name", list(PROMPTS))
def test_the_anchors_are_there_once(name):
    """A premise of both tests: each anchor stands once in each prompt. Passes today."""
    assert text(name).count(RULE3_END) == 1 and text(name).count(ANALYZE_ANCHOR) == 1
