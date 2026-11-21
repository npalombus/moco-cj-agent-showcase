"""S3A C77 (D-093): a breakdown by district lists the districts in number order. Seen in the
variety trial of 21 November 2026: substance abuse calls by district came out as district 4, 3, 6,
5, 2, 1, 8 (12 of the 13 source files list their districts in no order). Written by the planning
chat (no separate tests session, D-093)."""
import json
from datetime import date
from pathlib import Path

import pytest

from moco_agent import counting

ROOT = Path(__file__).resolve().parents[2]
REAL = sorted((ROOT / "config" / "sources").glob("*.json"))


@pytest.mark.parametrize("path", REAL, ids=[p.stem for p in REAL])
def test_c77_every_real_source_breaks_down_by_district_in_number_order(path):
    source = json.loads(path.read_text())
    labels = counting.group_labels(source, "district", {"year": 2025}, date(2026, 11, 18))
    numbers = [int(label.split()[1]) for label in labels]
    assert numbers == sorted(numbers) and len(numbers) >= 6, labels


def test_c77_other_categories_keep_file_order():
    f = {"kind": "category", "values": {"b": "White", "a": "Black", "c": "Asian"}}
    assert counting._labels(f) == ["White", "Black", "Asian"]


def test_c77_a_mixed_list_keeps_file_order():
    f = {"kind": "category", "values": {"x": "district 3", "y": "district 1", "z": "unknown"}}
    assert counting._labels(f) == ["district 3", "district 1", "unknown"]
