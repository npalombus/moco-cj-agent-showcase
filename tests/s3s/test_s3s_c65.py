"""C65 of docs/S3A-DESIGN.md (D-082), the statistics that R runs for. Brief:
briefs/S3-R29-A-tests.md (steps 5 and 6). The tests that need no R are in tests/s3/test_s3_c65.py,
with the readings R29-1 to R29-11 (also in kit-log/raw/S3-R29-A-notes.txt). Tests only; red until
C65 is built, except those that pin what stays (named in their docstrings).

Everything is SYNTHETIC: the Part S fixture stats_like (tests/s3s/fixtures) with its ages changed
in this file so that two records in three are aged 10 to 16 (YOUTH_ROWS: so a statistic of ages 10
to 16 has the records R needs), stats_edges as a second source, and Part S2's rates_like with its
made-up Census copies (tests/s3s2). R really runs (marker needs_r), as in tests/s3s.
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parents[1]
if str(TESTS / "s3s2") not in sys.path:
    sys.path.insert(0, str(TESTS / "s3s2"))

import s3ssupport as T  # noqa: E402
from p1support import THREAD_1, Step, call, finish, mod  # noqa: E402
from s3sagent import MAIN, StatsEnv, service_for  # noqa: E402
from s3support import C62_REFUSAL, COPY_NOW, age, count, dates, is_, months, year  # noqa: E402
from test_s3_c61d import WHY_THREAD, assert_refused  # noqa: E402
from test_s3_c65 import KIND_CASES, WHY, nothing_run, spy_runs  # noqa: E402
from test_s3_round5 import U18  # noqa: E402

EDGES = T.EDGES
MAIN_ID, EDGES_ID = T.SOURCE_IDS[MAIN], T.SOURCE_IDS[EDGES]
A10_16 = age(10, 16)
Y25 = year(2025)
WHOLE = dates("2021-01-01", "2026-10-14")       # stats_like's whole copy
EARLY = dates("2021-01-01", "2023-12-31")       # three whole years the count of 2025 does not share
TALK = ["off", "on"]
FIRST = date(2021, 1, 1)                         # coverage_start of the Part S fixtures


def youth(rows):
    """The rows with two ages in three changed to 10 to 16 (SYNTHETIC, made up for these tests)."""
    out = []
    for i, row in enumerate(rows):
        row = dict(row)
        if i % 3 and row.get("age"):
            row["age"] = str(10 + i % 7)
        out.append(row)
    return out


YOUTH_ROWS = youth(T.fixture_rows(MAIN))


def stats_env(tmp_path, monkeypatch, names=(MAIN,), rows=None, **values):
    rows = dict({MAIN: YOUTH_ROWS}, **(rows or {}))
    return StatsEnv(tmp_path, monkeypatch, names=names, rows={n: rows[n] for n in names if n in rows},
                    **values)


def analyze(kind, period, filters=(), options=None, source=MAIN_ID):
    arguments = {"kind": kind, "source": source, "period": period, "filters": list(filters)}
    if options is not None:
        arguments["options"] = options
    return call("analyze", arguments)


def count_call(period, filters, source=MAIN_ID):
    return count(source, period, filters, [])


def ask(env, question, *calls, text="I found that."):
    return env.ask(question, Step(*calls), Step(finish("finding", text)))


def answered_statistic(env, reply, position=0):
    answer = env.model.answer(0, position)
    assert reply.status == "ANSWERED" and str(answer.get("result_id", "")).startswith("a"), \
        (reply.status, reply.reason_code, answer, reply.text)


def answered_count(env, reply, position=0):
    answer = env.model.answer(0, position)
    assert reply.status == "ANSWERED" and answer.get("result_id", "").startswith("r"), \
        (reply.status, reply.reason_code, answer, reply.text)


def refused_turn(env, reply, why=WHY_THREAD, position=0):
    assert_refused(env.model.answer(0, position), why=why)
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", "NOT_ALLOWED"), \
        (reply.status, reply.reason_code, reply.text)
    if why == WHY_THREAD:
        assert reply.text.startswith(C62_REFUSAL), reply.text


def under_18_in_2025(env, source=MAIN_ID):
    reply = ask(env, "how many arrests of people under 18 were there in 2025?",
                count_call(Y25, [U18], source), text="I counted {r1.count}.")
    answered_count(env, reply)
    return reply


# ---- P20: the trend, then the count -------------------------------------------------------------

@pytest.mark.needs_r
@pytest.mark.parametrize("talk", TALK)
def test_p20_the_trend_is_given_then_under_18_is_refused(tmp_path, monkeypatch, talk):
    """C65's test, point 1, thread P20 ("the count after the trend"): "are arrests of people aged 10
    to 16 going up or down since 2021?" (the trend over the whole copy) is answered; "how many
    arrests of people under 18 were there in 2025?" is then refused: NOT_ALLOWED with C21's `why`
    and C61's sentence, the reply with C62 point 2's sentence. Talk off and on."""
    env = stats_env(tmp_path, monkeypatch, MOCO_TALK=talk)
    reply = ask(env, "are arrests of people aged 10 to 16 going up or down since 2021?",
                analyze("trend", WHOLE, [A10_16]))
    answered_statistic(env, reply)
    reply = ask(env, "how many arrests of people under 18 were there in 2025?",
                count_call(Y25, [U18]), text="I counted {r1.count}.")
    refused_turn(env, reply)


# ---- point 2: each kind, for days the count does not share --------------------------------------

@pytest.mark.needs_r
@pytest.mark.parametrize("kind", list(KIND_CASES))
def test_p2_each_kind_for_days_the_count_does_not_share_is_given(tmp_path, monkeypatch, kind):
    """C65's test, point 2: "the same statistic for days the count does not share is given": under
    18 in 2025, then each kind with an age filter of 10 to 16 over 2021 to 2023: answered, R run.
    Passes today; must still pass.
    Changed by briefs/S3-R31-A-tests.md (C65 point 8), [distribution] only: a distribution of ages
    10 to 16 is now refused on its own, for these days too (NOT_ALLOWED with C21's `why` alone,
    the NOT_ALLOWED row); the test's first point is kept with a distribution point 8 allows: then
    the distribution of under 18 over 2021 to 2023 is answered, R run. Before, the distribution of
    10 to 16 was answered. Fails today (the 10 to 16 one is answered today)."""
    env = stats_env(tmp_path, monkeypatch)
    under_18_in_2025(env)
    filters, options = KIND_CASES[kind]
    if kind == "before_after":
        options = {"date": "2022-07-01"}
    reply = ask(env, "and the same for ages 10 to 16 in 2021 to 2023?",
                analyze(kind, EARLY, filters, options))
    if kind == "distribution":  # C65 point 8 (briefs/S3-R31-A-tests.md)
        refused_turn(env, reply, why=WHY)
        reply = ask(env, "and how old were the people under 18 in 2021 to 2023?",
                    analyze(kind, EARLY, [U18], options))
    answered_statistic(env, reply)


@pytest.mark.needs_r
def test_p2_a_statistic_with_no_age_filter_after_under_18_is_given(tmp_path, monkeypatch):
    """C65's test, point 2: under 18 in 2025, then the trend of every age over the whole copy:
    answered. Passes today; must still pass."""
    env = stats_env(tmp_path, monkeypatch)
    under_18_in_2025(env)
    reply = ask(env, "are arrests going up?", analyze("trend", WHOLE))
    answered_statistic(env, reply)


@pytest.mark.needs_r
def test_p2_under_18_then_17_and_over_after_a_trend_of_every_age(tmp_path, monkeypatch):
    """C65's test, point 2: the trend of every age (answered), under 18 in 2025 (answered: with the
    trend it gives nothing of one year), then 17 and over in 2025: refused with the sentence."""
    env = stats_env(tmp_path, monkeypatch)
    reply = ask(env, "are arrests going up?", analyze("trend", WHOLE))
    answered_statistic(env, reply)
    under_18_in_2025(env)
    reply = ask(env, "and 17 and over in 2025?", count_call(Y25, [age(17)]),
                text="I counted {r1.count}.")
    refused_turn(env, reply)


@pytest.mark.needs_r
def test_p2b_a_count_after_a_statistic_of_the_same_message(tmp_path, monkeypatch):
    """Point 2b, "the statistics of the message": the trend of 10 to 16 and then under 18 in 2025 in
    one message: the trend answered, the count refused with C21's `why` alone; the turn ANSWERED."""
    env = stats_env(tmp_path, monkeypatch)
    reply = env.ask("is 10 to 16 going up, and how many under 18 in 2025?",
                    Step(analyze("trend", WHOLE, [A10_16])), Step(count_call(Y25, [U18])),
                    Step(finish("finding", "I found that.")))
    assert str(env.model.answer(0).get("result_id")).startswith("a"), env.model.answer(0)
    assert_refused(env.model.answer(1), why=WHY)
    assert reply.status == "ANSWERED", (reply.status, reply.reason_code, reply.text)


