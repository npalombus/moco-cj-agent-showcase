"""The live loop check (design P1A, A15). Replaces tools/model_check.py.

    .venv/bin/python tools/loop_check.py --models ID1,ID2 [--cases FILE] [--repeat N] [--background] [--talk]

For each case of config/loop_check_cases.json and each run: a fresh memory and runs folder
of its own (under runs/loop-check/, which is not in git, so each turn.json can be read
afterwards), seeded with the case's earlier turns (made through the real
handle_question with a scripted stand-in model, so their saved records are real); then the
real handle_question with the real model. One line per run: PASS or FAIL against the case's
`expect` (the status, the exact set of counts that ran after filling, whether a compare
ran, the reply kind), the steps and seconds, style=, the failure codes, and the reply as
sent. A case passes only if all its runs pass. Then totals per model: must cases passed,
finding replies in agent style against fallback, the failure codes seen, and the seconds
per turn.

Cases marked "background" run only with --background, which also turns MOCO_BACKGROUND on;
the other cases run either way. --talk turns MOCO_TALK on for the run (docs/T-DESIGN.md T9),
and a case's `expect` may then also hold `no_digits` (a talk reply holds no digit) and
`styles` (the reply styles that pass); each run line also gives the codes of the first
finish text (first=), and the totals count talk replies by style. Exit 0 when a model passes every must case run, 1
when none does, 4 when a setting is missing. It reads the key through moco_agent.config at
run time and prints no key. It paces itself under 40 requests a minute.
"""
import argparse
import dataclasses
import json
import re
import statistics
import sys
import time
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from moco_agent.agent import handle_question
from moco_agent.config import ConfigError, load_settings, require_for_model, with_model
from moco_agent.llm import ModelStep, NvidiaModelClient, ToolCall
from moco_agent.memory import Store
from moco_agent.registry import load_registry

REPO = Path(__file__).resolve().parents[1]
DEFAULT_CASES = REPO / "config" / "loop_check_cases.json"
PAUSE_SECONDS = 3.0  # at most 20 requests a minute (1.6 met HTTP 429 in T-B run 2)
THREAD = "loop-check:local:thread"
USER = "loop-check"


class Paced:
    """The real model client, with at least PAUSE_SECONDS between two requests."""

    def __init__(self, client):
        self.client, self.model_id, self._last = client, client.model_id, None

    def step(self, messages, tools):
        if self._last is not None:
            time.sleep(max(0.0, PAUSE_SECONDS - (time.monotonic() - self._last)))
        try:
            return self.client.step(messages, tools)
        finally:
            self._last = time.monotonic()


class Scripted:
    """A stand-in model that plays fixed steps, used only to seed earlier turns."""

    model_id = "loop-check-seed"

    def __init__(self, steps):
        self.steps, self.index = steps, 0

    def step(self, messages, tools):
        calls = self.steps[min(self.index, len(self.steps) - 1)]
        self.index += 1
        return ModelStep(tool_calls=[ToolCall(id=f"seed_{self.index}_{i}", name=name,
                                              arguments_json=json.dumps(arguments))
                                     for i, (name, arguments) in enumerate(calls)], text=None)


def seed_steps(turn):
    """The steps that remake one earlier turn of a case."""
    if turn["status"] == "NEEDS_INPUT":
        return [[("count_arrests", {"year": None,
                                    "age_group": turn["pending"].get("age_group")})]]
    counts = [("count_arrests", {"year": y, "age_group": g or "all"}) for y, g in turn["counts"]]
    steps = [counts]
    # Texts in revision 2's fact slots (R1) that pass its check, as a real earlier reply would.
    if turn.get("compared") or turn.get("compare"):
        ids = [f"r{i + 1}" for i in range(len(counts))]
        steps.append([("compare", {"result_ids": ids, "field": "total"})])
        text = f"Here is the comparison: {{r{len(counts) + 1}.compare}}."
    elif len(counts) == 1:
        text = "I counted {r1.count}. {r1.months}."
    else:
        text = "I counted " + " and ".join(f"{{r{i + 1}.count}}" for i in range(len(counts))) + "."
    steps.append([("finish", {"kind": "finding", "text": text})])
    return steps


