"""R10 points 1 to 5 (docs/S3S2-DESIGN.md; R0, R3, R5, R6 as R10 words them; Part S's S4 and S5):
the rate and ratio phrases of each breakdown exactly, `<years>` in its three forms, the table
lines, the lines after the table exactly and in order, both forms of the source line, the slots,
R1's limits; and point 4, a group that is not shown.

The words are written out by hand in s2support (rate_phrase, ratio_phrase, table_line,
used_line, R0_LINE, R5_LINE, R3_LINE, ASSOCIATION_LINE, source_line, reply_lines); the
no-program tests below pin those to R10's text, literally. The program tests read the fixed
rendering (MOCO_REPLY_STYLE=fixed): line 1 is every rate phrase, then every ratio phrase, each
its own sentence; then the table; then point 5's lines. A reply is compared line by line, word
for word (blank lines aside).

READINGS (briefs/QUESTIONS.md, Brief S3S2-A2): a table line starts with the label as R10 writes
it (`female: ...`, `aged 10 to 17: ...`, no capital); the Census copy's date is written as the
county's (`13 November 2026`); margins have the decimals of their figure (rate and its margin
one, ratio and its margin two; reading 9 of the first session); with only the used line's
`<k>` a not-shown group's count may stand there (point 4 gives that line), and nowhere else.
"""
import pytest

import s2support as T
from s2agent import (COUNTY_DATE, RATES, TITLE, S2Env, SlotModel, ask_rate, assert_reply,
                     census_dates, details_of, line1_of, lines_of, offered_slots, reply_problem)
from s3sagent import _DECIMAL
from s3support import figures

HAND_COUNTY, HAND_CENSUS = "12 November 2026", "13 November 2026"

# re_2025 (rates_like, race_ethnicity, 2025), written out by hand from R10: every line.
HAND_REPLY = "\n".join([
    "There were about 30.0 arrest records per 10,000 residents counted as Hispanic (any race) in "
    "2025 (margin of error ±0.6). There were about 50.0 arrest records per 10,000 residents "
    "counted as Black, not Hispanic in 2025 (margin of error ±1.0). There were about 10.0 arrest "
    "records per 10,000 residents counted as White, not Hispanic in 2025 (margin of error ±0.1). "
    "There were about 10.0 arrest records per 10,000 residents counted as Asian, not Hispanic in "
    "2025 (margin of error ±0.2). The rate for Hispanic (any race) was about 3.00 times the rate "
    "for White, not Hispanic (margin of error ±0.06). The rate for Black, not Hispanic was about "
    "5.00 times the rate for White, not Hispanic (margin of error ±0.10). The rates for Asian, "
    "not Hispanic and White, not Hispanic were not clearly different (ratio 1.00, margin of "
    "error ±0.02).",
    "Hispanic (any race): 600 records, 200,000 residents (margin of error ±4,000), 30.0 per 10,000",
    "Black, not Hispanic: 900 records, 180,000 residents (margin of error ±3,600), 50.0 per 10,000",
    "White, not Hispanic: 400 records, 400,000 residents (margin of error ±2,400), 10.0 per 10,000",
    "Asian, not Hispanic: 150 records, 150,000 residents (margin of error ±3,000), 10.0 per 10,000",
    "(2,050 records over 12 months; 30 not included: no race and ethnicity that the Census "
    "counts.)",
    "This is not the share of residents who were arrested: one person can be arrested several "
    "times, and people arrested in the county do not all live in it.",
    "The margin of error comes from the Census's survey alone, at the Census's 90 percent level; "
    "it says nothing about chance in the number of arrests from year to year.",
    "The police record what an officer writes down; the Census records what people say about "
    "themselves. The two do not match person for person.",
    "These are patterns in recorded arrest records: what goes with what, not what causes what.",
    "Source: SYNTHETIC fixture arrests for rates (made up for tests) (county open data), copy of "
    "12 November 2026; Census Bureau, American Community Survey one-year estimates, copy of 13 "
    "November 2026. A count is of arrest records, not people. Want the details and the R "
    "script?"])

