"""Part S2: rates per resident (docs/S3S2-DESIGN.md; R11 wins over R10, R10 over R0 to R9).

`analyze` with kind `rate`: records counted in whole calendar years, over the Census Bureau's
estimate of the residents of that kind (config/census.json), per 10,000. Python checks the
request and refuses, in R10 point 7's order, with its fixed sentence; counts the records into
the groups of R3 and R4; adds up the Census variables of each group; and writes the phrases,
the table and the lines. R (analysis_r/rate.R) does the arithmetic of R5: the residents'
margins by the Bureau's formula for a sum, each rate and its margin, each rate ratio and its
margin by the formula for a ratio, and draws the chart.

A group with fewer than 100 records in the years asked is not shown (R10 point 4): it gets no
phrase, slot, table line, dot or line in `details`, and none of its figures is kept or given
to R; only its label and, in the used line, the records of the groups not shown (by the
floor).
"""
import csv
import json
import math
import urllib.parse
from collections import OrderedDict
from datetime import date
from pathlib import Path

from . import census, counting
from .analysis import join_and
from .counting import SpecError, day_text, shown

PER = 10000
MIN_RECORDS = 100                 # R5 and R10 point 4: a group is shown from 100 records
BREAKDOWNS = ("race_ethnicity", "gender", "age_band")
NO_BREAKDOWN = ("", "none")       # `by` left out
TABLE = {"race_ethnicity": "B03002"}   # R10 point 6: B01001 otherwise
BY_WORDS = {"race_ethnicity": "race and ethnicity", "gender": "gender", "age_band": "age band"}
REASONS = {"race_ethnicity": "no race and ethnicity that the Census counts",
           "gender": "no gender recorded", "age_band": "no usable age"}
SMALL_REASON = f"in a group with fewer than {MIN_RECORDS} records"
CENSUS_SOURCE = "Census Bureau, American Community Survey one-year estimates"
NO_MARGIN = "(the Census gives no margin of error for this figure)"
OFFER = "a rate by gender, by age band, or by race and ethnicity"

# R10 point 5, word for word
R0_LINE = ("This is not the share of residents who were arrested: one person can be arrested "
           "several times, and people arrested in the county do not all live in it.")
R5_LINE = ("The margin of error comes from the Census's survey alone, at the Census's 90 percent "
           "level; it says nothing about chance in the number of arrests from year to year.")
R3_LINE = ("The police record what an officer writes down; the Census records what people say "
           "about themselves. The two do not match person for person.")

# R10 point 7, word for word
BY_DISTRICT = ("I can't give a rate by police district, because the Census does not count "
               "residents by district. I can give the count by district, or a rate for the whole "
               "county.")
IN_DISTRICT = ("I can't give a rate inside one police district, because the Census does not "
               "count residents by district. I can give the count for that district, or a rate "
               "for the whole county.")
BY_RACE = ("I can't give a rate by race alone, because many Hispanic residents do not choose a "
           "race such as White in the Census while the police record one for them, so the two "
           "counts would not be of the same people. I can give a rate by race and ethnicity "
           "together.")
BY_ETHNICITY = ("I can't give a rate by ethnicity alone, because the groups have to mean the same "
                "in the police records and in the Census, and this agent matches them by race and "
                "ethnicity together. I can give a rate by race and ethnicity together; its first "
                "group is Hispanic (any race).")
TWO_WAYS = ("I can't give a rate broken down two ways at once: this version matches the Census "
            "one breakdown at a time. Ask for one of: by gender, by age band, or by race and "
            "ethnicity.")
PART_YEAR = ("I can't give a rate for part of a year, because the Census counts residents for "
             "whole calendar years only. Ask for one or more whole years.")
TOO_LITTLE_LINE = (f"There is too little data for a rate: it needs at least {MIN_RECORDS} "
                   f"records in a group, and none here has that many.")
# Not in point 7 (readings, kit-log/raw/S3S2-B-notes.txt): each still says no and why.
NOT_A_RUN = ("I can't give a rate for years that are not one after another: ask for one year, or "
             "for several years in a row.")
