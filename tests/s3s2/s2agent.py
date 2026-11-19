"""Helpers that drive the program for the Part S2 tests (docs/S3S2-DESIGN.md). The truth is in
s2support.py (no program code); this file runs the program: county copies through the
county's fake service (s3support.FakeService), Census copies through `python -m moco_agent
fetch-census` with a fake Census service, and turns through agent.handle_question with the
stand-in model, exactly as tests/s3s does (its helpers imported, nothing copied).

READINGS (each is in kit-log/raw/S3S2-A-notes.txt; the contract does not say):
- The Census service is the Census Bureau's own API, `https://api.census.gov/data/<year>/
  acs/acs1` (config/census.json has the survey `acs/acs1` and the place, not the address).
  FakeCensus answers it the way the Census does: `get=` a list of variables (at most 50, as
  the Census allows) or `group(<table>)`, the place as `for=county:031&in=state:24` or
  `ucgid=0500000US24031`, `key=`; the answer is a JSON list, a first line of names and one
  line of values, every value a string, a margin the Census does not give written
  -555555555. The labels: `groups/<table>.json`, `variables.json` or
  `variables/<name>.json`. A year it has not published: 404.
- The program reaches the Census through urllib.request (as sources._get does today; no
  other HTTP library is installed). CensusNet stands in for every urllib opener while
  fetch-census runs; any other address is refused and counted.
- `fetch-census` is run as the county `fetch` command is tested (tests/s3/test_s3_fetch.py):
  `__main__.main(["fetch-census"])` in this process, with MOCO_STATE_DIR in tmp_path and
  the made-up key in CENSUS_API_KEY (set in the environment; the settings file stays empty).
- A rate is asked as `analyze` with kind `rate` (R8), the period whole years
  (`{"year": 2025}` or `{"years": [...]}`), options `by` and `reference`.
- The phrases are read from the fixed rendering (MOCO_REPLY_STYLE=fixed: each phrase its own
  sentence, capitalised, S4), so the tests need not know the slot names, which R6 leaves
  open for a breakdown (`{aN.rate}` once, or once per group). SlotModel writes a finding from
  the slots Python offered, whatever they are named.
"""
import email.message
import io
import json
import re
import urllib.error
import urllib.request
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import s2support as T
from p1support import (FakeClock, FakeModel, Step, THREAD_1, USER, call, finish, load_registry,
                       mod, open_store, show_details, tool_messages)
from s3support import COPY_NOW, NOW_S3, TODAY_S3, FakeService, county_settings, use_sources

import importlib.util

_MF = importlib.util.spec_from_file_location("s2_make_fixtures", T.FIXTURES / "make_fixtures.py")
MF = importlib.util.module_from_spec(_MF)
_MF.loader.exec_module(MF)

RATES, MAIN = T.RATES, T.MAIN
RATES_ID, MAIN_ID = T.SOURCE_IDS[RATES], T.SOURCE_IDS[MAIN]
KEY = T.KEY
UNIT_MANY = T.UNIT_MANY
TITLE = {RATES: T.source_json(RATES)["title"], MAIN: T.source_json(MAIN)["title"]}
Q_RATE = "How many arrests were there per 10,000 residents, by group?"
CENSUS_BASE = "https://api.census.gov/data/"


# ---- the Census service ----------------------------------------------------------------------

NOT_FOUND_PAGE = ("<html><head><title>404 Not Found</title></head><body><h1>Not Found</h1>"
                  "<p>SYNTHETIC fixture: the requested resource is not available.</p></body>"
                  "</html>")
HTML_PAGE = ("<!DOCTYPE html><html><head><title>Census Data API</title></head><body>SYNTHETIC "
             "fixture: the service is down for maintenance.</body></html>")
FAILURES = ("network", "timeout", "http500", "html", "error_text", "empty", "bad_shape",
            "short")


