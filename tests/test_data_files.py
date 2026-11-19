"""Point 1: the data files themselves (design section 3). These need no moco_agent."""
import calendar
import random
from collections import Counter

from support import AGE_GROUPS, COLUMNS, DATA_CSV, DATASET_ID, MONTHS, load_truth, read_rows


def test_truth_file_describes_the_synthetic_dataset():
    truth = load_truth()
    assert truth["dataset_id"] == DATASET_ID
    assert truth["data_class"] == "SYNTHETIC"
    assert truth["coverage"] == {"start": "2024-01-01", "end": "2025-12-31"}
    assert truth["age_groups"] == AGE_GROUPS


def test_truth_file_has_24_months_each_with_the_four_age_groups():
    counts = load_truth()["counts"]
    assert list(counts) == MONTHS  # 2024-01 .. 2025-12, in order
    for month, groups in counts.items():
        assert list(groups) == AGE_GROUPS, month


def test_every_truth_count_is_a_whole_number_from_5_to_60():
    for month, groups in load_truth()["counts"].items():
        for group, n in groups.items():
            assert type(n) is int and 5 <= n <= 60, (month, group, n)


def test_truth_counts_are_the_random_375_draws_in_the_stated_order():
    rng = random.Random(375)
    drawn = {m: {g: rng.randint(5, 60) for g in AGE_GROUPS} for m in MONTHS}
    assert load_truth()["counts"] == drawn


def test_csv_has_exactly_the_rows_the_truth_file_says():
    counts = load_truth()["counts"]
    rows = read_rows()
    per_cell = Counter((r["arrest_date"][:7], r["age_group"]) for r in rows)
    for month in MONTHS:
        for group in AGE_GROUPS:
            assert per_cell[(month, group)] == counts[month][group], (month, group)
    assert len(rows) == sum(sum(groups.values()) for groups in counts.values())
    assert set(per_cell) == {(m, g) for m in MONTHS for g in AGE_GROUPS}


def test_csv_header_is_the_four_columns():
    with open(DATA_CSV, encoding="utf-8") as f:
        assert f.readline().rstrip("\r\n") == ",".join(COLUMNS)


def test_every_csv_row_is_labeled_synthetic():
    rows = read_rows()
    assert rows
    assert {r["data_class"] for r in rows} == {"SYNTHETIC"}


def test_arrest_ids_are_unique():
    ids = [r["arrest_id"] for r in read_rows()]
    assert len(ids) == len(set(ids))


def test_csv_follows_the_section_3_layout_row_by_row():
    """ids SYN-000001.. in file order; rows by month, then age group, then i; row i of a
    cell gets day (i % days_in_month) + 1. Rebuilt here from the truth file."""
    counts = load_truth()["counts"]
    rebuilt = []
    for month in MONTHS:
        year, mon = (int(part) for part in month.split("-"))
        days_in_month = calendar.monthrange(year, mon)[1]
        for group in AGE_GROUPS:
            for i in range(counts[month][group]):
                rebuilt.append({
                    "arrest_id": f"SYN-{len(rebuilt) + 1:06d}",
                    "arrest_date": f"{month}-{(i % days_in_month) + 1:02d}",
                    "age_group": group,
                    "data_class": "SYNTHETIC",
                })
    assert read_rows() == rebuilt

