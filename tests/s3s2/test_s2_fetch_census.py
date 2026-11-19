"""R9, point 5: `python -m moco_agent fetch-census` (docs/S3S2-DESIGN.md R1, R8): the request it
makes; a label that does not match refuses the year and keeps the last good copy; a failed or
error answer; the key is in no file, log line, printed line, saved record or script.

R8: for each year from 2021 on that the Census has published, fetch the two tables and the
Census's own list of variable labels, with CENSUS_API_KEY (never printed, logged or saved). A
year's copy is kept only if every variable's label holds the words config/census.json expects;
otherwise that year is refused, with the variable named, and the last good copy stays. Copies
live under <state dir>/census/<year>/, dated and fingerprinted like county copies.

The fake Census service and how it is reached: s2agent (READINGS there). The key is the
made-up `TEST-KEY-NOT-REAL`. A copy is recognised by what it must hold: the year's figures
(B01001_001's estimate, as the Census writes it), a sha256 fingerprint (64 hex characters)
and the day it was made; the file names are not given and not checked.

READINGS: the exit code of a run where every published year was fetched is not given (a year
not yet published may be asked and answered 404), so it is not checked; a run where a year
failed prints no traceback. A missing key: the project's rule for commands (A14, the
__main__ docstring) is that the command names the KEY and stops before it makes anything.
"""
import json
import logging
import os
import re
import urllib.request
from pathlib import Path

import pytest

import s2support as T
from p1support import mod
from s2agent import (FAILURES, KEY, MF, CensusNet, FakeCensus, S2Env, assert_is_a_command,
                     assert_no_key, ask_rate, census_folder, date_forms, details_of, holds,
                     run_fetch_census, script_of, total_text, tree_texts)

HEX64 = re.compile(r"\b[0-9a-f]{64}\b")
BAD_LABEL = "Estimate!!Total:!!Female:!!18 and 19 years"        # B01001_030 says 15 to 17
SWAPPED = "Estimate!!Total:!!Female:!!10 to 14 years"            # B01001_005 is Male


def _real_variables():
    cfg = json.loads((T.HERE.parents[1] / "config" / "census.json").read_text(encoding="utf-8"))
    return sorted({v["variable"] for groups in cfg["breakdowns"].values()
                   for variables in groups.values() for v in variables})


# ---- the stand-in itself (no program code) ------------------------------------------------------

def test_the_fake_census_answers_as_the_census_does(monkeypatch):
    census = FakeCensus()
    net = CensusNet(census).install(monkeypatch)
    base = "https://api.census.gov/data/2025/acs/acs1"
    with urllib.request.urlopen(f"{base}?get=group(B01001)&for=county:031&in=state:24"
                                f"&key={KEY}") as answer:
        names, row = json.loads(answer.read())
    assert [names, row] == [T.census_file(2025, "B01001")["answer"][0][:-2] + ["state", "county"],
                            T.census_file(2025, "B01001")["answer"][1][:-2] + ["24", "031"]]
    with urllib.request.urlopen(f"{base}?get=NAME,B03002_012E,B03002_012M,B03002_001M"
                                f"&ucgid=0500000US24031") as answer:
        assert json.loads(answer.read()) == [
            ["NAME", "B03002_012E", "B03002_012M", "B03002_001M", "ucgid"],
            ["Montgomery County, Maryland", "200000", "4000", "-555555555", "0500000US24031"]]
    too_many = ",".join(f"B01001_{n:03d}E" for n in range(1, 50)) + ",B01001_001M,NAME"
    for url, code in ((f"{base}?get={too_many}&for=county:031&in=state:24", 400),
                      (f"{base}?get=B01001_050E&for=county:031&in=state:24", 400),
                      (f"{base}?get=B01001_001E&for=county:032&in=state:24", 400),
                      ("https://api.census.gov/data/2026/acs/acs1?get=B01001_001E"
                       "&for=county:031&in=state:24", 404)):
        with pytest.raises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(url)
        assert caught.value.code == code, url
    with urllib.request.urlopen(f"{base}/groups/B01001.json") as answer:
        labels = json.loads(answer.read())["variables"]
    assert labels["B01001_030E"]["label"] == "Estimate!!Total:!!Female:!!15 to 17 years"
    changed = FakeCensus(labels={2025: {"B01001_030E": BAD_LABEL}})
    CensusNet(changed).install(monkeypatch)
    with urllib.request.urlopen(f"{base}/variables/B01001_030E.json") as answer:
        assert json.loads(answer.read())["label"] == BAD_LABEL
    with pytest.raises(urllib.error.URLError):
        urllib.request.urlopen("https://fixture.invalid/elsewhere")
    assert total_text(2023) == "1038600" and total_text(2023, 100) == "1043200"