OPTIONS_SHAPE = ('I can\'t give that rate: its options are "by" (gender, age_band or '
                 'race_ethnicity, or left out) and "reference" (the label of one group).')


class Refused(Exception):
    """A rate refused before R (BAD_OPTIONS, or TOO_LITTLE after counting), with its fixed
    sentence. The sentence holds no value from the data."""

    def __init__(self, code, sentence):
        super().__init__(sentence)
        self.code, self.sentence = code, sentence


# ---- words (R10 point 1) -----------------------------------------------------------------------

def label(by, key):
    """A group's label: the config's name, `aged <name>` for an age band, `All residents`."""
    if by is None:
        return "All residents"
    return f"aged {key}" if by == "age_band" else key


def in_rate(by, lab):
    return {"race_ethnicity": f"residents counted as {lab}", "gender": f"{lab} residents",
            "age_band": f"residents {lab}", None: "residents"}[by]


def in_ratio(by, lab):
    return lab if by == "race_ethnicity" else f"{lab} residents" if by == "gender" else \
        f"residents {lab}"


def years_words(years):
    """`2025`; `2024 and 2025`; `2021 to 2025` (the years of a rate are one unbroken run)."""
    ys = sorted(years)
    if len(ys) == 1:
        return str(ys[0])
    if ys != list(range(ys[0], ys[-1] + 1)):
        return join_and([str(y) for y in ys])
    return f"{ys[0]} and {ys[1]}" if len(ys) == 2 else f"{ys[0]} to {ys[-1]}"


def margin_words(m, decimals):
    """R11 point 5: a margin that rounds to nothing is `under ±0.1` (a rate) or `under ±0.01`
    (a ratio)."""
    text = f"{m:.{decimals}f}"
    if float(text) == 0:
        return f"under ±{10 ** -decimals:.{decimals}f}"
    return f"±{text}"


def whole(x):
    return f"{round(x):,}"


def read_as(source, by, years):
    """What was analysed, in words: the tool answer, the chart's title, details."""
    words = f" by {BY_WORDS[by]}" if by else ""
    return f"{source['unit']['many']} per 10,000 residents{words}, {years_words(years)}"


def refuse_field(dimension):
    return (f"I can't give a rate by {dimension}, because the Census does not count residents "
            f"by {dimension}. I can give the count by {dimension}, or {OFFER}.")


def refuse_filtered(what, many):
    return (f"I can't give a rate for a filtered selection ({what}), because the Census has no "
            f"count of residents to match it. I can give the count, or a rate for all {many} by "
            f"gender, by age band, or by race and ethnicity.")


def refuse_not_marked(title):
    return (f"I can't give a rate for {title}, because no count of residents has been matched to "
            f"that source. I can give counts from it.")


def refuse_no_copy(years):
    which = "that year" if len(years) == 1 else "those years"
    return (f"I can't give a rate for {years_words(years)}, because I have no Census figures for "
            f"{which} yet. The Census publishes a year's estimates late in the following year.")


def refuse_reference(given, shown_labels):
    return (f"I can't compare with \"{given}\", because it is not one of the groups shown for "
            f"that breakdown: {'; '.join(shown_labels)}.")


def refuse_by(by):
    return (f"I can't give a rate by {by}: {OFFER} is what this version can match to the "
            f"Census.")


def refuse_not_in_source(title, by):
    return (f"I can't give a rate by {BY_WORDS[by]} for {title}, because its records do not "
            f"hold {BY_WORDS[by]}.")


# ---- the request, checked in R10 point 7's order -------------------------------------------------

def whole_years(period):
    """The years of a period that is whole calendar years, else None."""
    if "years" in period:
        return list(period["years"])
    if "year" in period:
        months = period.get("months")
        return [period["year"]] if months is None or (months["from"], months["to"]) == (1, 12) \
            else None
    first, last = date.fromisoformat(period["from"]), date.fromisoformat(period["to"])
    if (first.month, first.day, last.month, last.day) == (1, 1, 12, 31):
        return list(range(first.year, last.year + 1))
    return None


def _district(fields):
    return next((name for name, f in fields.items() if f.get("dimension") == "district"), None)


def _person(fields):
    return {name for name, f in fields.items()
            if f["kind"] == "age" or (f["kind"] == "category" and f.get("person"))}


