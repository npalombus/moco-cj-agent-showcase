"""Make the SYNTHETIC fixture sources for the stage 3 Part S tests (brief S3S-A step 4).

Everything here is made up for tests. No row, label, place or address is real: ids start
with FIXTURE-, labels are generic ("district 3", "shift B", "batch R100", "zone 4") and both
addresses are on the reserved .invalid domain, which can never be reached.

    .venv/bin/python tests/s3s/fixtures/make_fixtures.py

writes, next to this script:

    sources/stats_like.json   a source file in the shape of C3 (docs/S3A-DESIGN.md), shaped
                              like Police Arrests: age, gender (a sensitive person field),
                              district, shift, two flags; coverage from 1 January 2021
    rows/stats_like.json      its rows, as the fake transport serves them: about 9,500 rows
                              over five full years (2021 to 2025) and one unfinished year
                              (2026, newest record 14 October 2026)
    sources/stats_edges.json  a small source whose `batch` field picks out one made-up case
                              per refusal of S1 (docs/S3S-DESIGN.md), each at its edge
    rows/stats_edges.json     its rows

The seed is fixed, so the files are the same every time; running the script again leaves
them unchanged (git diff is empty). The script checks, by plain counting, every counting
fact the tests rely on and stops if one does not hold. The statistical facts (what is clear
and what is not) are checked by tests/s3s/s3ssupport.py, and against R by
kit-log/raw/S3S-A-r-crosscheck.R; the fixture was tuned until both agreed.

S2 (the window): the newest record of both sources is 14 October 2026, so the last full
month in a copy is September 2026, and with `drop_newest_months` 1 the models end in August
2026. Every case below that reaches into 2026 is built with that in mind: the "last six
months" of the fit line are March to August 2026; September and October 2026 are never used
by a model. Most tests use the period 2021 to 2025, which the dropped month does not touch.

The source files carry `data_class` COUNTY_OPEN_DATA only so that county mode (C0) reads
them; their titles, notices and every row say SYNTHETIC.
"""
import calendar
import json
from datetime import date
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SEED = 375  # the course number; fixed so every run gives the same files
NOTE = ("SYNTHETIC: made up for the stage 3 Part S tests by tests/s3s/fixtures/"
        "make_fixtures.py. Not county data; no row is a real record.")
NEWEST = date(2026, 10, 14)
NEWEST_TIME = "2026-10-14T13:05:00.000"  # the anchor row: the newest record of each source
FIRST = (2021, 1)
LAST = (2026, 10)

AGE_FIELD = {"name": "age", "kind": "age", "usable": [10, 98],
             "bands": [[10, 17], [18, 24], [25, 34], [35, 44], [45, 54], [55, 98]],
             "sensitive": False}
GENDER_FIELD = {"name": "gender", "kind": "category", "person": True, "sensitive": True,
                "dimension": "gender", "wording": "recorded as {labels}",
                "values": {"Female": "female", "Male": "male"}}
SHIFT_FIELD = {"name": "shift", "kind": "category", "person": False, "sensitive": False,
               "dimension": "shift", "wording": "on {labels}",
               "values": {"A": "shift A", "B": "shift B"}}
SCHOOL_FIELD = {"name": "adjacent_to_school", "kind": "flag",
                "dimension": "distance from a school", "yes_raw": "1", "no_raw": "0",
                "yes": "within 500 feet of a school", "no": "not within 500 feet of a school"}
WEAPON_FIELD = {"name": "weapon", "kind": "flag", "dimension": "weapon", "yes_raw": "1",
                "no_raw": "0", "yes": "with a weapon recorded", "no": "with no weapon recorded"}


