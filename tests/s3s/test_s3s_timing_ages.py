"""`timing` and `distribution`: docs/S3S-DESIGN.md S1, S4 (`{aN.timing}`, `{aN.ages}`), S5.1,
C8 (a cell from 1 to 9 is written `fewer than 10`).

Timing: the busiest and the quietest weekday-hour cell of 2021 to 2025, without ties; the
quietest is the one cell from 1 to 9 (4 records), so it is written `fewer than 10`. Ages:
the median and quartiles, which the fixture makes the same whole number under every usual
quantile rule (s3ssupport.age_summary checks). With `by`, how the groups' phrases are joined
in the slot is asked (QUESTIONS.md, 8): each group's phrase must be in line 1, in group
order. Phrases by hand from S4.
"""
import re

import pytest

import s3ssupport as T
from s3sagent import StatsEnv, answered, ask_case, assert_line1, line1_of, tool_answer

TIMING = ("the busiest hour was Friday at 11 pm (122) and the quietest Tuesday at 4 am (fewer "
          "than 10)")
# C59 of docs/S3A-DESIGN.md (added by briefs/S3-R21-A-tests.md): the days first, then TIMING. The
# fixture's days: Friday 1,488 records, Tuesday 1,063 (tests/s3/test_s3_c59.py checks the sums).
TIMING_C59 = ("the busiest day of the week was Friday (1,488) and the quietest Tuesday (1,063); "
              + TIMING)
AGES = "the median age was 30 (the middle half were 24 to 38)"
AGES_BY = ["for female, the median age was 30 (the middle half were 24 to 38)",
           "for male, the median age was 30 (the middle half were 24 to 39)"]


def test_the_hand_written_phrases_match_the_truth():
    assert T.timing_text(T.truth("timing")) == TIMING
    assert T.ages_text(T.truth("ages")["groups"][None]) == AGES
    by = T.truth("ages_gender")["groups"]
    assert [T.ages_text(s, lab) for lab, s in by.items()] == AGES_BY


@pytest.mark.needs_r
def test_timing(tmp_path, monkeypatch):
    env = StatsEnv(tmp_path, monkeypatch)
    reply = answered(ask_case(env, "timing", text="I found that {a1.timing}."))
    assert reply.reply_style == "agent", reply.draft_failures
    assert tool_answer(env)["slots"] == ["{a1.timing}"]
    # Changed by briefs/S3-R21-A-tests.md (C59; was re.escape(TIMING)).
    assert_line1(reply.text, re.escape(TIMING_C59), before="I found that ")
    assert "(4)" not in reply.text


@pytest.mark.needs_r
def test_ages(tmp_path, monkeypatch):
    env = StatsEnv(tmp_path, monkeypatch)
    reply = answered(ask_case(env, "ages", text="I found that {a1.ages}."))
    assert reply.reply_style == "agent", reply.draft_failures
    assert_line1(reply.text, re.escape(AGES), before="I found that ")


@pytest.mark.needs_r
def test_ages_by_gender(tmp_path, monkeypatch):
    """S4: with `by`, one phrase per group, each starting `for <label>, `; S5.1: the table
    has one line per group (each label on a line of its own after line 1)."""
    env = StatsEnv(tmp_path, monkeypatch)
    reply = answered(ask_case(env, "ages_gender", text="{a1.ages}."))
    assert reply.reply_style == "agent", reply.draft_failures
    line1 = line1_of(reply.text)
    found = [line1.lower().find(p) for p in AGES_BY]
    assert all(i >= 0 for i in found) and found == sorted(found), (line1, AGES_BY)
    rest = reply.text[len(line1):]
    for label in ("female", "male"):
        assert re.search(rf"(?m)^{label}\b", rest), (label, reply.text)


@pytest.mark.needs_r
def test_a_group_of_30_usable_ages_is_answered(tmp_path, monkeypatch):
    """S1 at its edge (the refused side is in test_s3s_too_little.py): 30 women with a usable
    age, and 3 more without one, are enough."""
    assert T.truth("ages_d30")["groups"]["female"]["n"] == 30
    env = StatsEnv(tmp_path, monkeypatch, names=(T.EDGES,))
    answered(ask_case(env, "ages_d30", text="{a1.ages}."))
