"""Make the SYNTHETIC fixtures for the Part S2 tests (rates per resident, docs/S3S2-DESIGN.md;
brief S3S2-A step 3).

Everything here is made up for tests. No figure is a real Census figure and no row is a real
record. The Census tables have the Census's own shape and the Census's own label texts (the
words config/census.json checks), filled with round made-up numbers; every file says
SYNTHETIC at its top.

    .venv/bin/python tests/s3s2/fixtures/make_fixtures.py

writes, next to this script:

    census/<year>/B01001.json          for 2021 to 2025: the Census service's answer to
    census/<year>/B03002.json          `get=group(<table>)` for one county, as a first line
                                       of variable names and one line of values (estimates
                                       end `E`, margins `M`, their notes `EA`/`MA`), under
                                       "answer", with a SYNTHETIC "note" above it. The total
                                       of each table (B01001_001, B03002_001) has the
                                       Census's "no margin" code, -555555555 (note *****).
    census/<year>/B01001_labels.json   the service's list of variable labels for the table
    census/<year>/B03002_labels.json   (its groups/<table>.json answer), under "variables"
    census.json                        a census config for the tests in the shape R8 of the
                                       contract describes, worked out HERE from the tables'
                                       own line labels (not copied from config/census.json):
                                       for every group the variables added up and words each
                                       label must hold
    sources/rates_like.json            a small source file in the shape of C3 with race and
                                       ethnicity (the Part S source has neither), marked
                                       "rates": true
    rows/rates_like.json               its rows: round counts per group and year, chosen so
                                       that every rate of the race_ethnicity breakdown is a
                                       round number (see RECORDS and RESIDENTS_RE below)

The gender, age_band and "none" breakdowns use Part S's main fixture source
(tests/s3s/fixtures, stats_like) through a change that marks it "rates": true; its rows are
not changed. Its counts are not round, so its rates are not either: the truth helper
(tests/s3s2/s2support.py) works them out.

THE MADE-UP CENSUS FIGURES (all residents, Montgomery County as the tests pretend it is):

B01001, sex by age. 23 age lines per sex. For 2025 (k = 0) each male line is MALE[i] x 1,000
and each female line FEMALE[i] x 1,000; for an earlier year k = 2025 - year and every line is
200 x k lower. Margins: MALE_MOE[i] x 100 (FEMALE_MOE[i] x 100) plus 100 x k. The male and
female totals are the sums of their lines; their margins are 12,000 and 13,000 plus 1,000 x k.
The total is male plus female and has no margin (-555555555), as the Census writes a total
it fixes to its own population estimates.

  So for 2025: 10 to 17 (both sexes) = 35,000 + 34,000 + 21,000 + 20,000 = 110,000 and its
  margin = sqrt(1,600^2 + 1,200^2 + 900^2 + 1,200^2) = sqrt(6,250,000) = 2,500.

B03002, Hispanic or Latino origin by race. For 2025 (k = 0): Not Hispanic: White alone
400,000 (margin 2,400), Black alone 180,000 (3,600), Asian alone 150,000 (3,000), American
Indian alone 2,000, Pacific Islander alone 1,000, some other race 6,000, two or more races
the rest (10,000 + the rest); Hispanic or Latino 200,000 (4,000), split over its race lines.
For an earlier year: Hispanic 4,000 x k lower, Black 2,000 x k lower, White 3,000 x k
higher, Asian 1,000 x k lower; each of those four margins 100 x k higher. The total equals
B01001's total and has no margin.

THE RECORDS of rates_like (per calendar year; the residents in brackets give the rate):

  2025: Hispanic 600 (200,000: 30.0), Black 900 (180,000: 50.0), White 400 (400,000:
        10.0), Asian 150 (150,000: 10.0)
  2024: Hispanic 490 (196,000: 25.0), Black 712 (178,000: 40.0), White 806 (403,000:
        20.0), Asian 298 (149,000: 20.0)
  2023: Hispanic 576 (192,000: 30.0), Black 704 (176,000: 40.0), White 609 (406,000:
        15.0), Asian 148 (148,000: 10.0)
  2022: Hispanic 470, Black 870, White 409, Asian 60 (between 10 and 99: TOO_LITTLE)
  2021: Hispanic 552, Black 688, White 412, Asian 7 (under 10: never shown)
  2026 (to 14 October, an unfinished year): Hispanic 50, Black 60, White 40, Asian 20

Every year 2021 to 2025 also has 30 records that belong to no group (left out, R3):
American Indian and not Hispanic 5, Pacific Islander and not Hispanic 3 (the two groups
"with fewer than 10 records a year"), race unknown and not Hispanic 12, Black with no
ethnicity recorded 6, neither recorded 4. "Hispanic (any race)" is ethnicity Hispanic with
any race, recorded or not: 45 in 100 White, 30 race unknown, 10 Black, 10 no race, the rest
Asian.

The seed is fixed: running the script again leaves the files unchanged. It checks every
counting fact above by plain counting and stops if one does not hold.
"""
import json
import random
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEED = 375
YEARS = (2021, 2022, 2023, 2024, 2025)
NOTE = ("SYNTHETIC: made up for the Part S2 tests by tests/s3s2/fixtures/make_fixtures.py. "
        "Not Census data and not county data: every figure is invented.")