def source_file(name, title, fields, address_part):
    return {
        "id": f"FIXTURE:{name}",
        "data_class": "COUNTY_OPEN_DATA",
        "fixture_note": NOTE + " data_class says COUNTY_OPEN_DATA only so that county mode "
                               "reads it.",
        "title": title,
        "publisher": "SYNTHETIC fixture publisher (made up for tests)",
        "address": f"https://fixture.invalid/resource/{address_part}.json",
        "page": f"https://fixture.invalid/d/{address_part}",
        "row_meaning": "one made-up arrest",
        "unit": {"one": "arrest record", "many": "arrest records"},
        "is_not": ["people", "charges", "cases", "convictions", "sentences", "a rate"],
        "time_field": "event_date_time",
        "coverage_start": "2021-01-01",
        "floor": 10,
        "fields": [{"name": "id", "kind": "key"}] + fields,
        "notices": [
            "SYNTHETIC fixture notice: these records are made up for tests and come from no "
            "county.",
            "SYNTHETIC fixture notice two: THE FIXTURE MAKES NO PROMISE ABOUT ANY OF THIS DATA."],
        "approved_by": "nobody (test fixture)",
        "approved_on": "2026-11-12",
        "approval_record": "none: a SYNTHETIC test fixture",
    }


STATS_LIKE = source_file(
    "stats_like", "SYNTHETIC fixture arrests for statistics (made up for tests)",
    [AGE_FIELD, GENDER_FIELD,
     {"name": "district", "kind": "category", "person": False, "sensitive": False,
      "dimension": "district", "wording": "in {labels}",
      "values": {str(d): f"district {d}" for d in range(1, 8)}},
     SHIFT_FIELD, SCHOOL_FIELD, WEAPON_FIELD],
    "stats-like")

BATCHES = ["P", "Q1", "Q2", "R099", "R100", "Y099", "Y100", "N099", "N100", "K100", "K109",
           "K110", "S099", "S100", "D29", "D30", "anchor"]
STATS_EDGES = source_file(
    "stats_edges", "SYNTHETIC fixture edge cases for statistics (made up for tests)",
    [AGE_FIELD, GENDER_FIELD,
     {"name": "zone", "kind": "category", "person": False, "sensitive": False,
      "dimension": "zone", "wording": "in {labels}",
      "values": {str(z): f"zone {z}" for z in range(1, 10)}},
     SHIFT_FIELD, SCHOOL_FIELD, WEAPON_FIELD,
     {"name": "batch", "kind": "category", "person": False, "sensitive": False,
      "dimension": "batch", "wording": "in {labels}",
      "values": {b: f"batch {b}" for b in BATCHES}}],
    "stats-edges")


# ---- time ---------------------------------------------------------------------------------

def months(first=FIRST, last=LAST):
    y, m = first
    while (y, m) <= last:
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def years_since_2021(y, m):
    """Time in years, as the tests read S3: (year - 2021) + (month - 1) / 12."""
    return (y - 2021) + (m - 1) / 12


# Month of year: the same pattern for every series (the models' eleven month indicators).
SEASON = [0.88, 0.86, 0.95, 1.00, 1.06, 1.12, 1.15, 1.12, 1.04, 1.00, 0.94, 0.88]

# Weekday by hour (timing). Monday first. Every cell is drawn from these weights except
# Tuesday at 4 am, which gets exactly 4 records by hand (the one cell from 1 to 9: the
# quietest, and the cell a heat map must draw empty). Friday at 11 pm is boosted to be the
# one busiest cell. Hours 0 and 12 are never the busiest or the quietest (C6 does not say
# how they are written).
HOUR_WEIGHT = [0.9, 0.8, 0.7, 0.65, 0.6, 0.6, 0.7, 0.85, 1.0, 1.1, 1.2, 1.2,
               1.2, 1.25, 1.3, 1.4, 1.5, 1.5, 1.45, 1.4, 1.3, 1.2, 1.1, 1.0]
WEEKDAY_WEIGHT = [0.95, 0.9, 0.95, 1.0, 1.15, 1.05, 1.0]
BUSIEST = (4, 23)   # Friday, 11 pm
QUIETEST = (1, 4)   # Tuesday, 4 am
QUIET_ROWS = [(2021, 3), (2022, 6), (2023, 9), (2024, 11)]  # the 4 records of that cell


def cell_weights():
    w = np.array([[WEEKDAY_WEIGHT[d] * HOUR_WEIGHT[h] for h in range(24)] for d in range(7)])
    w[BUSIEST] *= 2.4
    w[QUIETEST] = 0.0
    return (w / w.sum()).ravel()


