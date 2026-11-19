"""Helpers for the Part D tests. The contract is docs/D-DESIGN.md (D0 to D8).

The stand-ins are the ones the earlier tests use, imported, never copied: the model
(p1support.FakeModel), Slack's events and the made-up secrets (p1support), the county
fixture sources and the fake county service (s3support.FakeService), the guards
(tests/s3/conftest.py, loaded by tests/d/conftest.py). Part D adds:

- `Sandbox`: a copy of the program (the moco_agent package this process imports, and the
  project's config, data and analysis_r) in pytest's temporary folder, whose config/sources/ holds the fixture source files instead of the
  county's. Every command runs in a subprocess against that copy (tests/d/standin.py), so
  "the project's var" and "the project's runs" a command sees are the copy's, and nothing a
  command does, built or not, can reach the real project. Each run checks, as a premise,
  that the subprocess imported moco_agent from the copy and that it tried no network.
- The fixture source files are written as `arrests_like.json` (id FIXTURE:arrests_like)
  and `a_coded.json` (id FIXTURE:coded_like): in file-name order the coded one comes first,
  in id order the arrests one does, so a refresh in file order shows.
- Copies made before a command are made here, in this process, by the real sources.fetch
  with a FakeService and a `now` of the test's choosing, under a state folder in tmp_path.
- `listing` and `project_folders`: the project's var/ and runs/ (and a sandbox's), file by
  file with size and change time, for the before-and-after checks the brief asks for.

Readings (each also in kit-log/raw/D-A-notes.txt):
- A setting's value is read back as the Settings attribute named like every other key
  (MOCO_LOG_STDOUT -> settings.moco_log_stdout), as config.py does for every key it has.
- The day in a refresh line may be written `13 November 2026`, `November 13, 2026` or
  `2026-11-13`, as the stage 3 tests accept for the copy's date (D4 does not say); it is the
  UTC day of the copy, read from the digits of the copy folder's name.
- runs/.matplotlib (stage 1's chart cache) is left out of every runs listing, as in the
  earlier guards. MPLCONFIGDIR is set for the subprocess to one folder in pytest's temporary
  folder, shared by the session, so matplotlib's font cache is built once.
"""
import json
import os
import re
import shutil
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from p1support import (AGENT_USER, FAKE_MODEL_ID, FAKE_SECRETS, ONE_COUNT_TEXT, TEAM, USER, USER2,
                       DEAD_PROXY, Env, Step, decline, finish, mention, mod)
from p1support import count as count_arrests
from s3support import (A_ID, C_ID, FakeService, Q_COUNT, copy_folders, current_folder,
                       fixture_rows, rows_file_sha256, source_json, use_sources, year)
from s3support import count as county_count
from support import REPO, VENV_PYTHON

HERE = Path(__file__).resolve().parent
STANDIN = HERE / "standin.py"
VAR = REPO / "var"
RUNS = REPO / "runs"

A_NAME, C_NAME = "arrests_like", "coded_like"
A_ROWS = len(fixture_rows(A_NAME))   # 600
C_ROWS = len(fixture_rows(C_NAME))
FAIL_EXIT = 4  # what `fetch` gives for a failed fetch today (__main__.EXIT_CODES["ERROR"])
SETTINGS_EXIT = 4  # what a ConfigError gives today

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]


# ---- the project's folders, before and after ---------------------------------------------

def listing(folder, leave_out=(".matplotlib",)):
    """Every file and folder under `folder` (relative path, size, change time), or None when
    the folder does not exist. Top-level names in `leave_out` are skipped."""
    folder = Path(folder)
    if not folder.exists():
        return None
    out = []
    for path in folder.rglob("*"):
        rel = path.relative_to(folder)
        if rel.parts[0] in leave_out:
            continue
        try:
            stat = path.stat()
        except FileNotFoundError:
            continue
        out.append((str(rel), path.is_dir(), stat.st_size, stat.st_mtime_ns))
    return sorted(out)


def project_folders():
    """The real project's var/ and runs/, listed."""
    return {"var": listing(VAR), "runs": listing(RUNS)}


