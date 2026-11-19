"""The truth for the stage 3 Part S tests (docs/S3S-DESIGN.md), recomputed in Python from the
fixture rows (tests/s3s/fixtures/), with no program code: nothing here imports moco_agent
or reads anything under analysis_r/. Brief S3S-A step 5.

- Monthly tables, shares, timing and ages: plain loops and dictionaries.
- The three models of S3, written out by hand from S3 with statsmodels:
  T: negative binomial, log link, exposure the days in the month, on time in years and
     eleven month indicators (January the reference); theta estimated by maximum
     likelihood and then held fixed for the standard errors (as R's MASS::glm.nb does);
     when it does not converge or the spread is not above zero: Poisson with the same
     terms and HC1 standard errors as sandwich computes them (HC0 times n / (n - k)).
     trend_compare (S12 item 1, D-058): each group fitted alone, the difference from the two
     own fits (see _truth_compare); before_after adds an indicator for the
     months from the date on and the time since the date (0 before it).
  L: logistic regression, factors as 0/1, category controls as indicators against their
     most common label.
  S: the share by calendar year with Wilson 95% ranges by formula; logistic regression of
     "matches part" on the year as a number.
  Intervals: Wald 95%, estimate plus or minus 1.959964 standard errors on the model's
  scale, turned into percentages (100 x (exp(b) - 1)) or odds ratios (exp(b)) at the ends.
- The phrases of S4, as regexes (`*_re`), written by hand from S4; the odds, difference
  and bend phrases, the yes_no table line, the hidden line, the partial year, the held
  join, the one line about cause and R1's limits for odds slots written by hand from S11
  (the wording round, brief S3S-R2-A).
- A PNG reader with the standard library (size, colour type, pixels).
- A reader for R's result.json that takes no key names for granted.

READINGS (each is in kit-log/raw/S3S-A-notes.txt):
- Time in years is (year - 2021) + (month - 1) / 12 (the planning chat's sample); the
  origin changes no estimate the tests check.
- The window (S2): full months from the later of coverage_start and the period's start
  (a period starting after the 1st starts at the next month) to the earlier of the
  period's last full month and the copy's last full month minus drop_newest_months. A
  month is full in the copy when the newest record is on or after its last day.
- `trend_compare`: "a" is the spec's own filters, "b" the `versus` filters; the
  difference is b(B) - b(A) of the two own fits (S12 item 1, brief S3S-R3-A; it was the
  product term of one model with both groups), written as 100 x (exp(d) - 1) (S3: intervals
  "turned into percentages at the ends"). `before_after`'s bend is its own term, so.
- L and S use the records of the period as given (S2's full-month window is for count
  models); every L and S case in the tests uses whole years 2021 to 2025, so both
  readings give the same records.
- Options: a flag outcome or factor is its field name (`"adjacent_to_school"`), a
  category with one label is `{"field": "gender", "is": "female"}`, and `"under_18"`,
  `"weekend"`, `"night"` are strings; controls are field names or `"year"`.
"""
import calendar
import json
import math
import re
import zlib
from collections import OrderedDict
from datetime import date
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
MAIN, EDGES = "stats_like", "stats_edges"
SOURCE_IDS = {MAIN: "FIXTURE:stats_like", EDGES: "FIXTURE:stats_edges"}
NEWEST = date(2026, 10, 14)          # the newest record of both fixture sources
DROP_NEWEST_MONTHS = 1               # S2, config/analysis.json to start with
Z = 1.959964                         # S3
FLOOR = 10
# S1's thresholds, written here from the contract (not read from config/analysis.json).
MIN_MONTHS, MIN_RECORDS, MIN_CASES, PER_COEFFICIENT = 24, 100, 100, 10
MIN_BASE_YEAR, MIN_AGES = 100, 30
FIT_BAND = (0.90, 1.10)              # S3 fit note
# S9's tolerances: estimates within 0.01 of a percentage point or 0.001 of an odds ratio;
# interval ends within 0.10 of a percentage point for T and 0.005 of an odds ratio for L and
# S. Shares and their Wilson ends are worked out by formula on both sides: 0.01 points.
TOL_PCT, TOL_OR, TOL_PCT_END, TOL_OR_END, TOL_SHARE = 0.01, 0.001, 0.10, 0.005, 0.01
TOL_RATIO = 0.0005                   # the fit ratio, R against Python (a ratio of sums)

MONTH_NAMES = list(calendar.month_name)[1:]
WEEKDAYS = list(calendar.day_name)


# ---- the fixtures -----------------------------------------------------------------------------

@lru_cache(maxsize=None)
def _source_text(name):
    return (FIXTURES / "sources" / f"{name}.json").read_text(encoding="utf-8")


def source_json(name):
    return json.loads(_source_text(name))


@lru_cache(maxsize=None)
def _rows(name):
    return tuple(json.loads((FIXTURES / "rows" / f"{name}.json").read_text(
        encoding="utf-8"))["rows"])


def fixture_rows(name):
    """The rows the fake transport serves (fresh dicts each time)."""
    return [dict(r) for r in _rows(name)]


def field(src, name):
    (found,) = [f for f in src["fields"] if f["name"] == name]
    return found


# ---- one record ----------------------------------------------------------------------------

def row_time(row, src):
    text = row[src["time_field"]]
    return date.fromisoformat(text[:10]), int(text[11:13])


def usable_age(row, f):
    text = row.get(f["name"])
    if not isinstance(text, str) or not re.fullmatch(r"[0-9]+", text):
        return None
    a = int(text)
    return a if f["usable"][0] <= a <= f["usable"][1] else None


def placeable(row, f):
    if f["kind"] == "age":
        return usable_age(row, f) is not None
    if f["kind"] == "category":
        return row.get(f["name"]) in f["values"]
    if f["kind"] == "flag":
        return row.get(f["name"]) in (f["yes_raw"], f["no_raw"])
    raise AssertionError(f)


def label(row, f):
    if f["kind"] == "age":
        return usable_age(row, f)
    if f["kind"] == "category":
        return f["values"][row[f["name"]]]
    return f["yes"] if row[f["name"]] == f["yes_raw"] else f["no"]


def record_field(name, src):
    """The source field a filter, option or breakdown uses (None for one from the time)."""
    if name in ("weekday", "hour", "year", "month", "weekend", "night"):
        return None
    if name in ("age_band", "under_18"):
        (f,) = [f for f in src["fields"] if f["kind"] == "age"]
        return f
    return field(src, name)


def matches(row, flt, src):
    name = flt["field"]
    day, hour = row_time(row, src)
    if name == "weekday":
        return WEEKDAYS[day.weekday()] in flt["in"]
    if name == "hour":
        lo, hi = flt["from"], flt["to"]
        return lo <= hour <= hi if lo <= hi else hour >= lo or hour <= hi
    f = field(src, name)
    value = label(row, f)
    if f["kind"] == "age":
        return ((flt.get("from") is None or value >= flt["from"])
                and (flt.get("to") is None or value <= flt["to"]))
    if f["kind"] == "flag":
        return (value == f["yes"]) is bool(flt["is"])
    return value in ([flt["is"]] if "is" in flt else list(flt["in"]))


# ---- periods and the window (C5, S2) ----------------------------------------------------------

def last_day(y, m):
    return date(y, m, calendar.monthrange(y, m)[1])


def period_bounds(period):
    if "years" in period:
        ys = sorted(period["years"])
        return date(ys[0], 1, 1), date(ys[-1], 12, 31)
    if "year" in period:
        y = period["year"]
        if "months" in period:
            return date(y, period["months"]["from"], 1), last_day(y, period["months"]["to"])
        return date(y, 1, 1), date(y, 12, 31)
    return date.fromisoformat(period["from"]), date.fromisoformat(period["to"])


def next_month(y, m):
    return (y + 1, 1) if m == 12 else (y, m + 1)


def prev_month(y, m):
    return (y - 1, 12) if m == 1 else (y, m - 1)


