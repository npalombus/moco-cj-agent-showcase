"""Every word a person reads that Python writes, and the checks on every word the model
writes (design P1A, A7, A10, A13; revision 2, R1). All fixed wording lives here. The allowed
words of a finding or an about_data text are config/reply_words.json (load_words); the word
lists for background are config/reply_rules.json (load_rules). Both are the planning chat's.

`results` is always AgentReply.results of a turn: a list of dicts, in the order made.
  count:   {"id", "kind": "count", "year", "age_group" (code or None), "age" (wording),
            "total", "by_month" (12 ints, January first), "run_id"}
  compare: {"id", "kind": "compare", "ids", "top_label", "top_value", "bottom_label",
            "bottom_value", "difference", "all_equal"}
The model writes fact slots such as {r1.count}; Python writes each fact as one whole phrase
(R1), so a number never stands apart from what it counts. The model's own words around the
slots must all come from the allowed list.
"""
import calendar
import json
import re
import string
import unicodedata
from collections import Counter, OrderedDict
from datetime import date
from functools import lru_cache
from pathlib import Path

from . import counting, rates, statwords
from .analysis import age_wording, join_and
from .core import REPO

DEFAULT_RULES = REPO / "config" / "reply_rules.json"
DEFAULT_WORDS = REPO / "config" / "reply_words.json"
DEFAULT_FACTS = REPO / "config" / "fact_sheet.md"

MONTHS = list(calendar.month_name)[1:]
MONTH_ABBREVIATIONS = list(calendar.month_abbr)[1:]

# ---- fixed wording ------------------------------------------------------------------------

DATA_TAG = "It's SYNTHETIC (made-up) test data."
NOTED = "I've noted it as a request."
LINE2_FIRST = ("This is SYNTHETIC (made-up) test data, not real Montgomery County figures. "
               "Want the details, or a different year or age group?")
LINE2_LATER = "(SYNTHETIC test data, not real county figures.)"
BACKGROUND_PREFIX = "General background, not from this data: "
BACKGROUND_SUFFIX = " I can't check this against the data I have."
DETAILS_HEAD = "Here are the details of my last answer."

# Slack's fixed lines (A13).
ONE_MOMENT = "One moment."
# S3A C56 point 5: the last line of a reply the backup model wrote.
BACKUP_NOTE = ("Note: I'm temporarily running on a smaller backup model, so this answer may "
               "be less sharp than usual.")
NOT_AUTHORIZED = "Sorry, I only answer approved people in this workspace."
WAIT = "That's a lot of questions in one minute. Give me a minute, then ask again."
RESET_DONE = "Done. I've cleared what I remembered of this conversation."
# C65 point 4: in county mode reset keeps which counts were given, and says so.
RESET_DONE_COUNTY = (RESET_DONE + " I keep only a list of which counts I gave here, with no "
                     "figures and no words of yours, so that my rule about single years of age "
                     "under 18 still holds.")
ERROR_LINE = "Something went wrong on my side, so nothing was counted. (ref {ref})"
HELP = ("I count arrest records in SYNTHETIC (made-up) test data and compare the counts. Ask "
        "in your own words, for example \"How many arrests were there each month in 2025 for "
        "ages 18 to 25?\" or \"Compare 2024 and 2025 for people under 18.\" Then follow up: "
        "\"and under 18?\", \"what about 2024?\". You can also ask what the data is and what "
        "it lacks. Say \"details\" for the full breakdown of my last answer, or \"reset\" to "
        "make me forget this conversation.")


def years_wording(registry):
    """`2024`; `2024 or 2025`; `2024 to 2027`, from the registry's coverage."""
    years = registry.coverage_years
    if len(years) == 1:
        return str(years[0])
    if len(years) == 2:
        return f"{years[0]} or {years[1]}"
    return f"{years[0]} to {years[-1]}"


def groups_wording(registry):
    """The registry's wordings joined: `people under 18, ages 18 to 25, ..., or ages 41 and
    over`."""
    wordings = list(registry.age_groups.values())
    return wordings[0] if len(wordings) == 1 else \
        ", ".join(wordings[:-1]) + ", or " + wordings[-1]


def can_ask(registry):
    return (f"I can count arrest records per month for {years_wording(registry)}, for all "
            f"ages or one group ({groups_wording(registry)}), and compare those counts.")


def covers(registry):
    """What a count error tells the model: `2024 to 2025`."""
    years = registry.coverage_years
    return f"{years[0]} to {years[-1]}"


def fixed_text(code, registry, limit=None):
    """A7's table, ABOUT, the background refusal and A10's two refusals. `code` is a reason
    code, or NEEDS_year, NEEDS_age_group, NEEDS_other, ABOUT or BACKGROUND_OFF."""
    ask = can_ask(registry)
    data_problem = ["There's a problem with my data file, so nothing was counted. Whoever "
                    "runs this agent needs to look at it."]
    parts = {
        "REAL_DATA_NOT_AVAILABLE": ["I don't have real figures yet: only SYNTHETIC (made-up) "
                                    "test data is loaded.", NOTED, ask],
        "UNSUPPORTED_METRIC": ["I can't answer that one: I only count arrest records, so I "
                               "have nothing on convictions, sentencing, jail, rates or "
                               "causes.", NOTED, ask, DATA_TAG],
        "UNSUPPORTED_FIELD": ["I can't break it down that way: the data has only the month "
                              "and the age group.", NOTED, ask, DATA_TAG],
        "UNRECOGNIZED_QUESTION": ["I couldn't read that as a question I can answer.", ask,
                                  DATA_TAG],
        "OUT_OF_COVERAGE": ["I have no data for that year.", ask, DATA_TAG],
        "INVALID_ARGUMENTS": ["I couldn't make sense of the year or age group, so nothing was "
                              "counted.", ask, DATA_TAG],
        "INPUT_TOO_LONG": [f"That's longer than I can read (the limit is {limit} characters). "
                           f"Could you ask it more briefly?"],
        "NEEDS_year": [f"Which year do you mean, {years_wording(registry)}?"],
        "NEEDS_age_group": [f"Which age group do you mean: {groups_wording(registry)}, or all "
                            f"ages?"],
        "NEEDS_other": ["Could you say a bit more about what you'd like?", ask, DATA_TAG],
        "MODEL_UNAVAILABLE": ["I can't read questions right now, so nothing was counted. "
                              "Please try again in a few minutes."],
        "MODEL_BAD_OUTPUT": ["I got muddled working on that, so I have no answer. Could you "
                             "ask it again, maybe in other words?"],
        "RATE_LIMITED": ["I've reached today's limit on questions, so nothing was counted. "
                         "Please try again tomorrow."],
        "DATA_CLASS_MISMATCH": data_problem,
        "DATA_UNREADABLE": data_problem,
        "ABOUT": [f"I work with SYNTHETIC (made-up) test data: arrest records for "
                  f"{years_wording(registry)}, each with a month and an age group. I count "
                  f"records, not people, and I have nothing on convictions, sentencing, jail, "
                  f"rates, race, place or offense.", ask],
        "BACKGROUND_OFF": ["That's a general question I can't back up with the data I have.",
                           ask, DATA_TAG],
        "NO_PREVIOUS_ANSWER": ["There's no answer in this conversation to give details on "
                               "yet."],
        "RECORD_NOT_FOUND": ["I can't find the saved record for that answer, so I can't show "
                             "its details."],
    }[code]
    return " ".join(parts)


