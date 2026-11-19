"""D5 (docs/D-DESIGN.md): MOCO_REFRESH_HOURS, a whole number from 0 to 168; 0 (the default)
is off; anything else is a ConfigError naming the key. Above 0, with MOCO_DATA=county, serve
keeps the copies fresh by itself: at start and every ten minutes it looks at every valid
source; a source with no copy, or whose newest copy was fetched more than that many hours
ago, is due; each due source is fetched as D4 does it (pruning included); this runs beside
the Slack connection and never blocks or stops it; a failure of any kind is caught, logged
as one line (the source id and what failed) and tried again at the next look; a source that
failed is not tried more than once an hour; a turn uses the newest copy there is when it
starts. With MOCO_DATA not county the setting is read and checked but nothing is fetched.
`moco_agent.refresh.due(sources, state_dir, now, hours)` gives the due ids in order;
`moco_agent.refresh.run_once(state_dir, now, hours, transport=None)` fetches what is due and
returns {source id: "ok" or the failure's text}.

D8: due with no copy, a copy one minute younger than the limit, one minute older; run_once
fetches only what is due; a failure is returned and logged and raises nothing; a source that
failed is not tried again within the hour; 0, 168 and each bad value (-1, 169, 1.5, x,
empty); with MOCO_DATA not county nothing is fetched; serve with the Slack stand-in starts
the refresh and still answers a message while a slow fetch is under way.

due and run_once are called in this process with a `now` of the test's own, the fixture
sources (written as arrests_like.json and coded_like.json, so file order is id order) and
the fake county service; nothing is slept. serve runs against a copy of the program with the
Slack stand-in (tests/d/standin.py); its "slow fetch" is a fake service whose first request
waits on an event the stand-in sets only after the message has been answered.

Readings (kit-log/raw/D-A-notes.txt):
- `sources` given to due is what sources.load_sources() returns ({id: source file}).
- The keys of run_once's answer are the sources it tried; a source it did not try (not
  due, or failed within the hour) may be left out, and is never "ok".
- "The failure's text" holds the reason fetch gives (FetchFailed's text) when fetch failed.
- "Logged" is a record of a moco_agent logger (serve writes those to agent.log); "one line"
  is a record with no line break and no traceback attached.
- What the failure memory belongs to is not said; each test that makes a source fail uses a
  source id no other test uses, so the tests hold whether it is kept per state folder or
  for the whole process.
- An empty MOCO_REFRESH_HOURS is a bad value (D8 says so), although config.py treats an
  empty value as unset for every other key.
"""
import logging
from datetime import datetime, timedelta, timezone

import pytest

from dsupport import (A_ID, A_NAME, C_ID, C_NAME, COUNTY_FIRST, COUNTY_Q, COUNTY_STEPS,
                      SETTINGS_EXIT, SYNTHETIC_Q, SYNTHETIC_STEPS, Sandbox, Services,
                      address_for, copy_names, files_under, log_lines, make_copies, message,
                      project_folders, serve_env, service, source_file, tree_bytes, utc_now,
                      write_files)
from p1support import make_settings, mod
from s3support import (FakeService, bulk_rows, copies_root, current_folder, fixture_rows,
                       source_json, use_sources)

NOW = datetime(2026, 11, 13, 12, 0, 0, tzinfo=timezone.utc)
MINUTE = timedelta(minutes=1)
A_ADDRESS, C_ADDRESS = source_json(A_NAME)["address"], source_json(C_NAME)["address"]
REDIRECT = "the service answered with HTTP status 302, not a list of rows"


# ---- the setting -------------------------------------------------------------------------------

@pytest.mark.parametrize("value, hours", [(None, 0), ("0", 0), ("24", 24), ("168", 168)],
                         ids=["unset", "0", "24", "168"])
def test_whole_hours_from_0_to_168_are_read(tmp_path, value, hours):
    values = {} if value is None else {"MOCO_REFRESH_HOURS": value}
    assert make_settings(tmp_path, **values).moco_refresh_hours == hours


@pytest.mark.parametrize("value", ["-1", "169", "1.5", "x", ""],
                         ids=["minus_1", "169", "1.5", "x", "empty"])
def test_a_bad_value_is_a_config_error_naming_the_key(tmp_path, value):
    config = mod("config")
    with pytest.raises(config.ConfigError) as caught:
        make_settings(tmp_path, MOCO_REFRESH_HOURS=value)
    assert "MOCO_REFRESH_HOURS" in str(caught.value)


# ---- due ----------------------------------------------------------------------------------------

