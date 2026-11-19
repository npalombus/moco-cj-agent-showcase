"""`details` and the script anyone can run: docs/S3S-DESIGN.md S7 and S9 ("the script of S7
is produced, holds no data row, and (with a fake transport standing in for the county)
prints the same estimates"), with C11 of docs/S3A-DESIGN.md (the notices word for word and
the course-project line).

- `details` after a statistical answer shows the copy's date and fingerprint (Part A shows
  the first 12 characters of the copy's sha256), the months and records used, the county's
  notices word for word and the course-project line; for the Poisson fallback the model's
  sentence names Poisson (READING: S3 "the result says which was used", S7 "the model in one
  plain sentence").
- The script is attached to the details message as one .R file (READING: s3sagent.attached).
  It holds no record: no fixture id, no row's JSON line, no row's exact time. The source's
  address appears exactly once, on its own line `data_url <- "<address with its query>"`. Its
  top (the lines above data_url) names the copy's date (the wording of the warning about
  corrections is not given). It loads no package but jsonlite, MASS and sandwich.
- Pointed at a local file holding what the county's service would answer to that URL (the
  fake service: s3sagent.socrata_rows), `Rscript` prints, in its last lines, `<name>
  <estimate> <low> <high>` for every estimate, equal to the truth within S9's tolerances
  (on whichever scale it writes them).
"""
import json
import re
import subprocess
from pathlib import Path

import pytest

import s3ssupport as T
from s3sagent import (EDGES, MAIN, StatsEnv, answered, ask_case, script_of, socrata_rows)
from p1support import Step, show_details
from s3support import COPY_DATE_RE

CASES = ["trend_all", "compare_school", "ba_d6", "yn_main", "sh_school", "trend_fallback"]
DATA_URL = re.compile(r'(?m)^data_url <- "([^"\n]+)"\s*$')
ALLOWED_PACKAGES = {"jsonlite", "MASS", "sandwich", "base", "stats", "utils", "methods",
                    "grDevices", "graphics"}
OUT_LINE = re.compile(r"^(\S+)\s+(-?[0-9.]+(?:[eE][-+]?\d+)?)\s+(-?[0-9.]+(?:[eE][-+]?\d+)?)"
                      r"\s+(-?[0-9.]+(?:[eE][-+]?\d+)?)\s*$")


def _env_and_details(tmp_path, monkeypatch, name):
    source = T.case(name)["source"]
    env = StatsEnv(tmp_path, monkeypatch, names=(source,))
    answered(ask_case(env, name))
    # C36 point 5 (S3-R6-A): `details` goes to the model, which calls show_details
    details = env.ask("details", Step(show_details()))
    assert details.status == "DETAILS", (details.status, details.reason_code, details.text)
    return env, details, source


def _copy_json(env, source):
    found = list((env.state_dir / "copies").rglob("copy.json"))
    assert len(found) == 1, found
    return json.loads(found[0].read_text(encoding="utf-8"))


def last_estimates(stdout):
    """The trailing lines `<name> <estimate> <low> <high>` of the script's output."""
    out = []
    for line in reversed([x for x in stdout.splitlines() if x.strip()]):
        found = OUT_LINE.match(line.strip())
        if not found:
            break
        out.append({"name": found[1], "estimate": float(found[2]), "low": float(found[3]),
                    "high": float(found[4])})
    return list(reversed(out))


def test_the_output_reader_and_the_fake_answer():
    """No program code: the line reader, and the fake service on a URL with a query."""
    text = "Readable table\n  a b\ntrend 0.085 0.066 0.105\nother -1.5e-02 -0.03 0.001\n"
    assert [e["name"] for e in last_estimates(text)] == ["trend", "other"]
    assert last_estimates(text)[1]["estimate"] == -0.015
    rows = T.fixture_rows(MAIN)
    url = (T.source_json(MAIN)["address"] + "?$where=event_date_time >= '2021-01-01T00:00:00' "
           "AND event_date_time < '2022-01-01T00:00:00'&$limit=50000&$select=id,"
           "event_date_time,district")
    got = socrata_rows(url, rows)
    assert got and all(r["event_date_time"].startswith("2021") for r in got)
    assert set(got[0]) <= {"id", "event_date_time", "district"}