def answered_text(line1, *, kept_year=None, kept_age=None, first):
    """An ANSWERED reply: line 1, the kept note on the same line, then line 2."""
    kept = ([str(kept_year)] if kept_year is not None else []) + \
        ([kept_age] if kept_age is not None else [])
    note = f" (I kept {' and '.join(kept)} from earlier.)" if kept else ""
    return line1 + note + "\n" + (LINE2_FIRST if first else LINE2_LATER)


def background_text(text):
    return BACKGROUND_PREFIX + text + BACKGROUND_SUFFIX


# ---- the word lists and the facts -----------------------------------------------------

def load_rules(path=None):
    """The parsed config/reply_rules.json (background only, R7)."""
    return json.loads(Path(DEFAULT_RULES if path is None else path).read_text(encoding="utf-8"))


def load_words(path=None):
    """The allowed words of config/reply_words.json, lower case (R1)."""
    data = json.loads(Path(DEFAULT_WORDS if path is None else path).read_text(encoding="utf-8"))
    return frozenset(word.lower() for word in data["allowed"])


def load_facts(path=None):
    """The fact sheet's lines that start with "- ", without the "- ", in order (A8)."""
    text = Path(DEFAULT_FACTS if path is None else path).read_text(encoding="utf-8")
    return [line[2:] for line in text.splitlines() if line.startswith("- ")]


# ---- fact slots and fill (R1) ---------------------------------------------------------------

def _month_list(values, value):
    return join_and([MONTHS[i] for i, v in enumerate(values) if v == value])


def months_phrase(values):
    """`April was the busiest month (50) and January and August the quietest (8 each)`, or
    `every month had the same count (<n>)`."""
    high, low = max(values), min(values)
    if high == low:
        return f"every month had the same count ({high:,})"
    busiest = [i for i, v in enumerate(values) if v == high]
    quietest = [i for i, v in enumerate(values) if v == low]
    first = (f"{MONTHS[busiest[0]]} was the busiest month ({high:,})" if len(busiest) == 1
             else f"{_month_list(values, high)} were the busiest months ({high:,} each)")
    second = (f"{MONTHS[quietest[0]]} the quietest ({low:,})" if len(quietest) == 1
              else f"{_month_list(values, low)} the quietest ({low:,} each)")
    return f"{first} and {second}"


def compare_phrase(c):
    """`2025 had the highest count (303) and 2024 the lowest (249), a difference of 54`, or
    `the counts were the same (<n>) for <labels>`; labels as the registry writes them."""
    if c["all_equal"]:
        return f"the counts were the same ({c['top_value']:,}) for {c['top_label']}"
    return (f"{c['top_label']} had the highest count ({c['top_value']:,}) and "
            f"{c['bottom_label']} the lowest ({c['bottom_value']:,}), a difference of "
            f"{c['difference']:,}")


def _age_phrase(group, wording):
    return "across all ages" if group is None else "for " + wording


def slot_phrases(result, registry=None):
    """What each fact slot of one result fills with: {"count": ..., "months": ...} or
    {"compare": ...}. The age wording is the registry's; without a registry, the wording the
    count result already holds (agent.py wrote it from the same registry)."""
    if "phrases" in result:  # a county result (S3A C6): its phrases, already floored
        return dict(result["phrases"])
    if result["kind"] == "compare":
        return {"compare": compare_phrase(result)}
    group = result["age_group"]
    wording = result["age"] if registry is None else age_wording(group, registry)
    records = "1 arrest record" if result["total"] == 1 else f"{result['total']:,} arrest records"
    return {"count": f"{records} {_age_phrase(group, wording)} in {result['year']}",
            "months": months_phrase(result["by_month"])}


def offered_slots(results=(), facts=None, registry=None):
    """Every fact slot a text may use, with its phrase: {"{r1.count}": ..., "{f1}": ...}."""
    slots = {f"{{{r['id']}.{name}}}": phrase for r in results
             for name, phrase in slot_phrases(r, registry).items()}
    slots.update({f"{{f{n}}}": line[:-1] if line.endswith(".") else line
                  for n, line in enumerate(facts or [], 1)})
    return slots


_SLOT = re.compile(r"\{[^{}]*\}")


def _fill(text, slots):
    """Each slot of `slots` replaced by its phrase, with a capital first letter when it is
    the first thing in the text or the first thing after a sentence end; anything else left
    as it is."""
    def phrase(match):
        if match[0] not in slots:
            return match[0]
        before = text[:match.start()]
        starts = before == "" or re.search(r"[.!?]\s+$", before) is not None
        found = slots[match[0]]
        return found[:1].upper() + found[1:] if starts else found
    return _SLOT.sub(phrase, text)


def fill(text, results, registry, facts=None):
    return _fill(text, offered_slots(results, facts, registry))


# ---- the one check for finding and about_data (R1) ------------------------------------------

_MARK = "\ue000"  # each {...} becomes one private-use character: no letters, its own place
_WORD = re.compile(r"[A-Za-z']+")
# C13 rule 2: the mark is not allowed in the model's own text (checked with the slots taken out).
_ALLOWED_CHARS = frozenset(string.ascii_letters + " '\u2019.,;:!?()-\u2013\u2014")
_AFTER_SLOT = frozenset(" .,;:!?")
_JOINS = (" and ", ", and ")  # C13 rule 1: all that may stand between two slots of a sentence
# {rN.months} and {rN.groups} name no period or filter: only straight after their own count.
_FOLLOWS_COUNT = re.compile(r"\{(r[0-9]+)\.(?:months|groups)\}")
_HELD = re.compile(r"\{(a[0-9]+)\.held\}")  # S3S S4


def _held_misplaced(text):
    """S4: `{aN.held}` must come in the same sentence as, or the sentence after, an odds slot
    of the same result."""
    where = [(i, name) for i, sentence in enumerate(_sentences(text))
             for name in _SLOT.findall(sentence)]
    for i, name in where:
        held = _HELD.fullmatch(name)
        if held and not any(j in (i, i - 1) and other.startswith(f"{{{held[1]}.odds.")
                            for j, other in where):
            return True
    return False


def _sentences(text):
    """A sentence ends at ., ! or ? followed by white space or the end of the text."""
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]


