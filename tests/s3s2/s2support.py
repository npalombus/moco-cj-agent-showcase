"""The truth for the Part S2 tests (rates per resident, docs/S3S2-DESIGN.md), worked out by
plain arithmetic from the fixtures, written out from R5's formulas. Nothing here imports
moco_agent or reads anything under analysis_r/. Brief S3S2-A step 4.

R5, as this file does it (each line is the contract's own):
- residents of a group in a year: the estimates of its Census variables added up; the margin
  of the sum: sqrt(sum of the squared margins) (the Bureau's formula for a sum). A variable
  the Census gives no margin (-555555555) gives the group no margin.
- several years: records added up over residents added up; the residents' margin by the
  formula for a sum, over every variable of every year.
- the rate per 10,000: records / residents x 10,000; its margin: rate x (margin of residents
  / residents) (the Bureau's ratio formula when the top number is exact).
- the rate ratio of a group against the reference: rate / reference rate; its margin by the
  Bureau's formula for a ratio of two estimates, SE(A/B) = (1/B) sqrt(SE(A)^2 + (A/B)^2
  SE(B)^2) with SE = margin / 1.645, given back as a margin (x 1.645): the 1.645 cancels, so
  margin(A/B) = sqrt(mA^2 + (A/B)^2 mB^2) / B. "Clear": ratio - margin to ratio + margin does
  not hold 1.
- the reference: by default the group with the most residents over the years asked.
- R10 point 4: a group under 100 records in the years asked is not shown (no phrase, slot,
  table line); the reference is chosen among the shown groups; no group shown: TOO_LITTLE.

Which records count (R3, R4, config/census.json "records"; the test's own copy of that
section is tests/s3s2/fixtures/census.json, worked out by make_fixtures.py):
- race_ethnicity: ethnicity Hispanic (any race, recorded or not) -> "Hispanic (any race)";
  ethnicity not Hispanic and race Black or African American / White / Asian -> that group;
  everything else (no ethnicity, race unknown or missing with not Hispanic, the two small
  races) is left out.
- gender: the file's labels female and male; anything else (no value, a value the file does
  not list) is left out.
- age_band: a usable age (the source's own `usable` range) in a band; 65 and over runs to the
  top of the usable range; no usable age: left out.
- none: every record of the years.

The words of R10 (phrases, table lines, the lines after the table, the source line, every
refusal sentence), written out by hand from docs/S3S2-DESIGN.md R10, near the end.
"""
import json
import math
import re
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path

import s3ssupport as S

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
CENSUS_DIR = FIXTURES / "census"
YEARS = (2021, 2022, 2023, 2024, 2025)
KEY = "TEST-KEY-NOT-REAL"   # the made-up Census key (brief S3S2-A step 5); never a real one
KEY_PARTS = (KEY, "KEY-NOT-REAL", "TEST-KEY")
Z90 = 1.645
NO_MARGIN = ("-555555555", "*****")
PER = 10000
MIN_RECORDS = 100           # R5: TOO_LITTLE
FLOOR = 10                  # the source's floor
RATES, MAIN = "rates_like", S.MAIN
SOURCE_IDS = {RATES: "FIXTURE:rates_like", MAIN: S.SOURCE_IDS[MAIN]}
UNIT_MANY = "arrest records"
CENSUS_HOST = "api.census.gov"


# ---- the fixtures -------------------------------------------------------------------------

@lru_cache(maxsize=None)
def config():
    """The test's census config (R8's shape), worked out from the Census labels."""
    return json.loads((FIXTURES / "census.json").read_text(encoding="utf-8"))


