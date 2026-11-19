"""Part S: statistics by R on a saved copy (docs/S3S-DESIGN.md S1 to S3, S7, S8).

Python checks an `analyze` call's kind and options (S1), works out the window of full
months (S2), counts the copy's records into the one table R is given, refuses an analysis
with too little data (TOO_LITTLE) or one whose chart would show a count under the floor
(TOO_FINE), writes the job folder (job.json and input.csv), starts `Rscript
analysis_r/<kind>.R <job folder>` with a list of arguments and a time limit, and reads
result.json. R fits the model and draws the chart. Every word a person reads is
statwords.py's. The table holds counts by month, 0/1 lines, a weekday-by-hour grid or ages:
never an id or a time.
"""
import calendar
import csv
import json
import logging
import math
import os
import re
import subprocess
import urllib.parse
from collections import OrderedDict
from datetime import date
from functools import lru_cache
from pathlib import Path

from . import counting, statwords
from .counting import SpecError

REPO = Path(__file__).resolve().parents[2]
R_DIR = REPO / "analysis_r"
CONFIG = REPO / "config" / "analysis.json"
KINDS = ("trend", "trend_compare", "before_after", "yes_no", "shares", "timing",
         "distribution")
T_KINDS = ("trend", "trend_compare", "before_after")
MADE_UP = ("under_18", "weekend", "night")      # S10 answer 2
NIGHT = (22, 23, 0, 1, 2, 3, 4, 5)              # 10 p.m. to 5:59 a.m.
OPTIONS = {"trend": (), "trend_compare": ("versus",), "before_after": ("date",),
           "yes_no": ("outcome", "factors", "controls"), "shares": ("part",), "timing": (),
           "distribution": ("by",)}
PACKAGES = ("MASS", "ggplot2", "jsonlite", "sandwich")
MISSING_MARK = "MOCO-MISSING-PACKAGE"
R_ENVIRONMENT = ("PATH", "HOME", "LANG", "LC_ALL", "TZ", "TMPDIR")  # S12 item 4b, and R_*
PNG = b"\x89PNG\r\n\x1a\n"

log = logging.getLogger(__name__)


class EngineError(Exception):
    """ENGINE_MISSING or ENGINE_FAILED (S1). `why` is for the log only: it may hold R's own
    message, so it never goes to the person, the model, memory or turn.json."""

    def __init__(self, code, why):
        super().__init__(code)
        self.code, self.why = code, why


@lru_cache(maxsize=None)
def settings(path=None):
    """config/analysis.json (S8)."""
    return json.loads(Path(CONFIG if path is None else path).read_text(encoding="utf-8"))


def _bad(why, **hint):
    return SpecError("BAD_OPTIONS", why=why, **hint)


def _fields(source):
    return {f["name"]: f for f in source["fields"]}


def age_field(source):
    return next((f for f in source["fields"] if f["kind"] == "age"), None)


# ---- the options of S1 ------------------------------------------------------------------

def _item(source, raw, role):
    """An outcome or factor: a flag field's name (or {"field", "is": true|false}), a category
    with one label ({"field", "is": label}), or under_18, weekend, night."""
    fields = _fields(source)
    if isinstance(raw, dict) and set(raw) == {"field"} and raw["field"] in MADE_UP:
        raw = raw["field"]
    if isinstance(raw, str):
        if raw in MADE_UP:
            if raw == "under_18" and age_field(source) is None:
                raise _bad("under_18 needs an age field, and this source has none")
            return {"type": "made", "name": raw}
        f = fields.get(raw)
        if f is not None and f["kind"] == "flag":
            return {"type": "flag", "field": raw, "is": True}
        # S13.7: a bare label ("female") read as {"field": <its field>, "is": <label>} when
        # exactly one category field of the source has that label
        owners = [(c["name"], label) for c in fields.values() if c["kind"] == "category"
                  for label in counting._labels(c) if label.lower() == raw.lower()]
        if len({name for name, _ in owners}) == 1:
            return {"type": "category", "field": owners[0][0], "label": owners[0][1]}
    elif isinstance(raw, dict) and isinstance(raw.get("field"), str):
        f = fields.get(raw["field"])
        keys = set(raw) - {"field"}
        if f is not None and f["kind"] == "flag" and keys == {"is"}:
            value = raw["is"]
            if isinstance(value, str):
                value = {"true": True, "false": False}.get(value.lower(), value)
            if isinstance(value, bool):
                return {"type": "flag", "field": f["name"], "is": value}
        if f is not None and f["kind"] == "category":
            given = raw.get("is") if keys == {"is"} else (
                raw["in"][0] if keys == {"in"} and isinstance(raw["in"], list)
                and len(raw["in"]) == 1 else None)
            labels = {label.lower(): label for label in counting._labels(f)}
            if isinstance(given, str) and given.lower() in labels:
                return {"type": "category", "field": f["name"], "label": labels[given.lower()]}
    raise _bad(f"each {role} is a yes-or-no field's name, a category with one label "
               f'({{"field": "<field>", "is": "<label>"}}), or one of under_18, weekend, night')


