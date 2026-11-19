"""Points 5 and 6: provenance and repeatability (design sections 4, 6, 7 and 8).

Changed copies of the data are written into pytest's tmp_path, never into the repo.
"""
import hashlib
import json
import shutil

from support import (DATA_CSV, ROUTER_RULES, SUPPORTED, TRUTH_JSON, ask, check_numbers,
                     check_refused, expected_values, first_index, read_rows, record,
                     snapshot_of, write_rows)


def test_snapshot_id_is_sha256_of_the_data_file(runs_dir):
    question, _, _ = SUPPORTED["S1"]
    d = record(ask(question, runs_dir))
    computed_here = hashlib.sha256(DATA_CSV.read_bytes()).hexdigest()
    assert d["snapshot_id"] == "sha256:" + computed_here


def test_removing_one_counted_row_changes_snapshot_and_lowers_total_by_one(tmp_path, runs_dir):
    question, year, age_group = SUPPORTED["S1"]
    rows = read_rows()
    removed = rows.pop(first_index(rows, f"{year}-", age_group))  # a row S1 counts
    copy = write_rows(tmp_path / "one_row_removed.csv", rows)

    d = record(ask(question, runs_dir, data_path=copy))

    assert d["status"] == "ANSWERED", (d["reason_code"], d["user_facing_summary"])
    assert d["computed_values"]["total"] == expected_values(year, age_group)["total"] - 1
    want = expected_values(year, age_group)
    want["by_month"][removed["arrest_date"][:7]] -= 1
    want["total"] -= 1
    check_numbers(d, year, age_group, want)
    assert d["snapshot_id"] == snapshot_of(copy)
    assert d["snapshot_id"] != snapshot_of(DATA_CSV)


def test_counts_come_from_the_file_at_the_time_of_the_call(tmp_path, runs_dir):
    """Added by the tests session. The same path is rewritten between two calls, and an
    unchanged truth file sits beside it: the second answer must follow the new rows, so no
    stored, cached or truth-file numbers can stand in for counting."""
    question, year, age_group = SUPPORTED["S1"]
    folder = tmp_path / "data" / "synthetic"
    folder.mkdir(parents=True)
    path = folder / DATA_CSV.name
    shutil.copyfile(DATA_CSV, path)
    shutil.copyfile(TRUTH_JSON, folder / TRUTH_JSON.name)

    first = record(ask(question, runs_dir, data_path=path))
    rows = read_rows(path)
    rows.pop(first_index(rows, f"{year}-", age_group))
    write_rows(path, rows)
    second = record(ask(question, runs_dir, data_path=path))

    assert (first["status"], second["status"]) == ("ANSWERED", "ANSWERED")
    check_numbers(first, year, age_group)
    assert second["computed_values"]["total"] == first["computed_values"]["total"] - 1
    assert second["snapshot_id"] == snapshot_of(path)
    assert second["snapshot_id"] != first["snapshot_id"]


def test_a_month_with_no_rows_is_counted_as_zero(tmp_path, runs_dir):
    """Added by the tests session. Section 4: all 12 months, even one with no rows."""
    question, year, age_group = SUPPORTED["S1"]
    month = f"{year}-03"
    rows = [r for r in read_rows()
            if not (r["arrest_date"].startswith(month) and r["age_group"] == age_group)]
    copy = write_rows(tmp_path / "march_removed.csv", rows)

    d = record(ask(question, runs_dir, data_path=copy))

    assert d["status"] == "ANSWERED", (d["reason_code"], d["user_facing_summary"])
    want = expected_values(year, age_group)
    want["total"] -= want["by_month"][month]
    want["by_month"][month] = 0
    check_numbers(d, year, age_group, want)


def test_a_year_with_rows_but_none_for_the_age_group_is_answered_with_zeros(tmp_path, runs_dir):
    """Added by the tests session. Section 8: OUT_OF_COVERAGE is for a year with no rows.
    Here 2025 still has rows for the other age groups, so the answer is 12 zeros."""
    question, year, age_group = SUPPORTED["S1"]
    rows = [r for r in read_rows()
            if not (r["arrest_date"].startswith(f"{year}-") and r["age_group"] == age_group)]
    copy = write_rows(tmp_path / "no_18_25_rows_in_2025.csv", rows)

    d = record(ask(question, runs_dir, data_path=copy))

    assert d["status"] == "ANSWERED", (d["reason_code"], d["user_facing_summary"])
    zeros = {month: 0 for month in expected_values(year, age_group)["by_month"]}
    check_numbers(d, year, age_group, {"by_month": zeros, "total": 0})


def test_coverage_comes_from_the_rows_in_the_data(tmp_path, runs_dir):
    """Added by the tests session. Section 8: OUT_OF_COVERAGE means the year has no rows
    in the data file used."""
    question, year, _ = SUPPORTED["S1"]
    rows = [r for r in read_rows() if not r["arrest_date"].startswith(f"{year}-")]
    copy = write_rows(tmp_path / f"no_{year}_rows.csv", rows)

    d = check_refused(ask(question, runs_dir, data_path=copy), runs_dir, question=question,
                      router=ROUTER_RULES, status="UNSUPPORTED", code="OUT_OF_COVERAGE",
                      data_path=copy)
    assert d["snapshot_id"] == snapshot_of(copy)  # the file was read to find no rows


def test_same_question_twice_same_answer_new_run(runs_dir):
    """Point 6."""
    question, _, _ = SUPPORTED["S1"]
    first = record(ask(question, runs_dir))
    second = record(ask(question, runs_dir))

    for key in ("computed_values", "snapshot_id", "calculation_version"):
        assert first[key] == second[key], key
    assert first["run_id"] != second["run_id"]
    for d in (first, second):
        manifest = runs_dir / d["run_id"] / "manifest.json"
        assert json.loads(manifest.read_text(encoding="utf-8"))["run_id"] == d["run_id"]