def month_range(first, last):
    out, ym = [], first
    while ym <= last:
        out.append(ym)
        ym = next_month(*ym)
    return out


def last_full_month(newest=NEWEST):
    ym = (newest.year, newest.month)
    return ym if newest == last_day(*ym) else prev_month(*ym)


def window(src, period, newest=NEWEST, drop=DROP_NEWEST_MONTHS):
    """S2: the full months a count model uses, as [(year, month)]."""
    first_day, end_day = period_bounds(period)
    start = max(first_day, date.fromisoformat(src["coverage_start"]))
    first = (start.year, start.month) if start.day == 1 else next_month(start.year, start.month)
    end_day = min(end_day, newest)
    end = ((end_day.year, end_day.month) if end_day == last_day(end_day.year, end_day.month)
           else prev_month(end_day.year, end_day.month))
    copy_last = last_full_month(newest)
    for _ in range(drop):
        copy_last = prev_month(*copy_last)
    return month_range(first, min(end, copy_last))


def month_text(ym):
    return f"{MONTH_NAMES[ym[1] - 1]} {ym[0]}"


def years_since_2021(y, m):
    return (y - 2021) + (m - 1) / 12


# ---- selecting records ------------------------------------------------------------------------

def select(name, first_day, end_day, filters=(), uses=()):
    """The records from first_day to end_day that match `filters` and can be placed on
    every field the spec uses (the filters' fields and `uses`), and the left-out counts by
    field. C2/C3: a record is left out only when everything else about it matches."""
    src = source_json(name)
    used = OrderedDict()
    for part in [f["field"] for f in filters] + list(uses):
        f = record_field(part, src)
        if f is not None:
            used[f["name"]] = f
    kept, left = [], _Left((n, 0) for n in used)
    order = [f["name"] for f in src["fields"]]
    # S10 answer 5 with 16: each left-out record once, under its first gap in the order of
    # the source file's fields (added by the planning chat after the automatic check)
    left.once = OrderedDict((n, 0) for n in sorted(
        used, key=lambda n: order.index(n) if n in order else len(order)))
    for row in _rows(name):
        day, _ = row_time(row, src)
        if not first_day <= day <= end_day:
            continue
        gaps = [n for n, f in used.items() if not placeable(row, f)]
        rest = [flt for flt in filters
                if record_field(flt["field"], src) is None
                or record_field(flt["field"], src)["name"] not in gaps]
        if not all(matches(row, flt, src) for flt in rest):
            continue
        if gaps:
            for n in gaps:
                left[n] += 1
            left.once[next(n for n in left.once if n in gaps)] += 1
            continue
        kept.append(row)
    return kept, left


class _Left(OrderedDict):
    """The left-out counts by field (a record with two gaps counts under both), with
    `.once`: the same records counted once each, under their first gap."""
    once = None


def monthly(name, period, filters=()):
    """The window's months, the count in each, the left-out counts."""
    src = source_json(name)
    months = window(src, period)
    rows, left = select(name, date(*months[0], 1), last_day(*months[-1]), filters)
    counts = OrderedDict((ym, 0) for ym in months)
    for row in rows:
        day, _ = row_time(row, src)
        counts[(day.year, day.month)] += 1
    return months, list(counts.values()), left


# ---- the models (S3) -------------------------------------------------------------------------

def _p_value(z):
    return math.erfc(abs(z) / math.sqrt(2))


def _estimate(name, coef, se, scale):
    lo, hi = coef - Z * se, coef + Z * se
    show = (lambda b: 100 * (math.exp(b) - 1)) if scale == "percent" else math.exp
    return {"name": name, "coef": coef, "se": se, "low_coef": lo, "high_coef": hi,
            "p": _p_value(coef / se), "scale": scale,
            "estimate": show(coef), "low": show(lo), "high": show(hi),
            "clear": not (lo <= 0 <= hi)}


def _count_design(rows):
    """rows: dicts with n, days, t, month, and extra 0/1 or numeric terms in `extra`."""
    import numpy as np
    names = ["const", "t"] + [f"month{m}" for m in range(2, 13)]
    extra = list(rows[0]["extra"]) if rows else []
    X = [[1.0, r["t"]] + [1.0 if r["month"] == m else 0.0 for m in range(2, 13)]
         + [float(r["extra"][k]) for k in extra] for r in rows]
    return (np.array([float(r["n"]) for r in rows]), np.array(X),
            np.log(np.array([float(r["days"]) for r in rows])), names + extra)


def fit_counts(rows):
    """T: negative binomial (theta held fixed for the standard errors, as glm.nb), or the
    Poisson fallback with HC1. Returns {"model", "alpha", "params", "bse", "names",
    "fitted"}."""
    import warnings

    import numpy as np
    import statsmodels.api as sm
    y, X, offset, names = _count_design(rows)
    alpha, converged = None, False
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            nb = sm.NegativeBinomial(y, X, offset=offset, loglike_method="nb2")
            res = nb.fit(disp=0, method="bfgs", maxiter=20000)
            res = nb.fit(start_params=res.params, disp=0, method="newton", maxiter=200)
            alpha = float(res.params[-1])
            converged = bool(res.mle_retvals.get("converged", False))
        except Exception:  # noqa: BLE001 - any failure to fit is "did not converge"
            converged = False
    if converged and alpha is not None and alpha > 1e-5:
        glm = sm.GLM(y, X, family=sm.families.NegativeBinomial(alpha=alpha),
                     offset=offset).fit(tol=1e-12, maxiter=200)
        model = "negative binomial"
    else:
        # HC1 as sandwich::vcovHC(type = "HC1") has it: HC0 times n / (n - k). statsmodels'
        # GLM "HC1" leaves that factor out (found by the R cross-check, step 6).
        glm = sm.GLM(y, X, family=sm.families.Poisson(), offset=offset).fit(
            cov_type="HC0", tol=1e-12, maxiter=200)
        model, alpha = "poisson", None
    n_obs, k = X.shape
    scale = math.sqrt(n_obs / (n_obs - k)) if model == "poisson" else 1.0
    return {"model": model, "alpha": alpha, "params": dict(zip(names, glm.params)),
            "bse": {nm: b * scale for nm, b in zip(names, glm.bse)}, "names": names,
            "fitted": list(np.asarray(glm.fittedvalues)), "n": list(y)}


def _rows_for(months, counts, extra=lambda ym: {}):
    return [{"n": n, "days": calendar.monthrange(*ym)[1], "t": years_since_2021(*ym),
             "month": ym[1], "extra": extra(ym)} for ym, n in zip(months, counts)]


def fit_logistic(y, columns):
    """columns: OrderedDict name -> list of 0/1 (const added). Returns params and bse."""
    import warnings

    import numpy as np
    import statsmodels.api as sm
    names = ["const"] + list(columns)
    X = np.column_stack([np.ones(len(y))] + [np.asarray(v, dtype=float)
                                             for v in columns.values()])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = sm.GLM(np.asarray(y, dtype=float), X, family=sm.families.Binomial()).fit(
            tol=1e-12, maxiter=200)
    return dict(zip(names, res.params)), dict(zip(names, res.bse))


def wilson(k, n, z=Z):
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return 100 * (centre - half), 100 * (centre + half)


# ---- the cases the tests use ---------------------------------------------------------------

P5 = {"from": "2021-01-01", "to": "2025-12-31"}   # five whole years: Jan 2021 to Dec 2025
P6 = {"from": "2021-01-01", "to": "2026-10-14"}   # to the newest record: ends Aug 2026 (S2)


def is_(name, value):
    return {"field": name, "is": value}


def in_(name, *labels):
    return {"field": name, "in": list(labels)}


def batch(b):
    return [is_("batch", f"batch {b}")]


SCHOOL, WEAPON = "adjacent_to_school", "weapon"
FEMALE = is_("gender", "female")
SHIFT_B = is_("shift", "shift B")


def district(d):
    return [is_("district", f"district {d}")]


