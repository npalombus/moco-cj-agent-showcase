"""Counting a county source's saved copy, and the phrases Python writes about it (design
S3A, C3 and C5 to C8).

The model sends a spec (source, period, filters, at most two breakdowns); Python checks it
against the source file, counts the rows of the current copy with plain loops, applies the
floor (C8) and writes every phrase a person reads (C6). A result holds its exact figures
(for the record and turn.json only) and its phrases, already floored.
"""
import calendar
import json
import math
from collections import OrderedDict
from datetime import date, timedelta
from fractions import Fraction

from .analysis import join_and

MONTHS = list(calendar.month_name)[1:]
WEEKDAYS = list(calendar.day_name)        # Monday first
TIME_PARTS = ("year", "month", "weekday", "hour")
DIMENSION_WORDS = {"year": "year", "month": "month", "weekday": "day of the week",
                   "hour": "hour", "age_band": "age band"}
MAX_GROUPS = 400
VERSION = "count@0.1.0"


class SpecError(Exception):
    """A spec, share or compare Python refuses (a tool error; the turn goes on). `hint`
    never holds a value from the data or a record."""

    def __init__(self, code, **hint):
        super().__init__(code)
        self.code, self.hint = code, hint

    def answer(self):
        return {"error": self.code, **self.hint}


# ---- numbers and words (C6) ---------------------------------------------------------------

def shown(n, floor):
    """C8: 1 to floor - 1 is `fewer than <floor>`; 0 and the rest as numbers, with commas."""
    return f"fewer than {floor}" if 1 <= n < floor else f"{n:,}"


def is_hidden(n, floor):
    return 1 <= n < floor


def day_text(d):
    """`1 March 2025`."""
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def hour_label(h):
    # ponytail: C6 gives `10 pm`; 0 and 12 are not given, so midnight and noon.
    return {0: "midnight", 12: "noon"}.get(h, f"{h} am" if h < 12 else f"{h - 12} pm")


def _fields(source):
    return {f["name"]: f for f in source["fields"]}


def _age_field(source):
    found = [f for f in source["fields"] if f["kind"] == "age"]
    return found[0] if found else None


def age_name(source):
    return _age_field(source)["name"]


def _labels(f):
    """A category's labels in file order, each once."""
    return list(OrderedDict.fromkeys(f["values"].values()))


def usable_names(source):
    """What a spec may name: filter fields and breakdowns."""
    names = [f["name"] for f in source["fields"] if f["kind"] in ("age", "category", "flag")]
    return {"filters": names + ["weekday", "hour"],
            "group_by": [n for n in names if _fields(source)[n]["kind"] != "age"]
            + (["age_band"] if _age_field(source) else []) + list(TIME_PARTS)}


# ---- checking a spec (C5) -----------------------------------------------------------------

def _whole(value):
    """A whole number given as an int (not a bool) or a float with no fraction, else None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _year(value):
    if isinstance(value, str) and value.isdigit() and len(value) == 4:
        value = int(value)
    y = _whole(value)
    if y is None or not 1900 <= y <= 2100:
        raise SpecError("BAD_VALUE", field="period", why="a year is a whole number such as 2025")
    return y


def _date(value):
    try:
        if not (isinstance(value, str) and len(value) == 10):
            raise ValueError
        return date.fromisoformat(value)
    except ValueError:
        raise SpecError("BAD_VALUE", field="period",
                        why="dates are written YYYY-MM-DD and must exist") from None


def check_period(raw):
    """The period in one of C5's four shapes, tidied; a single year in `years` is a year."""
    if not isinstance(raw, dict):
        raise SpecError("BAD_VALUE", field="period", why="the period is an object")
    keys = set(raw)
    if keys == {"year"}:
        return {"year": _year(raw["year"])}
    if keys == {"years"} and isinstance(raw["years"], list) and raw["years"]:
        ys = sorted({_year(y) for y in raw["years"]})
        return {"year": ys[0]} if len(ys) == 1 else {"years": ys}
    if keys == {"year", "months"} and isinstance(raw["months"], dict) and \
            set(raw["months"]) == {"from", "to"}:
        first, last = _whole(raw["months"]["from"]), _whole(raw["months"]["to"])
        if first is None or last is None or not 1 <= first <= last <= 12:
            raise SpecError("BAD_VALUE", field="period",
                            why="months run from 1 to 12, the first not after the last")
        return {"year": _year(raw["year"]), "months": {"from": first, "to": last}}
    if keys == {"from", "to"}:
        first, last = _date(raw["from"]), _date(raw["to"])
        if first > last:
            raise SpecError("BAD_VALUE", field="period", why="the first date is after the last")
        return {"from": first.isoformat(), "to": last.isoformat()}
    raise SpecError("BAD_VALUE", field="period",
                    why='use {"year": 2025}, {"years": [2024, 2025]}, {"year": 2025, "months": '
                        '{"from": 1, "to": 10}} or {"from": "2025-03-01", "to": "2025-08-31"}')


def bounds(period):
    """(first day, last day, set of years or None) of a tidied period."""
    if "years" in period:
        ys = period["years"]
        return date(ys[0], 1, 1), date(ys[-1], 12, 31), set(ys)
    if "year" in period:
        y = period["year"]
        if "months" in period:
            m = period["months"]
            return (date(y, m["from"], 1),
                    date(y, m["to"], calendar.monthrange(y, m["to"])[1]), None)
        return date(y, 1, 1), date(y, 12, 31), None
    return date.fromisoformat(period["from"]), date.fromisoformat(period["to"]), None


def _ends(flt, f):
    out = {}
    for end in ("from", "to"):
        if end in flt:
            value = _whole(flt[end])
            if value is None:
                raise SpecError("BAD_VALUE", field=f, why="an age is a whole number of years")
            out[end] = value
    return out


