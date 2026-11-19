"""Helpers for the stage 3 Part A tests. The contract is docs/S3A-DESIGN.md (C0 to C13); it
adds to the agent loop of docs/P1A-DESIGN.md with docs/P1A-R2-DESIGN.md, which still hold.

What is here, and the readings it takes (each is listed in kit-log/raw/S3A-A-notes.txt):

- The fixtures (tests/s3/fixtures/, made by make_fixtures.py): two SYNTHETIC source files
  in the shape of C3 and the rows a fake transport serves for each. Every row id starts
  with FIXTURE-; every address is on the reserved .invalid domain.
- The truth: `truth()` counts the fixture rows with loops and dictionaries only. Nothing
  here imports moco_agent to count, and nothing copies a phrase from the program. Expected
  phrases are written out by hand in each test, from C6.
- `FakeService`, the fake transport given to sources.fetch. It answers the way the county's
  Socrata service does: a JSON list of row objects, a key left out when its value is empty,
  `$limit` (default 1000), `$offset`, `$order`, `$select` and a simple `$where` (`field >
  'value'`). Without `$order`, or with an `$order` on a field whose values repeat, each
  request sees the rows in a different order, so paging that is not ordered on a unique
  field overlaps and loses rows. It can fail on purpose: a network error, a redirect, an
  error page, an error object.
  READING (the contract gives no shape for `transport`): fetch calls the transport like
  `requests.get` (url, params=...), like `requests.request` (method, url, ...), with one
  request dict, or through `.get(...)`/`.request(...)`; it gets back a response object
  with `status_code`/`status`, `headers`, `text`/`content`/`read()`, `json()` and `url`.
  A network error is an OSError (ConnectionError, TimeoutError).
- `use_sources(monkeypatch, folder)`: READING (C4 names `load_sources(folder=None)` as the
  one reader of the source files, and `fetch`, `latest` and the turn take no folder): every
  part of the program that needs the source files gets them by calling
  `sources.load_sources()` when it needs them. The tests replace that function, in every
  moco_agent module that holds it, by one whose default folder is a test folder.
- `CountyEnv`: one county-mode agent (MOCO_DATA=county, MOCO_STATE_DIR in tmp_path) with
  its own sources folder, copies made through the FakeService, settings, store, runs
  folder and clock. Turns go through agent.handle_question with the same arguments as in
  stage 2 (no new argument), and the FakeModel of tests/p1/p1support.py.
- Tool calls of county mode (C0, C5, C7) and the parts of a county reply (C10), as regexes
  that accept one space, one line break or one blank line between the parts Python adds
  (the contract gives their order, not what joins them; the table is one line per group,
  so it starts on a new line). The date of a copy is accepted as `12 November 2026`,
  `November 12, 2026` or `2026-11-12` (the contract does not say how it is written).
"""
import calendar
import copy
import hashlib
import json
import re
import shutil
import sys
import zlib
from collections import OrderedDict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from p1support import (FakeClock, FakeModel, LEAVE_OUT, Step, THREAD_1, USER, call, describe,
                       ask_user, decline, deep_leaves, finish, has_leaf, leaves, load_registry,
                       make_settings, messages_text, mod, numbers_in, open_store, show_details,
                       tool_messages)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
FIXTURES = HERE / "fixtures"
FIXTURE_SOURCES = FIXTURES / "sources"
FIXTURE_ROWS = FIXTURES / "rows"
NAMES = ("arrests_like", "coded_like")
A_ID = "FIXTURE:arrests_like"
C_ID = "FIXTURE:coded_like"
REAL_SOURCES = REPO / "config" / "sources"
AGENT_PROMPT_S3 = REPO / "config" / "agent_prompt_s3.md"  # C0: the prompt in county mode

# The copy is made "today" in these tests; turns come an hour later. 15:00 UTC is the same
# calendar day in UTC and in the county's time zone, so the date of the copy reads the same
# either way.
TODAY_S3 = date(2026, 11, 12)
COPY_NOW = datetime(2026, 11, 12, 15, 0, 0, tzinfo=timezone.utc)
NOW_S3 = datetime(2026, 11, 12, 16, 0, 0, tzinfo=timezone.utc)
COPY_DATE_RE = r"(?:12 November 2026|November 12, 2026|2026-11-12)"

WEEKDAYS = list(calendar.day_name)          # Monday first
MONTH_NAMES = list(calendar.month_name)[1:]  # January first
FLOOR = 10

# The two fixtures' facts, read from their files (fixed, so named here for the tests).
NEWEST = {"arrests_like": date(2026, 9, 17), "coded_like": date(2026, 8, 20)}
LAST_FINISHED_MONTH = {"arrests_like": 8, "coded_like": 7}  # C7's M for each copy


def source_id(name):
    return {"arrests_like": A_ID, "coded_like": C_ID}[name]


def name_of(sid):
    return {A_ID: "arrests_like", C_ID: "coded_like"}[sid]


def source_json(name):
    """The fixture's source file, as a dict (a fresh copy each time)."""
    return json.loads((FIXTURE_SOURCES / f"{name}.json").read_text(encoding="utf-8"))


def fixture_rows(name):
    """The rows the fake transport serves for the fixture (a fresh copy each time)."""
    return json.loads((FIXTURE_ROWS / f"{name}.json").read_text(encoding="utf-8"))["rows"]


def field(name, field_name, src=None):
    src = src or source_json(name)
    (found,) = [f for f in src["fields"] if f["name"] == field_name]
    return found


def key_field(src):
    (found,) = [f["name"] for f in src["fields"] if f["kind"] == "key"]
    return found


def row_id(row):
    return row.get("id", row.get("case_no"))


# ---- numbers as a person reads them (written from C6 and C8 by hand) ----------------------

def fmt(n):
    """C6: a comma from 1,000 up."""
    return f"{n:,}"


def shown(n, floor=FLOOR):
    """C8: a value from 1 to floor - 1 is written `fewer than 10`; 0 is `0`."""
    return f"fewer than {floor}" if 1 <= n <= floor - 1 else fmt(n)


def is_hidden(n, floor=FLOOR):
    return 1 <= n <= floor - 1


def too_fine(values, floor=FLOOR):
    """C5 TOO_FINE: more than half of the groups that have any record would be hidden."""
    nonzero = [n for n in values if n >= 1]
    hidden = [n for n in nonzero if n < floor]
    return 2 * len(hidden) > len(nonzero)


def hour_label(hour):
    """C6: `10 pm`. Hours 0 and 12 are not labelled here (the contract does not say how);
    the tests keep them out of every label they check."""
    assert hour not in (0, 12), "the contract does not say how 0 and 12 are written"
    return f"{hour} am" if hour < 12 else f"{hour - 12} pm"