NO_MARGIN = "-555555555"
NO_MARGIN_NOTE = "*****"
GEO = {"state": "24", "county": "031", "name": "Montgomery County, Maryland",
       "geo_id": "0500000US24031"}

# ---- B01001 -----------------------------------------------------------------------------------

AGE_LINES = [  # (label, first age, last age or None)
    ("Under 5 years", 0, 4), ("5 to 9 years", 5, 9), ("10 to 14 years", 10, 14),
    ("15 to 17 years", 15, 17), ("18 and 19 years", 18, 19), ("20 years", 20, 20),
    ("21 years", 21, 21), ("22 to 24 years", 22, 24), ("25 to 29 years", 25, 29),
    ("30 to 34 years", 30, 34), ("35 to 39 years", 35, 39), ("40 to 44 years", 40, 44),
    ("45 to 49 years", 45, 49), ("50 to 54 years", 50, 54), ("55 to 59 years", 55, 59),
    ("60 and 61 years", 60, 61), ("62 to 64 years", 62, 64), ("65 and 66 years", 65, 66),
    ("67 to 69 years", 67, 69), ("70 to 74 years", 70, 74), ("75 to 79 years", 75, 79),
    ("80 to 84 years", 80, 84), ("85 years and over", 85, None)]
MALE = [32, 34, 35, 21, 12, 6, 6, 17, 33, 35, 37, 37, 36, 36, 34, 13, 18, 11, 15, 20, 13, 8, 7]
FEMALE = [31, 33, 34, 20, 11, 6, 6, 16, 34, 36, 39, 39, 38, 38, 36, 14, 19, 12, 17, 23, 16, 11,
          12]
MALE_MOE = [4, 18, 16, 9, 9, 8, 8, 11, 15, 16, 15, 15, 13, 13, 13, 9, 10, 8, 9, 10, 8, 6, 6]
FEMALE_MOE = [4, 17, 12, 12, 8, 8, 8, 11, 15, 16, 15, 15, 13, 13, 13, 9, 10, 8, 9, 10, 8, 7, 7]

# The age bands of R4 (D-056), as the contract writes them.
AGE_BANDS = [("10 to 17", 10, 17), ("18 to 24", 18, 24), ("25 to 34", 25, 34),
             ("35 to 44", 35, 44), ("45 to 54", 45, 54), ("55 to 64", 55, 64),
             ("65 and over", 65, None)]


def b01001_lines():
    """[(variable without E/M, label after `Estimate!!`, sex or None, (first, last) or None)]
    in the table's own order: total, male, 23 male lines, female, 23 female lines."""
    out = [("B01001_001", "Total:", None, None), ("B01001_002", "Total:!!Male:", "Male", None)]
    n = 3
    for sex in ("Male", "Female"):
        if sex == "Female":
            out.append((f"B01001_{n:03d}", "Total:!!Female:", "Female", None))
            n += 1
        for label, lo, hi in AGE_LINES:
            out.append((f"B01001_{n:03d}", f"Total:!!{sex}:!!{label}", sex, (lo, hi)))
            n += 1
    assert n == 50, n
    return out