def _filter(source, flt):
    if not isinstance(flt, dict) or not isinstance(flt.get("field"), str):
        raise SpecError("BAD_FIELD", why='each filter is an object with "field"',
                        fields=usable_names(source)["filters"])
    name, keys = flt["field"], set(flt) - {"field"}
    if name == "weekday":
        if keys == {"is"}:
            given = [flt["is"]]
        elif keys == {"in"} and isinstance(flt["in"], list) and flt["in"]:
            given = flt["in"]
        else:
            raise SpecError("BAD_FIELD", field=name, why='weekday takes "in": [day names]')
        lower = {d.lower(): d for d in WEEKDAYS}
        days = {lower.get(str(d).lower()) for d in given}
        if None in days:
            raise SpecError("BAD_VALUE", field=name, allowed=WEEKDAYS)
        return {"field": name, "in": [d for d in WEEKDAYS if d in days]}
    if name == "hour":
        if keys == {"is"}:
            flt, keys = {"from": flt["is"], "to": flt["is"]}, {"from", "to"}
        if not keys or not keys <= {"from", "to"}:
            raise SpecError("BAD_FIELD", field=name, why='hour takes "from" and "to" (0 to 23)')
        first, last = _whole(flt.get("from", 0)), _whole(flt.get("to", 23))
        if first is None or last is None or not (0 <= first <= 23 and 0 <= last <= 23):
            raise SpecError("BAD_VALUE", field=name, why="hours run from 0 to 23")
        return {"field": name, "from": first, "to": last}
    f = _fields(source).get(name)
    if f is None or f["kind"] not in ("age", "category", "flag"):
        raise SpecError("BAD_FIELD", field=name, fields=usable_names(source)["filters"])
    if f["kind"] == "age":
        if not keys or not keys <= {"from", "to"}:
            raise SpecError("BAD_FIELD", field=name, why='an age takes "from" and/or "to"')
        ends = _ends(flt, name)
        usable_low, usable_high = f["usable"]
        low, high = max(ends.get("from", usable_low), usable_low), \
            min(ends.get("to", usable_high), usable_high)
        if ends.get("from", usable_low) > ends.get("to", usable_high) or low > high:
            raise SpecError("BAD_VALUE", field=name,
                            why=f"ages run from {usable_low} to {usable_high}, the first not "
                                f"after the last")
        if high - low + 1 < 2 and low < 18:  # C5 NOT_ALLOWED, C8.4
            first, last = (low, low + 1) if low + 1 <= 17 else (low - 1, low)  # C35
            raise SpecError("NOT_ALLOWED", field=name,
                            why=f"under 18, an age range must cover at least two years, "
                                f"such as {first} to {last}")
        return {"field": name, **ends}
    if f["kind"] == "flag":
        if keys != {"is"}:
            raise SpecError("BAD_FIELD", field=name, why='a yes or no field takes "is": true or '
                                                         'false')
        value = flt["is"]
        if isinstance(value, str):
            value = {"true": True, "false": False, f["yes"].lower(): True,
                     f["no"].lower(): False}.get(value.lower(), value)
        if not isinstance(value, bool):
            raise SpecError("BAD_VALUE", field=name, why='"is" is true or false')
        return {"field": name, "is": value}
    if keys == {"is"}:
        given = [flt["is"]]
    elif keys == {"in"} and isinstance(flt["in"], list) and flt["in"]:
        given = flt["in"]
    else:
        raise SpecError("BAD_FIELD", field=name, why='a category takes "is": label or "in": '
                                                     '[labels]')
    labels = _labels(f)
    lower = {label.lower(): label for label in labels}
    chosen = {lower.get(g.lower()) if isinstance(g, str) else None for g in given}
    if None in chosen:
        raise SpecError("BAD_VALUE", field=name, labels=labels)
    return {"field": name, "in": [label for label in labels if label in chosen]}


def _filter_order(source):
    return [f["name"] for f in source["fields"]] + ["weekday", "hour"]


def check_filters(source, raw):
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        raise SpecError("BAD_FIELD", why="filters is a list")
    out = {}
    for flt in raw:
        checked = _filter(source, flt)
        if checked["field"] in out:
            raise SpecError("BAD_FIELD", field=checked["field"],  # C27
                            why='at most one filter per field: for several values use '
                                '"in": [...]; for every value use group_by')
        out[checked["field"]] = checked
    order = _filter_order(source)
    return [out[name] for name in order if name in out]


def check_group_by(source, raw):
    if raw is None:
        raw = []
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        raise SpecError("BAD_FIELD", why="group_by is a list")
    allowed = usable_names(source)["group_by"]
    out = []
    for g in raw:
        if isinstance(g, dict):
            age = _age_field(source)
            if g.get("field") == "age_band" and "bands" in g and age is not None and \
                    g["bands"] != age["bands"]:
                raise SpecError("NOT_ALLOWED", field="age_band",
                                why="age bands are the source's own")
            g = g.get("field")
        if not isinstance(g, str) or g not in allowed or g in out:
            raise SpecError("BAD_FIELD", field=g if isinstance(g, str) else None,
                            group_by=allowed)
        out.append(g)
    if len(out) > 2:
        raise SpecError("TOO_MANY", why="at most two breakdowns")
    if "year" in out and "month" in out:  # C17: a month label already names its year
        raise SpecError("BAD_FIELD", field="month", group_by=allowed,
                        why="month already names the year: use month alone")
    return out


# ---- C21: no single year of age under 18 from the figures of one turn ----------------------

def _span(period, start=None, newest=None):
    """C21: the days of a period as merged runs of (first day, last day), cut to the days the
    copy covers when those are given (C21 answer 3: two periods holding the same records are
    the same days)."""
    first, last, years = bounds(period)
    runs = ([(date(y, 1, 1), date(y, 12, 31)) for y in sorted(years)] if years
            else [(first, last)])
    if start is not None:
        runs = [(max(a, start), b) for a, b in runs]
    if newest is not None:
        runs = [(a, min(b, newest)) for a, b in runs]
    merged = []
    for a, b in sorted(r for r in runs if r[0] <= r[1]):
        if merged and a <= merged[-1][1] + timedelta(days=1):
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return tuple(merged)


def _cuts(runs, by):
    """C21 answer 6: the runs of each year (or month) a breakdown by year (or month) makes.
    The pieces of one year (or month) stay together (C54: after a weekday filter a month
    is many short runs, and they are one figure)."""
    out = OrderedDict()
    for a, b in runs:
        y, m = a.year, a.month
        while (y, m if by == "month" else 1) <= (b.year, b.month if by == "month" else 1):
            key = (y, m if by == "month" else 1)
            if by == "year":
                lo, hi = date(y, 1, 1), date(y, 12, 31)
                y += 1
            else:
                lo, hi = date(y, m, 1), date(y, m, calendar.monthrange(y, m)[1])
                y, m = (y + 1, 1) if m == 12 else (y, m + 1)
            out.setdefault(key, []).append((max(a, lo), min(b, hi)))
    return [tuple(pieces) for pieces in out.values()]


NO_VALUE = "no value recorded"  # C52 point 2: the kind of a left-out figure


def _on_days(runs, days):
    """C54: the days of these runs that fall on the named weekdays, as merged runs."""
    wanted = {WEEKDAYS.index(d) for d in days}
    out = []
    for a, b in runs:
        day = a
        while day <= b:
            if day.weekday() in wanted:
                if out and out[-1][1] + timedelta(days=1) == day:
                    out[-1] = (out[-1][0], day)
                else:
                    out.append((day, day))
            day += timedelta(days=1)
    return tuple(out)


def _names_every_value(source, flt):
    """C52 point 1: a filter that names every value its field can take (all 24 hours, every
    label of a category) keeps every record that has one. (Weekdays: C54, the days.)"""
    name = flt["field"]
    if name == "hour":
        return len(set(_hours(flt))) == 24
    f = _fields(source).get(name)
    return (f is not None and f["kind"] == "category"
            and set(flt.get("in") or ()) == set(_labels(f)))


