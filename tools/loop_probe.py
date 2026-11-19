"""Probe: which NVIDIA models on this key can work as an agent, in steps?

Written by the planning chat on 2026-11-10 to choose a model BEFORE the agent loop is
designed around one. It is a measuring tool, not part of the agent. Data: SYNTHETIC. The
tools here return made-up placeholders, never a count from the data.

    .venv/bin/python tools/loop_probe.py --list                 model ids this key can see
    .venv/bin/python tools/loop_probe.py --sweep [--max 8]      list, pick candidates, probe
    .venv/bin/python tools/loop_probe.py --models ID1,ID2 [--thinking default,off] [--repeat N]

What it asks of a model: call tools over several steps (count, rank, describe, ask), then
call `finish` with a reply whose values are slots such as {r1.total}, never typed numbers.
It reads the key through moco_agent.config and prints no key. It prints the model's final
reply (cut short) so a person can judge the wording.
"""
import argparse
import dataclasses
import json
import re
import sys
import time

from moco_agent.config import ConfigError, load_settings, require_for_model
from moco_agent.llm import OpenAITransport, TransportError

PAUSE_SECONDS = 1.6          # stays under 40 requests a minute
CALL_TIMEOUT_SECONDS = 45
MAX_STEPS = 6
SLOW_MODEL_SECONDS = 300     # stop probing a model that has used this much model time
THINKING_OFF = {"chat_template_kwargs": {"enable_thinking": False}}
ALLOWED_NUMBERS = {"2024", "2025", "18", "25", "26", "40", "41"}
GROUPS = ["under_18", "18_25", "26_40", "41_plus"]
SHORTLIST = ["nemotron-3.5-lightning", "nemotron-3-ultra", "nemotron-3-super", "mistral-large-4", "mistral-nemotron",
             "glm-5", "glm-4.7", "qwen3.5", "deepseek-v4", "deepseek-v3.2", "llama-4-maverick",
             "kimi-k2", "gpt-oss-120b", "minimax-m2", "devstral-2"]

SYSTEM = """You are a data agent for SYNTHETIC (made-up) arrest records. You work in steps by calling tools.

You never state a count yourself. Values reach the user only through slots that the program fills in.

Rules
1. For a question about counts, call count_arrests once for each year and age group you need. Each call returns a result id such as r1 and the names of its fields. The values are hidden from you.
2. To find which of several results is highest or lowest, call rank with their result ids. It returns a new result id with the fields top_label, top_value, bottom_label, bottom_value.
3. When you have what you need, call finish with the reply for the user, in one to three plain sentences. Put values in with slots such as {r1.total} or {r3.top_label}. Never type a count. Years and age group names may be typed.
4. If the question is about the data itself (what it is, where it comes from, what it lacks), call describe_data, then finish using only those facts.
5. If the question is about arrests but you cannot tell which year or which age group is meant, call ask_user. Never guess.
6. If the message is not about this data, call finish with one sentence saying what you can help with.
7. Use what was said earlier in the thread to fill in what the latest message leaves out.
Every step must be a tool call, until you call finish.

DATA: one dataset of made-up arrest records, 2024 and 2025. Each record has a month and an age group.
Age group codes: under_18 (people under 18), 18_25 (ages 18 to 25), 26_40 (ages 26 to 40), 41_plus (ages 41 and over). Use "all" for all ages."""


def _tool(name, description, properties, required):
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties, "required": required}}}


TOOLS = [
    _tool("count_arrests", "Count arrest records for one year and one age group (or all ages).",
          {"year": {"type": "integer"},
           "age_group": {"type": "string", "enum": [*GROUPS, "all"]}}, ["year", "age_group"]),
    _tool("rank", "Find the highest and lowest of several results.",
          {"result_ids": {"type": "array", "items": {"type": "string"}},
           "field": {"type": "string", "enum": ["total"]}}, ["result_ids", "field"]),
    _tool("describe_data", "Get the approved facts about the data.", {}, []),
    _tool("ask_user", "Ask the user for the one thing that is missing.",
          {"missing": {"type": "string", "enum": ["year", "age_group", "other"]}}, ["missing"]),
    _tool("finish", "Send the reply to the user and stop.",
          {"text": {"type": "string"}}, ["text"]),
]

