"""The live check with the real model (D-077): progressive threads. Each thread of
config/talk_threads_s3.json is one conversation: its messages go to the agent one after the
other, in county mode with talk on, and every reply is printed whole for a person to read.
There is no judge: a person reads the replies and looks for contradictions.

    python tools/thread_check.py                       every thread once
    python tools/thread_check.py --threads P05,P14     only these
    python tools/thread_check.py --repeat 3            each thread three times
    python tools/thread_check.py --down                first model service off: the backup (C56)

It calls the model service the settings name (it costs what the service charges), reads the
saved copies of the county data under MOCO_STATE_DIR, and writes its records to a temporary
folder. Prints no key. For a turn that ended on a fixed refusal or a fallback it prints the
steps, so the reason can be read. Written by the planning chat, 17 and 18 Nov 2026."""
import argparse
import dataclasses
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from loop_check import Paced  # noqa: E402

from moco_agent import sources  # noqa: E402
from moco_agent.agent import handle_question  # noqa: E402
from moco_agent.config import (backup_settings, load_settings, require_for_model,  # noqa: E402
                               with_model)
from moco_agent.llm import ModelUnavailable, NvidiaModelClient  # noqa: E402
from moco_agent.memory import Store  # noqa: E402
from moco_agent.registry import load_registry  # noqa: E402


def say(text=""):
    for line in str(text).splitlines() or [""]:
        print(line, flush=True)
        time.sleep(0.005)


class Down:
    """--down: a first model service that is always down, to see the backup (C56)."""
    def __init__(self, model_id):
        self.model_id = model_id

    def step(self, messages, tools):
        raise ModelUnavailable("the trial's first service is switched off")


def main():
    parser = argparse.ArgumentParser(prog="tools/thread_check.py")
    parser.add_argument("--threads", default=os.environ.get("LIVE_THREADS", ""),
                        help="thread ids, comma separated (P01,P05); default: all")
    parser.add_argument("--repeat", type=int, default=int(os.environ.get("LIVE_REPEAT", "1")))
    parser.add_argument("--model", default=os.environ.get("LIVE_MODEL", "claude-haiku-5-5"))
    parser.add_argument("--down", action="store_true",
                        default=os.environ.get("LIVE_DOWN", "").strip() == "1",
                        help="the first model service always fails, to see the backup")
    parser.add_argument("--file", default=str(REPO / "config" / "talk_threads_s3.json"))
    parser.add_argument("--steps", action="store_true",
                        default=os.environ.get("LIVE_STEPS", "").strip() == "1",
                        help="print the steps of every turn, not only of refusals and fallbacks")
    args = parser.parse_args()
    model_id = args.model
    settings = load_settings()
    require_for_model(settings)
    settings = with_model(dataclasses.replace(settings, moco_data="county", moco_talk="on"),
                          model_id)
    file = json.loads(Path(args.file).read_text(encoding="utf-8"))
    only = [t.strip() for t in args.threads.split(",") if t.strip()]
    threads = [t for t in file["threads"] if not only or t["id"].split("-")[0] in only]
    notices = sorted({n for s in sources.county_sources().values()
                      for n in s.get("notices", [])}, key=len, reverse=True)
    registry, model = load_registry(), Paced(NvidiaModelClient(settings))
    second = backup_settings(settings)
    backup = None if second is None else (second, Paced(NvidiaModelClient(second)))
    if args.down:
        model = Down(model_id)
    say(f"BACKUP {'none' if second is None else second.moco_model_provider}, first service "
        f"{'DOWN (trial)' if isinstance(model, Down) else 'on'}")
    repeat = args.repeat
    say(f"THREADS {len(threads)} x{repeat}, model {model_id}")
    for run in range(1, repeat + 1):
        for thread in threads:
            folder = Path(tempfile.mkdtemp(prefix="threads-"))
            store = Store(folder / "agent.db")
            base = datetime.now(timezone.utc)
            key = f"threads:{thread['id']}:{run}"
            say(f"## {thread['id']} run {run}")
            try:
                for i, question in enumerate(thread["turns"], 1):
                    started = time.monotonic()
                    reply = handle_question(question, thread_key=key, user_id="threads",
                                            settings=settings, registry=registry,
                                            model_client=model, store=store,
                                            runs_dir=folder / "runs", backup=backup,
                                            now=base + timedelta(seconds=30 * i))
                    text = reply.text or ""
                    for n in notices:
                        text = text.replace(n, "[COUNTY NOTICE]")
                    text = " // ".join(line for line in text.splitlines() if line.strip())
                    codes = ",".join(reply.draft_failures or [])
                    say(f"{thread['id']}.{run} Q{i:02d}: {question}")
                    say(f"{thread['id']}.{run} A{i:02d} [{reply.status} "
                        f"{reply.reason_code or '-'} {reply.reply_kind or '-'} "
                        f"{reply.reply_style} {codes or '-'} {reply.model_id or '-'} "
                        f"{time.monotonic() - started:.1f}s]: {text[:1500]}")
                    if (reply.reply_style == "fixed" and reply.status in ("UNSUPPORTED", "ERROR")) \
                            or reply.reply_style == "fallback" or args.steps:
                        try:  # why a turn ended on a fixed refusal or a fallback: its steps
                            rec = json.loads((folder / "runs" / reply.turn_id / "turn.json")
                                             .read_text(encoding="utf-8"))
                            for step in rec.get("steps") or []:
                                for call in step.get("tool_calls") or []:
                                    say(f"   STEP {step['step']} {call['name']} "
                                        f"{str(call.get('arguments'))[:600]} -> "
                                        f"{json.dumps(call.get('answer'))[:300]}")
                                if step.get("text"):
                                    say(f"   STEP {step['step']} text {step['text'][:300]!r}")
                        except Exception as e:
                            say(f"   STEPS not read ({type(e).__name__})")
            finally:
                store.close()
    say("=== THREADS DONE ===")


if __name__ == "__main__":
    main()