def month_label(year, month):
    return f"{MONTH_NAMES[month - 1]} {year}"


def day_text(d):
    """C6: `1 March 2025`, `9 November 2026`."""
    return f"{d.day} {MONTH_NAMES[d.month - 1]} {d.year}"


def join_and(items):
    """`A`, `A and B`, `A, B and C` (as analysis.join_and does; written here by hand)."""
    items = [str(i) for i in items]
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


# ---- the truth: plain counting -------------------------------------------------------------

def _time(row, src):
    text = row.get(src["time_field"])
    return date.fromisoformat(text[:10]), int(text[11:13])


def _last_day(year, month):
    return date(year, month, calendar.monthrange(year, month)[1])


def period_bounds(period):
    """(first day, last day, set of years or None) of a C5 period, as written."""
    if "years" in period:
        years = sorted(period["years"])
        return date(years[0], 1, 1), date(years[-1], 12, 31), set(years)
    if "year" in period:
        y = period["year"]
        if "months" in period:
            m = period["months"]
            return date(y, m["from"], 1), _last_day(y, m["to"]), None
        return date(y, 1, 1), date(y, 12, 31), None
    return date.fromisoformat(period["from"]), date.fromisoformat(period["to"]), None


def in_period(day, period):
    first, last, years = period_bounds(period)
    if years is not None:
        return day.year in years
    return first <= day <= last


def is_cut(name, period):
    """C6: the period reaches past the copy's newest record (it is then cut to it)."""
    return period_bounds(period)[1] > NEWEST[name]


def _usable_age(row, f):
    text = row.get(f["name"])
    if not isinstance(text, str) or not re.fullmatch(r"[0-9]+", text):
        return None  # empty, missing, not a number, or not a whole number
    age = int(text)
    low, high = f["usable"]
    return age if low <= age <= high else None


def _placeable(row, f):
    kind = f["kind"]
    if kind == "age":
        return _usable_age(row, f) is not None
    if kind == "category":
        return row.get(f["name"]) in f["values"]
    if kind == "flag":
        return row.get(f["name"]) in (f["yes_raw"], f["no_raw"])
    raise AssertionError(f"not a countable field: {f}")


def _label(row, f):
    """The label a placeable row has for field f (an int for age)."""
    if f["kind"] == "age":
        return _usable_age(row, f)
    if f["kind"] == "category":
        return f["values"][row[f["name"]]]
    return f["yes"] if row[f["name"]] == f["yes_raw"] else f["no"]


def _matches(row, flt, src):
    name = flt["field"]
    day, hour = _time(row, src)
    if name == "weekday":
        return WEEKDAYS[day.weekday()] in flt["in"]
    if name == "hour":
        low, high = flt["from"], flt["to"]
        return low <= hour <= high if low <= high else hour >= low or hour <= high
    f = field(None, name, src)
    value = _label(row, f)
    if f["kind"] == "age":
        return (flt.get("from") is None or value >= flt["from"]) and \
               (flt.get("to") is None or value <= flt["to"])
    if f["kind"] == "flag":
        return (value == f["yes"]) is bool(flt["is"])
    wanted = [flt["is"]] if "is" in flt else list(flt["in"])
    return value in wanted


def _record_field(name, src):
    """The source field a filter or breakdown uses, or None for one made from the time."""
    if name in ("weekday", "hour", "year", "month"):
        return None
    if name == "age_band":
        (f,) = [f for f in src["fields"] if f["kind"] == "age"]
        return f
    return field(None, name, src)


def group_labels(name, by, period, src=None):
    """Every group of a breakdown, in order (C6: every value the file lists, or every period
    in the range, including those with 0; a range is cut to the copy's newest record).
    Category labels in file order (a label once), a flag's yes then no, the file's bands,
    years and months in time order, Monday to Sunday, hours 0 to 23 (as ints)."""
    src = src or source_json(name)
    first, last, years = period_bounds(period)
    last = min(last, NEWEST[name])
    if by == "year":
        return [str(y) for y in (sorted(years) if years else range(first.year, last.year + 1))]
    if by == "month":
        out, y, m = [], first.year, first.month
        while (y, m) <= (last.year, last.month):
            if years is None or y in years:
                out.append(month_label(y, m))
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        return out
    if by == "weekday":
        return list(WEEKDAYS)
    if by == "hour":
        return list(range(24))
    f = _record_field(by, src)
    if by == "age_band":
        return [f"ages {a} to {b}" for a, b in f["bands"]]
    if f["kind"] == "flag":
        return [f["yes"], f["no"]]
    return list(OrderedDict.fromkeys(f["values"].values()))


def _group_of(row, by, src):
    day, hour = _time(row, src)
    if by == "year":
        return str(day.year)
    if by == "month":
        return month_label(day.year, day.month)
    if by == "weekday":
        return WEEKDAYS[day.weekday()]
    if by == "hour":
        return hour
    f = _record_field(by, src)
    if by == "age_band":
        age = _usable_age(row, f)
        (a, b), = [(a, b) for a, b in f["bands"] if a <= age <= b]
        return f"ages {a} to {b}"
    return _label(row, f)


def _c68_kept(by, labels, filters, src):
    """S3A C68 (D-085; added by the planning chat on 18 Nov, without a tests session, by Nino's
    decision): a breakdown lists only the groups that a filter on the same field keeps."""
    if by == "age_band":
        age = next(f for f in src["fields"] if f.get("kind") == "age")
        flt = next((x for x in filters if x["field"] == age["name"]), None)
        if flt is None:
            return labels
        low, high = flt.get("from", age["usable"][0]), flt.get("to", age["usable"][1])
        return [label for label, (a, b) in zip(labels, age["bands"]) if a <= high and low <= b]
    flt = next((x for x in filters if x["field"] == by), None)
    if flt is None:
        return labels
    if by == "hour":
        a, b = flt["from"], flt["to"]
        return [h for h in labels if (a <= h <= b if a <= b else h >= a or h <= b)]
    if "in" in flt:
        return [label for label in labels if label in flt["in"]]
    if "is" in flt:
        f = _record_field(by, src)
        return [f["yes"] if flt["is"] else f["no"]]
    return labels