def b01001_values(year, bump=0):
    """{variable: (estimate, margin or None)} for one year. `bump` is added to every age line
    (a second, changed answer for the tests of a refused year)."""
    k = 2025 - year
    values = {}
    totals = {}
    for var, label, sex, ages in b01001_lines():
        if ages is None:
            continue
        i = [a[0] for a in AGE_LINES].index(label.rsplit("!!", 1)[1])
        base, moe = (MALE[i], MALE_MOE[i]) if sex == "Male" else (FEMALE[i], FEMALE_MOE[i])
        est = base * 1000 - 200 * k + bump
        values[var] = (est, moe * 100 + 100 * k)
        totals[sex] = totals.get(sex, 0) + est
    values["B01001_002"] = (totals["Male"], 12000 + 1000 * k)
    values["B01001_026"] = (totals["Female"], 13000 + 1000 * k)
    values["B01001_001"] = (totals["Male"] + totals["Female"], None)
    return values


# ---- B03002 -----------------------------------------------------------------------------------

B03002_LABELS = [
    ("B03002_001", "Total:"),
    ("B03002_002", "Total:!!Not Hispanic or Latino:"),
    ("B03002_003", "Total:!!Not Hispanic or Latino:!!White alone"),
    ("B03002_004", "Total:!!Not Hispanic or Latino:!!Black or African American alone"),
    ("B03002_005", "Total:!!Not Hispanic or Latino:!!American Indian and Alaska Native alone"),
    ("B03002_006", "Total:!!Not Hispanic or Latino:!!Asian alone"),
    ("B03002_007", "Total:!!Not Hispanic or Latino:!!Native Hawaiian and Other Pacific "
                   "Islander alone"),
    ("B03002_008", "Total:!!Not Hispanic or Latino:!!Some other race alone"),
    ("B03002_009", "Total:!!Not Hispanic or Latino:!!Two or more races:"),
    ("B03002_010", "Total:!!Not Hispanic or Latino:!!Two or more races:!!Two races including "
                   "Some other race"),
    ("B03002_011", "Total:!!Not Hispanic or Latino:!!Two or more races:!!Two races excluding "
                   "Some other race, and three or more races"),
    ("B03002_012", "Total:!!Hispanic or Latino:"),
    ("B03002_013", "Total:!!Hispanic or Latino:!!White alone"),
    ("B03002_014", "Total:!!Hispanic or Latino:!!Black or African American alone"),
    ("B03002_015", "Total:!!Hispanic or Latino:!!American Indian and Alaska Native alone"),
    ("B03002_016", "Total:!!Hispanic or Latino:!!Asian alone"),
    ("B03002_017", "Total:!!Hispanic or Latino:!!Native Hawaiian and Other Pacific Islander "
                   "alone"),
    ("B03002_018", "Total:!!Hispanic or Latino:!!Some other race alone"),
    ("B03002_019", "Total:!!Hispanic or Latino:!!Two or more races:"),
    ("B03002_020", "Total:!!Hispanic or Latino:!!Two or more races:!!Two races including Some "
                   "other race"),
    ("B03002_021", "Total:!!Hispanic or Latino:!!Two or more races:!!Two races excluding Some "
                   "other race, and three or more races"),
]

# 2025's figures of the four groups of R3, and how each moves for an earlier year (k years).
RESIDENTS_RE = {  # group: (variable, 2025 estimate, change per year back, 2025 margin)
    "Hispanic (any race)": ("B03002_012", 200000, -4000, 4000),
    "Black, not Hispanic": ("B03002_004", 180000, -2000, 3600),
    "White, not Hispanic": ("B03002_003", 400000, 3000, 2400),
    "Asian, not Hispanic": ("B03002_006", 150000, -1000, 3000),
}


