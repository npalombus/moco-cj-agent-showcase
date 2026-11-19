"""Make the two SYNTHETIC fixture sources for the stage 3 Part A tests (brief S3A-A step 3).

Everything here is made up for tests. No row, label, place or address is real: ids start
with FIXTURE-, labels are generic ("district 3", "group Alpha", "station 2"), and both
addresses are on the reserved .invalid domain, which can never be reached.

    .venv/bin/python tests/s3/fixtures/make_fixtures.py

writes, next to this script:

    sources/arrests_like.json   a source file in the shape of C3, shaped like Police Arrests:
                                age, three person categories, a place category with a value
                                missing on some rows, a flag, a time field; 600 rows over
                                2024 to 2026, the last year unfinished (newest 17 Sep 2026)
    sources/coded_like.json     coded labels (two raw spellings mapped to one label), a
                                different unit, no flag, floor 10; 300 rows, 2025 to 2026
                                (newest 20 Aug 2026)
    rows/arrests_like.json      the rows a fake transport serves, as the county's service
    rows/coded_like.json        does: JSON objects of strings, a key left out when empty

The seed is fixed, so the files are the same every time. The script checks, by plain
counting of its own, that each case the tests rely on holds on purpose (DESIGNED below), and
stops if one does not. Running it again must leave the files unchanged (git diff is empty).

The source files carry `data_class` COUNTY_OPEN_DATA only so that county mode (C0) will read
them; their titles, notices and every row say SYNTHETIC.
"""
import calendar
import json
import random
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEED = 375  # the course number; fixed so every run gives the same files
WEEKDAYS = list(calendar.day_name)  # Monday first
NOTE = ("SYNTHETIC: made up for the stage 3 Part A tests by tests/s3/fixtures/"
        "make_fixtures.py. Not county data; no row is a real record.")

# ---- the two source files (C3) ----------------------------------------------------------

ARRESTS_LIKE = {
    "id": "FIXTURE:arrests_like",
    "data_class": "COUNTY_OPEN_DATA",
    "fixture_note": NOTE + " data_class says COUNTY_OPEN_DATA only so that county mode reads "
                           "it.",
    "title": "SYNTHETIC fixture arrests (made up for tests)",
    "publisher": "SYNTHETIC fixture publisher (made up for tests)",
    "address": "https://fixture.invalid/resource/arrests-like.json",
    "page": "https://fixture.invalid/d/arrests-like",
    "row_meaning": "one made-up arrest",
    "unit": {"one": "arrest record", "many": "arrest records"},
    "is_not": ["people", "charges", "cases", "convictions", "sentences", "a rate"],
    "time_field": "event_date_time",
    "coverage_start": "2024-01-01",
    "floor": 10,
    "fields": [
        {"name": "id", "kind": "key"},
        {"name": "age", "kind": "age", "usable": [10, 98],
         "bands": [[10, 17], [18, 24], [25, 34], [35, 44], [45, 54], [55, 98]],
         "sensitive": False},
        {"name": "gender", "kind": "category", "person": True, "sensitive": True,
         "dimension": "gender", "wording": "recorded as {labels}",
         "values": {"Female": "female", "Male": "male"}},
        {"name": "race", "kind": "category", "person": True, "sensitive": True,
         "dimension": "race", "wording": "recorded as {labels}",
         "values": {"Alpha": "group Alpha", "Beta": "group Beta", "Gamma": "group Gamma"}},
        {"name": "ethnicity", "kind": "category", "person": True, "sensitive": True,
         "dimension": "ethnicity", "wording": "recorded as {labels}",
         "values": {"HISP": "Hispanic", "NONHISP": "not Hispanic"}},
        {"name": "district", "kind": "category", "person": False, "sensitive": False,
         "dimension": "district", "wording": "in {labels}",
         "values": {str(n): f"district {n}" for n in range(1, 7)}},
        {"name": "adjacent_to_school", "kind": "flag", "dimension": "distance from a school",
         "yes_raw": "1", "no_raw": "0", "yes": "within 500 feet of a school",
         "no": "not within 500 feet of a school"},
    ],
    "notices": [
        "SYNTHETIC fixture notice: these records are made up for tests and come from no "
        "county.",
        "SYNTHETIC fixture notice two: THE FIXTURE MAKES NO PROMISE ABOUT ANY OF THIS DATA.",
    ],
    "approved_by": "nobody (test fixture)",
    "approved_on": "2026-11-12",
    "approval_record": "none: a SYNTHETIC test fixture",
}