def check(text, slots, words, most_slots=None):
    """R1's check of a text against the fact slots it may use and the allowed words.
    Returns (failure codes, details): [] means it passes; details are the words and
    characters that failed (R6), for turn.json only."""
    text = text if isinstance(text, str) else ""
    found = list(_SLOT.finditer(text))
    names = [m[0] for m in found]
    outside = _SLOT.sub(_MARK, text)
    bad_chars = sorted({ch for ch in _SLOT.sub("", text) if ch not in _ALLOWED_CHARS})
    bad_words = [w for w in _WORD.findall(outside.replace("\u2019", "'"))
                 if w.lower() not in words]

    def months_alone(i, name):
        month = _FOLLOWS_COUNT.fullmatch(name)
        return month is not None and (i == 0 or names[i - 1] != f"{{{month[1]}.count}}")

    def glued(i, m):
        before = text[m.start() - 1] if m.start() else " "
        after = text[m.end()] if m.end() < len(text) else " "
        between = text[found[i - 1].end():m.start()] if i else None
        one_sentence = between is not None and not re.search(r"[.!?]\s", between)
        return before != " " or after not in _AFTER_SLOT or \
            (one_sentence and between not in _JOINS)

    codes = [code for code, failed in [
        ("SLOT", not names or len(set(names)) != len(names)
         or any(name not in slots or months_alone(i, name) for i, name in enumerate(names))
         or _held_misplaced(text)),
        ("GLUE", any(glued(i, m) for i, m in enumerate(found))),
        ("CHARS", bool(bad_chars)),
        ("WORD", bool(bad_words)),
        ("SHAPE", not text.strip() or len(_sentences(outside)) > statwords.odds_room(names)[0]
         or len(_fill(text, slots)) > statwords.odds_room(names)[1]  # S11 2i
         or (most_slots is not None and len(names) > most_slots)),
    ] if failed]
    return codes, {"words": bad_words, "chars": bad_chars}


def check_finding(text, results, words):
    """A finding offers the count and months slots of this turn's counts and the compare
    slot of its compares."""
    return check(text, offered_slots(results), words)[0]


def check_about(text, facts, words):
    """An about_data text offers {f1} to {fN}, at most four of them."""
    return check(text, offered_slots(facts=facts), words, most_slots=4)[0]


# ---- background (A7, unchanged by R7) -------------------------------------------------------

@lru_cache(maxsize=None)
def _pattern(entries):
    """Whole words or phrases, any letter case; an entry ending in * matches any word that
    starts with it."""
    parts = []
    for entry in (e.strip().lower() for e in entries):
        stem = entry[:-1] if entry.endswith("*") else entry
        if stem:
            parts.append(r"\s+".join(map(re.escape, stem.split()))
                         + (r"\w*" if entry.endswith("*") else ""))
    if not parts:
        return re.compile(r"(?!)")
    return re.compile(r"(?<!\w)(?:" + "|".join(parts) + r")(?!\w)", re.IGNORECASE)


def _has(rules, name, text):
    return _pattern(tuple(rules[name])).search(text) is not None


def check_background(text, rules):
    """A7's checks on general background: no number at all, hedged, no advice, nothing
    stated as certain."""
    text = text if isinstance(text, str) else ""
    lowered = text.lower()
    sentences = _sentences(text)
    return [code for code, failed in [
        ("SLOT", "{" in text or "}" in text),
        ("NUMBER", re.search(r"\d|%", text) is not None or _has(rules, "number_words", text)
         or _has(rules, "month_names", text)),
        ("ADVICE", _has(rules, "advice_words", text)),
        ("CERTAIN", _has(rules, "certain_words", text)),
        ("HEDGE", not _has(rules, "hedge_words", text)),
        ("SHAPE", not text.strip() or len(sentences) > 5 or len(text) > 700
         or "\n" in text or "\r" in text or "_" in text
         or any(mark.lower() in lowered for mark in rules["markup"])),
    ] if failed]


# ---- MOCO_TALK on: talk (T1), sentence by sentence (T2), REASON (T6) --------------------------
# Each check returns (codes, found): `found` is what failed, as the model wrote it, lower case
# (T3 gives at most five of them back to the model).

DEFAULT_TALK_RULES = REPO / "config" / "talk_rules.json"
_TALK_LETTERS = frozenset(string.ascii_letters + " ")  # T1 CHARS: ASCII letters, as R1
_LINE_BREAKS = "\n\r\v\f\x85\u2028\u2029"
_CODE_ORDER = ("SLOT", "GLUE", "CHARS", "WORD", "NUMBER", "LABEL", "CLAIM", "JUDGE", "ORDER",
               "SHAPE")  # R1's codes, then T2's
_TALK_ORDER = ("NUMBER", "LABEL", "CLAIM", "CHARS", "SHAPE")  # T1


def load_talk_rules(path=None):
    """The parsed config/talk_rules.json (the planning chat's)."""
    return json.loads(Path(DEFAULT_TALK_RULES if path is None else path).read_text(
        encoding="utf-8"))


def _hits(entries, text):
    """The entries `text` holds (whole words or phrases, any case; * as in _pattern), as
    written in it, lower case."""
    return [m[0].lower() for m in _pattern(tuple(entries)).finditer(text)]


def _number_hits(text, rules):
    """A digit or % (the word that holds it), a number word or a month name."""
    typed = [t.rstrip(".,;:!?") for t in re.findall(r"\S*[\d%]\S*", text.lower())]
    return typed + _hits(rules["number_words"] + rules["month_names"], text)


def _ordered(found, order=_CODE_ORDER):
    """The codes that found something, in `order`, and everything found."""
    codes = [code for code in order if found.get(code)]
    return codes, list(dict.fromkeys(f for code in codes for f in found[code] if f is not True))


def _talk_found(text, labels, in_finding):
    """What each code of the talk check finds in `text`: {code: [found, ...]}."""
    talk, rules = load_talk_rules(), load_rules()
    marks = set(talk["allowed_marks"])
    found = {"NUMBER": _number_hits(text, rules),
             "LABEL": _hits(labels, text),
             "CLAIM": _hits(talk["claim_phrases"], text),
             # ponytail: a digit or % is NUMBER only (the tests allow CHARS too), so the
             # model is told one thing about it and never sees a lone digit given back.
             "CHARS": [ch.lower() for ch in text if ch not in _TALK_LETTERS and ch not in marks
                       and not re.fullmatch(r"[\d%]", ch)]
             + [m.lower() for m in rules["markup"] if m.lower() in text.lower()]}
    if in_finding:  # T2: a talk sentence of a finding; the whole text's SHAPE is checked there
        found["JUDGE"] = _hits(talk["judgement_words"], text)
    else:
        found["SHAPE"] = [True] if (not text.strip()
                                    or len(_sentences(text)) > talk["most_talk_sentences_in_talk"]
                                    or len(text) > talk["most_chars_talk"]
                                    or any(ch in text for ch in _LINE_BREAKS)) else []
    return found


_TIDY = {0x2010: "-", 0x2011: "-", 0x00A0: " ", 0x2007: " ", 0x2009: " ", 0x202F: " "}
_TIDY_DROP = frozenset("*`\ufe0f\u200d")


def tidy(text):
    """T10: a finish text as it is checked, sent and saved. Odd hyphens and spaces become
    plain ones; *, the backtick and pictures (emoji) go; white space becomes one space."""
    if not isinstance(text, str):
        return text
    text = "".join(ch for ch in text.translate(_TIDY)
                   if ch not in _TIDY_DROP and unicodedata.category(ch) != "So"
                   and not 0x1F3FB <= ord(ch) <= 0x1F3FF)
    return re.sub(r"\s+", " ", text).strip()