# all_2025 (no breakdown): the no-margin bracket, no R5 sentence, no R3 line.
HAND_NONE = "\n".join([
    "There were about 19.3 arrest records per 10,000 residents in 2025 (the Census gives no "
    "margin of error for this figure).",
    "All residents: 2,040 records, 1,057,000 residents (the Census gives no margin of error for "
    "this figure), 19.3 per 10,000",
    "(2,040 records over 12 months.)",
    "This is not the share of residents who were arrested: one person can be arrested several "
    "times, and people arrested in the county do not all live in it.",
    "These are patterns in recorded arrest records: what goes with what, not what causes what.",
    "Source: SYNTHETIC fixture arrests for statistics (made up for tests) (county open data), "
    "copy of 12 November 2026; Census Bureau, American Community Survey one-year estimates, copy "
    "of 13 November 2026. A count is of arrest records, not people. Want the details and the R "
    "script?"])


def _check_hand(text, name="re_2025"):
    """The check every program test makes, with the hand dates."""
    t = T.truth(name)
    problem = reply_problem(text, [T.reply_lines(t, TITLE[t["source"]], HAND_COUNTY,
                                                 HAND_CENSUS)])
    assert problem is None, problem


def test_the_readers_take_replies_written_as_r10_says():
    """No program code: the replies written out by hand pass the check the program tests make."""
    _check_hand(HAND_REPLY)
    _check_hand(HAND_NONE, "all_2025")


def test_the_words_of_each_breakdown_by_hand():
    """No program code: point 1's forms, `<years>` in its three forms, point 3's lines."""
    g, a, a5 = T.truth("gender_2025"), T.truth("age_2025"), T.truth("age_5y")
    assert T.rate_phrase(g, "male") == ("there were about 27.5 arrest records per 10,000 male "
                                        "residents in 2025 (margin of error ±0.6)")
    assert T.ratio_phrase(g, "male") == ("the rate for male residents was about 2.48 times the "
                                         "rate for female residents (margin of error ±0.08)")
    assert T.table_line(g, "female") == ("female: 601 records, 541,000 residents (margin of "
                                         "error ±13,000), 11.1 per 10,000")
    assert T.rate_phrase(a, "18 to 24") == ("there were about 46.1 arrest records per 10,000 "
                                            "residents aged 18 to 24 in 2025 (margin of error "
                                            "±1.5)")
    assert T.ratio_phrase(a, "45 to 54") == ("the rate for residents aged 45 to 54 was about 0.45 "
                                             "times the rate for residents aged 35 to 44 (margin "
                                             "of error ±0.01)")
    assert T.table_line(a, "18 to 24") == ("aged 18 to 24: 369 records, 80,000 residents (margin "
                                           "of error ±2,536), 46.1 per 10,000")
    assert T.rate_phrase(a5, "65 and over").endswith("per 10,000 residents aged 65 and over in "
                                                     "2021 to 2025 (margin of error under ±0.1)")
    two = T.truth("re_2024_25")
    assert T.rate_phrase(two, "Hispanic (any race)") == (
        "there were about 27.5 arrest records per 10,000 residents counted as Hispanic (any "
        "race) in 2024 and 2025 (margin of error ±0.4)")
    assert T.table_line(two, "Hispanic (any race)") == (
        "Hispanic (any race): 1,090 records, 396,000 residents (margin of error ±5,728), 27.5 "
        "per 10,000")
    assert T.rate_phrase(T.truth("all_5y"), "all residents") == (
        "there were about 16.4 arrest records per 10,000 residents in 2021 to 2025 (the Census "
        "gives no margin of error for this figure)")
    assert T.used_line(T.truth("gender_2025")) == ("(2,022 records over 12 months; 18 not "
                                                   "included: no gender recorded.)")
    assert T.used_line(a5) == "(8,336 records over 60 months; 155 not included: no usable age.)"
    assert T.used_line(a) == ("(1,898 records over 12 months; 40 not included: no usable age; "
                              "102 not included: in a group with fewer than 100 records.)")
    assert T.not_shown_line(a) == ("Not shown, with fewer than 100 records: aged 55 to 64; aged "
                                   "65 and over.")
    assert T.source_line("X", "1 May 2026", "2 May 2026", first=False) == (
        "(X, county open data, copy of 1 May 2026; Census Bureau, American Community Survey "
        "one-year estimates, copy of 2 May 2026.)")
    assert T.slots(T.truth("re_2025")) == ["{a1.rate.1}", "{a1.rate.2}", "{a1.rate.3}",
                                           "{a1.rate.4}", "{a1.ratio.1}", "{a1.ratio.2}",
                                           "{a1.ratio.4}"]
    assert T.slots(T.truth("re_2022")) == ["{a1.rate.1}", "{a1.rate.2}", "{a1.rate.3}",
                                           "{a1.ratio.1}", "{a1.ratio.2}"]
    assert T.slots(a) == [f"{{a1.rate.{k}}}" for k in range(1, 6)] + [
        "{a1.ratio.1}", "{a1.ratio.2}", "{a1.ratio.3}", "{a1.ratio.5}"]
    assert T.slots(T.truth("all_2025")) == ["{a1.rate}"]