def item_field(source, item):
    """The source field an outcome or factor reads (None for weekend and night)."""
    if item["type"] == "made":
        return age_field(source)["name"] if item["name"] == "under_18" else None
    return item["field"]


def _filters(source, raw, role):
    """A filter list inside the options: C5's checks, its errors as BAD_OPTIONS (NOT_ALLOWED
    stays itself: C8.4)."""
    if not isinstance(raw, list) or not raw:
        raise _bad(f"{role} is a list of one or more filters")
    try:
        return counting.check_filters(source, raw)
    except SpecError as e:
        if e.code == "NOT_ALLOWED":
            raise
        raise _bad(f"{role}: " + str(e.hint.get("why") or e.code), **{
            k: v for k, v in e.hint.items() if k != "why"}) from None


def _values(source, flt):
    """The set a filter keeps, to tell whether two groups overlap."""
    name = flt["field"]
    if name == "hour":
        lo, hi = flt["from"], flt["to"]
        return set(range(lo, hi + 1)) if lo <= hi else set(range(lo, 24)) | set(range(hi + 1))
    if name == "weekday" or "in" in flt:
        return set(flt["in"])
    if "is" in flt:
        return {flt["is"]}
    f = _fields(source)[name]
    return set(range(flt.get("from", f["usable"][0]), flt.get("to", f["usable"][1]) + 1))