CODED_LIKE = {
    "id": "FIXTURE:coded_like",
    "data_class": "COUNTY_OPEN_DATA",
    "fixture_note": NOTE + " data_class says COUNTY_OPEN_DATA only so that county mode reads "
                           "it.",
    "title": "SYNTHETIC fixture intake records (made up for tests)",
    "publisher": "SYNTHETIC fixture publisher (made up for tests)",
    "address": "https://fixture.invalid/resource/coded-like.json",
    "page": "https://fixture.invalid/d/coded-like",
    "row_meaning": "one made-up intake",
    "unit": {"one": "intake record", "many": "intake records"},
    "is_not": ["people", "charges", "cases", "a rate"],
    "time_field": "booked_at",
    "coverage_start": "2025-01-01",
    "floor": 10,
    "fields": [
        {"name": "case_no", "kind": "key"},
        {"name": "age_years", "kind": "age", "usable": [12, 90],
         "bands": [[12, 17], [18, 29], [30, 49], [50, 90]], "sensitive": False},
        {"name": "race_code", "kind": "category", "person": True, "sensitive": True,
         "dimension": "race", "wording": "recorded as {labels}",
         "values": {"W": "group W", "White": "group W", "B": "group B", "Blk": "group B",
                    "U": "group U"}},
        {"name": "sex", "kind": "category", "person": True, "sensitive": True,
         "dimension": "sex", "wording": "recorded as {labels}",
         "values": {"F": "female", "M": "male"}},
        {"name": "station", "kind": "category", "person": False, "sensitive": False,
         "dimension": "station", "wording": "at {labels}",
         "values": {"1D": "station 1", "2D": "station 2", "2nd": "station 2",
                    "3D": "station 3", "3rd": "station 3"}},
    ],
    "notices": [
        "SYNTHETIC coded fixture notice: made up for tests; no county publishes this.",
    ],
    "approved_by": "nobody (test fixture)",
    "approved_on": "2026-11-12",
    "approval_record": "none: a SYNTHETIC test fixture",
}

# ---- what the rows hold on purpose (checked below by plain counting) -------------------

DESIGNED = {
    "arrests_like": {
        "rows": 600,
        "newest": "2026-09-17T08:30:00.000",
        "per_year": {2024: 230, 2025: 240, 2026: 130},
        # 2025, within 500 feet of a school, by district: groups of 0, 1, 9 and 10; and 1
        # left out (no district).
        "2025 school by district": {"district 1": 10, "district 2": 9, "district 3": 1,
                                    "district 4": 0, "district 5": 24, "district 6": 31},
        "2025 school no district": 1,
        # Left out by district: 10 in 2024, 9 in 2025, 0 in 2026 (and 1 above).
        "no district": {2024: 10, 2025: 9, 2026: 0},
        # 2024 by district: a tie for the most (district 2 and district 3), one fewest.
        "2024 by district": {"district 1": 40, "district 2": 45, "district 3": 45,
                             "district 4": 35, "district 5": 35, "district 6": 20},
        # 2026 by district: a tie for the most and a tie for the fewest.
        "2026 by district": {"district 1": 25, "district 2": 25, "district 3": 20,
                             "district 4": 20, "district 5": 20, "district 6": 20},
        # 2026 by gender: every group equal.
        "2026 by gender": {"female": 65, "male": 65},
        # 2026 by race: 2 of the 3 groups with records would be hidden (more than half).
        "2026 by race": {"group Alpha": 3, "group Beta": 2, "group Gamma": 125},
        # 2026 by ethnicity: 1 of 2 hidden (exactly half: allowed).
        "2026 by ethnicity": {"Hispanic": 5, "not Hispanic": 125},
        # Ages left out (not usable): 10 in 2024, 5 in 2025 (0, 9, 99, a non-number, 17.5).
        "unusable ages": {2024: 10, 2025: 5, 2026: 0},
        "2025 unusable age values": ["0", "9", "99", "unknown", "17.5"],
        "2025 under 18": 31,
        "no gender 2024": 2,
        "no flag 2024": 3,
        # 2025 by hour: 10 pm has the most, no record at all at 5 am; every other hour has
        # at least one. No row of any year is at 5 am (so "to 5" reads the same whether the
        # hour 5 is in or out).
        "2025 by hour": {"most": 22, "most_n": 25},
        "2025 by month": {"most": 7, "most_n": 30, "fewest": 2, "fewest_n": 12},
        "2025 by weekday": {"Saturday": 45, "Tuesday": 25, "Monday": 34, "Wednesday": 34,
                            "Thursday": 34, "Friday": 34, "Sunday": 34},
    },
    "coded_like": {
        "rows": 300,
        "newest": "2026-08-20T13:05:00.000",
        "per_year": {2025: 200, 2026: 100},
        # Two raw spellings, one label: station 3 is "3D" (40) and "3rd" (15) in 2025;
        # group W is "W" (60) and "White" (30) in 2025.
        "2025 station 3 raw": {"3D": 40, "3rd": 15},
        "2025 group W raw": {"W": 60, "White": 30},
        "no station": {2025: 6, 2026: 0},
    },
}