@pytest.mark.parametrize("broken", [
    ("30.0 arrest", "30.1 arrest"),                                    # a rate
    ("in 2025 (margin of error ±0.6)", "in 2025 (margin of error ±0.7)"),  # its margin
    ("residents counted as Hispanic", "residents recorded as Hispanic"),   # point 1's form
    ("about 3.00 times", "about 3.01 times"),                          # a ratio
    ("(ratio 1.00, margin of error ±0.02)", "(ratio 1.00, margin of error ±0.03)"),
    ("were not clearly different (ratio 1.00,", "were about 1.00 times ("),  # clear for not
    ("for White, not Hispanic (margin of error ±0.06)",
     "for White residents (margin of error ±0.06)"),                  # the reference's words
    ("200,000 residents (margin of error ±4,000)", "200,000 residents (margin of error ±4,001)"),
    ("150 records, 150,000", "150 records, 150000"),                    # thousands commas
    ("(2,050 records", "(2,080 records"),                              # the used line
    ("30 not included: no race and ethnicity that the Census counts",
     "30 not included: no race or ethnicity recorded"),
    ("This is not the share", "This is the share"),                    # R0
    ("90 percent", "95 percent"),                                      # R5
    ("The police record", "Police record"),                            # R3
    ("recorded arrest records: what", "recorded arrest records, not rates: what"),  # S11 2f
    ("copy of 12 November 2026;", "copy;"),                            # the county's date
    ("; Census Bureau, American Community Survey one-year estimates, copy of 13 November 2026.",
     "."),                                                            # the Census source
    ("Want the details and the R script?", "Want the details?"),
])
def test_the_readers_refuse_a_reply_broken_in_one_place(broken):
    text = HAND_REPLY.replace(*broken, 1)
    assert text != HAND_REPLY, broken
    with pytest.raises(AssertionError):
        _check_hand(text)


@pytest.mark.parametrize("broken", [
    ("(the Census gives no margin of error for this figure).",
     "(no margin of error)."),                                          # the bracket
    ("in 2025 (the Census gives no margin of error for this figure)", "in 2025"),
    ("1,057,000 residents (the Census gives", "1,057,000 residents (margin of error ±0, the "
                                              "Census gives"),
])
def test_the_readers_refuse_a_county_total_broken(broken):
    text = HAND_NONE.replace(*broken, 1)
    assert text != HAND_NONE, broken
    with pytest.raises(AssertionError):
        _check_hand(text, "all_2025")