def day_with_weekday(rng, y, m, weekday, last_day=None):
    days = [d for d in range(1, (last_day or calendar.monthrange(y, m)[1]) + 1)
            if date(y, m, d).weekday() == weekday]
    return int(rng.choice(days))


def stamp(y, m, d, h, minute):
    return f"{y:04d}-{m:02d}-{d:02d}T{h:02d}:{minute:02d}:00.000"


# ---- the main source: stats_like ------------------------------------------------------------
#
# Seven districts, each a monthly series built on purpose (expected count per month, times
# the month-of-year pattern, then a negative binomial draw with spread THETA so that the
# negative binomial can be fitted):
#
#   district 1  rises by a known 18% a year                     trend: clear rise
#   district 2  flat                                            trend: not clear; before_after
#                                                               at 1 July 2022: neither a step
#                                                               nor a bend
#   district 3  falls by a known 15% a year                     trend: clear fall
#   district 4  flat; March to August 2026 (the last six        fit line: below (the fitted
#               months of a window that ends in August 2026)    line takes up part of the
#               set by hand to 0.60 of expected                 change, so the ratio is nearer
#                                                               1 than 0.60; s3ssupport has it)
#   district 5  flat; March to August 2026 set to 1.60          fit line: above
#   district 6  flat to June 2023; from 1 July 2023 a step up   before_after at 1 July 2023:
#               (x 1.5) and a rise of 45% a year                step higher, bend higher
#   district 7  rising 35% a year to June 2023; from 1 July     before_after at 1 July 2023:
#               2023 a step down (x 0.55) and flat              step lower, bend lower
#
# All districts together rise clearly (trend, clear rise), and their last six months sit
# inside the fit band (no fit line).
#
# About one record a month has no district at all (left out of anything that uses district).
#
# Each record then gets, by chance:
#   shift A or B, in turn (see main_rows); weapon yes one in four (no link with time, so `weapon` yes
#   and no rise alike: trend_compare, no clear difference); gender female 30%, male 69%,
#   1% left out (empty or an unlisted value); an age (8% under 18; about 2% left out:
#   empty, 7, 120 or 25.5);
#   within 500 feet of a school with log-odds -2.0 + 0.13 a year + 1.2 weapon - 0.30 female
#   + 0.75 under 18 + a district effect, shift none. So:
#     trend_compare school yes against no: clearly different yearly change;
#     yes_no outcome school: weapon strongly above 1, female weakly below 1, shift B not
#     at all, district as the category control (under 18 above 1);
#     shares part school: a clear rise year by year; part not school: a clear fall;
#     part shift B: no change.
#   The school flag and shift are never empty: whether a record with no value for the
#   part's field counts against a share or is left out, S3 does not say, so no share case
#   depends on it. Left-out records come from district (no district), gender (empty or
#   unlisted) and age.
#
# Ages (distribution): overall and by gender, quartiles fall inside long runs of equal
# ages, so every usual quantile rule gives the same whole number (checked by s3ssupport).

THETA = 20.0
THETA_BY_DISTRICT = {}
DISTRICT_EFFECT = {"1": 0.0, "2": 0.3, "3": -0.2, "4": 0.1, "5": -0.3, "6": 0.2, "7": -0.1}


def district_expected(d, y, m):
    t = years_since_2021(y, m)
    if d == "1":
        mu = 28 * 1.18 ** t
    elif d == "2":
        mu = 14.0
    elif d == "3":
        mu = 26 * 0.85 ** t
    elif d == "4":
        mu = 12.0
    elif d == "5":
        mu = 10.0
    elif d == "6":
        mu = 14.0
        if (y, m) >= (2023, 7):
            mu *= 1.5 * 1.45 ** (t - 2.5)
    else:
        mu = 14 * 1.35 ** min(t, 2.5)
        if (y, m) >= (2023, 7):
            mu *= 0.55
    return mu * SEASON[m - 1]


FIT_MONTHS = [(2026, m) for m in range(3, 9)]  # the last six months of a window to Aug 2026
FIT_FACTOR = {"4": 0.60, "5": 1.60}