def seed_question(turn, registry):
    """An earlier turn's question; config/loop_check_cases_talk.json gives none, so one is
    written from the turn's counts."""
    if "question" in turn:
        return turn["question"]
    years = " and ".join(dict.fromkeys(str(y) for y, _ in turn["counts"]))
    groups = " and ".join(dict.fromkeys("all ages" if g is None else registry.age_groups[g]
                                        for _, g in turn["counts"]))
    if turn.get("compared") or turn.get("compare"):
        return f"Compare the arrests in {years} for {groups}."
    return f"How many arrests were there in {years} for {groups}?"


def run_case(case, model, settings, registry, today, folder):
    """Seed the case's earlier turns, then one real turn. Returns (reply, seconds)."""
    store = Store(folder / "agent.db")
    runs = folder / "runs"
    now = datetime.now(timezone.utc)
    try:
        for i, turn in enumerate(case["thread"]):
            seeded = handle_question(
                seed_question(turn, registry), thread_key=THREAD, user_id=USER,
                settings=settings,
                registry=registry, model_client=Scripted(seed_steps(turn)), store=store,
                runs_dir=runs, today=today,
                now=now - timedelta(minutes=10 * (len(case["thread"]) - i)))
            if seeded.status != turn["status"]:
                raise RuntimeError(f"seeding {case['id']} gave {seeded.status}")
        started = time.monotonic()
        reply = handle_question(case["question"], thread_key=THREAD, user_id=USER,
                                settings=settings, registry=registry, model_client=model,
                                store=store, runs_dir=runs, today=today, now=now)
        return reply, time.monotonic() - started
    finally:
        store.close()


def judge(case, reply):
    """Why the run fails against the case's `expect`, or "" when it passes."""
    expect = case["expect"]
    counts = {(r["year"], r["age_group"]) for r in reply.results if r["kind"] == "count"}
    compared = any(r["kind"] == "compare" for r in reply.results)
    problems = []
    if reply.status not in expect["status"]:
        problems.append(f"status {reply.status}")
    if expect["counts"] is not None and counts != {(y, g) for y, g in expect["counts"]}:
        shown = sorted(counts, key=lambda c: (str(c[0]), str(c[1])))
        problems.append(f"counts {shown}")
    if expect["compare"] is not None and compared != expect["compare"]:
        problems.append(f"compare {compared}")
    if expect["kind"] is not None and reply.reply_kind != expect["kind"]:
        problems.append(f"kind {reply.reply_kind}")
    if expect.get("no_digits") and reply.status == "TALKED" \
            and re.search(r"\d", reply.text):  # T9: a fixed refusal may name the years
        problems.append("a digit in the reply")
    if expect.get("styles") is not None and reply.reply_style not in expect["styles"]:
        problems.append(f"style {reply.reply_style}")
    return "; ".join(problems)