def test_the_readers_refuse_extra_lines_and_the_lines_out_of_order():
    lines = HAND_REPLY.split("\n")
    used, r0, r5, r3, assoc = lines[5:10]
    for order in ([used, r3, r5, r0, assoc], [used, r0, r5, assoc, r3], [r0, used, r5, r3, assoc],
                  [used, r0, r3, r5, assoc], [used, r0, r5, r3],
                  [used, r0, r5, r3, assoc, T.NOT_RATES[1]]):
        with pytest.raises(AssertionError):
            _check_hand("\n".join(lines[:5] + order + lines[10:]))
    with pytest.raises(AssertionError):   # R5's sentence on the county total
        _check_hand(HAND_NONE.replace("(2,040 records over 12 months.)",
                                      "(2,040 records over 12 months.)\n" + T.R5_LINE),
                    "all_2025")
    with pytest.raises(AssertionError):   # a table line out of table order
        _check_hand("\n".join([lines[0], lines[2], lines[1]] + lines[3:]))


# ---- with the program ----------------------------------------------------------------------

WHOLE = ["re_2025", "re_2024_25", "re_5y", "gender_2025", "gender_5y", "age_5y", "all_2025",
         "all_5y", "re_2025_hisp", "gender_2025_male"]


@pytest.mark.needs_r
@pytest.mark.parametrize("name", WHOLE)
def test_the_whole_reply_word_for_word(tmp_path, monkeypatch, name):
    """Every line of the fixed reply. On race_ethnicity and gender the plain association line
    and neither "not rates" line; on the county total the no-margin bracket and no R5
    sentence."""
    t = T.truth(name)
    env = S2Env(tmp_path, monkeypatch, names=(t["source"],), MOCO_REPLY_STYLE="fixed")
    reply = ask_rate(env, name)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    for line in T.NOT_RATES:
        assert line not in reply.text, f"R10 point 5: a rate answer never says {line!r}"
    if t["by"] is None:
        assert "±" not in reply.text and T.R5_LINE not in reply.text, reply.text
    assert_reply(reply, t, env)


@pytest.mark.needs_r
def test_a_later_answer_has_the_short_source_line(tmp_path, monkeypatch):
    """Point 5: the source line of a later answer in the thread."""
    t, later = T.truth("re_2025"), T.truth("re_2023")
    env = S2Env(tmp_path, monkeypatch, MOCO_REPLY_STYLE="fixed")
    assert_reply(ask_rate(env, "re_2025"), t, env)
    reply = ask_rate(env, "re_2023")
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert_reply(reply, later, env, first=False)


@pytest.mark.needs_r
@pytest.mark.parametrize("reference", ["hispanic (ANY RACE)", "HISPANIC (any race)"])
def test_the_reference_named_without_capitals(tmp_path, monkeypatch, reference):
    """Point 2: `reference` names a shown group by its label; capitals do not count."""
    t = T.truth("re_2025_hisp")
    env = S2Env(tmp_path, monkeypatch, MOCO_REPLY_STYLE="fixed")
    args = T.analyze_arguments("re_2025_hisp")
    args["options"]["reference"] = reference
    reply = ask_rate(env, arguments=args)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert_reply(reply, t, env)


@pytest.mark.needs_r
@pytest.mark.parametrize("name", ["re_2025", "re_2025_hisp", "re_2022", "age_2025",
                                  "gender_2025", "all_2025"])
def test_the_slots_in_the_tool_answer(tmp_path, monkeypatch, name):
    """Point 2: `{a1.rate}` alone with no breakdown; `{a1.rate.<k>}` for each shown group,
    `{a1.ratio.<k>}` for each shown group but the reference, with that group's k."""
    t = T.truth(name)
    env = S2Env(tmp_path, monkeypatch, names=(t["source"],))
    reply = ask_rate(env, name)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    got = offered_slots(env)
    assert sorted(got) == sorted(T.slots(t)) and len(set(got)) == len(got), (got, T.slots(t))


