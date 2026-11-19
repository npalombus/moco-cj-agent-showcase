"""DETERMINISTIC_RULES_V0: the fixed rules that read a question (design sections 8 and 9).

No AI model. Plain patterns on the lower-cased text, checked in the section 8 order:

1. an instruction to ignore the rules or to state a figure -> UNRECOGNIZED_QUESTION
2. real, actual or official figures                       -> REAL_DATA_NOT_AVAILABLE
3. a measure other than an arrest count                   -> UNSUPPORTED_METRIC
4. a breakdown or filter the data does not have           -> UNSUPPORTED_FIELD
5. (OUT_OF_COVERAGE needs the data, so execute_call decides it)
6. anything the rules cannot read as the one question     -> UNRECOGNIZED_QUESTION

Step 6 is strict on purpose: after the year and the age wording are taken out, every word
left must be on a short list of plain question words, and every other character must be
ordinary punctuation. Anything else (a place or person's name, a month name, a number, a
symbol such as %) is refused rather than silently ignored, so the rules never answer a
narrower or different question with the whole year's count.
"""
import re
from dataclasses import dataclass

ROUTER = "DETERMINISTIC_RULES_V0"
SKILL = "arrest_count_trend"

# 1. Telling the system to ignore its rules, or to state a figure.
# ponytail: fixed word lists; a reworded instruction falls through to step 6, which
# still refuses it as long as it uses any word outside VOCAB.
_IGNORE = re.compile(r"\b(ignore|disregard|forget|override|bypass|pretend|claim)\b")
_STATE_VERB = r"\b(say|report|state|write|announce|declare|assert|confirm|tell\s+\w+)\b"
_STATE_THAT = re.compile(_STATE_VERB + r"\s+that\b")
_STATE = re.compile(_STATE_VERB)
_FIGURE_CLAIM = re.compile(  # "fell 50", "rose to 900", "was 900", "is 90"
    r"\b(is|are|was|were|be|fell|rose|dropped|declined|increased|decreased|doubled|tripled"
    r"|halved|grew|reached|hit|totall?ed)\s+(?:to\s+|by\s+)?\d")

# 2. Real, actual or official figures.
_REAL = re.compile(
    r"\b(real|actual|actually|official|officially|true|genuine|verified|authentic)\b")

# 3. Measures other than a count of arrest records (% is a rate too).
_METRIC = re.compile(
    r"\b(convict\w*|prosecut\w*|sentenc\w*|jail\w*|incarcerat\w*|imprison\w*|prisons?"
    r"|recidiv\w*|rates?|percent\w*|proportions?|ratios?|per\s+capita"
    r"|per\s+(?:person|people|residents?|population|\d[\d,]*))\b|%")

# 4. Fields the data does not have: race, ethnicity, gender, offense, place, a person.
# ponytail: word lists only. A town or person's name cannot be told apart from any other
# unknown word, so step 6 refuses it as UNRECOGNIZED_QUESTION, not UNSUPPORTED_FIELD.
_FIELD = re.compile(
    r"\b(rac(e|es|ial)|ethnic\w*|hispanic|latin[aox]s?|black|white|asian|gender\w*|sex"
    r"|(fe)?males?|men|women|boys?|girls?|offen[cs]e\w*|crimes?|charges?|drugs?|dui|dwi"
    r"|theft|assaults?|burglar\w*|robber\w*|homicides?|murders?|violent|weapons?"
    r"|location\w*|places?|district\w*|neighbou?rhoods?|city|cities|town\w*|zip|precincts?"
    r"|address\w*|streets?|areas?|regions?|where|named|mr|mrs|ms|dr|suspects?|defendants?"
    r"|person)\b")

# Section 9: the only age wording the rules read (any letter case).
_AGE_WORDING = (
    (re.compile(r"\bunder[\s-]*18\b"), "under_18"),
    (re.compile(r"\bjuveniles?\b"), "under_18"),
    (re.compile(r"\b18\s*(?:to|[-–])\s*25\b"), "18_25"),
    (re.compile(r"\byoung\s+adults?\b"), "18_25"),
    (re.compile(r"\b26\s*(?:to|[-–])\s*40\b"), "26_40"),
    (re.compile(r"\b41(?:\s*\+|\s+and\s+over\b)"), "41_plus"),
    (re.compile(r"\bover\s+40\b"), "41_plus"),
)
_ALL_AGES = re.compile(r"\ball\s+(?:ages|age\s+groups)\b")  # the same as no age wording
# Any other age range or age word (checked after the four groups' wording is taken out).
_OTHER_AGE = re.compile(
    r"\bages?\s*\d+|\d+\s*(?:to|through|[-–])\s*\d+"
    r"|\b(?:under|over|below|above|younger\s+than|older\s+than)\s+\d+|\d+\s*\+"
    r"|\d+\s+(?:and|or)\s+(?:over|older|above|up|under|younger|below)\b"
    r"|\d+\s*-?\s*years?\s*-?\s*olds?"
    r"|\b(?:teen\w*|minors?|child\w*|kids?|youths?|young|seniors?|elderly|adults?|old|older"
    r"|younger)\b")
