"""Make the SYNTHETIC arrests dataset for stage 1 (design section 3).

The data is invented. It describes no real person or event and says nothing about
Montgomery County.

1. Draws the truth file once with random.Random(375): one whole number from 5 to 60 per
   month (2024-01 .. 2025-12, in order) and age group (in the listed order).
2. Builds the CSV from the truth file as written on disk, with no randomness of its own.

Run: .venv/bin/python tools/make_synthetic.py
Running it again gives byte-for-byte identical files.
"""
import calendar
import csv
import json
import random
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "synthetic"
TRUTH_PATH = OUT_DIR / "SYNTHETIC_arrests_v1.truth.json"
CSV_PATH = OUT_DIR / "SYNTHETIC_arrests_v1.csv"
AGE_GROUPS = ["under_18", "18_25", "26_40", "41_plus"]
MONTHS = [f"{year}-{month:02d}" for year in (2024, 2025) for month in range(1, 13)]


def draw_truth():
    rng = random.Random(375)
    return {
        "dataset_id": "SYNTHETIC:arrests_v1",
        "data_class": "SYNTHETIC",
        "coverage": {"start": "2024-01-01", "end": "2025-12-31"},
        "age_groups": AGE_GROUPS,
        # Months in order, age groups in listed order: the draw order the design fixes.
        "counts": {m: {g: rng.randint(5, 60) for g in AGE_GROUPS} for m in MONTHS},
    }


def write_csv(truth, path):
    """n rows per (month, age group); row i gets day (i % days_in_month) + 1."""
    arrest_no = 0
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["arrest_id", "arrest_date", "age_group", "data_class"])
        for month in sorted(truth["counts"]):
            year, mon = (int(part) for part in month.split("-"))
            days_in_month = calendar.monthrange(year, mon)[1]
            for group in truth["age_groups"]:
                for i in range(truth["counts"][month][group]):
                    arrest_no += 1
                    day = (i % days_in_month) + 1
                    writer.writerow([f"SYN-{arrest_no:06d}", f"{month}-{day:02d}", group, "SYNTHETIC"])
    return arrest_no


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    TRUTH_PATH.write_text(json.dumps(draw_truth(), indent=2) + "\n", encoding="utf-8")
    truth = json.loads(TRUTH_PATH.read_text(encoding="utf-8"))  # the CSV comes from the file
    rows = write_csv(truth, CSV_PATH)
    print(f"SYNTHETIC data written: {TRUTH_PATH.name}, {CSV_PATH.name} ({rows} rows)")


if __name__ == "__main__":
    main()