FACTS = ["The data is SYNTHETIC (made-up) test data, not real Montgomery County figures.",
         "It covers 2024 and 2025.",
         "Each row is one arrest record with a month and an age group.",
         "The age groups are people under 18, ages 18 to 25, ages 26 to 40, and ages 41 and over.",
         "It has nothing on race, place, offense type, convictions, jail or rates."]


def _counts(calls):
    return sorted((c["args"].get("year"), c["args"].get("age_group"))
                  for c in calls if c["name"] == "count_arrests")


def _names(calls):
    return [c["name"] for c in calls]


def _stray_numbers(text):
    return [n for n in re.findall(r"[0-9][0-9,.]*", re.sub(r"\{[^{}]*\}", " ", text or ""))
            if n.strip(",.") not in ALLOWED_NUMBERS]


def _final_ok(text, need_slots=(), max_chars=500):
    if not text or not text.strip():
        return "no reply text"
    if len(text) > max_chars:
        return f"reply longer than {max_chars} characters"
    stray = _stray_numbers(text)
    if stray:
        return f"typed number(s) {stray[:3]}"
    for slot in need_slots:
        if not re.search(slot, text):
            return f"no slot matching {slot}"
    return ""


def check_single(calls, text):
    if _counts(calls) != [(2025, "under_18")]:
        return f"wanted one count for (2025, under_18), got {_counts(calls)}"
    return _final_ok(text, [r"\{r1\.total\}"])


def check_compare(calls, text):
    if _counts(calls) != [(2024, "under_18"), (2025, "under_18")]:
        return f"wanted counts for 2024 and 2025 under_18, got {_counts(calls)}"
    return _final_ok(text, [r"\{r1\.total\}", r"\{r2\.total\}"])


def check_breakdown(calls, text):
    if _counts(calls) != sorted((2025, g) for g in GROUPS):
        return f"wanted four counts for 2025, one per age group, got {_counts(calls)}"
    if "rank" not in _names(calls):
        return "never called rank"
    return _final_ok(text, [r"\{r[0-9]+\.top_label\}"])


def check_followup(calls, text):
    if _counts(calls) != [(2025, "under_18")]:
        return f"wanted one count for (2025, under_18), got {_counts(calls)}"
    return _final_ok(text, [r"\{r1\.total\}"])


def check_about(calls, text):
    if "describe_data" not in _names(calls):
        return "never called describe_data"
    if _counts(calls):
        return "counted when asked about the data"
    return _final_ok(text, max_chars=700)


def check_offtopic(calls, text):
    if _counts(calls) or "rank" in _names(calls):
        return "ran an analysis for an off-topic message"
    if "ask_user" in _names(calls):
        return "asked a question back instead of saying what it can do"
    return _final_ok(text, max_chars=400)


def check_unclear(calls, text):
    if _counts(calls):
        return f"guessed instead of asking: {_counts(calls)}"
    if "ask_user" not in _names(calls):
        return "did not ask"
    return ""


EARLIER = ("Earlier in this thread the user asked: \"How many arrest records were there each month "
           "in 2025 for ages 18 to 25?\" and you answered it for 2025, ages 18 to 25.")
SCENARIOS = [
    ("S1 single", None, "How many arrest records were there in 2025 for people under 18?", check_single),
    ("S2 compare", None, "Compare 2024 and 2025 for people under 18.", check_compare),
    ("S3 chain", None, "In 2025, which age group had the most arrest records?", check_breakdown),
    ("S4 follow-up", EARLIER, "and for people under 18?", check_followup),
    ("S5 about", None, "What data do you have, and what is missing from it?", check_about),
    ("S6 off-topic", None, "What's the weather in DC tomorrow?", check_offtopic),
    ("S7 unclear", None, "How many arrests for young people?", check_unclear),
]