def sources_here(tmp_path, monkeypatch, *extra, fixtures=True):
    """The two fixture source files (unless `fixtures` is False) and the `extra` dicts in
    tmp_path/sources, read through load_sources() by the program."""
    files = ({"arrests_like.json": source_file(A_NAME), "coded_like.json": source_file(C_NAME)}
             if fixtures else {})
    files.update({f"{data['id'].split(':', 1)[1]}.json": data for data in extra})
    folder = write_files(tmp_path / "sources", files)
    use_sources(monkeypatch, folder)
    return folder


def copy_at(monkeypatch, folder, state, when, name=A_NAME, **kw):
    make_copies(monkeypatch, folder, state, name, [when], **kw)


def due(state, hours, now=NOW):
    return list(mod("refresh").due(mod("sources").load_sources(), state, now, hours))


def test_a_source_with_no_copy_is_due(tmp_path, monkeypatch):
    sources_here(tmp_path, monkeypatch)
    assert due(tmp_path / "state", 24) == [A_ID, C_ID]


@pytest.mark.parametrize("hours", [1, 24, 168])
def test_a_copy_one_minute_younger_than_the_limit_is_not_due(tmp_path, monkeypatch, hours):
    folder, state = sources_here(tmp_path, monkeypatch), tmp_path / "state"
    copy_at(monkeypatch, folder, state, NOW - timedelta(hours=hours) + MINUTE)
    assert due(state, hours) == [C_ID]


@pytest.mark.parametrize("hours", [1, 24, 168])
def test_a_copy_one_minute_older_than_the_limit_is_due(tmp_path, monkeypatch, hours):
    folder, state = sources_here(tmp_path, monkeypatch), tmp_path / "state"
    copy_at(monkeypatch, folder, state, NOW - timedelta(hours=hours) - MINUTE)
    assert due(state, hours) == [A_ID, C_ID]


def test_due_goes_by_the_newest_copy(tmp_path, monkeypatch):
    """An old copy and a fresh one: the newest decides, so the source is not due."""
    folder, state = sources_here(tmp_path, monkeypatch), tmp_path / "state"
    make_copies(monkeypatch, folder, state, A_NAME, [NOW - timedelta(days=3),
                                                      NOW - timedelta(hours=1)])
    make_copies(monkeypatch, folder, state, C_NAME, [NOW - timedelta(days=3)])
    assert due(state, 24) == [C_ID]


# ---- run_once -------------------------------------------------------------------------------------

def run_once(state, transport, now=NOW, hours=24):
    return mod("refresh").run_once(state, now, hours, transport=transport)


def lone_source(tag):
    """A source file of its own (the arrests fixture with id FIXTURE:<tag> and an address of
    its own), so that no other test makes the same id fail."""
    return source_file(A_NAME, sid=f"FIXTURE:{tag}", address=address_for(tag))


def records_naming(caplog, sid):
    return [r for r in caplog.records if sid in r.getMessage()]


def assert_logged_once_per_line(caplog, sid, *, holding=None):
    found = records_naming(caplog, sid)
    assert found, f"no log line names {sid}"
    for record in found:
        assert record.name.startswith("moco_agent"), record.name
        assert "\n" not in record.getMessage() and record.exc_info is None, record.getMessage()
    if holding is not None:
        assert any(holding in r.getMessage() for r in found), [r.getMessage() for r in found]


def test_run_once_fetches_only_what_is_due(tmp_path, monkeypatch):
    """The arrests copy is an hour old (not due), the coded source has none (due): only the
    coded source is fetched, and the answer says so."""
    folder, state = sources_here(tmp_path, monkeypatch), tmp_path / "state"
    copy_at(monkeypatch, folder, state, NOW - timedelta(hours=1))
    kept = tree_bytes(copies_root(state, A_NAME))
    services = Services({A_ADDRESS: FakeService(fixture_rows(A_NAME), address=A_ADDRESS),
                         C_ADDRESS: FakeService(fixture_rows(C_NAME), address=C_ADDRESS)})
    assert run_once(state, services) == {C_ID: "ok"}
    assert A_ADDRESS not in services.asked and C_ADDRESS in services.asked
    assert current_folder(state, C_NAME) is not None
    assert tree_bytes(copies_root(state, A_NAME)) == kept


def test_a_failure_is_returned_and_logged_and_raises_nothing(tmp_path, monkeypatch, caplog):
    """A due source with a last good copy fails (a redirect): run_once raises nothing,
    answers with fetch's reason for it, logs one line naming it, and the last good copy is
    byte for byte what it was. The other sources are still fetched."""
    caplog.set_level(logging.INFO)
    lone = lone_source("d5_returned")
    folder, state = sources_here(tmp_path, monkeypatch, lone), tmp_path / "state"
    copy_at(monkeypatch, folder, state, NOW - timedelta(days=2), sid=lone["id"],
            address=lone["address"])
    kept = tree_bytes(copies_root(state, "d5_returned"))
    services = Services({
        lone["address"]: FakeService(fixture_rows(A_NAME), address=lone["address"],
                                     fail={"all": "redirect"}),
        A_ADDRESS: FakeService(fixture_rows(A_NAME), address=A_ADDRESS),
        C_ADDRESS: FakeService(fixture_rows(C_NAME), address=C_ADDRESS)})
    answer = run_once(state, services)
    assert answer[A_ID] == "ok" and answer[C_ID] == "ok", answer
    text = answer[lone["id"]]
    assert isinstance(text, str) and text != "ok" and REDIRECT in text, text
    assert_logged_once_per_line(caplog, lone["id"], holding=REDIRECT)
    assert tree_bytes(copies_root(state, "d5_returned")) == kept