def _needs(by, cfg):
    """The source fields a breakdown reads."""
    if by == "age_band":
        return []
    return sorted({name for rule in cfg["records"][by].values() for name in rule})


def check(source, copy, spec, options, state_dir, cfg=None):
    """R10 point 7 up to the two refusals that come after counting. Returns the plan
    {"by", "years", "reference"}; raises Refused, or SpecError for a year the copy does not
    reach at all."""
    cfg = cfg or census.settings()
    if source.get("rates") is not True:
        raise Refused("BAD_OPTIONS", refuse_not_marked(source["title"]))
    years = whole_years(spec["period"])
    start, newest = counting.coverage(source, copy)
    if years is not None and any(y < start.year or y > newest.year for y in years):
        raise SpecError("OUT_OF_COVERAGE", covers=counting.covers_text(source, copy))
    if years is None or any(date(y, 1, 1) < start or date(y, 12, 31) > newest for y in years):
        raise Refused("BAD_OPTIONS", PART_YEAR)
    if years != list(range(years[0], years[-1] + 1)):
        raise Refused("BAD_OPTIONS", NOT_A_RUN)
    missing = [y for y in years if census.latest(state_dir, y, cfg) is None]
    if missing:
        raise Refused("BAD_OPTIONS", refuse_no_copy(missing))
    options = {} if options is None else options
    if not isinstance(options, dict):
        raise Refused("BAD_OPTIONS", OPTIONS_SHAPE)
    by = options.get("by")
    if isinstance(by, list) and len(by) == 1:  # ponytail: one breakdown sent as a list
        by = by[0]
    if by is None or (isinstance(by, str) and by.strip().lower() in NO_BREAKDOWN):
        by = None
    fields = {f["name"]: f for f in source["fields"]}
    named = [flt["field"] for flt in spec["filters"]]
    district = _district(fields)
    if district is not None and by == district:
        raise Refused("BAD_OPTIONS", BY_DISTRICT)
    if district is not None and district in named:
        raise Refused("BAD_OPTIONS", IN_DISTRICT)
    if by == "race":
        raise Refused("BAD_OPTIONS", BY_RACE)
    if by == "ethnicity":
        raise Refused("BAD_OPTIONS", BY_ETHNICITY)
    if by is not None and not isinstance(by, list) and by not in BREAKDOWNS:
        f = fields.get(by) if isinstance(by, str) else None
        if f is not None and f.get("dimension"):
            raise Refused("BAD_OPTIONS", refuse_field(f["dimension"]))
        raise Refused("BAD_OPTIONS", refuse_by(by if isinstance(by, str) else "that"))
    if isinstance(by, list) or (by is not None and set(named) & _person(fields)):
        raise Refused("BAD_OPTIONS", TWO_WAYS)
    if spec["filters"]:
        from .statwords import what
        raise Refused("BAD_OPTIONS", refuse_filtered(what(source, spec["filters"]),
                                                     source["unit"]["many"]))
    reference = options.get("reference")
    if set(options) - {"by", "reference"} or not (reference is None or isinstance(reference, str)):
        raise Refused("BAD_OPTIONS", OPTIONS_SHAPE)
    if by is not None:
        lacking = [n for n in _needs(by, cfg) if fields.get(n, {}).get("kind") != "category"]
        if lacking or (by == "age_band" and not any(f["kind"] == "age" for f in fields.values())):
            raise Refused("BAD_OPTIONS", refuse_not_in_source(source["title"], by))
    return {"by": by, "years": years, "reference": reference}


# ---- the records (R3, R4) ------------------------------------------------------------------------

def group_of(row, by, fields, age, rules):
    """The config's group a record counts in, or None (left out)."""
    if by is None:
        return True
    if by == "age_band":
        a = counting._usable_age(row.get(age["name"]), age)
        if a is None:
            return None
        return next((band for band, (lo, hi) in rules.items()
                     if a >= lo and (hi is None or a <= hi)), None)
    for group, rule in rules.items():
        if all(fields[name]["values"].get(row.get(name)) == want for name, want in rule.items()):
            return group
    return None