def b03002_values(year, bump=0):
    k = 2025 - year
    total = b01001_values(year, bump)["B01001_001"][0]
    v = {}
    for var, est, step, moe in RESIDENTS_RE.values():
        v[var] = (est + step * k, moe + 100 * k)
    v["B03002_005"] = (2000, 500)
    v["B03002_007"] = (1000, 400)
    v["B03002_008"] = (6000, 1000)
    hispanic = v["B03002_012"][0]
    v["B03002_013"] = (50000 - 1000 * k, 2000)
    v["B03002_014"] = (6000, 900)
    v["B03002_015"] = (2000, 600)
    v["B03002_016"] = (1000, 400)
    v["B03002_017"] = (500, 300)
    v["B03002_018"] = (80000 - 2000 * k, 3000)
    v["B03002_020"] = (40000, 2500)
    rest_h = hispanic - sum(v[f"B03002_{n:03d}"][0] for n in (13, 14, 15, 16, 17, 18))
    v["B03002_019"] = (rest_h, 2800)
    v["B03002_021"] = (rest_h - 40000, 2000)
    not_h = total - hispanic
    known = sum(v[f"B03002_{n:03d}"][0] for n in (3, 4, 5, 6, 7, 8))
    v["B03002_009"] = (not_h - known, 3500)
    v["B03002_010"] = (10000, 1200)
    v["B03002_011"] = (not_h - known - 10000, 3300)
    v["B03002_002"] = (not_h, 2000)
    v["B03002_001"] = (total, None)
    assert all(e > 0 for e, _ in v.values()), v
    return v


# ---- the Census service's shapes ----------------------------------------------------------------

TABLES = {"B01001": "Sex by Age", "B03002": "Hispanic or Latino Origin by Race"}


def table_lines(table):
    if table == "B01001":
        return [(var, label) for var, label, _, _ in b01001_lines()]
    return list(B03002_LABELS)


def table_values(table, year, bump=0):
    return b01001_values(year, bump) if table == "B01001" else b03002_values(year, bump)


def group_answer(table, year, bump=0):
    """The service's answer to `get=group(<table>)&for=county:031&in=state:24`: a first line
    of names, one line of values, every value a string (as the service writes them)."""
    values = table_values(table, year, bump)
    names, row = [], []
    for var, _ in table_lines(table):
        est, moe = values[var]
        names += [f"{var}E", f"{var}EA", f"{var}M", f"{var}MA"]
        row += [str(est), None, NO_MARGIN if moe is None else str(moe),
                NO_MARGIN_NOTE if moe is None else None]
    names += ["GEO_ID", "NAME", "state", "county"]
    row += [GEO["geo_id"], GEO["name"], GEO["state"], GEO["county"]]
    return [names, row]


def labels_answer(table, year):
    """The service's groups/<table>.json: {"variables": {name: {"label", "concept", ...}}}."""
    out = {}
    concept = TABLES[table]
    for var, label in table_lines(table):
        for suffix, head, kind in (("E", "Estimate!!", "int"), ("M", "Margin of Error!!", "int"),
                                   ("EA", "Annotation of Estimate!!", "string"),
                                   ("MA", "Annotation of Margin of Error!!", "string")):
            entry = {"label": head + label, "concept": concept, "predicateType": kind,
                     "group": table, "limit": 0, "predicateOnly": True}
            if suffix == "E":
                entry["attributes"] = f"{var}M,{var}MA,{var}EA"
            out[var + suffix] = entry
    out["GEO_ID"] = {"label": "Geography", "concept": concept, "predicateType": "string",
                     "group": table, "limit": 0, "predicateOnly": True}
    out["NAME"] = {"label": "Geographic Area Name", "concept": concept,
                   "predicateType": "string", "group": table, "limit": 0,
                   "predicateOnly": True}
    return {"variables": out}


# ---- the census config for the tests (R8's shape), worked out from the labels ---------------

