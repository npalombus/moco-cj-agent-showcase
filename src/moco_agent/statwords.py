"""The words of a statistical answer (docs/S3S-DESIGN.md S4, S5, S7 and S10): the phrases of
the slots, the table lines, the fixed lines and the refusals. Every number here was computed
by R (estimates) or counted by Python (totals); the floor applies to every count.

Signs (S10 answer 1): after a direction word the number is its size; everywhere else a value
below zero takes `-`, one above zero `+`, and zero is `0.0`. Odds ratios and shares (levels,
S10 answer 18) never take a sign.
"""
import calendar
from collections import OrderedDict

from .analysis import join_and
from .counting import segments, shown

MONTHS = list(calendar.month_name)[1:]
WEEKDAYS = list(calendar.day_name)
BEFORE_AFTER_LINE = "Other things changed over the same months. This shows timing, not cause."
ENGINE_MISSING_LINE = ("I can't run statistics here right now: the statistics engine is not "
                       "installed. Counts still work.")
ENGINE_FAILED_LINE = ("The statistics run failed, so there is no result to show. Counts still "
                      "work, and the failure is logged.")
FIRST_ENDING = "Want the details and the R script?"
FACTOR_LABELS = {"under_18": "being under 18", "weekend": "a weekend day",
                 "night": "night hours (10 p.m. to 6 a.m.)"}      # S10 answer 2
OUTCOME_LABELS = {"under_18": "being under 18", "weekend": "falling on a weekend",
                  "night": "falling at night (10 p.m. to 6 a.m.)"}


# ---- numbers --------------------------------------------------------------------------------

def signed(value, decimals=1):
    text = f"{abs(value):.{decimals}f}"
    if float(text) == 0:
        return f"{0:.{decimals}f}"
    return ("-" if value < 0 else "+") + text


def size(value):
    return f"{abs(value):.1f}"


def odds(value):
    return f"{value:.2f}"


def level(value):
    return f"{value:.1f}"


def age_text(value):
    return str(int(value)) if float(value).is_integer() else f"{value:.1f}"


def month_text(ym):
    return f"{MONTHS[ym[1] - 1]} {ym[0]}"


def hour_text(h):
    return {0: "midnight", 12: "noon"}.get(h, f"{h} am" if h < 12 else f"{h - 12} pm")


def cap(text):
    return text[:1].upper() + text[1:]


# ---- labels --------------------------------------------------------------------------------

def what(source, filters):
    """C6's `<what>` of a filter list."""
    return " ".join(phrase for _, phrase, _ in segments(source, filters))


def item_what(source, item):
    """S11 item 1: a factor or the outcome as C6's `<what>` of the matching filter."""
    if item["type"] == "made":
        age = next((f["name"] for f in source["fields"] if f["kind"] == "age"), None)
        flt = {"under_18": {"field": age, "to": 17},
               "weekend": {"field": "weekday", "in": ["Saturday", "Sunday"]},
               "night": {"field": "hour", "from": 22, "to": 5}}[item["name"]]  # D-053
    elif item["type"] == "category":
        flt = {"field": item["field"], "in": [item["label"]]}
    else:
        flt = {"field": item["field"], "is": item["is"]}
    return what(source, [flt])


def year_months(year, window):
    """S11 2c: the months of `year` inside the window, as (first, last) month numbers."""
    first, last = window["first"], window["last"]
    return (first[1] if year == first[0] else 1, last[1] if year == last[0] else 12)


def year_label(year, window):
    """S11 2c: `2026`, or `2026 (January to September)` for a year the window covers in part."""
    a, b = year_months(year, window)
    if (a, b) == (1, 12):
        return str(year)
    return f"{year} ({MONTHS[a - 1]})" if a == b else f"{year} ({MONTHS[a - 1]} to {MONTHS[b - 1]})"


def year_in(year, window):
    """S11 2g: `2021`, or `January to September 2026`, after "in"."""
    a, b = year_months(year, window)
    if (a, b) == (1, 12):
        return str(year)
    return f"{MONTHS[a - 1]} {year}" if a == b else f"{MONTHS[a - 1]} to {MONTHS[b - 1]} {year}"


def item_label(source, item, role):
    """S4 with S10 answer 2: a factor's or the outcome's label."""
    if item["type"] == "made":
        return (FACTOR_LABELS if role == "factor" else OUTCOME_LABELS)[item["name"]]
    if item["type"] == "category":
        return item["label"]
    f = next(f for f in source["fields"] if f["name"] == item["field"])
    return f["yes"] if item["is"] else f["no"]


