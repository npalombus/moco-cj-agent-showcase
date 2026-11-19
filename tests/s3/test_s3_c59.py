"""C59 of docs/S3A-DESIGN.md: the timing answer names the busiest day too (live rounds, N07).
Brief: briefs/S3-R21-A-tests.md (the part added 17 Nov 15:37 EST). Tests only; the planning chat
builds C59. Red until the build.

`statwords.timing_phrase(cells, floor)` is called with SYNTHETIC tables made here (7 rows,
Monday first, of 24 hours each); the county turn uses the Part S fixture (tests/s3s/) through
`analyze` with kind timing, which starts R. Every expected text is written out by hand from
C59 point 1 and, after the semicolon, from today's text (S4 with C16, unchanged).

Readings (also in kit-log/raw/S3-R21-A-notes.txt):
- R21-C59-1. "Ties are joined with `and` ... as for the hours": tied days are joined as
  join_and joins them ("A and B", "A, B and C"), in day order, Monday first, as the hours'
  cells are.
- R21-C59-2. "A day whose total is under the floor" is tested with one such day only: C59
  does not say whether C16's rule for hidden hours (never ranked against each other) holds for
  two hidden days of different totals, so no test here has two (asked in briefs/QUESTIONS.md).
"""
import re
import sys
from pathlib import Path

import pytest

from p1support import mod

TESTS = Path(__file__).resolve().parents[1]
if str(TESTS / "s3s") not in sys.path:
    sys.path.insert(0, str(TESTS / "s3s"))

import s3ssupport as S  # noqa: E402
from s3sagent import StatsEnv, answered, ask_case, assert_line1, tool_answer  # noqa: E402

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
FLOOR = 10


def table(base=20, **cells):
    """7 x 24 cells of `base`, with cells["<day index>_<hour>"] = n put over it."""
    out = [[base] * 24 for _ in range(7)]
    for key, n in cells.items():
        d, h = (int(part) for part in key.lstrip("c").split("_"))
        out[d][h] = n
    return out


def phrase(cells, floor=FLOOR):
    return mod("statwords").timing_phrase(cells, floor)


# ---- the tables and their texts, by hand ---------------------------------------------------------

# Every cell 20, Friday 11 pm 60, Tuesday 4 am 12, Wednesday 2 am 15: Friday 520, Tuesday 472.
ONE_EACH = table(c4_23=60, c1_4=12, c2_2=15)
ONE_EACH_HOURS = ("the busiest hour was Friday at 11 pm (60) and the quietest Tuesday at 4 am "
                  "(12)")
ONE_EACH_TEXT = ("the busiest day of the week was Friday (520) and the quietest Tuesday (472); "
                 + ONE_EACH_HOURS)

# Friday 11 pm and Saturday 1 am 60: Friday and Saturday 520 each.
TOP_TIE = table(c4_23=60, c5_1=60, c1_4=12)
TOP_TIE_HOURS = ("the busiest hour was Friday at 11 pm and Saturday at 1 am (60 each) and the "
                 "quietest Tuesday at 4 am (12)")
TOP_TIE_TEXT = ("the busiest day of the week was Friday and Saturday (520 each) and the quietest "
                "Tuesday (472); " + TOP_TIE_HOURS)

# Tuesday 4 am and Wednesday 3 am 12: Tuesday and Wednesday 472 each.
BOTTOM_TIE = table(c4_23=60, c1_4=12, c2_3=12)
BOTTOM_TIE_HOURS = ("the busiest hour was Friday at 11 pm (60) and the quietest Tuesday at 4 am "
                    "and Wednesday at 3 am (12 each)")
BOTTOM_TIE_TEXT = ("the busiest day of the week was Friday (520) and the quietest Tuesday and "
                   "Wednesday (472 each); " + BOTTOM_TIE_HOURS)

# Sunday: 0 in every hour but noon, which has 5: Sunday's total 5, under the floor.
UNDER = table(c4_23=60, **{f"c6_{h}": 0 for h in range(24) if h != 12}, c6_12=5)


def _hour(h):
    return {0: "midnight", 12: "noon"}.get(h, f"{h} am" if h < 12 else f"{h - 12} pm")


_ZERO_SUNDAY = [f"Sunday at {_hour(h)}" for h in range(24) if h != 12]
UNDER_HOURS = ("the busiest hour was Friday at 11 pm (60) and the quietest "
               + ", ".join(_ZERO_SUNDAY[:-1]) + " and " + _ZERO_SUNDAY[-1] + " (0 each)")
UNDER_TEXT = ("the busiest day of the week was Friday (520) and the quietest Sunday (fewer than "
              "10); " + UNDER_HOURS)