def truth(name, period, filters=(), group_by=(), rows=None, src=None):
    """The figures a correct count gives, by plain counting of the fixture rows.

    Returns {"total": int, "groups": OrderedDict(label -> n) for a one-way breakdown or None,
    "grid": {(label1, label2): n} for a two-way one or None, "left_out": {field name: n} for
    each source field the spec uses}.

    C3 and C2: a record whose value for a field the spec uses is empty, missing, not listed
    (or an age not usable) is left out: counted under that field, not in the total. A
    record is left out only when everything else about it matches the spec (the fixtures
    never have two gaps in one row, so no record is left out twice)."""
    src = src or source_json(name)
    rows = fixture_rows(name) if rows is None else rows
    filters, group_by = list(filters), list(group_by)
    used = OrderedDict()
    for part in [f["field"] for f in filters] + group_by:
        f = _record_field(part, src)
        if f is not None:
            used[f["name"]] = f
    labels = [_c68_kept(by, group_labels(name, by, period, src), filters, src)
              for by in group_by]
    groups = OrderedDict((label, 0) for label in labels[0]) if len(group_by) == 1 else None
    grid = ({(a, b): 0 for a in labels[0] for b in labels[1]} if len(group_by) == 2 else None)
    left_out = {f: 0 for f in used}
    total = 0
    for row in rows:
        day, _ = _time(row, src)
        if not in_period(day, period):
            continue
        gaps = [n for n, f in used.items() if not _placeable(row, f)]
        rest = [flt for flt in filters if _record_field(flt["field"], src) is None
                or _record_field(flt["field"], src)["name"] not in gaps]
        if not all(_matches(row, flt, src) for flt in rest):
            continue
        if gaps:
            for n in gaps:
                left_out[n] += 1
            continue
        total += 1
        keys = [_group_of(row, by, src) for by in group_by]
        if groups is not None:
            groups[keys[0]] += 1
        if grid is not None:
            grid[tuple(keys)] += 1
    return {"total": total, "groups": groups, "grid": grid, "left_out": left_out}


def most_and_fewest(groups):
    """(labels with the most, the most, labels with the fewest, the fewest), labels in the
    order of the groups."""
    values = list(groups.values())
    high, low = max(values), min(values)
    return ([k for k, v in groups.items() if v == high], high,
            [k for k, v in groups.items() if v == low], low)


# ---- text a person must never see as a figure ---------------------------------------------

_MONTH = "(?:" + "|".join(MONTH_NAMES) + ")"
_NON_FIGURES = [
    r"https?://\S+",
    r"\b(?:district|station) \d+\b",
    rf"\b\d{{1,2}} {_MONTH} \d{{4}}\b",
    rf"\b{_MONTH} \d{{1,2}}, \d{{4}}\b",
    rf"\b{_MONTH} \d{{4}}\b",
    r"\b\d{4}-\d{2}-\d{2}(?:T[0-9:.]+Z?)?",
    r"\b(?:19|20)\d{2}\b",
    r"\bages? \d+ (?:to|and) \d+\b",
    r"\bages? \d+ and over\b",
    r"\baged \d+(?: to \d+| and over)?\b",
    r"\bunder \d+%",
    r"(?<![0-9,])\d+%",  # a share's percentage is not a count (C6); added in the second session
    r"\bunder \d+\b",
    r"\b\d{1,2} (?:am|pm)\b",
    r"\b500 feet\b",
    r"\bfewer than \d+\b",
]


def figures(text):
    """The numbers of `text` that stand as figures: every whole number left once the labels
    and dates that hold digits are taken out (district 3, station 2, 1 March 2025, March
    2025, 2025, ages 18 to 24, aged 21, under 18, 10 pm, 500 feet, fewer than 10, under 1%,
    an address). Digits next to a letter (r1, a hex id) are never numbers here."""
    for pattern in _NON_FIGURES:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
    return numbers_in(text)


def assert_no_hidden_figure(text, where="text"):
    """C1 and C8: no count from 1 to 9 stands as a figure."""
    bad = sorted(n for n in figures(text) if 1 <= n <= 9)
    assert not bad, f"a count from 1 to 9 ({bad}) stands as a figure in the {where}: {text!r}"


def assert_no_row(text, rows, where="text"):
    """C1: no single record: no row id and no row's exact time from the fixture."""
    for row in rows:
        rid = row_id(row)
        assert rid not in text, f"a row id ({rid}) is in the {where}"
    times = {v for row in rows for k, v in row.items() if isinstance(v, str)
             and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}", v)}
    for t in times:
        assert t[:16] not in text, f"a row's exact time ({t}) is in the {where}"
    assert "FIXTURE-" not in text, f"a row id is in the {where}"


# ---- the fake transport (C4: "Tests use a fake transport") -------------------------------

class FakeHTTPError(OSError):
    """What raise_for_status raises for a status of 400 or more."""


class FakeResponse:
    """A response as requests, httpx or urllib give one, and readable as a dict too."""

    def __init__(self, status, body, headers=None, url=""):
        self.status_code = self.status = status
        self.text = body
        self.content = body.encode("utf-8")
        self.headers = dict(headers or {"Content-Type": "application/json"})
        self.url = url
        self.ok = status < 400
        self.reason = {200: "OK", 302: "Found", 404: "Not Found", 400: "Bad Request",
                       500: "Internal Server Error"}.get(status, "")
        self.is_redirect = 300 <= status < 400

    def json(self):
        return json.loads(self.text)

    def raise_for_status(self):
        if self.status >= 400:
            raise FakeHTTPError(f"HTTP {self.status}")

    def read(self, *args):
        return self.content

    def getcode(self):
        return self.status

    def geturl(self):
        return self.url

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def _as_dict(self):
        return {"status": self.status, "status_code": self.status, "body": self.text,
                "text": self.text, "headers": self.headers, "url": self.url}

    def __getitem__(self, key):
        return self._as_dict()[key]

    def get(self, key, default=None):
        return self._as_dict().get(key, default)


ERROR_PAGE = ("<!DOCTYPE html><html><head><title>Error</title></head><body>SYNTHETIC fixture "
              "error page: the service is down.</body></html>")
FAILURES = ("network", "timeout", "redirect", "error_page", "error_json", "error_object")