CASES = {
    # T, trend
    "trend_all": dict(kind="trend", source=MAIN, period=P5, filters=[]),
    "trend_d1": dict(kind="trend", source=MAIN, period=P5, filters=district(1)),
    "trend_d2": dict(kind="trend", source=MAIN, period=P5, filters=district(2)),
    "trend_d3": dict(kind="trend", source=MAIN, period=P5, filters=district(3)),
    "trend_all_p6": dict(kind="trend", source=MAIN, period=P6, filters=[]),
    "trend_d4_p6": dict(kind="trend", source=MAIN, period=P6, filters=district(4)),
    "trend_d5_p6": dict(kind="trend", source=MAIN, period=P6, filters=district(5)),
    "trend_fallback": dict(kind="trend", source=EDGES, period=P5, filters=batch("P")),
    "trend_q1": dict(kind="trend", source=EDGES, period=P5, filters=batch("Q1")),
    "trend_r100": dict(kind="trend", source=EDGES, period={"from": "2024-01-01",
                                                           "to": "2025-12-31"},
                       filters=batch("R100")),
    "trend_24": dict(kind="trend", source=MAIN, period={"from": "2024-01-01",
                                                        "to": "2025-12-31"}, filters=[]),
    "trend_23": dict(kind="trend", source=MAIN, period={"from": "2024-02-01",
                                                        "to": "2025-12-31"}, filters=[]),
    # S2's window: before coverage_start; a period starting and ending inside a month; a
    # period ending with the copy's newest full month (September 2026), which is dropped
    "trend_coverage": dict(kind="trend", source=MAIN, period={"from": "2019-01-01",
                                                              "to": "2025-12-31"}, filters=[]),
    "trend_mid": dict(kind="trend", source=MAIN, period={"from": "2021-01-15",
                                                         "to": "2025-12-15"}, filters=[]),
    "trend_sep": dict(kind="trend", source=MAIN, period={"from": "2024-01-01",
                                                         "to": "2026-09-30"}, filters=[]),
    "trend_female": dict(kind="trend", source=MAIN, period=P5, filters=[FEMALE]),
    "trend_r099": dict(kind="trend", source=EDGES, period={"from": "2024-01-01",
                                                           "to": "2025-12-31"},
                       filters=batch("R099")),
    # T with a group
    "compare_school": dict(kind="trend_compare", source=MAIN, period=P5,
                           filters=[is_(SCHOOL, True)],
                           options={"versus": [is_(SCHOOL, False)]}),
    "compare_school_rev": dict(kind="trend_compare", source=MAIN, period=P5,
                               filters=[is_(SCHOOL, False)],
                               options={"versus": [is_(SCHOOL, True)]}),
    "compare_gender": dict(kind="trend_compare", source=MAIN, period=P5, filters=[FEMALE],
                           options={"versus": [is_("gender", "male")]}),
    "compare_weapon": dict(kind="trend_compare", source=MAIN, period=P5,
                           filters=[is_(WEAPON, True)],
                           options={"versus": [is_(WEAPON, False)]}),
    # T with a step
    "ba_d6": dict(kind="before_after", source=MAIN, period=P5, filters=district(6),
                  options={"date": "2023-07-01"}),
    "ba_d7": dict(kind="before_after", source=MAIN, period=P5, filters=district(7),
                  options={"date": "2023-07-01"}),
    "ba_d2": dict(kind="before_after", source=MAIN, period=P5, filters=district(2),
                  options={"date": "2022-07-01"}),
    # L
    "yn_main": dict(kind="yes_no", source=MAIN, period=P5, filters=[],
                    options={"outcome": SCHOOL, "factors": [WEAPON, FEMALE, SHIFT_B],
                             "controls": ["district"]}),
    "yn_nocontrol": dict(kind="yes_no", source=MAIN, period=P5, filters=[],
                         options={"outcome": SCHOOL, "factors": [WEAPON, FEMALE, SHIFT_B],
                                  "controls": []}),
    "yn_u18": dict(kind="yes_no", source=MAIN, period=P5, filters=[],
                   options={"outcome": SCHOOL, "factors": ["under_18", "weekend"],
                            "controls": ["district"]}),
    "yn_plain": dict(kind="yes_no", source=MAIN, period=P5, filters=[],
                     options={"outcome": SCHOOL, "factors": [WEAPON, SHIFT_B],
                              "controls": ["district"]}),
    "yn_k110": dict(kind="yes_no", source=EDGES, period=P5, filters=batch("K110"),
                    options={"outcome": SCHOOL, "factors": [WEAPON, SHIFT_B],
                             "controls": ["zone"]}),
    # S
    "sh_school": dict(kind="shares", source=MAIN, period=P5, filters=[],
                      options={"part": [is_(SCHOOL, True)]}),
    "sh_noschool": dict(kind="shares", source=MAIN, period=P5, filters=[],
                        options={"part": [is_(SCHOOL, False)]}),
    "sh_shift": dict(kind="shares", source=MAIN, period=P5, filters=[],
                     options={"part": [SHIFT_B]}),
    "sh_s100": dict(kind="shares", source=EDGES, period=P5, filters=batch("S100"),
                    options={"part": [is_(SCHOOL, True)]}),
    # counts only
    "timing": dict(kind="timing", source=MAIN, period=P5, filters=[]),
    "ages": dict(kind="distribution", source=MAIN, period=P5, filters=[]),
    "ages_gender": dict(kind="distribution", source=MAIN, period=P5, filters=[],
                        options={"by": "gender"}),
    "ages_d30": dict(kind="distribution", source=EDGES, period=P5, filters=batch("D30"),
                     options={"by": "gender"}),
}


def case(name):
    c = dict(CASES[name])
    c.setdefault("options", {})
    return c


def analyze_arguments(name, *, source=True, **change):
    """The arguments of an `analyze` call for a case (S1)."""
    c = case(name)
    c.update(change)
    out = {"kind": c["kind"]}
    if source:
        out["source"] = SOURCE_IDS[c["source"]]
    out["period"] = c["period"]
    out["filters"] = c["filters"]
    if c["options"]:
        out["options"] = c["options"]
    return out


# ---- truth for each kind -----------------------------------------------------------------------

def _what_fields(filters):
    return [f["field"] for f in filters]


@lru_cache(maxsize=None)
def truth(name):
    """Everything the tests expect of one case, recomputed from the fixture rows."""
    c = case(name)
    return {"trend": _truth_trend, "trend_compare": _truth_compare,
            "before_after": _truth_before_after, "yes_no": _truth_yes_no,
            "shares": _truth_shares, "timing": _truth_timing,
            "distribution": _truth_distribution}[c["kind"]](c)


def _yearly(months, counts):
    out = OrderedDict()
    for (y, _), n in zip(months, counts):
        out[y] = out.get(y, 0) + n
    return out


def _truth_trend(c):
    months, counts, left = monthly(c["source"], c["period"], c["filters"])
    fit = fit_counts(_rows_for(months, counts))
    est = _estimate("trend", fit["params"]["t"], fit["bse"]["t"], "percent")
    last6 = slice(len(months) - 6, len(months))
    ratio = sum(fit["n"][last6]) / sum(fit["fitted"][last6])
    return {"kind": "trend", "model": fit["model"], "alpha": fit["alpha"], "months": months,
            "counts": counts, "records": sum(counts), "left_out": dict(left), "left_once": dict(left.once),
            "estimates": [est], "trend": est, "fit_ratio": ratio,
            "fit_line": not FIT_BAND[0] <= ratio <= FIT_BAND[1],
            "yearly": _yearly(months, counts), "fit": fit}