def census_config():
    """For every group of R3 and R4, the variables added up, each with words its label must
    hold, found HERE from the label texts above (not copied from config/census.json)."""
    lines = b01001_lines()
    by = {"none": {"all residents": [_var("B01001_001", ["Total"])]},
          "gender": {"female": [_var("B01001_026", ["Female"])],
                     "male": [_var("B01001_002", ["Male"])]},
          "age_band": {}, "race_ethnicity": {}}
    for band, blo, bhi in AGE_BANDS:
        chosen = []
        for sex in ("Male", "Female"):
            for var, label, s, ages in lines:
                if s == sex and ages is not None:
                    lo, hi = ages
                    inside = lo >= blo and (bhi is None or (hi is not None and hi <= bhi))
                    if inside:
                        chosen.append((var, [sex, label.rsplit("!!", 1)[1]]))
        # the table's order: male lines then female lines, both ascending
        by["age_band"][band] = [_var(v, words) for v, words in chosen]
    words = {"Hispanic (any race)": ["Hispanic or Latino"],
             "Black, not Hispanic": ["Not Hispanic or Latino", "Black or African American alone"],
             "White, not Hispanic": ["Not Hispanic or Latino", "White alone"],
             "Asian, not Hispanic": ["Not Hispanic or Latino", "Asian alone"]}
    for group, (var, _, _, _) in RESIDENTS_RE.items():
        by["race_ethnicity"][group] = [_var(var, words[group])]
    records = {
        "race_ethnicity": {"Hispanic (any race)": {"ethnicity": "Hispanic"},
                           "Black, not Hispanic": {"ethnicity": "not Hispanic",
                                                   "race": "Black or African American"},
                           "White, not Hispanic": {"ethnicity": "not Hispanic", "race": "White"},
                           "Asian, not Hispanic": {"ethnicity": "not Hispanic", "race": "Asian"}},
        "gender": {"female": {"gender": "female"}, "male": {"gender": "male"}},
        "age_band": {band: [lo, hi] for band, lo, hi in AGE_BANDS}}
    return {"note": NOTE + " The groups were worked out by make_fixtures.py from the Census "
                           "line labels, in the shape R8 of docs/S3S2-DESIGN.md describes.",
            "survey": "acs/acs1", "first_year": 2021,
            "place": {"state": GEO["state"], "county": GEO["county"], "name": GEO["name"]},
            "tables": dict(TABLES), "margin_level": 0.9, "margin_z": 1.645,
            "no_margin_codes": [NO_MARGIN, NO_MARGIN_NOTE], "breakdowns": by,
            "records": records}


def _var(variable, label_has):
    return {"variable": variable, "label_has": label_has}


# ---- the source with race and ethnicity ------------------------------------------------------

RACE = {"Black/African American": "Black or African American", "White": "White",
        "Asian": "Asian", "American Indian/ALSK Natv": "American Indian or Alaska Native",
        "Hawaiian/Pacific Islander": "Native Hawaiian or Pacific Islander",
        "Unknown": "race unknown"}
ETHNICITY = {"HISPANIC": "Hispanic", "NON-HISPANIC": "not Hispanic"}
DISTRICTS = {"1": "district 1", "2": "district 2", "3": "district 3", "4": "district 4",
             "5": "district 5", "6": "district 6", "8": "district 8"}