class FakeCensus:
    """The Census Bureau's API for the tests. `years`: the years it has published. `bump`:
    added to every age line of B01001 (and so to the totals and B03002's total), for a second
    answer that differs: an int, or {year: int}. `labels`: {year: {"B01001_030E": new label}}.
    `fail`: {year or "all": one of FAILURES, or "echo_key"}. `requests`: every request, as
    {"url", "base", "path", "params", "year", "kind"}."""

    def __init__(self, years=T.YEARS, *, bump=0, labels=None, fail=None):
        self.years = tuple(years)
        self.bump = bump
        self.labels = labels or {}
        self.fail = dict(fail or {})
        self.requests = []

    def _bump(self, year):
        return self.bump.get(year, 0) if isinstance(self.bump, dict) else self.bump

    def answer(self, url):
        """(status, body text, content type), or raises OSError as urllib would."""
        parts = urlsplit(url)
        query = {k: v[-1] for k, v in parse_qs(parts.query, keep_blank_values=True).items()}
        found = re.fullmatch(r"/data/(\d{4})/acs/acs1(/.*)?", parts.path)
        year = int(found[1]) if found else None
        rest = (found[2] or "") if found else None
        kind = ("data" if rest in ("", "/") else "labels") if found else "other"
        self.requests.append({"url": url, "base": f"{parts.scheme}://{parts.netloc}{parts.path}",
                              "path": parts.path, "params": query, "year": year, "kind": kind})
        if parts.scheme != "https" or parts.netloc != T.CENSUS_HOST or not found:
            return 404, NOT_FOUND_PAGE, "text/html"
        if year not in self.years:
            return 404, NOT_FOUND_PAGE, "text/html"
        mode = self.fail.get(year, self.fail.get("all"))
        if mode:
            return self._failure(mode, url)
        if kind == "data":
            return self._data(year, query)
        return self._labels(year, rest)

    @staticmethod
    def _failure(mode, url):
        if mode == "network":
            raise urllib.error.URLError(ConnectionRefusedError(61, "SYNTHETIC: refused"))
        if mode == "timeout":
            raise urllib.error.URLError(TimeoutError("SYNTHETIC: timed out"))
        if mode == "http500":
            return 500, "error: SYNTHETIC fixture server error", "text/plain"
        if mode == "echo_key":  # an error that repeats the request it was given
            return 400, f"error: SYNTHETIC fixture could not answer {url}", "text/plain"
        if mode == "html":
            return 200, HTML_PAGE, "text/html"
        if mode == "error_text":
            return 400, "error: unknown/unsupported geography heirarchy", "text/plain"
        if mode == "empty":
            return 204, "", "text/plain"
        if mode == "bad_shape":
            return 200, json.dumps({"error": "SYNTHETIC: not a table"}), "application/json"
        if mode == "short":
            return 200, json.dumps([["NAME", "B01001_001E"]]), "application/json"
        raise AssertionError(mode)

    def _data(self, year, query):
        key = query.get("key")
        if key is not None and key != KEY:
            return 400, "error: SYNTHETIC fixture: invalid key", "text/plain"
        if query.get("ucgid"):
            if query["ucgid"] != MF.GEO["geo_id"]:
                return 400, "error: unknown/unsupported geography heirarchy", "text/plain"
            geo = [("ucgid", MF.GEO["geo_id"])]
        else:
            if query.get("for") != f"county:{MF.GEO['county']}" or \
                    query.get("in") != f"state:{MF.GEO['state']}":
                return 400, "error: unknown/unsupported geography heirarchy", "text/plain"
            geo = [("state", MF.GEO["state"]), ("county", MF.GEO["county"])]
        asked = [x.strip() for x in query.get("get", "").split(",") if x.strip()]
        if not asked:
            return 400, "error: missing 'get' parameter", "text/plain"
        cells = {}
        for table in MF.TABLES:
            names, row = MF.group_answer(table, year, self._bump(year))
            cells.update(zip(names, row))
        names = []
        for item in asked:
            group = re.fullmatch(r"group\((B\d{5})\)", item)
            if group:
                if group[1] not in MF.TABLES:
                    return 400, f"error: unknown group '{group[1]}'", "text/plain"
                names += MF.group_answer(group[1], year)[0][:-2]  # its variables, GEO_ID, NAME
            elif item in cells:
                names.append(item)
            else:
                return 400, f"error: error: unknown variable '{item}'", "text/plain"
        if sum(1 for x in asked if not x.startswith("group(")) > 50:
            return 400, "error: Number of variables is limited to 50.", "text/plain"
        names = list(dict.fromkeys(names))
        header = names + [g for g, _ in geo]
        values = [cells[n] for n in names] + [v for _, v in geo]
        return 200, json.dumps([header, values]), "application/json;charset=utf-8"

    def _labels(self, year, rest):
        variables = {}
        for table in MF.TABLES:
            variables.update(MF.labels_answer(table, year)["variables"])
        for name, label in self.labels.get(year, {}).items():
            variables[name] = dict(variables[name], label=label)
        group = re.fullmatch(r"/groups/(B\d{5})(?:\.json)?", rest)
        if group:
            if group[1] not in MF.TABLES:
                return 404, NOT_FOUND_PAGE, "text/html"
            mine = {k: v for k, v in variables.items() if v.get("group") == group[1]}
            return 200, json.dumps({"variables": mine}), "application/json"
        if re.fullmatch(r"/variables(?:\.json)?", rest):
            extra = {"for": {"label": "Census API FIPS 'for' clause", "concept": "Census API "
                             "Geography Specification", "predicateType": "fips-for",
                             "group": "N/A", "limit": 0, "predicateOnly": True},
                     "in": {"label": "Census API FIPS 'in' clause", "concept": "Census API "
                            "Geography Specification", "predicateType": "fips-in",
                            "group": "N/A", "limit": 0, "predicateOnly": True}}
            return 200, json.dumps({"variables": {**extra, **variables}}), "application/json"
        one = re.fullmatch(r"/variables/([A-Z0-9_]+)(?:\.json)?", rest)
        if one and one[1] in variables:
            return 200, json.dumps({"name": one[1], **variables[one[1]]}), "application/json"
        if re.fullmatch(r"/groups(?:\.json)?", rest):
            return 200, json.dumps({"groups": [{"name": t, "description": d}
                                               for t, d in MF.TABLES.items()]}), \
                "application/json"
        return 404, NOT_FOUND_PAGE, "text/html"

    def data_requests(self, year=None):
        return [r for r in self.requests if r["kind"] == "data"
                and (year is None or r["year"] == year)]

    def label_requests(self, year=None):
        return [r for r in self.requests if r["kind"] == "labels"
                and (year is None or r["year"] == year)]