def check_options(source, spec, kind, raw):
    """S1: the options of `kind`, tidied, or SpecError BAD_OPTIONS (decided before R)."""
    if kind not in KINDS:
        raise _bad(f"kind is one of {', '.join(KINDS)}")
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise _bad("options is an object")
    unknown = sorted(set(raw) - set(OPTIONS[kind]))
    if unknown:
        raise _bad(f"{kind} takes no option {', '.join(unknown)}",
                   allowed=list(OPTIONS[kind]))
    fields = _fields(source)
    filtered = {flt["field"]: flt for flt in spec["filters"]}
    if kind == "trend_compare":
        if "versus" not in raw:
            raise _bad('trend_compare needs "versus": a second filter list')
        versus = _filters(source, raw["versus"], "versus")
        other = {flt["field"]: flt for flt in versus}
        differ = [name for name in filtered if other.get(name) != filtered[name]]
        if set(other) == set(filtered) and not differ:  # S13.8
            raise _bad("versus is the same group as filters: for the trend of one group use "
                       "kind trend")
        if set(other) != set(filtered) or len(differ) != 1:
            raise _bad("the two filter lists must name the same fields and differ in exactly one")
        if _values(source, filtered[differ[0]]) & _values(source, other[differ[0]]):
            raise _bad("the two groups overlap; they must not share a record")
        return {"versus": versus, "field": differ[0]}
    if kind == "before_after":
        when = raw.get("date")
        try:
            if not (isinstance(when, str) and re.fullmatch(r"\d{4}-\d{2}-01", when)):
                raise ValueError
            date.fromisoformat(when)
        except ValueError:
            raise _bad('before_after needs "date": "YYYY-MM-01", the first of a month') from None
        return {"date": when}
    if kind == "yes_no":
        if "outcome" not in raw:
            raise _bad('yes_no needs "outcome"')
        outcome = _item(source, raw["outcome"], "outcome")
        factors = raw.get("factors")
        if not isinstance(factors, list) or not 1 <= len(factors) <= 6:
            raise _bad('yes_no needs "factors": a list of 1 to 6')
        factors = [_item(source, f, "factor") for f in factors]
        controls = raw.get("controls", [])
        if controls is None:
            controls = []
        if not isinstance(controls, list) or len(controls) > 3 or not all(
                c == "year" or (isinstance(c, str) and fields.get(c, {}).get("kind") == "category")
                for c in controls):
            raise _bad('"controls" is a list of 0 to 3 category fields or "year"')
        items = [outcome] + factors
        if len({json.dumps(i, sort_keys=True) for i in items}) != len(items) or \
                len(set(controls)) != len(controls):
            raise _bad("the outcome, the factors and the controls are each named once")
        outcome_field = item_field(source, outcome) or outcome.get("name")
        if any((item_field(source, f) or f.get("name")) == outcome_field for f in factors):
            raise _bad("a factor cannot use the outcome's field")
        if set(controls) & {item_field(source, i) for i in items}:
            raise _bad("a control cannot be the outcome's or a factor's field")
        for i in items:
            flt = filtered.get(item_field(source, i) or "")
            if flt is not None and i["type"] != "made" and (
                    "is" in flt or len(flt.get("in", [])) == 1):
                raise _bad("the filters already fix the field of the outcome or a factor")
        return {"outcome": outcome, "factors": factors, "controls": list(controls)}
    if kind == "shares":
        if "part" not in raw:
            raise _bad('shares needs "part": one or more filters added to the spec')
        part = _filters(source, raw["part"], "part")
        if {flt["field"] for flt in part} & set(filtered):
            raise _bad('shares: the part must not filter a field that filters already limit. '
                       'For "the share of X among all records" send filters [] and options '
                       '{"part": [the filters of X]}')  # S13.5
        return {"part": part}
    if kind == "distribution":
        if age_field(source) is None:
            raise _bad("this source has no age field")
        by = raw.get("by")
        if by is not None and not (isinstance(by, str)
                                   and fields.get(by, {}).get("kind") in ("category", "flag")):
            raise _bad('"by" names the field of the groups whose ages are compared, such as '
                       '"gender" (a category or yes-or-no field); leave it out for everyone')
        return {"by": by}
    return {}


# ---- the window (S2) -----------------------------------------------------------------------

def _next(y, m):
    return (y + 1, 1) if m == 12 else (y, m + 1)


def _prev(y, m):
    return (y - 1, 12) if m == 1 else (y, m - 1)


def _last_day(y, m):
    return date(y, m, calendar.monthrange(y, m)[1])


def window(source, copy, period, drop):
    """The full months a model uses: from the later of coverage_start and the period's start
    to the earlier of the period's end and the copy's last full month less `drop` months."""
    first_day, end_day, _ = counting.bounds(period)
    start = max(first_day, date.fromisoformat(source["coverage_start"]))
    first = (start.year, start.month) if start.day == 1 else _next(start.year, start.month)
    end_day = min(end_day, copy.newest_day)
    end = (end_day.year, end_day.month)
    if end_day != _last_day(*end):
        end = _prev(*end)
    newest = copy.newest_day
    last = (newest.year, newest.month)
    if newest != _last_day(*last):
        last = _prev(*last)
    for _ in range(drop):
        last = _prev(*last)
    out, ym = [], first
    while ym <= min(end, last):
        out.append(ym)
        ym = _next(*ym)
    return out


# ---- the table R is given, and the refusals before R ------------------------------------------

def _hidden(n, floor):
    return 1 <= n < floor


def _too_fine(values, floor):
    """S10 answer 6: more than half of the points that are not 0 would be left empty."""
    nonzero = [n for n in values if n]
    return 2 * sum(1 for n in nonzero if _hidden(n, floor)) > len(nonzero)


