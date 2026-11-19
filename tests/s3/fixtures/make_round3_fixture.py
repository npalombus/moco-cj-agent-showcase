"""Make the third SYNTHETIC fixture source for the stage 3 Part A round 3 tests (brief
S3A-R3-A step 3; docs/S3A-DESIGN.md C23: "with three sources (a third made-up fixture
source)").

Everything here is made up for tests. No row, label, place or address is real: ids start
with FIXTURE-, the one label pair is generic ("area North", "area South"), and the address
is on the reserved .invalid domain, which can never be reached.

    .venv/bin/python tests/s3/fixtures/make_round3_fixture.py

writes, next to this script:

    round3/sources/visits_like.json   a source file in the shape of C3, with its own unit
                                      words ("visit record", "visit records"), one place
                                      category and no age, flag or person field
    round3/rows/visits_like.json      the rows a fake transport serves: 36 rows over 2025
                                      and the first half of 2026, as JSON objects of strings

The files live in their own folder, round3/, and not in sources/ and rows/ beside the two
older fixtures: tests/s3/test_s3_sources.py loads fixtures/sources/ and expects exactly
the two older fixtures there, so a third file in that folder would change an existing test.

The seed is fixed, so the files are the same every time; running the script again leaves
them unchanged.
"""
import json
import random
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "round3"
SEED = 2313  # fixed: round 3 of stage 3, written 2026-11-13
ROWS = 36
NOTE = ("SYNTHETIC: made up for the stage 3 Part A round 3 tests by tests/s3/fixtures/"
        "make_round3_fixture.py. Not county data; no row is a real record.")

VISITS_LIKE = {
    "id": "FIXTURE:visits_like",
    "data_class": "COUNTY_OPEN_DATA",
    "fixture_note": NOTE + " data_class says COUNTY_OPEN_DATA only so that county mode reads "
                           "it.",
    "title": "SYNTHETIC fixture visits (made up for tests)",
    "publisher": "SYNTHETIC fixture publisher (made up for tests)",
    "address": "https://fixture.invalid/resource/visits-like.json",
    "page": "https://fixture.invalid/d/visits-like",
    "row_meaning": "one made-up visit",
    "unit": {"one": "visit record", "many": "visit records"},
    "is_not": ["people", "cases", "a rate"],
    "time_field": "visited_at",
    "coverage_start": "2025-01-01",
    "floor": 10,
    "fields": [
        {"name": "id", "kind": "key"},
        {"name": "area", "kind": "category", "person": False, "sensitive": False,
         "dimension": "area", "wording": "in {labels}",
         "values": {"N": "area North", "S": "area South"}},
    ],
    "notices": [
        "SYNTHETIC visits fixture notice: made up for tests; no county publishes this.",
    ],
    "approved_by": "nobody (test fixture)",
    "approved_on": "2026-11-13",
    "approval_record": "none: a SYNTHETIC test fixture",
}


def make_rows():
    """ROWS made-up rows, one id each, spread over 1 January 2025 to 30 June 2026."""
    chance = random.Random(SEED)
    first, days = date(2025, 1, 1), (date(2026, 6, 30) - date(2025, 1, 1)).days
    out = []
    for n in range(1, ROWS + 1):
        day = first + timedelta(days=chance.randrange(days + 1))
        when = f"{day:%Y-%m-%d}T{chance.randrange(24):02d}:{chance.randrange(60):02d}:00.000"
        out.append({"id": f"FIXTURE-V-{n:04d}", "visited_at": when,
                    "area": chance.choice(["N", "S"]), "data_class": "SYNTHETIC"})
    out.sort(key=lambda row: (row["visited_at"], row["id"]))
    return out


def main():
    rows = make_rows()
    assert len({row["id"] for row in rows}) == ROWS
    assert all(row["id"].startswith("FIXTURE-") for row in rows)
    for folder, data in ((OUT / "sources", VISITS_LIKE),
                         (OUT / "rows", {"note": NOTE, "rows": rows})):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "visits_like.json").write_text(json.dumps(data, indent=2) + "\n",
                                                 encoding="utf-8")


if __name__ == "__main__":
    main()