class _Response(io.BytesIO):
    """What urllib's opener gives back: http.client.HTTPResponse's reading side."""

    def __init__(self, url, status, body, content_type):
        super().__init__(body.encode("utf-8"))
        self.url = url
        self.status = self.code = status
        self.reason = self.msg = {200: "OK", 204: "No Content"}.get(status, "")
        self.headers = email.message.Message()
        self.headers["Content-Type"] = content_type

    def getcode(self):
        return self.status

    def geturl(self):
        return self.url

    def info(self):
        return self.headers

    def getheader(self, name, default=None):
        return self.headers.get(name, default)

    def getheaders(self):
        return list(self.headers.items())


class CensusNet:
    """Stands in for every urllib opener: an address on api.census.gov goes to the
    FakeCensus; any other address is refused (URLError) and listed in `others`."""

    def __init__(self, census):
        self.census = census
        self.others = []
        self.headers = []

    def install(self, monkeypatch):
        net = self

        def open_(opener, fullurl, data=None, timeout=None, *args, **kwargs):
            return net.open(fullurl, data)
        monkeypatch.setattr(urllib.request.OpenerDirector, "open", open_)
        return self

    def open(self, fullurl, data=None):
        if isinstance(fullurl, urllib.request.Request):
            url, headers = fullurl.full_url, dict(fullurl.header_items())
        else:
            url, headers = str(fullurl), {}
        self.headers.append(headers)
        if urlsplit(url).netloc != T.CENSUS_HOST:
            self.others.append(url)
            raise urllib.error.URLError("SYNTHETIC: only the fake Census service is reachable")
        status, body, content_type = self.census.answer(url)
        if status >= 400:
            hdrs = email.message.Message()
            hdrs["Content-Type"] = content_type
            raise urllib.error.HTTPError(url, status, "SYNTHETIC error", hdrs,
                                         io.BytesIO(body.encode("utf-8")))
        return _Response(url, status, body, content_type)


class FetchRun:
    def __init__(self, code, out, err, net, before, after):
        self.code, self.out, self.err, self.net = code, out, err, net
        self.text = out + err
        # the day of the run, in UTC and in local time (the evening is the next day in UTC)
        self.days = sorted({t.date() for t in (before, after, before.astimezone(),
                                               after.astimezone())})

    @property
    def census(self):
        return self.net.census