def _hours(flt):
    if flt is None:
        return list(range(24))
    a, b = flt["from"], flt["to"]
    return list(range(a, b + 1)) if a <= b else list(range(a, 24)) + list(range(0, b + 1))


def age_figures(source, spec, start=None, newest=None):
    """C21: the figures of a checked spec as (kind, (first age, last age)). A kind is the
    source, the days and every filter but age. A group of a category, a flag, a weekday or an
    hour is of the kind of a count filtered to it; a group of a year or a month is of the kind
    of a count of those days (C21 answer 6). Empty for a source with no age field."""
    age = _age_field(source)
    if age is None:
        return []
    low, high = age["usable"]
    rest, by_field = {}, {}
    for flt in spec["filters"]:
        if flt["field"] == age["name"]:
            low, high = max(low, flt.get("from", low)), min(high, flt.get("to", high))
        else:
            by_field[flt["field"]] = flt
            # C54 point 1: a weekday filter picks days, so it is in the days, not the kind.
            # C65 point 6: a filter that names every label is still a filter: it leaves out
            # the records with no value, and the check reads it so (C52 point 1 then follows
            # from the sums: those labels and the no-value figure make every record).
            if flt["field"] != "weekday":
                rest[flt["field"]] = json.dumps(flt, sort_keys=True)
    runs = _span(spec["period"], start, newest)
    if "weekday" in by_field:
        runs = _on_days(runs, by_field["weekday"]["in"])
    groups, bands = [(runs, dict(rest))], [(low, high)]
    for by in spec["group_by"]:
        if by == "age_band":
            bands = [(max(a, low), min(b, high)) for a, b in age["bands"]
                     if max(a, low) <= min(b, high)]
        elif by in ("year", "month"):
            groups = [(cut, k) for r, k in groups for cut in _cuts(r, by)]
        elif by == "weekday":  # C54 point 2
            groups = [(_on_days(r, [d]), k) for r, k in groups for d in WEEKDAYS]
            groups = [(r, k) for r, k in groups if r]
        elif by == "hour":
            groups = [(r, dict(k, hour=json.dumps({"field": "hour", "from": h, "to": h},
                                                  sort_keys=True)))
                      for r, k in groups for h in _hours(by_field.get("hour"))]
        else:
            f = _fields(source).get(by)
            if f is not None and f["kind"] == "flag":
                only = [by_field[by]["is"]] if by in by_field else [True, False]
                groups = [(r, dict(k, **{by: json.dumps({"field": by, "is": v},
                                                        sort_keys=True)}))
                          for r, k in groups for v in only]
            elif f is not None:
                only = by_field[by]["in"] if by in by_field else _labels(f)
                groups = [(r, dict(k, **{by: json.dumps({"field": by, "in": [v]},
                                                        sort_keys=True)}))
                          for r, k in groups for v in only]
    fields = _fields(source)

    def valued(name):
        return name in fields and fields[name]["kind"] in ("category", "flag")
    # C65 point 6: the total of a count broken down by a category or a flag it does not
    # filter holds only the records with a value there: it is the sum of its groups, so it
    # is no figure of its own.
    figures = ([] if any(valued(by) and by not in by_field for by in spec["group_by"])
               else [(runs, dict(rest), (low, high))])  # the total
    if spec["group_by"]:
        figures += [(r, k, band) for r, k in groups for band in bands]
    # C52 point 2: the records left out for a category or flag field the request uses are a
    # figure too, of the kind "no value recorded for that field". C65 point 6: such a
    # record is left out whatever it holds in the count's other category and flag filters
    # when it has no value there either (counting.tally), so those filters are read as
    # "these values, or none".
    for name in list(OrderedDict.fromkeys(list(by_field) + list(spec["group_by"]))):
        if valued(name):
            kind = {other: (json.dumps(dict(by_field[other], or_none=True), sort_keys=True)
                            if valued(other) else text)
                    for other, text in rest.items() if other != name}
            figures.append((runs, dict(kind, **{name: NO_VALUE}), (low, high)))
    return [(((spec["source"], r), tuple(sorted(k.items()))), band)
            for r, k, band in figures if r]


def one_year_under_18(source, specs, copy=None, days=None, shown=()):
    """C21 and C65: True when the figures of these specs, added and subtracted, cover exactly
    one year of age under 18 for some records: all of a kind (C21), or any part of the
    records that several kinds share or make up together (C65: the two halves of a year, the
    values of a field). With the copy, periods are cut to its days. C62 point 5: `days`, as
    long as `specs`, gives a spec the (first, last) day of the copy it was counted from; None
    there means this copy. `shown`: more figures, as (runs, {field: constraint}, band), for
    what the statistics of the thread showed (C65 point 2)."""
    age = _age_field(source)
    if age is None:
        return False
    first, last = age["usable"]
    here = coverage(source, copy) if copy is not None else (None, None)
    figures = [(runs, dict(kept), band, True) for runs, kept, band in shown]
    for i, spec in enumerate(specs):
        own = days[i] if days is not None and days[i] is not None else None
        start, newest = (_day(own[0]), _day(own[1])) if own is not None else here
        for ((_, runs), kept), band in age_figures(source, spec, start, newest):
            figures.append((runs, dict(kept), band, False))
    return _one_year_somewhere(source, figures, first, last)


def _kept_values(name, constraint):
    """C65: the values of a field that a kind's constraint keeps, or None when this check
    cannot read the constraint (then the figure is held against every value)."""
    if constraint == NO_VALUE:
        return frozenset([NO_VALUE])
    try:
        flt = json.loads(constraint)
    except (TypeError, ValueError):
        return None
    if not isinstance(flt, dict):
        return None
    if name == "hour" and isinstance(flt.get("from"), int) and isinstance(flt.get("to"), int):
        return frozenset(_hours(flt))
    none = frozenset([NO_VALUE] if flt.get("or_none") is True else [])  # C65 point 6
    if isinstance(flt.get("in"), list):
        return frozenset(json.dumps(v, sort_keys=True) for v in flt["in"]) | none
    if isinstance(flt.get("is"), bool):
        return frozenset([flt["is"]]) | none
    return None


def _all_values(source, name):
    """C65: every value a record can have in a field, as _kept_values writes them, or None
    for a field this check does not know. A category or a flag can also have no value."""
    if name == "hour":
        return frozenset(range(24))
    f = _fields(source).get(name)
    if f is None:
        return None
    if f["kind"] == "category":
        return frozenset(json.dumps(v, sort_keys=True) for v in _labels(f)) | {NO_VALUE}
    if f["kind"] == "flag":
        return frozenset([True, False, NO_VALUE])
    return None