def test_a_failure_of_any_kind_is_caught(tmp_path, monkeypatch, caplog):
    """A transport that raises something fetch does not expect (a RuntimeError): run_once
    still raises nothing, answers with a text that is not "ok", and logs one line naming the
    source."""
    caplog.set_level(logging.INFO)
    lone = lone_source("d5_any_kind")
    sources_here(tmp_path, monkeypatch, lone)

    def broken(*args, **kwargs):
        raise RuntimeError("SYNTHETIC fixture: an unexpected fault")

    services = Services({lone["address"]: broken,
                         A_ADDRESS: FakeService(fixture_rows(A_NAME), address=A_ADDRESS),
                         C_ADDRESS: FakeService(fixture_rows(C_NAME), address=C_ADDRESS)})
    answer = run_once(tmp_path / "state", services)
    text = answer[lone["id"]]
    assert isinstance(text, str) and text.strip() and text != "ok", text
    assert answer[A_ID] == "ok" and answer[C_ID] == "ok", answer
    assert_logged_once_per_line(caplog, lone["id"])


def test_a_source_that_failed_is_not_tried_again_within_the_hour(tmp_path, monkeypatch):
    """It fails at NOW; at NOW + 59 minutes it is not tried (no request reaches its
    service); at NOW + 61 minutes it is tried again, and succeeds. (Only this source is
    offered, so no other source fails here.)"""
    lone = lone_source("d5_hourly")
    state = tmp_path / "state"
    sources_here(tmp_path, monkeypatch, lone, fixtures=False)
    failing = Services({lone["address"]: FakeService(fixture_rows(A_NAME),
                                                     address=lone["address"],
                                                     fail={"all": "redirect"})})
    first = run_once(state, failing, now=NOW)
    assert first[lone["id"]] != "ok" and lone["address"] in failing.asked, first
    good = Services({lone["address"]: FakeService(fixture_rows(A_NAME), address=lone["address"])})
    second = run_once(state, good, now=NOW + 59 * MINUTE)
    assert lone["address"] not in good.asked, "tried again within the hour"
    assert second.get(lone["id"]) != "ok", second
    third = run_once(state, good, now=NOW + 61 * MINUTE)
    assert lone["address"] in good.asked, "not tried again after the hour"
    assert third[lone["id"]] == "ok", third


def test_run_once_prunes_as_refresh_does(tmp_path, monkeypatch):
    """A due source with three copies, fetched by run_once: the newest three stay (the
    oldest dated folder is gone); a source that is not due is left as it was."""
    folder, state = sources_here(tmp_path, monkeypatch), tmp_path / "state"
    make_copies(monkeypatch, folder, state, A_NAME,
                [NOW - timedelta(days=d) for d in (4, 3, 2)])
    make_copies(monkeypatch, folder, state, C_NAME, [NOW - timedelta(hours=1)])
    old = copy_names(state, A_NAME)
    kept = tree_bytes(copies_root(state, C_NAME))
    services = Services({A_ADDRESS: FakeService(fixture_rows(A_NAME), address=A_ADDRESS),
                         C_ADDRESS: FakeService(fixture_rows(C_NAME), address=C_ADDRESS)})
    assert run_once(state, services) == {A_ID: "ok"}
    now = copy_names(state, A_NAME)
    assert len(now) == 3 and now[:2] == old[1:], (old, now)
    assert not (copies_root(state, A_NAME) / old[0]).exists()
    assert tree_bytes(copies_root(state, C_NAME)) == kept


# ---- serve -------------------------------------------------------------------------------------------

def county_serve_env(state, hours, **extra):
    return serve_env(MOCO_DATA="county", MOCO_STATE_DIR=state, MOCO_REFRESH_HOURS=hours,
                     **extra)


def reply_texts(result):
    return [p["text"] for p in result.posts if p["text"] != "One moment."]


