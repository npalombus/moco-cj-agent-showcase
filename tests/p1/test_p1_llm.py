"""Brief point 10, first half: the model client (design P1A A14, and P1 section 8 where A14
says "as P1"), through fake transports only. No test touches the network.

    model_client.step(messages, tools) -> ModelStep(tool_calls, text)
    each tool call is ToolCall(id, name, arguments_json), read as attributes

Covered: a good response becomes a ModelStep; ids the model gave are kept, and a call with
no id (key missing, null or "") gets a non-empty one from Python, different from every
other id of that step (an empty id is read as no id: A14 does not say so, but an empty id
cannot pair a tool result with its call); text with no tool call; unknown tools and non-object arguments are
passed on (A3/A4 judge them); the request (model, messages, tools, tool_choice, temperature,
max_tokens with the new default 2048, extra_body); retries and waits with the new default
MOCO_MODEL_MAX_RETRIES 1; the breaker; unreadable responses; the key in no exception, log
line or return value; the HTTP status in the log line of a refused request.

Time is injected: a FakeSleep records the waits, p1support's FakeClock is moved by hand.

Accepted both ways, because the design does not say:
- whether the breaker's 60 seconds end at exactly 60 or just after (59 and 61 are used),
  and whether a call refused while the breaker is open starts the 60 seconds again (the
  61-second check makes no call in between);
- whether an unreadable response is retried (those tests set MOCO_MODEL_MAX_RETRIES=0);
- the form of an id Python gives (only: a non-empty str, unlike the step's other ids).
Not checked, because A14 asks the HTTP status only for a refused request (auth, client):
whether the log line of a retried error (rate_limit, server) shows its status.
Not checkable without the network: the default transport (the openai package itself) and
its use of MOCO_MODEL_TIMEOUT_SECONDS.

Local helpers (p1support has none for these): FakeTransport, FakeSleep, response().
"""
import copy
import json
import logging
import traceback

import pytest

from p1support import FAKE_SECRETS, LATEST_HEADER, FakeClock, assert_no_secret, make_settings, mod

ARGS = '{"year": 2025, "age_group": "18_25"}'
MESSAGES = [{"role": "system", "content": "test system text"},
            {"role": "user", "content": f"{LATEST_HEADER}\nHow many arrests?"}]
TOOLS = [{"type": "function", "function": {
    "name": "decline", "description": "test tool",
    "parameters": {"type": "object", "properties": {"reason_code": {"type": "string"}}}}}]
RETRIED = ["timeout", "rate_limit", "server", "network"]
NOT_RETRIED = [("auth", 401), ("client", 400), ("client", 404)]
NO_ID = object()  # leave the "id" key out of a tool call


def response(*calls, content=None):
    """The endpoint's JSON in the OpenAI shape. Each call is (name, arguments_json) with the
    id call_test_<i>, or (name, arguments_json, id); an id of NO_ID leaves the key out."""
    message = {"role": "assistant", "content": content}
    if calls:
        message["tool_calls"] = []
        for i, call in enumerate(calls):
            name, arguments, call_id = (*call, f"call_test_{i}")[:3]
            raw = {"type": "function", "function": {"name": name, "arguments": arguments}}
            if call_id is not NO_ID:
                raw["id"] = call_id
            message["tool_calls"].append(raw)
    return {"id": "resp-test", "object": "chat.completion", "model": "test",
            "choices": [{"index": 0, "finish_reason": "stop", "message": message}]}


GOOD = response(("count_arrests", ARGS))


