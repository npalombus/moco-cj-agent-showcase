"""The live check on real county data (stage 3): does the real model, given a real
question, ask Python for the right count?

    python tools/county_check.py --models <model id>[,<model id>] [--repeat 3] [--talk]
                                 [--cases config/loop_check_cases_s3.json] [--only C01,C02]

It runs every case of the cases file through the agent loop in county mode, with the real
NVIDIA model and the copies already in the state folder (MOCO_STATE_DIR; run
`python -m moco_agent refresh` or `fetch` first). It fetches nothing itself. Earlier turns
of a case are replayed with a stand-in model, so only the case's own question costs model
requests. A case passes when the status, the counts that ran (source, period, filters and
breakdown, compared after the program's own tidying), and whether a share or a comparison
was made are what the case expects. Numbers are not judged here: Python makes them, and
they are checked against the planning chat's reference answers elsewhere.

Each run's record is kept under runs/county-check/ (not in git). It prints no key and no
record of the data. Exit 0 when a model passes every must case in at least 2 of 3 runs
(or all runs, when --repeat is under 3), 1 when none does, 4 when a setting or a copy is
missing. Written by the planning chat (D-050).
"""
import argparse
import dataclasses
import json
import sys
import time
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from loop_check import Paced, Scripted  # noqa: E402  (the pacing and the stand-in model)

from moco_agent import counting, sources, stats  # noqa: E402
from moco_agent.agent import handle_question  # noqa: E402
from moco_agent.config import (ConfigError, load_settings, require_for_model,  # noqa: E402
                               with_model)
from moco_agent.llm import NvidiaModelClient  # noqa: E402
from moco_agent.memory import Store  # noqa: E402
from moco_agent.registry import load_registry  # noqa: E402

DEFAULT_CASES = REPO / "config" / "loop_check_cases_s3.json"
THREAD, USER = "county-check:local:thread", "county-check"


def same_ages(source, flt):
    """An age filter with an end at the edge of the usable ages left out, so that "10 to 17"
    and "to 17" compare equal: they are the same records (found by the live run of
    2026-11-13, case C13)."""
    age = next((f for f in source["fields"] if f["kind"] == "age"), None)
    if age is None or flt.get("field") != age["name"]:
        return flt
    low, high = age["usable"]
    return {k: v for k, v in flt.items()
            if not (k == "from" and v <= low) and not (k == "to" and v >= high)}


def tidy_spec(spec, loaded, copies):
    """A count request in the program's own tidy form, as text, with the filters in a fixed
    order, so that two ways of writing one request compare equal."""
    source = loaded[spec["source"]]
    tidy = counting.check_spec(source, copies[spec["source"]], dict(spec))
    tidy = dict(tidy, filters=sorted((same_ages(source, f) for f in tidy["filters"]),
                                     key=lambda f: json.dumps(f, sort_keys=True)))
    return json.dumps(tidy, sort_keys=True, default=str)


def same_options(source, options):
    """same_ages inside the filter lists of an analysis's options (versus, part)."""
    if not isinstance(options, dict):
        return options
    out = dict(options)
    for key in ("versus", "part"):
        if isinstance(out.get(key), list):
            out[key] = sorted((same_ages(source, f) for f in out[key]),
                              key=lambda f: json.dumps(f, sort_keys=True))
    return out


def tidy_analysis(a, loaded):
    """An analysis in the program's own tidy form, as text: its kind, source, filters (in a
    fixed order) and options as `stats.check_options` writes them. The period is left out:
    the months used are compared through `window` where a case gives one."""
    source = loaded[a["source"]]
    filters = counting.check_filters(source, list(a.get("filters") or []))
    if a["kind"] == "rate":  # Part S2: a rate is judged by its breakdown only
        options = {"by": (a.get("options") or {}).get("by")}
    else:
        options = stats.check_options(source, {"filters": filters}, a["kind"], a.get("options"))
    return json.dumps({"kind": a["kind"], "source": a["source"],
                       "options": same_options(source, options),
                       "filters": sorted((same_ages(source, f) for f in filters),
                                         key=lambda f: json.dumps(f, sort_keys=True))},
                      sort_keys=True, default=str)