_QUOTED = re.compile('"([^"]*)"|\u201c([^\u201d]*)\u201d')


def _words_of(text):
    return re.findall(r"[^\W_]+", text.lower())


ECHO_WORDS = 2  # C47: the most words of a quoted echo that is checked as "it"


def unquoted(text, question, labels=()):
    """C43 point 2 as C47 has it: a quoted stretch becomes the word "it" for T1's check when
    its words are words of the person's message, one after another as the message has them,
    it has at most ECHO_WORDS words, and it holds no number and no label of its own."""
    asked = _words_of(question if isinstance(question, str) else "")

    def check_as(m):
        stretch = m.group(1) if m.group(1) is not None else m.group(2)
        said = _words_of(stretch)
        n = len(said)
        echoed = 0 < n <= ECHO_WORDS and any(asked[i:i + n] == said
                                             for i in range(len(asked) - n + 1))
        if echoed:
            found = _talk_found(stretch, list(labels), True)
            echoed = not (found["NUMBER"] or found["LABEL"])
        return "it" if echoed else m.group(0)
    return _QUOTED.sub(check_as, text)


def cut_talk(text):
    """T14: the leading whole sentences of a talk text that fit both limits, or ""."""
    talk, kept = load_talk_rules(), []
    for sentence in _sentences(text):
        if len(kept) >= talk["most_talk_sentences_in_talk"] \
                or len(" ".join(kept + [sentence])) > talk["most_chars_talk"]:
            break
        kept.append(sentence)
    return " ".join(kept)


def talk_check(text, labels):
    """T1's check of a talk text. `labels`: the LABEL entries of the data mode."""
    return _ordered(_talk_found(tidy(text) if isinstance(text, str) else "", labels, False),
                    _TALK_ORDER)


OWN_CHARS = 400  # C38: the most characters of the model's own words in a county reply


def talk_finding_check(text, slots, words, labels, most_slots=None, own_words=False):
    """T2: a finding or about_data text with MOCO_TALK on. A sentence that holds a slot is a
    fact sentence and keeps R1 and C13; one that holds none is a talk sentence and gets the
    talk check with JUDGE. Returns (codes, details); details as check()'s, plus `found`.
    `own_words` (C38, county mode): SHAPE counts only the model's own words."""
    text = tidy(text) if isinstance(text, str) else ""
    talk = load_talk_rules()
    parts = _sentences(text)
    facts = [s for s in parts if _SLOT.search(s)]
    talks = [i for i, s in enumerate(parts) if not _SLOT.search(s)]
    names = _SLOT.findall(text)
    whole, _ = check(text, slots, words)                        # SLOT and GLUE as today
    in_facts, details = check(" ".join(facts), slots, words)    # CHARS and WORD as today
    found = {code: [] for code in _CODE_ORDER}
    if "SLOT" in whole:
        found["SLOT"] = [n.lower() for n in names if n not in slots or names.count(n) > 1] \
            or [True]
    if "GLUE" in whole:
        found["GLUE"] = [True]
    if "CHARS" in in_facts:
        found["CHARS"] = [ch.lower() for ch in details["chars"]]
    if "WORD" in in_facts:  # R1 reads a curly apostrophe as a straight one
        found["WORD"] = [w.lower() if w.lower() in text.lower() else w.lower().replace("'", "\u2019")
                         for w in details["words"]]
    for i in talks:
        for code, hits in _talk_found(parts[i], labels, True).items():
            found[code] += hits
    where = {}
    for i, sentence in enumerate(parts):
        for name in _SLOT.findall(sentence):
            where.setdefault(name, i)
    found["ORDER"] = [True for name, i in where.items()
                      if (m := _FOLLOWS_COUNT.fullmatch(name)) and f"{{{m[1]}.count}}" in where
                      and any(where[f"{{{m[1]}.count}}"] < t < i for t in talks)]
    most_facts, most_chars = statwords.odds_room(names)  # S11 2i
    if own_words:  # C38: how many slots, and how long once filled, no longer count
        found["SHAPE"] = [True] if (not text.strip()
                                    or len(talks) > talk["most_talk_sentences_in_finding"]
                                    or len(_SLOT.sub("", text)) > OWN_CHARS
                                    or re.search(r"[^\S ]", text)  # one line
                                    or len(names) != len(set(names))
                                    or (most_slots is not None and len(names) > most_slots)) \
            else []
        codes, hits = _ordered(found)
        return codes, dict(details, found=hits)
    found["SHAPE"] = [True] if (not text.strip() or len(facts) > most_facts
                                or len(talks) > talk["most_talk_sentences_in_finding"]
                                or len(_fill(text, slots)) > max(talk["most_chars_finding"],
                                                                 most_chars)
                                or re.search(r"[^\S ]", text)  # one line
                                or (most_slots is not None and len(names) > most_slots)) else []
    codes, hits = _ordered(found)
    return codes, dict(details, found=hits)


def reason_check(text):
    """T6: a background text says why (reason_phrases) and how to check (check_phrases)."""
    talk = load_talk_rules()
    text = text if isinstance(text, str) else ""
    return [] if _has(talk, "reason_phrases", text) and _has(talk, "check_phrases", text) \
        else ["REASON"]


def background_found(text, codes):
    """What failed today's background check, from the text (T3's `found`)."""
    rules, text = load_rules(), text if isinstance(text, str) else ""
    found = {"SLOT": [ch for ch in text if ch in "{}"], "NUMBER": _number_hits(text, rules),
             "ADVICE": _hits(rules["advice_words"], text),
             "CERTAIN": _hits(rules["certain_words"], text)}
    return list(dict.fromkeys(f for code in codes for f in found.get(code, [])))


# ---- the fixed rendering and details ------------------------------------------------------

def _sentence(phrase):
    return phrase[:1].upper() + phrase[1:] + "."


def months_sentence(values):
    """`April was the busiest month (50) and January and August the quietest (8 each).`"""
    return _sentence(months_phrase(values))


def compare_sentence(c):
    return _sentence(compare_phrase(c))


def _count_sentence(c, registry):
    phrase = _age_phrase(c["age_group"], age_wording(c["age_group"], registry))
    return f"In {c['year']} there were {c['total']:,} arrest records {phrase}."


def render_fixed(results, registry):
    """Line 1 written by Python alone, from the results."""
    counts = [r for r in results if r["kind"] == "count"]
    compares = [r for r in results if r["kind"] == "compare"]
    if len(counts) == 1 and not compares:
        return _count_sentence(counts[0], registry) + " " + months_sentence(counts[0]["by_month"])
    sentences = [] if compares and len(counts) > 2 else \
        [_count_sentence(c, registry) for c in counts]
    return " ".join(sentences + [compare_sentence(c) for c in compares])