@pytest.mark.needs_r
@pytest.mark.parametrize("name,used,style", [("re_2025", 4, "agent"), ("re_2025", 5, "fallback"),
                                             ("gender_2025", 3, "agent"),
                                             ("all_2025", 1, "agent")])
def test_r1_four_sentences_pass_and_five_are_refused(tmp_path, monkeypatch, name, used, style):
    """Point 2: R1's limits do not change. The model's own text with up to four sentences,
    each one slot it chose, stands; with five it is refused and the fixed rendering (every
    rate phrase, then every ratio phrase) is the line instead."""
    t = T.truth(name)
    env = S2Env(tmp_path, monkeypatch, names=(t["source"],))
    chosen = []

    def write(slots):
        chosen[:] = slots[:used]
        return " ".join(f"{s}." for s in chosen)
    reply = env.ask("What is the arrest rate per resident?",
                    model=SlotModel(T.analyze_arguments(name), write=write))
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert reply.reply_style == style, (reply.reply_style, reply.draft_failures, reply.text)
    line1 = line1_of(reply.text)
    if style == "fallback":
        assert line1 == T.line1(t), (line1, T.line1(t))
        return
    phrases = T.phrases(t)
    for slot in chosen:
        assert phrases[slot] in line1 or T.cap(phrases[slot]) in line1, (slot, line1)


# ---- point 4: a group that is not shown ------------------------------------------------------

def _without_used_part(text, t):
    """The text without the used line's `; <k> not included: in a group with fewer than 100
    records` (point 4 puts the hidden records there, and only there)."""
    small = sum(t["groups"][g]["n"] for g in t["not_shown"])
    return text.replace(f"; {T.floored(small)} not included: {T.SMALL_REASON}", " ")


def _nothing_of(text, t, group, where):
    """Neither the group's count, its residents figure (or its margin) nor its rate."""
    v = t["groups"][group]
    plain = T.undated(_without_used_part(text, t))
    assert v["n"] not in figures(_DECIMAL.sub(" ", plain)), (where, group, v["n"], text)
    assert not T.written(plain, v["residents"], whole=True), (where, group, v["residents"], text)
    assert not T.written(plain, v["residents_margin"], whole=True), (where, group, text)
    assert not T.written(plain, v["rate"]), (where, group, T.one(v["rate"]), text)


@pytest.mark.needs_r
@pytest.mark.parametrize("name", ["re_2022", "re_2021", "age_2025"])
def test_a_group_not_shown(tmp_path, monkeypatch, name):
    """re_2022: Asian, not Hispanic has 60 records (10 to 99); re_2021: 7 (under 10); age_2025:
    aged 55 to 64 (72) and aged 65 and over (30). Each is named in the not-shown line and in no
    other line; its count, residents figure and rate are in no line of the reply and nowhere
    in `details`; no slot, no table line; its records in the used line by the floor; the
    reference chosen among the shown groups (the whole reply word for word)."""
    t = T.truth(name)
    env = S2Env(tmp_path, monkeypatch, names=(t["source"],), MOCO_REPLY_STYLE="fixed")
    reply = ask_rate(env, name)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    not_shown = T.not_shown_line(t)
    for group in t["not_shown"]:
        label = t["groups"][group]["label"]
        naming = [line for line in lines_of(reply.text) if label in line]
        assert naming == [not_shown], f"{label} is named outside the not-shown line: {naming}"
        _nothing_of(reply.text, t, group, "reply")
    assert_reply(reply, t, env)
    details = details_of(env).text
    for group in t["not_shown"]:
        _nothing_of(details, t, group, "details")
    if name == "re_2021":
        assert "; fewer than 10 not included: in a group with fewer than 100 records" in \
            reply.text, reply.text