def first_failures(reply, run_folder):
    """T3: the codes of the turn's first finish text, from its turn record ("-" if none)."""
    try:
        record = json.loads((run_folder / "runs" / reply.turn_id / "turn.json").read_text(
            encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return "?"
    return ",".join(record.get("first_failures") or []) or "-"


def check_model(model_id, cases, settings, registry, today, repeat, folder, out=print):
    """Run every case `repeat` times on one model. Returns the summary dict."""
    settings = with_model(settings, model_id)  # S3A C51: the active service's model
    folder = folder / model_id.replace("/", "_")
    model = Paced(NvidiaModelClient(settings))
    out(f"\n== {model_id}")
    must_passed = must_total = 0
    styles, talks, failures, seconds = Counter(), Counter(), Counter(), []
    for case in cases:
        passes = 0
        for n in range(1, repeat + 1):
            run_folder = folder / f"{case['id']}-{n}"
            run_folder.mkdir(parents=True, exist_ok=True)
            try:
                reply, took = run_case(case, model, settings, registry, today, run_folder)
                why = judge(case, reply)
            except Exception as e:  # one broken run is a FAIL, never the end of the check
                out(f"{case['id']} run {n}: FAIL  the run itself failed ({type(e).__name__})")
                failures.update(["RUN_FAILED"])
                continue
            passes += not why
            seconds.append(took)
            failures.update(reply.draft_failures)
            if reply.reply_kind == "finding":
                styles[reply.reply_style] += 1
            if reply.reply_kind == "talk":
                talks[reply.reply_style] += 1
            shown = " / ".join(reply.text.splitlines())
            first = (f"  first={first_failures(reply, run_folder)}"
                     if settings.moco_talk == "on" else "")
            out(f"{case['id']} run {n}: {'PASS' if not why else 'FAIL'}"
                f"{'' if case['must'] else ' (not must)'}  status={reply.status}"
                f"{f' ({reply.reason_code})' if reply.reason_code else ''}  "
                f"steps={reply.steps}  seconds={took:.1f}  kind={reply.reply_kind}  "
                f"style={reply.reply_style}  failures={','.join(reply.draft_failures) or '-'}"
                + first + (f"  <- {why}" if why else ""))
            out(f"    question: {case['question']}")
            out(f"    reply: {shown}")
        if case["must"]:
            must_total += 1
            must_passed += passes == repeat
        out(f"{case['id']}: {'PASS' if passes == repeat else 'FAIL'} ({passes} of {repeat} runs)")
    summary = {"model": model_id, "must_passed": must_passed, "must_total": must_total,
               "agent": styles["agent"], "fallback": styles["fallback"],
               "fixed": styles["fixed"], "talk_agent": talks["agent"],
               "talk_fallback": talks["fallback"], "failures": dict(failures),
               "seconds": seconds}
    out(f"\nTOTAL {model_id}: must cases passed {must_passed} of {must_total}; finding replies "
        f"agent {styles['agent']}, fallback {styles['fallback']}, fixed {styles['fixed']}"
        + (f"; talk replies agent {talks['agent']}, fallback {talks['fallback']}"
           if settings.moco_talk == "on" else ""))
    out("Failure codes seen: " + (", ".join(f"{code} x{n}" for code, n in
                                          failures.most_common()) or "none"))
    if seconds:
        out(f"Seconds per turn: lowest {min(seconds):.1f}, median "
            f"{statistics.median(seconds):.1f}, highest {max(seconds):.1f}")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(prog="tools/loop_check.py")
    parser.add_argument("--models", required=True, help="model ids, comma separated")
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--background", action="store_true",
                        help="run the background cases, with MOCO_BACKGROUND on")
    parser.add_argument("--talk", action="store_true", help="MOCO_TALK on for the run")
    args = parser.parse_args(argv)
    if args.repeat < 1:
        parser.error("--repeat must be 1 or more")
    sys.stdout.reconfigure(line_buffering=True)  # each line at once, even into a file
    try:
        settings = load_settings()
        require_for_model(settings)
    except ConfigError as e:  # names the KEY, never a value
        print(f"Error: {e}", file=sys.stderr)
        return 4
    data = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    # T9: a background case runs only with --background; the others run either way.
    cases = [c for c in data["cases"] if args.background or not c.get("background")]
    if args.background:
        settings = dataclasses.replace(settings, moco_background="on")
    if args.talk:
        settings = dataclasses.replace(settings, moco_talk="on")
    registry = load_registry()
    today = date.fromisoformat(data["today"])
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    print(f"LOOP CHECK (data: SYNTHETIC; no key is printed). {len(cases)} cases, repeat "
          f"{args.repeat}, background {'on' if args.background else 'off'}, talk "
          f"{settings.moco_talk}, reply style "
          f"{settings.moco_reply_style}, today {today}, at most {settings.moco_max_steps} "
          f"steps and {settings.moco_turn_seconds} seconds a turn.")
    folder = REPO / "runs" / "loop-check" / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"
    print(f"Each run's memory and records: {folder.relative_to(REPO)}/<model>/<case>-<run>")
    summaries = [check_model(m, cases, settings, registry, today, args.repeat, folder)
                 for m in models]
    print("\nSUMMARY")
    for s in summaries:
        print(f"  {s['model']}: must {s['must_passed']} of {s['must_total']}; finding replies "
              f"agent {s['agent']}, fallback {s['fallback']}"
              + (f"; talk replies agent {s['talk_agent']}, fallback {s['talk_fallback']}"
                 if args.talk else ""))
    return 0 if any(s["must_passed"] == s["must_total"] for s in summaries) else 1


if __name__ == "__main__":
    sys.exit(main())