def test_todays_transport_reaches_the_stand_in(monkeypatch):
    """No program code beyond today's sources._get: the stand-in answers the transport the
    county copies use, with an error status for an error."""
    census = FakeCensus(fail={2023: "http500"})
    CensusNet(census).install(monkeypatch)
    get = mod("sources")._get
    ok = get("https://api.census.gov/data/2024/acs/acs1",
             params={"get": "B01001_001E", "for": "county:031", "in": "state:24", "key": KEY})
    assert ok.status_code == 200 and json.loads(ok.text)[1][0] == "1047800"
    bad = get("https://api.census.gov/data/2023/acs/acs1", params={"get": "B01001_001E"})
    assert bad.status_code == 500
    assert census.requests[0]["params"]["key"] == KEY


# ---- the command ------------------------------------------------------------------------------

def _fetch(tmp_path, monkeypatch, census=None, key=KEY):
    run = run_fetch_census(monkeypatch, tmp_path / "state", census or FakeCensus(), key=key)
    assert_is_a_command(run)
    return run


def _asked_variables(requests):
    out = set()
    for r in requests:
        for item in r["params"].get("get", "").split(","):
            item = item.strip()
            group = re.fullmatch(r"group\((B\d{5})\)", item)
            if group:
                out |= {n for n in MF.group_answer(group[1], 2025)[0]}
            elif item:
                out.add(item)
    return out


def _labels_asked(requests, variable):
    table = variable.split("_")[0]
    for r in requests:
        rest = r["path"].split("/acs/acs1", 1)[1]
        if re.fullmatch(rf"/groups/{table}(?:\.json)?|/variables(?:\.json)?", rest):
            return True
        if re.fullmatch(rf"/variables/{variable}E(?:\.json)?", rest):
            return True
    return False


def test_the_requests_it_makes(tmp_path, monkeypatch):
    """Both tables and their labels for every published year from 2021, for Montgomery County
    (state 24, county 031), from the ACS one-year survey, with the key as the Census takes
    it (`key=`); no other address."""
    run = _fetch(tmp_path, monkeypatch)
    census = run.census
    assert run.net.others == [], f"addresses other than the Census: {run.net.others}"
    assert census.requests, "no request reached the Census"
    data_years = {r["year"] for r in census.data_requests()}
    assert set(T.YEARS) <= data_years and min(data_years) >= 2021, data_years
    for r in census.requests:
        assert r["base"].startswith("https://api.census.gov/data/") and \
            "/acs/acs1" in r["path"], r["url"]
    wanted = _real_variables()
    for year in T.YEARS:
        asked = census.data_requests(year)
        for r in asked:
            p = r["params"]
            assert p.get("key") == KEY, f"R8: the data request carries the key: {r['url']}"
            assert (p.get("for"), p.get("in")) == ("county:031", "state:24") or \
                p.get("ucgid") == "0500000US24031", r["url"]
        names = _asked_variables(asked)
        for v in wanted:
            assert {v + "E", v + "M"} <= names, (year, v, sorted(names)[:10])
            assert _labels_asked(census.label_requests(year), v), (
                f"R8: the Census's own label of {v} for {year} is fetched")


def test_a_dated_fingerprinted_copy_for_each_year(tmp_path, monkeypatch):
    run = _fetch(tmp_path, monkeypatch)
    state = tmp_path / "state"
    for year in T.YEARS:
        folder = census_folder(state, year)
        texts = tree_texts(folder)
        assert texts, f"R8: no copy under {folder}"
        assert holds(folder, total_text(year)), f"the copy of {year} lacks its figures"
        assert any(HEX64.search(t) for t in texts.values()), f"no fingerprint for {year}"
        days = [f for d in run.days for f in date_forms(d)]
        where = " ".join(texts) + " " + " ".join(texts.values())
        assert any(d in where for d in days), f"the copy of {year} is not dated"
    assert not holds(census_folder(state, 2026), "B01001"), "2026 is not published"
    assert "Traceback" not in run.text, run.text


@pytest.mark.parametrize("year,variable,label", [(2023, "B01001_030", BAD_LABEL),
                                                 (2024, "B01001_005", SWAPPED)])
def test_a_label_that_does_not_match_keeps_the_last_good_copy(tmp_path, monkeypatch, year,
                                                              variable, label):
    """A second fetch whose figures changed (every age line 100 more) but whose label of one
    variable for one year does not hold the words config/census.json expects: that year is
    refused with the variable named, its last good copy stays, the other years are new."""
    _fetch(tmp_path, monkeypatch)
    again = _fetch(tmp_path, monkeypatch, FakeCensus(bump=100, labels={
        year: {variable + "E": label}}))
    state = tmp_path / "state"
    assert holds(census_folder(state, year), total_text(year)), "the last good copy is gone"
    assert not holds(census_folder(state, year), total_text(year, 100)), \
        f"R8: the refused copy of {year} was kept"
    other = 2025
    assert holds(census_folder(state, other), total_text(other, 100)), "the good year was not kept"
    assert str(year) in again.text and variable in again.text, (
        f"R8: the year is refused with the variable named:\n{again.text}")
    assert "Traceback" not in again.text, again.text