# ---- helpers ------------------------------------------------------------------------------

def stamp(day, hour, minute):
    return f"{day:%Y-%m-%d}T{hour:02d}:{minute:02d}:00.000"


def row(rid, when, **values):
    """A row as the service gives it: strings, and a key left out when its value is None."""
    out = {"id": rid} if not rid.startswith("FIXTURE-C") else {"case_no": rid}
    out.update({k: v for k, v in values.items() if v is not None})
    out["data_class"] = "SYNTHETIC"  # not a listed field: a copy must drop it
    return out


def days_of(year, month, weekday):
    days = calendar.monthrange(year, month)[1]
    return [date(year, month, d) for d in range(1, days + 1)
            if date(year, month, d).weekday() == weekday]


def random_day(rng, start, end):
    return start + timedelta(days=rng.randrange((end - start).days + 1))


def hour_no_five(rng):
    hour = rng.randrange(23)
    return hour + 1 if hour >= 5 else hour  # 0..23 without 5


# ---- arrests_like -------------------------------------------------------------------------

def arrests_rows(rng):
    rows = []
    serial = iter(range(1, 10_000))

    def rid():
        return f"FIXTURE-A-{next(serial):04d}"

    def usable_age(under_18=False):
        return str(rng.randint(10, 17) if under_18 else rng.choice(
            [18, 19, 20, 21, 22, 24, 25, 28, 30, 33, 35, 38, 41, 44, 47, 52, 55, 61, 70, 98]))

    # -- 2025: 240 rows with designed months, weekdays, hours, districts and flags --------
    months_2025 = [7] * 30 + [2] * 12
    others = [m for m in range(1, 13) if m not in (2, 7)]
    months_2025 += [m for i, m in enumerate(others) for _ in range(19 if i < 2 else 20)]
    weekdays_2025 = ([5] * 45 + [1] * 25 + [0] * 34 + [2] * 34 + [3] * 34 + [4] * 34
                     + [6] * 34)
    hours_2025 = [22] * 25 + [h for i, h in enumerate(h for h in range(24) if h not in (5, 22))
                              for _ in range(10 if i < 17 else 9)]
    assert len(months_2025) == len(weekdays_2025) == len(hours_2025) == 240
    rng.shuffle(weekdays_2025)
    rng.shuffle(hours_2025)
    # Flag yes (76): districts 1..6 as designed, and 1 with no district (key left out).
    school = (["1"] * 10 + ["2"] * 9 + ["3"] * 1 + ["5"] * 24 + ["6"] * 31 + [None])
    # Flag no (164): 8 with no district ("" twice, left out three times, "9" unlisted three
    # times), the rest spread over districts 1..6.
    no_school = ["", "", None, None, None, "9", "9", "9"]
    no_school += [str(1 + i % 6) for i in range(164 - len(no_school))]
    districts = [(d, "1") for d in school] + [(d, "0") for d in no_school]
    rng.shuffle(districts)
    unusable = list(DESIGNED["arrests_like"]["2025 unusable age values"])
    usable_slots = [i for i, (d, f) in enumerate(districts) if d not in (None, "", "9")]
    unusable_at = set(rng.sample(usable_slots, len(unusable)))
    under_18_at = set(rng.sample([i for i in range(240) if i not in unusable_at], 31))
    genders = ["Female"] * 100 + ["Male"] * 140
    rng.shuffle(genders)
    for i in range(240):
        month, weekday, hour = months_2025[i], weekdays_2025[i], hours_2025[i]
        day = rng.choice(days_of(2025, month, weekday))
        district, flag = districts[i]
        age = unusable.pop() if i in unusable_at else usable_age(i in under_18_at)
        race = rng.choice(["Alpha", "Beta", "Gamma", "Gamma"])
        rows.append(row(rid(), None, event_date_time=stamp(day, hour, rng.randrange(60)),
                        age=age, gender=genders[i], race=race,
                        ethnicity=rng.choice(["HISP", "NONHISP", "NONHISP"]),
                        district=district, adjacent_to_school=flag))

    # -- 2024: 230 rows; tie for the most by district; 10 unusable ages; gaps -----------
    districts_2024 = (["1"] * 40 + ["2"] * 45 + ["3"] * 45 + ["4"] * 35 + ["5"] * 35
                      + ["6"] * 20 + [None] * 4 + [""] * 3 + ["9"] * 3)
    rng.shuffle(districts_2024)
    placed = [i for i, d in enumerate(districts_2024) if d not in (None, "", "9")]
    picks = rng.sample(placed, 15)
    bad_age_at, no_gender_at, no_flag_at = set(picks[:10]), set(picks[10:12]), set(picks[12:])
    bad_ages = iter(["", "00", "99", "N/A", "120", "8", "9", "unknown", "0", "1"])
    for i, district in enumerate(districts_2024):
        day = random_day(rng, date(2024, 1, 2), date(2024, 12, 31))
        rows.append(row(rid(), None,
                        event_date_time=stamp(day, hour_no_five(rng), rng.randrange(60)),
                        age=next(bad_ages) if i in bad_age_at else usable_age(rng.random() < .1),
                        gender="" if i in no_gender_at else rng.choice(["Female", "Male"]),
                        race=rng.choice(["Alpha", "Beta", "Gamma"]),
                        ethnicity=rng.choice(["HISP", "NONHISP"]),
                        district=district,
                        adjacent_to_school=None if i in no_flag_at else rng.choice(["0", "1"])))

    # -- 2026: 130 rows to 17 September; ties, all equal, too fine ------------------------
    districts_2026 = ["1"] * 25 + ["2"] * 25 + ["3"] * 20 + ["4"] * 20 + ["5"] * 20 + ["6"] * 20
    races_2026 = ["Alpha"] * 3 + ["Beta"] * 2 + ["Gamma"] * 125
    ethnicities_2026 = ["NONHISP"] * 5 + ["HISP"] * 5 + ["NONHISP"] * 120  # Hispanic: Gamma
    genders_2026 = ["Female"] * 65 + ["Male"] * 65
    rng.shuffle(districts_2026)
    rng.shuffle(genders_2026)
    for i in range(130):
        if i == 0:  # the newest record of the copy, alone on its day
            when = DESIGNED["arrests_like"]["newest"]
        else:
            day = random_day(rng, date(2026, 1, 1), date(2026, 9, 16))
            when = stamp(day, hour_no_five(rng), rng.randrange(60))
        rows.append(row(rid(), None, event_date_time=when, age=usable_age(rng.random() < .12),
                        gender=genders_2026[i], race=races_2026[i],
                        ethnicity=ethnicities_2026[i], district=districts_2026[i],
                        adjacent_to_school=rng.choice(["0", "1"])))

    # A few rows share their exact time with another row, so paging ordered by the time
    # field alone could overlap (C4: "ordered so that pages cannot overlap").
    for a, b in [(250, 251), (300, 301), (500, 501)]:  # 2024 and 2026 only
        rows[b]["event_date_time"] = rows[a]["event_date_time"]
    rng.shuffle(rows)  # the service's own order is not the id order
    return rows