def details_text(counts, compares, registry, limitations, run_ids):
    """A10. `counts`: [{"year", "age_group", "by_month", "total"}] in result order (at most
    four are shown); `compares`: compare dicts; the limitations of the first count's saved
    record."""
    lines = [DETAILS_HEAD]
    for c in counts[:4]:
        lines.append(f"Read as: arrest records per month in {c['year']}, "
                     f"{age_wording(c['age_group'], registry)}.")
        lines.append("By month: " + ", ".join(f"{abbr} {n:,}" for abbr, n in
                                              zip(MONTH_ABBREVIATIONS, c["by_month"]))
                     + f". Total {c['total']:,}.")
    lines += [f"Compared: {compare_sentence(c)}" for c in compares]
    lines.append(f"Data: {registry.dataset_id}, SYNTHETIC (made-up) test data, not real "
                 f"Montgomery County figures.")
    lines.append("Limits:")
    lines += [f"- {sentence}" for sentence in limitations]
    lines.append("Run ids: " + ", ".join(run_ids))
    return "\n".join(lines)


# ---- county mode (S3A C6, C8, C10, C11) ------------------------------------------------------
# Everything here is generated from the source files; nothing names SYNTHETIC data. `results`
# are county results (agent.py): counts carry their exact figures and floored phrases.

COURSE_LINE = "This agent is a university course project. It is not a county service."
FULL_TABLE = "The full table is in the details."
NEEDS_DETAILS = "Want the details, or a different breakdown?"


def _join_or(items):
    items = [str(item) for item in items]
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " or " + items[-1]


def _dimensions(source):
    words = [("age" if f["kind"] == "age" else f["dimension"]) for f in source["fields"]
             if f["kind"] in ("age", "category", "flag")]
    return words + ["year", "month", "day of the week", "hour"]


def _date_words(iso):
    return counting.day_text(date.fromisoformat(iso[:10]))


SHORT_FROM = 3  # C23: from this many sources on, "what I can do" is one short sentence


def county_can_ask_full(sources):
    """C11: the "what I can do" sentence, one per source, from the source files. With three
    or more sources only `about the data` uses it (C23)."""
    return " ".join(f"I can count {s['unit']['many']} from {s['title']} for any period its copy "
                    f"covers, filtered or broken down by {join_and(_dimensions(s))}, and compare "
                    f"those counts or give one as a share of another."
                    for s in sources.values())


def _source_names(sources):
    """C23: the sources by what they count, in file order."""
    return join_and([s["unit"]["many"] for s in sources.values()])


def county_can_ask(sources):
    """C11 and C23: the sentence that ends a refusal."""
    if len(sources) < SHORT_FROM:
        return county_can_ask_full(sources)
    return (f"I can count records from {len(sources)} county sources, filter them, break them "
            f"down, compare counts and give one as a share of another. Ask \"what data do you "
            f"have?\" for the list.")  # C57 point 1


def county_help(sources):
    """C11: `help` in county mode, from the source files."""
    first = next(iter(sources.values()), None)
    place = None if first is None else next(
        (f["dimension"] for f in first["fields"]
         if f["kind"] == "category" and not f.get("person")), "month")
    example = "" if first is None else (
        f' For example: "How many {first["unit"]["many"]} were there last year, by {place}?"')
    if len(sources) >= SHORT_FROM:  # C23
        return (f"I count records in county open data. I have {len(sources)} sources: "
                f"{_source_names(sources)}. Ask in your own words.{example} Then follow up, for "
                f"example \"and the year before?\". Ask \"what data do you have?\" for what each "
                f"source covers and how it can be broken down. I never show a single record. Say "
                f"\"details\" for the full breakdown of my last answer, or \"reset\" to make me "
                f"forget this conversation.")
    return (f"I count records in county open data. {county_can_ask(sources)} Ask in your own "
            f"words.{example} Then follow up, for example \"and the year before?\". I never "
            f"show a single record. Say \"details\" for the full breakdown of my last answer, or "
            f"\"reset\" to make me forget this conversation.")


def _covers(source, copy):
    return counting.covers_text(source, copy) if copy is not None else None


def ages_question(words):
    """C32: the question when the message names an age group in words and no ages."""
    return f'Which ages do you mean by "{words}"? Say a range of ages and I\'ll count it.'


def county_text(code, sources, copies, registry, limit=None, source_id=None, lead=None):
    """County mode's fixed rows: A7's table in county words, NO_COPY and the questions
    Python asks (C4, C5). `source_id` is the source a question about the period is asked
    for (C24)."""
    ask = county_can_ask(sources)
    floor = next(iter(sources.values()), {}).get("floor", 10)
    one = len(sources) >= SHORT_FROM and source_id in sources  # C24: name that source only
    covered = [f"{s['title']} covers {_covers(s, copies.get(sid))}"
               for sid, s in sources.items()
               if copies.get(sid) is not None and (not one or sid == source_id)]
    muddled = ["I couldn't make sense of what to count, so nothing was counted.", ask]
    rows = {
        "UNRECOGNIZED_QUESTION": ["I couldn't read that as a question I can answer.", ask],
        "UNSUPPORTED_METRIC": ["I can't answer that one: I only count records, so I have "
                               "nothing on convictions, sentencing, jail or causes.",
                               NOTED, ask],
        "UNSUPPORTED_FIELD": ["I can't break it down that way: no source I have records it.",
                              NOTED, ask],
        "REAL_DATA_NOT_AVAILABLE": ["I can only answer from the county open data listed here.",
                                    NOTED, ask],
        "OUT_OF_COVERAGE": ["I have no data for that period.", ask],
        "NOT_ALLOWED": ["I don't count a single year of age under 18; I can count ranges of two "
                        "years or more.", ask],
        "TOO_FINE": [f"That breakdown is too fine: more than half of its groups would be under "
                     f"{floor}.", ask],
        "NO_COPY": ["I don't have a saved copy of that source yet, so nothing was counted. "
                    "Whoever runs this agent needs to fetch it."],
        "NEEDS_source": (["Which source do you mean?",
                          f"I have {len(sources)}: {_source_names(sources)}."]  # C23, C41
                         if len(sources) >= SHORT_FROM else
                         [f"Which source do you mean: "
                          f"{_join_or(s['title'] for s in sources.values())}?"]),
        "NEEDS_period": ["Which period do you mean?"]
                        + ([f"{'; '.join(covered)}."] if covered else []),  # C41: split
        "NEEDS_other": ["Could you say a bit more about what you'd like?", ask],
        "BACKGROUND_OFF": ["That's a general question I can't back up with the data I have.",
                           ask],
        "ENGINE_MISSING": [statwords.ENGINE_MISSING_LINE],   # S3S S10 answer 10
        "ENGINE_FAILED": [statwords.ENGINE_FAILED_LINE],
        "TOO_LITTLE": ["There is too little data in that selection for that analysis.", ask],
    }
    if code in rows:
        row = list(rows[code])
        if lead and not (code == "NEEDS_source" and len(sources) < SHORT_FROM):  # C41 point 2
            row[0] = lead
            if code == "NEEDS_other":  # C43 point 3: his own question alone
                row = row[:1]
            elif "noted it as a request" in lead.replace("\u2019", "'").lower():
                row = [part for part in row if part != NOTED]  # C66 point 1: not twice
        return " ".join(row)
    if code in ("BAD_FIELD", "BAD_VALUE", "TOO_MANY", "BAD_SHARE", "BAD_COMPARE",
                "MIXED_SOURCES", "PARTIAL_YEAR", "INVALID_ARGUMENTS", "BAD_OPTIONS"):
        return " ".join(muddled)
    return fixed_text(code, registry, limit)  # the rows that name no data