WORK_EXACT = 10_000_000  # C65 point 9: a decision bigger than this is cut into slices
PARTS_MAX = 20_000     # the most parts ever listed for a set of figures that cannot be read


def _dims(source, figures):
    """C65: what cuts the records of these figures apart, one list for each dimension: first
    the days, then every field a figure names. Each entry is (mask, none): the figures
    (their indexes) that count one stretch of days or one value of the field, and whether
    that value is "no value recorded". Returns (dims, readable): readable is False when a
    constraint or a field could not be read; the figure is then held against every value."""
    everyone = frozenset(range(len(figures)))
    cuts = sorted({d for runs, *_ in figures for a, b in runs
                   for d in (a.toordinal(), b.toordinal() + 1)})
    spans = [[(a.toordinal(), b.toordinal()) for a, b in runs] for runs, *_ in figures]
    days = OrderedDict()
    for lo in cuts[:-1]:
        inside = frozenset(i for i, own in enumerate(spans)
                           if any(a <= lo <= b for a, b in own))
        if inside:
            days[(inside, False)] = None
    dims, readable = [list(days)], True
    for name in sorted({name for _, kept, *_ in figures for name in kept}):
        keeps = [None if name not in kept else _kept_values(name, kept[name])
                 for _, kept, *_ in figures]
        if any(name in kept and keeps[i] is None for i, (_, kept, *_) in enumerate(figures)):
            readable = False
        domain = _all_values(source, name)
        if domain is None:
            readable = False
        values = set().union(*[k for k in keeps if k is not None]) | (domain or set())
        masks = OrderedDict()
        for v in sorted(values, key=repr):
            mask = frozenset(i for i in everyone if keeps[i] is None or v in keeps[i])
            if mask:
                masks[(mask, v == NO_VALUE)] = None
        dims.append(list(masks))
    return dims, readable


def _product(dims, within, one_gap=False, gap=False):
    """C65: the parts these dimensions cut the figures of `within` into, each the set of the
    figures that count it. C65 point 6d: with `one_gap`, without the parts that have no
    value recorded in more than one field (`gap`: one such field is already fixed)."""
    parts = {(within, gap)}  # each with whether one of its values is "no value recorded"
    for masks in dims:
        parts = {(part & mask, had or none) for part, had in parts for mask, none in masks
                 if part & mask and not (one_gap and had and none)}
    return {part for part, _ in parts}


def _parts(source, figures, one_gap=False):
    """C65: the parts of the records these figures cut them into (see _dims and _product),
    and whether every constraint could be read."""
    dims, readable = _dims(source, figures)
    return _product(dims, frozenset(range(len(figures))), one_gap), readable


