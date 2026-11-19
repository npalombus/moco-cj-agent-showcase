"""The guard: Python screens the question before the model sees it (design P1A, A2).

It applies stage 1's first four refusal rules, in stage 1's order, through stage 1's own
function (router.screen), so the patterns live in one place. Rule 1 (an instruction to
ignore the rules, or to state a figure) refuses the turn with no model call. Rules 2 to 4
(real figures, a measure other than a count, a field the data lacks) restrict it: the model
is called, so it can explain, but the counting tools are not offered.
"""
import re
from dataclasses import dataclass

from .router import screen as _stage1_screen

REFUSE_CODE = "UNRECOGNIZED_QUESTION"


@dataclass(frozen=True)
class GuardResult:
    refuse: str | None
    restricted: str | None


def screen(question):
    hit = _stage1_screen(question.lower()) if isinstance(question, str) else None
    if hit is None:
        return GuardResult(refuse=None, restricted=None)
    if hit[0] == REFUSE_CODE:
        return GuardResult(refuse=REFUSE_CODE, restricted=None)
    return GuardResult(refuse=None, restricted=hit[0])


# C29: what happens after an arrest. No county source records it, so in county mode a
# question that names it is answered by the fixed row, not by a count of something else.
_OUTCOME = re.compile(
    r"\b(convict\w*|prosecut\w*|sentenc\w*|jail\w*|incarcerat\w*|imprison\w*|prisons?"
    r"|recidiv\w*|acquit\w*|guilty|parole\w*|probation)\b", re.IGNORECASE)


def asks_outcome(question):
    return bool(_OUTCOME.search(question))


def outcome_word(question):
    """C36 point 2: the first word of C29's list in the question, as the question has it."""
    m = _OUTCOME.search(question) if isinstance(question, str) else None
    return m.group(0) if m else None


# C30: a question about who a person was. No county source holds a name.
_WHO = re.compile(r"\bwho\s+(was|were|got|has been|have been)\s+(arrested|cited|stopped|"
                  r"searched|charged|detained|picked up)\b", re.IGNORECASE)  # C53: no "names of"


def asks_who(question):
    return bool(_WHO.search(question))