class FakeService:
    """The fake transport. `rows`: what the service holds. `make_rows(n)`: rows made on the
    first request instead, n = 2 x that request's $limit (1000 when none) + 7, so that
    whatever page size the build picks, at least three pages are needed. `fail`: {request
    index from 0, or "all": one of FAILURES}. `requests`: every request, in order, as
    {"method", "url", "base", "params"}."""

    def __init__(self, rows=None, *, address, fail=None, make_rows=None):
        self.address = address
        self._rows = None if rows is None else list(rows)
        self.make_rows = make_rows
        self.fail = dict(fail or {})
        self.requests = []

    # -- the ways a build may call it ------------------------------------------------------
    def __call__(self, *args, **kwargs):
        args = list(args)
        method = kwargs.pop("method", "GET")
        url = kwargs.pop("url", None)
        params = kwargs.pop("params", None)
        if args and isinstance(args[0], dict):
            request = args.pop(0)
            method = request.get("method", method)
            url = request.get("url", url)
            params = request.get("params", params)
        if len(args) >= 2 and isinstance(args[0], str) and \
                args[0].upper() in ("GET", "HEAD", "POST"):
            method = args.pop(0)
        if args:
            url = args.pop(0)
        if args:
            params = args.pop(0)
        return self._handle(method, url, params)

    def get(self, url, params=None, **kwargs):
        return self._handle("GET", url, params)

    def request(self, method, url, params=None, **kwargs):
        return self._handle(method, url, params)

    # -- answering -------------------------------------------------------------------------
    @property
    def rows(self):
        return self._rows

    def _handle(self, method, url, params):
        url = getattr(url, "full_url", url)  # a urllib Request
        index = len(self.requests)
        parts = urlsplit(str(url))
        base = f"{parts.scheme}://{parts.netloc}{parts.path}"
        query = {k: v[-1] for k, v in parse_qs(parts.query, keep_blank_values=True).items()}
        if params:
            pairs = params.items() if hasattr(params, "items") else params
            query.update({str(k): str(v) for k, v in pairs})
        self.requests.append({"method": str(method).upper(), "url": str(url), "base": base,
                              "params": query})
        mode = self.fail.get(index, self.fail.get("all"))
        if mode:
            return self._failure(mode, str(url))
        if base != self.address:
            return self._error(404, "no such resource", url)
        return self._serve(index, query, str(url))

    @staticmethod
    def _param(query, name):
        return query.get("$" + name, query.get(name))

    def _error(self, status, message, url):
        body = json.dumps({"error": True, "code": "fixture.error", "message": message})
        return FakeResponse(status, body, {"Content-Type": "application/json"}, str(url))

    def _failure(self, mode, url):
        if mode == "network":
            raise ConnectionError("SYNTHETIC fixture: the network is down")
        if mode == "timeout":
            raise TimeoutError("SYNTHETIC fixture: the request timed out")
        if mode == "redirect":
            return FakeResponse(302, "<html><body>Moved</body></html>",
                                {"Location": "https://fixture.invalid/login",
                                 "Content-Type": "text/html"}, url)
        if mode == "error_page":
            return FakeResponse(200, ERROR_PAGE, {"Content-Type": "text/html"}, url)
        if mode == "error_json":
            return self._error(500, "SYNTHETIC fixture server error", url)
        if mode == "error_object":
            return FakeResponse(200, json.dumps({"error": True, "message": "not rows"}),
                                {"Content-Type": "application/json"}, url)
        raise AssertionError(f"unknown failure mode {mode}")

    def _serve(self, index, query, url):
        limit_text = self._param(query, "limit")
        limit = int(limit_text) if limit_text else 1000
        if self._rows is None:
            self._rows = list(self.make_rows(2 * limit + 7))
        rows = self._rows
        columns = {k for row in rows for k in row}
        select = self._param(query, "select")
        names = [s.strip() for s in select.split(",")] if select else None
        if names and any(n not in columns and n != ":id" for n in names):
            return self._error(400, "No such column", url)
        ordered = list(rows)
        where = self._param(query, "where")
        if where:
            keyset = re.fullmatch(r"\s*(:?\w+)\s*>\s*'([^']*)'\s*", where)
            if not keyset:
                return self._error(400, "Could not parse $where", url)
            name, value = keyset[1], keyset[2]
            name = None if name == ":id" else name
            ordered = [r for r in ordered if (row_id(r) if name is None else r.get(name, ""))
                       > value]

        def scramble(row):
            return zlib.crc32(f"{index}:{row_id(row)}".encode())

        order = self._param(query, "order")
        if order:
            words = order.split()
            name = words[0]
            if name not in columns and name != ":id":
                return self._error(400, "No such column", url)
            descending = len(words) > 1 and words[1].upper() == "DESC"

            def key(row):
                value = row_id(row) if name == ":id" else row.get(name, "")
                return value, scramble(row)  # ties: a different order on every request
            ordered.sort(key=key, reverse=descending)
        else:
            ordered.sort(key=scramble)  # no order asked: a different order on every request
        offset_text = self._param(query, "offset")
        offset = int(offset_text) if offset_text else 0
        page = ordered[offset:offset + limit]
        if names:
            page = [{k: r[k] for k in names if k in r} for r in page]
        return FakeResponse(200, json.dumps(page), {"Content-Type": "application/json"}, url)


def bulk_rows(name, n, year=2025, prefix="FIXTURE-BULK-"):
    """n more made-up rows for a fixture, all placeable, spread over one year, made without
    chance. arrests_like: district 5, not near a school, age 30, male, group Gamma, not
    Hispanic. coded_like: station 1, age 30, group B, male. Many rows share their exact
    time (one time per day, 300 days), so paging ordered on the time field alone overlaps."""
    out = []
    start = date(year, 1, 1)
    for i in range(n):
        day = start + timedelta(days=i % 300)
        when = f"{day:%Y-%m-%d}T14:00:00.000"
        if name == "arrests_like":
            out.append({"id": f"{prefix}{i:06d}", "event_date_time": when, "age": "30",
                        "gender": "Male", "race": "Gamma", "ethnicity": "NONHISP",
                        "district": "5", "adjacent_to_school": "0", "data_class": "SYNTHETIC"})
        else:
            out.append({"case_no": f"{prefix}{i:06d}", "booked_at": when, "age_years": "30",
                        "race_code": "B", "sex": "M", "station": "1D",
                        "data_class": "SYNTHETIC"})
    return out


def service_for(name, rows=None, **kw):
    rows = fixture_rows(name) if rows is None else rows
    return FakeService(rows, address=source_json(name)["address"], **kw)


# ---- copies on disk (C4) -------------------------------------------------------------------

def copies_root(state_dir, name):
    """`<state_dir>/copies/<source name>/`; the source name is the file's name without
    .json, which for both fixtures is also the part of the id after the colon."""
    return Path(state_dir) / "copies" / name


def copy_folders(state_dir, name):
    root = copies_root(state_dir, name)
    return sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else []


def current_text(state_dir, name):
    path = copies_root(state_dir, name) / "current"
    return path.read_text(encoding="utf-8").strip() if path.is_file() else None


def current_folder(state_dir, name):
    """The copy folder the `current` file names (by its folder name or its path)."""
    text = current_text(state_dir, name)
    if text is None:
        return None
    found = [p for p in copy_folders(state_dir, name) if p.name in text]
    assert len(found) == 1, f"`current` ({text!r}) names {len(found)} copy folders"
    return found[0]