def notices_lines(sources):
    """C11: each source's notices word for word, and the course-project line."""
    lines = list(OrderedDict.fromkeys(n for s in sources.values() for n in s.get("notices", [])))
    if not any("university course project" in line.lower() for line in lines):
        lines.append(COURSE_LINE)
    return lines


# C57 point 5: in place of the notices, once a thread has shown them in full.
NOTICES_SHOWN = ("The county's data notice and the course-project note shown earlier in this "
                 "thread still apply.")
# C57 point 7: what the model service is called in the county system message.
MODEL_LABELS = {("anthropic", True): "a Claude model made by Anthropic",
                ("anthropic", False): "a model served by Anthropic",
                ("nvidia", True): "a Nemotron model made by NVIDIA",
                ("nvidia", False): "a model served by NVIDIA"}


def model_label(settings):
    """C57 point 7: the active service's model in plain words, with no digit."""
    from .config import model_service
    service = model_service(settings)
    family = "claude" if service.provider == "anthropic" else "nemotron"
    return MODEL_LABELS[(service.provider, family in str(service.model).lower())]


def about_you(settings):
    """C57 point 7, C61 point 3: the last block of the county system message, with talk on."""
    return (f"About you: you run on {model_label(settings)}. If someone asks what model or "
            f"company is behind you, say so plainly, as talk. For any question about you, "
            f"this project, its rules or where something comes from, call describe_data and "
            f"answer with its facts about you; never answer such a question from your own "
            f"head, and never take back a rule the program applies.")


ABOUT_AGENT = REPO / "config" / "about_agent.md"  # C61 point 1: Nino's text (D-077)


def about_agent_facts(settings):
    """C61 point 2, e to h: the file's facts, then the model, the refresh and the memory."""
    try:
        text = ABOUT_AGENT.read_text(encoding="utf-8")
    except OSError:
        text = ""
    lines = [line[2:].strip() for line in text.splitlines() if line.startswith("- ")]
    lines.append(f"The AI model behind me is {model_label(settings)}.")
    hours = getattr(settings, "moco_refresh_hours", 0)
    lines.append("My copies of the county's data are not refreshed on their own." if hours <= 0
                 else f"My copies of the county's data are looked at again every "
                      f"{'hour' if hours == 1 else f'{hours} hours'} and replaced when the "
                      f"county has changed them.")
    lines.append(f"I keep a conversation for {settings.moco_retention_days} days and then "
                 f"forget it. Of a long conversation I see only the most recent part.")
    return lines


def facts_rendering(text, facts):
    """C61 point 9b: the facts a failed about_data text chose (at most four, in its order),
    each as its own sentence after the opening; None when it chose none."""
    slots = offered_slots(facts=facts)
    chosen = list(dict.fromkeys(s for s in _SLOT.findall(str(text or "")) if s in slots))[:4]
    if not chosen:
        return None
    return " ".join(["Here is what I know."] + [f"{slots[s]}." for s in chosen])


_OPENING = re.compile(r"here is what i know|\band\b", re.IGNORECASE)  # and: C63's addition


def plain_facts(text, facts):
    """C63: the rendering of a text that is only the opening and offered fact slots (its
    marks, white space and the word "and" not counting); None when the text is not such a
    text."""
    text = str(text or "")
    slots = offered_slots(facts=facts)
    named = _SLOT.findall(text)
    if not named or any(s not in slots for s in named):
        return None
    if any(ch.isalnum() for ch in _OPENING.sub(" ", _SLOT.sub(" ", text))):
        return None
    return facts_rendering(text, facts)


_MAKERS = re.compile(r"\b(anthropic|claude|nvidia|nemotron)\b", re.IGNORECASE)
# C62 point 2: the fixed refusal's first sentence, and what replaces it when the thread's
# earlier figures are the reason.
SINGLE_AGE = "I don't count a single year of age under 18; I can count ranges of two years or more."
EARLIER_FIGURES = ("With the figures already given in this conversation, that count would give "
                   "one single year of age under 18, so I don't give it.")


def maker_words(text, label):
    """C62 point 1: the maker's and the model's names in a talk text outside the label of
    the turn's own model, as written; [] when there are none. The label is the label too
    with a capital first letter (C62's answer after check 12)."""
    text = str(text or "")
    for form in (label, label[:1].upper() + label[1:]):
        text = text.replace(form, " ")
    return _MAKERS.findall(text)


# C64 point 1: what replaces a county talk text that wrote a figure itself.
NUMBER_IN_TALK = ("I only give a figure by counting it, so I do not repeat, change or work on one "
                  "in plain talk. My counts come from my saved copy of the county's data, and I "
                  "cannot check them against any other source. Ask me to count it again, or say "
                  "\"details\" after a count to see how it was counted.")
# C64 point 3: a count or a comparison of the turn that was not made, said in the reply.
HELD_BACK_LINE = ("(One count asked for here is not given: with the other figures it would give "
                  "one single year of age under 18.)")
MIXED_SOURCES_LINE = "(Counts of different sources are never compared with each other.)"


def too_many_line(most):
    return (f"(I make at most {most} counts in one message, so not everything asked for is "
            f"here. Ask for the rest in a new message.)")


def county_talk_fallback(sources, failures=()):
    """C61 point 9: what replaces a talk text that failed its checks, in county mode.
    C64 point 1: its own line when the text wrote a figure."""
    if "NUMBER" in failures:
        return NUMBER_IN_TALK
    return f"I can't put that in words I can back up. {county_can_ask(sources)}"


def sent_text(text, sources):
    """C61 point 4: the reply as sent, without the notices and C56's note, cut to 600
    characters at a word's end."""
    drop = {*notices_lines(sources), NOTICES_SHOWN, BACKUP_NOTE}
    kept = "\n".join(line for line in str(text or "").split("\n") if line not in drop)
    if len(kept) <= 600:
        return kept
    head = kept[:600]
    if kept[600] not in " \n":  # inside a word: back to the end of the word before
        head = head[:max(head.rfind(" "), head.rfind("\n"), 0)] or head
    return head + " ..."


def all_sources_fact(sources):
    """C57 point 3a: one fact naming every source by what it counts (C39's join)."""
    n = len(sources)
    return (f"I work with {'one source' if n == 1 else f'{n} sources'} of Montgomery County "
            f"open data: {_source_names(sources)}.")


def added_facts(sources):
    """C57 point 3, a to d: after every fact of before C57, so their slot numbers stay."""
    if not sources:
        return []
    lines = [all_sources_fact(sources)]
    lines += OrderedDict.fromkeys(n for s in sources.values() for n in s.get("notes", []))
    lines += [f"In {s['title']}, {f.get('dimension', f['name'])} is {f['meaning']}."
              for s in sources.values() for f in s["fields"] if f.get("meaning")]
    lines += OrderedDict.fromkeys(n for s in sources.values() for f in s["fields"]
                                  for n in f.get("notes", []))
    return lines


