"""S3A C75 and C76 (D-093). Written by the planning chat (no separate tests session, D-093).

C75: the county's weapon pointing file holds only a few records a month before February 2022
and many more from then on, so a trend over the whole copy read as rising (trial of 21 November
2026 on the live code). The source file now starts on 1 February 2022 and says why.
C76: one day reads "on 25 December 2024" and one whole month "in December 2021", not "from ...
to ..." the same day or month."""
import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from moco_agent import counting, stats

ROOT = Path(__file__).resolve().parents[2]
WEAPON = ROOT / "config" / "sources" / "weapon_pointing.json"
COPY = SimpleNamespace(newest_day=date(2026, 11, 18))


def weapon():
    return json.loads(WEAPON.read_text())


def test_c75_weapon_pointing_starts_on_1_february_2022_and_says_why():
    source = weapon()
    assert source["coverage_start"] == "2022-02-01"
    note = [n for n in source["notes"] if "February 2022" in n]
    assert len(note) == 1 and "leave the earlier ones out" in note[0], source["notes"]
    assert counting.covers_text(source, COPY).startswith("1 February 2022 to ")


def test_c75_a_model_over_a_period_from_2021_starts_in_february_2022():
    months = stats.window(weapon(), COPY, {"from": "2021-01-01", "to": "2026-11-18"}, 0)
    assert months[0] == (2022, 2), months[:3]


def test_c75_records_before_february_2022_are_not_counted():
    source = weapon()
    rows = [{"id": str(i), "event_date_time": when} for i, when in enumerate(
        ["2021-06-01T10:00:00.000", "2022-01-31T23:00:00.000",
         "2022-02-01T00:30:00.000", "2023-05-05T12:00:00.000"])]
    spec = {"period": {"from": "2021-01-01", "to": "2026-11-18"}, "filters": [], "group_by": []}
    assert counting.tally(source, rows, spec, COPY.newest_day)["total"] == 2


def test_c75_a_count_of_2021_is_outside_what_the_copy_covers():
    with pytest.raises(counting.SpecError) as e:
        counting.check_spec(weapon(), COPY, {"period": {"year": 2021}})
    assert e.value.code == "OUT_OF_COVERAGE"
    assert "1 February 2022" in json.dumps(e.value.hint), e.value.hint


@pytest.mark.parametrize("period,words,label", [
    ({"from": "2024-12-25", "to": "2024-12-25"}, "on 25 December 2024", "25 December 2024"),
    ({"from": "2021-12-01", "to": "2021-12-31"}, "in December 2021", "December 2021"),
    ({"from": "2024-02-01", "to": "2024-02-29"}, "in February 2024", "February 2024"),
    ({"from": "2024-02-01", "to": "2024-02-28"},
     "from 1 February 2024 to 28 February 2024", "from 1 February 2024 to 28 February 2024"),
    ({"from": "2025-01-01", "to": "2025-11-18"},
     "from 1 January 2025 to 18 November 2025", "from 1 January 2025 to 18 November 2025"),
    ({"year": 2025}, "in 2025", "2025"),
])
def test_c76_one_day_and_one_whole_month_read_plainly(period, words, label):
    assert counting.period_words(period) == words
    assert counting.period_label(period) == label