def count(source, rows, plan, cfg=None):
    """({group: records in the years asked}, records of those years in no group)."""
    cfg = cfg or census.settings()
    by, years = plan["by"], set(plan["years"])
    keys = list(cfg["breakdowns"]["none" if by is None else by])
    fields = {f["name"]: f for f in source["fields"]}
    age = next((f for f in source["fields"] if f["kind"] == "age"), None)
    rules = cfg["records"].get(by) if by else None
    counts, left = OrderedDict((k, 0) for k in keys), 0
    tf = source["time_field"]
    for row in rows:
        when = row.get(tf)
        if not (isinstance(when, str) and when[:4].isdigit() and int(when[:4]) in years):
            continue
        g = group_of(row, by, fields, age, rules)
        if g is None:
            left += 1
        else:
            counts[keys[0] if g is True else g] += 1
    return counts, left


def residents(cfg, by, key, years, copies):
    """The estimates of a group's Census variables added up over the years (whole numbers)."""
    lines = cfg["breakdowns"]["none" if by is None else by][key]
    return sum(copies[y]["values"][v["variable"]][0] for y in years for v in lines)


def choose(plan, counts, copies, cfg=None):
    """After counting (R10 points 4 and 7): the shown groups and the reference, or Refused
    (TOO_LITTLE, then an unknown reference)."""
    cfg = cfg or census.settings()
    by = plan["by"]
    shown_keys = [k for k, n in counts.items() if n >= MIN_RECORDS]
    if not shown_keys:
        raise Refused("TOO_LITTLE", TOO_LITTLE_LINE)
    labels = {k: label(by, k) for k in counts}
    given = plan["reference"]
    if given is not None:
        found = [k for k in shown_keys if labels[k].lower() == given.strip().lower()]
        if not found:
            raise Refused("BAD_OPTIONS", refuse_reference(given, [labels[k] for k in shown_keys]))
        reference = found[0]
    else:
        reference = max(shown_keys, key=lambda k: residents(cfg, by, k, plan["years"], copies))
    return shown_keys, (None if by is None else reference)


# ---- R's job and its answer ------------------------------------------------------------------------

def census_rows(cfg, by, shown_keys, years, copies):
    """input.csv: one line per shown group, year and Census variable."""
    out = []
    for k, key in enumerate(shown_keys, 1):
        for y in years:
            for v in cfg["breakdowns"]["none" if by is None else by][key]:
                est, moe = copies[y]["values"][v["variable"]]
                out.append([k, y, v["variable"], est, "" if moe is None else moe])
    return out