def _item_value(source, item, row, day, hour):
    if item["type"] == "made":
        if item["name"] == "under_18":
            return int(int(row[age_field(source)["name"]]) < 18)
        if item["name"] == "weekend":
            return int(day.weekday() >= 5)
        return int(hour in NIGHT)
    f = _fields(source)[item["field"]]
    if item["type"] == "flag":
        return int((row[f["name"]] == f["yes_raw"]) is item["is"])
    return int(f["values"][row[f["name"]]] == item["label"])


def used_fields(source, spec, kind, options):
    """The source fields the analysis reads, in the source file's order: a record without a
    usable value in one of them is left out (C2)."""
    names = {flt["field"] for flt in spec["filters"]}
    if kind == "yes_no":
        names |= {item_field(source, i) for i in [options["outcome"], *options["factors"]]}
        names |= {c for c in options["controls"] if c != "year"}
    elif kind == "shares":
        names |= {flt["field"] for flt in options["part"]}
    elif kind == "distribution":
        names |= {age_field(source)["name"], options["by"]}
    return [f["name"] for f in source["fields"] if f["name"] in names]


def prepare(source, copy, rows, spec, kind, options, cfg):
    """Count the copy into R's table (S2) and refuse what has too little data (TOO_LITTLE,
    checked first) or would chart a hidden count (TOO_FINE): SpecError, before R."""
    floor = source["floor"]
    months = window(source, copy, spec["period"], cfg["drop_newest_months"])
    if not months:
        raise SpecError("OUT_OF_COVERAGE", why="no full month of this period can be used: the "
                        "newest months of a copy are left out",
                        covers=counting.covers_text(source, copy))
    first_day, last_day = date(*months[0], 1), _last_day(*months[-1])
    fields = _fields(source)
    used = used_fields(source, spec, kind, options)
    groups = [spec["filters"]] + ([options["versus"]] if kind == "trend_compare" else [])
    tests = [[(flt, fields.get(flt["field"])) for flt in g] for g in groups]
    index = {ym: i for i, ym in enumerate(months)}
    left = OrderedDict((name, 0) for name in used)
    counts = [[0] * len(months) for _ in groups]
    base, part = [0] * len(months), [0] * len(months)
    cells = [[0] * 24 for _ in range(7)]
    lines, ages = [], []
    for row in rows:
        when = row.get(source["time_field"])
        try:
            day, hour = date.fromisoformat(when[:10]), int(when[11:13])
        except (TypeError, ValueError):
            continue
        if not first_day <= day <= last_day:
            continue
        gaps = [name for name in used if not counting._placeable(row, fields[name])]
        group = next((g for g, test in enumerate(tests) if all(
            counting._matches(row, flt, f, day, hour) for flt, f in test
            if f is None or f["name"] not in gaps)), None)
        if group is None:
            continue
        if gaps:
            left[gaps[0]] += 1  # S10 answer 16: once, under its first missing field
            continue
        i = index[(day.year, day.month)]
        counts[group][i] += 1
        if kind == "shares":
            base[i] += 1
            part[i] += all(counting._matches(row, flt, fields.get(flt["field"]), day, hour)
                           for flt in options["part"])
        elif kind == "timing":
            cells[day.weekday()][hour] += 1
        elif kind == "yes_no":
            lines.append([_item_value(source, it, row, day, hour)
                          for it in [options["outcome"], *options["factors"]]]
                         + [str(day.year) if c == "year" else fields[c]["values"][row[c]]
                            for c in options["controls"]])
        elif kind == "distribution":
            by = fields.get(options["by"]) if options["by"] else None
            label = None if by is None else (
                (by["yes"] if row[by["name"]] == by["yes_raw"] else by["no"])
                if by["kind"] == "flag" else by["values"][row[by["name"]]])
            ages.append((int(row[age_field(source)["name"]]), label))
    prep = {"months": months, "records": sum(map(sum, counts)), "left_out": dict(left),
            "chart_points": None}
    builder = {"trend": _t_table, "trend_compare": _t_table, "before_after": _t_table,
               "yes_no": _l_table, "shares": _s_table, "timing": _timing_table,
               "distribution": _ages_table}[kind]
    builder(prep, source, kind, options, cfg, floor, counts=counts, base=base, part=part,
            cells=cells, lines=lines, ages=ages)
    return prep