def _truth_compare(c):
    """S12 item 1 (approved, D-058; brief S3S-R3-A step 3): no third model. Each group is
    fitted alone (the fits whose yearly change the table shows); the difference is, on the
    model's scale, b(B) minus b(A), its standard error the square root of se(A) squared plus
    se(B) squared, then S3's 95% Wald interval and verdict. The fit ratio is the two groups'
    last six months together over what their two own fits expected. Each group names its
    own model (one may fall back to Poisson: compare_school's group a does)."""
    months, a, left_a = monthly(c["source"], c["period"], c["filters"])
    _, b, left_b = monthly(c["source"], c["period"], c["options"]["versus"])
    fits = {"a": fit_counts(_rows_for(months, a)), "b": fit_counts(_rows_for(months, b))}
    own = {k: _estimate(f"trend_{k}", f["params"]["t"], f["bse"]["t"], "percent")
           for k, f in fits.items()}
    est = _estimate("difference", fits["b"]["params"]["t"] - fits["a"]["params"]["t"],
                    math.hypot(fits["a"]["bse"]["t"], fits["b"]["bse"]["t"]), "percent")
    last6 = slice(len(months) - 6, len(months))
    ratio = (sum(sum(f["n"][last6]) for f in fits.values())
             / sum(sum(f["fitted"][last6]) for f in fits.values()))
    models = {k: f["model"] for k, f in fits.items()}
    model = models["a"] if models["a"] == models["b"] else f"{models['a']} and {models['b']}"
    return {"kind": "trend_compare", "model": model, "models": models, "months": months,
            "fit_ratio": ratio, "fit_line": not FIT_BAND[0] <= ratio <= FIT_BAND[1],
            "counts": {"a": a, "b": b}, "records": sum(a) + sum(b),
            "left_out": {"a": dict(left_a), "b": dict(left_b)},
            # a record outside both groups for lack of the differing field counts once (S10.16)
            "left_once": dict(left_a.once), "estimates": [est],
            "difference": est, "own": own, "fits": fits}


def _truth_before_after(c):
    months, counts, left = monthly(c["source"], c["period"], c["filters"])
    when = date.fromisoformat(c["options"]["date"])
    t0 = years_since_2021(when.year, when.month)

    def extra(ym):
        after = ym >= (when.year, when.month)
        return {"post": 1 if after else 0,
                "since": years_since_2021(*ym) - t0 if after else 0.0}
    fit = fit_counts(_rows_for(months, counts, extra))
    step = _estimate("step", fit["params"]["post"], fit["bse"]["post"], "percent")
    bend = _estimate("bend", fit["params"]["since"], fit["bse"]["since"], "percent")
    before = sum(1 for ym in months if ym < (when.year, when.month))
    last6 = slice(len(months) - 6, len(months))
    ratio = sum(fit["n"][last6]) / sum(fit["fitted"][last6])
    return {"kind": "before_after", "model": fit["model"], "months": months, "counts": counts,
            "fit_ratio": ratio, "fit_line": not FIT_BAND[0] <= ratio <= FIT_BAND[1],
            "records": sum(counts), "left_out": dict(left), "left_once": dict(left.once), "estimates": [step, bend],
            "step": step, "bend": bend, "date_month": (when.year, when.month),
            "months_before": before, "months_after": len(months) - before,
            "yearly": _yearly(months, counts), "fit": fit}


def _l_value(row, item, src):
    """A factor or outcome as 0/1 (READING of S1's option shapes; see the module text)."""
    if item == "under_18":
        return 1 if usable_age(row, record_field("age", src)) < 18 else 0
    if item == "weekend":
        return 1 if row_time(row, src)[0].weekday() >= 5 else 0
    if isinstance(item, str):  # a flag field
        f = field(src, item)
        return 1 if row[item] == f["yes_raw"] else 0
    f = field(src, item["field"])
    return 1 if label(row, f) == item["is"] else 0


def _l_field(item):
    if item in ("under_18",):
        return "age"
    if item in ("weekend", "night"):
        return None
    return item if isinstance(item, str) else item["field"]


def l_label(item, src):
    """The label a factor or outcome is written with in S4 (the file's label, C6), or None
    where the contract gives none (under_18, weekend, night: asked in QUESTIONS.md)."""
    if item in ("under_18", "weekend", "night"):
        return None
    if isinstance(item, str):
        return field(src, item)["yes"]
    return item["is"]


def _truth_yes_no(c):
    src = source_json(c["source"])
    o = c["options"]
    uses = [x for x in [_l_field(o["outcome"])] + [_l_field(f) for f in o["factors"]]
            + [k for k in o["controls"] if k != "year"] if x]
    first, end = period_bounds(c["period"])
    rows, left = select(c["source"], first, min(end, NEWEST), c["filters"], uses)
    y = [_l_value(r, o["outcome"], src) for r in rows]
    columns = OrderedDict()
    for i, f in enumerate(o["factors"], 1):
        columns[f"factor{i}"] = [_l_value(r, f, src) for r in rows]
    references = {}
    for k in o["controls"]:
        if k == "year":
            values = [str(row_time(r, src)[0].year) for r in rows]
        else:
            values = [label(r, field(src, k)) for r in rows]
        tally = OrderedDict()
        for v in values:
            tally[v] = tally.get(v, 0) + 1
        top = max(tally.values())
        assert list(tally.values()).count(top) == 1, f"a tie for the most common {k}"
        ref = next(v for v, n in tally.items() if n == top)
        references[k] = ref
        for v in sorted(tally, key=_label_order(src, k)):
            if v != ref:
                columns[f"{k}={v}"] = [1 if x == v else 0 for x in values]
    params, bse = fit_logistic(y, columns)
    raw = OrderedDict((f"factor{i}", columns[f"factor{i}"])
                      for i in range(1, len(o["factors"]) + 1))
    for k in o["controls"]:
        raw[k] = ([str(row_time(r, src)[0].year) for r in rows] if k == "year"
                  else [label(r, field(src, k)) for r in rows])
    odds = [_estimate(f"odds{i}", params[f"factor{i}"], bse[f"factor{i}"], "odds")
            for i in range(1, len(o["factors"]) + 1)]
    for est, f in zip(odds, o["factors"]):
        est["label"] = l_label(f, src)
        est["factor"] = f
    yes = sum(y)
    return {"kind": "yes_no", "records": len(rows), "left_out": dict(left), "left_once": dict(left.once), "yes": yes,
            "no": len(y) - yes, "estimates": odds, "odds": odds,
            "outcome_label": l_label(o["outcome"], src), "references": references,
            "coefficients": len(columns), "controls": list(o["controls"]),
            "columns": columns, "raw": raw, "y": y}


def _label_order(src, k):
    if k == "year":
        return lambda v: v
    labels = list(OrderedDict.fromkeys(field(src, k)["values"].values()))
    return labels.index


def _truth_shares(c):
    src = source_json(c["source"])
    first, end = period_bounds(c["period"])
    part = c["options"]["part"]
    rows, left = select(c["source"], first, min(end, NEWEST), c["filters"],
                        [f["field"] for f in part])
    by_year = OrderedDict()
    for r in rows:
        yr = row_time(r, src)[0].year
        hit = all(matches(r, flt, src) for flt in part)
        n, k = by_year.get(yr, (0, 0))
        by_year[yr] = (n + 1, k + hit)
    by_year = OrderedDict(sorted(by_year.items()))
    shares = OrderedDict((yr, {"base": n, "part": k, "share": 100 * k / n,
                               "range": wilson(k, n)}) for yr, (n, k) in by_year.items())
    ys, xs = [], []
    for r in rows:
        ys.append(1 if all(matches(r, flt, src) for flt in part) else 0)
        xs.append(row_time(r, src)[0].year)
    params, bse = fit_logistic(ys, OrderedDict(year=xs))
    est = _estimate("sharetrend", params["year"], bse["year"], "odds")
    return {"kind": "shares", "records": len(rows), "left_out": dict(left), "left_once": dict(left.once), "years": shares,
            "estimates": [est], "sharetrend": est, "y": ys, "year": xs}