def control_words(source, controls):
    fields = {f["name"]: f for f in source["fields"]}
    return ["year" if c == "year" else fields[c]["dimension"] for c in controls]


def held_text(source, controls):
    words = control_words(source, controls)
    return f"holding {join_and(words)} fixed" if words else "with nothing else held fixed"


def compare_labels(source, spec, options):
    """trend_compare: the `<what>` fragments and C6's compare labels of the one filter that
    differs (S10 answer 7), for a and for b."""
    name = options["field"]
    a = [f for f in spec["filters"] if f["field"] == name]
    b = [f for f in options["versus"] if f["field"] == name]
    (_, a_what, a_label), = segments(source, a)
    (_, b_what, b_label), = segments(source, b)
    return {"a_what": a_what, "b_what": b_what, "a_label": a_label, "b_label": b_label}


def read_as(source, spec, kind, options, months):
    """What was analysed, in words (S1): the tool answer, the chart's title, details."""
    many = source["unit"]["many"]
    base = " ".join([many] + ([what(source, spec["filters"])] if spec["filters"] else []))
    period = f"from {month_text(months[0])} to {month_text(months[-1])}" if months else ""
    if kind == "trend":
        return f"the trend in {base}, {period}"
    if kind == "trend_compare":
        labels = compare_labels(source, spec, options)
        rest = [f for f in spec["filters"] if f["field"] != options["field"]]
        common = " ".join([many] + ([what(source, rest)] if rest else []))
        return (f"the trends in {common}, {labels['a_label']} against {labels['b_label']}, "
                f"{period}")
    if kind == "before_after":
        when = options["date"]
        return f"{base} before and after {month_text((int(when[:4]), int(when[5:7])))}, {period}"
    # S12 item 4, with S11 item 1's `<what>` fragments; the spec's filters stay with <unit
    # many> (`arrest records in district 3`: one of the two readings the tests accept)
    if kind == "yes_no":
        factors = [item_what(source, f) for f in options["factors"]]
        return (f"the odds of {base} being {item_what(source, options['outcome'])}, for those "
                f"{join_and(factors)}, {held_text(source, options['controls'])}, {period}")
    if kind == "shares":
        return f"the yearly share of {base} that were {what(source, options['part'])}, {period}"
    if kind == "timing":
        return f"{base} by weekday and hour, {period}"
    by = options.get("by")
    dim = next((f["dimension"] for f in source["fields"] if f["name"] == by), None)
    return f"the ages in {base}" + (f" by {dim}" if dim else "") + f", {period}"


# ---- the phrases of S4 ------------------------------------------------------------------------

def _range_pct(e):
    return f"95% range {signed(e['low'])}% to {signed(e['high'])}%"


def trend_phrase(head, e, first, last):
    if e["clear"]:
        word = "rose" if e["estimate"] > 0 else "fell"
        return (f"{head} {word} by about {size(e['estimate'])}% a year from {first} to {last} "
                f"({_range_pct(e)})")
    return (f"{head} showed no clear change from {first} to {last} (about "
            f"{signed(e['estimate'])}% a year, {_range_pct(e)})")


RATIO = "the ratio of the two yearly changes"  # S11 item 2: not percentage points


def difference_phrase(e, labels):
    if e["clear"]:
        word = "above" if e["estimate"] > 0 else "below"
        return (f"the yearly trend {labels['b_what']} was about {size(e['estimate'])}% {word} "
                f"the yearly trend {labels['a_what']} ({RATIO}; {_range_pct(e)})")
    return (f"there was no clear difference in yearly trend between {labels['a_label']} and "
            f"{labels['b_label']} ({RATIO} was about {signed(e['estimate'])}%, {_range_pct(e)})")


def step_phrase(e, month):
    if e["clear"]:
        word = "higher" if e["estimate"] > 0 else "lower"
        return (f"from {month} on, the monthly level was about {size(e['estimate'])}% {word} than "
                f"the earlier trend pointed to ({_range_pct(e)})")
    return f"there was no clear step in {month} (about {signed(e['estimate'])}%, {_range_pct(e)})"


def bend_phrase(e, month):
    if e["clear"]:
        word = "above" if e["estimate"] > 0 else "below"
        return (f"after {month} the yearly trend was about {size(e['estimate'])}% {word} the "
                f"yearly trend before ({RATIO}; {_range_pct(e)})")
    return (f"there was no clear change in the yearly trend after {month} ({RATIO} was about "
            f"{signed(e['estimate'])}%, {_range_pct(e)})")