_AGE_MENTION = re.compile(r"\b(age|ages|aged|group|groups)\b")
_COUNT_OF_PEOPLE = re.compile(r"\b(how\s+many|number\s+of|count\s+of)\s+(people|persons)\b")

_ARREST = re.compile(r"\barrest(s|ed)?\b")
_YEAR = re.compile(r"\b\d{4}\b")
_ODD_CHARACTER = re.compile(r"[^\w\s.,?!'\"‘’“”:;()\-–—]")

# Step 6: the plain words a supported question may use besides the year and age wording.
VOCAB = frozenset("""
    a an the of in for during each every per by from all and to on among with
    how many much what was were is are be been there s that which
    show me give list tell display get see find plot chart graph draw please
    can could would you i want need like know did do does have has had
    monthly month months year calendar
    arrest arrests arrested
    number numbers count counts counted total totals trend trends
    record records recorded made happened occurred
    people age ages aged group groups
""".split())


@dataclass
class Route:
    """What the rules decided: a refusal (reason_code set) or a call to make."""
    reason_code: str | None
    why: str
    skill: str | None = None
    arguments: dict | None = None


def _refuse(code, why):
    return Route(reason_code=code, why=why)


def screen(text):
    """Steps 1 to 4 on lower-cased text: (reason code, why), or None when none applies.
    The stage 2 guard (guard.py) calls this too, so these patterns live in one place."""
    m = (_IGNORE.search(text) or _STATE_THAT.search(text)
         or (_STATE.search(text) and _FIGURE_CLAIM.search(_YEAR.sub(" ", text))))
    if m:
        return ("UNRECOGNIZED_QUESTION",
                f"the question tells the system to ignore its rules or to state "
                f"a figure (matched {m.group(0)!r})")
    if m := _REAL.search(text):
        return ("REAL_DATA_NOT_AVAILABLE",
                f"the question asks for real, actual or official figures "
                f"(matched {m.group(0)!r}); only SYNTHETIC data is loaded")
    if m := _METRIC.search(text):
        return ("UNSUPPORTED_METRIC",
                f"the question asks for a measure other than a count of arrest "
                f"records (matched {m.group(0)!r})")
    if m := _FIELD.search(text):
        return ("UNSUPPORTED_FIELD",
                f"the question asks for a field the data does not have "
                f"(matched {m.group(0)!r})")
    return None


def route(question):
    """Read the question with the fixed rules. Never raises."""
    text = question.lower() if isinstance(question, str) else ""

    if hit := screen(text):
        return _refuse(*hit)

    years = sorted({int(y) for y in _YEAR.findall(text)})
    rest = _YEAR.sub(" ", text)
    groups = set()
    for pattern, group in _AGE_WORDING:
        if pattern.search(rest):
            groups.add(group)
            rest = pattern.sub(" ", rest)
    rest = _ALL_AGES.sub(" ", rest)
    if m := _OTHER_AGE.search(rest):
        return _refuse("UNSUPPORTED_FIELD",
                       f"the question names an age range that is not one of the four age "
                       f"groups (matched {m.group(0)!r})")

    if not _ARREST.search(text):
        return _refuse("UNRECOGNIZED_QUESTION", "the question does not mention arrests")
    if len(years) != 1:
        return _refuse("UNRECOGNIZED_QUESTION",
                       f"the question must name exactly one four-digit year; it names "
                       f"{len(years)}")
    if len(groups) > 1:
        return _refuse("UNRECOGNIZED_QUESTION",
                       "the question names more than one age group; one call counts one")
    if not groups and _AGE_MENTION.search(rest):
        return _refuse("UNRECOGNIZED_QUESTION",
                       "the question mentions age but names none of the four age groups "
                       "(a breakdown by age group is not the approved question)")
    if _COUNT_OF_PEOPLE.search(text):
        return _refuse("UNRECOGNIZED_QUESTION",
                       "the question asks how many people; the data counts arrest records, "
                       "not people")
    if odd := sorted(set(_ODD_CHARACTER.findall(rest))):
        return _refuse("UNRECOGNIZED_QUESTION",
                       f"the rules cannot read these characters: {ascii(''.join(odd))}")
    unknown = sorted({w for w in re.findall(r"\w+", rest) if w not in VOCAB})
    if unknown:
        return _refuse("UNRECOGNIZED_QUESTION",
                       f"the rules cannot read these words: {ascii(', '.join(unknown))}")

    return Route(reason_code=None, why="read as the approved question", skill=SKILL,
                 arguments={"year": years[0], "age_group": groups.pop() if groups else None})


def read_age_group(text):
    """Stage 2 (design P1A, A2): the one age group whose fixed wording (section 9) appears
    in the text, "all" for "all ages", else None; two different groups give None. It reads
    with the same patterns as route() and changes nothing route() returns."""
    if not isinstance(text, str):
        return None
    rest = _YEAR.sub(" ", text.lower())
    groups = {group for pattern, group in _AGE_WORDING if pattern.search(rest)}
    if len(groups) == 1:
        return groups.pop()
    if not groups and _ALL_AGES.search(rest):
        return "all"
    return None
