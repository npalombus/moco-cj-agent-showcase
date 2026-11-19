"""`trend_compare`: docs/S3S-DESIGN.md S1 (`"versus": [filters]`, the two differ in exactly
one field), S3 with S12 item 1 (approved, D-058: each group fitted alone, the difference from
the two own fits), S4 (`{aN.difference}`), S9.

The two groups differ in a flag, so that `<a label>` and `<b label>` read the same whether
they are C6's compare labels or C6's `<what>` fragments (S10 answer 7). "a" is the spec's
own filters, "b" the `versus` filters; the difference is b(B) - b(A) of the two own fits
written as 100 x (exp(d) - 1) (S12 item 1; READING, s3ssupport), in S11 item 2's wording: "the
ratio of the two yearly changes", a percentage, signed as S10 answer 1. Phrases written by
hand from S11 with the numbers of the R cross-check (round 3's: kit-log/raw/
S3S-R3-A-r-crosscheck.txt).

Not tested: "Each group's own trend is in the table" (S4): whether a group's own trend comes
from the joint model or from its own fit is not said, and the table's format is not given
(QUESTIONS.md, 9).
"""
import re

import pytest

import s3ssupport as T
from s3sagent import StatsEnv, answered, ask_case, assert_estimates, assert_line1

NEAR, NOT_NEAR = "within 500 feet of a school", "not within 500 feet of a school"
WITH, WITHOUT = "with a weapon recorded", "with no weapon recorded"
# case: (a label, b label, the phrase by hand)
PHRASES = {
    "compare_school": (NEAR, NOT_NEAR,
                       "the yearly trend not within 500 feet of a school was about 15.2% below "
                       "the yearly trend within 500 feet of a school (the ratio of the two "
                       "yearly changes; 95% range -18.5% to -11.8%)"),
    "compare_school_rev": (NOT_NEAR, NEAR,
                           "the yearly trend within 500 feet of a school was about 18.0% above "
                           "the yearly trend not within 500 feet of a school (the ratio of the "
                           "two yearly changes; 95% range +13.4% to +22.7%)"),
    "compare_weapon": (WITH, WITHOUT,
                       "there was no clear difference in yearly trend between with a weapon "
                       "recorded and with no weapon recorded (the ratio of the two yearly "
                       "changes was about -0.5%, 95% range -4.2% to +3.4%)"),
}


def test_the_hand_written_phrases_match_the_truth():
    """No program code: below, above, not clear; each hand-written phrase matches."""
    forms = {n: (T.truth(n)["difference"]["clear"], T.truth(n)["difference"]["estimate"] > 0)
             for n in PHRASES}
    assert forms == {"compare_school": (True, False), "compare_school_rev": (True, True),
                     "compare_weapon": (False, False)}
    for name, (a, b, text) in PHRASES.items():
        assert re.fullmatch(T.difference_re(T.truth(name), a, b), text), name
    assert not re.fullmatch(T.difference_re(T.truth("compare_school"), NEAR, NOT_NEAR),
                            PHRASES["compare_school"][2].replace("below", "above"))


def test_the_groups_differ_in_one_field_only():
    """S1: the two filter lists differ in exactly one field (the cases' premise)."""
    for name in PHRASES:
        c = T.case(name)
        a = {f["field"]: f for f in c["filters"]}
        b = {f["field"]: f for f in c["options"]["versus"]}
        assert set(a) == set(b) and sum(a[k] != b[k] for k in a) == 1, name


@pytest.mark.needs_r
@pytest.mark.parametrize("name", list(PHRASES))
def test_difference_estimate_and_phrase(tmp_path, monkeypatch, name):
    env = StatsEnv(tmp_path, monkeypatch)
    reply = answered(ask_case(env, name, text="I found that {a1.difference}."))
    assert reply.reply_style == "agent", reply.draft_failures
    assert_estimates(env, name)
    a, b, _ = PHRASES[name]
    assert_line1(reply.text, T.difference_re(T.truth(name), a, b), before="I found that ")