def files_under(folder):
    """The files under `folder` (relative paths), [] when it does not exist."""
    folder = Path(folder)
    if not folder.exists():
        return []
    return sorted(str(p.relative_to(folder)) for p in folder.rglob("*")
                  if p.is_file() and p.relative_to(folder).parts[0] != ".matplotlib")


def tree_bytes(folder):
    """{relative path: bytes} of every file under `folder`."""
    folder = Path(folder)
    return {str(p.relative_to(folder)): p.read_bytes() for p in sorted(folder.rglob("*"))
            if p.is_file()}


# ---- source files and copies --------------------------------------------------------------

def address_for(tag):
    return f"https://fixture.invalid/resource/{tag}.json"


class Services:
    """One transport for several fake services, each picked by the address asked for
    (scheme, host and path). `services` is {address: s3support.FakeService, or any callable
    taking the request as FakeService does}. `asked` lists every address asked for, in
    order; an address with no service gets a 404 error object."""

    def __init__(self, services=None, on_request=None):
        self.services = dict(services or {})
        self.asked = []
        self.on_request = on_request

    @staticmethod
    def _url(args, kwargs):
        for value in list(args) + list(kwargs.values()):
            if isinstance(value, dict) and isinstance(value.get("url"), str):
                return value["url"]
            value = getattr(value, "full_url", value)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                return value
        return ""

    def _pick(self, args, kwargs):
        from urllib.parse import urlsplit
        parts = urlsplit(self._url(args, kwargs))
        base = f"{parts.scheme}://{parts.netloc}{parts.path}"
        self.asked.append(base)
        if self.on_request is not None:
            self.on_request(base)
        return self.services.get(base) or FakeService([], address="https://nothing.invalid/")

    def __call__(self, *args, **kwargs):
        return self._pick(args, kwargs)(*args, **kwargs)

    def get(self, *args, **kwargs):
        target = self._pick(args, kwargs)
        return target.get(*args, **kwargs) if hasattr(target, "get") else target(*args, **kwargs)

    def request(self, *args, **kwargs):
        target = self._pick(args, kwargs)
        return (target.request(*args, **kwargs) if hasattr(target, "request")
                else target(*args, **kwargs))


def source_file(name, *, sid=None, address=None, drop=()):
    """A fixture source file as a dict, with a new id, address, or keys taken out."""
    data = source_json(name)
    if sid is not None:
        data["id"] = sid
    if address is not None:
        data["address"] = address
    for key in drop:
        data.pop(key)
    return data


def fixture_files(**more):
    """The two fixture source files, named so that file order is not id order, plus `more`
    ({file name: dict})."""
    files = {"arrests_like.json": source_file(A_NAME), "a_coded.json": source_file(C_NAME)}
    files.update(more)
    return files


def write_files(folder, files):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("*.json"):
        old.unlink()
    for file_name, data in files.items():
        (folder / file_name).write_text(json.dumps(data, indent=2), encoding="utf-8")
    return folder


def make_copies(monkeypatch, sources_dir, state_dir, name, times, *, sid=None, address=None,
                rows=None):
    """One copy per time in `times`, by the real sources.fetch with a FakeService, under
    `state_dir`. `name` is the fixture whose rows are served; `sid` and `address` those of
    the source file (default: the fixture's)."""
    use_sources(monkeypatch, sources_dir)
    src = source_json(name)
    for now in times:
        service = FakeService(fixture_rows(name) if rows is None else rows,
                              address=address or src["address"])
        mod("sources").fetch(sid or src["id"], state_dir=Path(state_dir), transport=service,
                             now=now)


def copy_names(state_dir, name):
    return [p.name for p in copy_folders(state_dir, name)]


def folder_day(folder):
    """The UTC day of a copy folder, from the digits of its name (YYYYMMDD...)."""
    digits = "".join(ch for ch in Path(folder).name if ch.isdigit())
    return date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))


def day_forms(day):
    return (f"{day.day} {MONTHS[day.month - 1]} {day.year}",
            f"{MONTHS[day.month - 1]} {day.day}, {day.year}", day.isoformat())