def odds_phrase(e, many, factor, outcome):
    """S11 item 1: both sides as C6's `<what>` fragments."""
    numbers = f"odds ratio {odds(e['estimate'])}, 95% range {odds(e['low'])} to {odds(e['high'])}"
    if e["clear"]:
        word = "higher" if e["estimate"] > 1 else "lower"
        return f"{many} {factor} had {word} odds of being {outcome} ({numbers})"
    return f"{many} {factor} showed no clear difference in the odds of being {outcome} ({numbers})"


def _cells_text(cells):
    return join_and(f"{WEEKDAYS[d]} at {hour_text(h)}" for d, h in cells)


def timing_phrase(cells, floor):
    """The busiest and the quietest cell. Ties are named together, `(<n> each)`. C16: hidden
    values are never ranked, so with no cell at 0 the quietest side names every hidden cell."""
    flat = [(d, h, n) for d in range(7) for h in range(24) for n in [cells[d][h]]]
    high = max(n for _, _, n in flat)
    low = min(n for _, _, n in flat)
    top = [(d, h) for d, h, n in flat if n == high]
    hidden = [(d, h) for d, h, n in flat if 1 <= n < floor]
    if hidden and low != 0:
        bottom, bottom_n = hidden, f"fewer than {floor}" + (" each" if len(hidden) > 1 else "")
    else:
        bottom = [(d, h) for d, h, n in flat if n == low]
        bottom_n = shown(low, floor) + (" each" if len(bottom) > 1 else "")
    top_n = shown(high, floor) + (" each" if len(top) > 1 else "")
    return (f"{_days_phrase(cells, floor)}; the busiest hour was {_cells_text(top)} ({top_n}) "
            f"and the quietest {_cells_text(bottom)} ({bottom_n})")


def _days_phrase(cells, floor):
    """C59: the busiest and the quietest day of the week, each day the sum of its 24 cells,
    shown as any figure is; hidden totals are never ranked (C16), as for the hours."""
    totals = [sum(cells[d]) for d in range(7)]
    high, low = max(totals), min(totals)
    top = [d for d in range(7) if totals[d] == high]
    hidden = [d for d in range(7) if 1 <= totals[d] < floor]
    if hidden and low != 0:
        bottom, bottom_n = hidden, f"fewer than {floor}" + (" each" if len(hidden) > 1 else "")
    else:
        bottom = [d for d in range(7) if totals[d] == low]
        bottom_n = shown(low, floor) + (" each" if len(bottom) > 1 else "")
    top_n = shown(high, floor) + (" each" if len(top) > 1 else "")
    return (f"the busiest day of the week was {join_and(WEEKDAYS[d] for d in top)} ({top_n}) "
            f"and the quietest {join_and(WEEKDAYS[d] for d in bottom)} ({bottom_n})")


def ages_phrase(group, label=None):
    text = (f"the median age was {age_text(group['median'])} (the middle half were "
            f"{age_text(group['q1'])} to {age_text(group['q3'])})")
    return text if label is None else f"for {label}, {text}"


def phrases(r):
    """The slots of one statistical result and their phrases, in slot order."""
    kind, out = r["stat"], OrderedDict()
    est = {e["name"]: e for e in r["estimates"]}
    first, last = month_text(r["window"]["first"]), month_text(r["window"]["last"])
    if kind == "trend":
        out["trend"] = trend_phrase(r["head"], est["trend"], first, last)
    elif kind == "trend_compare":
        out["difference"] = difference_phrase(est["difference"], r["labels"])
    elif kind == "before_after":
        out["step"] = step_phrase(est["step"], r["date_month"])
        out["bend"] = bend_phrase(est["bend"], r["date_month"])
    elif kind == "yes_no":
        # a record saved before S11 has the labels only: it is read with those
        outcome = r.get("outcome_what", r["outcome_label"])
        for i, (factor, e) in enumerate(zip(r.get("factor_whats", r["factor_labels"]),
                                            r["estimates"]), 1):
            out[f"odds.{i}"] = odds_phrase(e, r["unit"]["many"], factor, outcome)
        out["held"] = r["held"]
    elif kind == "shares":
        years = r["years"]
        out["share"] = (f"the share {r['part']} went from {level(years[0]['share'])}% in "
                        f"{year_in(years[0]['year'], r['window'])} to "
                        f"{level(years[-1]['share'])}% in "
                        f"{year_in(years[-1]['year'], r['window'])}")  # S11 2g
        e = est["sharetrend"]
        out["sharetrend"] = (f"a clear {'rise' if e['estimate'] > 1 else 'fall'} over the years"
                             if e["clear"] else "no clear change over the years")
    elif kind == "timing":
        out["timing"] = timing_phrase(r["cells"], r["floor"])
    else:  # S10 answer 8: every group's phrase in one slot, in table order
        groups = r["ages"]
        out["ages"] = (ages_phrase(groups[0]) if not r["groups_by"] else
                       "; ".join(ages_phrase(g, g["label"]) for g in groups))
    return out