@pytest.mark.needs_r
@pytest.mark.parametrize("name", CASES)
def test_details_after_a_statistical_answer(tmp_path, monkeypatch, name):
    env, details, source = _env_and_details(tmp_path, monkeypatch, name)
    text = details.text
    src = T.source_json(source)
    for notice in src["notices"]:
        assert notice in text, notice
    assert "This agent is a university course project. It is not a county service." in text
    assert re.search(COPY_DATE_RE, text), text
    assert _copy_json(env, source)["sha256"][:12] in text
    t = T.truth(name)
    assert f"{t['records']:,}" in text, (t["records"], text)
    if "months" in t:
        assert re.search(rf"\b{len(t['months'])} months\b", text), text
    if name == "trend_fallback":
        assert "Poisson" in text, text
    assert "FIXTURE-" not in text


WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


@pytest.mark.needs_r
def test_details_of_timing_hides_the_small_cell(tmp_path, monkeypatch):
    """S10 answer 14 with C8 (added by the planning chat after the automatic check): `details`
    after a timing answer shows one line per weekday, Monday first, `<weekday>: ` and then
    the 24 hourly counts from midnight on joined by " | ", a count from 1 to 9 written
    `fewer than 10`. The fixture has exactly one such cell (4 records)."""
    env, details, source = _env_and_details(tmp_path, monkeypatch, "timing")
    cells = T.truth("timing")["cells"]
    assert sum(1 <= n <= 9 for n in cells.values()) == 1 and min(cells.values()) == 4
    rows = [line.split(": ", 1) for line in details.text.splitlines()
            if line.split(": ", 1)[0] in WEEKDAYS]
    assert [day for day, _ in rows] == list(WEEKDAYS), details.text
    hidden = 0
    for d, (day, rest) in enumerate(rows):
        items = [item.strip() for item in rest.split("|")]
        assert len(items) == 24, (day, rest)
        for h, item in enumerate(items):
            n = cells[(d, h)]
            if 1 <= n <= 9:
                assert item == "fewer than 10", (day, h, item)
                hidden += 1
            else:
                assert item == f"{n:,}", (day, h, item, n)
    assert hidden == 1


def _row_times(rows):
    return {r["event_date_time"][:16] for r in rows
            if not re.fullmatch(r"\d{4}-\d{2}-01T00:00", r["event_date_time"][:16])}


@pytest.mark.needs_r
@pytest.mark.parametrize("name", CASES)
def test_the_script_holds_no_record_and_one_address(tmp_path, monkeypatch, name):
    env, details, source = _env_and_details(tmp_path, monkeypatch, name)
    script = script_of(details).read_text(encoding="utf-8")
    rows = T.fixture_rows(source)
    assert "FIXTURE-" not in script
    for row in rows[:: max(1, len(rows) // 2000)]:
        assert json.dumps(row) not in script
    assert not any(stamp in script for stamp in _row_times(rows)), "a record's exact time"
    address = T.source_json(source)["address"]
    lines = DATA_URL.findall(script)
    assert len(lines) == 1, f"S7: exactly one data_url line; found {lines}"
    assert lines[0].startswith(address), lines[0]
    assert script.count(address) == 1, "the address appears exactly once"
    top = script[:DATA_URL.search(script).start()]
    assert re.search(COPY_DATE_RE, top), "the top says which copy's date the numbers are from"
    used = set(re.findall(r"(?:library|require|requireNamespace)\(\s*[\"']?([A-Za-z.]+)", script))
    used |= set(re.findall(r"\b([A-Za-z][A-Za-z0-9.]*)::", script))
    assert used <= ALLOWED_PACKAGES, used - ALLOWED_PACKAGES


@pytest.mark.needs_r
@pytest.mark.parametrize("name", CASES)
def test_the_script_prints_the_same_estimates(tmp_path, monkeypatch, name):
    env, details, source = _env_and_details(tmp_path, monkeypatch, name)
    script = script_of(details).read_text(encoding="utf-8")
    (url,) = DATA_URL.findall(script)
    answer = tmp_path / "county-answer.json"
    answer.write_text(json.dumps(socrata_rows(url, T.fixture_rows(source))), encoding="utf-8")
    local = DATA_URL.sub(lambda m: f'data_url <- "{answer}"', script, count=1)
    run_dir = tmp_path / "rerun"
    run_dir.mkdir()
    path = run_dir / "rerun.R"
    path.write_text(local, encoding="utf-8")
    done = subprocess.run(["Rscript", str(path)], cwd=run_dir, capture_output=True, text=True,
                          timeout=120)
    assert done.returncode == 0, done.stderr[-2000:]
    entries = last_estimates(done.stdout)
    assert entries, f"no `<name> <estimate> <low> <high>` lines at the end:\n{done.stdout[-1500:]}"
    t = T.truth(name)
    for est in t["estimates"]:
        assert T.find_estimate(entries, est, t["kind"]), (est["name"], est["estimate"], entries)
    assert "FIXTURE-" not in done.stdout