def write_job(folder, job, rows):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "job.json").write_text(json.dumps(job, indent=2) + "\n", encoding="utf-8")
    with open(folder / "input.csv", "w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(["k", "year", "variable", "estimate", "margin"])
        writer.writerows(rows)


def _finite(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def read_result(folder, kind="rate"):
    """result.json in rate.R's shape, and a chart.png; else EngineError ENGINE_FAILED."""
    from .stats import PNG, EngineError
    folder = Path(folder)
    try:
        result = json.loads((folder / "result.json").read_text(encoding="utf-8"))
        chart = (folder / "chart.png").read_bytes()[:8]
        job = json.loads((folder / "job.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise EngineError("ENGINE_FAILED", "R left no readable result.json or chart.png") from None
    want = job["groups"]
    groups = result.get("groups") if isinstance(result, dict) else None
    ratios = result.get("ratios") if isinstance(result, dict) else None

    def group_ok(g, w):
        return (isinstance(g, dict) and g.get("k") == w["k"] and g.get("records") == w["records"]
                and g.get("residents") == w["residents"] and _finite(g.get("rate"))
                and (g.get("margin") is None) is w["no_margin"]
                and (g.get("residents_margin") is None) is w["no_margin"]
                and (g["margin"] is None or _finite(g["margin"]))
                and isinstance(g.get("years"), list) and len(g["years"]) == len(job["years"]))

    others = [w["k"] for w in want if job["reference"] is not None and w["k"] != job["reference"]]
    ok = (chart == PNG and isinstance(groups, list) and len(groups) == len(want)
          and all(group_ok(g, w) for g, w in zip(groups, want)) and isinstance(ratios, list)
          and [r.get("k") if isinstance(r, dict) else None for r in ratios] == others
          and all(_finite(r.get("ratio")) and _finite(r.get("margin"))
                  and isinstance(r.get("clear"), bool) for r in ratios))
    if not ok:
        raise EngineError("ENGINE_FAILED", "R's result.json is not in the shape rate.R gives")
    return result


# ---- what Python writes (R10 points 2 to 6) ---------------------------------------------------------

def rate_phrase(many, by, years, g):
    bracket = NO_MARGIN if g["margin"] is None else \
        f"(margin of error {margin_words(g['margin'], 1)})"
    return (f"there were about {g['rate']:.1f} {many} per 10,000 {in_rate(by, g['label'])} in "
            f"{years_words(years)} {bracket}")


def ratio_phrase(by, g, ref, x):
    a, b = in_ratio(by, g["label"]), in_ratio(by, ref["label"])
    m = margin_words(x["margin"], 2)
    if x["clear"]:
        return f"the rate for {a} was about {x['ratio']:.2f} times the rate for {b} (margin of error {m})"
    return (f"the rates for {a} and {b} were not clearly different (ratio {x['ratio']:.2f}, "
            f"margin of error {m})")


def table_line(g):
    m = g["residents_margin"]
    bracket = NO_MARGIN if m is None else f"(margin of error ±{whole(m)})"
    return (f"{g['label']}: {g['records']:,} records, {whole(g['residents'])} residents {bracket}, "
            f"{g['rate']:.1f} per 10,000")


def used_text(rate, floor):
    """R10 point 5: `<n> records over <m> months` and one part per reason."""
    parts = ""
    if rate["by"] is not None and rate["left_out"]:
        parts += f"; {shown(rate['left_out'], floor)} not included: {REASONS[rate['by']]}"
    if rate["small"]:
        parts += f"; {shown(rate['small'], floor)} not included: {SMALL_REASON}"
    return f"{shown(rate['records'], floor)} records over {12 * len(rate['years'])} months{parts}"


def used_line(r, named=False):
    text = used_text(r["rate"], r["floor"])
    return f"For {r['read_as']}: {text}." if named else f"({text}.)"


def not_shown_line(rate):
    if not rate["not_shown"]:
        return None
    return (f"Not shown, with fewer than {MIN_RECORDS} records: "
            f"{'; '.join(rate['not_shown'])}.")


def margin_shown(r):
    return any(g["margin"] is not None for g in r["rate"]["groups"])


def census_part(r):
    """`; Census Bureau, American Community Survey one-year estimates, copy of <date>`."""
    return f"; {CENSUS_SOURCE}, copy of {day_text(date.fromisoformat(r['rate']['census_date']))}"


def fill(r, answer, plan, shown_keys, counts, left, by_labels):
    """R's figures into the result, then the phrases, slots and table."""
    many, by, years = r["unit"]["many"], plan["by"], plan["years"]
    groups = []
    for key, g in zip(shown_keys, answer["groups"]):
        groups.append({"key": key, "label": by_labels[key], "records": g["records"],
                       "residents": g["residents"], "residents_margin": g["residents_margin"],
                       "rate": g["rate"], "margin": g["margin"],
                       "years": [{"year": int(y["year"]), "residents": y["residents"],
                                  "residents_margin": y["residents_margin"]}
                                 for y in g["years"]]})
    by_k = {k: g for k, g in enumerate(groups, 1)}
    ref_k = answer.get("reference")
    ratios = [{"k": x["k"], "label": by_k[x["k"]]["label"], "ratio": x["ratio"],
               "margin": x["margin"], "clear": x["clear"]} for x in answer["ratios"]]
    not_shown = [by_labels[k] for k in counts if k not in shown_keys]
    r["rate"] = {"by": by, "years": list(years), "table": TABLE.get(by, "B01001"),
                 "groups": groups, "ratios": ratios,
                 "reference": by_k[ref_k]["label"] if ref_k else None, "not_shown": not_shown,
                 "small": sum(n for k, n in counts.items() if k not in shown_keys),
                 "left_out": left, "records": sum(g["records"] for g in groups),
                 **r.pop("census_info")}
    phrases = OrderedDict()
    for k, g in by_k.items():
        phrases["rate" if by is None else f"rate.{k}"] = rate_phrase(many, by, years, g)
    for x in ratios:
        phrases[f"ratio.{x['k']}"] = ratio_phrase(by, by_k[x["k"]], by_k[ref_k], x)
    r["phrases"] = dict(phrases)
    r["slots"] = [f"{{{r['id']}.{name}}}" for name in phrases]
    r["table"] = [table_line(g) for g in groups]


def details_lines(r, source):
    """R10 point 6: the Census table, each year's residents of each shown group with its margin,
    the model sentence, the script; nothing of a group not shown but its label."""
    rate = r["rate"]
    lines = [f"Read as: {r['read_as']}."] + list(r["table"])
    if rate["not_shown"]:
        lines.append(not_shown_line(rate))
    lines.append(f"Census: {CENSUS_SOURCE}, table {rate['table']}, Montgomery County, Maryland; "
                 f"newest copy of {day_text(date.fromisoformat(rate['census_date']))}.")
    for c in rate["copies"]:
        lines.append(f"Census copy of {c['year']}: saved "
                     f"{day_text(date.fromisoformat(c['fetched_at'][:10]))}, fingerprint "
                     f"{c['sha256'][:12]}.")
    for y in rate["years"]:
        for g in rate["groups"]:
            one = next(v for v in g["years"] if v["year"] == y)
            m = one["residents_margin"]
            lines.append(f"{y}, {g['label']}: {whole(one['residents'])} residents "
                         + (NO_MARGIN if m is None else f"(margin of error ±{whole(m)})") + ".")
    lines.append("Model: " + model_sentence(r))
    lines += [f"Result: {p[:1].upper()}{p[1:]}." for p in r["phrases"].values()]
    lines.append(f"Used: {used_text(rate, r['floor'])}.")
    lines.append("The R script attached downloads the same public data from the county and the "
                 "same tables from the Census, counts and adds up the same way, and prints the "
                 "same rates, ratios and margins.")
    return lines


def model_sentence(r):
    rate = r["rate"]
    ref = (f" Each ratio compares a group's rate with the rate for {rate['reference']}."
           if rate["reference"] else "")
    return ("The records counted in each calendar year, divided by the Census Bureau's estimate "
            "of the residents of that kind that year, times 10,000; for several years, the records "
            "added up over the residents added up. The margins of error are the Census's own, at "
            "its 90 percent level, carried by the Bureau's published formulas for a sum and for a "
            "ratio; the count of records is taken as exact." + ref)


def limitations(source, r):
    many, copy = source["unit"]["many"], r["copy"]
    return [
        f"A rate here is {many} per 10,000 residents. " + R0_LINE,
        "The residents are the Census Bureau's American Community Survey one-year estimates for "
        "Montgomery County, Maryland. " + R5_LINE,
        f"Counts under {source['floor']} are never shown, and a group with fewer than "
        f"{MIN_RECORDS} records in the years asked is not shown at all.",
        f"Every rate and margin was computed by R from saved copies (the county's of "
        f"{day_text(date.fromisoformat(copy['date']))}, the Census's of "
        f"{day_text(date.fromisoformat(r['rate']['census_date']))}), not from the live sites. An "
        f"AI model chose the analysis from a fixed menu and never saw a figure; Python wrote every "
        f"word and number of the answer.",
    ]


def chart_labels(source, copy, r_read_as, years, census_date, by):
    return {"title": r_read_as[:1].upper() + r_read_as[1:],
            "subtitle": f"{years_words(years)}. Copies of the county's data of "
                        f"{day_text(copy.day)} and of the Census's estimates of "
                        f"{day_text(date.fromisoformat(census_date))}.",
            "foot": f"{source['title']}; {CENSUS_SOURCE}. Recorded {source['unit']['many']}, "
                    f"not people, and not the share of residents arrested. Lines: the Census's "
                    f"90 percent margin of error."
                    + (" The reference group is marked." if by else ""),
            "axis": f"{source['unit']['many'][:1].upper()}{source['unit']['many'][1:]} per "
                    f"10,000 residents"}


# ---- the script anyone can run (S7 with R8) -------------------------------------------------------

def script_text(source, copy, r, plan, cfg=None):
    """One R file that downloads the county's records and the Census's tables from their public
    addresses (the Census's with no key), counts and adds up the same way and prints the same
    rates. The county's address is written once, on `data_url <- "..."`; no record is in it."""
    cfg = cfg or census.settings()
    from .stats import R_DIR
    by, years = plan["by"], plan["years"]
    tf = source["time_field"]
    fields = {f["name"]: f for f in source["fields"]}
    age = next((f for f in source["fields"] if f["kind"] == "age"), None)
    used = ([age["name"]] if by == "age_band" else _needs(by, cfg) if by else [])
    query = urllib.parse.urlencode(
        {"$select": ",".join([tf] + used),
         "$where": f"{tf} >= '{years[0]:04d}-01-01T00:00:00' AND "
                   f"{tf} < '{years[-1] + 1:04d}-01-01T00:00:00'",
         "$limit": 1000000}, quote_via=urllib.parse.quote)
    breakdown = cfg["breakdowns"]["none" if by is None else by]
    job = {"read_as": r["read_as"], "per": PER, "z": cfg["margin_z"], "min_records": MIN_RECORDS,
           "years": list(years), "by": by, "time_field": tf, "tables": [r["rate"]["table"]],
           "no_margin": cfg["no_margin_codes"], "reference": plan["reference"],
           "groups": [{"key": key, "label": label(by, key),
                       "variables": [v["variable"] for v in lines],
                       "ages": cfg["records"]["age_band"][key] if by == "age_band" else None,
                       "rule": cfg["records"][by][key] if by in ("gender", "race_ethnicity")
                       else None}
                      for key, lines in breakdown.items()],
           "fields": {n: {"values": fields[n]["values"]} for n in used if n in fields
                      and fields[n]["kind"] == "category"},
           "age_field": age["name"] if by == "age_band" else None,
           "usable": age["usable"] if by == "age_band" else None}
    place = cfg["place"]
    census_dates = ", ".join(f"{c['year']} saved {day_text(date.fromisoformat(c['fetched_at'][:10]))}"
                             for c in r["rate"]["copies"])
    head = [
        "# The R script of one rate per resident by the Montgomery County criminal justice data",
        "# agent (a university course project, not a county service).",
        f"# It reruns: {r['read_as']}.",
        f"# The agent's numbers came from its copy of {source['title']}, saved on",
        f"# {day_text(copy.day)} (fingerprint {copy.sha256[:12]}), and its copies of the Census "
        f"Bureau's",
        f"# American Community Survey one-year estimates, table {r['rate']['table']} "
        f"({census_dates}).",
        "# The county may have corrected records since then, so the last digit can differ.",
        "# It downloads the county's records from the address below and the Census tables from",
        "# api.census.gov, counts and adds up the same way and prints the same rates, one line",
        "# each: <name> <estimate> <low> <high>, the range being the estimate minus and plus its",
        "# 90 percent margin of error. It holds no record of the data and saves nothing.",
        "# It uses base R and jsonlite. Run it with: Rscript script.R",
        "# To use a saved copy instead, point data_url (or census_url) at that file.",
        "",
        f'data_url <- "{source["address"]}?{query}"',
        "",
        "# The Census address holds no key: add your own Census API key at the end of census_url,",
        '# as paste0(<the address>, "&key=", <your key>).',
        "census_url <- function(year, table) {",
        f'  sprintf("{census.API}/%d/{cfg["survey"]}?get=group(%s)&for=county:{place["county"]}'
        f'&in=state:{place["state"]}", year, table)',
        "}",
        "",
        f'job <- jsonlite::fromJSON(r"---({json.dumps(job)})---", simplifyVector = FALSE)',
        "",
        "job_num <- function(x) as.numeric(unlist(x))",
        "job_chr <- function(x) as.character(unlist(x))",
        "",
    ]
    return "\n".join(head) + (R_DIR / "rate_common.R").read_text(encoding="utf-8") + "\n" + \
        (R_DIR / "rate_rerun.R").read_text(encoding="utf-8")