def rows_file_sha256(folder):
    return hashlib.sha256((Path(folder) / "rows.jsonl").read_bytes()).hexdigest()


def read_copy_rows(folder):
    lines = (Path(folder) / "rows.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def read_copy_json(folder):
    return json.loads((Path(folder) / "copy.json").read_text(encoding="utf-8"))


# ---- the sources the program reads (C4 load_sources) --------------------------------------

def use_sources(monkeypatch, folder):
    """Point sources.load_sources()'s default folder at `folder`, in every moco_agent module
    that holds the function (so `from .sources import load_sources` is covered too)."""
    target = Path(folder)
    sources = mod("sources")
    for part in ("agent", "replies", "context", "slack_app", "memory", "config", "__main__"):
        try:
            mod(part)
        except ModuleNotFoundError:
            pass
    real = sources.load_sources

    def load_sources(folder=None, *args, **kwargs):
        return real(target if folder is None else folder, *args, **kwargs)

    for module_name, module in list(sys.modules.items()):
        if (module_name == "moco_agent" or module_name.startswith("moco_agent.")) and \
                getattr(module, "load_sources", None) is real:
            monkeypatch.setattr(module, "load_sources", load_sources)
    return load_sources


def write_sources(folder, names, change=None):
    """Copy the fixture source files `names` into `folder`, after change[name](data)."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for name in names:
        data = source_json(name)
        if change and name in change:
            change[name](data)
        (folder / f"{name}.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    return folder


def make_copy(name, state_dir, rows=None, now=COPY_NOW, **service_kw):
    """sources.fetch with a FakeService of the fixture's rows (or `rows`). Returns (copy,
    service)."""
    service = service_for(name, rows, **service_kw)
    made = mod("sources").fetch(source_id(name), state_dir=Path(state_dir), transport=service,
                                now=now)
    return made, service


def county_settings(tmp_path, state_dir, **environ_values):
    values = {"MOCO_DATA": "county", "MOCO_STATE_DIR": str(state_dir)}
    values.update(environ_values)
    return make_settings(tmp_path, **values)


class CountyEnv:
    """One county-mode agent in tmp_path. `names`: the source files in its sources folder;
    `copies`: which of them get a copy now (default: all of `names`); `rows`: {name: rows}
    to serve instead of the fixture's; `change`: {name: function(source dict)} applied to a
    source file before it is written. Turns run through agent.handle_question exactly as
    in stage 2."""

    def __init__(self, tmp_path, monkeypatch, *, names=("arrests_like",), copies=None,
                 rows=None, change=None, **settings_values):
        self.tmp_path = Path(tmp_path)
        self.names = tuple(names)
        self.sources_dir = write_sources(self.tmp_path / "sources", self.names, change)
        self.load_sources = use_sources(monkeypatch, self.sources_dir)
        self.state_dir = self.tmp_path / "state"
        self.state_dir.mkdir(exist_ok=True)
        self.rows = {name: (dict(rows or {}).get(name) if rows and name in rows
                            else fixture_rows(name)) for name in self.names}
        self.services = {}
        for name in (self.names if copies is None else copies):
            self.fetch(name)
        self.settings = county_settings(self.tmp_path, self.state_dir, **settings_values)
        self.store = open_store(self.tmp_path)
        self.runs_dir = self.tmp_path / "runs"
        self.runs_dir.mkdir(exist_ok=True)
        self.registry = load_registry()
        self.clock = FakeClock()
        self.model = None
        self._turns = 0

    def fetch(self, name, rows=None, now=COPY_NOW):
        made, service = make_copy(name, self.state_dir,
                                  self.rows[name] if rows is None else rows, now=now)
        self.services[name] = service
        return made

    def source(self, name):
        return json.loads((self.sources_dir / f"{name}.json").read_text(encoding="utf-8"))

    def ask(self, question, *steps, model=None, thread_key=THREAD_1, user_id=USER, now=None,
            today=TODAY_S3, memory_minutes=None, error=None, fail_at=0, seconds=0.0):
        self.model = model if model is not None else FakeModel(
            *steps, error=error, fail_at=fail_at, clock=self.clock, seconds=seconds)
        if now is None:
            now = NOW_S3 + timedelta(minutes=self._turns)
        self._turns += 1
        return mod("agent").handle_question(
            question, thread_key=thread_key, user_id=user_id, settings=self.settings,
            registry=self.registry, model_client=self.model, store=self.store,
            runs_dir=self.runs_dir, today=today, now=now, clock=self.clock,
            memory_minutes=memory_minutes)

    def answers(self):
        """Every tool answer Python gave the model in the last turn, in order, parsed."""
        last = self.model.calls[-1]["messages"] if self.model.calls else []
        return [json.loads(m["content"]) for m in tool_messages(last)]


# ---- the tool calls of county mode (C0, C5, C7) --------------------------------------------

COUNTY_TOOLS = frozenset({"count", "share", "compare", "describe_data", "ask_user",
                          "show_details", "decline", "finish", "analyze"})
SYNTHETIC_TOOLS = frozenset({"count_arrests", "compare", "describe_data", "ask_user",
                             "show_details", "decline", "finish"})
SPEC_ERRORS = ("BAD_FIELD", "BAD_VALUE", "OUT_OF_COVERAGE", "NOT_ALLOWED", "TOO_FINE",
               "TOO_MANY", "PARTIAL_YEAR")


def count(source=LEAVE_OUT, period=LEAVE_OUT, filters=LEAVE_OUT, group_by=LEAVE_OUT, **extra):
    """C5 count(source, period, filters, group_by). A part left as LEAVE_OUT is not sent."""
    arguments = {k: v for k, v in (("source", source), ("period", period),
                                   ("filters", filters), ("group_by", group_by))
                 if v is not LEAVE_OUT}
    arguments.update(extra)
    return call("count", arguments)


def share(part_id, whole_id):
    """C7 share(part_id, whole_id)."""
    return call("share", {"part_id": part_id, "whole_id": whole_id})


def compare(*result_ids):
    """C7 compare(result_ids)."""
    return call("compare", {"result_ids": list(result_ids)})


def year(y):
    return {"year": y}


def years(*ys):
    return {"years": list(ys)}


def months(y, first, last):
    return {"year": y, "months": {"from": first, "to": last}}


def dates(first, last):
    return {"from": first, "to": last}


def age(first=None, last=None, field_name="age"):
    out = {"field": field_name}
    if first is not None:
        out["from"] = first
    if last is not None:
        out["to"] = last
    return out


def is_(field_name, value):
    return {"field": field_name, "is": value}


def in_(field_name, *labels):
    return {"field": field_name, "in": list(labels)}


def weekdays(*names):
    return {"field": "weekday", "in": list(names)}


def hours(first, last):
    return {"field": "hour", "from": first, "to": last}


def clear(field_name):
    return {"field": field_name, "clear": True}


SCHOOL = "adjacent_to_school"


# ---- the reply (C10) -------------------------------------------------------------------------

SEP = r"(?: |\n|\n\n)"
FULL_TABLE_LINE = "The full table is in the details."


def hidden_line(page):
    return f"Counts under 10 are not shown here; the county's open data has every record: {page}."


def sensitive_line(unit_many):
    return f"These are counts of {unit_many}, not rates, and they show no cause."


def left_out_line(n, dimension):
    return f"({shown(n)} had no {dimension} recorded and are not included.)"


def age_left_out_line(n):
    return f"({shown(n)} had no usable age and are not included.)"


def source_first_re(title, unit_many):
    return (re.escape(f"Source: {title} (county open data), copy of ") + COPY_DATE_RE
            + re.escape(f". A count is of {unit_many}, not people. Want the details, or a "
                        f"different breakdown?"))


def source_later_re(title):
    """C18 (round 2): `(<title>, county open data, copy of <date>.)`."""
    return re.escape(f"({title}, county open data, copy of ") + COPY_DATE_RE + re.escape(".)")


def source_re(name, first=True, src=None):
    src = src or source_json(name)
    return (source_first_re(src["title"], src["unit"]["many"]) if first
            else source_later_re(src["title"]))


def _part(part):
    return part.pattern if isinstance(part, re.Pattern) else re.escape(part)


KEPT_ANY = re.compile(r"\(I kept [^()\n]+ from earlier\.\)")  # where C9 gives no wording


def reply_re(line1, *, source, table=None, full_table=False, kept=None, left_out=(),
             hidden=None, hidden_optional=None, sensitive=None):
    """C10: line 1, then in this order: the table (one line per group, `<label>: <n>`), or
    the full-table line; the kept note; each left-out line; the hidden line; the sensitive
    line; the source line. `line1` and the parts are exact strings (or compiled patterns);
    `source` is a regex string (source_re). A part given as None must be absent, except
    `hidden_optional` (a page): the hidden line may be there or not (READING: C12 says the
    hidden line comes "exactly when a group is hidden"; when only a total or a left-out
    count is hidden, the tests accept either)."""
    out = _part(line1)
    if table:
        out += r"\n" + r"\n".join(re.escape(line) for line in table)
    if full_table:
        out += SEP + re.escape(FULL_TABLE_LINE)
    for part in [kept, *left_out, hidden]:
        if part:
            out += SEP + _part(part)
    if hidden_optional:
        out += "(?:" + SEP + re.escape(hidden_line(hidden_optional)) + ")?"
    if sensitive:
        out += SEP + _part(sensitive)
    return out + SEP + source


def assert_reply(text, line1, **kw):
    pattern = reply_re(line1, **kw)
    assert re.fullmatch(pattern, text), (f"not the expected county reply.\n--- got ---\n{text}"
                                         f"\n--- expected (regex) ---\n{pattern}")


def table_lines(groups, floor=FLOOR):
    """C10: one line per group, `<label>: <n>`, n as C8 shows it."""
    return [f"{label}: {shown(n, floor)}" for label, n in groups.items()]


def check_county_reply(reply):
    """What every county reply must be: an AgentReply with A4's fields, to_dict JSON-safe,
    no chart in Part A (C10), and no row or hidden figure in its text (C1)."""
    for attribute in ("status", "reason_code", "text", "chart_path", "run_ids", "turn_id",
                      "reply_kind", "reply_style", "draft_failures", "steps", "results"):
        assert hasattr(reply, attribute), f"AgentReply has no {attribute}"
    json.dumps(reply.to_dict())
    assert isinstance(reply.text, str) and reply.text.strip(), reply.text
    counts = [r for r in reply.results if r.get("kind") == "count"]
    chart_due = reply.status == "ANSWERED" and not any(
        r.get("kind") == "analysis" for r in reply.results) and (
        (len(counts) == 1 and len(counts[0]["spec"]["group_by"]) == 1
         and len(counts[0]["groups"] or []) >= 2)
        or (len(counts) >= 2 and all(not r["spec"]["group_by"] for r in counts)
            and len({r["source"] for r in counts}) == 1))  # C40 amendment 2 point a
    if chart_due:  # C40 point 1, the contract's exception to C10 (planning chat, S3-R7-A q. 6)
        assert reply.chart_path and Path(reply.chart_path).name == "chart.png" \
            and Path(reply.chart_path).is_file(), reply.chart_path
    else:
        assert reply.chart_path is None, "no chart in Part A (C10) unless C40 point 1 gives one"
    assert "FIXTURE-" not in reply.text, reply.text
    assert_no_hidden_figure(reply.text, "reply")
    return reply


def run_records(reply, runs_dir):
    """C5: the record each count saved: runs/<run id>/manifest.json, as stage 1 saves it
    (READING: "stage 1's kind of record" is a manifest.json in the run's folder)."""
    out = []
    for run_id in reply.run_ids:
        path = Path(runs_dir) / run_id / "manifest.json"
        assert path.is_file(), f"no record at {path}"
        out.append(json.loads(path.read_text(encoding="utf-8")))
    return out


def turn_json(reply, runs_dir):
    path = Path(runs_dir) / reply.turn_id / "turn.json"
    assert path.is_file(), f"no turn record at {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def guard_free(question):
    """A premise: stage 1's guard neither refuses nor restricts the question (so the county
    tools are offered whatever the build does with the guard in county mode)."""
    screened = mod("guard").screen(question)
    assert screened.refuse is None and screened.restricted is None, (question, screened)
    return question


# Questions that pass the guard (checked by test_s3_sources.py); the stand-in model decides
# what is counted, so their wording only has to be plausible.
Q_COUNT = "How many arrests were there in 2025?"
Q_BREAKDOWN = "Break the 2025 arrests down for me."
Q_FOLLOW = "And for 2024?"
Q_SHARE = "What part of the 2025 arrests were near a school?"
Q_COMPARE = "Compare 2024 and 2025."
Q_ABOUT = "What data do you have?"


# ---- synthetic mode, exactly as today (C0, brief step 7) -----------------------------------

SYNTHETIC_TODAY = FIXTURES / "synthetic_today.json"


def synthetic_three_turns(tmp_path, **settings_values):
    """Three stage 2 turns in one thread, through agent.handle_question with p1support's Env
    (the synthetic data, the registry, the FakeModel), and everything that can be compared
    with today: each reply's fields and every model call's messages and tools. Run ids and
    turn ids change from run to run, so each run id is written `<run id N>` and the turn id
    and chart path are left out. Used by fixtures/record_synthetic_today.py (which saved
    synthetic_today.json from the program as it was before stage 3) and by
    test_s3_synthetic_untouched.py.

    1. a count of 2025, ages 18 to 25, with a passing finding (style agent, first answer);
    2. a count of 2024 and 2025 for people under 18, compared, with a passing finding;
    3. `details`, answered by Python with no model call."""
    import p1support as p1

    env = p1.Env(tmp_path, **settings_values)
    turns = [
        ("How many arrests were recorded each month in 2025 for ages 18 to 25?",
         [p1.Step(p1.count(2025, "18_25")), p1.Step(p1.finish("finding", p1.ONE_COUNT_TEXT))]),
        ("Compare 2024 and 2025 for people under 18.",
         [p1.Step(p1.count(2024, "under_18"), p1.count(2025, "under_18")),
          p1.Step(p1.compare("r1", "r2")), p1.Step(p1.finish("finding", p1.compare_text("r3")))]),
        ("details", []),
    ]
    run_ids, out = [], []
    for question, steps in turns:
        reply = env.ask(question, *steps)
        run_ids += [r for r in reply.run_ids if r not in run_ids]
        record = reply.to_dict()
        record.pop("turn_id")
        record["chart_path"] = record["chart_path"] is not None
        record.pop("results", None)
        out.append({"question": question, "reply": record,
                    "model_calls": [{"messages": c["messages"], "tools": c["tools"]}
                                    for c in env.model.calls]})

    def mask(value):
        if isinstance(value, str):
            for n, run_id in enumerate(run_ids, 1):
                value = value.replace(run_id, f"<run id {n}>")
            return value
        if isinstance(value, list):
            return [mask(v) for v in value]
        if isinstance(value, dict):
            return {k: mask(v) for k, v in value.items()}
        return value
    return mask(out)


# ---- rows made for one test (added by the second tests session; see the notes) -------------

_BASE_ROW = {
    "arrests_like": {"event_date_time": "2025-03-04T14:00:00.000", "age": "30",
                     "gender": "Male", "race": "Gamma", "ethnicity": "NONHISP", "district": "5",
                     "adjacent_to_school": "0"},
    "coded_like": {"booked_at": "2025-03-04T14:00:00.000", "age_years": "30", "race_code": "B",
                   "sex": "M", "station": "1D"},
}
_ANCHOR = {"arrests_like": "2026-09-17T08:30:00.000", "coded_like": "2026-08-20T13:05:00.000"}


def made_rows(name, *groups, prefix="FIXTURE-M-"):
    """SYNTHETIC rows made for one test: for each (n, values) in `groups`, n rows of the
    base row with `values` put over it (a value of None leaves the key out, as the service
    does for an empty value). The base row is placeable in every field, on 4 March 2025 at
    2 pm: arrests_like age 30, male, group Gamma, not Hispanic, district 5, not within 500
    feet of a school; coded_like age 30, group B, male, station 1. One more row, alone,
    stands at the fixture's newest record time (NEWEST), so the copy's newest record is the
    fixture's and 2024 and 2025 are whole past years; it is counted only in 2026."""
    key, time_field = (("id", "event_date_time") if name == "arrests_like"
                       else ("case_no", "booked_at"))
    out, serial = [], 0
    for n, values in groups:
        for _ in range(n):
            serial += 1
            row = {key: f"{prefix}{serial:05d}", **_BASE_ROW[name], **values}
            out.append({k: v for k, v in row.items() if v is not None})
            out[-1]["data_class"] = "SYNTHETIC"
    out.append({key: f"{prefix}ANCHOR", **_BASE_ROW[name], time_field: _ANCHOR[name],
                "data_class": "SYNTHETIC"})
    return out


# ---- C57 point 6: the stock line of a talk text (added by briefs/S3-R21-A-tests.md) --------

FALLBACK_LINE_BEFORE_C57 = ("I'd rather not say something I can't back up. Ask me for a count "
                            "and I'll show you the numbers.")
FALLBACK_LINE_C57 = ("I can't answer that without running a count. Tell me what to count and "
                     "for which period, and I'll show you the numbers.")  # C57 point 6, by hand


def fallback_lines(county):
    """The stock line a talk text that fails twice may end with. READING (round 21, a
    question in briefs/QUESTIONS.md): C57 point 6 changes config/talk_rules.json's
    fallback_line, which SYNTHETIC mode reads too, and C57 says "County mode only: with
    MOCO_DATA other than county nothing changes". County mode: C57's line. SYNTHETIC mode:
    today's line or C57's, both accepted until the planning chat answers."""
    return (FALLBACK_LINE_C57,) if county else (FALLBACK_LINE_BEFORE_C57, FALLBACK_LINE_C57)


def fallback_line_of(text, county):
    """`text` when it is a stock line fallback_lines accepts, else C57's line (so a check of
    the text against it fails and shows C57's line)."""
    return text if text in fallback_lines(county) else FALLBACK_LINE_C57


# ---- C61 (added by briefs/S3-R23-A-tests.md): its fixed texts, written out by hand ---------------

# Point 9: the county talk fallback's first sentence, then replies.county_can_ask(sources).
C61_FALLBACK_LEAD = "I can't put that in words I can back up. "
# Point 5: the block's second line when it shows fewer turns than the thread remembers.
C61_NOT_SHOWN = "(Earlier messages of this thread are not shown.)"
# Point 10: the sentence the NOT_ALLOWED `why` ends with when earlier turns make it so.
C61_EARLIER = " Counts given earlier in this conversation are taken into account."
# A fixture copy of config/about_agent.md (point 1's form), made in a test: SYNTHETIC lines, a
# heading and lines for people, and two lines that do not start with "- " (not facts).
C61_ABOUT_LINES = [
    "# SYNTHETIC fixture: what the agent may say about itself (made up for tests)",
    "",
    "Lines for people, not facts. Each line that starts with a dash and a space is one fact.",
    "- SYNTHETIC fixture fact one: I am a made-up agent for tests.",
    "- SYNTHETIC fixture fact two: no county runs this made-up agent.",
    "  - An indented line is not a fact.",
    "-Nor is a line with no space after the dash.",
    "- SYNTHETIC fixture fact three: my made-up rules are the fixture's own.",
]
C61_ABOUT_FACTS = [line[2:] for line in C61_ABOUT_LINES if line.startswith("- ")]


def county_fallback_line(n_sources):
    """C61 point 9: the line that replaces a county talk text that failed, with the fixture
    sources of the env (1: arrests_like; 2: and coded_like; 3: and round 3's visits_like). The
    can-ask sentences are tests/s3/test_s3_c41.py's CAN_ASK (C11, C23, C57 point 1)."""
    from test_s3_c41 import CAN_ASK
    return C61_FALLBACK_LEAD + CAN_ASK[n_sources]


def about_agent_fixture(tmp_path, monkeypatch, lines=None, name="about_agent.md"):
    """C61 correction 1: replies.ABOUT_AGENT pointed at a fixture copy written in tmp_path
    (never the file under config/). `lines`: the file's lines (default C61_ABOUT_LINES); False:
    no file is written (a file that is not there). Returns the path. raising=False: on a program
    without the constant the tests fail at their own checks."""
    path = Path(tmp_path) / "about-agent-fixture" / name
    if lines is not False:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(C61_ABOUT_LINES if lines is None else lines) + "\n",
                        encoding="utf-8")
    monkeypatch.setattr(mod("replies"), "ABOUT_AGENT", path, raising=False)
    return path