def _truth_timing(c):
    src = source_json(c["source"])
    first, end = period_bounds(c["period"])
    rows, left = select(c["source"], first, min(end, NEWEST), c["filters"])
    cells = {(d, h): 0 for d in range(7) for h in range(24)}
    for r in rows:
        day, hour = row_time(r, src)
        cells[(day.weekday(), hour)] += 1
    values = sorted(cells.values())
    top = max(cells, key=cells.get)
    low = min(cells, key=cells.get)
    assert values[-1] > values[-2] and values[0] < values[1], "busiest and quietest are unique"
    return {"kind": "timing", "records": len(rows), "left_out": dict(left), "left_once": dict(left.once), "cells": cells,
            "busiest": top, "busiest_n": cells[top], "quietest": low,
            "quietest_n": cells[low], "estimates": []}


QUANTILE_METHODS = ("inverted_cdf", "averaged_inverted_cdf", "closest_observation",
                    "interpolated_inverted_cdf", "hazen", "weibull", "linear",
                    "median_unbiased", "normal_unbiased")


def age_summary(ages):
    """Median and quartiles, the same under every usual quantile rule (checked)."""
    import numpy as np
    out = []
    for q in (0.5, 0.25, 0.75):
        found = {float(np.quantile(ages, q, method=m)) for m in QUANTILE_METHODS}
        assert len(found) == 1 and float(next(iter(found))).is_integer(), (q, found)
        out.append(int(found.pop()))
    return {"median": out[0], "q1": out[1], "q3": out[2], "n": len(ages)}


def _truth_distribution(c):
    src = source_json(c["source"])
    by = c["options"].get("by")
    first, end = period_bounds(c["period"])
    rows, left = select(c["source"], first, min(end, NEWEST), c["filters"],
                        ["age"] + ([by] if by else []))
    agef = record_field("age", src)
    groups = OrderedDict()
    if by:
        f = field(src, by)
        order = (list(OrderedDict.fromkeys(f["values"].values())) if f["kind"] == "category"
                 else [f["yes"], f["no"]])
        for lab in order:
            groups[lab] = [usable_age(r, agef) for r in rows if label(r, f) == lab]
    else:
        groups[None] = [usable_age(r, agef) for r in rows]
    summaries = OrderedDict((lab, age_summary(a) if len(a) >= MIN_AGES else {"n": len(a)})
                            for lab, a in groups.items())
    bins = OrderedDict()
    for a in (x for v in groups.values() for x in v):
        lo = a - a % 2
        bins[lo] = bins.get(lo, 0) + 1
    return {"kind": "distribution", "records": len(rows), "left_out": dict(left), "left_once": dict(left.once),
            "groups": summaries, "ages": groups, "bins": dict(sorted(bins.items())),
            "estimates": []}


def left_out_parts(name):
    """S10 answers 5 and 16: the left-out counts of a case that are not 0, one per reason, in
    the order of the source file's fields; each record counted once."""
    return [k for k in truth(name)["left_once"].values() if k]


def left_out_records(name):
    """How many distinct records of a case are left out (a record with two gaps counts
    once). Corrected by the planning chat after the automatic check: it was wrong for
    trend_compare (it gave a number below zero)."""
    return sum(left_out_parts(name))


def _left_out_by_difference(name):
    """The first way this was counted, kept as a cross-check for the kinds it is right for
    (not trend_compare): the records that match the period and filters, less those used."""
    c, t = case(name), truth(name)
    if t["kind"] in ("trend", "before_after"):
        months = t["months"]
        first, end = date(*months[0], 1), last_day(*months[-1])
    else:
        first, end = period_bounds(c["period"])
        end = min(end, NEWEST)
    src = source_json(c["source"])
    every = [r for r in _rows(c["source"]) if first <= row_time(r, src)[0] <= end]
    matching = [r for r in every if all(
        (record_field(f["field"], src) is not None and not placeable(r, record_field(
            f["field"], src))) or matches(r, f, src) for f in c["filters"])]
    return len(matching) - t["records"]


# ---- the TOO_LITTLE thresholds of S1, by plain counting ---------------------------------------

def too_little_trend(name, period, filters):
    months, counts, _ = monthly(name, period, filters)
    return len(months) < MIN_MONTHS or sum(counts) < MIN_RECORDS


# ---- the phrases of S4, as regexes -------------------------------------------------------------
#
# S4: "Percentages have one decimal, odds ratios two, with the sign written out (-3.2%)."
# Whether a positive value is written with a "+" and whether "rose by about" / "fell by
# about" / "points higher" / "points lower" take the magnitude or the signed value is not
# said; it is asked in briefs/QUESTIONS.md. Until it is answered, these regexes accept both
# at that one place and nowhere else. A value may be written as any rounding of a number
# within the S9 tolerance of the truth (R's number is the one shown; R and statsmodels may
# differ by that much).

def _candidates(value, decimals, tol):
    unit = 10 ** -decimals
    lo, hi = value - tol, value + tol
    k_min = math.floor(lo / unit + 0.5 - 1e-9)
    k_max = math.floor(hi / unit + 0.5 + 1e-9)
    out = []
    for k in range(k_min, k_max + 1):
        centre = k * unit
        if centre + unit / 2 >= lo - 1e-12 and centre - unit / 2 <= hi + 1e-12:
            out.append(round(centre, decimals))
    return out


def _alt(texts):
    texts = list(OrderedDict.fromkeys(texts))
    return texts[0] if len(texts) == 1 else "(?:" + "|".join(texts) + ")"


def signed_re(value, decimals=1, tol=TOL_PCT):
    """A signed value: `-3.2`; a positive one `4.5` or `+4.5` (asked)."""
    out = []
    for c in _candidates(value, decimals, tol):
        text = f"{abs(c):.{decimals}f}"
        if c < 0 and text.strip("0.") != "":
            out.append(re.escape("-" + text))
        else:
            out.append(r"[+]?" + re.escape(text) if c > 0 else r"[+-]?" + re.escape(text))
    return _alt(out)


def amount_re(value, decimals=1, tol=TOL_PCT):
    """After `rose by about`, `fell by about`, `points higher|lower`: the magnitude, or the
    signed value (asked)."""
    out = []
    for c in _candidates(value, decimals, tol):
        text = re.escape(f"{abs(c):.{decimals}f}")
        out.append((r"[+]?" if c >= 0 else r"-?") + text)
    return _alt(out)


def or_re(value, tol=TOL_OR):
    return _alt(re.escape(f"{c:.2f}") for c in _candidates(value, 2, tol))


def count_text(n, floor=FLOOR):
    return f"fewer than {floor}" if 1 <= n <= floor - 1 else f"{n:,}"


def unit_what(unit_many, what):
    return unit_many + (" " + what if what else "")


def trend_re(t, unit_many, what):
    """{aN.trend}"""
    e = t["trend"]
    first, last = month_text(t["months"][0]), month_text(t["months"][-1])
    ends = (f"{signed_re(e['low'], 1, TOL_PCT_END)}% to "
            f"{signed_re(e['high'], 1, TOL_PCT_END)}%")
    head = re.escape(unit_what(unit_many, what))
    if e["clear"]:
        word = "rose" if e["estimate"] > 0 else "fell"
        return (head + rf" {word} by about {amount_re(e['estimate'])}% a year from "
                + re.escape(f"{first} to {last}") + rf" \(95% range {ends}\)")
    return (head + re.escape(f" showed no clear change from {first} to {last}")
            + rf" \(about {signed_re(e['estimate'])}% a year, 95% range {ends}\)")


def sign_re(value, decimals=1, tol=TOL_PCT):
    """S10 answer 1 as S11 restates it (the wording round's phrases only): below zero `-`,
    above zero `+`, zero `0.0`. Strict: no unsigned positive value."""
    out = []
    for c in _candidates(value, decimals, tol):
        text = f"{abs(c):.{decimals}f}"
        out.append(re.escape(text if float(text) == 0 else ("-" if c < 0 else "+") + text))
    return _alt(out)


def size_re(value, decimals=1, tol=TOL_PCT):
    """S11 item 2: after `above` or `below`, the size with no sign."""
    return _alt(re.escape(f"{abs(c):.{decimals}f}") for c in _candidates(value, decimals, tol))


