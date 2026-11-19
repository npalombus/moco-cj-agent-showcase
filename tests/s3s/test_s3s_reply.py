"""The statistical reply: docs/S3S-DESIGN.md S5 (what Python adds, in this order), S4's last
paragraph (R1's check with these slots on offer; `{aN.held}` in the same sentence as, or the
sentence after, an odds slot of the same result; the fixed rendering is each phrase as its
own sentence, capitalised), C10 and C18 of docs/S3A-DESIGN.md (the sensitive line, the
source lines).

S5's order: 1 the table, 2 the fit line, 3 the before-and-after line, 4 what was used and
left out, 5 the association line (always), 6 the sensitive line (when a sensitive field is a
filter, factor, control or group), 7 the source line, ending for a first answer `Want the
details and the R script?`.

Readings (s3sagent): the parts are joined by one space, one line break or one blank line;
the table is any lines between line 1 and the first fixed line (its format is not given,
QUESTIONS.md 9; for T each year's total must be a line `<year>: <total>`). The used line:
`(<n> records over <m> months` exactly; the reason's words and the form when nothing is left
out are asked (QUESTIONS.md, 5). Which failure code a misplaced `{aN.held}` gets is not said:
the tests check the text fails (the fixed rendering is used), not the code.
"""
import re

import pytest

import s3ssupport as T
from p1support import Step, finish
from s3sagent import (MAIN, StatsEnv, UNIT_MANY, answered, ask_case, assert_stat_reply,
                      first_source, later_source, line1_of, stat_reply_re)


def used(name):
    t = T.truth(name)
    months = len(t["months"]) if "months" in t else 60
    return T.used_re(t["records"], months, T.left_out_parts(name))


def test_the_fixed_lines_by_hand():
    """No program code: S5's fixed lines exactly as the contract writes them."""
    assert T.BEFORE_AFTER_LINE == ("Other things changed over the same months. This shows "
                                   "timing, not cause.")
    assert T.association_line(UNIT_MANY) == ("These are patterns in recorded arrest records: "
                                             "what goes with what, not what causes what.")
    assert T.sensitive_line(UNIT_MANY) == ("These are counts of arrest records, not rates, "
                                           "and they show no cause.")
    assert re.fullmatch(T.used_re(8491, 60), "(8,491 records over 60 months.)")
    assert re.fullmatch(T.used_re(774, 68, 47),
                        "(774 records over 68 months; 47 not included: no district recorded.)")
    assert re.fullmatch(T.source_first_re("SYNTHETIC fixture arrests for statistics (made up "
                                          "for tests)", UNIT_MANY),
                        "Source: SYNTHETIC fixture arrests for statistics (made up for tests) "
                        "(county open data), copy of 12 November 2026. A count is of arrest "
                        "records, not people. Want the details and the R script?")
    assert re.fullmatch(T.source_later_re("SYNTHETIC fixture arrests for statistics (made up "
                                          "for tests)"),
                        "(SYNTHETIC fixture arrests for statistics (made up for tests), county "
                        "open data, copy of 12 November 2026.)")


TREND = r"I found that " + T.trend_re(T.truth("trend_all"), UNIT_MANY, "") + r"\."


@pytest.mark.needs_r
def test_a_first_trend_answer_in_full(tmp_path, monkeypatch):
    """S5 with nothing to add but the table, the used line, the association line and the
    first source line; the table holds each year's total."""
    env = StatsEnv(tmp_path, monkeypatch)
    reply = answered(ask_case(env, "trend_all", text="I found that {a1.trend}."))
    assert_stat_reply(reply.text, re.compile(TREND), used=used("trend_all"),
                      source=first_source())
    for year, total in T.truth("trend_all")["yearly"].items():
        assert re.search(rf"(?m)^{year}: {total:,}$", reply.text), (year, total, reply.text)


@pytest.mark.needs_r
def test_the_fit_line_and_left_out_records(tmp_path, monkeypatch):
    """S5.2 then S5.4 with records left out (no district recorded)."""
    env = StatsEnv(tmp_path, monkeypatch)
    reply = answered(ask_case(env, "trend_d4_p6", text="I found that {a1.trend}."))
    t = T.truth("trend_d4_p6")
    assert T.left_out_records("trend_d4_p6") == 47
    line1 = "I found that " + T.trend_re(t, UNIT_MANY, "in district 4") + r"\."
    assert_stat_reply(reply.text, re.compile(line1), fit=T.fit_line_re(t["fit_ratio"]),
                      used=used("trend_d4_p6"), source=first_source())


@pytest.mark.needs_r
def test_the_before_and_after_line(tmp_path, monkeypatch):
    env = StatsEnv(tmp_path, monkeypatch)
    reply = answered(ask_case(env, "ba_d6", text="{a1.step}. {a1.bend}."))
    t = T.truth("ba_d6")
    line1 = T.cap_re(T.step_re(t)) + r"\. " + T.cap_re(T.bend_re(t)) + r"\."
    assert_stat_reply(reply.text, re.compile(line1), before_after=True, used=used("ba_d6"),
                      source=first_source())
    assert reply.text.count(T.BEFORE_AFTER_LINE) == 1