SOURCE = {
    "id": "FIXTURE:rates_like",
    "data_class": "COUNTY_OPEN_DATA",
    "fixture_note": NOTE + " data_class says COUNTY_OPEN_DATA only so that county mode reads "
                           "it.",
    "title": "SYNTHETIC fixture arrests for rates (made up for tests)",
    "publisher": "SYNTHETIC fixture publisher (made up for tests)",
    "address": "https://fixture.invalid/resource/rates-like.json",
    "page": "https://fixture.invalid/d/rates-like",
    "row_meaning": "one made-up arrest",
    "unit": {"one": "arrest record", "many": "arrest records"},
    "is_not": ["people", "charges", "cases", "convictions", "sentences", "a rate"],
    "time_field": "event_date_time",
    "coverage_start": "2021-01-01",
    "floor": 10,
    "rates": True,
    "fields": [
        {"name": "id", "kind": "key"},
        {"name": "age", "kind": "age", "usable": [10, 98],
         "bands": [[10, 17], [18, 24], [25, 34], [35, 44], [45, 54], [55, 98]],
         "sensitive": False},
        {"name": "gender", "kind": "category", "person": True, "sensitive": True,
         "dimension": "gender", "wording": "recorded as {labels}",
         "values": {"Female": "female", "Male": "male"}},
        {"name": "race", "kind": "category", "person": True, "sensitive": True,
         "dimension": "race", "wording": "recorded as {labels}", "values": RACE},
        {"name": "ethnicity", "kind": "category", "person": True, "sensitive": True,
         "dimension": "ethnicity", "wording": "recorded as {labels}", "values": ETHNICITY},
        {"name": "district", "kind": "category", "person": False, "sensitive": False,
         "dimension": "district", "wording": "in {labels}", "values": DISTRICTS},
        {"name": "adjacent_to_school", "kind": "flag", "dimension": "distance from a school",
         "yes_raw": "1", "no_raw": "0", "yes": "within 500 feet of a school",
         "no": "not within 500 feet of a school"},
    ],
    "notices": ["SYNTHETIC fixture notice: these records are made up for tests and come from "
                "no county."],
    "approved_by": "nobody (test fixture)",
    "approved_on": "2026-11-13",
    "approval_record": "none: a SYNTHETIC test fixture",
}

# Records per group and year (R3's four groups); see the module text.
RECORDS = {
    2021: {"Hispanic (any race)": 552, "Black, not Hispanic": 688, "White, not Hispanic": 412,
           "Asian, not Hispanic": 7},
    2022: {"Hispanic (any race)": 470, "Black, not Hispanic": 870, "White, not Hispanic": 409,
           "Asian, not Hispanic": 60},
    2023: {"Hispanic (any race)": 576, "Black, not Hispanic": 704, "White, not Hispanic": 609,
           "Asian, not Hispanic": 148},
    2024: {"Hispanic (any race)": 490, "Black, not Hispanic": 712, "White, not Hispanic": 806,
           "Asian, not Hispanic": 298},
    2025: {"Hispanic (any race)": 600, "Black, not Hispanic": 900, "White, not Hispanic": 400,
           "Asian, not Hispanic": 150},
    2026: {"Hispanic (any race)": 50, "Black, not Hispanic": 60, "White, not Hispanic": 40,
           "Asian, not Hispanic": 20},
}
# Records of no group, each year 2021 to 2025 (2026: one of each of the first five):
# (race raw or None, ethnicity raw or None, how many)
LEFT_OUT = [("American Indian/ALSK Natv", "NON-HISPANIC", 5),
            ("Hawaiian/Pacific Islander", "NON-HISPANIC", 3),
            ("Unknown", "NON-HISPANIC", 12),
            ("Black/African American", None, 6),
            (None, None, 4)]
# How the Hispanic records of a year are split by recorded race (raw; None: no race).
HISPANIC_RACES = [("White", 45), ("Unknown", 30), ("Black/African American", 10), (None, 10),
                  ("Asian", 5)]
GROUP_RAW = {"Black, not Hispanic": ("Black/African American", "NON-HISPANIC"),
             "White, not Hispanic": ("White", "NON-HISPANIC"),
             "Asian, not Hispanic": ("Asian", "NON-HISPANIC")}
NEWEST = date(2026, 10, 14)
NEWEST_TIME = "2026-10-14T13:05:00.000"