def ok_line_re(sid, rows, state_dir, name):
    """D4's first line for the current copy of `name`: `<source id>: <rows> rows, copy of
    <day>, sha256:<first 12 characters>`."""
    folder = current_folder(state_dir, name)
    assert folder is not None, f"no current copy of {name}"
    sha = rows_file_sha256(folder)
    days = "|".join(re.escape(d) for d in day_forms(folder_day(folder)))
    return (re.escape(f"{sid}: {rows} rows, copy of ") + f"(?:{days})"
            + re.escape(f", sha256:{sha[:12]}"))


def utc_now():
    return datetime.now(timezone.utc)


# ---- scripted turns ------------------------------------------------------------------------

SYNTHETIC_Q = "How many arrests were recorded each month in 2025 for ages 18 to 25?"
SYNTHETIC_STEPS = (Step(count_arrests(2025, "18_25")), Step(finish("finding", ONE_COUNT_TEXT)))
COUNTY_Q = Q_COUNT  # "How many arrests were there in 2025?"
COUNTY_STEPS = (Step(county_count(A_ID, year(2025))),
                Step(finish("finding", "I counted {r1.count}.")))
COUNTY_FIRST = "I counted 240 arrest records in 2025."  # the fixture's count (test_s3_fetch.py)


def message(question):
    """An app_mention from an approved person in an allowed workspace."""
    return mention(f"<@{AGENT_USER}> {question}")


def steps_json(steps):
    return [{"calls": [[name, arguments] for name, arguments in s.calls], "text": s.text}
            for s in steps]


def service(name, *, address=None, fail=None, slow=False, extra_rows=()):
    """A fake county service for the subprocess: the fixture's rows (plus `extra_rows`) at
    `address` (default: the fixture's own). `fail` is one of s3support.FAILURES."""
    return {"address": address or source_json(name)["address"], "fixture": name,
            "fail": fail, "slow": slow, "extra_rows": list(extra_rows)}


def serve_env(**extra):
    """What require_for_serve needs (made-up values), then `extra`."""
    env = dict(FAKE_SECRETS, SLACK_ALLOWED_TEAM_ID=TEAM, SLACK_ALLOWED_USER_IDS=f"{USER},{USER2}")
    env.update({key: str(value) for key, value in extra.items()})
    return env


def model_env(**extra):
    env = {"NVIDIA_API_KEY": FAKE_SECRETS["NVIDIA_API_KEY"]}
    env.update({key: str(value) for key, value in extra.items()})
    return env


def refused_db(folder, path, question):
    """A memory file at `path` holding one turn refused with UNSUPPORTED_FIELD an hour ago,
    made through handle_question with the fake model in `folder` (p1support.Env)."""
    Path(folder).mkdir(parents=True, exist_ok=True)
    env = Env(folder)
    reply = env.ask(question, Step(decline("UNSUPPORTED_FIELD")),
                    now=utc_now() - timedelta(hours=1))
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", "UNSUPPORTED_FIELD"), reply.text
    env.store.close()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(Path(folder) / "agent.db", path)
    return path


# ---- the sandbox --------------------------------------------------------------------------

IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc")
PROXIES = ("http_proxy", "https_proxy", "all_proxy", "no_proxy")


class Result:
    def __init__(self, proc, report):
        self.code = report["code"]
        self.stdout, self.stderr = proc.stdout, proc.stderr
        self.report = report
        self.lines = [line for line in proc.stdout.splitlines() if line.strip()]
        self.err_lines = [line for line in proc.stderr.splitlines() if line.strip()]

    @property
    def posts(self):
        return self.report["posts"]

    def explain(self):
        return (f"exit code {self.code}\n--- stdout ---\n{self.stdout[-3000:]}\n--- stderr ---\n"
                f"{self.stderr[-3000:]}\n--- error ---\n{self.report.get('error')}")


def program():
    """The folder of the moco_agent package this process imports (the project's src/ through
    the .venv's path file), which is the program a Sandbox copies."""
    import importlib.util
    return Path(importlib.util.find_spec("moco_agent").origin).parent