# ---- the lines of S5 ----------------------------------------------------------------------------

def table_lines(r):
    """S5.1 with S10 answer 9 (timing's table is in details only, S10 answer 14)."""
    kind, floor = r["stat"], r["floor"]
    if kind in ("trend", "before_after"):
        return [f"{year_label(y, r['window'])}: {shown(n, floor)}" for y, n in r["yearly"]]
    if kind == "trend_compare":
        return [f"{label}: about {signed(e['estimate'])}% a year ({_range_pct(e)})"
                for label, e in zip((r["labels"]["a_label"], r["labels"]["b_label"]), r["own"])]
    if kind == "yes_no":
        return [f"{factor}: odds ratio {odds(e['estimate'])} (95% range {odds(e['low'])} to "
                f"{odds(e['high'])})"
                for factor, e in zip(r.get("factor_whats", r["factor_labels"]), r["estimates"])]
    if kind == "shares":
        return [f"{year_label(y['year'], r['window'])}: {level(y['share'])}% (95% range "
                f"{level(y['low'])}% to {level(y['high'])}%)" for y in r["years"]]
    if kind == "distribution" and r["groups_by"]:
        return [f"{g['label']}: median {age_text(g['median'])}, middle half {age_text(g['q1'])} "
                f"to {age_text(g['q3'])}" for g in r["ages"]]
    return []


def timing_table(cells, floor):
    """S10 answer 14: seven lines, Monday first, the 24 hourly counts from midnight on."""
    return [f"{WEEKDAYS[d]}: " + " | ".join(shown(n, floor) for n in cells[d]) for d in range(7)]


def fit_line(r, band):
    """S5.2: only for T, and only outside the band."""
    ratio = r.get("fit_ratio")
    if ratio is None or band[0] <= ratio <= band[1]:
        return None
    return (f"The last six months were about {abs(1 - ratio) * 100:.1f}% "
            f"{'below' if ratio < 1 else 'above'} the trend line, so a straight line describes "
            f"the recent period poorly.")


def reason(source, name):
    f = next(f for f in source["fields"] if f["name"] == name)
    return "no usable age" if f["kind"] == "age" else f"no {f['dimension']} recorded"


def used_text(r, source):
    """S5.4 with S10 answers 5 and 16: `<n> records over <m> months` and one `; <k> not
    included: <reason>` part per reason, in the source file's order."""
    floor = r["floor"]
    parts = "".join(f"; {shown(k, floor)} not included: {reason(source, name)}"
                    for name, k in r["left_out"].items() if k)
    return f"{shown(r['records'], floor)} records over {r['window']['months']} months{parts}"


def used_line(r, source, named=False):
    """C19's form when the reply holds more than one result: `For <read_as>: ...`."""
    text = used_text(r, source)
    return f"For {r['read_as']}: {text}." if named else f"({text}.)"


def association_line(unit_many, sensitive=False):
    """S5.5; S11 2f: with a sensitive field in the same reply, one line says both."""
    rates = ", not rates" if sensitive else ""
    return (f"These are patterns in recorded {unit_many}{rates}: what goes with what, not what "
            f"causes what.")


def hides(r):
    """S11 2b: a phrase or a table line of this result holds a hidden count."""
    mark = f"fewer than {r['floor']}"
    return any(mark in text for text in list(r["phrases"].values()) + list(r["table"]))


def odds_room(names):
    """S11 2i: R1's sentences and characters for a reply that fills k odds slots."""
    k = sum(1 for name in names if ".odds." in name)
    return max(4, k + 2), max(600, 200 * k + 200)


# ---- refusals (S10 answer 10) -----------------------------------------------------------------