# ---- coded_like ----------------------------------------------------------------------------

def coded_rows(rng):
    rows = []
    serial = iter(range(1, 10_000))
    stations_2025 = (["3D"] * 40 + ["3rd"] * 15 + ["1D"] * 60 + ["2D"] * 50 + ["2nd"] * 29
                     + [None] * 3 + [""] * 2 + ["4D"] * 1)
    races_2025 = ["W"] * 60 + ["White"] * 30 + ["B"] * 50 + ["Blk"] * 40 + ["U"] * 20
    rng.shuffle(stations_2025)
    rng.shuffle(races_2025)
    for i in range(200):
        day = random_day(rng, date(2025, 1, 1), date(2025, 12, 31))
        rows.append(row(f"FIXTURE-C-{next(serial):04d}", None,
                        booked_at=stamp(day, hour_no_five(rng), rng.randrange(60)),
                        age_years=str(rng.choice([12, 14, 16, 17, 18, 22, 27, 29, 30, 41, 49,
                                                  50, 63, 90])),
                        race_code=races_2025[i], sex=rng.choice(["F", "M"]),
                        station=stations_2025[i]))
    for i in range(100):
        if i == 0:
            when = DESIGNED["coded_like"]["newest"]
        else:
            day = random_day(rng, date(2026, 1, 1), date(2026, 8, 19))
            when = stamp(day, hour_no_five(rng), rng.randrange(60))
        rows.append(row(f"FIXTURE-C-{next(serial):04d}", None, booked_at=when,
                        age_years=str(rng.choice([13, 17, 19, 25, 33, 45, 58, 70])),
                        race_code=rng.choice(["W", "White", "B", "Blk", "U"]),
                        sex=rng.choice(["F", "M"]),
                        station=rng.choice(["1D", "2D", "2nd", "3D", "3rd"])))
    rng.shuffle(rows)
    return rows