class Sandbox:
    """A copy of the program in tmp_path/project, its config/sources/ holding `sources`
    ({file name: dict}; default: fixture_files())."""

    def __init__(self, tmp_path, sources=None):
        self.tmp = Path(tmp_path)
        self.root = self.tmp / "project"
        for part in ("config", "data", "analysis_r"):
            shutil.copytree(REPO / part, self.root / part, ignore=IGNORE)
        shutil.copytree(program(), self.root / "src" / "moco_agent", ignore=IGNORE)
        self.sources_dir = write_files(self.root / "config" / "sources",
                                       fixture_files() if sources is None else sources)
        self.var = self.root / "var"
        self.runs = self.root / "runs"
        self.env_file = self.tmp / "sandbox-empty.env"
        self.env_file.write_text("", encoding="utf-8")
        self.home = self.tmp / "sandbox-home"
        self.home.mkdir(exist_ok=True)
        self.mpl = self.tmp.parent / "d-matplotlib"
        self.mpl.mkdir(exist_ok=True)
        self.runs_made = 0

    def environ(self, extra):
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("NVIDIA_", "SLACK_", "MOCO_", "OPENAI_", "ANTHROPIC_"))
               and k.lower() not in PROXIES and k not in ("PYTHONPATH", "MPLCONFIGDIR")}
        tests = HERE.parent
        env.update({"MOCO_ENV_FILE": str(self.env_file), "HOME": str(self.home),
                    "NVIDIA_MODEL": FAKE_MODEL_ID, "MPLCONFIGDIR": str(self.mpl),
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONPATH": os.pathsep.join(str(p) for p in (
                        self.root / "src", HERE, tests / "p1", tests / "s3", tests))})
        for key in ("http_proxy", "https_proxy", "all_proxy"):
            env[key] = env[key.upper()] = DEAD_PROXY
        env.update({key: str(value) for key, value in (extra or {}).items()})
        return env

    def run(self, *argv, env=None, steps=(), services=(), events=(), wait_for=(),
            timeout=150):
        """One command through tests/d/standin.py. `steps`: the model's (p1support.Step);
        `services`: fake county services (service()); `events`: Slack events delivered
        once serve connects; `wait_for`: addresses whose first request the Slack session
        waits for (at most 30 seconds) before it delivers the events."""
        self.runs_made += 1
        work = self.tmp / f"standin-{self.runs_made}"
        work.mkdir()
        config = {"argv": [str(a) for a in argv], "report": str(work / "report.json"),
                  "services": list(services), "model_steps": steps_json(steps),
                  "events": list(events), "team_id": TEAM, "wait_for": list(wait_for)}
        (work / "config.json").write_text(json.dumps(config), encoding="utf-8")
        proc = subprocess.run([str(VENV_PYTHON), str(STANDIN), str(work / "config.json")],
                              cwd=self.root, env=self.environ(env), capture_output=True,
                              text=True, timeout=timeout)
        report_file = work / "report.json"
        assert report_file.is_file(), (f"the stand-in runner did not finish:\n"
                                       f"{proc.stdout[-2000:]}\n{proc.stderr[-3000:]}")
        report = json.loads(report_file.read_text(encoding="utf-8"))
        assert Path(report["module_file"]).resolve().is_relative_to(self.root / "src"), \
            f"premise: moco_agent was imported from {report['module_file']}, not the copy"
        assert report["network"] == 0, "the program tried to use the network"
        return Result(proc, report)


START_LINE = "The agent is connecting to Slack (model {model}, data {data}). Log: {log}. " \
             "Stop it with Ctrl+C."  # today's line (slack_app.serve), written out by hand


def start_line(data, log):
    return START_LINE.format(model=FAKE_MODEL_ID, data=data, log=log)


def start_lines(result):
    return [line for line in result.lines if line.startswith("The agent is connecting")]


def log_lines(path):
    path = Path(path)
    return path.read_text(encoding="utf-8").splitlines() if path.is_file() else []


def db_text(path):
    """Every cell of the memory file, as one text (p1support.db_cells reads the file)."""
    from p1support import db_cells
    path = Path(path)
    assert path.is_file(), f"no memory file at {path}"  # (sqlite3 would make an empty one)
    return " ".join(str(c) for c in db_cells(path.parent, path.name))


def turn_folders(folder):
    """Turn record folders (holding turn.json) under `folder`."""
    return sorted(p.parent for p in Path(folder).glob("*/turn.json"))


def run_folders(folder):
    """Run folders (holding manifest.json) under `folder`."""
    return sorted(p.parent for p in Path(folder).glob("*/manifest.json"))