def _little(rule, cfg):
    return SpecError("TOO_LITTLE", rule=rule, why=statwords.too_little_line(rule, cfg))


def _fine(floor):
    return SpecError("TOO_FINE", why=statwords.too_fine_line(floor))


def _t_table(prep, source, kind, options, cfg, floor, *, counts, **_):
    months = prep["months"]
    if len(months) < cfg["min_months"]:
        raise _little("months", cfg)
    if any(sum(c) < cfg["min_records"] for c in counts):  # S10 answer 13: each group
        raise _little("records", cfg)
    if kind == "before_after":
        when = date.fromisoformat(options["date"])
        ym = (when.year, when.month)
        if not months[0] <= ym <= months[-1]:  # S10 answer 12
            raise _bad("the date must lie inside the months used, "
                       f"{statwords.month_text(months[0])} to "
                       f"{statwords.month_text(months[-1])}")
        before = sum(1 for m in months if m < ym)
        if min(before, len(months) - before) < cfg["min_months_each_side"]:
            raise _little("sides", cfg)
        # S12 item 4c: with 12 months or fewer on both sides, the months from the date on are
        # the time in years less a function of the month of the year, so the step cannot be
        # told apart from the trend and the 11 month indicators by any data (R's glm marks
        # it NA; kit-log/raw/S3S-R3-B-notes.txt). Refused before R.
        if max(before, len(months) - before) <= 12:
            raise _little("step_apart", cfg)
    quarter = any(_hidden(n, floor) for c in counts for n in c)
    if quarter:  # S6: drawn by quarter; S10 answers 6 and 17: TOO_FINE over the whole chart
        quarters = [sum(c[i:i + 3]) for c in counts for i in range(0, len(c), 3)]
        if _too_fine(quarters, floor):
            raise _fine(floor)
    prep["chart_points"] = "quarter" if quarter else "month"
    header = ["year", "month", "days"] + (["group"] if kind == "trend_compare" else []) + ["n"]
    prep["header"], prep["rows"] = header, [
        [y, m, calendar.monthrange(y, m)[1]] + ([g] if kind == "trend_compare" else []) + [c[i]]
        for g, c in enumerate(counts) for i, (y, m) in enumerate(months)]
    prep["groups"] = [sum(c) for c in counts]
    prep["yearly"] = [[y, sum(c[i] for i, (yy, _) in enumerate(months) if yy == y)]
                      for y in sorted({y for y, _ in months}) for c in counts[:1]]


def _l_table(prep, source, kind, options, cfg, floor, *, lines, **_):
    yes = sum(line[0] for line in lines)
    no = len(lines) - yes
    if min(yes, no) < cfg["min_cases"]:
        raise _little("cases", cfg)
    k = len(options["factors"])
    for i in range(1, k + 1):
        if len({line[i] for line in lines}) < 2:
            raise _bad("a factor takes one value only in this selection, so nothing can be "
                       "compared")
    levels = []
    for j, c in enumerate(options["controls"]):
        present = {line[1 + k + j] for line in lines}
        order = [str(y) for y in sorted({y for y, _ in prep["months"]})] if c == "year" else \
            counting._labels(_fields(source)[c])
        levels.append([v for v in order if v in present])
        if len(levels[-1]) < 2:
            raise _bad("a control takes one value only in this selection")
    # S10 answer 3: every indicator column of a factor or a control is one coefficient;
    # the intercept is not counted.
    coefficients = k + sum(len(lv) - 1 for lv in levels)
    if min(yes, no) / coefficients < cfg["per_coefficient"]:
        raise _little("per_coefficient", cfg)
    prep["header"] = ["outcome"] + [f"factor{i}" for i in range(1, k + 1)] + \
        [f"control{j}" for j in range(1, len(options["controls"]) + 1)]
    prep["rows"], prep["levels"] = lines, levels
    prep["records"], prep["yes"], prep["coefficients"] = len(lines), yes, coefficients