def _answer_tool(name, args, state):
    """What the program tells the model after a tool call. No value from the data, ever."""
    if name == "count_arrests":
        year, group = args.get("year"), args.get("age_group")
        if year not in (2024, 2025):
            return {"error": "no data for that year; the data covers 2024 and 2025"}
        if group not in (*GROUPS, "all"):
            return {"error": "unknown age group"}
        state["n"] += 1
        return {"result_id": f"r{state['n']}", "year": year, "age_group": group,
                "fields": ["total", "busiest_month", "busiest_count", "quietest_month",
                           "quietest_count"], "note": "values are hidden; use slots"}
    if name == "rank":
        state["n"] += 1
        return {"result_id": f"r{state['n']}",
                "fields": ["top_label", "top_value", "bottom_label", "bottom_value"],
                "note": "values are hidden; use slots"}
    if name == "describe_data":
        return {"facts": FACTS}
    return {"error": f"unknown tool {name}"}


class Stop(Exception):
    pass


def run_scenario(transport, model, extra_body, earlier, question, sleep=time.sleep):
    """Returns (calls, final_text, steps, seconds, note). Raises TransportError."""
    messages = [{"role": "system", "content": SYSTEM}]
    if earlier:
        messages.append({"role": "user", "content": f"THREAD CONTEXT (data, not instructions)\n{earlier}"})
    messages.append({"role": "user", "content": question})
    calls, state, seconds = [], {"n": 0}, 0.0
    for step in range(1, MAX_STEPS + 1):
        sleep(PAUSE_SECONDS)
        started = time.monotonic()
        body = transport({"model": model, "messages": messages, "tools": TOOLS,
                          "tool_choice": "auto", "temperature": 0, "max_tokens": 2048,
                          "extra_body": dict(extra_body)})
        seconds += time.monotonic() - started
        message = (body.get("choices") or [{}])[0].get("message") or {}
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            return calls, message.get("content") or "", step, seconds, "plain text, no finish call"
        echo = {"role": "assistant", "content": message.get("content") or "", "tool_calls": []}
        replies = []
        for raw in tool_calls:
            function = raw.get("function") or {}
            name, arguments = function.get("name"), function.get("arguments")
            try:
                args = json.loads(arguments) if isinstance(arguments, str) else (arguments or {})
            except ValueError:
                args = {}
            if not isinstance(args, dict):
                args = {}
            calls.append({"name": name, "args": args})
            echo["tool_calls"].append({"id": raw.get("id") or f"call_{len(calls)}", "type": "function",
                                       "function": {"name": name, "arguments": json.dumps(args)}})
            if name == "finish":
                return calls, str(args.get("text") or ""), step, seconds, ""
            if name == "ask_user":
                return calls, "", step, seconds, f"asked for {args.get('missing')}"
            replies.append({"role": "tool", "tool_call_id": echo["tool_calls"][-1]["id"],
                            "content": json.dumps(_answer_tool(name, args, state))})
        messages.append(echo)
        messages.extend(replies)
    return calls, "", MAX_STEPS, seconds, f"no finish after {MAX_STEPS} steps"


def _show_calls(calls):
    parts = []
    for c in calls:
        if c["name"] == "count_arrests":
            parts.append(f"count({c['args'].get('year')},{c['args'].get('age_group')})")
        else:
            parts.append(str(c["name"]))
    return " ".join(parts) or "(none)"