def level_re(value, tol=TOL_SHARE):
    """A share or a share's range end: a level, never a sign (S10 answer 18)."""
    return _alt(re.escape(f"{c:.1f}") for c in _candidates(value, 1, tol))


def _ratio_ends(e):
    """S11 item 2's range: `95% range <lo>% to <hi>%`, both signed."""
    return (f"95% range {sign_re(e['low'], 1, TOL_PCT_END)}% to "
            f"{sign_re(e['high'], 1, TOL_PCT_END)}%")


RATIO = "the ratio of the two yearly changes"


def difference_re(t, a, b):
    """{aN.difference}, S11 item 2. Clear: `a` and `b` are the `<what>` fragments of the one
    filter that differs; not clear: C6's compare labels (S10 answer 7)."""
    e = t["difference"]
    if e["clear"]:
        word = "above" if e["estimate"] > 0 else "below"
        return (re.escape(f"the yearly trend {b} was about ") + size_re(e["estimate"])
                + re.escape(f"% {word} the yearly trend {a} ({RATIO}; ") + _ratio_ends(e)
                + r"\)")
    return (re.escape(f"there was no clear difference in yearly trend between {a} and {b} "
                      f"({RATIO} was about ") + sign_re(e["estimate"]) + "%, "
            + _ratio_ends(e) + r"\)")


def step_re(t):
    """{aN.step}"""
    e, month = t["step"], month_text(t["date_month"])
    ends = (f"{signed_re(e['low'], 1, TOL_PCT_END)}% to "
            f"{signed_re(e['high'], 1, TOL_PCT_END)}%")
    if e["clear"]:
        word = "higher" if e["estimate"] > 0 else "lower"
        return (re.escape(f"from {month} on, the monthly level was about ")
                + amount_re(e["estimate"])
                + re.escape(f"% {word} than the earlier trend pointed to")
                + rf" \(95% range {ends}\)")
    return (re.escape(f"there was no clear step in {month}") + rf" \(about "
            + signed_re(e["estimate"]) + rf"%, 95% range {ends}\)")


def bend_re(t):
    """{aN.bend}, S11 item 2, clear and not clear."""
    e, month = t["bend"], month_text(t["date_month"])
    if e["clear"]:
        word = "above" if e["estimate"] > 0 else "below"
        return (re.escape(f"after {month} the yearly trend was about ") + size_re(e["estimate"])
                + re.escape(f"% {word} the yearly trend before ({RATIO}; ") + _ratio_ends(e)
                + r"\)")
    return (re.escape(f"there was no clear change in the yearly trend after {month} ({RATIO} "
                      f"was about ") + sign_re(e["estimate"]) + "%, " + _ratio_ends(e) + r"\)")


# S11 item 1: a factor or an outcome is written as C6 writes a filter on that one field and
# label. Written out by hand from C6 and the Part A phrase tests (tests/s3/test_s3_phrases.py:
# "a flag", "a person category alone", "under 18", "weekends", "hours over midnight"), for
# the fixture's fields; `night` is C6's hour filter from 10 pm to 5 am (S10 answer 2).
L_WHAT = {
    SCHOOL: "within 500 feet of a school",
    WEAPON: "with a weapon recorded",
    ("gender", "female"): "of people recorded as female",
    ("shift", "shift B"): "on shift B",
    "under_18": "of people under 18",
    "weekend": "on weekends",
    "night": "between 10 pm and 5 am",
}


def what_of(item):
    """The `<what>` of a factor or outcome (an option as the cases write it)."""
    return L_WHAT[item if isinstance(item, str) else (item["field"], item["is"])]


def _odds_numbers(est):
    return (f"odds ratio {or_re(est['estimate'])}, 95% range "
            f"{or_re(est['low'], TOL_OR_END)} to {or_re(est['high'], TOL_OR_END)}")


def odds_re(est, unit_many, outcome):
    """{aN.odds.<k>}, S11 item 1. `outcome`: the outcome option; the factor is est's."""
    head = re.escape(f"{unit_many} {what_of(est['factor'])} ")
    if est["clear"]:
        word = "higher" if est["estimate"] > 1 else "lower"
        words = f"had {word} odds of being {what_of(outcome)}"
    else:
        words = f"showed no clear difference in the odds of being {what_of(outcome)}"
    return head + re.escape(words) + rf" \({_odds_numbers(est)}\)"


def odds_line_re(est):
    """The yes_no table line, S11 item 1: `<factor what>: odds ratio <or> (95% range <lo> to
    <hi>)`."""
    return (re.escape(f"{what_of(est['factor'])}: odds ratio ") + or_re(est["estimate"])
            + r" \(95% range " + or_re(est["low"], TOL_OR_END) + " to "
            + or_re(est["high"], TOL_OR_END) + r"\)")


def fixed_odds_re(t, unit_many, outcome, held):
    """S11 2d: the fixed rendering of a yes_no result: each odds phrase its own sentence,
    capitalised, and `{aN.held}` joined to the last one with `, `."""
    return (r"\. ".join(cap_re(odds_re(e, unit_many, outcome)) for e in t["odds"])
            + re.escape(f", {held}."))


def held_text(controls_words):
    """{aN.held}: `holding <controls> fixed`, or `with nothing else held fixed`. READING:
    <controls> is the controls' dimension words joined with `and` (district -> district)."""
    return f"holding {join_and(controls_words)} fixed" if controls_words else \
        "with nothing else held fixed"


def year_label(year, months=None):
    """S11 2c and 2g: a year the window (`months`, [(year, month)]) covers only in part is
    written with its months, `2026 (January to September)`; a whole year as `2026`."""
    ms = [m for y, m in months or () if y == year]
    if not months or len(ms) == 12:
        return str(year)
    assert len(ms) > 1, "S11 2c does not say how a year of one month is written"
    return f"{year} ({MONTH_NAMES[ms[0] - 1]} to {MONTH_NAMES[ms[-1] - 1]})"


def yearly_lines(t):
    """The yearly table of trend and before_after, exactly: `<year>: <n>` (S10 answer 9) with
    S11 2c's partial years."""
    return [f"{year_label(y, t['months'])}: {count_text(n)}" for y, n in t["yearly"].items()]


def share_line_re(year, v, months=None):
    """The shares table line (S10 answer 9) with S11 2g: `2026 (January to September): 14.8%
    (95% range 14.0% to 15.8%)`; levels, so no sign."""
    return (re.escape(f"{year_label(year, months)}: ") + level_re(v["share"])
            + r"% \(95% range " + level_re(v["range"][0]) + "% to " + level_re(v["range"][1])
            + r"%\)")


def share_re(t, part_what, months=None):
    """{aN.share}: shares by formula on both sides, so one decimal is exact. With the
    window's `months`, a partial last year is written `in January to September 2026` (S11
    2g; a partial first year is not said, so it is refused here)."""
    ys = list(t["years"])
    p1, p2 = t["years"][ys[0]]["share"], t["years"][ys[-1]]["share"]
    assert year_label(ys[0], months) == str(ys[0]), "S11 2g says nothing of a partial first year"
    last = year_label(ys[-1], months)
    if last != str(ys[-1]):
        last = f"{last[6:-1]} {ys[-1]}"           # `2026 (January to August)` -> `January to August 2026`
    return (re.escape(f"the share {part_what} went from ") + signed_re(p1, 1, TOL_SHARE)
            + re.escape(f"% in {ys[0]} to ") + signed_re(p2, 1, TOL_SHARE)
            + re.escape(f"% in {last}"))


def sharetrend_text(t):
    """{aN.sharetrend}"""
    e = t["sharetrend"]
    if not e["clear"]:
        return "no clear change over the years"
    return f"a clear {'rise' if e['estimate'] > 1 else 'fall'} over the years"


def hour_text(h):
    assert h not in (0, 12), "C6 does not say how 0 and 12 are written"
    return f"{h} am" if h < 12 else f"{h - 12} pm"