@pytest.mark.needs_r
def test_p2c_the_memory_record_holds_a_statistics_days(tmp_path, monkeypatch):
    """C65's test, point 2 ("the memory record holds a statistic's days"), point 2c: the remembered
    analysis holds `days`, the first and last day its copy covered, as two ISO dates."""
    env = stats_env(tmp_path, monkeypatch)
    reply = ask(env, "are arrests going up?", analyze("trend", WHOLE))
    answered_statistic(env, reply)
    (turn,) = env.store.recent_turns(THREAD_1, 10)
    (stored,) = turn["results"]
    assert stored["kind"] == "analysis" and stored.get("days") == [FIRST.isoformat(),
                                                                    T.NEWEST.isoformat()], stored


def rows_until(day):
    return [r for r in YOUTH_ROWS if r["event_date_time"][:10] <= day.isoformat()]


@pytest.mark.needs_r
@pytest.mark.parametrize("period, refused", [(dates("2026-07-01", "2026-09-30"), False),
                                             (months(2026, 1, 4), True)],
                         ids=["days after the old copy", "days of the old copy"])
def test_p2c_a_refresh_between_the_statistic_and_the_count(tmp_path, monkeypatch, period, refused):
    """Point 2c with C62 point 5: the trend of 10 to 16 from 2024 to the end of 2026 on a copy that
    ends on 30 June 2026 (answered); the copy is refreshed (to 14 October 2026); under 18 from July
    to September 2026 is answered (the statistic's days end with its own copy, kept in `days`),
    under 18 from January to April 2026 refused with the sentence."""
    env = stats_env(tmp_path, monkeypatch, rows={MAIN: rows_until(date(2026, 6, 30))})
    reply = ask(env, "is 10 to 16 going up since 2024?",
                analyze("trend", dates("2024-01-01", "2026-12-31"), [A10_16]))
    answered_statistic(env, reply)
    made = mod("sources").fetch(MAIN_ID, state_dir=env.state_dir,
                                transport=service_for(MAIN, YOUTH_ROWS),
                                now=COPY_NOW + timedelta(minutes=30))
    assert made.newest_day == T.NEWEST, made.newest_day
    reply = ask(env, "how many under 18?", count_call(period, [U18]), text="I counted {r1.count}.")
    if refused:
        refused_turn(env, reply)
    else:
        answered_count(env, reply)