# ---- C62 (added by briefs/S3-R24-A-tests.md): its fixed texts, written out by hand -------------

# Point 1: the four words of the maker check, and config/talk_rules.json's new rewrite hint.
C62_MAKER_WORDS = ("Anthropic", "Claude", "NVIDIA", "Nemotron")
C62_MAKER_HINT = ("Say what you run on only in the exact words of the About you line, and say "
                  "nothing else about who built you: the facts of describe_data say that.")
# Point 2: the first sentence of the NOT_ALLOWED row when C61 point 10's sentence was given.
C62_REFUSAL = ("With the figures already given in this conversation, that count would give one "
               "single year of age under 18, so I don't give it.")
# Point 3: the two sentences at the end of C61 point 7's line (county talk prompt).
C62_PROMPT_SENTENCES = (
    "When someone asks which of several figures you gave is the highest or lowest, or what the "
    "difference is, do not point back: count them again in one count with a breakdown, or count "
    "each and call compare, and let the slots say it. When someone asks what you answered "
    "earlier, make the same count again and give it.")


# ---- C64 (added by briefs/S3-R28-A-tests.md): its fixed texts, written out by hand -------------

# Point 1: the line sent for a county talk text that ends the turn failing NUMBER (in place of C61
# point 9's whole line), and the sentence config/talk_rules.json's NUMBER hint gains at its end.
C64_TALK_LINE = (
    "I only give a figure by counting it, so I do not repeat, change or work on one in plain talk. "
    "My counts come from my saved copy of the county's data, and I cannot check them against any "
    'other source. Ask me to count it again, or say "details" after a count to see how it was '
    "counted.")