def _rank(rows):
    """The rank of a list of rows of whole numbers, exactly: whole-number steps, each new
    row divided by what all its entries share, so the numbers stay small."""
    rows, rank = [[int(x) for x in r] for r in rows], 0
    for col in range(len(rows[0]) if rows else 0):
        pivot = next((r for r in range(rank, len(rows)) if rows[r][col]), None)
        if pivot is None:
            continue
        rows[rank], rows[pivot] = rows[pivot], rows[rank]
        top = rows[rank]
        for r in range(rank + 1, len(rows)):
            if rows[r][col]:
                factor = rows[r][col]
                row = [top[col] * x - factor * y for x, y in zip(rows[r], top)]
                shared = math.gcd(*row) or 1
                rows[r] = [x // shared for x in row]
        rank += 1
        if rank == len(rows):
            break
    return rank


def _leaves_one_year(figures, parts, classes):
    """C65: True when some sum of these figures (index: (band, each)), over these parts,
    leaves records of one single year of age under 18 and nothing else."""
    parts = sorted(parts, key=sorted)
    rows = []
    for i, ((a, b), each) in sorted(figures.items()):
        for own in ([part for part in parts if i in part] if each else [None]):
            rows.append([int((part is own if each else i in part) and a <= lo and hi - 1 <= b)
                         for lo, hi in classes for part in parts])
    rows = [row for row in rows if any(row)]
    if not rows:
        return False
    width = len(parts)
    whole = _rank(rows)
    for c, (lo, hi) in enumerate(classes):
        if hi - lo == 1 and lo <= 17:
            without = [row[:c * width] + row[(c + 1) * width:] for row in rows]
            if whole > _rank(without):
                return True
    return False


def _one_year_somewhere(source, figures, first, last):
    """C65: True when adding and subtracting these figures gives a number for records that
    are all of one year of age under 18. Each figure counts, of every part it holds, the
    ages of its band; the question is whether some sum of the figures leaves only one such
    year. A figure whose fourth entry is True (what a statistic showed) is known for each
    of its parts alone. Point 6d: exactly, or once the records with no value recorded in
    more than one field are taken not to exist. Point 9: a decision too big to make in one
    piece is made slice by slice (one stretch of days, or one value of one field, at a
    time), each figure then taken as known for the slice alone: that errs on the side of
    True and never on the other. When a constraint cannot be read the answer errs on the
    side of True too."""
    figures = list(OrderedDict.fromkeys(
        (tuple(runs), tuple(sorted(kept.items())), tuple(band), bool(each))
        for runs, kept, band, each in figures))
    figures = [(runs, dict(kept), band, each) for runs, kept, band, each in figures if runs]
    if not figures or all(band[0] > 17 for _, _, band, _ in figures):
        return False
    dims, readable = _dims(source, figures)
    everyone = frozenset(range(len(figures)))
    if not readable:  # every part on its own: its bands as if they were of one kind
        size = 1
        for masks in dims:
            size *= len(masks)
        return size > PARTS_MAX or any(
            _one_year({figures[i][2] for i in part}, first, last)
            for part in _product(dims, everyone))
    edges = sorted({first, last + 1} | {e for _, _, (a, b), _ in figures for e in (a, b + 1)
                                        if first <= e <= last + 1})
    classes = list(zip(edges, edges[1:]))  # [from, to) in years of age
    bands = [(band, each) for _, _, band, each in figures]
    # where[i][d]: the entries of dimension d that count figure i (what figure i is, there)
    where = [[frozenset(k for k, (mask, _) in enumerate(masks) if i in mask) for masks in dims]
             for i in range(len(figures))]
    seen = {}

    def decide(alive, left, gaps):
        """The figures `alive`, cut by the dimensions `left`; `gaps`: how many values fixed
        so far are "no value recorded" (2 stands for two or more)."""
        if not any(bands[i][0][0] <= 17 < bands[i][0][1] for i in alive):
            alive = frozenset(i for i in alive if bands[i][0][0] <= 17)  # adults alone: no part
        if not alive:
            return False
        twins = {}  # figures that are the same here: one stands for all
        for i in sorted(alive):
            twins.setdefault((bands[i], tuple(where[i][d] for d in left)), i)
        key = (frozenset(twins), left, gaps)
        if key in seen:
            return seen[key]
        keep = frozenset(twins.values())
        live = []  # each dimension's entries as these figures see them
        for d in left:
            none_only = {}
            for mask, none in dims[d]:
                if mask & keep:
                    none_only[mask & keep] = none_only.get(mask & keep, True) and none
            live.append(list(none_only.items()))
        size = 1
        for masks in live:
            size *= len(masks)
        each = sum(1 for i in keep if bands[i][1])
        rows = len(keep) - each + each * size
        widest = max(range(len(live)), key=lambda k: len(live[k])) if live else None
        if rows * rows * len(classes) * size <= WORK_EXACT or widest is None \
                or len(live[widest]) == 1:
            mine = {i: bands[i] for i in keep}
            answer = _leaves_one_year(mine, _product(live, keep), classes) or (
                gaps < 2 and _leaves_one_year(mine, _product(live, keep, True, gaps == 1),
                                              classes))
        else:
            rest = left[:widest] + left[widest + 1:]
            answer = any(decide(mask, rest, min(2, gaps + none))
                         for mask, none in live[widest])
        seen[key] = answer
        return answer
    return decide(everyone, tuple(range(len(dims))), 0)


def _one_year(bands, first, last):
    """C21: True when these bands of one kind, added and subtracted, cover exactly one year
    of age under 18."""
    basis = []  # rows in echelon form, each cleared of the pivots before it

    def reduce(row):
        for pivot, other in basis:
            if row[pivot]:
                factor = row[pivot] / other[pivot]
                row = [x - factor * y for x, y in zip(row, other)]
        return row
    for a, b in sorted(bands):
        row = reduce([Fraction(a <= age_ <= b) for age_ in range(first, last + 1)])
        pivot = next((i for i, x in enumerate(row) if x), None)
        if pivot is not None:
            basis.append((pivot, row))
    return any(not any(reduce([Fraction(age_ == year) for age_ in range(first, last + 1)]))
               for year in range(first, min(last, 17) + 1))


def shown_bands(source, spec, options=None, age_bands=None, steps=False):
    """C65 point 2: the age bands a statistic shows figures for: the band of its own age
    filter (or every usable age), the band of any age filter among its options, the
    source's own bands when it is broken down by age band, and under 18 and 18 and over
    when it uses the made-up under_18. Empty for a source with no age field. C65 point 7:
    `age_bands`, when given, are the bands its breakdown by age band uses in place of the
    source's own (a rate's are the Census's), each (first, last) with last None for "and
    over". C65 point 8: with `steps`, the two-year steps of the age chart too (a
    distribution's), each cut to the statistic's own ages."""
    age = _age_field(source)
    if age is None:
        return []
    first, last = age["usable"]
    low, high = first, last
    for flt in spec.get("filters") or []:
        if flt.get("field") == age["name"]:
            low, high = max(low, flt.get("from", low)), min(high, flt.get("to", high))
    bands = [(low, high)]

    def walk(node):
        if isinstance(node, dict):
            if node.get("field") == age["name"] and ("from" in node or "to" in node):
                bands.append((max(first, node.get("from", first)),
                              min(last, node.get("to", last))))
            for value in node.values():
                walk(value)
        elif isinstance(node, (list, tuple)):
            for value in node:
                walk(value)
        elif node == "age_band":
            bands.extend((max(a, low), min(last if b is None else b, high))
                         for a, b in (age_bands if age_bands is not None else age["bands"]))
        elif node == "under_18":
            bands.extend([(max(first, low), min(17, high)), (max(18, low), min(last, high))])
    walk(options)
    if steps:  # analysis_r/theme.R draw_ages: bars of two years, from an even age
        bands.extend((max(b, low), min(b + 1, high))
                     for b in range(first - first % 2, last + 1, 2))
    return list(OrderedDict.fromkeys(b for b in bands if b[0] <= b[1]))


def shown_figures(source, spec, options=None, start=None, newest=None, age_bands=None,
                  steps=False):
    """C65 point 2: what a statistic shows, as figures for one_year_under_18's `shown`: each
    of its bands over the days of its period, held against every value of every field (a
    statistic shows a table, sums and parts of its records, so no filter of it narrows what
    it is held against)."""
    runs = _span(spec["period"], start, newest)
    return ([(runs, {}, band)
             for band in shown_bands(source, spec, options, age_bands, steps)] if runs else [])


def _day(value):
    return value if isinstance(value, date) else date.fromisoformat(str(value))


def coverage(source, copy):
    """(first day, newest record's day) the copy covers."""
    return date.fromisoformat(source["coverage_start"]), copy.newest_day


def covers_text(source, copy):
    start, newest = coverage(source, copy)
    return f"{day_text(start)} to {day_text(newest)}"


def group_labels(source, by, period, newest):
    """Every group of one breakdown, in order, including those that will hold 0 (C6)."""
    first, last, years = bounds(period)
    last = min(last, newest)
    if by == "year":
        return [str(y) for y in (sorted(years) if years else range(first.year, last.year + 1))
                if y <= last.year]
    if by == "month":
        out, y, m = [], first.year, first.month
        while (y, m) <= (last.year, last.month):
            if years is None or y in years:
                out.append(f"{MONTHS[m - 1]} {y}")
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        return out
    if by == "weekday":
        return list(WEEKDAYS)
    if by == "hour":
        return [hour_label(h) for h in range(24)]
    if by == "age_band":
        return [f"ages {a} to {b}" for a, b in _age_field(source)["bands"]]
    f = _fields(source)[by]
    return [f["yes"], f["no"]] if f["kind"] == "flag" else _labels(f)


def kept_labels(source, by, labels, filters):
    """S3A C68: the groups of a breakdown that a filter on the same field keeps, in order. A
    group the person left out ("without district 8") is not listed with 0. With no filter on
    the field, every group, as C6 has it."""
    age = _age_field(source)
    name = age["name"] if by == "age_band" and age is not None else by
    flt = next((f for f in filters if f.get("field") == name), None)
    if flt is None:
        return labels
    if by == "age_band":
        low, high = flt.get("from", age["usable"][0]), flt.get("to", age["usable"][1])
        return [label for label, (a, b) in zip(labels, age["bands"]) if a <= high and low <= b]
    if by == "hour":
        keep = {hour_label(h) for h in _hours(flt)}
        return [label for label in labels if label in keep]
    if isinstance(flt.get("in"), list):
        return [label for label in labels if label in flt["in"]]
    f = _fields(source).get(by)
    if f is not None and f["kind"] == "flag" and isinstance(flt.get("is"), bool):
        return [f["yes"] if flt["is"] else f["no"]]
    return labels


def check_spec(source, copy, raw):
    """The whole spec checked against the source file and the copy (C5), tidied:
    {"source", "period", "filters", "group_by"}. Raises SpecError."""
    group_by = check_group_by(source, raw.get("group_by"))
    filters = check_filters(source, raw.get("filters"))
    period = check_period(raw.get("period"))
    start, newest = coverage(source, copy)
    first, last, years = bounds(period)
    inside = (any(date(y, 12, 31) >= start and date(y, 1, 1) <= newest for y in years)
              if years else not (last < start or first > newest))
    if not inside:
        raise SpecError("OUT_OF_COVERAGE", covers=covers_text(source, copy))
    groups = 1
    for by in group_by:
        groups *= len(group_labels(source, by, period, newest))
    if groups > MAX_GROUPS:
        raise SpecError("TOO_MANY", why=f"more than {MAX_GROUPS} groups")
    filters = [f for f in filters if not _every_value(source, f, group_by)]  # C31
    group_by = [by for by in group_by if not _one_group(source, by, filters, first, last)]
    return {"source": source["id"], "period": period, "filters": filters, "group_by": group_by}


def _every_value(source, flt, group_by):
    """C31: a filter that names every value of a field the request also breaks down by leaves
    out nothing the breakdown keeps, so it is dropped (the count and its groups are the same,
    and the reply does not list every value)."""
    by = flt["field"]
    if by not in group_by or not isinstance(flt.get("in"), list):
        return False
    if by == "weekday":
        return len(set(flt["in"])) == 7
    f = _fields(source).get(by)
    return f is not None and f["kind"] == "category" and set(_labels(f)) <= set(flt["in"])


def _one_group(source, by, filters, first, last):
    """C26: the request's own period or filters fix this breakdown to one value."""
    if by == "year":
        return first.year == last.year
    flt = next((f for f in filters if f["field"] == by), None)
    if flt is None:
        return False
    if by == "weekday":
        return len(flt["in"]) == 1
    kind = _fields(source).get(by, {}).get("kind")
    return kind == "flag" or (kind == "category" and len(flt["in"]) == 1)


# ---- counting ------------------------------------------------------------------------------

def _usable_age(value, f):
    if not isinstance(value, str) or not value.isdigit():
        return None
    age = int(value)
    return age if f["usable"][0] <= age <= f["usable"][1] else None


def _placeable(row, f):
    value = row.get(f["name"])
    if f["kind"] == "age":
        return _usable_age(value, f) is not None
    if f["kind"] == "category":
        return value in f["values"]
    return value in (f["yes_raw"], f["no_raw"])


def _record_field(source, name):
    """The source field a filter or breakdown uses, or None for one made from the time."""
    if name in ("weekday", "hour", "year", "month"):
        return None
    return _age_field(source) if name == "age_band" else _fields(source)[name]


def _matches(row, flt, f, day, hour):
    name = flt["field"]
    if name == "weekday":
        return WEEKDAYS[day.weekday()] in flt["in"]
    if name == "hour":
        low, high = flt["from"], flt["to"]
        return low <= hour <= high if low <= high else hour >= low or hour <= high
    value = row[f["name"]]
    if f["kind"] == "age":
        age = int(value)
        return flt.get("from", age) <= age <= flt.get("to", age)
    if f["kind"] == "flag":
        return (value == f["yes_raw"]) is flt["is"]
    return f["values"][value] in flt["in"]


def _group_of(row, by, f, day, hour, source):
    if by == "year":
        return str(day.year)
    if by == "month":
        return f"{MONTHS[day.month - 1]} {day.year}"
    if by == "weekday":
        return WEEKDAYS[day.weekday()]
    if by == "hour":
        return hour_label(hour)
    if by == "age_band":
        age = int(row[f["name"]])
        return next(f"ages {a} to {b}" for a, b in f["bands"] if a <= age <= b)
    if f["kind"] == "flag":
        return f["yes"] if row[f["name"]] == f["yes_raw"] else f["no"]
    return f["values"][row[f["name"]]]


def tally(source, rows, spec, newest):
    """{"total", "groups": [[label, n]] or None, "grid": [[label, label, n]] or None,
    "left_out": {field: n}}. A record that matches the rest of the spec but has no usable
    value for a field the spec uses is left out (C2), counted under that field."""
    time_field = source["time_field"]
    start = date.fromisoformat(source["coverage_start"])
    first, last, years = bounds(spec["period"])
    filters, group_by = spec["filters"], spec["group_by"]
    used = OrderedDict()
    for name in [flt["field"] for flt in filters] + group_by:
        f = _record_field(source, name)
        if f is not None:
            used[f["name"]] = f
    checks = [(flt, _record_field(source, flt["field"])) for flt in filters]
    parts = [(by, _record_field(source, by)) for by in group_by]
    labels = [kept_labels(source, by, group_labels(source, by, spec["period"], newest), filters)
              for by in group_by]  # S3A C68: only the groups the filters keep
    counts = OrderedDict(((a,) if len(labels) == 1 else (a, b), 0)
                         for a in (labels[0] if labels else [])
                         for b in (labels[1] if len(labels) == 2 else [None]))
    left_out = {name: 0 for name in used}
    total = 0
    for row in rows:
        when = row.get(time_field)
        try:
            day, hour = date.fromisoformat(when[:10]), int(when[11:13])
        except (TypeError, ValueError):
            continue  # ponytail: a record with no readable time is in no period
        if day < start or day > newest or \
                not (day.year in years if years else first <= day <= last):
            continue
        gaps = [name for name, f in used.items() if not _placeable(row, f)]
        if not all(_matches(row, flt, f, day, hour) for flt, f in checks
                   if f is None or f["name"] not in gaps):
            continue
        if gaps:
            for name in gaps:
                left_out[name] += 1
            continue
        total += 1
        if parts:
            key = tuple(_group_of(row, by, f, day, hour, source) for by, f in parts)
            counts[key] += 1
    return {"total": total,
            "groups": [[k[0], n] for k, n in counts.items()] if len(labels) == 1 else None,
            "grid": [[k[0], k[1], n] for k, n in counts.items()] if len(labels) == 2 else None,
            "left_out": left_out}


def too_fine(values, floor):
    """C5: more than half of the groups that have any record would be hidden."""
    nonzero = [n for n in values if n >= 1]
    return 2 * sum(1 for n in nonzero if n < floor) > len(nonzero)


def count(source, copy, rows, spec):
    """The figures of a checked spec, or SpecError TOO_FINE naming the one-way breakdowns
    that would not be too fine."""
    figures = tally(source, rows, spec, copy.newest_day)
    values = [g[-1] for g in (figures["groups"] or figures["grid"] or [])]
    if values and too_fine(values, source["floor"]):
        fine = []
        for by in usable_names(source)["group_by"]:
            if by in spec["group_by"]:
                continue
            other = dict(spec, group_by=[by])
            try:
                check_spec(source, copy, other)
            except SpecError:
                continue
            groups = tally(source, rows, other, copy.newest_day)["groups"]
            if not too_fine([n for _, n in groups], source["floor"]):
                fine.append(by)
        raise SpecError("TOO_FINE", why=f"more than half the groups would be under "
                                        f"{source['floor']}", would_work=fine)
    return figures


# ---- the phrases (C6) ----------------------------------------------------------------------

def _age_fragment(flt):
    low, high = flt.get("from"), flt.get("to")
    if low is not None and high is not None:
        return f"aged {low}" if low == high else f"aged {low} to {high}"
    return f"aged {low} and over" if low is not None else f"under {high + 1}"


def _wording(f, flt):
    return f["wording"].replace("{labels}", join_and(flt["in"]))


def _weekday_words(days):
    if days == ["Saturday", "Sunday"]:
        return "weekends"
    if days == WEEKDAYS[:5]:
        return "weekdays"
    return join_and(days)


def segments(source, filters):
    """The `<what>` of C6 in its order, as [(key, phrase, label)]: phrase as the count phrase
    writes it, label as a compare or a kept note names it."""
    fields = _fields(source)
    by_field = {flt["field"]: flt for flt in filters}
    person = []
    for f in source["fields"]:
        flt = by_field.get(f["name"])
        if flt is None:
            continue
        if f["kind"] == "age":
            person.insert(0, _age_fragment(flt))
        elif f["kind"] == "category" and f.get("person"):
            person.append(_wording(f, flt))
    out = [("person", "of people " + ", ".join(person), "people " + ", ".join(person))] \
        if person else []
    for f in source["fields"]:
        flt = by_field.get(f["name"])
        if flt is not None and f["kind"] == "category" and not f.get("person"):
            out.append((f["name"], _wording(f, flt), join_and(flt["in"])))
    for f in source["fields"]:
        flt = by_field.get(f["name"])
        if flt is not None and f["kind"] == "flag":
            text = fields[f["name"]]["yes" if flt["is"] else "no"]
            out.append((f["name"], text, text))
    if "weekday" in by_field:
        words = _weekday_words(by_field["weekday"]["in"])
        out.append(("weekday", "on " + words, words))
    if "hour" in by_field:
        h = by_field["hour"]
        words = f"between {hour_label(h['from'])} and {hour_label(h['to'])}"
        out.append(("hour", words, words))
    return out


def filter_label(source, flt):
    """How a kept note names one filter: `district 3`, `people recorded as female`."""
    ((_, _, label),) = segments(source, [flt])
    return label


def period_words(period):
    """`in 2025`; `in 2024 and 2025`; `from January to October 2025`; `from 1 March 2025 to
    31 August 2025`."""
    if "years" in period:
        return "in " + join_and(period["years"])
    if "year" in period:
        if "months" in period:
            m = period["months"]
            if m["from"] == m["to"]:  # ponytail: one month reads better than "from March to March"
                return f"in {MONTHS[m['from'] - 1]} {period['year']}"
            return f"from {MONTHS[m['from'] - 1]} to {MONTHS[m['to'] - 1]} {period['year']}"
        return f"in {period['year']}"
    first, last = date.fromisoformat(period["from"]), date.fromisoformat(period["to"])
    return f"from {day_text(first)} to {day_text(last)}"


def period_label(period):
    words = period_words(period)
    return words[3:] if words.startswith("in ") else words


def cut_suffix(period, newest):
    """C6: a period that reaches past the copy's newest record is cut to it."""
    return (f" (through {day_text(newest)}, the latest in this copy)"
            if bounds(period)[1] > newest else "")


def read_as(source, spec, newest):
    """The count phrase without its number (C5)."""
    parts = [source["unit"]["many"]] + [phrase for _, phrase, _ in segments(source, spec["filters"])]
    return " ".join(parts) + " " + period_words(spec["period"]) + cut_suffix(spec["period"], newest)


def _a(word):
    return ("an " if word[:1].lower() in "aeiou" else "a ") + word


def recorded_suffix(source, spec, left_out):
    """C15: ` with a district recorded`, ` with a usable age`, ` with a district and a
    bureau recorded`: what the counted records have, when a field the spec breaks down by
    left records out. Empty when none did."""
    fields = _fields(source)
    age = _age_field(source)
    usable_age, recorded = False, []
    for by in spec["group_by"]:
        if by == "age_band":
            usable_age = age is not None and bool(left_out.get(age["name"]))
        elif by in fields and left_out.get(by):
            recorded.append(_a(fields[by]["dimension"]))
    parts = (["a usable age"] if usable_age else []) + \
        ([join_and(recorded) + " recorded"] if recorded else [])
    return " with " + " and ".join(parts) if parts else ""


def _count_phrase(result, suffix=""):
    n, floor, unit = result["total"], result["floor"], result["unit"]
    words = unit["one"] if shown(n, floor) == "1" else unit["many"]
    return f"{shown(n, floor)} {words}{result['read_as'][len(unit['many']):]}{suffix}"


def _fewer(count, floor):
    return f"fewer than {floor}" + (" each" if count > 1 else "")


def groups_phrase(dimension, groups, floor):
    """`by district, district 2 and district 3 had the most (45 each) and district 6 the
    fewest (20)`; all equal: `by gender, every group had the same count (65)`. C16: hidden
    values are never ranked against each other: with no group at 0, the fewest side names
    every hidden group, `(fewer than 10 each)`, whatever their values."""
    values = [n for _, n in groups]
    high, low = max(values), min(values)
    if len(groups) == 1 and not is_hidden(high, floor):  # C68: one group kept by the filter
        return f"by {dimension}, all of them were in {groups[0][0]}"
    hidden = [label for label, n in groups if is_hidden(n, floor)]
    if is_hidden(high, floor):  # every group is hidden or 0 (TOO_FINE comes first in a count)
        return f"by {dimension}, no group had as many as {floor}"
    if high == low:
        return f"by {dimension}, every group had the same count ({shown(high, floor)})"

    def side(n):
        labels = [label for label, v in groups if v == n]
        return join_and(labels), shown(n, floor) + (" each" if len(labels) > 1 else "")
    top, top_n = side(high)
    if hidden and low != 0:
        bottom, bottom_n = join_and(hidden), _fewer(len(hidden), floor)
    else:
        bottom, bottom_n = side(low)
    return f"by {dimension}, {top} had the most ({top_n}) and {bottom} the fewest ({bottom_n})"


def dimension_of(source, by):
    return DIMENSION_WORDS.get(by) or _fields(source)[by]["dimension"]


def count_result(source, copy, spec, figures):
    """A count result: its spec, exact figures, what is shown, and its phrases (C6, C8)."""
    newest = copy.newest_day
    result = {"kind": "count", "source": source["id"], "spec": spec,
              "read_as": read_as(source, spec, newest), "unit": dict(source["unit"]),
              "floor": source["floor"], "total": figures["total"], "groups": figures["groups"],
              "grid": figures["grid"], "left_out": figures["left_out"],
              "dimensions": [dimension_of(source, by) for by in spec["group_by"]],
              "copy": {"sha256": copy.sha256, "date": copy.day.isoformat(),
                       "fetched_at": copy.fetched_at, "newest": newest.isoformat(),
                       "rows": copy.rows}}
    result["phrases"] = {"count": _count_phrase(
        result, recorded_suffix(source, spec, figures["left_out"]))}
    if figures["groups"] is not None:
        result["phrases"]["groups"] = groups_phrase(result["dimensions"][0], figures["groups"],
                                                    source["floor"])
    return result


def share_result(source, part, whole):
    """C7: the part's spec is the whole's plus one or more filters, same source and
    period, neither value hidden; else BAD_SHARE. `<p>% of the <whole> were <part>`."""
    p, w = part["spec"], whole["spec"]
    whole_filters = w["filters"]
    added = [flt for flt in p["filters"] if flt not in whole_filters]
    if (part["source"] != whole["source"] or p["period"] != w["period"]
            or p["group_by"] != w["group_by"] or not added
            or any(flt not in p["filters"] for flt in whole_filters)):
        raise SpecError("BAD_SHARE", why="the part must be the whole's count plus one or more "
                                         "filters, from the same source and period")
    floor = whole["floor"]
    if is_hidden(part["total"], floor) or is_hidden(whole["total"], floor) or whole["total"] == 0:
        raise SpecError("BAD_SHARE", why="no share can be given of a count under "
                                         f"{floor} or of nothing")
    n, of = part["total"], whole["total"]
    percent = "0" if n == 0 else ("under 1" if 200 * n < of else str((200 * n + of) // (2 * of)))
    what = " ".join(phrase for _, phrase, _ in segments(source, added))
    return {"kind": "share", "source": whole["source"], "part": n, "whole": of,
            "percent": percent,
            "phrases": {"share": f"{percent}% of the {whole['phrases']['count']} were {what}"}}


def _labels_for_compare(source, counts):
    """C6: each result's label is the part of its count phrase on which the compared specs
    differ (`2024`; `district 3`; `people aged 18 to 21`); when a part is missing from one
    of them, the whole phrase without its number."""
    parts = []
    for r in counts:
        found = {key: label for key, _, label in segments(source, r["spec"]["filters"])}
        found["period"] = period_label(r["spec"]["period"]) + cut_suffix(
            r["spec"]["period"], date.fromisoformat(r["copy"]["newest"]))
        parts.append(found)
    every = [flt for r in counts for flt in r["spec"]["filters"]]
    order = [key for key, _, _ in segments(source, every)] + ["period"]
    keys = [k for k in OrderedDict.fromkeys(order) if len({json.dumps(p.get(k)) for p in parts}) > 1]
    if not keys or any(k not in p for p in parts for k in keys):
        return [r["read_as"] for r in counts]
    labels = [", ".join(p[k] for k in keys) for p in parts]
    return labels if len(set(labels)) == len(labels) else [r["read_as"] for r in counts]


def compare_result(source, counts):
    """C7 and A6: the highest, the lowest and the difference; with a hidden value, no
    difference (C6, C8.5)."""
    if len({r["source"] for r in counts}) != 1:
        raise SpecError("MIXED_SOURCES", why="counts of different sources are never compared")
    labels = _labels_for_compare(source, counts)
    totals = [r["total"] for r in counts]
    floor = counts[0]["floor"]
    top, bottom = max(totals), min(totals)
    top_label = join_and([lb for lb, t in zip(labels, totals) if t == top])
    bottom_label = join_and([lb for lb, t in zip(labels, totals) if t == bottom])
    hidden_labels = [lb for lb, t in zip(labels, totals) if is_hidden(t, floor)]
    zero_labels = [lb for lb, t in zip(labels, totals) if t == 0]
    hidden = bool(hidden_labels)
    if hidden and len(hidden_labels) == len(totals):  # C16: every value hidden
        phrase = f"the counts for {join_and(hidden_labels)} were each fewer than {floor}"
    elif hidden and len(hidden_labels) + len(zero_labels) == len(totals):
        phrase = (f"{join_and(hidden_labels)} {'each ' if len(hidden_labels) > 1 else ''}had "
                  f"fewer than {floor} and {join_and(zero_labels)} had 0")
    elif hidden and zero_labels:  # the lowest is 0; a hidden value is never ranked
        phrase = (f"{top_label} had the highest count ({shown(top, floor)}) and "
                  f"{join_and(zero_labels)} the lowest (0)")
    elif hidden:  # C16: the lowest side names every hidden result
        phrase = (f"{top_label} had the highest count ({shown(top, floor)}) and "
                  f"{join_and(hidden_labels)} the lowest "
                  f"({_fewer(len(hidden_labels), floor)})")
    elif top == bottom:
        phrase = f"the counts were the same ({shown(top, floor)}) for {join_and(labels)}"
    else:
        phrase = (f"{top_label} had the highest count ({shown(top, floor)}) and {bottom_label} "
                  f"the lowest ({shown(bottom, floor)}), a difference of {top - bottom:,}")
    return {"kind": "compare", "source": counts[0]["source"], "top_value": top,
            "bottom_value": bottom, "difference": None if hidden else top - bottom,
            "phrases": {"compare": phrase}}


def partial_months(counts):
    """C58: every compared period is a year with the same months, in two or more years, one
    the copy's newest year, the last month the copy's newest and unfinished in it: that year
    and the months up to the one before (`to` below `from` when none is finished). Else None."""
    periods = [r["spec"]["period"] for r in counts]
    if not all(set(p) == {"year", "months"} for p in periods):
        return None
    spans = {(p["months"]["from"], p["months"]["to"]) for p in periods}
    years = {p["year"] for p in periods}
    newest = date.fromisoformat(counts[0]["copy"]["newest"])
    if len(spans) != 1 or len(years) < 2 or newest.year not in years:
        return None
    first, last = next(iter(spans))
    if last != newest.month or newest.day == calendar.monthrange(newest.year, newest.month)[1]:
        return None
    return {"year": newest.year, "from": first, "to": last - 1}


def partial_year(source, counts):
    """C7: compared periods are whole years and one is the copy's last, unfinished year:
    the last finished month M, else None. Python decides M."""
    periods = [r["spec"]["period"] for r in counts]
    newest = date.fromisoformat(counts[0]["copy"]["newest"])
    if not all(set(p) == {"year"} for p in periods) or len({p["year"] for p in periods}) < 2:
        return None
    if newest.month == 12 and newest.day == 31 or newest.year not in {p["year"] for p in periods}:
        return None
    last_day = calendar.monthrange(newest.year, newest.month)[1]
    return {"year": newest.year,
            "months": {"from": 1, "to": newest.month if newest.day == last_day else newest.month - 1}}