@pytest.mark.needs_r
@pytest.mark.parametrize("name,sensitive", [
    ("yn_main", True),         # gender is a factor
    ("yn_plain", False),       # weapon, shift B, district: none is sensitive
    ("trend_female", True),    # gender is a filter
    ("compare_gender", True),  # gender makes the groups
    ("trend_d2", False),       # a district is not sensitive
])
def test_the_sensitive_line_exactly_when_a_sensitive_field_is_used(tmp_path, monkeypatch, name,
                                                                   sensitive):
    """S11 2f (the wording round): with a sensitive field, one line replaces the association
    line and the sensitive line, in the association line's place; without one, the
    association line is as it was."""
    env = StatsEnv(tmp_path, monkeypatch)
    reply = answered(ask_case(env, name))
    assert (T.cause_line(UNIT_MANY) in reply.text) is sensitive, reply.text
    assert T.sensitive_line(UNIT_MANY) not in reply.text, reply.text
    assert reply.text.count(T.association_line(UNIT_MANY)) == (0 if sensitive else 1)
    # and the order of the lines that are there
    pattern = stat_reply_re(re.compile(r"[^\n]+"), used=used(name), before_after=False,
                            source=first_source())
    if sensitive:
        pattern = pattern.replace(re.escape(T.association_line(UNIT_MANY)),
                                  re.escape(T.cause_line(UNIT_MANY)))
    assert re.fullmatch(pattern, reply.text), (reply.text, pattern)


@pytest.mark.needs_r
@pytest.mark.parametrize("name", ["timing", "ages", "sh_school", "compare_weapon"])
def test_the_association_line_is_on_every_statistical_answer(tmp_path, monkeypatch, name):
    env = StatsEnv(tmp_path, monkeypatch)
    reply = answered(ask_case(env, name))
    assert reply.text.count(T.association_line(UNIT_MANY)) == 1, reply.text
    assert T.BEFORE_AFTER_LINE not in reply.text
    assert "The last six months" not in reply.text


@pytest.mark.needs_r
def test_a_later_answer_carries_the_short_source_line(tmp_path, monkeypatch):
    """C10.6 with C18: a later answer of the thread ends `(<title>, county open data, copy of
    <date>.)`."""
    env = StatsEnv(tmp_path, monkeypatch)
    answered(ask_case(env, "trend_d2"))
    reply = answered(ask_case(env, "trend_d3", text="I found that {a1.trend}."))
    line1 = "I found that " + T.trend_re(T.truth("trend_d3"), UNIT_MANY, "in district 3") + r"\."
    assert_stat_reply(reply.text, re.compile(line1), used=used("trend_d3"),
                      source=later_source())


@pytest.mark.needs_r
@pytest.mark.parametrize("text,passes", [
    ("{a1.odds.1} and {a1.held}.", True),                       # the same sentence
    ("{a1.odds.1}. {a1.held}.", True),                          # the sentence after
    ("{a1.odds.1}. {a1.odds.2}. {a1.odds.3}. {a1.held}.", True),
    ("{a1.held}. {a1.odds.1}.", False),                         # before any odds slot
    ("{a1.odds.1}. I found that. {a1.held}.", False),           # two sentences after
])
def test_held_is_placed_as_s4_says(tmp_path, monkeypatch, text, passes):
    env = StatsEnv(tmp_path, monkeypatch)
    reply = answered(ask_case(env, "yn_main", text=text))
    assert (reply.reply_style == "agent") is passes, (reply.reply_style, reply.draft_failures)
    if not passes:
        assert reply.draft_failures, "a misplaced {a1.held} fails the check"


@pytest.mark.needs_r
@pytest.mark.parametrize("text", ["{a1.trend} because of the weather.",  # a word not allowed
                                  "{a1.odds.1}.",                           # a slot not offered
                                  "There were 4321 more, {a1.trend}."])     # a number typed
def test_a_failed_check_gives_the_fixed_rendering(tmp_path, monkeypatch, text):
    """S4: the fixed rendering is each phrase as its own sentence, capitalised; nothing the
    model wrote is in it."""
    env = StatsEnv(tmp_path, monkeypatch)
    reply = answered(ask_case(env, "trend_all", text=text))
    assert reply.reply_style == "fallback" and reply.draft_failures, reply.reply_style
    line1 = T.cap_re(T.trend_re(T.truth("trend_all"), UNIT_MANY, "")) + r"\."
    assert_stat_reply(reply.text, re.compile(line1), used=used("trend_all"),
                      source=first_source())
    for word in ("weather", "4321", "because"):
        assert word not in reply.text


@pytest.mark.needs_r
@pytest.mark.parametrize("name", ["yn_main", "sh_school", "ba_d7"])
def test_the_fixed_rendering_of_several_phrases(tmp_path, monkeypatch, name):
    """MOCO_REPLY_STYLE=fixed: each phrase of the result as its own sentence, capitalised, in
    slot order; for yes_no, `{aN.held}` joined to the last odds sentence (S11 2d)."""
    env = StatsEnv(tmp_path, monkeypatch, MOCO_REPLY_STYLE="fixed")
    reply = answered(ask_case(env, name))
    assert reply.reply_style == "fixed"
    t = T.truth(name)
    if name == "yn_main":  # S11 2d: {a1.held} joined to the last odds sentence with ", "
        line1 = T.fixed_odds_re(t, UNIT_MANY, T.case(name)["options"]["outcome"],
                                "holding district fixed")
    else:
        parts = ([T.share_re(t, "within 500 feet of a school"), re.escape(T.sharetrend_text(t))]
                 if name == "sh_school" else [T.step_re(t), T.bend_re(t)])
        line1 = " ".join(T.cap_re(p) + r"\." for p in parts)
    assert re.match(line1 + r"(?=\s|$)", reply.text), (line1, reply.text)
    assert line1_of(reply.text)
