"""`shares`: docs/S3S-DESIGN.md S1 (`"part": [filters]`), S3 (model S: the share per calendar
year with a Wilson 95% range; logistic regression of "matches part" on the year as a
number), S4 (`{aN.share}`, `{aN.sharetrend}`), S9.

`<part>` is C6's share-phrase part: the `<what>` of the filters the part adds. The table's
format is not given (QUESTIONS.md, 9): each year's share with one decimal must stand on a
line with its year, nothing more is checked of it. Phrases by hand from S4, numbers by plain
counting (the same on both sides).
"""
import re

import pytest

import s3ssupport as T
from s3sagent import (StatsEnv, answered, ask_case, assert_estimates, assert_line1, line1_of)

# case: (<part>, the share phrase by hand, the sharetrend phrase by hand)
PHRASES = {
    "sh_school": ("within 500 feet of a school",
                  "the share within 500 feet of a school went from 16.3% in 2021 to 27.1% in "
                  "2025", "a clear rise over the years"),
    "sh_noschool": ("not within 500 feet of a school",
                    "the share not within 500 feet of a school went from 83.7% in 2021 to 72.9% "
                    "in 2025", "a clear fall over the years"),
    "sh_shift": ("on shift B", "the share on shift B went from 50.4% in 2021 to 50.1% in 2025",
                 "no clear change over the years"),
}


def test_the_hand_written_phrases_match_the_truth():
    for name, (part, share, trend) in PHRASES.items():
        t = T.truth(name)
        assert re.fullmatch(T.share_re(t, part), share), name
        assert T.sharetrend_text(t) == trend, name
        assert list(t["years"]) == [2021, 2022, 2023, 2024, 2025]


def test_wilson_by_formula():
    """No program code: the Wilson range of 20 of 100 at z = 1.959964."""
    lo, hi = T.wilson(20, 100)
    assert (round(lo, 4), round(hi, 4)) == (13.3367, 28.8829)


@pytest.mark.needs_r
@pytest.mark.parametrize("name", list(PHRASES))
def test_share_and_sharetrend(tmp_path, monkeypatch, name):
    env = StatsEnv(tmp_path, monkeypatch)
    reply = answered(ask_case(env, name))
    assert reply.reply_style == "agent", reply.draft_failures
    assert_estimates(env, name)
    t = T.truth(name)
    part = PHRASES[name][0]
    assert_line1(reply.text, T.cap_re(T.share_re(t, part)) + r"\. "
                 + re.escape(T.cap(T.sharetrend_text(t))))
    table = reply.text[len(line1_of(reply.text)):]
    for year, v in t["years"].items():
        share = T.signed_re(v["share"], 1, T.TOL_SHARE)
        assert re.search(rf"(?m)^[^\n]*\b{year}\b[^\n]*{share}", table), (year, reply.text)
