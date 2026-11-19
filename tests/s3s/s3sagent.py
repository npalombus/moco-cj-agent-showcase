"""Helpers that drive the program for the stage 3 Part S tests (docs/S3S-DESIGN.md). The
truth is in s3ssupport.py, which imports no program code; this file is the other half: it
runs county-mode turns through agent.handle_question exactly as tests/s3 does (s3support's
FakeService, use_sources and settings; p1support's FakeModel and clock), on the Part S
fixtures (tests/s3s/fixtures/).

READINGS (each is in kit-log/raw/S3S-A-notes.txt; the contract does not say):
- The `analyze` call's arguments are `kind`, `source`, `period`, `filters`, `options` (S1),
  sent as one JSON object; a result is `a1`, `a2` in the order of the turn's good
  `analyze` calls. Its slots: trend `{aN.trend}`; trend_compare `{aN.difference}`;
  before_after `{aN.step}`, `{aN.bend}`; yes_no `{aN.odds.1}` .. `{aN.odds.k}` (one per
  factor label, in the order of `factors`) and `{aN.held}`; shares `{aN.share}`,
  `{aN.sharetrend}`; timing `{aN.timing}`; distribution `{aN.ages}`.
- The job folder (S2: "kept with the saved record") is a folder holding `job.json`, found
  anywhere under the runs folder (or the state folder) the test gave the agent; R's
  `result.json` and `chart.png` are in it (S2).
- The chart "attached to the same message" (S5) is the reply's `chart_path`. A file
  attached to a reply (the script of S7) is in `chart_path` or in a list attribute of the
  reply named `attachments`, `files`, `attached` or `file_paths` (paths, or dicts with
  a `path`).
- The input table R is given (S2) is one CSV file in the job folder besides job.json.
- The fixed lines of S5 are joined by one space, one line break or one blank line (as
  Part A's reply); the table (S5.1), whose line format S5 does not give, is any lines
  between line 1 and the first fixed line.
"""
import csv
import json
import re
from datetime import timedelta
from pathlib import Path

from p1support import (FakeClock, FakeModel, Step, THREAD_1, USER, call, finish,
                       load_registry, mod, open_store, tool_messages)
from s3support import (COPY_NOW, NOW_S3, TODAY_S3, FakeService, county_settings, figures,
                       use_sources)

import s3ssupport as T

FIXTURE_SOURCES = T.FIXTURES / "sources"
MAIN, EDGES = T.MAIN, T.EDGES
MAIN_ID, EDGES_ID = T.SOURCE_IDS[MAIN], T.SOURCE_IDS[EDGES]
UNIT_MANY = "arrest records"
TITLE = {MAIN: T.source_json(MAIN)["title"], EDGES: T.source_json(EDGES)["title"]}
PAGE = {MAIN: T.source_json(MAIN)["page"], EDGES: T.source_json(EDGES)["page"]}

# Questions a person might ask; the stand-in model decides what is run, so their wording
# only has to be plausible (each passes stage 1's guard: test_s3s_analyze_spec checks).
Q_TREND = "Are arrests going up over the years?"
Q_COMPARE = "Is the change over the years different near schools?"
Q_BEFORE_AFTER = "Did anything change after July 2023?"
Q_YES_NO = "What goes with an arrest being near a school?"
Q_SHARES = "What share of arrests were near a school, year by year?"
Q_TIMING = "When do arrests happen?"
Q_AGES = "How old are people at arrest?"
QUESTION = {"trend": Q_TREND, "trend_compare": Q_COMPARE, "before_after": Q_BEFORE_AFTER,
            "yes_no": Q_YES_NO, "shares": Q_SHARES, "timing": Q_TIMING,
            "distribution": Q_AGES}


# ---- the agent ------------------------------------------------------------------------------