C64_HINT_SENTENCE = ('In talk, point at a figure with the words "the figure I gave" and write no '
                     'number.')
# Point 2: three sentences at the end of C61 point 7's line, after C62 point 3's two (one space).
C64_PROMPT_SENTENCES = (
    "When THREAD SO FAR says that earlier messages are not shown, you do not know how the "
    "conversation began. Never call a message, a question or a count the first, also when you "
    "count it again: call it the earliest one still shown to you. When asked for the first one, "
    "or for everything said or counted so far, say in your text that the start of the "
    "conversation is no longer shown to you, and go by what is shown.")
# Point 3: the three lines of a count that was not made (b with the program's own number, 8).
C64_LINE_A = ("(One count asked for here is not given: with the other figures it would give one "
              "single year of age under 18.)")
C64_LINE_B = ("(I make at most 8 counts in one message, so not everything asked for is here. Ask "
              "for the rest in a new message.)")
C64_LINE_C = "(Counts of different sources are never compared with each other.)"
C64_LINES = (C64_LINE_A, C64_LINE_B, C64_LINE_C)
# Point 4: the ninth fact of config/about_agent.md (version 2).
C64_NINTH_FACT = ("Questions or complaints about me go to the owner of this project, who set me up "
                  "in this Slack workspace. I have no address to give.")