def run_fetch_census(monkeypatch, state_dir, census, *, key=KEY):
    """`python -m moco_agent fetch-census` in this process: MOCO_STATE_DIR, the made-up key
    (or none), the fake Census behind urllib. Returns a FetchRun (exit code, what it
    printed, the requests)."""
    monkeypatch.setenv("MOCO_STATE_DIR", str(state_dir))
    if key is None:
        monkeypatch.delenv("CENSUS_API_KEY", raising=False)
    else:
        monkeypatch.setenv("CENSUS_API_KEY", key)
    net = CensusNet(census).install(monkeypatch)
    out, err = io.StringIO(), io.StringIO()
    before = datetime.now(timezone.utc)
    with redirect_stdout(out), redirect_stderr(err):
        try:
            code = mod("__main__").main(["fetch-census"])
        except SystemExit as stop:
            code = stop.code
    after = datetime.now(timezone.utc)
    return FetchRun(0 if code is None else code, out.getvalue(), err.getvalue(), net, before,
                    after)


def assert_is_a_command(run):
    assert not (run.code == 2 and "invalid choice" in run.text), (
        "R8: `python -m moco_agent fetch-census` is not a command yet:\n" + run.text[-600:])


def date_forms(day):
    """A day as a reader or a file may write it."""
    month = ["January", "February", "March", "April", "May", "June", "July", "August",
             "September", "October", "November", "December"][day.month - 1]
    return (f"{day.day} {month} {day.year}", f"{month} {day.day}, {day.year}",
            day.isoformat(), f"{day:%Y%m%d}")


def census_date_re(run):
    forms = [f for d in run.days for f in date_forms(d)[:3]]
    return "(?:" + "|".join(re.escape(f) for f in forms) + ")"


COUNTY_DATE = date_forms(COPY_NOW.date())[0]   # the county copy's day, as C10 writes it


def census_dates(run):
    """The Census copy's day as the source line writes it (READING: as the county's date,
    `13 November 2026`): the run's day, in UTC or local time."""
    return [date_forms(d)[0] for d in run.days]


def lines_of(text):
    return [line for line in text.split("\n") if line.strip()]


def reply_problem(text, wants):
    """None when the reply's lines are one of `wants` (lists of lines) exactly; else where the
    nearest one differs first."""
    got = lines_of(text)
    if any(got == want for want in wants):
        return None
    want = wants[-1]
    for i, (a, b) in enumerate(zip(want, got), 1):
        if a != b:
            return f"line {i} differs:\n  want {a}\n  got  {b}\n--- the reply:\n{text}"
    return f"{len(got)} lines, {len(want)} wanted:\n{text}\n--- wanted:\n" + "\n".join(want)


def assert_reply(reply, t, env, first=True):
    """R10 points 2 to 5: the fixed reply, every line word for word and in order."""
    wants = [T.reply_lines(t, TITLE[t["source"]], COUNTY_DATE, d, first)
             for d in census_dates(env.census_runs[-1])]
    problem = reply_problem(reply.text, wants)
    assert problem is None, problem


# ---- the files under the state folder ---------------------------------------------------------

def census_folder(state_dir, year):
    return Path(state_dir) / "census" / str(year)


def tree_texts(folder):
    """{relative path: text} of every file under `folder` (bytes read as UTF-8, bad bytes
    replaced), {} when there is none."""
    folder = Path(folder)
    if not folder.exists():
        return {}
    return {str(p.relative_to(folder)): p.read_bytes().decode("utf-8", "replace")
            for p in sorted(folder.rglob("*")) if p.is_file()}


def total_text(year, bump=0):
    """B01001_001E of a year, as the Census writes it (digits only)."""
    return str(MF.b01001_values(year, bump)["B01001_001"][0])


def holds(folder, text):
    return any(text in t for t in tree_texts(folder).values())


# ---- the agent ---------------------------------------------------------------------------------