def monthly_counts(rng):
    out = {}
    for y, m in months():
        for d in DISTRICT_EFFECT:
            mu = district_expected(d, y, m)
            if (y, m) == LAST:
                mu *= 13 / 31  # October 2026: records up to the 13th (the anchor is the 14th)
            if (y, m) in FIT_MONTHS and d in FIT_FACTOR:
                out[(y, m, d)] = int(round(mu * FIT_FACTOR[d]))  # set by hand, no chance
            else:
                theta = THETA_BY_DISTRICT.get(d, THETA)
                out[(y, m, d)] = int(rng.poisson(rng.gamma(theta, mu / theta)))
        out[(y, m, None)] = int(rng.poisson(0.7 * (13 / 31 if (y, m) == LAST else 1)))
    return out


def draw_age(rng):
    """(the raw age text or None for a missing key, usable age or None)."""
    u = rng.random()
    if u < 0.006:
        return None, None
    if u < 0.011:
        return "7", None
    if u < 0.016:
        return "120", None
    if u < 0.020:
        return "25.5", None
    if rng.random() < 0.08:
        a = int(rng.integers(12, 18))
    else:
        a = min(85, 18 + int(rng.gamma(2.2, 7.5)))
    return str(a), a


def draw_gender(rng):
    u = rng.random()
    if u < 0.30:
        return "Female"
    if u < 0.99:
        return "Male"
    return None if u < 0.996 else "Unknown"