def seed_steps(turn):
    """The steps that remake one earlier ANSWERED turn of a case from its counts, or from
    one trend analysis (`"trend": {source, period, filters}`; it runs R), or one talk reply
    (`"talk": "<the reply>"`, status TALKED)."""
    if turn.get("talk"):
        return [[("finish", {"kind": "talk", "text": turn["talk"]})]]
    if turn.get("trend"):
        return [[("analyze", dict(turn["trend"], kind="trend"))],
                [("finish", {"kind": "finding", "text": "I found that {a1.trend}."})]]
    counts = [("count", dict(spec)) for spec in turn["counts"]]
    text = "I counted " + " and ".join(f"{{r{i + 1}.count}}" for i in range(len(counts))) + "."
    return [counts, [("finish", {"kind": "finding", "text": text})]]


def run_case(case, model, settings, registry, today, folder):
    """Replay the case's earlier turns, then one real turn. Returns (reply, seconds)."""
    store, runs = Store(folder / "agent.db"), folder / "runs"
    now = datetime.now(timezone.utc)
    try:
        for i, turn in enumerate(case["thread"]):
            seeded = handle_question(
                turn.get("question", "An earlier question of this thread."),
                thread_key=THREAD, user_id=USER, settings=settings, registry=registry,
                model_client=Scripted(seed_steps(turn)), store=store, runs_dir=runs,
                today=today, now=now - timedelta(minutes=10 * (len(case["thread"]) - i)))
            if seeded.status != turn["status"]:
                raise RuntimeError(f"replaying the earlier turn of {case['id']} gave "
                                   f"{seeded.status} ({seeded.reason_code})")
        started = time.monotonic()
        reply = handle_question(case["question"], thread_key=THREAD, user_id=USER,
                                settings=settings, registry=registry, model_client=model,
                                store=store, runs_dir=runs, today=today, now=now)
        return reply, time.monotonic() - started
    finally:
        store.close()


def judge(case, reply, loaded, copies):
    """Why the run fails against the case's `expect`, or "" when it passes. A case may give
    `expect_or`: other answers that are also right; the run passes if any of them passes,
    and the reasons given are those of `expect`."""
    first = judge_one(case["id"], case["expect"], reply, loaded, copies)
    if first and any(not judge_one(case["id"], other, reply, loaded, copies)
                     for other in case.get("expect_or") or []):
        return ""
    return first


def judge_one(case_id, expect, reply, loaded, copies):
    case, problems = {"id": case_id}, []
    ran = [r for r in reply.results if r["kind"] == "count"]
    if reply.status not in expect["status"]:
        problems.append(f"status {reply.status}"
                        + (f" ({reply.reason_code})" if reply.reason_code else ""))
    if expect["counts"] is not None:
        try:
            want = {tidy_spec(s, loaded, copies) for s in expect["counts"]}
        except (counting.SpecError, KeyError) as e:
            raise RuntimeError(f"case {case['id']}: an expected count is not a valid request "
                               f"({type(e).__name__}: {e})") from None
        got = {tidy_spec(r["spec"], loaded, copies) for r in ran}
        if got != want:
            problems.append("counts " + "; ".join(sorted(r["read_as"] for r in ran)) if ran
                            else "no count ran")
    if expect.get("analyses") is not None:  # version 2: which analyses ran
        analyses = [r for r in reply.results if r["kind"] == "analysis"]
        try:
            want = sorted(tidy_analysis(a, loaded) for a in expect["analyses"])
        except (counting.SpecError, KeyError) as e:
            raise RuntimeError(f"case {case['id']}: an expected analysis is not a valid request "
                               f"({type(e).__name__}: {e})") from None
        got = sorted(json.dumps(  # what ran is already tidy: its options are not tidied twice
            {"kind": r["stat"], "source": r["source"],
             "options": ({"by": r["options"].get("by")} if r["stat"] == "rate" else
                         same_options(loaded[r["source"]], r["options"])),
             "filters": sorted((same_ages(loaded[r["source"]], f) for f in r["spec"]["filters"]),
                               key=lambda f: json.dumps(f, sort_keys=True))},
            sort_keys=True, default=str) for r in analyses)
        if got != want:
            problems.append("analyses " + "; ".join(sorted(r["read_as"] for r in analyses))
                            if analyses else "no analysis ran")
        windows = [a["window"] for a in expect["analyses"] if a.get("window")]
        if got == want and windows and [
                {"first": r["window"]["first"], "last": r["window"]["last"]}
                for r in analyses] != windows:
            problems.append("months " + "; ".join(
                f"{r['window']['first']} to {r['window']['last']}" for r in analyses))
    for kind in ("compare", "share"):
        made = any(r["kind"] == kind for r in reply.results)
        if expect.get(kind) is not None and made != expect[kind]:
            problems.append(f"{kind} {made}")
    if expect.get("kind") is not None and reply.reply_kind != expect["kind"]:
        problems.append(f"kind {reply.reply_kind}")
    return "; ".join(problems)