def _s_table(prep, source, kind, options, cfg, floor, *, base, part, **_):
    months = prep["months"]
    years = OrderedDict()
    for (y, _), b, p in zip(months, base, part):
        years.setdefault(y, [0, 0])
        years[y][0] += b
        years[y][1] += p
    if len(years) < 2:  # S14: a share followed across years needs two years at least
        raise _little("years", cfg)
    if any(b < cfg["min_base_year"] for b, _ in years.values()):
        raise _little("base_year", cfg)
    if any(_hidden(p, floor) for _, p in years.values()):  # S10 answer 6: the share gives it away
        raise _fine(floor)
    prep["header"] = ["year", "month", "base", "part"]
    prep["rows"] = [[y, m, b, p] for (y, m), b, p in zip(months, base, part)]
    prep["records"] = sum(base)


def _timing_table(prep, source, kind, options, cfg, floor, *, cells, **_):
    flat = [n for day in cells for n in day]
    if not sum(flat):  # ponytail: no rule names an empty selection; refused as too little
        raise _little("records", cfg)
    if _too_fine(flat, floor):
        raise _fine(floor)
    prep["header"] = ["weekday", "hour", "n"]
    prep["rows"] = [[d, h, cells[d][h]] for d in range(7) for h in range(24)]
    prep["cells"] = cells


def _ages_table(prep, source, kind, options, cfg, floor, *, ages, **_):
    by = options["by"]
    f = _fields(source).get(by) if by else None
    labels = ([None] if f is None else
              [f["yes"], f["no"]] if f["kind"] == "flag" else counting._labels(f))
    if any(sum(1 for _, g in ages if g == label) < cfg["min_ages"] for label in labels):
        raise _little("ages", cfg)
    usable = age_field(source)["usable"]
    low = usable[0] - usable[0] % 2
    bins = [sum(1 for a, g in ages if g == label and b <= a < b + 2)
            for label in labels for b in range(low, usable[1] + 1, 2)]
    if _too_fine(bins, floor):
        raise _fine(floor)
    prep["header"] = ["age"] + (["group"] if f is not None else [])
    prep["rows"] = [[a] + ([g] if f is not None else []) for a, g in ages]
    prep["labels"] = labels if f is not None else []
    prep["records"] = len(ages)


# ---- the job folder, R and its answer (S2, S3) ------------------------------------------------

def write_job(folder, job, prep):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "job.json").write_text(json.dumps(job, indent=2) + "\n", encoding="utf-8")
    with open(folder / "input.csv", "w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(prep["header"])
        writer.writerows(prep["rows"])


def r_environment():
    """S12 item 4b: what R is started with: PATH, HOME, LANG, LC_ALL, TZ, TMPDIR and the
    variables whose name starts with R_; nothing else of the agent's environment (its keys)."""
    return {k: v for k, v in os.environ.items() if k in R_ENVIRONMENT or k.startswith("R_")}


def run_r(rscript, kind, folder, seconds, read=None):
    """S2: `Rscript analysis_r/<kind>.R <job folder>`, a list of arguments, no shell, a time
    limit. Returns result.json, checked (by `read`, else read_result); raises EngineError."""
    args = [str(rscript), str(R_DIR / f"{kind}.R"), str(folder)]
    try:
        done = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=seconds, env=r_environment())
    except subprocess.TimeoutExpired:
        raise EngineError("ENGINE_FAILED", f"R ran over {seconds} seconds and was stopped") \
            from None
    except OSError as e:  # no such file, not executable
        raise EngineError("ENGINE_MISSING", f"Rscript could not be started ({type(e).__name__}: "
                                            f"{rscript})") from None
    said = (done.stderr or "").strip()[-2000:]
    if done.returncode != 0:
        if MISSING_MARK in said:
            raise EngineError("ENGINE_MISSING", said)
        raise EngineError("ENGINE_FAILED", f"R ended with exit code {done.returncode}: {said}")
    return (read or read_result)(folder, kind)


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _estimate_ok(e, name):
    return (isinstance(e, dict) and e.get("name") == name and isinstance(e.get("clear"), bool)
            and all(_finite(e.get(k)) for k in ("estimate", "low", "high")))