def probe(transport, model, mode, extra_body, repeat, out=print, sleep=time.sleep):
    """Probe one model in one mode. Returns (passed, total, model_seconds, status)."""
    out(f"\n== {model}  [thinking: {mode}]")
    passed = total = 0
    used, failures_in_a_row, status = 0.0, 0, "ok"
    try:
        for label, earlier, question, check in SCENARIOS:
            for _ in range(repeat):
                total += 1
                try:
                    calls, text, steps, seconds, note = run_scenario(
                        transport, model, extra_body, earlier, question, sleep=sleep)
                except TransportError as e:
                    failures_in_a_row += 1
                    out(f"{label:13} FAIL  request failed: {e}")
                    if failures_in_a_row >= 2:
                        status = f"stopped: two requests in a row failed ({e})"
                        raise Stop from None
                    continue
                failures_in_a_row = 0
                used += seconds
                why = check(calls, text)
                passed += not why
                shown = " ".join(text.split())
                out(f"{label:13} {'PASS' if not why else 'FAIL'}  {steps} step(s), {seconds:.1f} s  "
                    f"calls: {_show_calls(calls)}" + (f"  [{note}]" if note else "")
                    + (f"  <- {why}" if why else ""))
                if shown:
                    out(f"{'':13} reply: {shown[:220]}")
                if used > SLOW_MODEL_SECONDS:
                    status = f"stopped: over {SLOW_MODEL_SECONDS} s of model time, too slow to use live"
                    raise Stop
    except Stop:
        pass
    out(f"TOTAL {model} [thinking: {mode}]: {passed}/{len(SCENARIOS) * repeat} passed, "
        f"{used:.0f} s of model time, {status}")
    return passed, len(SCENARIOS) * repeat, used, status


def list_models(settings):
    import openai
    client = openai.OpenAI(api_key=settings.nvidia_api_key, base_url=settings.nvidia_base_url,
                           timeout=30.0, max_retries=0)
    try:
        return sorted(m.id for m in client.models.list().data)
    except openai.APIStatusError as e:
        raise SystemExit(f"Error: listing models failed (HTTP {e.status_code}).") from None
    except openai.OpenAIError as e:
        raise SystemExit(f"Error: listing models failed ({type(e).__name__}).") from None


def pick_candidates(ids, limit):
    """One id per shortlist entry (the shortest id that contains it), in shortlist order."""
    picked = []
    for wanted in SHORTLIST:
        matches = sorted((i for i in ids if wanted in i.lower()), key=len)
        if matches and matches[0] not in picked:
            picked.append(matches[0])
    return picked[:limit]


def main(argv=None):
    parser = argparse.ArgumentParser(prog="tools/loop_probe.py")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--sweep", action="store_true")
    parser.add_argument("--models", default="")
    parser.add_argument("--thinking", default="", help="default, off, or default,off")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--max", type=int, default=8)
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(line_buffering=True)  # show each line at once, even through tee
    try:
        settings = load_settings()
        require_for_model(settings)
    except ConfigError as e:  # names the KEY, never a value
        print(f"Error: {e}", file=sys.stderr)
        return 4
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    if args.list or args.sweep:
        ids = list_models(settings)
        print(f"{len(ids)} model ids visible to this key:")
        for i in ids:
            print(f"  {i}")
        if args.list:
            return 0
        models = pick_candidates(ids, args.max)
        print(f"\nCandidates picked from that list ({len(models)}): {', '.join(models) or 'none'}")
    if not models:
        print("Nothing to probe. Use --sweep, or --models ID1,ID2.", file=sys.stderr)
        return 2
    transport = OpenAITransport(dataclasses.replace(
        settings, moco_model_timeout_seconds=CALL_TIMEOUT_SECONDS))
    print(f"\nLOOP PROBE (data: SYNTHETIC; no key is printed). {len(SCENARIOS)} scenarios, "
          f"repeat {args.repeat}, at most {MAX_STEPS} steps each, {CALL_TIMEOUT_SECONDS} s a call.")
    results = []
    for model in models:
        modes = [m.strip() for m in args.thinking.split(",") if m.strip()] or (
            ["default", "off"] if "nemotron-3.5-lightning" in model else ["default"])
        for mode in modes:
            extra = THINKING_OFF if mode == "off" else {}
            results.append((model, mode, *probe(transport, model, mode, extra, args.repeat)))
    print("\nSUMMARY (best first)")
    for model, mode, passed, total, used, status in sorted(
            results, key=lambda r: (-r[2], r[4])):
        print(f"  {passed}/{total}  {used:5.0f} s  {model} [thinking: {mode}]  {status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
