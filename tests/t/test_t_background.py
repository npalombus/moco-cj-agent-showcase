"""T6 of docs/T-DESIGN.md (D-049), and T7's last point: with MOCO_TALK on, a background text
must also pass REASON: at least one phrase of reason_phrases (why the possibility is
plausible) and at least one of check_phrases (what records would be needed to check it),
both in config/talk_rules.json. Still governed by MOCO_BACKGROUND, and all of today's
checks stay.

What this file covers
- Texts with reasoning and a way to check pass: EXPLAINED, kind background, style agent,
  with today's fixed words before and after (A7). Several phrases of each list, any case.
- A text without the reasoning, without the way to check, or without both fails REASON
  (exactly, and once); the REWRITE answer's hint is REASON's.
- Today's checks stay: NUMBER, ADVICE, CERTAIN and HEDGE on texts that do have the
  reasoning and the way to check.
- The second try: a passing second text is sent; a failing one gives the fixed refusal.
- MOCO_BACKGROUND off: the fixed refusal, with or without talk, and no second try.
- MOCO_TALK unset or off: the background check is exactly today's (a text with no
  reasoning passes; a failing text falls back at once).

Each text's premise is checked against the lists of config/reply_rules.json (today's
background check) and config/talk_rules.json (REASON). The status of the fixed refusal
after a failed text is UNSUPPORTED or EXPLAINED, as test_p1_replies.py accepts it.
"""
import pytest

from p1support import (BACKGROUND_PREFIX, BACKGROUND_SUFFIX, Env, Step, assert_fixed, finish,
                       make_settings, reply_rules)
from tsupport import (BACKGROUND_CODES, HINTS, check_cases, county_talk_env, first_try,
                      listed_in, talk_env, talk_rules, thread)

Q = "Why might arrests rise in summer?"
GOOD = [
    ("Arrests may rise in summer because people spend more time outdoors. To check it, you "
     "would need records of arrests by season and by place."),
    ("Counts might differ between places since police record arrests in different ways. You "
     "would look at records on how each place records an arrest."),
    ("One explanation could be the weather. The idea is that people spend more time outside "
     "when it is warm. It could be tested with data on arrests by season."),
    ("Arrests may vary by season BECAUSE of school holidays. TO TEST it, records of arrests "
     "by week would show it."),
]
NO_REASON = ("Arrests may rise in summer. To check it, you would need records of arrests by "
             "season and by place.")
NO_CHECK = "Arrests may rise in summer because people spend more time outdoors."
NEITHER = "Arrests may rise in summer, and it depends on the place."


def today_faults(text):
    """Premise: the codes today's background check (A7) gives on the plain reading of
    reply_rules.json's lists (SLOT and SHAPE are not used by these texts)."""
    rules = reply_rules()
    codes = set()
    if any(ch.isdigit() for ch in text) or "%" in text or \
            listed_in(rules["number_words"] + rules["month_names"], text):
        codes.add("NUMBER")
    if listed_in(rules["advice_words"], text):
        codes.add("ADVICE")
    if listed_in(rules["certain_words"], text):
        codes.add("CERTAIN")
    if not listed_in(rules["hedge_words"], text):
        codes.add("HEDGE")
    return codes


def reason_faults(text):
    rules = talk_rules()
    ok = listed_in(rules["reason_phrases"], text) and listed_in(rules["check_phrases"], text)
    return set() if ok else {"REASON"}


def premise(text, today, reason):
    assert today_faults(text) == set(today), (text, today_faults(text))
    assert reason_faults(text) == set(reason), (text, reason_faults(text))


def background_env(tmp_path, **kw):
    return talk_env(tmp_path, MOCO_BACKGROUND="on", **kw)


def run_on(env):
    return lambda i, text: first_try(env, Q, "background", text, thread_key=thread(i))


def test_reasoning_and_a_way_to_check_pass(tmp_path):
    """T6: a text that offers a possibility, says why it is plausible and what records
    would check it passes; it is sent with today's fixed words before and after it."""
    for text in GOOD:
        premise(text, [], [])
    env = background_env(tmp_path)
    assert env.settings.moco_talk == "on"  # these texts pass today's check too
    for i, text in enumerate(GOOD):
        reply = env.ask(Q, Step(finish("background", text)), thread_key=thread(i))
        assert (reply.status, reply.reply_kind, reply.reply_style) == \
            ("EXPLAINED", "background", "agent"), (text, reply.status, reply.reply_style)
        assert reply.text == BACKGROUND_PREFIX + text + BACKGROUND_SUFFIX
        assert len(env.model.calls) == 1


@pytest.mark.parametrize("text", [NO_REASON, NO_CHECK, NEITHER],
                         ids=["no reasoning", "no way to check", "neither"])