def read_result(folder, kind):
    """result.json in S3's shape for `kind`, and a chart.png; else ENGINE_FAILED."""
    folder = Path(folder)
    try:
        result = json.loads((folder / "result.json").read_text(encoding="utf-8"))
        chart = (folder / "chart.png").read_bytes()[:8]
    except (OSError, ValueError):
        raise EngineError("ENGINE_FAILED", "R left no readable result.json or chart.png") \
            from None
    job = json.loads((folder / "job.json").read_text(encoding="utf-8"))
    want = {"trend": ["trend"], "trend_compare": ["difference"],
            "before_after": ["step", "bend"], "shares": ["sharetrend"], "timing": [],
            "distribution": [],
            "yes_no": [f"odds{i}" for i in range(1, len(job.get("factors", [])) + 1)]}[kind]
    estimates = result.get("estimates") if isinstance(result, dict) else None
    ok = (chart == PNG and isinstance(result, dict) and result.get("kind") == kind
          and isinstance(result.get("model"), str) and isinstance(estimates, list)
          and len(estimates) == len(want)
          and all(_estimate_ok(e, n) for e, n in zip(estimates, want)))
    if ok and kind in T_KINDS:
        ok = _finite(result.get("fit_ratio")) and result.get("chart_points") in ("month",
                                                                                 "quarter")
    if ok and kind == "trend_compare":
        own = result.get("own")
        ok = isinstance(own, list) and len(own) == 2 and all(
            _estimate_ok(e, n) and isinstance(e.get("model"), str)  # S12 item 1: each its own
            for e, n in zip(own, ["trend_a", "trend_b"]))
    if ok and kind == "shares":
        ok = isinstance(result.get("years"), list) and bool(result["years"]) and all(
            isinstance(y, dict) and all(_finite(y.get(k)) for k in ("year", "share", "low", "high"))
            for y in result["years"])
    if ok and kind == "distribution":
        groups = result.get("groups")
        ok = isinstance(groups, list) and len(groups) == max(1, len(job.get("groups", []))) \
            and all(isinstance(g, dict) and all(_finite(g.get(k)) for k in ("median", "q1", "q3"))
                    for g in groups)
    if not ok:
        raise EngineError("ENGINE_FAILED", "R's result.json is not in the shape S3 asks for")
    return result


def check_engine(rscript):
    """S8: (every package loads, the lines to print): the R version and each package."""
    code = ('cat(R.version.string, "\\n"); for (p in c(%s)) cat(p, if (requireNamespace(p, '
            'quietly = TRUE)) paste("loads, version", as.character(utils::packageVersion(p))) '
            'else "is MISSING", "\\n")' % ", ".join(f'"{p}"' for p in PACKAGES))
    try:
        done = subprocess.run([str(rscript), "-e", code], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=settings()["seconds"],
                              env=r_environment())
    except subprocess.TimeoutExpired:
        return False, [f"R ({rscript}) did not answer within {settings()['seconds']} seconds."]
    except OSError as e:
        return False, [f"R was not found: {rscript} could not be started ({type(e).__name__}). "
                       f"Set MOCO_RSCRIPT or install R."]
    lines = [line.rstrip() for line in done.stdout.splitlines() if line.strip()]
    ok = done.returncode == 0 and len(lines) == 1 + len(PACKAGES) and \
        not any("MISSING" in line for line in lines)
    return ok, lines or [f"R gave no answer (exit code {done.returncode})."]


# ---- job.json, and the script anyone can run (S2, S7) -------------------------------------------

def _field_for_script(f):
    keep = {"age": ("usable",), "category": ("values",), "flag": ("yes_raw", "no_raw", "yes", "no"),
            "key": ()}[f["kind"]]
    return {"name": f["name"], "kind": f["kind"], **{k: f[k] for k in keep}}


