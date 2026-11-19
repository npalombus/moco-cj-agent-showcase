"""R9, point 7: the chart exists, has the stated size and is not blank (docs/S3S2-DESIGN.md R6:
"one dot per group with its range, the reference group marked"; Part S's S6: PNG, 1600 by
1000 pixels, attached to the same message). With R1 and R8 on `details`: it names the Census
table and year, and its script (S7) downloads both the county data and the Census tables from
their public addresses, the Census address holding no key, with one comment line telling the
reader to add their own.

How a chart looks is not judged (Part S's S9 "cannot show"). READINGS: the chart is the
reply's chart_path (Part S); the script is the one .R file attached to the details message
(Part S, s3sagent.attached). A key in the script would be the made-up one or any `key=` with a
value. Every test starts R.
"""
import re
from pathlib import Path

import pytest

import s2support as T
from s2agent import (KEY, RATES, S2Env, ask_rate, census_date_re, details_of, script_of)

DATA_URL = re.compile(r'(?m)^data_url <- "([^"\n]+)"\s*$')


@pytest.mark.needs_r
@pytest.mark.parametrize("name", ["re_2025", "gender_2025", "all_2025"])
def test_the_chart(tmp_path, monkeypatch, name):
    t = T.truth(name)
    env = S2Env(tmp_path, monkeypatch, names=(t["source"],))
    reply = ask_rate(env, name)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    assert reply.chart_path, "R6: a chart with the rate answer"
    path = Path(reply.chart_path)
    assert path.is_file(), path
    width, height = T.S.png_header(path)[:2]
    assert (width, height) == (1600, 1000), (width, height)
    assert T.S.png_distinct_pixels(path, limit=50) > 2, "the chart is blank"


@pytest.mark.needs_r
@pytest.mark.parametrize("name,tables", [("re_2025", ("B03002",)),
                                         ("gender_2025", ("B01001",)),
                                         ("re_2024_25", ("B03002",))])
def test_details_name_the_census_table_year_and_copy(tmp_path, monkeypatch, name, tables):
    """R1: the agent names the table and year in `details`; R6: each source with its copy's
    date; the county's notices still word for word (C11)."""
    t = T.truth(name)
    env = S2Env(tmp_path, monkeypatch, names=(t["source"],))
    reply = ask_rate(env, name)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    details = details_of(env)
    for table in tables:
        assert table in details.text, (table, details.text)
    for year in t["years"]:
        assert str(year) in details.text, (year, details.text)
    assert "Census" in details.text
    assert re.search(census_date_re(env.census_runs[-1]), details.text), details.text
    for notice in T.source_json(t["source"])["notices"]:
        assert notice in details.text, notice


@pytest.mark.needs_r
@pytest.mark.parametrize("name", ["re_2025", "gender_2025"])
def test_the_script_downloads_both_and_holds_no_key(tmp_path, monkeypatch, name):
    t = T.truth(name)
    env = S2Env(tmp_path, monkeypatch, names=(t["source"],))
    reply = ask_rate(env, name)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)
    script = script_of(details_of(env)).read_text(encoding="utf-8")
    county = DATA_URL.findall(script)
    assert len(county) == 1 and county[0].startswith(T.source_json(t["source"])["address"]), \
        "S7: the county's address once, on its data_url line"
    assert "api.census.gov" in script, "R8: the script downloads the Census tables too"
    for table in ("B03002",) if t["by"] == "race_ethnicity" else ("B01001",):
        assert table in script, table
    for part in T.KEY_PARTS:
        assert part not in script, "the made-up key is in the script"
    assert not re.search(r"[?&]key=[A-Za-z0-9]", script), "R8: the Census address holds no key"
    comments = [line for line in script.splitlines()
                if line.lstrip().startswith("#") and re.search(r"(?i)\bkey\b", line)]
    assert len(comments) >= 1, "R8: one comment line tells the reader to add their own key"
    assert "FIXTURE-" not in script and not re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}",
                                                      script), "a record in the script"