def write_sources(folder, names, change=None):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for name in names:
        data = T.source_json(name)
        if change and name in change:
            change[name](data)
        (folder / f"{name}.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    return folder


def service_for(name, rows=None, **kw):
    return FakeService(T.fixture_rows(name) if rows is None else rows,
                       address=T.source_json(name)["address"], **kw)


class StatsEnv:
    """One county-mode agent in tmp_path with the Part S fixture sources. `names`: the
    source files in its sources folder (each gets a copy now, made through the fake
    transport); `rows`: {name: rows} served instead of the fixture's; `change`: {name:
    function(source dict)}; settings as keyword arguments (MOCO_RSCRIPT=...)."""

    def __init__(self, tmp_path, monkeypatch, *, names=(MAIN,), rows=None, change=None,
                 **settings_values):
        self.tmp_path = Path(tmp_path)
        self.names = tuple(names)
        self.sources_dir = write_sources(self.tmp_path / "sources", self.names, change)
        self.load_sources = use_sources(monkeypatch, self.sources_dir)
        self.state_dir = self.tmp_path / "state"
        self.state_dir.mkdir(exist_ok=True)
        self.rows = {n: (rows[n] if rows and n in rows else T.fixture_rows(n))
                     for n in self.names}
        for n in self.names:
            mod("sources").fetch(T.SOURCE_IDS[n], state_dir=self.state_dir,
                                 transport=service_for(n, self.rows[n]), now=COPY_NOW)
        self.settings = county_settings(self.tmp_path, self.state_dir, **settings_values)
        self.store = open_store(self.tmp_path)
        self.runs_dir = self.tmp_path / "runs"
        self.runs_dir.mkdir(exist_ok=True)
        self.registry = load_registry()
        self.clock = FakeClock()
        self.model = None
        self._turns = 0

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
        """Python's JSON answer to every tool call of the last turn that a later model step
        saw, in order."""
        last = self.model.calls[-1]["messages"] if self.model.calls else []
        return [json.loads(m["content"]) for m in tool_messages(last)]

    def stored_turns(self):
        return self.store.recent_turns(THREAD_1, 50)


# ---- the analyze call (S1) and the finish text -----------------------------------------------

def analyze(arguments):
    """One `analyze` call; `arguments` a dict (sent as JSON) or a str (sent as given)."""
    return call("analyze", arguments)


def analyze_case(name, **change):
    return analyze(T.analyze_arguments(name, **change))


def slots(name, rid="a1"):
    """The slots a good call of case `name` offers (READING above)."""
    kind = T.case(name)["kind"]
    if kind == "yes_no":
        k = len(T.case(name)["options"]["factors"])
        return [f"{{{rid}.odds.{i}}}" for i in range(1, k + 1)] + [f"{{{rid}.held}}"]
    return [f"{{{rid}.{s}}}" for s in {
        "trend": ["trend"], "trend_compare": ["difference"], "before_after": ["step", "bend"],
        "shares": ["share", "sharetrend"], "timing": ["timing"],
        "distribution": ["ages"]}[kind]]


def slot_text(name, rid="a1"):
    """A finding that uses every slot of the case, each as its own sentence."""
    return " ".join(f"{s}." for s in slots(name, rid))


def ask_case(env, name, text=None, question=None, **kw):
    """One turn: the stand-in model calls analyze for the case, then finishes with `text`
    (default: every slot as its own sentence)."""
    q = question or QUESTION[T.case(name)["kind"]]
    return env.ask(q, Step(analyze_case(name)),
                   Step(finish("finding", slot_text(name) if text is None else text)), **kw)


# ---- what the program leaves on disk ---------------------------------------------------------

def job_folders(env):
    """Every job folder (a folder holding job.json) under the agent's runs and state
    folders, oldest first by name."""
    found = {p.parent for root in (env.runs_dir, env.state_dir) for p in Path(root).rglob(
        "job.json")}
    return sorted(found, key=lambda p: (p.stat().st_mtime_ns, str(p)))


def job_folder(env):
    folders = job_folders(env)
    assert len(folders) == 1, f"expected one job folder, found {len(folders)}: {folders}"
    return folders[0]


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def result_of(env):
    folder = job_folder(env)
    path = folder / "result.json"
    assert path.is_file(), f"no result.json in the job folder {folder}"
    return read_json(path)


def input_table(folder):
    """The input table of S2: the one CSV in the job folder, as (header, rows)."""
    tables = sorted(p for p in Path(folder).iterdir() if p.suffix.lower() in (".csv", ".tsv"))
    assert len(tables) == 1, f"expected one input table (CSV) in {folder}: {tables}"
    text = tables[0].read_text(encoding="utf-8")
    dialect = csv.Sniffer().sniff(text.splitlines()[0]) if "\t" in text.splitlines()[0] \
        else csv.excel
    rows = list(csv.reader(text.splitlines(), dialect))
    return rows[0], rows[1:]


def assert_estimates(env, name):
    """S9: every estimate of the case, as R left it in result.json, equals the truth within
    S9's tolerances (on whichever scale result.json writes it)."""
    entries = T.result_estimates(result_of(env))
    assert entries, "result.json holds no estimate with a name, an estimate and both ends"
    t = T.truth(name)
    for est in t["estimates"]:
        found = T.find_estimate(entries, est, t["kind"])
        assert found, (f"no estimate in result.json matches the truth's {est['name']} "
                       f"{est['estimate']:.5f} ({est['low']:.5f} to {est['high']:.5f}) within "
                       f"S9's tolerances; result.json has {entries}")
    return entries


def result_text(env):
    return json.dumps(result_of(env)).lower()


# ---- what is attached to a reply ----------------------------------------------------------------

_FILE_ATTRIBUTES = ("attachments", "files", "attached", "file_paths")


def attached(reply):
    """Every file attached to a reply: chart_path, and the paths in a list attribute named as
    the READING above says."""
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


def chart_of(reply):
    assert reply.chart_path, "S5: the chart is attached to the same message (chart_path)"
    path = Path(reply.chart_path)
    assert path.is_file(), f"the chart file {path} does not exist"
    return path


def script_of(reply):
    scripts = [p for p in attached(reply) if p.suffix == ".R"]
    assert len(scripts) == 1, (f"S7: the script is attached to the message as one .R file; "
                               f"attached: {attached(reply)}")
    assert scripts[0].is_file(), scripts[0]
    return scripts[0]


# ---- the reply (S5) ----------------------------------------------------------------------------------

SEP = r"(?: |\n|\n\n)"
# A table line (S5.1) is any line that is not one of the fixed lines after it.
_TABLE_LINE = (r"\n(?!The last six months|Other things changed|These are |Source: |\(\d|\("
               r"[A-Z])[^\n]*")


def _part(part):
    return part.pattern if isinstance(part, re.Pattern) else re.escape(part)


def stat_reply_re(line1, *, used, source, table=True, fit=None, before_after=False,
                  sensitive=False, interpreted=None, unit_many=UNIT_MANY):
    """S5: line 1, then in this order: the table (any lines, or none when table=False), the
    fit line (a regex, from s3ssupport.fit_line_re), the before-and-after line, the used
    line (a regex, s3ssupport.used_re), the association line, the sensitive line, the
    interpreted line (C14's 6a, a string), the source line (a regex)."""
    out = _part(line1)
    if table:
        out += f"(?:{_TABLE_LINE})*?"
    if fit:
        out += SEP + fit
    if before_after:
        out += SEP + re.escape(T.BEFORE_AFTER_LINE)
    out += SEP + used
    out += SEP + re.escape(T.association_line(unit_many))
    if sensitive:
        out += SEP + re.escape(T.sensitive_line(unit_many))
    if interpreted:
        out += SEP + re.escape(interpreted)
    return out + SEP + source


def assert_stat_reply(text, line1, **kw):
    pattern = stat_reply_re(line1, **kw)
    assert re.fullmatch(pattern, text), (f"not the expected statistical reply.\n--- got ---\n"
                                         f"{text}\n--- expected (regex) ---\n{pattern}")


def first_source(name=MAIN):
    return T.source_first_re(TITLE[name], UNIT_MANY)


def later_source(name=MAIN):
    return T.source_later_re(TITLE[name])


def line1_of(text):
    return text.split("\n", 1)[0]


_DECIMAL = re.compile(r"[+-]?\d+\.\d+%?")


def assert_no_hidden_stat_figure(text, where="reply"):
    """C1 and C8 with S4's numbers: decimals (percentages, odds ratios) and `95%` taken out,
    no whole number from 1 to 9 stands as a figure."""
    cleaned = _DECIMAL.sub(" ", text).replace("95%", " ")
    bad = sorted(n for n in figures(cleaned) if 1 <= n <= 9)
    assert not bad, f"a count from 1 to 9 ({bad}) stands as a figure in the {where}: {text!r}"


def check_stat_reply(reply):
    """What every statistical reply must be: an AgentReply with A4's fields, JSON-safe, no
    row id and no hidden figure in its text."""
    for attribute in ("status", "reason_code", "text", "chart_path", "run_ids", "turn_id",
                      "reply_kind", "reply_style", "draft_failures", "steps", "results"):
        assert hasattr(reply, attribute), f"AgentReply has no {attribute}"
    json.dumps(reply.to_dict())
    assert isinstance(reply.text, str) and reply.text.strip(), reply.text
    assert "FIXTURE-" not in reply.text, reply.text
    assert_no_hidden_stat_figure(reply.text)
    return reply


def answered(reply):
    check_stat_reply(reply)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    return reply


def tool_answer(env, step=0, position=0):
    """Python's answer to call `position` of model step `step`."""
    return env.model.answer(step, position)


# ---- a Socrata-like answer for the script of S7 -------------------------------------------------

_COMPARISON = re.compile(r"\s*([A-Za-z_:][A-Za-z0-9_]*)\s*(>=|<=|!=|=|>|<)\s*"
                         r"('(?:[^']*)'|[-0-9.]+)\s*")


def socrata_rows(url, rows):
    """What the county's service would answer to `url` (S7's data_url), from `rows`: the
    query's $where (comparisons joined by AND), $select, $order, $limit and $offset. A query
    this cannot read fails the test with the query, so the reader can see why."""
    from urllib.parse import parse_qs, urlsplit
    query = {k.lstrip("$"): v[-1] for k, v in parse_qs(urlsplit(url).query).items()}
    out = list(rows)
    where = query.get("where")
    if where:
        parts = re.split(r"\s+AND\s+", where, flags=re.IGNORECASE)
        tests = []
        for part in parts:
            found = _COMPARISON.fullmatch(part)
            assert found, f"the fake service cannot read this $where part: {part!r} ({url})"
            tests.append(found.groups())

        def keep(row):
            for name, op, value in tests:
                have = row.get(name)
                if have is None:
                    return False
                want = value[1:-1] if value.startswith("'") else value
                if not value.startswith("'"):
                    have, want = float(have), float(want)
                if not {">": have > want, ">=": have >= want, "<": have < want,
                        "<=": have <= want, "=": have == want, "!=": have != want}[op]:
                    return False
            return True
        out = [r for r in out if keep(r)]
    order = query.get("order")
    if order:
        name = order.split()[0]
        out.sort(key=lambda r: r.get("id" if name == ":id" else name, ""),
                 reverse=order.upper().endswith("DESC"))
    offset = int(query.get("offset", 0))
    limit = int(query.get("limit", 1000))
    out = out[offset:offset + limit]
    if query.get("select"):
        names = [n.strip() for n in query["select"].split(",")]
        out = [{k: r[k] for k in names if k in r} for r in out]
    return out


def assert_line1(text, pattern, before="", after=r"\."):
    """Line 1 of a reply is `before` + the phrase regex + `after` (exactly), followed by the
    end of the text or white space."""
    full = re.escape(before) + pattern + after
    assert re.match(full + r"(?=\s|$)", text), (f"line 1 is not the expected phrase.\n--- got "
                                                f"---\n{text}\n--- expected (regex) ---\n{full}")


def phrase_in(text, pattern):
    assert re.search(pattern, text), (f"the phrase is not in the reply.\n--- got ---\n{text}\n"
                                      f"--- expected (regex) ---\n{pattern}")