def test_a_missing_reason_or_way_to_check_fails_reason(tmp_path, text):
    """T6: no reasoning, no way to check it, or neither: exactly REASON (once), and the
    REWRITE answer's hint is REASON's line."""
    premise(text, [], ["REASON"])
    assert talk_rules()["rewrite_hints"]["REASON"] == HINTS["REASON"]
    env = background_env(tmp_path)
    reply, problems = first_try(env, Q, "background", text)
    assert problems == ["REASON"], problems
    assert env.model.answer(0)["do"] == HINTS["REASON"]
    assert reply.reply_style == "fallback"


@pytest.mark.parametrize("code, text", [
    ("NUMBER", "Arrests may rise in July because people are outdoors. To check it, you would "
               "need records of arrests by month."),
    ("ADVICE", "Arrests may rise in summer because people are outdoors, so the county should "
               "act. To check it, you would need records of arrests by season."),
    ("CERTAIN", "Studies show arrests may rise in summer because people are outdoors. To check "
                "it, you would need records of arrests by season."),
    ("HEDGE", "Arrests rise in summer because people are outdoors. To check it, look at "
              "records of arrests by season."),
], ids=["NUMBER", "ADVICE", "CERTAIN", "HEDGE"])
def test_todays_checks_stay(tmp_path, code, text):
    """T6: "all of today's checks stay": a text with its reasoning and a way to check still
    fails today's codes."""
    premise(text, [code], [])
    check_cases(run_on(background_env(tmp_path)), [(text, code)], BACKGROUND_CODES)


def test_the_second_try(tmp_path):
    """T6 with T3: a failed background text gets a second try; a passing second text is
    sent (style agent), a failing one gives the fixed refusal (style fallback)."""
    env = background_env(tmp_path)
    reply = env.ask(Q, Step(finish("background", NO_REASON)), Step(finish("background", GOOD[0])),
                    thread_key=thread(1))
    assert env.model.answer(0)["error"] == "REWRITE"
    assert (reply.status, reply.reply_style) == ("EXPLAINED", "agent"), reply.text
    assert reply.text == BACKGROUND_PREFIX + GOOD[0] + BACKGROUND_SUFFIX
    reply = env.ask(Q, Step(finish("background", NO_REASON)), Step(finish("background", NO_CHECK)),
                    Step(finish("background", GOOD[0])), thread_key=thread(2))
    assert len(env.model.calls) == 2
    assert reply.status in ("UNSUPPORTED", "EXPLAINED") and reply.reply_style == "fallback"
    assert_fixed(reply.text, "BACKGROUND_OFF")


def test_still_governed_by_moco_background(tmp_path):
    """T6: with MOCO_TALK on and MOCO_BACKGROUND off, a good text gets today's fixed
    refusal at once: no second try, nothing of the model's text."""
    env = talk_env(tmp_path)
    assert env.settings.moco_talk == "on"
    reply = env.ask(Q, Step(finish("background", GOOD[0])), Step(finish("background", GOOD[1])))
    assert len(env.model.calls) == 1
    assert (reply.status, reply.reason_code) == ("UNSUPPORTED", "BACKGROUND_OFF")
    assert_fixed(reply.text, "BACKGROUND_OFF")


def test_reason_applies_in_county_mode_too(tmp_path, monkeypatch):
    """T6: REASON with MOCO_TALK on, in county mode as well."""
    env = county_talk_env(tmp_path, monkeypatch, MOCO_BACKGROUND="on")
    check_cases(run_on(env), [(NO_REASON, "REASON"), (GOOD[0], None)], BACKGROUND_CODES)


@pytest.mark.parametrize("values", [{}, {"MOCO_TALK": "off"}], ids=["unset", "off"])
def test_with_talk_off_the_background_check_is_exactly_todays(tmp_path, values):
    """T6 and T0: with MOCO_TALK unset or off, a text with no reasoning passes as today,
    and a text that fails today's check falls back at once, with no second try."""
    assert make_settings(tmp_path, **values).moco_talk == "off"
    premise(NEITHER, [], ["REASON"])
    env = Env(tmp_path, MOCO_BACKGROUND="on", **values)
    reply = env.ask(Q, Step(finish("background", NEITHER)))
    assert (reply.status, reply.reply_style) == ("EXPLAINED", "agent"), reply.text
    assert reply.text == BACKGROUND_PREFIX + NEITHER + BACKGROUND_SUFFIX
    hedge = "Arrests rise in summer because people are outdoors."
    premise(hedge, ["HEDGE"], ["REASON"])
    reply = env.ask(Q, Step(finish("background", hedge)), Step(finish("background", NEITHER)),
                    thread_key=thread(3))
    assert len(env.model.calls) == 1, "a second try was given with talk off"
    assert reply.reply_style == "fallback"
    assert_fixed(reply.text, "BACKGROUND_OFF")