@pytest.mark.needs_r
@pytest.mark.parametrize("order", ["statistic first", "count first"])
def test_another_sources_statistic_is_never_read_in(tmp_path, monkeypatch, order):
    """C65's test, point 1 ("another source's figures are never read in"), for a statistic: the
    trend of 10 to 16 of stats_like and under 18 in 2025 of stats_edges, in either order: both
    answered. Then under 18 in 2025 of stats_like is refused (the premise that it is read)."""
    env = stats_env(tmp_path, monkeypatch, names=(MAIN, EDGES))
    trend = analyze("trend", WHOLE, [A10_16])
    if order == "statistic first":
        answered_statistic(env, ask(env, "is 10 to 16 going up?", trend))
        under_18_in_2025(env, EDGES_ID)
    else:
        under_18_in_2025(env, EDGES_ID)
        answered_statistic(env, ask(env, "is 10 to 16 going up?", trend))
    reply = ask(env, "how many under 18 in 2025?", count_call(Y25, [U18]),
                text="I counted {r1.count}.")
    refused_turn(env, reply)


# ---- rates (Part S2's fixture) ------------------------------------------------------------------

def rate_env(tmp_path, monkeypatch, **values):
    from s2agent import S2Env
    return S2Env(tmp_path, monkeypatch, **values)