def timing_text(t):
    """{aN.timing}"""
    (bd, bh), (qd, qh) = t["busiest"], t["quietest"]
    return (f"the busiest hour was {WEEKDAYS[bd]} at {hour_text(bh)} "
            f"({count_text(t['busiest_n'])}) and the quietest {WEEKDAYS[qd]} at "
            f"{hour_text(qh)} ({count_text(t['quietest_n'])})")


def ages_text(summary, group_label=None):
    """{aN.ages}, one group. READING: ages are whole numbers here (the fixture makes every
    quantile a whole number under every usual rule)."""
    text = (f"the median age was {summary['median']} (the middle half were {summary['q1']} "
            f"to {summary['q3']})")
    return text if group_label is None else f"for {group_label}, {text}"


def join_and(items):
    items = [str(i) for i in items]
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def cap(text):
    return text[:1].upper() + text[1:]


def cap_re(pattern):
    """A phrase regex with its first letter capitalised (the fixed rendering, S4)."""
    first = pattern[0]
    return re.escape(first.upper()) + pattern[1:] if first.isalpha() else pattern


# ---- the fixed lines of S5 -------------------------------------------------------------------

def fit_line_re(ratio):
    q = abs(1 - ratio) * 100
    side = "below" if ratio < 1 else "above"
    return (r"The last six months were about " + _alt(re.escape(f"{c:.1f}") for c in
                                                      _candidates(q, 1, 0.02))
            + re.escape(f"% {side} the trend line, so a straight line describes the recent "
                        f"period poorly."))


BEFORE_AFTER_LINE = "Other things changed over the same months. This shows timing, not cause."


def association_line(unit_many):
    return (f"These are patterns in recorded {unit_many}: what goes with what, not what causes "
            f"what.")


def sensitive_line(unit_many):
    return f"These are counts of {unit_many}, not rates, and they show no cause."


def cause_line(unit_many):
    """S11 2f: on a statistical reply with a sensitive field, this one line replaces the
    association line and the sensitive line."""
    return (f"These are patterns in recorded {unit_many}, not rates: what goes with what, not "
            f"what causes what.")


def hidden_line_re(src):
    """S11 2b: C8.2's line on a statistical reply whose phrase or table holds `fewer than
    10`. C8.2 ends it with the source's `<page>`; S11 2b quotes it with `<address>` (asked in
    briefs/QUESTIONS.md): both are accepted at that one place."""
    return (re.escape(f"Counts under {src['floor']} are not shown here; the county's open data "
                      f"has every record: ")
            + _alt([re.escape(src["page"]), re.escape(src["address"])]) + r"\.")


def r1_limits(k):
    """S11 2i: R1's (sentences, characters) for a reply that fills k `{aN.odds.<n>}` slots."""
    return max(4, k + 2), max(600, 200 * k + 200)


def used_re(n, m, parts=()):
    """S5.4 with S10 answer 5: `(<n> records over <m> months.)` when nothing is left out,
    else one `; <k> not included: <reason>` part for each reason, in the order of the source
    file's fields. `parts`: the counts (one number is one part). The reason is any text
    without brackets or a semicolon."""
    parts = [parts] if isinstance(parts, int) else list(parts)
    head = re.escape(f"({n:,} records over {m} months")
    body = "".join(re.escape(f"; {count_text(k)} not included: ") + r"[^();\n]+"
                   for k in parts if k)
    return head + body + r"\.\)"


COPY_DATE_RE = r"(?:12 November 2026|November 12, 2026|2026-11-12)"


def source_first_re(title, unit_many):
    """C10's first-answer line, ending as S5.7 says for a statistical answer."""
    return (re.escape(f"Source: {title} (county open data), copy of ") + COPY_DATE_RE
            + re.escape(f". A count is of {unit_many}, not people. Want the details and the R "
                        f"script?"))


def source_later_re(title):
    """C18: `(<title>, county open data, copy of <date>.)`."""
    return re.escape(f"({title}, county open data, copy of ") + COPY_DATE_RE + re.escape(".)")


# ---- a PNG, read with the standard library ------------------------------------------------------

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def png_chunks(data):
    assert data[:8] == PNG_SIGNATURE, "not a PNG"
    pos, out = 8, []
    while pos < len(data):
        length = int.from_bytes(data[pos:pos + 4], "big")
        kind = data[pos + 4:pos + 8]
        out.append((kind, data[pos + 8:pos + 8 + length]))
        pos += 12 + length
        if kind == b"IEND":
            break
    return out


def png_header(path):
    """(width, height, bit depth, colour type, interlace) from IHDR."""
    data = Path(path).read_bytes()
    kind, body = png_chunks(data)[0]
    assert kind == b"IHDR", kind
    return (int.from_bytes(body[0:4], "big"), int.from_bytes(body[4:8], "big"), body[8],
            body[9], body[12])


_CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