def job_for(source, copy, spec, kind, options, prep, cfg, words):
    """What R is told (S2): the kind, its labels, the window, the floor; and, under "data",
    what the script of S7 needs to build the same table from the public records: the fields
    as the agent reads them, the filters, the months and the options. No record."""
    months = prep["months"]
    fields = _fields(source)
    used = used_fields(source, spec, kind, options)
    job = {"kind": kind, "read_as": words["read_as"], "source_title": source["title"],
           "unit_many": source["unit"]["many"], "copy_date": counting.day_text(copy.day),
           "floor": source["floor"], "z": cfg["z"],
           "window": {"first": statwords.month_text(months[0]),
                      "last": statwords.month_text(months[-1]), "months": len(months),
                      "first_year": months[0][0]}}
    data = {"time_field": source["time_field"], "first_day": f"{months[0][0]:04d}-"
            f"{months[0][1]:02d}-01", "last_day": _last_day(*months[-1]).isoformat(),
            "months": [list(ym) for ym in months], "fields": [_field_for_script(fields[n])
                                                               for n in used],
            "groups": [spec["filters"]] + ([options["versus"]] if kind == "trend_compare" else []),
            "age_field": (age_field(source) or {}).get("name")}
    if kind in T_KINDS:
        job["chart_points"] = prep["chart_points"]
    if kind == "trend_compare":
        job["labels"] = {"a": words["labels"]["a_label"], "b": words["labels"]["b_label"]}
    if kind == "before_after":
        when = date.fromisoformat(options["date"])
        job["date"] = {"year": when.year, "month": when.month, "text": words["date_month"]}
    if kind == "yes_no":
        job["outcome"], job["factors"] = words["outcome_label"], words["factor_labels"]
        job["controls"] = [{"column": f"control{j}", "dimension": dim, "levels": levels}
                           for j, (dim, levels) in enumerate(zip(
                               statwords.control_words(source, options["controls"]),
                               prep["levels"]), 1)]
        data.update(outcome=options["outcome"], factors=options["factors"],
                    controls=[{"column": f"control{j}", "field": c}
                              for j, c in enumerate(options["controls"], 1)])
    if kind == "shares":
        job["part"], data["part"] = words["part"], options["part"]
    if kind == "distribution":
        job["groups"], job["usable"] = prep["labels"], age_field(source)["usable"]
        by = fields.get(options["by"]) if options["by"] else None
        data["by"] = None if by is None else {"field": by["name"], "kind": by["kind"],
                                              "yes": by.get("yes"), "no": by.get("no")}
    job["data"] = data
    return job


def script_text(source, copy, job):
    """S7: one R file that downloads the same public dataset from the county's address, builds
    the same table, fits the same model with common.R and prints the same estimates. The
    address is written once, on the line `data_url <- "..."`; the script holds no record."""
    data = job["data"]
    tf = data["time_field"]
    (y, m) = data["months"][-1]
    after = f"{y + (m == 12):04d}-{m % 12 + 1:02d}-01"
    query = urllib.parse.urlencode(
        {"$select": ",".join([tf] + [f["name"] for f in data["fields"]]),
         "$where": f"{tf} >= '{data['first_day']}T00:00:00' AND {tf} < '{after}T00:00:00'",
         # ponytail: one request with a high limit, so a saved file can stand in for it; not
         # tried against the county's service from here (no network in this build).
         "$limit": 1000000}, quote_via=urllib.parse.quote)
    packages = "base R, jsonlite" + (", MASS and sandwich" if job["kind"] in T_KINDS else "")
    head = [
        "# The R script of one statistical answer by the Montgomery County criminal justice data",
        "# agent (a university course project, not a county service).",
        f"# It reruns: {job['read_as']}.",
        f"# The agent's numbers came from its copy of {source['title']}, saved on",
        f"# {job['copy_date']} (fingerprint {copy.sha256[:12]}). The county may have corrected",
        "# records since that date, so the last digit can differ.",
        "# It downloads the same public dataset from the county's address below, applies the same",
        "# filters and months, fits the same model and prints the same estimates, one line each:",
        "# <name> <estimate> <low> <high>. It holds no record of the data and saves nothing.",
        f"# It uses {packages}. Run it with: Rscript script.R",
        "# To use a saved copy of the answer instead, point data_url at that file.",
        "",
        f'data_url <- "{source["address"]}?{query}"',
        "",
        f'job <- jsonlite::fromJSON(r"---({json.dumps(job)})---", simplifyVector = FALSE)',
        "",
    ]
    return "\n".join(head) + (R_DIR / "common.R").read_text(encoding="utf-8") + "\n" + \
        (R_DIR / "rerun.R").read_text(encoding="utf-8")