# ---- the checks (plain counting, independent of tests/s3/s3support.py) ---------------------

def check_arrests(rows):
    d = DESIGNED["arrests_like"]
    assert len(rows) == d["rows"]
    assert all(r["id"].startswith("FIXTURE-") for r in rows)
    assert len({r["id"] for r in rows}) == len(rows)
    times = [r["event_date_time"] for r in rows]
    assert max(times) == d["newest"] and times.count(d["newest"]) == 1
    assert all(t[11:13] != "05" for t in times), "no row may be at 5 am"
    year = lambda r: int(r["event_date_time"][:4])  # noqa: E731
    for y, n in d["per_year"].items():
        assert sum(year(r) == y for r in rows) == n, y
    labels = {str(n): f"district {n}" for n in range(1, 7)}

    def by(rows_, key, mapping):
        out = {label: 0 for label in mapping.values()}
        for r in rows_:
            if r.get(key) in mapping:
                out[mapping[r[key]]] += 1
        return out

    y2025 = [r for r in rows if year(r) == 2025]
    school = [r for r in y2025 if r.get("adjacent_to_school") == "1"]
    assert by(school, "district", labels) == d["2025 school by district"]
    assert sum(r.get("district") not in labels for r in school) == d["2025 school no district"]
    for y, n in d["no district"].items():
        assert sum(year(r) == y and r.get("district") not in labels for r in rows) == n, y
    y2024 = [r for r in rows if year(r) == 2024]
    y2026 = [r for r in rows if year(r) == 2026]
    assert by(y2024, "district", labels) == d["2024 by district"]
    assert by(y2026, "district", labels) == d["2026 by district"]
    assert by(y2026, "gender", {"Female": "female", "Male": "male"}) == d["2026 by gender"]
    assert by(y2026, "race", {"Alpha": "group Alpha", "Beta": "group Beta",
                              "Gamma": "group Gamma"}) == d["2026 by race"]
    assert by(y2026, "ethnicity", {"HISP": "Hispanic", "NONHISP": "not Hispanic"}) == \
        d["2026 by ethnicity"]
    assert all(r["race"] == "Gamma" for r in y2026 if r["ethnicity"] == "HISP")

    def usable(r):
        text = r.get("age")
        return text is not None and text.isdigit() and 10 <= int(text) <= 98

    for y, n in d["unusable ages"].items():
        assert sum(year(r) == y and not usable(r) for r in rows) == n, y
    assert sorted(r["age"] for r in y2025 if not usable(r)) == \
        sorted(d["2025 unusable age values"])
    assert sum(usable(r) and int(r["age"]) <= 17 for r in y2025) == d["2025 under 18"]
    assert sum(r.get("gender") not in ("Female", "Male") for r in rows) == d["no gender 2024"]
    assert sum(r.get("adjacent_to_school") not in ("0", "1") for r in rows) == d["no flag 2024"]
    assert all(r.get("gender") in ("Female", "Male") for r in y2025 + y2026)
    assert all(r.get("adjacent_to_school") in ("0", "1") for r in y2025 + y2026)
    # The gaps never meet in one row: each row lacks at most one usable value.
    for r in rows:
        gaps = [r.get("district") not in labels, not usable(r),
                r.get("gender") not in ("Female", "Male"),
                r.get("adjacent_to_school") not in ("0", "1")]
        assert sum(gaps) <= 1, r
    hours = {h: 0 for h in range(24)}
    months = {m: 0 for m in range(1, 13)}
    weekdays = {name: 0 for name in WEEKDAYS}
    for r in y2025:
        t = r["event_date_time"]
        hours[int(t[11:13])] += 1
        months[int(t[5:7])] += 1
        weekdays[WEEKDAYS[date.fromisoformat(t[:10]).weekday()]] += 1
    top = d["2025 by hour"]
    assert hours[top["most"]] == top["most_n"] and hours[5] == 0
    assert all(0 < n < top["most_n"] for h, n in hours.items() if h not in (5, top["most"]))
    m = d["2025 by month"]
    assert months[m["most"]] == m["most_n"] and months[m["fewest"]] == m["fewest_n"]
    assert all(m["fewest_n"] < n < m["most_n"] for k, n in months.items()
               if k not in (m["most"], m["fewest"]))
    assert weekdays == d["2025 by weekday"]


