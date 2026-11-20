"""One agent turn (design P1A, A3 to A5, A7, A9 and A10; revision 2, R1 to R6).

The model works in steps: each step it calls tools, and Python answers each call. Counting
goes through stage 1's execute_call, the only door to a number; comparing goes through
analysis.compare_counts. The model is told result ids and fact slots, never a value. It
writes its reply around fact slots such as {r1.count}, each of which Python fills with one
whole phrase; Python checks the text (replies.py) and fills it, or writes the reply itself
when the text fails. Python, not the model, fills a missing year or age group from the
thread, and writes every question it asks.
"""
import json
import logging
import re
import time
import traceback
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import census, countchart, counting, guard, rates, replies, sources, stats, statwords
from .analysis import age_wording, compare_counts
from .context import (COUNTY_PROMPT, COUNTY_TALK_PROMPT, DECLINE_CODES, FINISH_KINDS,
                      MISSING_VALUES, TALK_KINDS, TALK_PROMPT, county_system_message,
                      county_tools, latest_message, read_prompt, system_message,
                      thread_message, tools)
from .config import model_router, runs_dir_of
from .core import DEFAULT_RUNS, SKILL, STATUS_FOR, _new_run, execute_call
from .llm import ModelUnavailable
from .router import read_age_group

log = logging.getLogger(__name__)

MAX_COUNTS = 8
OPTION_KEYS = ("versus", "date", "outcome", "factors", "controls", "part", "by")  # S13.4
DIST_HINT = ('distribution: to compare the ages of groups send options {"by": "<field>"}, '
             'for example {"by": "gender"}, and no filter on that field')
ANALYSIS_WORDS = re.compile(  # S13.9
    r"\b(ris(e|es|ing)|going (up|down)|increas\w*|decreas\w*|trends?|over the years|over "
    r"time|chang(e|ed|es|ing)|shares?|proportion|percentage|what times?|which (days|hours)"
    r"|busiest|times of the (day|week)|how old|ages|what goes with|odds|more likely)\b",
    re.IGNORECASE)
ANALYZE_HINT = ("This question is about change over time, a share, the times of the week, "
                "ages or what goes with what: use analyze, with the period left out (it uses "
                "every month). Pick its kind as the instructions say.")
SHARE_WORDS = re.compile(r"\b(shares?|proportions?|percentages?|percent)\b", re.IGNORECASE)
SHARES_HINT = ('This question asks about a share: use kind shares, with filters for the whole '
               '(none for all records) and options {"part": [the filters of the group]}, for '
               'example options {"part": [{"field": "age", "to": 17}]}.')
NO_PERIOD_QUESTION = ("Do not ask for the period. Call the tool again with the period left "
                      "out: analyze uses every month; count asks the person itself.")
ANALYSIS_IDS = ("compare and share take counts only; an analysis's own slots already say what "
                "it found: call finish with them")
VAGUE_AGES = re.compile(  # C32
    r"\b(young(?:er)?\s+(?:people|persons|adults|men|women|folks?|ones)|youths?|the young"
    r"|old(?:er)?\s+(?:people|persons|adults|men|women|folks?)|(?:the\s+)?elderly"
    r"|senior citizens|seniors?|teens|teenagers?)\b", re.IGNORECASE)
VERSUS_HINT = ('trend_compare: one group in filters and the other in options.versus, one '
               'filter each, for example filters [{"field": "district", "is": "district 3"}] '
               'and options {"versus": [{"field": "district", "is": "district 4"}]}')
MAX_CALLS = 12
PROGRAM_NOTE = "PROGRAM NOTE (not from the person). Your reply was not sent. "  # T13
# ponytail: the turns read from one thread; base and details look no further back.
HISTORY = 500
CHECK_TURNS = 5000     # C65 point 5: the turns of a thread C21's check reads
ALL = "all"            # all ages, as the model and memory say it
NOT_STATED = object()  # a value the latest message does not give
_NOT_STATED_WORDS = {"year": {"", "null", "none"},
                     "age_group": {"", "null", "none", "unspecified"}}
_ALL_AGES_WORDS = {"all", "all_ages", "all ages", "everyone", "overall", "total"}
_DETAILS_WORDS = {"details", "detail", "more", "more details"}


@dataclass
class AgentReply:
    status: str
    reason_code: str | None
    text: str
    chart_path: str | None = None
    chart_title: str | None = None
    run_ids: list = field(default_factory=list)
    turn_id: str | None = None
    model_called: bool = False
    model_id: str | None = None
    guard_code: str | None = None
    reply_kind: str | None = None
    reply_style: str = "fixed"
    draft_failures: list = field(default_factory=list)
    carried: dict = field(default_factory=lambda: {"year": False, "age_group": False})
    steps: int = 0
    results: list = field(default_factory=list)
    attachments: list = field(default_factory=list)  # S3S: files sent with the message

    def to_dict(self):
        d = asdict(self)
        d["chart_path"] = None if self.chart_path is None else str(self.chart_path)
        if not self.attachments:  # S3S: a reply with no file is exactly as before Part S
            del d["attachments"]
        return d


def year_filter_period(filters):
    """C34: one filter on `year` (`is` a year, `in` years, or `from` and `to` years), sent with
    no period, is read as the period and taken out of the filters. Anything else: (None, the
    filters unchanged)."""
    found = [f for f in filters if isinstance(f, dict) and f.get("field") == "year"]
    if len(found) != 1:
        return None, filters
    flt = found[0]

    def whole(value):  # C53 point 2: 2024, 2024.0 and "2024" are years; 2024.5 is not
        if isinstance(value, bool) or (isinstance(value, float) and not value.is_integer()):
            raise ValueError(value)
        return int(value)
    try:
        if "is" in flt:
            years = [whole(flt["is"])]
        elif isinstance(flt.get("in"), list) and flt["in"]:
            years = sorted({whole(y) for y in flt["in"]})
        elif "from" in flt and "to" in flt and whole(flt["to"]) - whole(flt["from"]) <= 50:
            years = list(range(whole(flt["from"]), whole(flt["to"]) + 1))
        else:
            return None, filters
    except (TypeError, ValueError, OverflowError):
        return None, filters
    if not years or not all(1900 <= y <= 2100 for y in years):
        return None, filters
    period = {"year": years[0]} if len(years) == 1 else {"years": years}
    return period, [f for f in filters if f is not flt]


@dataclass
class _End:
    """How a turn ends; turned into an AgentReply, remembered and recorded by _Turn.reply."""
    status: str
    reason_code: str | None
    text: str
    kind: str | None = None
    style: str = "fixed"
    failures: list = field(default_factory=list)
    reply_text: str | None = None   # the model's text, stored only when it passed
    details: dict | None = None     # what failed a check (R6): turn.json only
    pending: dict | None = None     # what a NEEDS_INPUT turn saved
    missing: str | None = None
    found: list = field(default_factory=list)  # T3: what failed, from the model's text
    draft: str | None = None        # T14: a failed talk text, tidied, in case it is only too long
    cut: bool = False               # T14: the reply is the leading sentences of the draft
    attachments: list = field(default_factory=list)  # S3S S7: the script sent with details
    notices: str | None = None      # C57 point 5: "full" or "short" when the reply carries them


def tidy(arguments, key):
    """A5: the year or age group as stated, NOT_STATED, or ALL (age only). Anything else is
    left unchanged for stage 1's strict check."""
    value = arguments.get(key)
    if value is None:
        return NOT_STATED
    if isinstance(value, str):
        if value.lower() in _NOT_STATED_WORDS[key]:
            return NOT_STATED
        if key == "age_group" and value.lower() in _ALL_AGES_WORDS:
            return ALL
        if key == "year" and re.fullmatch(r"[0-9]{4}", value):
            return int(value)
    if key == "year" and isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def is_details_word(text):
    """A4 step 2: exactly details, detail, more or more details; any case; one final ?, .
    or ! ignored."""
    cleaned = " ".join(text.lower().split())
    return re.sub(r"[?.!]$", "", cleaned) in _DETAILS_WORDS


def handle_question(question, *, thread_key, user_id, settings, registry, model_client,
                    store, data_path=None, runs_dir=None, today=None, now=None, clock=None,
                    memory_minutes=None, backup=None):
    """One turn. Never raises for bad input, a bad model answer or bad data. S3A C56:
    `backup` is (settings, model client) of the backup service; a turn whose model service
    is down is run again on it, once."""
    def try_with(use, client, backup_of=None):
        return _Turn(question, thread_key=thread_key, user_id=user_id, settings=use,
                     registry=registry, model_client=client, store=store,
                     data_path=data_path, runs_dir=runs_dir, today=today, now=now,
                     clock=clock, memory_minutes=memory_minutes, backup_of=backup_of)
    turn = try_with(settings, model_client)
    try:
        end = turn.run()
        if backup is not None and (end.status, end.reason_code) == ("ERROR",
                                                                    "MODEL_UNAVAILABLE"):
            first = turn
            first.reply(end, remember=False)  # C56 point 6: on record, not in the thread
            turn = try_with(backup[0], backup[1], backup_of=first.turn_id)
            log.warning("model %s was unavailable in turn %s: second try %s on the backup "
                        "model %s", first.model_id, first.turn_id, turn.turn_id,
                        getattr(backup[1], "model_id", None))
            end = turn.run()
        return turn.reply(end)
    except Exception as e:  # a last guard: the type and where, never a message or text
        log.error("agent turn %s failed: %s\n%s", turn.turn_id, type(e).__name__,
                  "".join(traceback.format_tb(e.__traceback__)))
        return turn.reply(turn.end("ERROR", "MODEL_BAD_OUTPUT"), save=False)