def check_model(model_id, cases, settings, registry, today, repeat, folder, loaded, copies,
                model=None, out=print):
    """Run every case `repeat` times. Returns (must cases passed, must cases)."""
    settings = with_model(settings, model_id)  # S3A C51: the active service's model
    model = model or Paced(NvidiaModelClient(settings))
    need = 2 if repeat >= 3 else repeat
    passed_must = must = 0
    styles, seconds, codes = Counter(), [], Counter()
    for case in cases:
        good = 0
        for run in range(1, repeat + 1):
            run_folder = folder / model_id.replace("/", "_") / f"{case['id']}-{run}"
            run_folder.mkdir(parents=True, exist_ok=True)
            try:
                reply, took = run_case(case, model, settings, registry, today, run_folder)
                why = judge(case, reply, loaded, copies)
            except RuntimeError as e:
                out(f"{case['id']} run {run}: ERROR  {e}")
                continue
            good += not why
            seconds.append(took)
            if reply.status == "ANSWERED":
                styles[reply.reply_style] += 1
            codes.update(reply.draft_failures)
            out(f"{case['id']} run {run}: {'PASS' if not why else 'FAIL'}"
                f"{'' if case['must'] else ' (not must)'}  status={reply.status}  "
                f"style={reply.reply_style}  seconds={took:.1f}"
                + (f"  failures={','.join(reply.draft_failures)}" if reply.draft_failures else "")
                + (f"  <- {why}" if why else ""))
            if run == 1 or why:
                out("    " + " ".join(reply.text.split())[:300])
        if case["must"]:
            must += 1
            passed_must += good >= need
    out(f"MODEL {model_id}: must cases passed in at least {need} of {repeat} runs: "
        f"{passed_must} of {must}. Answers in his own words: {styles['agent']}, replaced by "
        f"the fixed text: {styles['fallback']}. Median seconds: "
        f"{sorted(seconds)[len(seconds) // 2] if seconds else 0:.1f}."
        + (f" Failure codes seen: {', '.join(f'{c} x{n}' for c, n in codes.most_common())}."
           if codes else ""))
    return passed_must, must


def main(argv=None):
    parser = argparse.ArgumentParser(prog="tools/county_check.py")
    parser.add_argument("--models", required=True, help="model ids, comma separated")
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--only", help="case ids, comma separated")
    parser.add_argument("--talk", action="store_true", help="MOCO_TALK on for the run")
    args = parser.parse_args(argv)
    try:
        settings = load_settings()
        require_for_model(settings)
    except ConfigError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 4
    settings = dataclasses.replace(settings, moco_data="county",
                                   moco_talk="on" if args.talk else "off")
    file = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    cases = [c for c in file["cases"] if not args.only or c["id"] in args.only.split(",")]
    loaded = sources.county_sources()
    copies = {sid: sources.latest(sid, state_dir=settings.moco_state_dir) for sid in loaded}
    needed = {s["source"] for c in cases for t in [*c["thread"], c["expect"]]
              for s in [*(t.get("counts") or []), *(t.get("analyses") or []),
                        *([t["trend"]] if t.get("trend") else [])]}
    missing = sorted(sid for sid in needed if copies.get(sid) is None)
    if missing:
        print(f"Error: no copy in the state folder for: {', '.join(missing)}. Run "
              f"`python -m moco_agent fetch <id>` first.", file=sys.stderr)
        return 4
    today = date.fromisoformat(file["today"]) if file.get("today") else None
    folder = REPO / "runs" / "county-check" / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"
    print(f"County check: {len(cases)} cases, {args.repeat} runs each, talk "
          f"{'on' if args.talk else 'off'}. Copies: "
          + "; ".join(f"{sid} {copies[sid].rows:,} rows of {counting.day_text(copies[sid].day)}"
                      for sid in sorted(needed)) + ".")
    best = 0
    for model_id in [m.strip() for m in args.models.split(",") if m.strip()]:
        passed, must = check_model(model_id, cases, settings, load_registry(), today,
                                   args.repeat, folder, loaded, copies)
        best = max(best, int(passed == must))
    return 0 if best else 1


if __name__ == "__main__":
    sys.exit(main())