def county_facts(sources, copies, settings=None):
    """C11: describe_data's fact lines, generated from the source files: no record, no
    count from the data. C61: with a turn's settings, the facts about the agent follow."""
    lines = []
    for sid, s in sources.items():
        title, many, floor = s["title"], s["unit"]["many"], s["floor"]
        copy = copies.get(sid)
        age = next((f for f in s["fields"] if f["kind"] == "age"), None)
        lines += [
            f"{title} is published by {s['publisher']}. One record is "
            f"{s.get('row_meaning', 'one ' + s['unit']['one'])}, and I count {many}, not people.",
            f"My copy of {title} covers {_covers(s, copy)} and was saved on "
            f"{counting.day_text(copy.day)}." if copy is not None else
            f"I have no copy of {title} yet, so it cannot be counted.",
            f"{title} can be filtered or broken down by {join_and(_dimensions(s))}.",
            f"A count of {title} is of {many}. It is not {_join_or(s['is_not'])}.",
            f"Counts under {floor} are shown as fewer than {floor}. That is about what I say, "
            f"not a secret: the county's open data has every record.",
            f"A record with no value for a field a question uses"
            + (f", or an age outside {age['usable'][0]} to {age['usable'][1]}," if age else "")
            + " is left out of that count, and I say how many were left out.",
            f"Nothing else can be asked of {title}: no names, no addresses, and never a single "
            f"record.",
        ]
        grouped = [f["dimension"] for f in s["fields"] if f.get("interpreted")]
        if grouped:  # C14
            lines.append(f"In {title}, {join_and(grouped)} {'is' if len(grouped) == 1 else 'are'} "
                         f"grouped by the agent from free text. {s['interpreted_line']}")
    return lines + added_facts(sources) + (about_agent_facts(settings) if settings is not None
                                           else [])


def interpreted_lines(sources):
    """C14, about the data: the heading, one line per interpreted field, then each
    source's line. [] when no loaded source has such a field."""
    lines = []
    for s in sources.values():
        fields = [f for f in s["fields"] if f.get("interpreted")]
        if fields:
            lines += [f"{f['dimension']}: {f['coverage']}" for f in fields]
            lines.append(s["interpreted_line"])
    return ["Grouped by the agent from free text:"] + lines if lines else []


def county_about_text(sources, copies):
    """The fixed ABOUT reply in county mode; C39: short with three or more sources."""
    if len(sources) >= SHORT_FROM:
        return (f"I work with {len(sources)} sources of Montgomery County open data: "
                f"{_source_names(sources)}. I count records, not people, and I never show a "
                f"single record. Ask about any one of them for its dates and what it can be "
                f"broken down by.")
    have = "; ".join(f"{s['title']}, " + (f"covering {_covers(s, copies.get(sid))}"
                                          if copies.get(sid) else "with no copy yet")
                     for sid, s in sources.items())
    text = (f"I work with county open data: {have}. I count records, not people, and I never "
            f"show a single record. {county_can_ask_full(sources)}")  # C23: stays the full list
    return "\n".join([text] + interpreted_lines(sources))


def _cap(phrase):
    return phrase[:1].upper() + phrase[1:]


def county_fixed(results):
    """C10's fixed rendering: `I counted <count phrase>.` and ` <Groups phrase>.` per count,
    then the share and compare phrases as sentences."""
    counts = [r for r in results if r["kind"] == "count"]
    others = [r for r in results if r["kind"] != "count"]
    sentences = []
    for r in counts:
        sentences.append(f"I counted {r['phrases']['count']}.")
        if "groups" in r["phrases"]:
            sentences.append(_cap(r["phrases"]["groups"]) + ".")
    for r in others:  # S3S S4: an analysis's phrases, each as its own sentence
        if r["kind"] != "analysis":
            sentences.append(_cap(r["phrases"][r["kind"]]) + ".")
            continue
        for name, phrase in r["phrases"].items():
            if name == "held" and sentences:  # S11 2d: joined to the last odds sentence
                sentences[-1] = f"{sentences[-1][:-1]}, {phrase}."
            else:
                sentences.append(_cap(phrase) + ".")
    return " ".join(sentences)


def _left_out_lines(r, source, named=False):
    """C10 step 3. `named` (C19, a reply with more than one count): each line starts with
    `For <read_as>: ` and has no brackets."""
    fields = {f["name"]: f for f in source["fields"]}
    lines = []
    for name, n in r["left_out"].items():
        if not n:
            continue
        shown = counting.shown(n, r["floor"])
        f = fields.get(name, {})
        text = (f"{shown} had no usable age and are not included." if f.get("kind") == "age"
                else f"{shown} had no {f.get('dimension', name)} recorded and are not "
                     f"included.")
        lines.append(f"For {r['read_as']}: {text}" if named else f"({text})")
    return lines


def _left_out_texts(r, source):
    """C10 step 3: the left-out texts of a count, for every field that left records out,
    whether it is filtered on or broken down by (C49 withdraws C42 point 1)."""
    fields = {f["name"]: f for f in source["fields"]}
    out = []
    for name, n in r["left_out"].items():
        if not n:
            continue
        shown = counting.shown(n, r["floor"])
        f = fields.get(name, {})
        out.append(f"{shown} had no usable age and are not included." if f.get("kind") == "age"
                   else f"{shown} had no {f.get('dimension', name)} recorded and are not "
                        f"included.")
    return out


def _hidden_group(r):
    values = [g[-1] for g in (r["groups"] or r["grid"] or [])]
    return any(counting.is_hidden(n, r["floor"]) for n in values)


def _sensitive(r, source):
    fields = {f["name"]: f for f in source["fields"]}
    used = [flt["field"] for flt in r["spec"]["filters"]] + r["spec"]["group_by"]
    return any(fields.get(name, {}).get("sensitive") for name in used)


def _interpreted(r, source):
    """C14: the count filters or breaks down by a field the county wrote as free text."""
    fields = {f["name"]: f for f in source["fields"]}
    used = [flt["field"] for flt in r["spec"]["filters"]] + r["spec"]["group_by"]
    return any(fields.get(name, {}).get("interpreted") for name in used)


WIDENED_LINE = ("(I don't count a single year of age under 18, so I counted a wider "
                "range.)")  # C28


def cause_line(many):
    """C10's sensitive line; the count chart's foot uses it too (C40 amendment 2, point b)."""
    return f"These are counts of {many}, not rates, and they show no cause."


def counts_cause_line(counts, sources):
    """The sensitive line of a turn made of counts alone, from its first count that carries
    it, as county_answer writes it; None when no count does (C40 amendment 2, point b)."""
    sensitive = [r for r in counts if _sensitive(r, sources[r["source"]])]
    return cause_line(sources[sensitive[0]["source"]]["unit"]["many"]) if sensitive else None