def census_file(year, table, labels=False):
    name = f"{table}_labels.json" if labels else f"{table}.json"
    return json.loads((CENSUS_DIR / str(year) / name).read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def census_values(year, table):
    """{variable without E/M: (estimate, margin or None)} from the fixture's answer."""
    names, row = census_file(year, table)["answer"]
    cell = dict(zip(names, row))
    out = OrderedDict()
    for name in names:
        if re.fullmatch(r"B\d{5}_\d{3}E", name):
            var = name[:-1]
            margin = cell[var + "M"]
            out[var] = (int(cell[name]), None if margin in NO_MARGIN else int(margin))
    return out


def variable(year, var):
    return census_values(year, var.split("_")[0])[var]


@lru_cache(maxsize=None)
def _rates_rows():
    return tuple(json.loads((FIXTURES / "rows" / "rates_like.json").read_text(
        encoding="utf-8"))["rows"])


def source_json(name):
    if name == RATES:
        return json.loads((FIXTURES / "sources" / "rates_like.json").read_text(
            encoding="utf-8"))
    return S.source_json(name)


def fixture_rows(name):
    """Fresh dicts of the rows the fake county service serves for a source."""
    return [dict(r) for r in _rates_rows()] if name == RATES else S.fixture_rows(name)


def marked(data):
    """The change that marks a source file for rates (R2)."""
    data["rates"] = True


# ---- which records count ------------------------------------------------------------------

def groups_of(by):
    """The group labels of a breakdown, in the config's order (R3, R4)."""
    return list(config()["breakdowns"]["none" if by is None else by])


def group_of(row, by, src):
    """The group a record counts in, or None (left out)."""
    if by is None:
        return "all residents"
    if by == "gender":
        f = S.field(src, "gender")
        label = f["values"].get(row.get("gender"))
        return label if label in ("female", "male") else None
    if by == "age_band":
        (f,) = [f for f in src["fields"] if f["kind"] == "age"]
        age = S.usable_age(row, f)
        if age is None:
            return None
        for band, (lo, hi) in config()["records"]["age_band"].items():
            if age >= lo and (hi is None or age <= hi):
                return band
        return None
    if by == "race_ethnicity":
        eth = S.field(src, "ethnicity")["values"].get(row.get("ethnicity"))
        race = S.field(src, "race")["values"].get(row.get("race"))
        for group, rule in config()["records"]["race_ethnicity"].items():
            if eth == rule["ethnicity"] and ("race" not in rule or race == rule["race"]):
                return group
        return None
    raise AssertionError(by)


def record_counts(name, by, years):
    """({group: records in the years}, records of the years in no group)."""
    src = source_json(name)
    counts = OrderedDict((g, 0) for g in groups_of(by))
    left = 0
    for row in (_rates_rows() if name == RATES else S._rows(name)):
        if int(row[src["time_field"]][:4]) not in years:
            continue
        g = group_of(row, by, src)
        if g is None:
            left += 1
        else:
            counts[g] += 1
    return counts, left


# ---- residents (R5: the formula for a sum) ----------------------------------------------

def group_variables(by, group):
    return [v["variable"] for v in config()["breakdowns"]["none" if by is None else by][group]]


def residents(by, group, years):
    """(estimate, margin or None) of a group over the years: estimates added up, the margin
    sqrt(sum of squared margins); None when a variable has no margin."""
    est, squares, none = 0, 0, False
    for y in years:
        for var in group_variables(by, group):
            e, m = variable(y, var)
            est += e
            if m is None:
                none = True
            else:
                squares += m * m
    return est, (None if none else math.sqrt(squares))


# ---- rates and ratios (R5) ----------------------------------------------------------------

def rate(n, est, moe):
    r = n / est * PER
    return r, (None if moe is None else r * (moe / est))


def ratio(r, m, r_ref, m_ref):
    """The rate ratio and its 90% margin (the Bureau's formula for a ratio of two estimates)
    and whether its range is clear of 1."""
    x = r / r_ref
    se_a, se_b = m / Z90, m_ref / Z90                    # standard error = margin / 1.645
    se = (1 / r_ref) * math.sqrt(se_a ** 2 + x * x * se_b ** 2)
    margin = se * Z90                                    # back to a 90 percent margin
    return x, margin, not (x - margin <= 1 <= x + margin)


CASES = {  # name: (source, by, years, reference or None)
    "re_2025": (RATES, "race_ethnicity", (2025,), None),
    "re_2024_25": (RATES, "race_ethnicity", (2024, 2025), None),
    "re_5y": (RATES, "race_ethnicity", YEARS, None),
    "re_2023": (RATES, "race_ethnicity", (2023,), None),
    "re_2025_hisp": (RATES, "race_ethnicity", (2025,), "Hispanic (any race)"),
    "re_2021": (RATES, "race_ethnicity", (2021,), None),     # Asian: 7 records (the floor)
    "re_2022": (RATES, "race_ethnicity", (2022,), None),     # Asian: 60 (TOO_LITTLE)
    "gender_2025": (MAIN, "gender", (2025,), None),
    "gender_5y": (MAIN, "gender", YEARS, None),
    "gender_2025_male": (MAIN, "gender", (2025,), "male"),
    "age_5y": (MAIN, "age_band", YEARS, None),
    "age_2025": (MAIN, "age_band", (2025,), None),           # two bands under 100 (TOO_LITTLE)
    "all_2025": (MAIN, None, (2025,), None),
    "all_5y": (MAIN, None, YEARS, None),
    "all_re_2025": (RATES, None, (2025,), None),
}


@lru_cache(maxsize=None)
def truth(name):
    """R5 with R10 point 4: a group with fewer than 100 records is not shown; the reference
    and the ratios are among the shown groups only; `records` counts the shown groups."""
    source, by, years, reference = CASES[name]
    counts, left = record_counts(source, by, years)
    groups = OrderedDict()
    for g, n in counts.items():
        est, moe = residents(by, g, years)
        r, m = rate(n, est, moe)
        groups[g] = {"n": n, "residents": est, "residents_margin": moe, "rate": r,
                     "margin": m, "hidden": 1 <= n <= FLOOR - 1,
                     "too_little": n < MIN_RECORDS, "label": label(by, g)}
    shown = [g for g, v in groups.items() if not v["too_little"]]
    ref = None
    if by is not None and shown:   # R10 point 2: capitals do not count in `reference`
        ref = (next(g for g in shown if groups[g]["label"].lower() == reference.lower())
               if reference else max(shown, key=lambda g: groups[g]["residents"]))
    ratios = OrderedDict()
    for g in shown:
        if ref is not None and g != ref:
            v, rr = groups[g], groups[ref]
            x, mx, clear = ratio(v["rate"], v["margin"], rr["rate"], rr["margin"])
            ratios[g] = {"ratio": x, "margin": mx, "clear": clear}
    return {"name": name, "source": source, "by": by, "years": tuple(years),
            "groups": groups, "reference": ref, "ratios": ratios, "left_out": left,
            "shown": shown, "not_shown": [g for g in groups if g not in shown],
            "records": sum(groups[g]["n"] for g in shown),
            "refused": not shown,
            "hidden": [g for g, v in groups.items() if v["hidden"]]}


def analyze_arguments(name, *, by=True, reference=True, period=None, filters=None, **options):
    """The `analyze` call of a case (R8): kind `rate`, the source, whole calendar years,
    options `by` (left out for none) and `reference` (only when the case names one)."""
    source, b, years, ref = CASES[name]
    out = {"kind": "rate", "source": SOURCE_IDS[source],
           "period": period or ({"year": years[0]} if len(years) == 1
                                else {"years": list(years)}),
           "filters": filters or []}
    opts = {}
    if by and b is not None:
        opts["by"] = b
    if reference and ref is not None:
        opts["reference"] = ref
    opts.update(options)
    if opts:
        out["options"] = opts
    return out


# ---- what a person reads: numbers -----------------------------------------------------------

def one(x):
    return f"{x:.1f}"


def two(x):
    return f"{x:.2f}"


def margin_words(m, decimals):
    """R11 point 5 (correction of 13 Nov, planning chat): a margin that rounds to nothing at
    the decimals shown is written `under ±0.1` (a rate) or `under ±0.01` (a ratio)."""
    shown = f"{m:.{decimals}f}"
    if float(shown) == 0:
        return f"under ±{10 ** -decimals:.{decimals}f}"
    return f"±{shown}"


def whole(x):
    return f"{round(x):,}"


def safe(x, decimals):
    """A shown value that is not near a rounding edge (so R and Python round it the same)."""
    scaled = abs(x) * 10 ** decimals
    return abs(scaled - math.floor(scaled) - 0.5) > 1e-6


def check_designed():
    """The facts the tests rely on, not near an edge. Returns lines saying what was checked."""
    lines = []
    for name in CASES:
        t = truth(name)
        for g in t["shown"]:
            v = t["groups"][g]
            assert safe(v["rate"], 1), (name, g, v)
            if v["margin"] is not None:
                assert safe(v["margin"], 1), (name, g, v)
                assert safe(v["residents_margin"], 0), (name, g, v)
        for g, v in t["ratios"].items():
            assert safe(v["ratio"], 2) and safe(v["margin"], 2), (name, g, v)
            lo, hi = v["ratio"] - v["margin"], v["ratio"] + v["margin"]
            assert min(abs(lo - 1), abs(hi - 1)) > 0.005, (name, g, v)
        lines.append(f"{name}: reference {t['reference']}; not shown {t['not_shown']}; " + "; ".join(
            f"{g} n={v['n']} residents={v['residents']} "
            f"margin={'none' if v['residents_margin'] is None else round(v['residents_margin'], 3)}"
            f" rate={v['rate']:.4f} margin={'none' if v['margin'] is None else round(v['margin'], 4)}"
            for g, v in t["groups"].items()) + "".join(
            f"; ratio {g} {v['ratio']:.4f} +/- {v['margin']:.4f} clear={v['clear']}"
            for g, v in t["ratios"].items()))
    assert truth("re_2025")["ratios"]["Asian, not Hispanic"]["clear"] is False
    assert truth("re_2025")["ratios"]["Hispanic (any race)"]["clear"] is True
    assert truth("re_2021")["hidden"] == truth("re_2021")["not_shown"] == ["Asian, not Hispanic"]
    assert truth("re_2022")["not_shown"] == ["Asian, not Hispanic"] and not truth("re_2022")["hidden"]
    assert truth("age_2025")["not_shown"] == ["55 to 64", "65 and over"]
    for name in CASES:
        if name not in ("re_2021", "re_2022", "age_2025"):
            assert not truth(name)["not_shown"], name
    assert truth("all_2025")["groups"]["all residents"]["margin"] is None
    return lines


# ---- R10: the words, written out by hand from docs/S3S2-DESIGN.md R10 -----------------------

# Point 1: each group's label in table order (the config's group names are the tests' keys).
LABELS = {
    "race_ethnicity": ["Hispanic (any race)", "Black, not Hispanic", "White, not Hispanic",
                       "Asian, not Hispanic"],
    "gender": ["female", "male"],
    "age_band": ["aged 10 to 17", "aged 18 to 24", "aged 25 to 34", "aged 35 to 44",
                 "aged 45 to 54", "aged 55 to 64", "aged 65 and over"],
    None: ["All residents"],
}


def label(by, group):
    return LABELS[by][groups_of(by).index(group)]


def in_rate(by, lab):
    """Point 1: the group in the rate phrase, after `per 10,000`."""
    return {"race_ethnicity": f"residents counted as {lab}", "gender": f"{lab} residents",
            "age_band": f"residents {lab}", None: "residents"}[by]


def in_ratio(by, lab):
    """Point 1: the group in a ratio phrase."""
    return {"race_ethnicity": lab, "gender": f"{lab} residents", "age_band": f"residents {lab}"}[by]


def years_words(years):
    """Point 1: `2025`; `2024 and 2025`; `2021 to 2025`."""
    ys = sorted(years)
    if len(ys) == 1:
        return str(ys[0])
    return f"{ys[0]} and {ys[1]}" if len(ys) == 2 else f"{ys[0]} to {ys[-1]}"


def floored(k):
    """A count as C6 and the floor write it."""
    return f"fewer than {FLOOR}" if 1 <= k < FLOOR else f"{k:,}"


def cap(text):
    return text[:1].upper() + text[1:]


NO_MARGIN_BRACKET = "(the Census gives no margin of error for this figure)"


def rate_phrase(t, group):
    """Point 2: `there were about <r> <unit many> per 10,000 <residents form> in <years>
    (margin of error ±<m>)`, the bracket for the county total `(the Census gives no margin of
    error for this figure)`."""
    v = t["groups"][group]
    bracket = (NO_MARGIN_BRACKET if v["margin"] is None
               else f"(margin of error {margin_words(v['margin'], 1)})")
    return (f"there were about {one(v['rate'])} {UNIT_MANY} per 10,000 "
            f"{in_rate(t['by'], v['label'])} in {years_words(t['years'])} {bracket}")


def ratio_phrase(t, group):
    """Point 2 with R6: clear `the rate for <group> was about <x> times the rate for
    <reference> (margin of error ±<m>)`; not clear `the rates for <group> and <reference> were
    not clearly different (ratio <x>, margin of error ±<m>)`."""
    v = t["ratios"][group]
    a = in_ratio(t["by"], t["groups"][group]["label"])
    b = in_ratio(t["by"], t["groups"][t["reference"]]["label"])
    if v["clear"]:
        return (f"the rate for {a} was about {two(v['ratio'])} times the rate for {b} "
                f"(margin of error {margin_words(v['margin'], 2)})")
    return (f"the rates for {a} and {b} were not clearly different (ratio {two(v['ratio'])}, "
            f"margin of error {margin_words(v['margin'], 2)})")


def slots(t, n="a1"):
    """Point 2: `{aN.rate}` with no breakdown; else `{aN.rate.<k>}` for each shown group (k
    counting the shown groups in table order from 1) and `{aN.ratio.<k>}` for each shown group
    but the reference, with that group's k."""
    if t["by"] is None:
        return [f"{{{n}.rate}}"]
    ks = {g: k for k, g in enumerate(t["shown"], 1)}
    return ([f"{{{n}.rate.{ks[g]}}}" for g in t["shown"]]
            + [f"{{{n}.ratio.{ks[g]}}}" for g in t["ratios"]])


def phrases(t):
    """{slot: phrase}, in the order the fixed rendering writes them (every rate, then every
    ratio)."""
    texts = [rate_phrase(t, g) for g in t["shown"]] + [ratio_phrase(t, g) for g in t["ratios"]]
    return dict(zip(slots(t), texts))


def line1(t):
    """Point 2: the fixed rendering, each phrase as its own sentence (S4)."""
    return " ".join(cap(p) + "." for p in phrases(t).values())


def table_line(t, group):
    """Point 3: `<label>: <n> records, <residents> residents (margin of error ±<m>), <r> per
    10,000`; residents and their margins whole, with thousands commas."""
    v = t["groups"][group]
    m = v["residents_margin"]
    bracket = NO_MARGIN_BRACKET if m is None else f"(margin of error ±{whole(m)})"
    return (f"{v['label']}: {v['n']:,} records, {whole(v['residents'])} residents {bracket}, "
            f"{one(v['rate'])} per 10,000")


REASON = {"race_ethnicity": "no race and ethnicity that the Census counts",
          "gender": "no gender recorded", "age_band": "no usable age"}
SMALL_REASON = "in a group with fewer than 100 records"


def not_shown_line(t):
    labels = [t["groups"][g]["label"] for g in t["not_shown"]]
    return f"Not shown, with fewer than 100 records: {'; '.join(labels)}." if labels else None


def used_line(t):
    """Point 5: `(<n> records over <m> months` then one `; <k> not included: <reason>` part
    per reason `.)`; n counts the shown groups' records, m is twelve for each year."""
    parts = []
    if t["by"] is not None and t["left_out"]:
        parts.append(f"; {floored(t['left_out'])} not included: {REASON[t['by']]}")
    small = sum(t["groups"][g]["n"] for g in t["not_shown"])
    if small:
        parts.append(f"; {floored(small)} not included: {SMALL_REASON}")
    return f"({floored(t['records'])} records over {12 * len(t['years'])} months{''.join(parts)}.)"


R0_LINE = ("This is not the share of residents who were arrested: one person can be arrested "
           "several times, and people arrested in the county do not all live in it.")
R5_LINE = ("The margin of error comes from the Census's survey alone, at the Census's 90 percent "
           "level; it says nothing about chance in the number of arrests from year to year.")
R3_LINE = ("The police record what an officer writes down; the Census records what people say "
           "about themselves. The two do not match person for person.")
ASSOCIATION_LINE = (f"These are patterns in recorded {UNIT_MANY}: what goes with what, not what "
                    f"causes what.")
NOT_RATES = (f"These are patterns in recorded {UNIT_MANY}, not rates: what goes with what, not "
             f"what causes what.",                                              # S11 2f
             f"These are counts of {UNIT_MANY}, not rates, and they show no cause.")  # C10
CENSUS_SOURCE = "Census Bureau, American Community Survey one-year estimates"


def source_line(title, county_date, census_date, first=True):
    """Point 5: the first answer's source line, or a later answer's."""
    if first:
        return (f"Source: {title} (county open data), copy of {county_date}; {CENSUS_SOURCE}, "
                f"copy of {census_date}. A count is of {UNIT_MANY}, not people. Want the "
                f"details and the R script?")
    return f"({title}, county open data, copy of {county_date}; {CENSUS_SOURCE}, copy of {census_date}.)"


def reply_lines(t, title, county_date, census_date, first=True):
    """The whole fixed reply, line by line: line 1, the table, then point 5's lines in order
    (R5's sentence only when a margin of error is shown somewhere; R3's for race_ethnicity)."""
    out = [line1(t)] + [table_line(t, g) for g in t["shown"]]
    if t["not_shown"]:
        out.append(not_shown_line(t))
    out += [used_line(t), R0_LINE]
    if any(t["groups"][g]["margin"] is not None for g in t["shown"]):
        out.append(R5_LINE)
    if t["by"] == "race_ethnicity":
        out.append(R3_LINE)
    return out + [ASSOCIATION_LINE, source_line(title, county_date, census_date, first)]


# Point 7, every sentence word for word.
REFUSE = {
    "by_district": ("I can't give a rate by police district, because the Census does not count "
                    "residents by district. I can give the count by district, or a rate for the "
                    "whole county."),
    "in_district": ("I can't give a rate inside one police district, because the Census does not "
                    "count residents by district. I can give the count for that district, or a "
                    "rate for the whole county."),
    "race": ("I can't give a rate by race alone, because many Hispanic residents do not choose a "
             "race such as White in the Census while the police record one for them, so the two "
             "counts would not be of the same people. I can give a rate by race and ethnicity "
             "together."),
    "ethnicity": ("I can't give a rate by ethnicity alone, because the groups have to mean the "
                  "same in the police records and in the Census, and this agent matches them by "
                  "race and ethnicity together. I can give a rate by race and ethnicity "
                  "together; its first group is Hispanic (any race)."),
    "two_ways": ("I can't give a rate broken down two ways at once: this version matches the "
                 "Census one breakdown at a time. Ask for one of: by gender, by age band, or by "
                 "race and ethnicity."),
    "part_year": ("I can't give a rate for part of a year, because the Census counts residents "
                  "for whole calendar years only. Ask for one or more whole years."),
}
TOO_LITTLE_LINE = ("There is too little data for a rate: it needs at least 100 records in a "
                   "group, and none here has that many.")


def refuse_field(dimension):
    return (f"I can't give a rate by {dimension}, because the Census does not count residents "
            f"by {dimension}. I can give the count by {dimension}, or a rate by gender, by age "
            f"band, or by race and ethnicity.")


def refuse_filtered(what):
    return (f"I can't give a rate for a filtered selection ({what}), because the Census has no "
            f"count of residents to match it. I can give the count, or a rate for all "
            f"{UNIT_MANY} by gender, by age band, or by race and ethnicity.")


def refuse_not_marked(title):
    return (f"I can't give a rate for {title}, because no count of residents has been matched "
            f"to that source. I can give counts from it.")


def refuse_no_copy(years):
    which = "that year" if len(years) == 1 else "those years"
    return (f"I can't give a rate for {years_words(years)}, because I have no Census figures "
            f"for {which} yet. The Census publishes a year's estimates late in the following "
            f"year.")


def refuse_reference(given, shown_labels):
    return (f"I can't compare with \"{given}\", because it is not one of the groups shown for "
            f"that breakdown: {'; '.join(shown_labels)}.")


# ---- a value written anywhere, at any precision (R10 point 9; autocheck change 5) -----------

_MONTHS = ("January|February|March|April|May|June|July|August|September|October|November|"
           "December")
_DATES = (rf"\b\d{{1,2}} (?:{_MONTHS}) \d{{4}}\b", rf"\b(?:{_MONTHS}) \d{{1,2}}, \d{{4}}\b",
          r"\b\d{4}-\d{2}-\d{2}(?:[T ][0-9:.]+(?:Z|[+-]\d{2}:?\d{2})?)?")
_NUMBER = re.compile(r"(?<![\w.,])\d{1,3}(?:,\d{3})+(?:\.\d+)?(?![\w])"
                     r"|(?<![\w.,])\d+(?:\.\d+)?(?![\w])")


def undated(text):
    """`text` with every date (and date-time) taken out, so the 7th of a month is no figure."""
    for pattern in _DATES:
        text = re.sub(pattern, " ", text)
    return text


def numbers(text):
    """[(value, decimals)] of every number written in `text` (thousands commas allowed)."""
    out = []
    for m in _NUMBER.finditer(text):
        digits = m.group(0).replace(",", "")
        out.append((float(digits), len(digits.split(".")[1]) if "." in digits else 0))
    return out


def written(text, value, *, whole=False, min_decimals=1):
    """Whether `value` is written in `text`: with d decimals (d >= min_decimals), rounded or
    cut to d; with `whole`, also as a whole number (rounded or cut). Full precision is allowed
    a relative 1e-9 (R's and Python's last digits may differ)."""
    for x, d in numbers(text):
        if d == 0 and not whole or 0 < d < min_decimals:
            continue
        step, slack = 10 ** -d, 1e-9 * max(1.0, abs(value))
        if abs(x - value) <= step / 2 + slack or 0 <= abs(value) - x < step + slack:
            return True
    return False


def hand_lines():
    """The truth's numbers for the three hand-checked cases (brief step 4)."""
    out = []
    t = truth("re_2025")
    out.append("CASE 1: race_ethnicity, 2025 (rates_like), reference by default")
    for g, v in t["groups"].items():
        out.append(f"  {g}: n={v['n']} residents={v['residents']:,} margin={v['residents_margin']:,.4f} "
                   f"rate={v['rate']:.6f} ({one(v['rate'])}) margin={v['margin']:.6f} "
                   f"({one(v['margin'])})")
    out.append(f"  reference: {t['reference']}")
    for g, v in t["ratios"].items():
        out.append(f"  ratio {g}: {v['ratio']:.6f} ({two(v['ratio'])}) margin {v['margin']:.6f} "
                   f"({two(v['margin'])}) clear={v['clear']}")
    t = truth("re_2024_25")
    out.append("CASE 2: race_ethnicity, 2024 and 2025 together (rates_like)")
    for g, v in t["groups"].items():
        out.append(f"  {g}: n={v['n']} residents={v['residents']:,} margin={v['residents_margin']:,.4f} "
                   f"rate={v['rate']:.6f} ({one(v['rate'])}) margin={v['margin']:.6f} "
                   f"({one(v['margin'])})")
    out.append(f"  reference: {t['reference']}")
    for g, v in t["ratios"].items():
        out.append(f"  ratio {g}: {v['ratio']:.6f} ({two(v['ratio'])}) margin {v['margin']:.6f} "
                   f"({two(v['margin'])}) clear={v['clear']}")
    t = truth("age_2025")
    v = t["groups"]["10 to 17"]
    out.append("CASE 3: age band 10 to 17, 2025 (stats_like; four Census lines added up)")
    out.append(f"  variables: {', '.join(group_variables('age_band', '10 to 17'))}: "
               + ", ".join(f"{variable(2025, x)[0]:,} (margin {variable(2025, x)[1]:,})"
                           for x in group_variables("age_band", "10 to 17")))
    out.append(f"  n={v['n']} residents={v['residents']:,} margin={v['residents_margin']:,.4f} "
               f"rate={v['rate']:.6f} ({one(v['rate'])}) margin={v['margin']:.6f} "
               f"({one(v['margin'])})")
    return out


if __name__ == "__main__":
    import sys
    for line in (hand_lines() if sys.argv[1:2] == ["--hand"] else check_designed()):
        print(line)