def png_rows(path):
    """The decoded rows of a non-interlaced PNG, each a bytes of its pixels (palette indices
    for colour type 3), and the bytes per pixel (at least 1)."""
    data = Path(path).read_bytes()
    chunks = png_chunks(data)
    width, height, depth, colour, interlace = png_header(path)
    assert interlace == 0, "an interlaced PNG (not read here)"
    raw = zlib.decompress(b"".join(body for kind, body in chunks if kind == b"IDAT"))
    bits = _CHANNELS[colour] * depth
    bpp = max(1, bits // 8)
    stride = (width * bits + 7) // 8
    rows, prior, pos = [], bytearray(stride), 0
    for _ in range(height):
        kind = raw[pos]
        line = bytearray(raw[pos + 1:pos + 1 + stride])
        pos += 1 + stride
        if kind == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 255
        elif kind == 2:
            for i in range(stride):
                line[i] = (line[i] + prior[i]) & 255
        elif kind == 3:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + prior[i]) >> 1)) & 255
        elif kind == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prior[i]
                c = prior[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        else:
            assert kind == 0, f"unknown PNG filter {kind}"
        rows.append(bytes(line))
        prior = line
    return rows, bpp, bits


def png_distinct_pixels(path, limit=None):
    """How many different pixel values the image holds (stops counting at `limit`)."""
    rows, bpp, bits = png_rows(path)
    seen = set()
    for line in rows:
        if bits >= 8:
            for i in range(0, len(line), bpp):
                seen.add(line[i:i + bpp])
        else:
            seen.update(line)  # palette indices packed below 8 bits: bytes are enough here
        if limit is not None and len(seen) >= limit:
            break
    return len(seen)


def png_pixels(path):
    """Every row's pixel bytes (to compare two images pixel for pixel)."""
    return png_rows(path)[0]


# ---- R's result.json, read without taking key names for granted ---------------------------------

_NAME_KEYS = ("name", "term", "label", "estimate_name", "what")
_EST_KEYS = ("estimate", "est", "value", "coef", "coefficient")
_LOW_KEYS = ("low", "lo", "lower", "conf_low", "ci_low", "lwr", "low95", "lower95")
_HIGH_KEYS = ("high", "hi", "upper", "conf_high", "ci_high", "upr", "high95", "upper95")


def _number(d, keys):
    for k in keys:
        v = d.get(k)
        if isinstance(v, list) and len(v) == 1:
            v = v[0]
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return float(v)
    return None


def result_estimates(result):
    """Every entry of a result.json that looks like an estimate: a dict with a name, an
    estimate and both interval ends (S3's last paragraph), wherever it is nested."""
    out = []

    def walk(node):
        if isinstance(node, dict):
            name = next((node[k] for k in _NAME_KEYS if isinstance(node.get(k), (str, list))),
                        None)
            values = [_number(node, keys) for keys in (_EST_KEYS, _LOW_KEYS, _HIGH_KEYS)]
            if name is not None and None not in values:
                out.append({"name": name if isinstance(name, str) else str(name),
                            "estimate": values[0], "low": values[1], "high": values[2]})
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(result)
    return out


def _shown_forms(value, scale):
    """A value as R may have written it: as shown (percent or odds ratio), or on the model's
    scale (the coefficient), or as a proportion change."""
    forms = [value]
    try:
        if scale == "percent":
            forms += [100 * (math.exp(value) - 1), 100 * value]
        else:
            forms += [math.exp(value)]
    except OverflowError:
        pass
    return forms


def estimate_matches(entry, est, tol_est, tol_end):
    """True when an entry of result.json gives the truth's estimate and interval within S9's
    tolerances, on whichever scale it is written."""
    def close(value, want, tol):
        return any(abs(f - want) <= tol for f in _shown_forms(value, est["scale"]))
    return (close(entry["estimate"], est["estimate"], tol_est)
            and close(entry["low"], est["low"], tol_end)
            and close(entry["high"], est["high"], tol_end))


def tolerances(est, kind):
    """S9's (estimate, interval end) tolerances for one estimate."""
    if est["scale"] == "percent":
        return TOL_PCT, TOL_PCT_END
    return TOL_OR, TOL_OR_END


def find_estimate(entries, est, kind):
    tol_est, tol_end = tolerances(est, kind)
    return [e for e in entries if estimate_matches(e, est, tol_est, tol_end)]


# ---- the fixture's statistical facts (brief step 4's list), checked against the truth ----------

def check_designed():
    """Each statistical fact the tests rely on holds (and is not near an edge where R and
    Python could fall on different sides). Returns a list of lines saying what was checked."""
    lines = []

    def clear(name, est, want_clear, direction=None, nochange=0.0):
        e = truth(name)[est] if isinstance(est, str) else est
        lo, hi = (e["low"], e["high"])
        tol = TOL_PCT_END if e["scale"] == "percent" else TOL_OR_END
        assert e["clear"] is want_clear, (name, e)
        assert abs(lo - nochange) > 3 * tol and abs(hi - nochange) > 3 * tol, (name, e)
        if direction is not None:
            assert (e["estimate"] > nochange) is (direction == "up"), (name, e)
        lines.append(f"{name}.{e['name']}: {e['estimate']:.3f} ({e['low']:.3f} to "
                     f"{e['high']:.3f}) clear={e['clear']}")

    clear("trend_all", "trend", True, "up")
    clear("trend_d1", "trend", True, "up")
    clear("trend_d2", "trend", False)
    clear("trend_d3", "trend", True, "down")
    clear("compare_school", "difference", True, "down")
    clear("compare_school_rev", "difference", True, "up")
    clear("compare_weapon", "difference", False)
    clear("ba_d6", "step", True, "up")
    clear("ba_d6", "bend", True, "up")
    clear("ba_d7", "step", True, "down")
    clear("ba_d7", "bend", True, "down")
    clear("ba_d2", "step", False)
    clear("ba_d2", "bend", False)
    yn = truth("yn_main")["odds"]
    clear("yn_main", yn[0], True, "up", 1.0)
    clear("yn_main", yn[1], True, "down", 1.0)
    clear("yn_main", yn[2], False, None, 1.0)
    assert yn[0]["estimate"] > 2.0 and 0.6 < yn[1]["estimate"] < 0.95, yn
    for e in truth("yn_u18")["odds"][:1]:
        clear("yn_u18", e, True, "up", 1.0)
    clear("sh_school", "sharetrend", True, "up", 1.0)
    clear("sh_noschool", "sharetrend", True, "down", 1.0)
    clear("sh_shift", "sharetrend", False, None, 1.0)
    for name in CASES:
        t = truth(name)
        if t["kind"] == "trend_compare":  # S12 item 1: each group's own model
            assert set(t["models"].values()) <= {"negative binomial", "poisson"}, (name, t)
        elif t["kind"] in ("trend", "before_after"):
            want = "poisson" if name in ("trend_fallback",) else None
            if want:
                assert t["model"] == want, (name, t["model"])
            elif name not in ("trend_q1", "trend_r100", "trend_r099"):
                assert t["model"] == "negative binomial", (name, t["model"])
        if t["kind"] in ("trend", "trend_compare", "before_after"):  # the fit note is T's
            r = t["fit_ratio"]
            assert min(abs(r - FIT_BAND[0]), abs(r - FIT_BAND[1])) > 0.01, (name, r)
            lines.append(f"{name}: model {t['model']}, fit ratio {r:.4f}, fit line "
                         f"{t['fit_line']}")
    # S12 item 1: the two groups' models differ in compare_school (a falls back to Poisson)
    assert truth("compare_school")["models"] == {"a": "poisson", "b": "negative binomial"}
    assert truth("compare_gender")["models"] == {"a": "negative binomial",
                                                 "b": "negative binomial"}
    assert truth("trend_d4_p6")["fit_line"] and truth("trend_d4_p6")["fit_ratio"] < 0.9
    assert truth("trend_d5_p6")["fit_line"] and truth("trend_d5_p6")["fit_ratio"] > 1.1
    for name in ("trend_all", "trend_all_p6"):  # the counterpart inside the band
        assert not truth(name)["fit_line"], name
    tm = truth("timing")
    assert tm["busiest"] == (4, 23) and tm["quietest"] == (1, 4) and tm["quietest_n"] == 4
    assert sorted(tm["cells"].values())[1] >= FLOOR
    lines.append(f"timing: busiest {tm['busiest']} ({tm['busiest_n']}), quietest "
                 f"{tm['quietest']} ({tm['quietest_n']})")
    ag = truth("ages_gender")["groups"]
    assert all("median" in s for s in ag.values()), ag
    lines.append(f"ages: {truth('ages')['groups'][None]}; by gender: {dict(ag)}")
    return lines


# ---- the cross-check against R (brief step 6) ------------------------------------------------

def crosscheck_input():
    """Every model case: the tables R is to fit (monthly tables; one line per record for L
    and S, holding only 0/1 and labels) and Python's numbers, for
    kit-log/raw/S3S-A-r-crosscheck.R. R works out the days, the time and the month
    indicators itself, and picks the most common label itself."""
    out = []
    for name, c in CASES.items():
        t = truth(name)
        item = {"case": name, "kind": t["kind"], "options": c.get("options", {}),
                "python": {"model": t.get("model"), "fit_ratio": t.get("fit_ratio"),
                           "estimates": [{"name": e["name"], "estimate": e["estimate"],
                                          "low": e["low"], "high": e["high"], "p": e["p"],
                                          "scale": e["scale"]} for e in t["estimates"]]}}
        if t["kind"] in ("trend", "before_after"):
            item["table"] = {"y": [ym[0] for ym in t["months"]],
                             "m": [ym[1] for ym in t["months"]], "n": t["counts"]}
        elif t["kind"] == "trend_compare":
            ms = t["months"]
            item["table"] = {"y": [ym[0] for ym in ms] * 2, "m": [ym[1] for ym in ms] * 2,
                             "n": t["counts"]["a"] + t["counts"]["b"],
                             "g": [0] * len(ms) + [1] * len(ms)}
            # S12 item 1: the two own fits the difference now comes from
            item["python"]["models"] = t["models"]
            item["python"]["own"] = {k: {"estimate": e["estimate"], "low": e["low"],
                                         "high": e["high"], "p": e["p"], "coef": e["coef"],
                                         "se": e["se"]} for k, e in t["own"].items()}
        elif t["kind"] == "yes_no":
            item["table"] = {"y": t["y"], **t["raw"]}
        elif t["kind"] == "shares":
            item["table"] = {"y": t["y"], "year": t["year"]}
            item["python"]["years"] = [{"year": yr, "base": v["base"], "part": v["part"],
                                        "share": v["share"], "low": v["range"][0],
                                        "high": v["range"][1]}
                                       for yr, v in t["years"].items()]
        else:
            continue
        out.append(item)
    return out


if __name__ == "__main__":
    import sys
    if sys.argv[1:2] == ["--crosscheck"]:
        Path(sys.argv[2]).write_text(json.dumps(crosscheck_input()) + "\n", encoding="utf-8")
    else:
        for line in check_designed():
            print(line)