def write_sources(folder, names, mark, change=None):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for name in names:
        data = T.source_json(name)
        data.pop("rates", None)
        if name in mark:
            T.marked(data)
        if change and name in change:
            change[name](data)
        (folder / f"{name}.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    return folder


class S2Env:
    """One county-mode agent in tmp_path. `names`: the source files in its sources folder
    (copies made now through the county's fake service); `mark`: those marked "rates": true
    (R2; by default every one); `census`: a FakeCensus to run fetch-census with now (True:
    the fixture's; False: none). Settings as keyword arguments."""

    def __init__(self, tmp_path, monkeypatch, *, names=(RATES,), mark=None, rows=None,
                 change=None, census=True, **settings_values):
        self.tmp_path = Path(tmp_path)
        self.monkeypatch = monkeypatch
        self.names = tuple(names)
        self.sources_dir = write_sources(self.tmp_path / "sources", self.names,
                                         self.names if mark is None else mark, change)
        self.load_sources = use_sources(monkeypatch, self.sources_dir)
        self.state_dir = self.tmp_path / "state"
        self.state_dir.mkdir(exist_ok=True)
        self.rows = {n: (rows[n] if rows and n in rows else T.fixture_rows(n))
                     for n in self.names}
        for n in self.names:
            mod("sources").fetch(T.SOURCE_IDS[n], state_dir=self.state_dir,
                                 transport=FakeService(self.rows[n],
                                                       address=T.source_json(n)["address"]),
                                 now=COPY_NOW)
        self.census_runs = []
        if census:
            self.fetch_census(FakeCensus() if census is True else census)
        self.settings = county_settings(self.tmp_path, self.state_dir, **settings_values)
        self.store = open_store(self.tmp_path)
        self.runs_dir = self.tmp_path / "runs"
        self.runs_dir.mkdir(exist_ok=True)
        self.registry = load_registry()
        self.clock = FakeClock()
        self.model = None
        self._turns = 0

    def fetch_census(self, census, key=KEY):
        run = run_fetch_census(self.monkeypatch, self.state_dir, census, key=key)
        assert_is_a_command(run)
        self.census_runs.append(run)
        return run

    def ask(self, question, *steps, model=None, thread_key=THREAD_1, user_id=USER, now=None,
            today=TODAY_S3, memory_minutes=None):
        self.model = model if model is not None else FakeModel(*steps, clock=self.clock)
        if now is None:
            now = NOW_S3 + timedelta(minutes=self._turns)
        self._turns += 1
        return mod("agent").handle_question(
            question, thread_key=thread_key, user_id=user_id, settings=self.settings,
            registry=self.registry, model_client=self.model, store=self.store,
            runs_dir=self.runs_dir, today=today, now=now, clock=self.clock,
            memory_minutes=memory_minutes)

    def answers(self):
        last = self.model.calls[-1]["messages"] if self.model.calls else []
        return [json.loads(m["content"]) for m in tool_messages(last)]

    def stored_turns(self):
        return self.store.recent_turns(THREAD_1, 50)


# ---- the rate call and the stand-in model --------------------------------------------------------

def rate_call(arguments):
    return call("analyze", arguments)


def ask_rate(env, name=None, arguments=None, text="I found that.", question=Q_RATE, **kw):
    """One turn: the model calls analyze for the case (or with `arguments`), then finishes
    with `text`."""
    args = arguments if arguments is not None else T.analyze_arguments(name, **kw)
    return env.ask(question, Step(rate_call(args)), Step(finish("finding", text)))


class SlotModel(FakeModel):
    """Calls analyze with `arguments`, then finishes with a finding written from the slots
    Python offered: `write(slots)` (default: each slot as its own sentence)."""

    def __init__(self, arguments, write=None, **kw):
        super().__init__(Step(rate_call(arguments)), Step(finish("finding", "")), **kw)
        self.write = write or (lambda slots: " ".join(f"{s}." for s in slots))

    def step(self, messages, tools):
        if len(self.calls) == 1:
            answers = [json.loads(m["content"]) for m in tool_messages(messages)]
            slots = answers[-1].get("slots", []) if answers else []
            self.steps[1] = Step(finish("finding", self.write(slots)))
        return super().step(messages, tools)


def offered_slots(env):
    answers = env.answers()
    return answers[0].get("slots", []) if answers else []


def line1_of(text):
    return text.split("\n", 1)[0]


def details_of(env):
    # C36 point 5 (S3-R6-A): `details` goes to the model, which calls show_details
    reply = env.ask("details", Step(show_details()))
    assert reply.status == "DETAILS", (reply.status, reply.reason_code, reply.text)
    return reply


_FILE_ATTRIBUTES = ("attachments", "files", "attached", "file_paths")


def attached(reply):
    out = []
    if getattr(reply, "chart_path", None):
        out.append(Path(reply.chart_path))
    for name in _FILE_ATTRIBUTES:
        value = getattr(reply, name, None)
        if isinstance(value, (list, tuple)):
            for item in value:
                path = item.get("path") if isinstance(item, dict) else item
                if path:
                    out.append(Path(path))
    return list(dict.fromkeys(out))


def script_of(reply):
    scripts = [p for p in attached(reply) if p.suffix == ".R"]
    assert len(scripts) == 1, f"S7/R8: one .R script attached; attached: {attached(reply)}"
    return scripts[0]


def assert_no_key(text, where):
    for part in T.KEY_PARTS:
        assert part not in text, f"the made-up Census key (or part of it) is in the {where}"