CASES = {"one busiest and one quietest day": (ONE_EACH, ONE_EACH_TEXT, ONE_EACH_HOURS),
         "ties at the top": (TOP_TIE, TOP_TIE_TEXT, TOP_TIE_HOURS),
         "ties at the bottom": (BOTTOM_TIE, BOTTOM_TIE_TEXT, BOTTOM_TIE_HOURS),
         "a day under the floor": (UNDER, UNDER_TEXT, UNDER_HOURS)}


def test_premise_the_day_totals_of_the_tables():
    sums = lambda t: [sum(row) for row in t]  # noqa: E731
    assert sums(ONE_EACH) == [480, 472, 475, 480, 520, 480, 480]
    assert sums(TOP_TIE) == [480, 472, 480, 480, 520, 520, 480]
    assert sums(BOTTOM_TIE) == [480, 472, 472, 480, 520, 480, 480]
    assert sums(UNDER)[6] == 5 and max(sums(UNDER)) == 520 == sums(UNDER)[4]


@pytest.mark.parametrize("case", list(CASES))
def test_the_phrase_word_for_word(case):
    """C59 point 1 for each table of C59's tests: the days first, then today's text."""
    cells, text, _ = CASES[case]
    assert phrase(cells) == text


@pytest.mark.parametrize("case", list(CASES))
def test_todays_hour_text_unchanged_after_the_semicolon(case):
    cells, _, hours = CASES[case]
    got = phrase(cells)
    assert "; " in got, got
    assert got.split("; ", 1)[1] == hours


def _days_part(cells, floor=FLOOR):
    """C59 point 1, by hand: the days' sums, the busiest and the quietest, ties joined."""
    sums = [sum(row) for row in cells]

    def side(value):
        days = [DAYS[d] for d in range(7) if sums[d] == value]
        joined = days[0] if len(days) == 1 else ", ".join(days[:-1]) + " and " + days[-1]
        n = f"fewer than {floor}" if 1 <= value < floor else f"{value:,}"
        return joined, n + (" each" if len(days) > 1 else "")

    (top, top_n), (low, low_n) = side(max(sums)), side(min(sums))
    return f"the busiest day of the week was {top} ({top_n}) and the quietest {low} ({low_n})"


IRREGULAR = [[50 + (d * 11 + h * 7) % 31 for h in range(24)] for d in range(7)]


def test_the_days_figures_are_the_sums_of_the_cells():
    """C59 point 1: a day's figure is the sum of its 24 cells, the true values, shown with a
    comma from 1,000 up (C6). An irregular table with unique busiest and quietest days."""
    sums = [sum(row) for row in IRREGULAR]
    assert len({max(sums), min(sums)}) == 2 and sums.count(max(sums)) == 1 \
        and sums.count(min(sums)) == 1 and min(sums) >= 1000, "premise"
    got = phrase(IRREGULAR)
    assert got.split("; ", 1)[0] == _days_part(IRREGULAR), got
    assert f"{max(sums):,}" in got and f"{min(sums):,}" in got


def test_three_tied_days_are_joined_as_the_hours_are():
    """C59 point 1 (R21-C59-1): three days tied at the top are `A, B and C (<n> each)`."""
    cells = table(c0_1=60, c2_5=60, c4_23=60, c1_4=12)
    assert _days_part(cells) == ("the busiest day of the week was Monday, Wednesday and Friday "
                                 "(520 each) and the quietest Tuesday (472)")
    assert phrase(cells).startswith(_days_part(cells) + "; ")


# ---- a county turn whose finding uses {a1.timing} -------------------------------------------------

DAYS_FIXTURE = ("the busiest day of the week was Friday (1,488) and the quietest Tuesday "
                "(1,063)")
TIMING_TODAY = ("the busiest hour was Friday at 11 pm (122) and the quietest Tuesday at 4 am "
                "(fewer than 10)")  # tests/s3s/test_s3s_timing_ages.py's TIMING


def test_premise_the_fixtures_days():
    cells = S.truth("timing")["cells"]
    sums = [sum(cells[(d, h)] for h in range(24)) for d in range(7)]
    assert sums == [1155, 1063, 1147, 1204, 1488, 1241, 1193]
    assert S.timing_text(S.truth("timing")) == TIMING_TODAY


@pytest.mark.needs_r
def test_a_county_turn_whose_finding_uses_the_timing_slot(tmp_path, monkeypatch):
    """C59 point 2: still one slot, {a1.timing}; the finding is sent filled with the days first."""
    env = StatsEnv(tmp_path, monkeypatch)
    reply = answered(ask_case(env, "timing", text="I found that {a1.timing}."))
    assert reply.reply_style == "agent", reply.draft_failures
    assert tool_answer(env)["slots"] == ["{a1.timing}"]
    assert_line1(reply.text, re.escape(DAYS_FIXTURE + "; " + TIMING_TODAY),
                 before="I found that ")