def check_coded(rows):
    d = DESIGNED["coded_like"]
    assert len(rows) == d["rows"]
    assert all(r["case_no"].startswith("FIXTURE-") for r in rows)
    assert len({r["case_no"] for r in rows}) == len(rows)
    times = [r["booked_at"] for r in rows]
    assert max(times) == d["newest"] and times.count(d["newest"]) == 1
    assert all(t[11:13] != "05" for t in times)
    year = lambda r: int(r["booked_at"][:4])  # noqa: E731
    for y, n in d["per_year"].items():
        assert sum(year(r) == y for r in rows) == n
    y2025 = [r for r in rows if year(r) == 2025]
    for raw, n in d["2025 station 3 raw"].items():
        assert sum(r.get("station") == raw for r in y2025) == n
    for raw, n in d["2025 group W raw"].items():
        assert sum(r.get("race_code") == raw for r in y2025) == n
    listed = {"1D", "2D", "2nd", "3D", "3rd"}
    for y, n in d["no station"].items():
        assert sum(year(r) == y and r.get("station") not in listed for r in rows) == n


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    rng = random.Random(SEED)
    arrests = arrests_rows(rng)
    coded = coded_rows(rng)
    check_arrests(arrests)
    check_coded(coded)
    write(HERE / "sources" / "arrests_like.json", ARRESTS_LIKE)
    write(HERE / "sources" / "coded_like.json", CODED_LIKE)
    write(HERE / "rows" / "arrests_like.json", {"note": NOTE, "rows": arrests})
    write(HERE / "rows" / "coded_like.json", {"note": NOTE, "rows": coded})
    print(f"arrests_like: {len(arrests)} rows; coded_like: {len(coded)} rows; every check held")


if __name__ == "__main__":
    main()