def _hispanic_split(n):
    parts = [n * share // 100 for _, share in HISPANIC_RACES]
    parts[0] += n - sum(parts)
    return [(race, k) for (race, _), k in zip(HISPANIC_RACES, parts)]


def make_rows():
    rng = random.Random(SEED)
    plan = []  # (year, race raw or None, ethnicity raw or None)
    for year, groups in RECORDS.items():
        for group, n in groups.items():
            if group == "Hispanic (any race)":
                for race, k in _hispanic_split(n):
                    plan += [(year, race, "HISPANIC")] * k
            else:
                race, eth = GROUP_RAW[group]
                plan += [(year, race, eth)] * n
        for race, eth, k in LEFT_OUT:
            plan += [(year, race, eth)] * (k if year < 2026 else 1)
    rows = []
    for i, (year, race, eth) in enumerate(plan, 1):
        last = date(year, 12, 31) if year < 2026 else NEWEST - timedelta(days=1)
        day = date(year, 1, 1) + timedelta(days=rng.randrange((last - date(year, 1, 1)).days + 1))
        when = f"{day:%Y-%m-%d}T{rng.randrange(24):02d}:{rng.randrange(60):02d}:00.000"
        row = {"id": f"FIXTURE-R-{i:05d}", "event_date_time": when,
               "age": str(rng.randrange(14, 70)),
               "gender": rng.choice(["Male", "Male", "Female"]),
               "district": rng.choice(list(DISTRICTS)),
               "adjacent_to_school": rng.choice(["0", "0", "0", "1"]),
               "data_class": "SYNTHETIC"}
        if race is not None:
            row["race"] = race
        if eth is not None:
            row["ethnicity"] = eth
        rows.append(row)
    # the anchor: the newest record of the copy (a White, not Hispanic record of 2026,
    # in place of the last one made for that group)
    anchor = next(r for r in reversed(rows) if r["event_date_time"].startswith("2026")
                  and r.get("race") == "White" and r.get("ethnicity") == "NON-HISPANIC")
    anchor["event_date_time"] = NEWEST_TIME
    return rows


def group_of(row):
    """R3's group of a record (by the file's labels), or None."""
    eth = ETHNICITY.get(row.get("ethnicity"))
    race = RACE.get(row.get("race"))
    if eth == "Hispanic":
        return "Hispanic (any race)"
    if eth == "not Hispanic":
        return {"Black or African American": "Black, not Hispanic",
                "White": "White, not Hispanic", "Asian": "Asian, not Hispanic"}.get(race)
    return None


def check(rows):
    """Every counting fact of the module text, by plain counting."""
    by_year = Counter((r["event_date_time"][:4], group_of(r)) for r in rows)
    for year, groups in RECORDS.items():
        for group, n in groups.items():
            assert by_year[(str(year), group)] == n, (year, group, by_year[(str(year), group)])
        left = by_year[(str(year), None)]
        assert left == (30 if year < 2026 else 5), (year, left)
    assert max(r["event_date_time"] for r in rows) == NEWEST_TIME
    assert len({r["id"] for r in rows}) == len(rows)
    for year in YEARS:
        for group, (var, est, step, moe) in RESIDENTS_RE.items():
            v = b03002_values(year)[var]
            assert v == (est + step * (2025 - year), moe + 100 * (2025 - year)), (year, group)
        b = b01001_values(year)
        assert b["B01001_001"][0] == b03002_values(year)["B03002_001"][0]
        for table in TABLES:
            values = table_values(table, year)
            assert len(values) == len(table_lines(table)), table
    ten17 = [b01001_values(2025)[v] for v in ("B01001_005", "B01001_006", "B01001_029",
                                               "B01001_030")]
    assert sum(e for e, _ in ten17) == 110000 and sum(m * m for _, m in ten17) == 2500 ** 2


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    for year in YEARS:
        for table in TABLES:
            write(HERE / "census" / str(year) / f"{table}.json",
                  {"note": NOTE, "year": year, "table": table,
                   "answer": group_answer(table, year)})
            write(HERE / "census" / str(year) / f"{table}_labels.json",
                  {"note": NOTE + " The label texts are the Census's own wording.",
                   "year": year, "table": table, **labels_answer(table, year)})
    write(HERE / "census.json", census_config())
    write(HERE / "sources" / "rates_like.json", SOURCE)
    rows = make_rows()
    check(rows)
    path = HERE / "rows" / "rates_like.json"  # one row per line
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"note": ' + json.dumps(NOTE) + ',\n "rows": [\n'
                    + ",\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n]}\n",
                    encoding="utf-8")
    print(f"wrote {len(YEARS) * 4} Census files, census.json, rates_like ({len(rows)} rows)")


if __name__ == "__main__":
    main()