def test_a_label_that_does_not_match_on_the_first_fetch(tmp_path, monkeypatch):
    run = _fetch(tmp_path, monkeypatch, FakeCensus(labels={2024: {"B01001_005E": SWAPPED}}))
    state = tmp_path / "state"
    assert not holds(census_folder(state, 2024), total_text(2024)), "a refused year was kept"
    assert holds(census_folder(state, 2025), total_text(2025))
    assert "2024" in run.text and "B01001_005" in run.text, run.text


@pytest.mark.parametrize("mode", FAILURES)
def test_a_failed_or_error_answer_keeps_the_last_good_copy(tmp_path, monkeypatch, mode):
    _fetch(tmp_path, monkeypatch)
    again = _fetch(tmp_path, monkeypatch, FakeCensus(bump=100, fail={2023: mode}))
    state = tmp_path / "state"
    assert holds(census_folder(state, 2023), total_text(2023)), "the last good copy is gone"
    assert not holds(census_folder(state, 2023), total_text(2023, 100))
    assert holds(census_folder(state, 2024), total_text(2024, 100)), \
        "a failure for one year stopped the others"
    assert "Traceback" not in again.text, again.text
    assert_no_key(again.text, "printed output")


def test_a_failure_on_the_first_fetch_makes_no_copy(tmp_path, monkeypatch):
    run = _fetch(tmp_path, monkeypatch, FakeCensus(fail={"all": "http500"}))
    state = tmp_path / "state"
    for year in T.YEARS:
        assert not holds(census_folder(state, year), total_text(year)), year
    assert "Traceback" not in run.text, run.text


def test_no_key_names_the_key_and_makes_nothing(tmp_path, monkeypatch):
    run = run_fetch_census(monkeypatch, tmp_path / "state", FakeCensus(), key=None)
    assert_is_a_command(run)
    assert run.code != 0, run.text
    assert "CENSUS_API_KEY" in run.text, run.text
    assert run.census.data_requests() == [], "a data request without the key"
    assert not tree_texts(tmp_path / "state" / "census")


def _everything(tmp_path, runs, caplog, extra=()):
    """Every text the key must not be in: each file under tmp_path and under the test's HOME
    folder (the guards' temporary one, R10 point 9), what each run printed, every log line."""
    home = Path(os.environ["HOME"])
    assert "pytest-of-" in str(home), f"HOME is not the test's own folder: {home}"
    out = [("file " + path, text) for path, text in tree_texts(tmp_path).items()]
    out += [("file under HOME " + path, text) for path, text in tree_texts(home).items()]
    out += [("printed output", r.text) for r in runs]
    out += [("log", "\n".join(f"{r.name} {r.getMessage()} {r.exc_text or ''}"
                              for r in caplog.records))]
    return out + list(extra)


def test_the_key_is_not_in_any_file_printed_line_or_log_line(tmp_path, monkeypatch, caplog):
    """A good fetch, then one where one year's service fails and another's error repeats the
    request it was given (key and all): the key is in nothing the program wrote, printed or
    logged."""
    caplog.set_level(logging.DEBUG)
    runs = [_fetch(tmp_path, monkeypatch),
            _fetch(tmp_path, monkeypatch, FakeCensus(fail={2022: "echo_key", 2023: "http500"})),
            _fetch(tmp_path, monkeypatch, FakeCensus(fail={"all": "network"}))]
    for where, text in _everything(tmp_path, runs, caplog):
        assert_no_key(text, where)


@pytest.mark.needs_r
def test_the_key_is_not_in_a_saved_record_or_the_script(tmp_path, monkeypatch, caplog):
    """After a rate answer and its details (with the script): the key is in no saved record,
    stored turn, message to the model, reply or script, and in no file under the folders."""
    caplog.set_level(logging.DEBUG)
    env = S2Env(tmp_path, monkeypatch)
    reply = ask_rate(env, "re_2025")
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    details = details_of(env)
    script = script_of(details).read_text(encoding="utf-8")
    from p1support import db_cells
    extra = [("reply", reply.text), ("details", details.text), ("script", script),
             ("stored turns", json.dumps(env.stored_turns(), default=str)),
             ("memory file", " ".join(str(c) for c in db_cells(tmp_path))),
             ("messages to the model", json.dumps([c["messages"] for c in env.model.calls]))]
    for where, text in _everything(tmp_path, env.census_runs, caplog, extra):
        assert_no_key(text, where)