def test_serve_refreshes_beside_slack_and_answers_during_a_slow_fetch(tmp_path, monkeypatch):
    """serve, county mode, MOCO_REFRESH_HOURS=24. The arrests copy is two days old (due),
    the coded copy an hour old (not due). The arrests service is slow and would serve 30
    more 2025 rows. The refresh starts by itself (the slow fetch is entered before the
    message comes); the message is answered while that fetch is still under way, from the
    copy there was when the turn started (240, not 270); the coded source is not fetched.
    The real project's var/ and runs/ are listed before and after."""
    before = project_folders()
    box, state = Sandbox(tmp_path), tmp_path / "state"
    make_copies(monkeypatch, box.sources_dir, state, A_NAME, [utc_now() - timedelta(days=2)])
    make_copies(monkeypatch, box.sources_dir, state, C_NAME, [utc_now() - timedelta(hours=1)])
    result = box.run("serve", env=county_serve_env(state, 24), steps=COUNTY_STEPS,
                     events=[message(COUNTY_Q)],
                     services=[service(A_NAME, slow=True,
                                       extra_rows=bulk_rows(A_NAME, 30, year=2025)),
                               service(C_NAME)])
    assert result.code == 0, result.explain()
    slow = result.report["slow"]
    assert slow["entered_before_message"], "serve did not start the refresh"
    assert result.report["answered"] == [True], "the message was not answered in time"
    assert slow["finished_before_reply"] is False, "the reply waited for the fetch"
    (text,) = reply_texts(result)
    assert text.startswith(COUNTY_FIRST), text
    assert C_ADDRESS not in result.report["requests"]
    assert project_folders() == before, "the real project's var/ or runs/ changed"


def test_serve_logs_a_failed_refresh_and_keeps_answering(tmp_path, monkeypatch):
    """serve, county mode, 24 hours, no copy of either source; the arrests service fails
    (a redirect). The refresh logs one line naming the arrests source with fetch's reason,
    goes on to the coded source (fetched next, in id order), and the message is answered."""
    box, state = Sandbox(tmp_path), tmp_path / "state"
    result = box.run("serve", env=county_serve_env(state, 24), steps=COUNTY_STEPS,
                     events=[message(COUNTY_Q)], wait_for=[C_ADDRESS],
                     services=[service(A_NAME, fail="redirect"), service(C_NAME)])
    assert result.code == 0, result.explain()
    assert result.report["seen"] == {C_ADDRESS: True}, "the coded source was not fetched"
    assert result.report["answered"] == [True] and reply_texts(result), result.explain()
    naming = [line for line in log_lines(state / "agent.log") if A_ID in line]
    assert any(REDIRECT in line for line in naming), naming


def test_serve_in_synthetic_mode_checks_the_hours_but_fetches_nothing(tmp_path):
    """MOCO_DATA not county: a bad MOCO_REFRESH_HOURS still stops serve (exit 4, the key
    named, Slack not touched); with 24, serve answers and nothing is fetched, though
    neither source has a copy."""
    box, state = Sandbox(tmp_path), tmp_path / "state"
    bad = box.run("serve", env=serve_env(MOCO_STATE_DIR=state, MOCO_REFRESH_HOURS="x"))
    assert bad.code == SETTINGS_EXIT, bad.explain()
    assert "MOCO_REFRESH_HOURS" in bad.stdout + bad.stderr, bad.explain()
    assert bad.report["apps"] == 0 and bad.report["socket_handlers"] == 0
    good = box.run("serve", env=serve_env(MOCO_DATA="synthetic", MOCO_STATE_DIR=state,
                                          MOCO_REFRESH_HOURS=24),
                   steps=SYNTHETIC_STEPS, events=[message(SYNTHETIC_Q)],
                   services=[service(A_NAME), service(C_NAME)])
    assert good.code == 0, good.explain()
    assert good.report["answered"] == [True], good.explain()
    assert good.report["requests"] == []
    assert not (state / "copies").exists()


def test_serve_in_county_mode_with_0_fetches_nothing_and_with_169_stops(tmp_path):
    """0 is off: serve answers in county mode and fetches nothing, though neither source has
    a copy. 169 stops serve before Slack with exit code 4 naming the key."""
    box, state = Sandbox(tmp_path), tmp_path / "state"
    off = box.run("serve", env=county_serve_env(state, 0), steps=COUNTY_STEPS,
                  events=[message(COUNTY_Q)], services=[service(A_NAME), service(C_NAME)])
    assert off.code == 0, off.explain()
    assert off.report["answered"] == [True], off.explain()
    assert off.report["requests"] == []
    too_many = box.run("serve", env=county_serve_env(state, 169))
    assert too_many.code == SETTINGS_EXIT, too_many.explain()
    assert "MOCO_REFRESH_HOURS" in too_many.stdout + too_many.stderr, too_many.explain()
    assert too_many.report["apps"] == 0 and too_many.report["socket_handlers"] == 0
    assert files_under(box.var) == []