# ---- C65 (added by briefs/S3-R29-A-tests.md): its fixed text, written out by hand ---------------
# Point 4: the reply to `reset` in county mode.
C65_RESET_LINE = ("Done. I've cleared what I remembered of this conversation. I keep only a list of "
                  "which counts I gave here, with no figures and no words of yours, so that my rule "
                  "about single years of age under 18 still holds.")


# ---- C65 points 6 and 7, C66 (added by briefs/S3-R30-A-tests.md): fixed texts, written out by hand

# C65 point 7: the Census's age bands for a rate (config/census.json, "records", "age_band"), each
# (first, last), last None for "and over".
C65_CENSUS_BANDS = ((10, 17), (18, 24), (25, 34), (35, 44), (45, 54), (55, 64), (65, None))
# C66 point 2: C41 point 5's line (county talk prompt, the line after rule 10), and the two
# sentences it gains at its end (one space before them).
C41_PROMPT_LINE = ("When you decline or ask, add text: one or two sentences in your own words "
                   "saying why, or what you need, with no number, date or name of a group or "
                   "place; the program adds the facts.")
C66_PROMPT_SENTENCES = (
    "When a tool answered NOT_ALLOWED, the reason is a rule of this project: say that it is a "
    "rule, and never say that the records or the data cannot do it. When THREAD SO FAR says that "
    "a count was refused under that rule and someone asks why, call describe_data and answer "
    "with its fact about the rule: never call it your mistake, and never offer to count it after "
    "all.")
# C66 point 3: what context.what_was_done adds for a turn whose record holds "age_rule": true.
C66_NOTE = " (a count was refused under the rule about single years of age under 18)"


C70_SENTENCE = (' A message that asks a new question of its own, and does not change just one thing'
                ' in your last answer, starts fresh: add {"field": "all", "clear": true} to its'
                ' filters, so that nothing is kept from earlier.')


def without_c70(text):
    """S3A C70 point 1 (D-087; added by the planning chat on 18 Nov without a tests session, by
    Nino's decision): the prompt with C70's sentence taken out from its place only, right after
    rule 11's '... send it with "clear": true.'."""
    anchor = '"Everyone", "overall" or "all districts" removes that filter: send it with "clear": true.'
    return text.replace(anchor + C70_SENTENCE, anchor, 1)


def without_c66(text):
    """A prompt text with C66 point 2's two sentences taken out from their place only: the end
    of the line that is C41 point 5's line, after one space. Anywhere else they stay (so a hash
    test then finds no match)."""
    text = without_c70(text)  # D-087: C70's sentence too, from its place only
    return "\n".join(C41_PROMPT_LINE if line == f"{C41_PROMPT_LINE} {C66_PROMPT_SENTENCES}"
                     else line for line in text.split("\n"))