def rate(period, by="age_band"):
    """A rate; the age filter that C9 would keep from the count before is cleared (a rate takes no
    filter, R10 point 7)."""
    from s2agent import RATES_ID
    return call("analyze", {"kind": "rate", "source": RATES_ID, "period": period,
                            "filters": [{"field": "age", "clear": True}], "options": {"by": by}})


def rates_count(period, filters):
    from s2agent import RATES_ID
    return count(RATES_ID, period, filters, [])


@pytest.mark.needs_r
@pytest.mark.parametrize("talk", TALK)
def test_rate_by_age_band_after_10_to_16_is_refused_before_anything_is_computed(
        tmp_path, monkeypatch, talk):
    """C65's test, point 2: 10 to 16 in 2025 (answered), then a rate by age band of 2025: refused,
    NOT_ALLOWED with the sentence, nothing computed; the reply C62 point 2's sentence."""
    env = rate_env(tmp_path, monkeypatch, MOCO_TALK=talk)
    reply = ask(env, "how many aged 10 to 16 in 2025?", rates_count(Y25, [A10_16]),
                text="I counted {r1.count}.")
    answered_count(env, reply)
    calls = spy_runs(monkeypatch)
    reply = ask(env, "and the arrest rate by age band in 2025?", rate(Y25))
    refused_turn(env, reply)
    nothing_run(env, calls)


@pytest.mark.needs_r
def rate_of_2023_after_10_to_16(tmp_path, monkeypatch):
    env = rate_env(tmp_path, monkeypatch)
    reply = ask(env, "how many aged 10 to 16 in 2025?", rates_count(Y25, [A10_16]),
                text="I counted {r1.count}.")
    answered_count(env, reply)
    reply = ask(env, "and the arrest rate by age band in 2023?", rate(year(2023)))
    answered_statistic(env, reply)
    return env


@pytest.mark.needs_r
def test_rate_by_age_band_of_another_year_is_given(tmp_path, monkeypatch):
    """C65's test, point 2, for a rate: 10 to 16 in 2025, then a rate by age band of 2023 (days the
    count does not share): answered, R run. Passes today; must still pass."""
    rate_of_2023_after_10_to_16(tmp_path, monkeypatch)


@pytest.mark.needs_r
def test_p2c_the_memory_record_holds_a_rates_days(tmp_path, monkeypatch):
    """Point 2c for a rate: the remembered rate holds `days`, as two ISO dates."""
    env = rate_of_2023_after_10_to_16(tmp_path, monkeypatch)
    stored = env.store.recent_turns(THREAD_1, 10)[-1]["results"]
    assert [r.get("days") for r in stored] == [[FIRST.isoformat(), T.NEWEST.isoformat()]], stored


@pytest.mark.needs_r
def test_a_count_after_a_rate_by_age_band_is_refused(tmp_path, monkeypatch):
    """Point 2b for a rate: the rate by age band of 2025 (answered), then 10 to 16 in 2025: refused
    with the sentence (the band 10 to 17 less 10 to 16 is the 17-year-olds)."""
    env = rate_env(tmp_path, monkeypatch)
    reply = ask(env, "the arrest rate by age band in 2025?", rate(Y25))
    answered_statistic(env, reply)
    reply = ask(env, "how many aged 10 to 16 in 2025?", rates_count(Y25, [A10_16]),
                text="I counted {r1.count}.")
    refused_turn(env, reply)


@pytest.mark.needs_r
def test_a_rate_by_gender_after_under_18_is_given(tmp_path, monkeypatch):
    """A rate whose only band is every age (by gender) gives no single year with under 18 in 2025:
    answered. Passes today; must still pass."""
    env = rate_env(tmp_path, monkeypatch)
    reply = ask(env, "how many under 18 in 2025?", rates_count(Y25, [U18]),
                text="I counted {r1.count}.")
    answered_count(env, reply)
    reply = ask(env, "the arrest rate by gender in 2025?", rate(Y25, "gender"))
    answered_statistic(env, reply)