class FakeTransport:
    """Each outcome is a response dict to return, a TransportError kind to raise, or a
    (kind, status) pair. Outcomes are used in order; the last one repeats."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.requests = []

    def __call__(self, request):
        self.requests.append(copy.deepcopy(request))
        outcome = self.outcomes.pop(0) if len(self.outcomes) > 1 else self.outcomes[0]
        if isinstance(outcome, str):
            raise mod("llm").TransportError(outcome)
        if isinstance(outcome, tuple):
            raise mod("llm").TransportError(outcome[0], status=outcome[1])
        return copy.deepcopy(outcome)


class FakeSleep:
    def __init__(self):
        self.waits = []

    def __call__(self, seconds):
        self.waits.append(seconds)


def client(tmp_path, transport, *, sleep=None, clock=None, **settings_values):
    settings = make_settings(tmp_path, NVIDIA_API_KEY=FAKE_SECRETS["NVIDIA_API_KEY"],
                             **settings_values)
    return mod("llm").NvidiaModelClient(settings, transport=transport,
                                        sleep=sleep if sleep is not None else FakeSleep(),
                                        clock=clock if clock is not None else FakeClock())


def step(model):
    return model.step(copy.deepcopy(MESSAGES), copy.deepcopy(TOOLS))


def unavailable(model):
    llm = mod("llm")
    with pytest.raises(llm.ModelUnavailable) as caught:
        step(model)
    return caught.value


def calls_of(model_step):
    return [(c.name, c.arguments_json) for c in model_step.tool_calls]


# ---- a good response (A14) -------------------------------------------------------------

def test_model_id_is_the_settings_model(tmp_path):
    model = client(tmp_path, FakeTransport(GOOD), NVIDIA_MODEL="test-org/test-model-zz")
    assert model.model_id == "test-org/test-model-zz"


def test_a_good_response_becomes_a_model_step(tmp_path):
    """A14: step returns ModelStep(tool_calls, text); each call is ToolCall(id, name,
    arguments_json); text is the message content."""
    llm = mod("llm")
    result = step(client(tmp_path, FakeTransport(response(("count_arrests", ARGS),
                                                          content="some words"))))
    assert isinstance(result, llm.ModelStep)
    assert isinstance(result.tool_calls, list) and len(result.tool_calls) == 1
    call = result.tool_calls[0]
    assert isinstance(call, llm.ToolCall)
    assert (call.id, call.name, call.arguments_json) == ("call_test_0", "count_arrests", ARGS)
    assert result.text == "some words"


def test_content_null_gives_text_none(tmp_path):
    result = step(client(tmp_path, FakeTransport(GOOD)))
    assert result.text is None
    assert calls_of(result) == [("count_arrests", ARGS)]


def test_ids_the_model_gave_are_kept_as_given(tmp_path):
    result = step(client(tmp_path, FakeTransport(response(
        ("count_arrests", ARGS, "chatcmpl-tool-aa11"),
        ("describe_data", "{}", "chatcmpl-tool-bb22")))))
    assert [c.id for c in result.tool_calls] == ["chatcmpl-tool-aa11", "chatcmpl-tool-bb22"]


@pytest.mark.parametrize("missing", [NO_ID, None, ""], ids=["key_missing", "null", "empty"])
def test_a_call_with_no_id_gets_one_unlike_every_other_id_of_the_step(missing, tmp_path):
    """A14: a call the model gave no id gets one from Python. It must differ from every
    other id of the step (ids pair each tool result with its call, A4/A11), given ones
    included. An empty id ("") is read as no id (the lead's reading; A14 does not say)."""
    result = step(client(tmp_path, FakeTransport(response(
        ("count_arrests", ARGS, missing),
        ("describe_data", "{}", "chatcmpl-tool-cc33"),
        ("count_arrests", '{"year": 2024, "age_group": null}', missing),
        ("show_details", "{}", "chatcmpl-tool-dd44")))))
    ids = [c.id for c in result.tool_calls]
    assert ids[1] == "chatcmpl-tool-cc33" and ids[3] == "chatcmpl-tool-dd44"  # kept as given
    for given_by_python in (ids[0], ids[2]):
        assert isinstance(given_by_python, str) and given_by_python
    assert len(set(ids)) == 4, ids
    assert calls_of(result) == [("count_arrests", ARGS), ("describe_data", "{}"),
                                ("count_arrests", '{"year": 2024, "age_group": null}'),
                                ("show_details", "{}")]


def test_an_unknown_tool_and_arguments_that_are_not_an_object_are_passed_on(tmp_path):
    """A3/A4 judge these (BAD_CALL), so the client hands them on as they came."""
    result = step(client(tmp_path, FakeTransport(response(
        ("drop_everything", '{"a": 1}'), ("decline", "[1, 2]")))))
    assert calls_of(result) == [("drop_everything", '{"a": 1}'), ("decline", "[1, 2]")]


def test_several_tool_calls_are_all_kept_in_order(tmp_path):
    result = step(client(tmp_path, FakeTransport(response(
        ("count_arrests", ARGS), ("ask_user", '{"missing": "year"}'),
        ("decline", '{"reason_code": "UNSUPPORTED_FIELD"}')))))
    assert calls_of(result) == [("count_arrests", ARGS), ("ask_user", '{"missing": "year"}'),
                                ("decline", '{"reason_code": "UNSUPPORTED_FIELD"}')]
    assert [c.id for c in result.tool_calls] == ["call_test_0", "call_test_1", "call_test_2"]


@pytest.mark.parametrize("tool_calls", ["absent", None, []], ids=["absent", "null", "empty"])
def test_text_without_a_tool_call_is_a_step_with_no_calls(tool_calls, tmp_path):
    body = response(content="There were 500 arrests")
    if tool_calls != "absent":
        body["choices"][0]["message"]["tool_calls"] = tool_calls
    result = step(client(tmp_path, FakeTransport(body)))
    assert result.tool_calls == []
    assert result.text == "There were 500 arrests"


# ---- the request (P1 section 8, new default from A14) ------------------------------------

def test_the_request_carries_what_section_8_lists(tmp_path):
    transport = FakeTransport(GOOD)
    model = client(tmp_path, transport, NVIDIA_MODEL="test-org/test-model-zz",
                   MOCO_MODEL_MAX_TOKENS="77",
                   NVIDIA_EXTRA_BODY='{"chat_template_kwargs": {"enable_thinking": false}}')
    step(model)
    assert len(transport.requests) == 1
    request = transport.requests[0]
    assert request["model"] == "test-org/test-model-zz"
    assert request["messages"] == MESSAGES
    assert request["tools"] == TOOLS
    assert request["tool_choice"] == "auto"
    assert request["temperature"] == 0
    assert request["max_tokens"] == 77
    assert request["extra_body"] == {"chat_template_kwargs": {"enable_thinking": False}}


def test_by_default_max_tokens_is_2048_and_extra_body_is_sent_empty(tmp_path):
    transport = FakeTransport(GOOD)
    step(client(tmp_path, transport))
    assert transport.requests[0]["extra_body"] == {}
    assert transport.requests[0]["max_tokens"] == 2048  # A14's new default


# ---- retries (P1 section 8, new default MOCO_MODEL_MAX_RETRIES 1 from A14) ---------------

@pytest.mark.parametrize("kind", RETRIED)
def test_by_default_a_retried_error_makes_2_tries_waiting_1(kind, tmp_path):
    transport, sleep = FakeTransport(kind), FakeSleep()
    unavailable(client(tmp_path, transport, sleep=sleep))
    assert len(transport.requests) == 2
    assert sleep.waits == [1]


@pytest.mark.parametrize("retries, waits", [("2", [1, 2]), ("3", [1, 2, 4])])
@pytest.mark.parametrize("kind", RETRIED)
def test_more_retries_wait_1_then_2_then_4(kind, retries, waits, tmp_path):
    transport, sleep = FakeTransport(kind), FakeSleep()
    unavailable(client(tmp_path, transport, sleep=sleep, MOCO_MODEL_MAX_RETRIES=retries))
    assert len(transport.requests) == int(retries) + 1
    assert sleep.waits == waits


def test_no_retries_when_the_limit_is_0(tmp_path):
    transport, sleep = FakeTransport("timeout"), FakeSleep()
    unavailable(client(tmp_path, transport, sleep=sleep, MOCO_MODEL_MAX_RETRIES="0"))
    assert len(transport.requests) == 1
    assert sleep.waits == []


@pytest.mark.parametrize("retries, failures, waits", [(None, 1, [1]), ("2", 2, [1, 2])],
                         ids=["default", "two_retries"])
@pytest.mark.parametrize("kind", RETRIED)
def test_a_retry_that_works_returns_the_step(kind, retries, failures, waits, tmp_path):
    transport, sleep = FakeTransport(*[kind] * failures, GOOD), FakeSleep()
    extra = {} if retries is None else {"MOCO_MODEL_MAX_RETRIES": retries}
    result = step(client(tmp_path, transport, sleep=sleep, **extra))
    assert calls_of(result) == [("count_arrests", ARGS)]
    assert len(transport.requests) == failures + 1
    assert sleep.waits == waits


@pytest.mark.parametrize("kind, status", [("rate_limit", 429), ("server", 503)])
def test_a_retried_error_with_a_status_is_retried(kind, status, tmp_path):
    transport, sleep = FakeTransport((kind, status), GOOD), FakeSleep()
    step(client(tmp_path, transport, sleep=sleep))
    assert len(transport.requests) == 2 and sleep.waits == [1]


@pytest.mark.parametrize("retries", [None, "3"], ids=["default", "three_retries"])
@pytest.mark.parametrize("kind, status", NOT_RETRIED)
@pytest.mark.parametrize("with_status", [True, False])
def test_auth_and_client_errors_are_not_retried(kind, status, with_status, retries, tmp_path):
    transport = FakeTransport((kind, status) if with_status else kind)
    sleep = FakeSleep()
    extra = {} if retries is None else {"MOCO_MODEL_MAX_RETRIES": retries}
    unavailable(client(tmp_path, transport, sleep=sleep, **extra))
    assert len(transport.requests) == 1
    assert sleep.waits == []


@pytest.mark.parametrize("kind, status", NOT_RETRIED)
def test_auth_and_client_errors_after_a_retry_are_not_retried(kind, status, tmp_path):
    """Two retries allowed, so a third try would happen if the auth or client error were
    retried."""
    transport, sleep = FakeTransport("timeout", (kind, status), GOOD), FakeSleep()
    unavailable(client(tmp_path, transport, sleep=sleep, MOCO_MODEL_MAX_RETRIES="2"))
    assert len(transport.requests) == 2
    assert sleep.waits == [1]


# ---- the circuit breaker (P1 section 8) --------------------------------------------------

def open_breaker(tmp_path, clock, sleep):
    transport = FakeTransport("server", "server", "server", GOOD)
    model = client(tmp_path, transport, sleep=sleep, clock=clock, MOCO_MODEL_MAX_RETRIES="0")
    for _ in range(3):
        unavailable(model)
    assert len(transport.requests) == 3
    return model, transport


def test_the_breaker_opens_after_3_failed_calls(tmp_path):
    clock, sleep = FakeClock(), FakeSleep()
    model, transport = open_breaker(tmp_path, clock, sleep)
    unavailable(model)  # open: at once, without the network
    assert len(transport.requests) == 3
    clock.now += 59
    unavailable(model)
    assert len(transport.requests) == 3
    assert sleep.waits == []


def test_the_breaker_closes_after_60_seconds(tmp_path):
    clock, sleep = FakeClock(), FakeSleep()
    model, transport = open_breaker(tmp_path, clock, sleep)
    clock.now += 61  # 61 seconds after it opened, with no call in between
    assert calls_of(step(model)) == [("count_arrests", ARGS)]
    assert len(transport.requests) == 4


def test_the_breaker_counts_calls_not_tries(tmp_path):
    """With the default 1 retry, 3 failed calls are 6 tries; the 4th call makes none."""
    transport, sleep = FakeTransport("timeout"), FakeSleep()
    model = client(tmp_path, transport, sleep=sleep)
    for _ in range(3):
        unavailable(model)
    assert len(transport.requests) == 6
    waits_before = list(sleep.waits)
    unavailable(model)
    assert len(transport.requests) == 6
    assert sleep.waits == waits_before  # no waiting while open


def test_one_success_resets_the_count(tmp_path):
    transport = FakeTransport("server", "server", GOOD, "server", "server", GOOD)
    model = client(tmp_path, transport, MOCO_MODEL_MAX_RETRIES="0")
    unavailable(model)
    unavailable(model)
    step(model)
    unavailable(model)
    unavailable(model)
    assert calls_of(step(model)) == [("count_arrests", ARGS)]  # still closed
    assert len(transport.requests) == 6


def test_unreadable_responses_count_toward_the_breaker(tmp_path):
    requests = []

    def transport(request):
        requests.append(request)
        return {}
    model = client(tmp_path, transport, MOCO_MODEL_MAX_RETRIES="0")
    for _ in range(3):
        unavailable(model)
    unavailable(model)
    assert len(requests) == 3


@pytest.mark.parametrize("kind, status", NOT_RETRIED)
def test_auth_and_client_failures_count_toward_the_breaker(kind, status, tmp_path):
    transport = FakeTransport((kind, status))
    model = client(tmp_path, transport)
    for _ in range(3):
        unavailable(model)
    unavailable(model)
    assert len(transport.requests) == 3


# ---- unreadable responses, the log line, and the key -------------------------------------

UNREADABLE = {
    "empty_dict": {},
    "choices_empty": {"choices": []},
    "choices_null": {"choices": None},
    "choice_without_message": {"choices": [{}]},
    "message_is_text": {"choices": [{"message": "text"}]},
    "tool_calls_is_text": {"choices": [{"message": {"content": None, "tool_calls": "oops"}}]},
    "tool_call_without_function": {"choices": [{"message": {"tool_calls": [{"type": "function"}]}}]},
    "not_a_dict": ["choices"],
    "none": None,
}


def _returning(body):
    """A transport that returns `body` as it is, whatever its shape."""
    def transport(request):
        return copy.deepcopy(body)
    return transport


@pytest.mark.parametrize("body", UNREADABLE.values(), ids=UNREADABLE)
def test_an_unreadable_response_raises_model_unavailable(body, tmp_path):
    unavailable(client(tmp_path, _returning(body), MOCO_MODEL_MAX_RETRIES="0"))


def _all_text(error):
    return "".join(traceback.format_exception(error)) + str(error) + repr(error)


def _logged(caplog):
    return caplog.text + "".join(str(r.args) for r in caplog.records)


@pytest.mark.parametrize("kind, status", NOT_RETRIED)
def test_the_log_line_of_a_refused_request_shows_its_http_status(kind, status, tmp_path,
                                                                  caplog):
    """A14: the log line shows the HTTP status, for example `client (HTTP 404)`."""
    caplog.set_level(logging.DEBUG)
    unavailable(client(tmp_path, FakeTransport((kind, status))))
    assert f"{kind} (HTTP {status})" in caplog.text


# Whether the log line of a retried error (rate_limit 429, server 503) shows its HTTP status
# is not checked: A14 asks it only for a refused request, which the test above covers.


@pytest.mark.parametrize("outcome", RETRIED + [k for k, _ in NOT_RETRIED[:2]] + ["unreadable"])
def test_the_key_appears_in_no_exception_and_no_log_line(outcome, tmp_path, caplog):
    caplog.set_level(logging.DEBUG)
    transport = _returning({}) if outcome == "unreadable" else FakeTransport(outcome)
    model = client(tmp_path, transport, MOCO_MODEL_MAX_RETRIES="1")
    errors = [unavailable(model) for _ in range(4)]  # the 4th comes from the open breaker
    for error in errors:
        assert_no_secret(_all_text(error))
    assert_no_secret(_logged(caplog))


def test_the_key_appears_in_no_step_and_no_log_line(tmp_path, caplog):
    """One call has an id from the model, one an id from Python: neither holds the key."""
    caplog.set_level(logging.DEBUG)
    result = step(client(tmp_path, FakeTransport(response(
        ("count_arrests", ARGS), ("describe_data", "{}", NO_ID), content="some words"))))
    assert_no_secret(repr(result) + str(result) + json.dumps(
        [[c.id, c.name, c.arguments_json] for c in result.tool_calls] + [result.text]))
    assert_no_secret(_logged(caplog))