def too_little_line(rule, cfg):
    return {
        "months": f"That needs at least {cfg['min_months']} full months of records, and this "
                  f"selection has fewer.",
        "records": f"That needs at least {cfg['min_records']} records in all, and this "
                   f"selection has fewer.",
        "cases": f"That needs at least {cfg['min_cases']} records with the outcome and "
                 f"{cfg['min_cases']} without, and this selection has fewer.",
        "per_coefficient": f"That needs at least {cfg['per_coefficient']} records of the rarer "
                           f"outcome for each thing compared, and this selection has fewer.",
        "base_year": f"That needs at least {cfg['min_base_year']} records in every year, and one "
                     f"year here has fewer.",
        "ages": f"That needs at least {cfg['min_ages']} usable ages in every group, and one group "
                f"here has fewer.",
        "sides": f"That needs at least {cfg['min_months_each_side']} full months on each side of "
                 f"the date, and this selection has fewer.",
        # S14: a shares analysis over fewer than two years, refused before R
        "years": "That follows a share across years, so it needs at least two years of "
                 "records. For one year, I can count the whole and the part and give the share.",
        # S12 item 4c: refused before R (stats._t_table says why)
        "step_apart": "That needs more than 12 full months on at least one side of the date: "
                      "with 12 on each side, a step at the date cannot be told apart from the "
                      "yearly trend. Try a longer period.",
    }[rule]


def too_fine_line(floor):
    return (f"That selection is too small to chart without showing counts under {floor}. Try a "
            f"wider period or fewer filters.")


# ---- details (S7) -------------------------------------------------------------------------------

def model_sentence(r):
    kind = r["stat"]
    if kind == "trend_compare":  # S12 item 1: the two own fits, no third model
        models = r.get("models") or [r["model"]] * 2
        many = r["unit"]["many"]
        each = [("a Poisson regression with robust (HC1) standard errors (the negative binomial "
                 "model could not be fitted)" if m == "poisson" else "a negative binomial "
                 "regression") + f" for {many} {w}"
                for m, w in zip(models, (r["labels"]["a_what"], r["labels"]["b_what"]))]
        return (f"Each group fitted on its own: {join_and(each)}, each of the monthly count on "
                f"time in years and the month of the year (11 indicators), with the days in each "
                f"month as exposure; the difference is {RATIO}, with its standard error from the "
                f"two fits (the groups share no record), and 95% Wald ranges.")
    if kind in ("trend", "before_after"):
        extra = ""
        if kind == "before_after":
            extra = (f", with an indicator for the months from {r['date_month']} on and the "
                     f"time since then (0 before it)")
        terms = ("the monthly count on time in years and the month of the year (11 indicators), "
                 "with the days in each month as exposure" + extra)
        if r["model"] == "poisson":
            return ("The negative binomial model could not be fitted (no spread beyond Poisson, "
                    f"or no convergence), so this is a Poisson regression of {terms}, with robust "
                    "(HC1) standard errors and 95% Wald ranges.")
        return f"A negative binomial regression of {terms}, with 95% Wald ranges."
    if kind == "yes_no":
        refs = r.get("references") or {}
        held = (f", holding {join_and(f'{dim} (against {ref})' for dim, ref in refs.items())} "
                f"fixed" if refs else ", with nothing else held fixed")
        return (f"A logistic regression of {r['outcome_label']} on the factors, each 0 or 1"
                f"{held}; 95% Wald ranges on the odds ratios.")
    if kind == "shares":
        return (f"The share {r['part']} in each calendar year with a Wilson 95% range, and a "
                f"logistic regression of matching it on the year as a number (clear when the "
                f"odds ratio's 95% range leaves out 1).")
    if kind == "timing":
        return "Counts of records by weekday and hour; no model."
    return "The median and the quartiles of the usable ages (R's quantile, type 7); no model."


def details_lines(r, source):
    floor = r["floor"]
    lines = [f"Read as: {r['read_as']}."]
    if r["stat"] == "timing":
        lines += timing_table(r["cells"], floor)
    elif r["stat"] in ("trend", "before_after"):
        lines += ["By year:"] + table_lines(r)
    else:
        lines += table_lines(r)
    lines.append(f"Model: {model_sentence(r)}")
    lines += [f"Result: {cap(p)}." for p in phrases(r).values()]
    first, last = month_text(r["window"]["first"]), month_text(r["window"]["last"])
    lines.append(f"Used: {used_text(r, source)} ({first} to {last}).")
    if r.get("fit_line"):
        lines.append(r["fit_line"])
    lines.append("The R script attached downloads the same public data from the county, applies "
                 "the same filters and months, fits the same model and prints the same "
                 "estimates.")
    return lines