def main_rows(rng):
    counts = monthly_counts(rng)
    weights = cell_weights()
    rows, serial = [], 0

    def add(y, m, wd, h, d):
        nonlocal serial
        serial += 1
        last_day = 13 if (y, m) == LAST else None
        day = day_with_weekday(rng, y, m, wd, last_day)
        age_raw, age = draw_age(rng)
        gender = draw_gender(rng)
        weapon = int(rng.random() < 0.25)
        shift = "A" if rng.random() < 0.5 else "B"
        logit = (-2.0 + 0.13 * years_since_2021(y, m) + 1.2 * weapon
                 - 0.30 * (gender == "Female") + 0.75 * (age is not None and age < 18)
                 + DISTRICT_EFFECT.get(d, 0.0))
        school = int(rng.random() < 1 / (1 + np.exp(-logit)))
        row = {"id": f"FIXTURE-S-{serial:05d}",
               "event_date_time": stamp(y, m, day, h, int(rng.integers(0, 60))),
               "age": age_raw, "gender": gender, "district": d, "shift": shift,
               "adjacent_to_school": str(school),
               "weapon": str(weapon), "data_class": "SYNTHETIC"}
        rows.append({k: v for k, v in row.items() if v is not None})

    for (y, m, d), n in counts.items():
        cells = rng.choice(len(weights), size=n, p=weights)
        for c in cells:
            add(y, m, int(c) // 24, int(c) % 24, d)
    for y, m in QUIET_ROWS:  # Tuesday at 4 am: exactly 4 records, district 2
        add(y, m, QUIETEST[0], QUIETEST[1], "2")
    # shift: A and B in turn within each (year, district, school flag) group, so that shift
    # has no link at all with the school flag (yes_no: "a third not at all"), the district or
    # the year (shares: part shift B does not move). Drawn by chance it came out "clear" at
    # p = 0.04 with this seed.
    turn = {}
    for row in rows:
        key = (row["event_date_time"][:4], row.get("district"), row["adjacent_to_school"])
        turn[key] = turn.get(key, 0) + 1
        row["shift"] = "AB"[turn[key] % 2]
    rows.append({"id": "FIXTURE-S-ANCHOR", "event_date_time": NEWEST_TIME, "age": "30",
                 "gender": "Male", "district": "2", "shift": "A", "adjacent_to_school": "0",
                 "weapon": "0", "data_class": "SYNTHETIC"})
    return rows


# ---- the edges source: stats_edges ----------------------------------------------------------
#
# One batch per case; a test picks one with the filter {"field": "batch", "is": "batch X"}.
# Every record of a batch is placeable in every field unless said otherwise, and falls in
# 2021 to 2025 unless said otherwise, so the dropped newest month never touches it.
#
#   P      the Poisson fallback: monthly counts set exactly to round(30 x 1.06^t x season),
#          Jan 2021 to Dec 2025: no spread beyond Poisson, so the negative binomial's spread
#          cannot be estimated above zero (R's glm.nb does not converge: checked by
#          kit-log/raw/S3S-A-r-crosscheck.R)
#   Q1     a monthly series with months from 1 to 9 that is fine by quarter (every quarter
#          10 or more), Jan 2021 to Dec 2025: drawn by quarter, answered
#   Q2     still hidden by quarter: 11 of 20 quarters hold 3 records (1 a month) and 9 hold
#          30 (10 a month), Jan 2021 to Dec 2025: 303 records, 60 months, TOO_FINE however
#          S1 and S6 are read together (more than half of the quarters are hidden)
#   R099   T, under 100 records in all: 99 records over the 24 months of 2024 and 2025,
#   R100   and 100: 4 or 5 a month, every quarter 12 or 13 (fine by quarter)
#   Y099   L, yes cases: 99 within 500 feet of a school and 400 not; and 100 and 400
#   Y100
#   N099   L, no cases: 400 yes and 99 no; and 400 and 100
#   N100
#   K100   L, rarer outcome per coefficient: 100 yes and 400 no, with weapon, shift and
#   K109   gender varying and every zone (9 labels) holding both outcomes. With the factors
#   K110   weapon and shift B and the control zone there are 10 coefficients besides the
#          intercept (11 with it); adding the factor female makes 11 (12). So:
#            K100, 2 factors: 10.0 a coefficient without the intercept, 9.09 with it
#            K100, 3 factors: 9.09 without, 8.33 with (refused either way)
#            K109, 2 factors: 10.9 without, 9.91 with
#            K110, 2 factors: 11.0 without, 10.0 with (answered either way)
#          (which of the two counts S1 means is asked in briefs/QUESTIONS.md)
#   S099   S, a base year under 100: 150, 150, 99, 150 and 150 records in 2021 to 2025,
#   S100   and 150, 150, 100, 150, 150; one in five within 500 feet of a school each year
#   D29    distribution by gender: 29 women with a usable age (and 3 more without one) and
#   D30    100 men; and 30 women
#   anchor the one record of 14 October 2026, the newest of the copy

WOMEN_AGES = [22, 27, 27, 31, 31, 31, 36, 36, 44, 52]
MEN_AGES = [24, 29, 29, 33, 33, 33, 38, 38, 46, 55]


def quarter_spread(total):
    """A quarter's records over its three months: 12 -> 4, 4, 4; 13 -> 4, 4, 5."""
    base = total // 3
    return [base, base, total - 2 * base]


def edge_rows(rng):
    rows, serial = [], 0

    def add(batch, y, m, *, gender="Male", age="30", zone="1", school="0", weapon="0",
            shift="A", day=None, hour=None):
        nonlocal serial
        serial += 1
        day = day or int(rng.integers(1, calendar.monthrange(y, m)[1] + 1))
        hour = hour if hour is not None else int(rng.integers(8, 21))
        row = {"id": f"FIXTURE-E-{batch}-{serial:05d}",
               "event_date_time": stamp(y, m, day, hour, int(rng.integers(0, 60))),
               "age": age, "gender": gender, "zone": zone, "shift": shift,
               "adjacent_to_school": school, "weapon": weapon, "batch": batch,
               "data_class": "SYNTHETIC"}
        rows.append({k: v for k, v in row.items() if v is not None})

    five_years = list(months((2021, 1), (2025, 12)))

    # P: exactly Poisson-like counts, no spread at all beyond the expected values.
    for y, m in five_years:
        n = int(round(30 * 1.06 ** years_since_2021(y, m) * SEASON[m - 1]))
        for _ in range(n):
            add("P", y, m)

    # Q1: fine by quarter.
    q1_pattern = [(8, 13, 12), (11, 9, 14), (12, 12, 7), (13, 10, 11), (9, 11, 13)]
    for q in range(20):
        for k, n in enumerate(q1_pattern[q % 5]):
            y, m = five_years[3 * q + k]
            for _ in range(n):
                add("Q1", y, m)

    # Q2: 11 hidden quarters (1 a month), then 9 of 10 a month.
    for q in range(20):
        for k in range(3):
            y, m = five_years[3 * q + k]
            for _ in range(1 if q < 11 else 10):
                add("Q2", y, m)

    # R099, R100: 24 months of 2024 and 2025.
    two_years = list(months((2024, 1), (2025, 12)))
    for batch, quarters in (("R099", [12, 13, 12, 13, 12, 13, 12, 12]),
                            ("R100", [12, 13, 12, 13, 12, 13, 12, 13])):
        for q, total in enumerate(quarters):
            for k, n in enumerate(quarter_spread(total)):
                y, m = two_years[3 * q + k]
                for _ in range(n):
                    add(batch, y, m)

    def spread_years(n):
        """n records over 2021 to 2025, month by month in turn."""
        return [five_years[(7 * i) % 60] for i in range(n)]

    # Y and N: yes and no cases of the school flag; shift varies with no link.
    for batch, yes, no in (("Y099", 99, 400), ("Y100", 100, 400), ("N099", 400, 99),
                           ("N100", 400, 100)):
        for i, (y, m) in enumerate(spread_years(yes + no)):
            add(batch, y, m, school="1" if i < yes else "0", shift="AB"[i % 2])

    # K: per coefficient. Both outcomes in every zone; weapon, shift and gender vary.
    for batch, yes in (("K100", 100), ("K109", 109), ("K110", 110)):
        for i, (y, m) in enumerate(spread_years(yes + 400)):
            j = i if i < yes else i - yes
            add(batch, y, m, school="1" if i < yes else "0",
                zone=str(j % 9 + 1) if j % 10 else "1",  # zone 1 the most common, alone
                weapon="1" if (j * 7) % 3 == 0 else "0", shift="AB"[(j // 2) % 2],
                gender="Female" if (j * 5) % 4 == 1 else "Male")

    # S: the base by year; one in five within 500 feet of a school.
    for batch, per_year in (("S099", [150, 150, 99, 150, 150]),
                            ("S100", [150, 150, 100, 150, 150])):
        for y, n in zip(range(2021, 2026), per_year):
            for i in range(n):
                add(batch, y, i % 12 + 1, school="1" if i % 5 == 0 else "0")

    # D: ages by gender; 3 women without a usable age in each. Ages repeat, so that the
    # median and quartiles of the groups with 30 or more fall inside runs of equal ages.
    for batch, women in (("D29", 29), ("D30", 30)):
        for i in range(women):
            add(batch, 2023, i % 12 + 1, gender="Female", age=str(WOMEN_AGES[i % 10]))
        for i, raw in enumerate(["", "120", "abc"]):
            add(batch, 2023, i + 1, gender="Female", age=raw or None)
        for i in range(100):
            add(batch, 2024, i % 12 + 1, gender="Male", age=str(MEN_AGES[i % 10]))

    rows.append({"id": "FIXTURE-E-ANCHOR", "event_date_time": NEWEST_TIME, "age": "30",
                 "gender": "Male", "zone": "1", "shift": "A", "adjacent_to_school": "0",
                 "weapon": "0", "batch": "anchor", "data_class": "SYNTHETIC"})
    return rows


# ---- the checks (plain counting) ----------------------------------------------------------

def month_of(row):
    return int(row["event_date_time"][:4]), int(row["event_date_time"][5:7])


def check_main(rows):
    times = [r["event_date_time"] for r in rows]
    assert max(times) == NEWEST_TIME and times.count(NEWEST_TIME) == 1, "the anchor is newest"
    assert len({r["id"] for r in rows}) == len(rows)
    assert 8500 <= len(rows) <= 10500, len(rows)
    # timing: the cell counts of 2021 to 2025
    cells = {}
    for r in rows:
        y = int(r["event_date_time"][:4])
        if 2021 <= y <= 2025:
            d = date.fromisoformat(r["event_date_time"][:10]).weekday()
            h = int(r["event_date_time"][11:13])
            cells[(d, h)] = cells.get((d, h), 0) + 1
    values = sorted(cells.values())
    assert len(cells) == 168, "every weekday-hour cell has a record"
    assert cells[QUIETEST] == 4 and values[0] == 4 and values[1] >= 10, values[:3]
    assert cells[BUSIEST] == values[-1] > values[-2], values[-3:]
    # the fit months of districts 4 and 5 are set by hand
    for d, factor in FIT_FACTOR.items():
        for y, m in FIT_MONTHS:
            n = sum(1 for r in rows if r.get("district") == d and month_of(r) == (y, m))
            assert n == int(round(district_expected(d, y, m) * factor)), (d, y, m, n)


def check_edges(rows):
    def batch(b):
        return [r for r in rows if r["batch"] == b]

    def by_month(b):
        out = {}
        for r in batch(b):
            out[month_of(r)] = out.get(month_of(r), 0) + 1
        return out

    def by_quarter(b):
        out = {}
        for (y, m), n in by_month(b).items():
            out[(y, (m - 1) // 3)] = out.get((y, (m - 1) // 3), 0) + n
        return out

    q1m, q1q = by_month("Q1"), by_quarter("Q1")
    assert len(q1m) == 60 and any(1 <= n <= 9 for n in q1m.values()) and min(q1q.values()) >= 10
    q2q = by_quarter("Q2")
    assert len(q2q) == 20 and sum(1 <= n <= 9 for n in q2q.values()) == 11
    assert len(batch("Q2")) == 303
    for b, n in (("R099", 99), ("R100", 100)):
        assert len(batch(b)) == n and len(by_month(b)) == 24 and min(by_quarter(b).values()) >= 10
        assert all(2024 <= y <= 2025 for y, _ in by_month(b))
    for b, yes, no in (("Y099", 99, 400), ("Y100", 100, 400), ("N099", 400, 99),
                       ("N100", 400, 100), ("K100", 100, 400), ("K109", 109, 400),
                       ("K110", 110, 400)):
        got = [r["adjacent_to_school"] for r in batch(b)]
        assert (got.count("1"), got.count("0")) == (yes, no), b
    for b in ("K100", "K109", "K110"):
        for z in map(str, range(1, 10)):
            outcomes = {r["adjacent_to_school"] for r in batch(b) if r["zone"] == z}
            assert outcomes == {"0", "1"}, (b, z)
        for f in ("weapon", "shift", "gender"):
            for o in "01":
                assert len({r[f] for r in batch(b) if r["adjacent_to_school"] == o}) == 2, (b, f)
    for b, per_year in (("S099", [150, 150, 99, 150, 150]), ("S100", [150, 150, 100, 150, 150])):
        got = [sum(1 for r in batch(b) if month_of(r)[0] == y) for y in range(2021, 2026)]
        assert got == per_year, (b, got)
    for b, women in (("D29", 29), ("D30", 30)):
        usable = [r for r in batch(b) if r["gender"] == "Female" and r.get("age", "").isdigit()
                  and 10 <= int(r["age"]) <= 98]
        assert len(usable) == women, b
    times = [r["event_date_time"] for r in rows]
    assert max(times) == NEWEST_TIME and times.count(NEWEST_TIME) == 1


def write(name, source, rows):
    (HERE / "sources").mkdir(exist_ok=True)
    (HERE / "rows").mkdir(exist_ok=True)
    (HERE / "sources" / f"{name}.json").write_text(json.dumps(source, indent=2) + "\n",
                                                   encoding="utf-8")
    body = ",\n".join(json.dumps(r, sort_keys=False) for r in rows)
    (HERE / "rows" / f"{name}.json").write_text(
        '{"note": ' + json.dumps(NOTE) + ', "rows": [\n' + body + "\n]}\n", encoding="utf-8")


def main():
    rng = np.random.default_rng(SEED)
    stats = main_rows(rng)
    check_main(stats)
    edges = edge_rows(np.random.default_rng(SEED + 1))
    check_edges(edges)
    write("stats_like", STATS_LIKE, stats)
    write("stats_edges", STATS_EDGES, edges)
    print(f"stats_like: {len(stats)} rows; stats_edges: {len(edges)} rows")


if __name__ == "__main__":
    main()