class _Turn:
    def __init__(self, question, *, thread_key, user_id, settings, registry, model_client,
                 store, data_path, runs_dir, today, now, clock, memory_minutes,
                 backup_of=None):
        self.backup_of = backup_of  # C56: the first try's turn id, in a second try
        self.question = question if isinstance(question, str) else ""
        self.thread_key, self.user_id = thread_key, user_id
        self.s, self.registry, self.model, self.store = settings, registry, model_client, store
        self.data_path = data_path
        self.runs = Path(runs_dir) if runs_dir is not None \
            else runs_dir_of(settings, DEFAULT_RUNS)  # Part D D2
        self.now = now if now is not None else datetime.now(timezone.utc)
        if self.now.tzinfo is None:
            self.now = self.now.replace(tzinfo=timezone.utc)
        self.today = today if today is not None else date.today()
        self.clock = clock if clock is not None else time.monotonic
        self.memory_minutes = memory_minutes
        self.turn_id = f"T{self.now.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
        self.model_id = None
        self.router = model_router(settings)  # S3A C51
        self.prompt_version = None
        self.guard_code = None
        self.restricted = None   # the guard's restricted code, when it switched counting off
        self.steps = 0
        self.calls = 0
        self.counts_run = 0
        self.results = []        # with values: AgentReply.results and turn.json only
        self.count_errors = []
        self.hinted_analyze = False  # S13.9: the analyze hint, once a turn
        self.hinted_period = False
        self.hinted_shares = False   # S13.14   # C25 point 0: the no-period-question hint, once a turn
        self.hinted_word = False     # C48: NOT_RECORDED, once a turn
        self.single_years = []  # C28: years of age under 18 a count of this turn was refused for
        self.vague_end = None   # C36 point 4: C32's question, if the model makes nothing
        self.described = False
        self.kept_year = self.kept_age = None
        self.carried = {"year": False, "age_group": False}
        self.step_log = []
        self.finish_text = None
        self.history = []        # this thread's earlier turns (in the DM window), oldest first
        # S3A C0: county mode is added beside synthetic mode; synthetic is untouched.
        self.county = getattr(settings, "moco_data", "synthetic") == "county"
        self._sources, self.copies = None, {}
        self.kept = []           # county: what a count took from memory, as the note says it
        self.analyses_run = 0    # S3S S1: R runs this turn
        self.error_text = None   # S3S: the fixed line of the last refused analysis
        self.facts = None
        # Part T (MOCO_TALK on): a fourth kind of finish, sentence checks, one second try.
        self.talk = getattr(settings, "moco_talk", "off") == "on"
        self.started = None
        self.first_failures = None  # T3: the codes of the first finish text, once checked
        self.third_try = False      # C61 point 8
        self.earlier_figures = False  # C62 point 2
        self.held_back = False      # C64 point 3a: C21's check refused a count of this turn
        self._given = None          # C65 points 4 and 5: read once, by given()
        self.too_many = False       # C64 point 3b
        self.mixed = False          # C64 point 3c
        self.left_district = []     # S3A C73: district filters left out of a rate
        self.held = None            # T3: how the turn ends if the second try never comes
        self.own_first = None       # C43 point 1: the codes of the first own words that failed
        self.own_text = None        # C45: the latest own words, as tidied
        if self.county:
            self.carried = {"source": False, "period": False, "filters": False}

    @property
    def sources(self):
        """County mode: the county sources (read once a turn) and their current copies."""
        if self._sources is None:
            self._sources = sources.county_sources()
            self.copies = {sid: sources.latest(sid, state_dir=self.s.moco_state_dir)
                           for sid in self._sources}
        return self._sources

    # ---- the turn, in A4's steps ------------------------------------------------------

    def run(self):
        text, s = self.question, self.s
        if not text.strip():
            return self.end("UNSUPPORTED", "UNRECOGNIZED_QUESTION")
        if len(text) > s.moco_max_question_chars:
            return self.end("UNSUPPORTED", "INPUT_TOO_LONG")
        since = (None if self.memory_minutes is None
                 else self.now - timedelta(minutes=self.memory_minutes))
        self.history = self.store.recent_turns(self.thread_key, HISTORY, since=since)
        if is_details_word(text) and not self.county:  # C36 point 5: county asks the model
            return self.details()
        screened = guard.screen(text)
        if screened.refuse and not self.county:  # C36 point 1: county mode adds nothing
            self.guard_code = screened.refuse
            return self.end("UNSUPPORTED", screened.refuse)
        self.guard_code = None if screened.refuse else screened.restricted
        # C36 points 2 and 3: C29's words and C30's question change what count and analyze
        # answer the model (word_hint); they no longer end the turn.
        # S3A: the guard's restrictions are about what the SYNTHETIC data lacks; in county
        # mode the eight tools are always offered (C0) and the refusal above still holds.
        self.restricted = None if self.county else screened.restricted
        utc_day = self.now.astimezone(timezone.utc).date()
        if s.moco_daily_model_calls > 0 and \
                self.store.model_calls_on(utc_day) >= s.moco_daily_model_calls:
            return self.end("ERROR", "RATE_LIMITED")
        self.store.record_model_call(utc_day)
        return self.loop()

    def loop(self):
        restricted = self.restricted is not None
        self.model_id = str(self.model.model_id)
        if self.county:
            prompt, self.prompt_version = read_prompt(COUNTY_TALK_PROMPT if self.talk
                                                      else COUNTY_PROMPT)
            offered = county_tools(self.sources, self.talk)
            messages = [county_system_message(
                prompt, self.sources, self.copies, self.today,
                replies.about_you(self.s) if self.talk else None)]  # C57 point 7
        else:
            prompt, self.prompt_version = read_prompt(TALK_PROMPT if self.talk else None)
            offered = tools(self.registry, restricted, self.talk)
            messages = [system_message(prompt, self.registry, self.today, restricted)]
        names = {t["function"]["name"] for t in offered}
        n = self.s.moco_thread_turns_in_context
        if n > 0 and (block := thread_message(
                self.history[-n:], total=len(self.history) if self.county else None)):
            messages.append(block)
        messages.append(latest_message(self.question))
        started = self.started = self.clock()
        while True:
            if self.steps >= self.s.moco_max_steps or \
                    self.clock() - started >= self.s.moco_turn_seconds:
                return self.unretried() or self.end_fixed("LOOP_LIMIT", "MODEL_BAD_OUTPUT")
            self.steps += 1
            try:
                step = self.model.step(messages, offered)
            except ModelUnavailable:
                return self.unretried() or self.end_fixed("MODEL_UNAVAILABLE",
                                                          "MODEL_UNAVAILABLE")
            calls = list(step.tool_calls or [])
            logged = []  # R6: each step keeps what the model wrote, exactly, or null
            self.step_log.append({"step": self.steps, "text": step.text, "tool_calls": logged})
            if not calls:
                if isinstance(step.text, str) and step.text.strip():  # read as finish (A4)
                    self.finish_text = step.text
                    kind = "about_data" if self.described and not self.results else "finding"
                    if self.talk and not self.results and not self.described:
                        kind = "talk"  # T1 reading: with talk on, plain words are talk
                    text = replies.tidy(step.text) if self.talk else step.text  # T10
                    out = self.second_try(self.finish_turn(kind, text), can_ask=self.talk)
                    if isinstance(out, _End):
                        return out
                    # T13: no finish call to answer, so the REWRITE goes in as a note
                    messages += [{"role": "assistant", "content": step.text},
                                 {"role": "user", "content": PROGRAM_NOTE + json.dumps(out)}]
                continue
            assistant = {"role": "assistant", "content": "", "tool_calls": []}
            answers = []
            for i, call in enumerate(calls):
                call_id = call.id or f"call_{self.steps}_{i}"
                outcome = self.run_call(call, names)
                logged.append({"id": call_id, "name": call.name,
                               "arguments": call.arguments_json,
                               "answer": "ended the turn" if isinstance(outcome, _End)
                               else outcome})
                if isinstance(outcome, _End):
                    return outcome
                assistant["tool_calls"].append({"id": call_id, "type": "function", "function": {
                    "name": call.name, "arguments": _echo(call.arguments_json)}})
                answers.append({"role": "tool", "tool_call_id": call_id,
                                "content": json.dumps(outcome)})
            messages += [assistant, *answers]

    def run_call(self, call, names):
        """One tool call: Python's JSON answer, or an _End when the call ends the turn."""
        self.calls += 1
        if self.calls > MAX_CALLS:
            return {"error": "LIMIT"}
        try:
            arguments = json.loads(call.arguments_json)
        except (TypeError, ValueError):
            arguments = None
        if call.name not in names or not isinstance(arguments, dict):
            return {"error": "BAD_CALL"}
        county = getattr(self, "county_" + call.name, None) if self.county else None
        return (county or getattr(self, "tool_" + call.name))(arguments)

    # ---- the tools (A3) -------------------------------------------------------------------

    def tool_count_arrests(self, arguments):
        year, age = tidy(arguments, "year"), tidy(arguments, "age_group")
        pending, base = self.pending(), self.base()
        year_kept = age_kept = False
        if year is NOT_STATED:
            year = pending.get("year") if pending.get("year") is not None else base.get("year")
            if year is None:
                stated = age if isinstance(age, str) and (
                    age == ALL or age in self.registry.age_groups) else None
                return self.needs_input("year", stated or read_age_group(self.question))
            year_kept = True
        if age is NOT_STATED:
            age = pending.get("age_group") or base.get("age_group")
            age_kept = age is not None
            age = age or ALL
        group = None if age == ALL else age
        for r in self.results:
            if r["kind"] == "count" and (r["year"], r["age_group"]) == (year, group):
                self.keep(year if year_kept else None, group if age_kept else NOT_STATED)
                return self.count_answer(r)
        if self.counts_run >= MAX_COUNTS:
            return {"error": "LIMIT"}
        self.counts_run += 1
        record = execute_call(SKILL, {"year": year, "age_group": group}, question=self.question,
                              data_path=self.data_path, runs_dir=self.runs,
                              model_id=self.model_id, router=self.router)
        if record.reason_code in ("DATA_CLASS_MISMATCH", "DATA_UNREADABLE"):
            return self.end("ERROR", record.reason_code)
        if record.status != "ANSWERED":
            self.count_errors.append(record.reason_code)
            return {"error": record.reason_code, "covers": replies.covers(self.registry)}
        values = record.computed_values
        result = {"id": f"r{len(self.results) + 1}", "kind": "count", "year": year,
                  "age_group": group, "age": age_wording(group, self.registry),
                  "total": values["total"],
                  "by_month": [n for _, n in sorted(values["by_month"].items())],
                  "run_id": record.run_id, "chart": record.chart_uri}
        self.results.append(result)
        self.keep(year if year_kept else None, group if age_kept else NOT_STATED)
        return self.count_answer(result)

    def count_answer(self, r):
        return {"result_id": r["id"], "year": r["year"], "age_group": r["age_group"] or ALL,
                "slots": [f"{{{r['id']}.count}}", f"{{{r['id']}.months}}"]}

    def keep(self, year, group):
        """Note what a count with a result took from memory (A5 "kept")."""
        if year is not None:
            self.kept_year, self.carried["year"] = year, True
        if group is not NOT_STATED:
            self.kept_age, self.carried["age_group"] = age_wording(group, self.registry), True

    def tool_compare(self, arguments):
        ids, counts = arguments.get("result_ids"), {r["id"]: r for r in self.results
                                                    if r["kind"] == "count"}
        if (not isinstance(ids, list) or not 2 <= len(ids) <= 8
                or arguments.get("field") != "total"
                or not all(isinstance(i, str) and i in counts for i in ids)
                or len(set(ids)) != len(ids)):
            return {"error": "BAD_COMPARE"}
        values = compare_counts([{k: counts[i][k] for k in ("year", "age_group", "total")}
                                 for i in ids], self.registry)
        result = {"id": f"r{len(self.results) + 1}", "kind": "compare", "ids": ids, **values}
        self.results.append(result)
        return {"result_id": result["id"], "slots": [f"{{{result['id']}.compare}}"]}

    def tool_describe_data(self, arguments):
        self.described = True
        return {"facts": [{"slot": f"{{f{n}}}", "text": line}
                          for n, line in enumerate(replies.load_facts(), 1)]}

    def tool_ask_user(self, arguments):
        missing = arguments.get("missing")
        missing = missing if isinstance(missing, str) and missing in MISSING_VALUES else "other"
        if missing != "year":
            return self.needs_input(missing, None)
        if self.restricted:  # R4: a restricted turn never counts
            return self.end("UNSUPPORTED", self.restricted)
        if self.pending().get("year") is None and self.base().get("year") is None:
            return self.needs_input("year", read_age_group(self.question))
        # A5: a year is known, so Python does not ask: one count, the fixed rendering.
        answer = self.tool_count_arrests({"year": None,
                                          "age_group": read_age_group(self.question)})
        if isinstance(answer, _End):
            return answer
        last_error = self.count_errors[-1] if self.count_errors else "MODEL_BAD_OUTPUT"
        return self.end_fixed("ASKED_KNOWN_YEAR", last_error)

    def tool_show_details(self, arguments):
        if self.results:  # R3: read as "send the answer"
            return self.end_fixed("DETAILS_THIS_TURN", "MODEL_BAD_OUTPUT")
        return self.details()

    def tool_decline(self, arguments):
        code = arguments.get("reason_code")
        if not (isinstance(code, str) and code in DECLINE_CODES):
            return {"error": "BAD_CALL"}
        if self.results:
            return self.end_fixed("DECLINED_AFTER_RESULTS", "MODEL_BAD_OUTPUT")
        lead, failures, found = self.own_words(arguments)  # C41
        return self.own_end(lambda words: self.end("UNSUPPORTED", code, lead=words), lead,
                            failures, found, ask=False)

    def own_words(self, arguments):
        """C41 points 2 and 3: the model's own `text` for a decline or an ask_user, when it
        passes T1's talk check: (lead, [], []); else (None, the check's codes, what it found).
        C43 point 2: the person's own words in quotation marks are checked as "it"."""
        text = arguments.get("text")
        self.own_text = None
        if not (self.county and self.talk and isinstance(text, str) and text.strip()):
            return None, [], []
        text = self.own_text = replies.tidy(text)
        labels = self.labels()
        failures, found = replies.talk_check(replies.unquoted(text, self.question, labels),
                                             labels)
        return (None, failures, found) if failures else (text, [], [])

    def own_end(self, make, lead, failures, found, *, ask):
        """C43 point 1: own words that fail get one second try (a REWRITE answer, the turn
        goes on) when a step and five seconds are left; the end it would have had is held.
        The failures are every failed try's codes, in order, without repeats. C45: a failing
        text that ends the turn keeps its sentences that pass. `make(words)` is the end."""
        if failures:
            lead = self.kept_words(ask)
        if self.own_first is not None:  # the second try: never a third
            self.held = None
            return self.own_style(make(lead), lead,
                                  list(dict.fromkeys(self.own_first + failures)))
        if failures and self.steps < self.s.moco_max_steps \
                and self.s.moco_turn_seconds - (self.clock() - self.started) >= 5:
            self.own_first = list(failures)
            self.held = self.own_style(make(None), None, failures)  # S3-R12-A answer 2
            found = [str(f) for f in dict.fromkeys(found)][:5]
            do = (f"Say it again in other words, without: {', '.join(found)}." if found else
                  "Say it again in other words, in one or two short sentences.")  # S3-R11-A q1
            return {"error": "REWRITE", "problems": list(failures), "found": found, "do": do}
        return self.own_style(make(lead), lead, failures)

    @staticmethod
    def own_style(end, lead, failures):
        if lead:
            end.style, end.reply_text = "agent", lead
        end.failures = list(failures)
        return end

    def kept_words(self, ask):
        """C45 point 1: the sentences of the latest own words that pass T1's check each alone
        (C43 point 2 too), in order, joined with one space; None when none passes or, for an
        ask_user, when the last kept sentence does not end with "?"."""
        if not self.own_text:
            return None
        keep = [s for s in replies._sentences(self.own_text)
                if not replies.talk_check(replies.unquoted(s, self.question, self.labels()),
                                           self.labels())[0]]
        if not keep or (ask and not keep[-1].endswith("?")):
            return None
        kept = " ".join(keep)
        if replies.talk_check(replies.unquoted(kept, self.question), self.labels())[0]:
            return None  # S3-R12-A answer 1: what is kept passes the check as a whole too
        return kept

    def tool_finish(self, arguments):
        kind = arguments.get("kind")
        if not (isinstance(kind, str) and kind in (TALK_KINDS if self.talk else FINISH_KINDS)):
            return {"error": "BAD_CALL"}
        self.finish_text = text = arguments.get("text")
        if self.talk:
            text = replies.tidy(text)  # T10: what is checked, sent and saved
        return self.second_try(self.finish_turn(kind, text), can_ask=True)

    # ---- memory (A5) ------------------------------------------------------------------------

    def last_turn(self):
        """The most recent earlier turn the filling reads: a talk turn is skipped (T4)."""
        return next((t for t in reversed(self.history) if t["status"] != "TALKED"), None)

    def pending(self):
        """The values the most recent earlier turn saved, when it was NEEDS_INPUT."""
        last = self.last_turn()
        return (last.get("pending") or {}) if last and last["status"] == "NEEDS_INPUT" else {}

    def base(self):
        """Year and age group from the most recent earlier turn with count results, each only
        when its counts share exactly one."""
        for turn in reversed(self.history):
            counts = [r for r in turn.get("results") or [] if r["kind"] == "count"]
            if counts:
                years = {r["year"] for r in counts}
                groups = {r["age_group"] or ALL for r in counts}
                return {"year": years.pop() if len(years) == 1 else None,
                        "age_group": groups.pop() if len(groups) == 1 else None}
        return {}

    # ---- ending the turn (A4, A5, A7, A10) ----------------------------------------------------

    def end(self, status, code, lead=None, **extra):
        limit = self.s.moco_max_question_chars
        if self.county:
            return _End(status, code, replies.county_text(code, self.sources, self.copies,
                                                          self.registry, limit, lead=lead),
                        **extra)
        return _End(status, code, replies.fixed_text(code, self.registry, limit), **extra)

    def needs_input(self, missing, age_group):
        return _End("NEEDS_INPUT", "NEEDS_CLARIFICATION",
                    replies.fixed_text(f"NEEDS_{missing}", self.registry),
                    pending={"year": None, "age_group": age_group}, missing=missing)

    def render(self):
        """The fixed rendering of this turn's results (A7; C10 in county mode)."""
        if self.county:
            return replies.county_fixed(self.results)
        return replies.render_fixed(self.results, self.registry)

    def answered(self, line1, kind, style, failures, reply_text=None):
        first = not any(t["status"] == "ANSWERED" for t in self.history)
        if self.county:
            text = replies.county_answer(line1, self.results, self.sources, kept=self.kept,
                                         first=first, widened=self.widened(),
                                         not_made=self.not_made())
        else:
            text = replies.answered_text(line1, kept_year=self.kept_year,
                                         kept_age=self.kept_age, first=first)
        return _End("ANSWERED", None, text, kind=kind, style=style, failures=list(failures),
                    reply_text=reply_text)

    def not_made(self):
        """C64 point 3: a line for each kind of count or comparison this turn was refused."""
        return ([replies.HELD_BACK_LINE] if self.held_back else []) \
            + ([replies.too_many_line(MAX_COUNTS)] if self.too_many else []) \
            + ([replies.MIXED_SOURCES_LINE] if self.mixed else []) \
            + ([replies.whole_county_line(self.left_district)] if self.left_district else [])

    def whole_county(self, source, spec, kept, carried, arguments):
        """S3A C73 (D-091): a rate is for the whole county (the Census counts no residents by
        police district), so a district filter kept from earlier, and not named in this call, is
        left out of the rate instead of refusing it; the reply says which. A district named in
        the call is still refused (R10 point 7)."""
        district = rates.district_field(source)
        stated = {f.get("field") for f in (arguments.get("filters") or []) if isinstance(f, dict)}
        if district is None or district in stated:
            return spec, kept
        dropped = [f for f in spec["filters"] if f.get("field") == district]
        if not dropped:
            return spec, kept
        gone = [counting.filter_label(source, f) for f in dropped]
        self.left_district += [g for g in gone if g not in self.left_district]
        kept = [k for k in kept if k not in gone]
        if not kept:
            carried.discard("filters")
        return dict(spec, filters=[f for f in spec["filters"] if f.get("field") != district]), kept

    def end_fixed(self, failure, code_without_results):
        """With results: ANSWERED, the fixed rendering, `failure` among the failure codes.
        Without: ERROR (or UNSUPPORTED for OUT_OF_COVERAGE) with the code's row."""
        if self.results:
            return self.answered(self.render(), "finding", "fallback", [failure])
        if self.made_nothing() is not None:  # C36: a word's tool answer, then no step left
            return self.made_nothing()
        return self.end(STATUS_FOR.get(code_without_results, "ERROR"), code_without_results)

    def made_nothing(self):
        """C36 points 2 to 4: a turn ending with nothing made after a word's tool answer
        ends as that answer's refusal would have: C32's question, or the code's row."""
        code = self.count_errors[-1] if self.count_errors else None
        if code == "AGES_NOT_STATED" and self.vague_end is not None:
            return self.vague_end
        if code in ("UNSUPPORTED_METRIC", "UNSUPPORTED_FIELD"):
            return self.end("UNSUPPORTED", code)
        return None

    def finish_turn(self, kind, text):
        if self.results:
            return self.finding(text)
        if self.count_errors:  # every count returned an error: that error's row (A7)
            code = self.count_errors[-1]
            if code == "AGES_NOT_STATED" and self.vague_end is not None:  # C36 point 4
                return self.vague_end
            if self.error_text is not None and self.error_text[0] == len(self.count_errors):
                # S3S S10 answer 10: a refused analysis ends with the line of its rule
                return _End(STATUS_FOR.get(code, "UNSUPPORTED"), code, self.error_text[1])
            return self.end(STATUS_FOR.get(code, "UNSUPPORTED"), code)
        if kind == "about_data" or (kind == "finding" and self.county and self.described):
            # C62 point 4: a finding with nothing counted, after describe_data, is about the data
            return self.county_about(text) if self.county else self.about(text)
        if kind == "background":
            return self.background(text)
        if kind == "talk":  # offered only with MOCO_TALK on
            return self.talked(text)
        return self.end("UNSUPPORTED", "UNRECOGNIZED_QUESTION")

    def check(self, text, slots, most_slots=None):
        """R1's check, or T2's sentence by sentence with MOCO_TALK on."""
        if self.talk:
            return replies.talk_finding_check(text, slots, replies.load_words(), self.labels(),
                                              most_slots, own_words=self.county)  # C38
        return replies.check(text, slots, replies.load_words(), most_slots=most_slots)

    def finding(self, text):
        fixed = self.render()
        if self.s.moco_reply_style == "fixed":
            return self.answered(fixed, "finding", "fixed", [])
        failures, details = self.check(text, replies.offered_slots(self.results))
        if failures:
            end = self.answered(fixed, "finding", "fallback", failures)
            end.details, end.found = details, details.get("found", [])
            return end
        return self.answered(replies.fill(text, self.results, self.registry), "finding",
                             "agent", [], text)

    def about(self, text):
        about = _End("EXPLAINED", None, replies.fixed_text("ABOUT", self.registry),
                     kind="about_data")
        if self.s.moco_reply_style == "fixed":
            return about
        about.style = "fallback"
        if not self.described:
            return about
        facts = replies.load_facts()
        about.failures, details = self.check(text, replies.offered_slots(facts=facts), 4)
        if about.failures:
            about.details, about.found = details, details.get("found", [])
        else:
            filled = replies.fill(text, [], self.registry, facts)
            about.text, about.style, about.reply_text = filled, "agent", text
            if "SYNTHETIC" not in filled:
                about.text = f"{filled} {replies.DATA_TAG}"
        return about

    def background(self, text):
        refused = self.end("UNSUPPORTED", "BACKGROUND_OFF", kind="background")
        if self.s.moco_background != "on" or self.s.moco_reply_style == "fixed":
            return refused
        failures = replies.check_background(text, replies.load_rules())
        if self.talk:  # T6: his reasoning made explicit
            failures += replies.reason_check(text)
        if failures:
            refused.style, refused.failures = "fallback", failures
            refused.found = replies.background_found(text, failures)
            return refused
        return _End("EXPLAINED", None, replies.background_text(text), kind="background",
                    style="agent", reply_text=text)

    def talked(self, text):
        """T1: a talk text that passes is sent as it is; else the fallback line. Either way
        the text sent is saved with the turn (T4)."""
        failures, found = replies.talk_check(text, self.labels())
        makers = replies.maker_words(text, replies.model_label(self.s)) if self.county else []
        if makers:  # C62 point 1
            failures, found = [*failures, "MAKER"], [*found, *makers]
        if failures:
            line = (replies.county_talk_fallback(self.sources, failures) if self.county  # C61.9
                    else replies.load_talk_rules()["fallback_line"])
            return _End("TALKED", None, line, kind="talk", style="fallback", failures=failures,
                        reply_text=line, found=found, draft=text)
        return _End("TALKED", None, text, kind="talk", style="agent", reply_text=text)

    def labels(self):
        """T1 LABEL: the registry's age wordings, or in county mode every label of every
        category or flag field of the loaded sources."""
        if not self.county:
            return list(self.registry.age_groups.values())
        out = []
        for source in self.sources.values():
            for f in source["fields"]:
                if f["kind"] == "category":
                    out += f["values"].values()
                elif f["kind"] == "flag":
                    out += [f["yes"], f["no"]]
        return list(dict.fromkeys(out))

    def second_try(self, end, *, can_ask):
        """T3. The first finish text of the turn that fails its check, with a step and five
        seconds left, is answered with REWRITE and the turn goes on; any other end stands."""
        if not self.talk or not isinstance(end, _End):
            return end
        failed = end.style == "fallback" and bool(end.failures)
        room = (can_ask and self.steps < self.s.moco_max_steps
                and self.s.moco_turn_seconds - (self.clock() - self.started) >= 5)
        if self.first_failures is not None:  # this was the second try
            # C61 point 8: a county talk text gets one more; the third text is the last
            if not (self.county and end.kind == "talk" and failed and room
                    and not self.third_try):
                return self.cut(end)
            self.third_try = True
        else:
            self.first_failures = list(end.failures) if failed else []
        if not (failed and room):
            return self.cut(end)
        self.held = end
        hints = replies.load_talk_rules()["rewrite_hints"]
        # ponytail: ADVICE, CERTAIN and HEDGE have no hint in talk_rules.json; the first code
        # that has one is used, else none.
        return {"error": "REWRITE", "problems": list(end.failures),
                "found": list(dict.fromkeys(end.found))[:5],
                "do": next((hints[c] for c in end.failures if c in hints), "")}

    def unretried(self):
        """T3: after a REWRITE with no step or time left (or no model), the first try's end,
        when the turn has made no result since (with results the fixed rendering stands)."""
        return self.cut(self.held) if self.held is not None and not self.results else None

    def cut(self, end):
        """T14: a talk text that ends the turn and is only too long is cut at a sentence
        end and sent, instead of the fallback line."""
        if not (end.kind == "talk" and end.style == "fallback" and end.failures == ["SHAPE"]
                and end.draft):
            return end
        short = replies.cut_talk(end.draft)
        if not short:
            return end
        return _End("TALKED", None, short, kind="talk", style="agent", failures=["SHAPE"],
                    reply_text=short, cut=True)

    def details(self):
        """A10: the most recent earlier turn of the thread that has results (no time limit),
        from the saved records."""
        if self.county:
            return self.county_details()
        turns = self.store.recent_turns(self.thread_key, HISTORY)
        earlier = next((t for t in reversed(turns) if t.get("results")), None)
        if earlier is None:
            return self.end("UNSUPPORTED", "NO_PREVIOUS_ANSWER")
        try:
            counts, limitations = {}, None
            for r in earlier["results"]:
                if r["kind"] != "count":
                    continue
                path = self.runs / r["run_id"] / "manifest.json"
                manifest = json.loads(path.read_text(encoding="utf-8"))
                values, filters = manifest["computed_values"], manifest["filters"]
                counts[r["id"]] = {"year": filters["year"], "age_group": filters["age_group"],
                                   "total": values["total"],
                                   "by_month": [n for _, n in sorted(values["by_month"].items())],
                                   "run_id": manifest["run_id"]}
                limitations = limitations or list(manifest["limitations"])
            compares = [compare_counts([counts[i] for i in r["ids"]], self.registry)
                        for r in earlier["results"] if r["kind"] == "compare"]
        except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError):
            return self.end("ERROR", "RECORD_NOT_FOUND")
        text = replies.details_text(list(counts.values()), compares, self.registry,
                                    limitations or [], [c["run_id"] for c in counts.values()])
        return _End("DETAILS", None, text)

    # ---- the reply, memory and the turn record (A4 step 6, A9, A12) ------------------------------

    def reply(self, end, save=True, remember=True):
        if self.backup_of is not None and self.model_id is not None and \
                (end.status, end.reason_code) != ("ERROR", "MODEL_UNAVAILABLE"):
            end.text = f"{end.text}\n{replies.BACKUP_NOTE}"  # C56 point 5
        if self.earlier_figures and (end.status, end.reason_code) == ("UNSUPPORTED",
                                                                      "NOT_ALLOWED"):
            end.text = end.text.replace(replies.SINGLE_AGE, replies.EARLIER_FIGURES, 1)  # C62
        if self.own_first:  # C50 point 1: a failed try of his own words is always on record
            end.failures = list(dict.fromkeys(self.own_first + list(end.failures or [])))
        counts = [r for r in self.results if r["kind"] == "count"]
        one_chart = not self.county and end.status == "ANSWERED" and len(self.results) == 1
        # S3S S5: each analysis's chart is attached to the same message
        charts = [r for r in self.results if r["kind"] == "analysis"] \
            if end.status == "ANSWERED" else []
        drawn = self.county_chart(counts) if (self.county and end.status == "ANSWERED"
                                              and not charts) else None  # C40
        reply = AgentReply(
            status=end.status, reason_code=end.reason_code, text=end.text,
            chart_path=counts[0]["chart"] if one_chart else (charts[0]["chart"] if charts
                                                             else (drawn and drawn[0])),
            chart_title=(f"Arrest records per month, {counts[0]['year']}, {counts[0]['age']} "
                         f"(SYNTHETIC test data)") if one_chart else (
                statwords.cap(charts[0]["read_as"]) if charts else (drawn and drawn[1])),
            attachments=[r["chart"] for r in charts[1:]] + list(end.attachments),
            run_ids=[r["run_id"] for r in counts], turn_id=self.turn_id,
            model_called=self.model_id is not None, model_id=self.model_id,
            guard_code=self.guard_code, reply_kind=end.kind, reply_style=end.style,
            draft_failures=list(end.failures), carried=dict(self.carried), steps=self.steps,
            results=self.results)
        if save:
            if remember:
                self.remember(end)
            if self.model_id is not None:
                self.save_record(end, reply)
        return reply

    def county_chart(self, counts):
        """C40: one bar chart for a count with a one-way breakdown of two or more groups, or
        for two or more counts of one source with no breakdown: (path, title), or None."""
        if any(r["kind"] == "analysis" for r in self.results) or not counts:
            return None
        one = len(counts) == 1 and len(counts[0]["spec"]["group_by"]) == 1 \
            and len(counts[0]["groups"] or []) >= 2
        many = len(counts) >= 2 and all(not r["spec"]["group_by"] for r in counts) \
            and len({r["source"] for r in counts}) == 1  # C40 amendment 2, point a
        if not (one or many):
            return None
        first = counts[0]
        source = self.sources[first["source"]]
        if one:
            bars = [(str(label), n) for label, n in first["groups"]]
            title = f"{statwords.cap(first['read_as'])}, by {first['dimensions'][0]}"
        else:
            bars = [(r["read_as"], r["total"]) for r in counts]
            title = statwords.cap(f"{source['unit']['many']} compared")
        subtitle = (f"Copy of the county's data of "
                    f"{counting.day_text(date.fromisoformat(first['copy']['date']))}.")
        foot = f"{source['title']}. Recorded {source['unit']['many']}, not people."
        line = replies.counts_cause_line(counts, self.sources)  # C40 point 3, amendment 2 b
        if line:
            foot += " " + line
        path = Path(self.runs) / first["run_id"] / "chart.png"
        try:
            countchart.draw(bars, first["floor"], title, subtitle, foot, path)
        except Exception:  # a chart never stops an answer
            log.warning("the count chart could not be drawn", exc_info=True)
            return None
        return str(path), title

    def remember(self, end):
        if self.county:  # C9: specs and read_as only, never a value
            stored = [{"id": r["id"], "kind": "count", "spec": r["spec"],
                       "read_as": r["read_as"], "run_id": r["run_id"],
                       "days": self.days_of(r["spec"]["source"])}  # C62 point 5
                      if r["kind"] == "count" else
                      {"id": r["id"], "kind": "analysis", "stat": r["stat"], "spec": r["spec"],
                       "options": r["options"], "read_as": r["read_as"], "run_id": r["run_id"],
                       "days": self.days_of(r["spec"]["source"])}  # C65 point 2
                      if r["kind"] == "analysis" else {"id": r["id"], "kind": r["kind"],
                                                       "ids": r["ids"]}
                      for r in self.results]
        else:
            stored = [{"id": r["id"], "kind": "count", "year": r["year"],
                       "age_group": r["age_group"], "run_id": r["run_id"]}
                      if r["kind"] == "count" else {"id": r["id"], "kind": "compare",
                                                    "ids": r["ids"]}
                      for r in self.results]
        self.store.add_turn(
            thread_key=self.thread_key, user_id=self.user_id,
            question=self.question[:self.s.moco_max_question_chars], status=end.status,
            reason_code=end.reason_code, created_at=self.now,
            record={"turn_id": self.turn_id, "guard_code": self.guard_code,
                    "model_id": self.model_id, "steps": self.steps, "results": stored,
                    "carried": self.carried, "pending": end.pending, "missing": end.missing,
                    "reply_kind": end.kind, "reply_style": end.style,
                    "reply_text": end.reply_text,
                    **({"notices": end.notices} if end.notices else {}),  # C57 point 5
                    **({"age_rule": True}  # C66 point 3: a count was refused under the rule
                       if self.county and "NOT_ALLOWED" in self.count_errors else {}),
                    **({"sent": replies.sent_text(end.text, self.sources)}  # C61 point 4
                       if self.county else {})})

    def save_record(self, end, reply):
        record = {"turn_id": self.turn_id, "created_at": self.now.isoformat(),
                  "data_class": sources.COUNTY if self.county else self.registry.data_class,
                  "question": self.question,
                  "model_id": self.model_id, "prompt_version": self.prompt_version,
                  "guard_code": self.guard_code, "steps": self.step_log,
                  "results": self.results, "finish_text": self.finish_text,
                  "draft_failures": list(end.failures), "check_details": end.details,
                  "reply": reply.text,
                  "kept": ({"carried": self.carried, "labels": self.kept} if self.county
                           else {"carried": self.carried, "year": self.kept_year,
                                 "age_group": self.kept_age}),
                  "status": end.status, "reason_code": end.reason_code,
                  "reply_kind": end.kind, "reply_style": end.style}
        if self.backup_of is not None:  # C56 point 6
            record["backup_of"] = self.backup_of
        if self.talk:  # T3: the codes of both tries
            record["first_failures"] = self.first_failures or []
            record["failures"] = list(end.failures)
            if end.cut:  # T14
                record["cut"] = True
        folder = self.runs / self.turn_id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "turn.json").write_text(json.dumps(record, indent=2, default=str) + "\n",
                                          encoding="utf-8")

    # ---- county mode: the tools of C5 and C7, filling (C9), about (C11), details --------------

    def analysis_hint(self, arguments):
        """S13.9: a count with no period, none pending or kept, for a question in the words of
        an analysis, is answered once a turn with a hint instead of the period question."""
        if self.hinted_analyze or arguments.get("period") not in (None, "", {}):
            return False
        if self.county_pending().get("period") or self.county_base().get("period"):
            return False
        if not ANALYSIS_WORDS.search(self.question):
            return False
        self.hinted_analyze = True
        return True

    def word_hint(self):
        """C36 points 2 and 3: a message with a word of C29's list, or C30's question, gets
        this tool answer instead of a count, once a turn (C48); inside, that request is
        refused with that code (so a turn ending with nothing made gets its row)."""
        if self.hinted_word:  # C48: once a turn; after it the model's request runs
            return None
        word = guard.outcome_word(self.question)
        if word or guard.asks_who(self.question):
            self.hinted_word = True
        if word:
            self.count_errors.append("UNSUPPORTED_METRIC")
            return {"error": "NOT_RECORDED",
                    "why": f"The message names {word}, which happens after an arrest: no "
                           f"listed source records it, and a count of records does not answer "
                           f"it. If that is what the message asks for, call decline with "
                           f"UNSUPPORTED_METRIC."}
        if guard.asks_who(self.question):
            self.count_errors.append("UNSUPPORTED_FIELD")
            return {"error": "NOT_RECORDED",
                    "why": "The message asks who someone was: no listed source holds a name. "
                           "If that is what the message asks for, call decline with "
                           "UNSUPPORTED_FIELD."}
        return None

    def county_count(self, arguments):
        if hint := self.word_hint():
            return hint
        if self.analysis_hint(arguments):
            return {"error": "USE_ANALYZE", "why": ANALYZE_HINT}
        filled = self.fill_spec(arguments)
        if isinstance(filled, _End):
            return filled
        if isinstance(filled, dict):  # a tool error; the turn goes on
            self.count_errors.append(filled["error"])
            if filled["error"] == "NOT_ALLOWED":
                self.single_years += [low for low, high in self.ages_asked(arguments)
                                      if low == high < 18]
            return filled
        spec, kept, carried = filled
        for r in self.results:
            if r["kind"] == "count" and r["spec"] == spec:
                self.keep_county(kept, carried)
                return self.county_count_answer(r)
        source, copy = self.sources[spec["source"]], self.copies[spec["source"]]
        held = self.one_year(source, copy, [spec], [])  # C21, C61 point 10, C65
        if held is not None:
            return held
        if self.counts_run >= MAX_COUNTS:
            self.count_errors.append("TOO_MANY")
            self.too_many = True
            return {"error": "TOO_MANY", "why": f"at most {MAX_COUNTS} counts in one message"}
        self.counts_run += 1
        try:
            figures = counting.count(source, copy, sources.copy_rows(copy), spec)
        except counting.SpecError as e:
            self.count_errors.append(e.code)
            return e.answer()
        result = {"id": f"r{len(self.results) + 1}",
                  **counting.count_result(source, copy, spec, figures)}
        result["run_id"] = self.save_count_record(result, source, copy)
        result["kept_labels"] = list(kept)  # S3A C70 point 2
        if not self.supersede(result):
            self.results.append(result)
        self.keep_county(kept, carried)
        return self.county_count_answer(result)

    def ages_asked(self, request):
        """C28: the (first, last) age of each age filter in a request, cut to the usable ages
        of its source (the source named, else any source with an age field)."""
        named = self.sources.get(request.get("source"))
        fields = [f for s in ([named] if named else self.sources.values())
                  for f in s["fields"] if f["kind"] == "age"]
        out = []
        for flt in request.get("filters") or []:
            f = next((f for f in fields if isinstance(flt, dict)
                      and flt.get("field") == f["name"]), None)
            try:
                if f is not None:
                    out.append((max(int(flt.get("from", f["usable"][0])), f["usable"][0]),
                                min(int(flt.get("to", f["usable"][1])), f["usable"][1])))
            except (TypeError, ValueError):
                pass
        return out

    def widened(self):
        """C28: a count in the reply covers a year of age a count of this turn was refused for.
        A count with no age filter covers every usable age of its source (R10 of the round 5
        tests)."""
        for r in self.results:
            if r["kind"] != "count":
                continue
            ranges = self.ages_asked(r["spec"])
            if not ranges:
                source = self.sources.get(r["spec"].get("source")) or {}
                ranges = [tuple(f["usable"]) for f in source.get("fields", [])
                          if f["kind"] == "age"][:1]
            if any(low <= year <= high for low, high in ranges for year in self.single_years):
                return True
        return False

    @staticmethod
    def county_count_answer(r):
        """C5: the result id, how the request was read, its slots; no value from the data."""
        slots = [f"{{{r['id']}.count}}"] + ([f"{{{r['id']}.groups}}"]
                                            if r["groups"] is not None else [])
        return {"result_id": r["id"], "read_as": r["read_as"], "slots": slots}

    def fill_spec(self, arguments, whole=False):
        """C9: A5's rule part by part (the source, the period, each filter by field): stated,
        else pending, else the last answer's. Returns (spec, kept labels, parts carried), a
        tool error, or an _End (Python asks, or NO_COPY)."""
        pending, base = self.county_pending(), self.county_base()
        kept, carried = [], set()
        sid = arguments.get("source")
        if not (isinstance(sid, str) and sid.strip()) or sid.strip().lower() in ("null", "none"):
            sid = None
        stated_period = arguments.get("period")
        if stated_period in (None, "", {}) or (isinstance(stated_period, str)
                                               and stated_period.lower() in ("null", "none")):
            stated_period = None
        stated = arguments.get("filters")
        stated = [] if stated is None else stated
        if not isinstance(stated, list):
            return {"error": "BAD_FIELD", "why": "filters is a list"}
        if stated_period is None:  # C34: a year sent as a filter is the period
            stated_period, stated = year_filter_period(stated)
        clears = {f.get("field") for f in stated if isinstance(f, dict) and f.get("clear") is True}
        given = [f for f in stated if not (isinstance(f, dict) and f.get("clear") is True)]
        if sid is None:
            with_copy = [s for s in self.sources if self.copies.get(s) is not None]
            if len(with_copy) == 1:
                sid = with_copy[0]
            elif pending.get("source") or base.get("source"):
                sid = pending.get("source") or base.get("source")
                carried.add("source")
                kept.append(re.sub(r"\s*\([^)]*\)", "", self.sources.get(sid, {}).get(
                    "title", sid)).strip())
            elif len(self.sources) == 1:
                sid = next(iter(self.sources))
            else:
                return self.county_needs("source", {"source": None, "period": stated_period,
                                                    "filters": given})
        if sid not in self.sources:
            return {"error": "BAD_VALUE", "field": "source", "sources": list(self.sources)}
        copy = self.copies.get(sid)
        if copy is None:
            return self.end("ERROR", "NO_COPY")
        source = self.sources[sid]
        named = {f.get("field") for f in given if isinstance(f, dict)}
        memory = {}
        if base.get("source") == sid:
            memory.update({f["field"]: f for f in base.get("filters") or []})
        if pending.get("source") in (sid, None):
            memory.update({f["field"]: f for f in pending.get("filters") or []
                           if isinstance(f, dict) and isinstance(f.get("field"), str)})
        if "all" in clears:  # S3A C70 point 1: a new question keeps no filter from earlier
            memory = {}
        vague = self.vague_ages(source, given, memory)
        if vague:  # C32, as C36 point 4: the tool answers the model; C32's question waits
            self.vague_end = _End(
                "NEEDS_INPUT", "NEEDS_CLARIFICATION", replies.ages_question(vague),
                pending={"source": sid, "period": stated_period,
                         "filters": [f for f in given if isinstance(f, dict) and
                                     f.get("field") != counting.age_name(source)]},
                missing="ages")
            return {"error": "AGES_NOT_STATED",
                    "why": f'The message says "{vague}", which names no ages, and this request '
                           f'has ages the message does not state. Call ask_user and ask which '
                           f'ages they mean, or send the request without an age filter.'}
        remembered = {name: f for name, f in memory.items()
                      if name not in named and name not in clears}
        period = stated_period
        if period is None:
            period = pending.get("period") or base.get("period")
            every = {"from": source["coverage_start"], "to": copy.newest_day.isoformat()}
            if period is None and whole:  # S13: an analysis with no period uses every month
                period = every
            elif period is None:
                return self.county_needs("period", {"source": sid, "period": None,
                                                    "filters": given + list(remembered.values())})
            # S3A C72 (D-090): an analysis whose remembered period is the whole copy, the
            # period it would use anyway, keeps nothing and says nothing was kept
            same = whole and isinstance(period, dict) and \
                (period.get("from"), period.get("to")) == (every["from"], every["to"])
            if not same and not (whole and pending.get("period") is None and
                                 base.get("period") is None):
                carried.add("period")
        raw = {"period": period, "filters": given + list(remembered.values()),
               "group_by": arguments.get("group_by")}
        try:
            spec = counting.check_spec(source, copy, raw)
        except counting.SpecError as e:
            return e.answer()
        if "period" in carried:
            kept.append(counting.period_label(spec["period"]))
        for flt in spec["filters"]:
            if flt["field"] in remembered:
                kept.append(counting.filter_label(source, flt))
                carried.add("filters")
        return spec, kept, carried

    def supersede(self, new):
        """S3A C70 point 2: when this new result asks again what an earlier result of this turn
        asked, without one or more filters that the earlier one had only kept from the thread
        (the model saw read_as and cleared them), the new result takes the earlier one's place
        and id, so the reply shows one answer, and the dropped filters are no longer named as
        kept. Not when a share or a comparison of this turn reads the earlier one."""
        b = new.get("spec") or {}
        for i, old in enumerate(self.results):
            if old.get("kind") != new.get("kind") or old is new:
                continue
            if new.get("kind") == "analysis" and (old.get("stat"), old.get("options")) != \
                    (new.get("stat"), new.get("options")):
                continue
            a = old.get("spec") or {}
            if (a.get("source"), a.get("period"), a.get("group_by")) != \
                    (b.get("source"), b.get("period"), b.get("group_by")):
                continue
            fa, fb = a.get("filters") or [], b.get("filters") or []
            dropped = [f for f in fa if f not in fb]
            if not dropped or any(f not in fa for f in fb):
                continue
            source = self.sources.get(a.get("source"))
            gone = {counting.filter_label(source, f) for f in dropped}
            if source is None or not gone <= set(old.get("kept_labels") or []):
                continue
            if any(old["id"] in (r.get("ids") or []) for r in self.results):
                continue
            new["id"] = old["id"]
            self.results[i] = new
            self.kept = [label for label in self.kept if label not in gone]
            return True
        return False

    def keep_county(self, kept, carried):
        self.kept += [label for label in kept if label not in self.kept]
        for part in carried:
            self.carried[part] = True

    def county_needs(self, missing, pending, lead=None):
        return _End("NEEDS_INPUT", "NEEDS_CLARIFICATION",
                    replies.county_text(f"NEEDS_{missing}", self.sources, self.copies,
                                        self.registry, source_id=pending.get("source"),
                                        lead=lead),
                    pending=pending, missing=missing)

    def vague_ages(self, source, given, memory):
        """C32: the words of a vague age group ("young people") in the message, when the
        request carries an age range the message does not state and the thread did not keep;
        else None."""
        words = VAGUE_AGES.search(self.question)
        age = next((f for f in source["fields"] if f["kind"] == "age"), None)
        if words is None or age is None:
            return None
        numbers = {int(n) for n in re.findall(r"(?<!\d)\d{1,3}(?!\d)", self.question)}
        for flt in given:
            if not (isinstance(flt, dict) and flt.get("field") == age["name"]):
                continue
            if age["name"] in memory:  # the thread already holds an age range
                continue
            ends = []
            lowest, highest = age["usable"]
            for key, step in (("from", -1), ("to", 1), ("is", 0)):
                try:
                    if flt.get(key) is None:
                        continue
                    n = int(flt[key])
                except (TypeError, ValueError):
                    return None
                # C55: an end at the usable limit that the message does not state keeps
                # what leaving it out keeps: no end (one the message states is a stated end)
                stated = n in numbers or n + step in numbers
                if not stated and ((key == "from" and n <= lowest)
                                   or (key == "to" and n >= highest)):
                    continue
                ends.append((n, step))
            if not ends or any(n not in numbers and n + step not in numbers
                               for n, step in ends):
                return words.group(0)
        return None

    def county_pending(self):
        last = self.last_turn()
        saved = (last.get("pending") or {}) if last and last["status"] == "NEEDS_INPUT" else {}
        return saved if "filters" in saved else {}

    def county_base(self):
        """The source, the period and the filters of the most recent earlier turn with county
        counts, each only when its counts share exactly one."""
        for turn in reversed(self.history):
            specs = [r["spec"] for r in turn.get("results") or []
                     if r.get("kind") in ("count", "analysis") and "spec" in r]
            if specs:
                ids = {spec["source"] for spec in specs}
                periods = {json.dumps(spec["period"], sort_keys=True) for spec in specs}
                shared = [f for f in specs[0]["filters"]
                          if all(f in spec["filters"] for spec in specs)]
                return {"source": ids.pop() if len(ids) == 1 else None,
                        "period": json.loads(periods.pop()) if len(periods) == 1 else None,
                        "filters": shared}
        return {}

    def save_count_record(self, result, source, copy):
        """C5: stage 1's kind of record, runs/<run id>/manifest.json: the spec, the copy's
        fingerprint and date, the exact figures, the figures as shown, what was left out,
        the limitations."""
        run_id, created_at, run_dir = _new_run(self.runs)
        floor = source["floor"]
        is_not = source["is_not"]
        limitations = [
            f"The count is of {source['unit']['many']}. It is not "
            f"{', '.join(is_not[:-1]) + ' or ' + is_not[-1] if len(is_not) > 1 else is_not[0]}.",
            f"Counts under {floor} are shown as fewer than {floor}. Totals are exact, and the "
            f"county's open data has every record.",
            "The numbers describe counts only. They show no cause and support no claim about "
            "any person.",
            f"Counted by Python from a saved copy of {counting.day_text(copy.day)}, not from "
            f"the live site.",
            "An AI model read the question and chose what to count. Python counted the rows "
            "and wrote every word and number of this answer.",
        ]
        record = {
            "run_id": run_id, "created_at": created_at, "status": "ANSWERED",
            "question": self.question, "router": self.router, "model_id": self.model_id,
            "calculation_version": counting.VERSION, "data_class": sources.COUNTY,
            "source": {"id": source["id"], "title": source["title"],
                       "address": source["address"], "page": source["page"]},
            "copy": result["copy"], "spec": result["spec"], "read_as": result["read_as"],
            "computed_values": {"total": result["total"], "groups": result["groups"],
                                "grid": result["grid"], "left_out": result["left_out"]},
            "shown_values": {
                "total": counting.shown(result["total"], floor),
                "groups": [[g[0], counting.shown(g[1], floor)] for g in result["groups"] or []],
                "grid": [[a, b, counting.shown(n, floor)] for a, b, n in result["grid"] or []],
                "left_out": {k: counting.shown(n, floor) for k, n in result["left_out"].items()}},
            "phrases": result["phrases"], "limitations": limitations, "result": result}
        (run_dir / "manifest.json").write_text(json.dumps(record, indent=2) + "\n",
                                               encoding="utf-8")
        return run_id

    def county_share(self, arguments):
        counts = {r["id"]: r for r in self.results if r["kind"] == "count"}
        part, whole = arguments.get("part_id"), arguments.get("whole_id")
        if {part, whole} & {r["id"] for r in self.results if r["kind"] == "analysis"}:
            return {"error": "BAD_SHARE", "why": ANALYSIS_IDS}  # S13.10
        if not (isinstance(part, str) and isinstance(whole, str)
                and part in counts and whole in counts):
            return {"error": "BAD_SHARE", "why": "both must be counts made in this turn"}
        try:
            values = counting.share_result(self.sources[counts[whole]["source"]], counts[part],
                                           counts[whole])
        except counting.SpecError as e:
            return e.answer()
        result = {"id": f"r{len(self.results) + 1}", **values, "ids": [part, whole]}
        self.results.append(result)
        return {"result_id": result["id"], "slots": [f"{{{result['id']}.share}}"]}

    def county_compare(self, arguments):
        ids = arguments.get("result_ids")
        counts = {r["id"]: r for r in self.results if r["kind"] == "count"}
        if isinstance(ids, list) and set(map(str, ids)) & {
                r["id"] for r in self.results if r["kind"] == "analysis"}:
            return {"error": "BAD_COMPARE", "why": ANALYSIS_IDS}  # S13.10
        if isinstance(ids, list) and len(ids) == 1 and ids[0] in counts \
                and len(counts[ids[0]]["spec"]["group_by"]) == 1:  # C27
            return {"error": "BAD_COMPARE",
                    "why": f"one count is not compared: its {{{ids[0]}.groups}} slot already "
                           f"says which group is highest and lowest"}
        if (not isinstance(ids, list) or not 2 <= len(ids) <= 8
                or not all(isinstance(i, str) and i in counts for i in ids)
                or len(set(ids)) != len(ids)):
            return {"error": "BAD_COMPARE", "why": "two to eight different counts of this turn"}
        chosen = [counts[i] for i in ids]
        if len({r["source"] for r in chosen}) != 1:
            self.mixed = True  # C64 point 3c
            return {"error": "MIXED_SOURCES", "why": "counts of different sources are never "
                                                     "compared"}
        if any(r["spec"]["group_by"] for r in chosen):
            return {"error": "BAD_COMPARE", "why": "only single counts, with no breakdown, are "
                                                   "compared: count each one again with no "
                                                   "group_by"}  # C27
        source = self.sources[chosen[0]["source"]]
        cut = counting.partial_months(chosen)  # C58: a month the copy cuts short
        if cut is not None and cut["to"] < cut["from"]:
            return {"error": "PARTIAL_YEAR", "year": cut["year"],
                    "why": "no month of that period is finished in this copy"}
        if cut is not None:
            return {"error": "PARTIAL_YEAR", "year": cut["year"],
                    "months": {"from": cut["from"], "to": cut["to"]},
                    "why": "count both years again with these months"}
        partial = counting.partial_year(source, chosen)
        if partial is not None:  # C7: Python decides M; the model counts both again
            if partial["months"]["to"] < 1:
                return {"error": "PARTIAL_YEAR", "year": partial["year"],
                        "why": "no month of that year is finished in this copy"}
            return {"error": "PARTIAL_YEAR", **partial,
                    "why": "count both years again with these months"}
        result = {"id": f"r{len(self.results) + 1}", **counting.compare_result(source, chosen),
                  "ids": ids}
        self.results.append(result)
        return {"result_id": result["id"], "slots": [f"{{{result['id']}.compare}}"]}

    # ---- county mode: Part S, the analyze tool (docs/S3S-DESIGN.md S1 to S7) ------------------

    def county_analyze(self, arguments):
        """S1: one analysis of a county source, by R. The source, the period and the filters
        are filled and checked as count's are (C5, C9); the options, the window and the
        refusals are stats.py's; R fits and draws; the model is answered with the result id,
        how the request was read and its slots, never a value."""
        if hint := self.word_hint():  # C36 points 2 and 3
            return hint
        cfg = stats.settings()
        kind = arguments.get("kind")
        if not (isinstance(kind, str) and kind in (*stats.KINDS, "rate")):
            return self.stat_error(counting.SpecError(
                "BAD_OPTIONS", why=f"kind is one of {', '.join(stats.KINDS)}"))
        if self.analyses_run >= cfg["most_analyses"]:
            self.count_errors.append("TOO_MANY")
            return {"error": "TOO_MANY",
                    "why": f"at most {cfg['most_analyses']} analyses in one message"}
        arguments = self.tidy_analyze(arguments)
        if kind == "rate":  # Part S2: rates per resident (docs/S3S2-DESIGN.md)
            return self.county_rate(arguments, cfg)
        if kind == "trend" and not self.hinted_shares and SHARE_WORDS.search(self.question):
            self.hinted_shares = True  # S13.14: once a turn
            return {"error": "USE_SHARES", "why": SHARES_HINT}
        filled = self.fill_spec({k: v for k, v in arguments.items() if k != "group_by"},
                                whole=True)
        if isinstance(filled, _End):
            return filled
        if isinstance(filled, dict):
            self.count_errors.append(filled["error"])
            if "at most one filter per field" in str(filled.get("why")):
                if kind == "trend_compare":
                    filled = dict(filled, why=VERSUS_HINT)
                elif kind == "distribution":
                    filled = dict(filled, why=DIST_HINT)
            return filled
        spec, kept, carried = filled
        source, copy = self.sources[spec["source"]], self.copies[spec["source"]]
        every = {"from": source["coverage_start"], "to": copy.newest_day.isoformat()}
        try:
            try:
                options = stats.check_options(source, spec, kind, arguments.get("options"))
                prep = None
                held = self.one_year(source, copy, [], counting.shown_figures(
                    source, spec, options, *counting.coverage(source, copy),
                    **self.shown_extras(kind)))  # C65 points 2 and 8
                if held is not None:
                    return held
                for r in self.results:  # the same analysis again: the same result
                    if r["kind"] == "analysis" and (r["stat"], r["spec"], r["options"]) == \
                            (kind, spec, options):
                        self.keep_county(kept, carried)
                        return self.analysis_answer(r)
                prep = stats.prepare(source, copy, sources.copy_rows(copy), spec, kind,
                                     options, cfg)
            except counting.SpecError as e:
                # S13.3: a before-and-after whose period leaves too few months on a side is
                # run on every month instead; the reply names the months used
                if not (kind == "before_after" and e.code == "TOO_LITTLE"
                        and e.hint.get("rule") == "sides" and spec["period"] != every):
                    raise
                if "period" in carried:  # S13 answer 2: a kept period not used is not kept
                    label = counting.period_label(spec["period"])
                    kept = [k for k in kept if k != label]
                    carried = {c for c in carried if c != "period"}
                spec = dict(spec, period=every)
                options = stats.check_options(source, spec, kind, arguments.get("options"))
                held = self.one_year(source, copy, [], counting.shown_figures(
                    source, spec, options, *counting.coverage(source, copy),
                    **self.shown_extras(kind)))  # C65 points 2 and 8
                if held is not None:
                    return held
                prep = stats.prepare(source, copy, sources.copy_rows(copy), spec, kind,
                                     options, cfg)
        except counting.SpecError as e:
            if kind == "trend_compare" and "at most one filter per field" in str(
                    e.hint.get("why")):
                e.hint["why"] = VERSUS_HINT
            return self.stat_error(e)
        self.analyses_run += 1
        result = self.analysis_result(source, copy, spec, kind, options, prep)
        run_id, created_at, run_dir = _new_run(self.runs)
        folder = run_dir / "job"  # S2: kept with the saved record, not in git
        job = stats.job_for(source, copy, spec, kind, options, prep, cfg, result)
        stats.write_job(folder, job, prep)
        try:
            answer = stats.run_r(self.s.moco_rscript, kind, folder, cfg["seconds"])
        except stats.EngineError as e:  # S1: logged with R's message, never shown or given
            log.warning("analysis %s (%s) ended with %s: %s", run_id, kind, e.code, e.why)
            return self.end("ERROR", e.code)
        self.fill_analysis(result, answer, prep, cfg)
        result.update(run_id=run_id, chart=str(folder / "chart.png"),
                      script=str(run_dir / "script.R"))
        (run_dir / "script.R").write_text(stats.script_text(source, copy, job),
                                          encoding="utf-8")
        self.save_analysis_record(result, source, run_id, created_at, run_dir)
        result["kept_labels"] = list(kept)  # S3A C70 point 2
        if not self.supersede(result):
            self.results.append(result)
        self.keep_county(kept, carried)
        return self.analysis_answer(result)

    def county_rate(self, arguments, cfg):
        """Part S2: a rate per resident. The source, the period and the filters are filled and
        checked as count's are (C9, C5; with no period Python asks, as for count); then the
        refusals of R10 point 7 in their order, each a tool error whose sentence also ends the
        turn if nothing else is made; the records are counted by Python and the Census figures
        added up; R works out the rates, margins and ratios and draws the chart."""
        filled = self.fill_spec({k: v for k, v in arguments.items() if k != "group_by"})
        if isinstance(filled, _End):
            return filled
        if isinstance(filled, dict):
            self.count_errors.append(filled["error"])
            return filled
        spec, kept, carried = filled
        source, copy = self.sources[spec["source"]], self.copies[spec["source"]]
        spec, kept = self.whole_county(source, spec, kept, carried, arguments)  # S3A C73
        state, ccfg = self.s.moco_state_dir, census.settings()
        try:
            plan = rates.check(source, copy, spec, arguments.get("options"), state, ccfg)
            options = {"by": plan["by"], "reference": plan["reference"]}
            held = self.one_year(source, copy, [], counting.shown_figures(
                source, spec, options, *counting.coverage(source, copy),
                **self.shown_extras("rate")))  # C65 points 2 and 7
            if held is not None:
                return held
            for r in self.results:  # the same rate again: the same result
                if r["kind"] == "analysis" and (r["stat"], r["spec"], r["options"]) == \
                        ("rate", spec, options):
                    self.keep_county(kept, carried)
                    return self.analysis_answer(r)
            copies = {y: census.latest(state, y, ccfg) for y in plan["years"]}
            counts, left = rates.count(source, sources.copy_rows(copy), plan, ccfg)
            shown_keys, reference = rates.choose(plan, counts, copies, ccfg)
        except rates.Refused as e:
            self.count_errors.append(e.code)
            self.error_text = (len(self.count_errors), e.sentence)
            return {"error": e.code, "why": e.sentence}
        except counting.SpecError as e:
            return self.stat_error(e)
        by, years = plan["by"], plan["years"]
        newest = max(copies.values(), key=lambda c: c["fetched_at"])
        labels = {k: rates.label(by, k) for k in counts}
        r = {"id": f"a{sum(1 for x in self.results if x['kind'] == 'analysis') + 1}",
             "kind": "analysis", "stat": "rate", "source": source["id"], "spec": spec,
             "options": options, "unit": dict(source["unit"]), "floor": source["floor"],
             "read_as": rates.read_as(source, by, years), "sensitive": False,
             "interpreted": False, "fit_line": None,
             "copy": {"sha256": copy.sha256, "date": copy.day.isoformat(),
                      "fetched_at": copy.fetched_at, "newest": copy.newest_day.isoformat(),
                      "rows": copy.rows},
             "census_info": {"census_date": newest["fetched_at"][:10],
                             "copies": [{"year": y, "fetched_at": copies[y]["fetched_at"],
                                         "sha256": copies[y]["sha256"]} for y in years]}}
        self.analyses_run += 1
        run_id, created_at, run_dir = _new_run(self.runs)
        folder = run_dir / "job"  # S2: kept with the saved record, not in git
        job = {"kind": "rate", "per": rates.PER, "z": ccfg["margin_z"], "years": years,
               "reference": None if reference is None else shown_keys.index(reference) + 1,
               "groups": [{"k": k, "label": labels[key], "records": counts[key],
                           "residents": rates.residents(ccfg, by, key, years, copies),
                           "no_margin": any(copies[y]["values"][v["variable"]][1] is None
                                            for y in years for v in ccfg["breakdowns"][
                                                "none" if by is None else by][key]),
                           "reference": key == reference}
                          for k, key in enumerate(shown_keys, 1)],
               "chart": rates.chart_labels(source, copy, r["read_as"], years,
                                           r["census_info"]["census_date"], by)}
        rates.write_job(folder, job, rates.census_rows(ccfg, by, shown_keys, years, copies))
        try:
            answer = stats.run_r(self.s.moco_rscript, "rate", folder, cfg["seconds"],
                                 read=rates.read_result)
        except stats.EngineError as e:  # S1: logged with R's message, never shown or given
            log.warning("analysis %s (rate) ended with %s: %s", run_id, e.code, e.why)
            return self.end("ERROR", e.code)
        rates.fill(r, answer, plan, shown_keys, counts, left, labels)
        r.update(run_id=run_id, chart=str(folder / "chart.png"), script=str(run_dir / "script.R"))
        (run_dir / "script.R").write_text(rates.script_text(source, copy, r, plan, ccfg),
                                          encoding="utf-8")
        self.save_analysis_record(r, source, run_id, created_at, run_dir,
                                  limitations=rates.limitations(source, r))
        r["kept_labels"] = list(kept)  # S3A C70 point 2
        if not self.supersede(r):
            self.results.append(r)
        self.keep_county(kept, carried)
        return self.analysis_answer(r)

    @staticmethod
    def tidy_analyze(arguments):
        """S13.4: the shapes the model sends by mistake, read as what they mean. Options sent
        beside `options` are taken as the options; a list or object sent as JSON text is
        read; a period with only one end is no period."""
        out = dict(arguments)
        options = out.get("options")
        if isinstance(options, str):
            try:
                options = json.loads(options)
            except ValueError:
                pass
        if not options:
            options = {k: out.pop(k) for k in OPTION_KEYS if k in out} or options
        if isinstance(options, dict):
            options = dict(options)
            for key, value in options.items():
                if isinstance(value, str) and value.strip()[:1] in ("[", "{"):
                    try:
                        options[key] = json.loads(value)
                    except ValueError:
                        pass
        period = out.get("period")
        # S13.13: a before_after whose date was put in the period: the date is the option
        if out.get("kind") == "before_after" and isinstance(period, dict) and \
                set(period) in ({"from"}, {"date"}) and isinstance(
                    period.get("from", period.get("date")), str) and \
                not (isinstance(options, dict) and options.get("date")):
            day = period.get("from", period.get("date"))
            options = dict(options or {}, date=day[:8] + "01" if len(day) >= 10 else day)
            out.pop("period")
            period = None
        out["options"] = options
        if isinstance(period, dict) and set(period) in ({"from"}, {"to"}, {"date"}):
            out.pop("period")
        return out

    def stat_error(self, e):
        """A refused analysis is a tool error and the turn goes on. TOO_LITTLE and TOO_FINE
        carry the fixed line of S10 answer 10, which ends the turn if nothing else is made;
        the model is told the error and which rule, never a value."""
        self.count_errors.append(e.code)
        if e.code in ("TOO_LITTLE", "TOO_FINE"):
            self.error_text = (len(self.count_errors), e.hint["why"])
        return e.answer()

    @staticmethod
    def analysis_answer(r):
        return {"result_id": r["id"], "read_as": r["read_as"], "slots": list(r["slots"])}

    def analysis_result(self, source, copy, spec, kind, options, prep):
        """A statistical result before R: what was asked and counted, and its labels."""
        months, fields = prep["months"], {f["name"]: f for f in source["fields"]}
        used = stats.used_fields(source, spec, kind, options)
        r = {"id": f"a{sum(1 for x in self.results if x['kind'] == 'analysis') + 1}",
             "kind": "analysis", "stat": kind, "source": source["id"], "spec": spec,
             "options": options, "unit": dict(source["unit"]), "floor": source["floor"],
             "read_as": statwords.read_as(source, spec, kind, options, months),
             "window": {"first": list(months[0]), "last": list(months[-1]),
                        "months": len(months)},
             "records": prep["records"], "left_out": prep["left_out"],
             "sensitive": any(fields[n].get("sensitive") for n in used),
             "interpreted": any(fields[n].get("interpreted") for n in used),
             "copy": {"sha256": copy.sha256, "date": copy.day.isoformat(),
                      "fetched_at": copy.fetched_at, "newest": copy.newest_day.isoformat(),
                      "rows": copy.rows}}
        if kind == "trend":
            r["head"] = " ".join([source["unit"]["many"]] + (
                [statwords.what(source, spec["filters"])] if spec["filters"] else []))
        if kind in ("trend", "before_after"):
            r["yearly"] = prep["yearly"]
        if kind == "trend_compare":
            r["labels"] = statwords.compare_labels(source, spec, options)
        if kind == "before_after":
            when = options["date"]
            r["date_month"] = statwords.month_text((int(when[:4]), int(when[5:7])))
        if kind == "yes_no":
            r["factor_labels"] = [statwords.item_label(source, f, "factor")
                                  for f in options["factors"]]
            r["outcome_label"] = statwords.item_label(source, options["outcome"], "outcome")
            r["factor_whats"] = [statwords.item_what(source, f) for f in options["factors"]]
            r["outcome_what"] = statwords.item_what(source, options["outcome"])  # S11 item 1
            r["held"] = statwords.held_text(source, options["controls"])
        if kind == "shares":
            r["part"] = statwords.what(source, options["part"])
        if kind == "timing":
            r["cells"] = prep["cells"]
        if kind == "distribution":
            r["groups_by"] = options["by"] is not None
        return r

    @staticmethod
    def fill_analysis(r, answer, prep, cfg):
        """R's estimates into the result, then Python's phrases, table and lines (S4, S5)."""
        kind = r["stat"]

        def named(model):
            low = model.lower()
            return ("poisson" if "poisson" in low else
                    "negative binomial" if "negative binomial" in low else model)
        r["model"] = named(answer["model"])

        def keep(e):
            return {k: e.get(k) for k in ("name", "estimate", "low", "high", "p", "clear")}
        r["estimates"] = [keep(e) for e in answer["estimates"]]
        if kind in stats.T_KINDS:
            r["fit_ratio"], r["chart_points"] = answer["fit_ratio"], answer["chart_points"]
        if kind == "trend_compare":  # S12 item 1: each group's own fit and model
            r["own"] = [keep(e) for e in answer["own"]]
            r["models"] = [named(e["model"]) for e in answer["own"]]
            r["model"] = " and ".join(dict.fromkeys(r["models"]))
        if kind == "yes_no":
            r["references"] = answer.get("references") or {}
        if kind == "shares":
            r["years"] = [{"year": int(y["year"]), "share": y["share"], "low": y["low"],
                           "high": y["high"]} for y in answer["years"]]
        if kind == "distribution":
            r["ages"] = [{"label": label, "n": g.get("n"), "median": g["median"], "q1": g["q1"],
                          "q3": g["q3"]} for label, g in zip(prep["labels"] or [None],
                                                             answer["groups"])]
        r["phrases"] = dict(statwords.phrases(r))
        r["slots"] = [f"{{{r['id']}.{name}}}" for name in r["phrases"]]
        r["table"] = statwords.table_lines(r)
        r["fit_line"] = statwords.fit_line(r, cfg["fit_band"])

    def save_analysis_record(self, r, source, run_id, created_at, run_dir, limitations=None):
        """S2 and C5: the saved record, runs/<run id>/manifest.json, beside the job folder
        and the script: the spec, the copy, the estimates, the phrases, the limitations."""
        many, is_not, cfg = source["unit"]["many"], source["is_not"], stats.settings()
        drop = cfg["drop_newest_months"]
        limitations = limitations or [
            f"The analysis is of {many}. It is not "
            f"{', '.join(is_not[:-1]) + ' or ' + is_not[-1] if len(is_not) > 1 else is_not[0]}.",
            statwords.association_line(many),
            f"Counts under {source['floor']} are never shown, in a table or on a chart.",
            f"Only full months are used, and the newest {drop} full month"
            f"{'' if drop == 1 else 's'} of the copy {'is' if drop == 1 else 'are'} left out: "
            f"it may still be filling in at the county.",
            f"Every estimate was computed by R from a saved copy of "
            f"{counting.day_text(date.fromisoformat(r['copy']['date']))}, not from the live "
            f"site. An AI model chose the analysis from a fixed menu and never saw an "
            f"estimate; Python wrote every word and number of the answer.",
        ]
        record = {
            "run_id": run_id, "created_at": created_at, "status": "ANSWERED",
            "question": self.question, "router": self.router, "model_id": self.model_id,
            "data_class": sources.COUNTY,
            "source": {"id": source["id"], "title": source["title"],
                       "address": source["address"], "page": source["page"]},
            "copy": r["copy"], "kind": r["stat"], "spec": r["spec"], "options": r["options"],
            "read_as": r["read_as"], "job_folder": "job", "script": "script.R",
            "phrases": r["phrases"], "limitations": limitations, "result": r}
        (run_dir / "manifest.json").write_text(json.dumps(record, indent=2) + "\n",
                                               encoding="utf-8")

    def county_describe_data(self, arguments):
        self.described = True
        self.facts = replies.county_facts(self.sources, self.copies, self.s)  # C61
        return {"facts": [{"slot": f"{{f{n}}}", "text": line}
                          for n, line in enumerate(self.facts, 1)]}

    def county_ask_user(self, arguments):
        if self.vague_end is not None:  # C36 point 4 (S3-R6-A question 4): C32's question
            return self.vague_end
        missing = arguments.get("missing")
        missing = missing if missing in ("period", "source", "other") else "other"
        if missing == "period" and not self.hinted_period:  # C25 point 0
            self.hinted_period = True
            return {"error": "NO_PERIOD_QUESTION", "why": NO_PERIOD_QUESTION}
        pending = {"source": None, "period": None, "filters": []}
        if missing == "period":  # C25: the thread's own source, else ask for the source
            known = self.county_pending().get("source") or self.county_base().get("source")
            with_copy = [s for s in self.sources if self.copies.get(s) is not None]
            if known not in self.sources and len(with_copy) == 1:  # C25 answer 4
                known = with_copy[0]
            if known in self.sources and self.copies.get(known) is not None:
                pending["source"] = known
            elif len(self.sources) >= replies.SHORT_FROM:
                missing = "source"
        lead, failures, found = self.own_words(arguments)  # C41
        if missing == "source" and len(self.sources) < replies.SHORT_FROM:  # C41 point 2:
            lead, failures, found = None, [], []  # not used, so not checked (S3-R9-A answer 1)
        return self.own_end(lambda words: self.county_needs(missing, pending, words), lead,
                            failures, found, ask=True)

    def county_about(self, text):
        """C11: about_data in county mode; every answer carries the notices."""
        short = self.notices_shown()  # C57 point 5: in full once a thread
        tail = "\n" + (replies.NOTICES_SHOWN if short
                       else "\n".join(replies.notices_lines(self.sources)))
        about = _End("EXPLAINED", None,
                     replies.county_about_text(self.sources, self.copies) + tail,
                     kind="about_data", notices="short" if short else "full")
        if self.s.moco_reply_style == "fixed":
            return about
        about.style = "fallback"
        if not self.described:
            return about
        facts = self.facts or replies.county_facts(self.sources, self.copies, self.s)
        plain = replies.plain_facts(text, facts)
        if plain:  # C63: only the opening and facts: the program writes it, with no check
            about.text, about.style, about.reply_text = plain + tail, "agent", text
            return about
        about.failures, details = self.check(text, replies.offered_slots(facts=facts), 4)
        if about.failures:
            about.details, about.found = details, details.get("found", [])
            chosen = replies.facts_rendering(text, facts)  # C61 point 9b
            if chosen:
                about.text = chosen + tail
        else:
            about.text = replies.fill(text, [], self.registry, facts) + tail
            about.style, about.reply_text = "agent", text
        return about

    def given(self):
        """C65 points 4 and 5: what C21's check holds against: every remembered turn of the
        thread (not only the minutes a direct message shows the model) and the stripped
        records `reset` kept, oldest first. Read once a turn."""
        if self._given is None:
            kept = getattr(self.store, "given_before_reset", None)
            self._given = (kept(self.thread_key, CHECK_TURNS) if kept else []) + \
                self.store.recent_turns(self.thread_key, CHECK_TURNS)
        return self._given

    @staticmethod
    def shown_extras(stat):
        """What counting.shown_figures needs to know of a statistic's kind. C65 point 7: a
        rate by age band shows the Census's bands (config/census.json), each (first, last or
        None). C65 point 8: a distribution's chart shows two-year steps of age."""
        if stat == "rate":
            return {"age_bands": [tuple(ends) for ends in
                                  census.settings()["records"]["age_band"].values()]}
        return {"steps": True} if stat == "distribution" else {}

    def one_year(self, source, copy, specs, shown):
        """C21 with C61 point 10 and C65: the NOT_ALLOWED answer when these new count specs
        and these new figures of a statistic, with what this turn and the thread's ANSWERED
        turns already gave for the source, would give one year of age under 18; else None."""
        sid = source["id"]
        made = [r["spec"] for r in self.results  # C54 point 4: this source's counts only
                if r["kind"] == "count" and r["spec"]["source"] == sid]
        before = [r for t in self.given()  # C65 point 10: of every turn, whatever its ending
                  for r in t.get("results") or []  # C61 point 10: the thread's counts too
                  if isinstance(r.get("spec"), dict) and r["spec"].get("source") == sid]
        earlier = [r for r in before if r.get("kind") == "count"]
        days = [r.get("days") for r in earlier] + [None] * (len(made) + len(specs))  # C62.5
        here = counting.coverage(source, copy)
        now = [f for r in self.results if r["kind"] == "analysis" and r["spec"]["source"] == sid
               for f in counting.shown_figures(source, r["spec"], r.get("options"), *here,
                                               **self.shown_extras(r.get("stat")))]
        then = []  # C65 point 2: what the thread's statistics showed
        for r in before:
            if r.get("kind") == "analysis":
                own = r.get("days")
                span = (counting._day(own[0]), counting._day(own[1])) if own else here
                then += counting.shown_figures(source, r["spec"], r.get("options"), *span,
                                               **self.shown_extras(r.get("stat")))
        if not counting.one_year_under_18(source, [r["spec"] for r in earlier] + made + specs,
                                          copy, days, shown=then + now + shown):
            return None
        self.count_errors.append("NOT_ALLOWED")
        self.held_back = True
        why = ("with this count, the figures of this message would give one year of "
               "age under 18")
        if not counting.one_year_under_18(source, made + specs, copy, shown=now + shown):
            self.earlier_figures = True  # C62 point 2
            why += " Counts given earlier in this conversation are taken into account."
        return counting.SpecError("NOT_ALLOWED", field=counting.age_name(source),
                                  why=why).answer()

    def days_of(self, sid):
        """C62 point 5: the first and last day this turn's copy of the source covers."""
        return [d.isoformat() for d in counting.coverage(self.sources[sid], self.copies[sid])]

    def notices_shown(self):
        """C57 point 5: an earlier turn of the thread's history carried the notices in full."""
        return any(t.get("notices") == "full" for t in getattr(self, "history", None) or [])

    def county_details(self):
        """A10 in county mode, from the saved records; shares and comparisons are worked
        out again from the counts' records."""
        turns = self.store.recent_turns(self.thread_key, HISTORY)
        earlier = next((t for t in reversed(turns) if t.get("results")), None)
        if earlier is None:
            return self.end("UNSUPPORTED", "NO_PREVIOUS_ANSWER")
        try:
            counts, limitations, run_ids, extras, analyses, scripts = {}, None, [], [], [], []
            for r in earlier["results"]:
                if r["kind"] in ("count", "analysis"):
                    path = self.runs / r["run_id"] / "manifest.json"
                    manifest = json.loads(path.read_text(encoding="utf-8"))
                    run_ids.append(manifest["run_id"])
                    limitations = limitations or list(manifest["limitations"])
                    if r["kind"] == "count":
                        counts[r["id"]] = manifest["result"]
                        continue
                    analyses.append(manifest["result"])  # S7: and its script, attached
                    script = self.runs / r["run_id"] / "script.R"
                    if not script.is_file():
                        raise OSError("no script")
                    scripts.append(str(script))
            for r in earlier["results"]:
                chosen = [counts[i] for i in r.get("ids") or []]
                if r["kind"] == "share":
                    phrase = counting.share_result(self.sources[chosen[1]["source"]],
                                                   *chosen)["phrases"]["share"]
                    extras.append(f"Share: {phrase}.")
                elif r["kind"] == "compare":
                    phrase = counting.compare_result(self.sources[chosen[0]["source"]],
                                                     chosen)["phrases"]["compare"]
                    extras.append(f"Compared: {phrase}.")
            short = self.notices_shown()
            text = replies.county_details(list(counts.values()), extras, self.sources,
                                          limitations or [], run_ids, analyses, short=short)
        except (OSError, ValueError, KeyError, TypeError, IndexError, counting.SpecError):
            return self.end("ERROR", "RECORD_NOT_FOUND")
        return _End("DETAILS", None, text, attachments=scripts,
                    notices="short" if short else "full")


def _echo(arguments_json):
    """A call's arguments as given back to the model: the JSON text when it is an object,
    else {} (an endpoint may refuse arguments that are not JSON)."""
    try:
        return arguments_json if isinstance(json.loads(arguments_json), dict) else "{}"
    except (TypeError, ValueError):
        return "{}"
