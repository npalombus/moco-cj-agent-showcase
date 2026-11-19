"""Checks on the tests' own helpers in support.py. These need no moco_agent, so they run
now and show that the changed data copies and the number matcher do what they claim."""
import pytest

from support import (COLUMNS, DATA_CSV, NOT_SYNTHETIC_COPIES, read_rows, standalone,
                     write_rows)


def counted_by_s1(row):
    return row["arrest_date"].startswith("2025-") and row["age_group"] == "18_25"


def test_copy_helper_reproduces_the_data_file_byte_for_byte(tmp_path):
    """A changed copy differs from the real file only by the change made to it."""
    copy = write_rows(tmp_path / "copy.csv", read_rows())
    assert copy.read_bytes() == DATA_CSV.read_bytes()


def test_no_data_class_column_copy_has_the_other_three_columns(tmp_path):
    copy = NOT_SYNTHETIC_COPIES["no_data_class_column"](tmp_path)
    with open(copy, encoding="utf-8") as f:
        assert f.readline().rstrip("\n") == ",".join(c for c in COLUMNS if c != "data_class")
    assert len(read_rows(copy)) == len(read_rows())


@pytest.mark.parametrize("key", [k for k in NOT_SYNTHETIC_COPIES if k != "no_data_class_column"])
def test_not_synthetic_copy_changes_only_data_class(key, tmp_path):
    original = read_rows()
    changed = read_rows(NOT_SYNTHETIC_COPIES[key](tmp_path))
    assert len(changed) == len(original)
    differing = [i for i, (a, b) in enumerate(zip(original, changed)) if a != b]
    assert differing
    for i in differing:
        assert changed[i]["data_class"] != "SYNTHETIC"
        assert {k: v for k, v in changed[i].items() if k != "data_class"} == \
               {k: v for k, v in original[i].items() if k != "data_class"}
    if key == "every_row_VERIFIED_OFFICIAL":
        assert len(differing) == len(original)
    else:
        assert len(differing) == 1
        assert not counted_by_s1(original[differing[0]])  # a row S1 does not count


@pytest.mark.parametrize("number, text, found", [
    ("400", "SYNTHETIC: 400 arrest records in 2025.", True),
    ("400", "a total of 400.", True),
    ("400", "(400)", True),
    ("400", "1400 records", False),
    ("400", "4000 records", False),
    ("400", "1,400 records", False),
    ("1393", "1393 records", True),
    ("1,393", "1,393 records", True),
    ("1393", "1,393 records", False),
    ("50", "arrests fell 50 percent", True),
    ("50", "years 2024 and 2025 only", False),
    ("90", "1900 records", False),
])
def test_standalone_number_matcher(number, text, found):
    assert standalone(number, text) is found