def county_answer(line1, results, sources, *, kept=(), first, widened=False, not_made=()):
    """C10: line 1, then the table, the kept note, left out, the hidden line, the sensitive
    line and the source line, each on its own line. S3S S5 adds, for statistical results:
    their tables with the others, then after the hidden line the fit line, the
    before-and-after line, what was used and left out and the association line; the source
    line of a first answer then ends by offering the R script."""
    counts = [r for r in results if r["kind"] == "count"]
    analyses = [r for r in results if r["kind"] == "analysis"]
    lines, full = [line1], False
    for r in counts:
        if r["groups"] is not None and len(r["groups"]) <= 12:
            lines += [f"{label}: {counting.shown(n, r['floor'])}" for label, n in r["groups"]]
        elif r["groups"] is not None or r["grid"] is not None:
            full = True
    for r in analyses:  # S5.1: at most 12 lines, else in details
        if len(r["table"]) <= 12:
            lines += r["table"]
        else:
            full = True
        if r["stat"] == "rate" and rates.not_shown_line(r["rate"]):  # S2 R10 point 4
            lines.append(rates.not_shown_line(r["rate"]))
    if full:
        lines.append(FULL_TABLE)
    if kept:
        lines.append(f"(I kept {join_and(kept)} from earlier.)")
    if widened:
        lines.append(WIDENED_LINE)
    lines += list(not_made)  # C64 point 3
    used = list(OrderedDict.fromkeys(r["source"] for r in counts + analyses))
    left = [(r, _left_out_texts(r, sources[r["source"]])) for r in counts]  # C42 point 1
    times = Counter(t for _, texts in left for t in texts)
    hides = any(_hidden_group(r) for r in counts)
    several = len(counts) + len(analyses) > 1
    named = several and (hides or any(times[t] == 1 for _, texts in left for t in texts))  # C19
    said = set()
    for r, texts in left:
        for t in texts:
            if times[t] > 1:  # C42 point 2: the same text of several counts, once, unnamed
                if t not in said:
                    lines.append(f"({t})")
                    said.add(t)
            else:
                lines.append(f"For {r['read_as']}: {t}" if named else f"({t})")
    for sid in used:
        if any(_hidden_group(r) for r in counts if r["source"] == sid) or \
                any(statwords.hides(r) for r in analyses if r["source"] == sid):  # S11 2b
            floor = sources[sid]["floor"]
            lines.append(f"Counts under {floor} are not shown here; the county's open data has "
                         f"every record: {sources[sid]['page']}.")
    for r in analyses:  # S5.2
        if r["fit_line"]:
            lines.append(f"For {r['read_as']}: {r['fit_line'][:1].lower()}{r['fit_line'][1:]}"
                         if several else r["fit_line"])
    if any(r["stat"] == "before_after" for r in analyses):  # S5.3
        lines.append(statwords.BEFORE_AFTER_LINE)
    for r in analyses:  # S5.4
        lines.append(rates.used_line(r, named=several) if r["stat"] == "rate" else
                     statwords.used_line(r, sources[r["source"]], named=several))
    rated = [r for r in analyses if r["stat"] == "rate"]
    if rated:  # S2 R10 point 5: R0's line; R5's when a margin is shown; R3's for race_ethnicity
        lines.append(rates.R0_LINE)
        if any(rates.margin_shown(r) for r in rated):
            lines.append(rates.R5_LINE)
        if any(r["rate"]["by"] == "race_ethnicity" for r in rated):
            lines.append(rates.R3_LINE)
    sensitive = [] if rated else [r for r in counts if _sensitive(r, sources[r["source"]])] + \
        [r for r in analyses if r["sensitive"]]  # S2: a rate answer never says "not rates"
    many = sources[sensitive[0]["source"]]["unit"]["many"] if sensitive else None
    # S11 2f: one line about cause when both would say it of the same records
    both = bool(analyses) and many == analyses[0]["unit"]["many"]
    if analyses:  # S5.5, always
        lines.append(statwords.association_line(analyses[0]["unit"]["many"], sensitive=both))
    if sensitive and not both:
        lines.append(cause_line(many))
    for sid in used:  # C14: once per source, after the sensitive line (S5.6a)
        if any(_interpreted(r, sources[sid]) for r in counts if r["source"] == sid) or \
                any(r["interpreted"] for r in analyses if r["source"] == sid):
            lines.append(sources[sid]["interpreted_line"])
    copy_of = {r["source"]: _date_words(r["copy"]["date"]) for r in counts + analyses}
    # S2 R10 point 5: a source with a rate names the Census too (its newest copy asked)
    also = {r["source"]: rates.census_part(r) for r in sorted(
        rated, key=lambda r: r["rate"]["census_date"])}
    if first:
        lines.append(" ".join(f"Source: {sources[sid]['title']} (county open data), copy of "
                              f"{copy_of[sid]}{also.get(sid, '')}. A count is of "
                              f"{sources[sid]['unit']['many']}, not people." for sid in used)
                     + " " + (statwords.FIRST_ENDING if analyses else NEEDS_DETAILS))
    else:
        lines += [f"({sources[sid]['title']}, county open data, copy of {copy_of[sid]}"
                  f"{also.get(sid, '')}.)" for sid in used]  # C18: the later line names its source
    return "\n".join(lines)


def county_details(counts, extras, sources, limitations, run_ids, analyses=(), short=False):
    """A10 in county mode: totals and tables as shown (C8), never a record; the notices and
    the course-project line (C11). `extras`: share and compare sentences. `analyses`: S7,
    each statistical result's full table, model, result and what was used."""
    lines = [DETAILS_HEAD]
    for r in counts[:4]:
        by = " and ".join(r["dimensions"])
        floor = r["floor"]
        lines.append(f"Read as: {r['read_as']}" + (f", by {by}" if by else "") + ".")
        lines.append(f"Total: {counting.shown(r['total'], floor)}.")
        if r["groups"] is not None:
            lines.append(f"By {by}:")
            lines += [f"{label}: {counting.shown(n, floor)}" for label, n in r["groups"]]
        if r["grid"] is not None:
            lines.append(f"By {by}:")
            lines += [f"{a}, {b}: {counting.shown(n, floor)}" for a, b, n in r["grid"]]
        lines += _left_out_lines(r, sources[r["source"]])
    lines += extras
    for r in analyses:
        lines += (rates.details_lines(r, sources[r["source"]]) if r["stat"] == "rate"
                  else statwords.details_lines(r, sources[r["source"]]))
    used = OrderedDict((r["source"], r["copy"]) for r in list(counts) + list(analyses))
    for sid, copy in used.items():
        s = sources[sid]
        lines.append(f"Data: {s['title']} (county open data), copy of {_date_words(copy['date'])}, "
                     f"fingerprint {copy['sha256'][:12]}. Every record: {s['page']}")
    lines.append("Limits:")
    lines += [f"- {sentence}" for sentence in limitations]
    lines += [NOTICES_SHOWN] if short else notices_lines({sid: sources[sid] for sid in used})
    lines.append("Run ids: " + ", ".join(run_ids))
    return "\n".join(lines)
