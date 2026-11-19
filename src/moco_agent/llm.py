"""The model client (design P1, section 8; design P1A, A14). Since S3A C51 it serves the
service MOCO_MODEL_PROVIDER names, NVIDIA's or Anthropic's; the class keeps its name.

`step(messages, tools)` makes one request and returns the tool calls the model made, as
received, with their ids (a call with no id gets one from Python), and its text; agent.py
judges them. Retries are bounded (1, 2, 4 seconds through `sleep`); after 3 calls in a row
end in ModelUnavailable, calls are refused at once for 60 seconds on `clock`. The key never
appears in an exception message, a log line or a return value.
"""
import json
import logging
import time
import uuid
from dataclasses import dataclass

from .config import model_service

log = logging.getLogger(__name__)

RETRIED = frozenset({"timeout", "rate_limit", "server", "network"})
KINDS = RETRIED | {"auth", "client"}
BREAKER_FAILURES = 3
BREAKER_SECONDS = 60


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments_json: str


@dataclass(frozen=True)
class ModelStep:
    tool_calls: list
    text: str | None


class ModelUnavailable(Exception):
    pass


class TransportError(Exception):
    def __init__(self, kind, status=None):
        self.kind = kind
        self.status = status
        super().__init__(kind if status is None else f"{kind} (HTTP {status})")


class NvidiaModelClient:
    def __init__(self, settings, transport=None, sleep=time.sleep, clock=time.monotonic):
        self._service = model_service(settings)  # S3A C51
        self.model_id = self._service.model
        self._settings = settings
        self._transport = transport if transport is not None else OpenAITransport(settings)
        self._sleep = sleep
        self._clock = clock
        self._failures = 0          # calls in a row that ended in ModelUnavailable
        self._paused_until = None   # set while the breaker is open

    def step(self, messages, tools):
        if self._paused_until is not None:
            if self._clock() < self._paused_until:
                raise ModelUnavailable("model calls are paused for a minute after "
                                       f"{BREAKER_FAILURES} failed calls in a row")
            self._paused_until = None  # the minute is over: try again
        try:
            result = self._call(messages, tools)
        except ModelUnavailable:
            self._failures += 1
            if self._failures >= BREAKER_FAILURES:
                self._paused_until = self._clock() + BREAKER_SECONDS
            raise
        self._failures = 0
        return result

    def _call(self, messages, tools):
        s = self._settings
        request = {"model": self.model_id, "messages": messages, "tools": tools,
                   "tool_choice": "auto", "temperature": self._service.temperature,
                   "max_tokens": s.moco_model_max_tokens,
                   "extra_body": dict(self._service.extra_body)}
        if self._service.temperature is None:  # C51 3b: Anthropic refuses 0 for this model
            del request["temperature"]
        tries = 1 + max(0, s.moco_model_max_retries)
        for attempt in range(tries):
            if attempt:
                self._sleep(2 ** (attempt - 1))
            try:
                body = self._transport(request)
            except TransportError as e:
                kind = e.kind if e.kind in KINDS else "client"
                shown = kind if e.status is None else f"{kind} (HTTP {e.status})"
                log.warning("model request failed: %s (try %d of %d)", shown, attempt + 1, tries)
                if kind in RETRIED and attempt + 1 < tries:
                    continue
                raise ModelUnavailable(f"the model endpoint failed ({kind})") from None
            except Exception as e:  # a transport that broke in some other way: no retry
                log.warning("model request failed: %s", type(e).__name__)
                raise ModelUnavailable("the model request failed") from None
            return _read(body)

    def __repr__(self):
        return f"NvidiaModelClient(model_id={self.model_id!r})"


def _read(body):
    """The OpenAI-shape response as a ModelStep; anything unreadable is ModelUnavailable."""
    try:
        message = body["choices"][0]["message"]
        content = message.get("content")
        raw_calls = message.get("tool_calls") or []
        if not isinstance(raw_calls, list):
            raise TypeError("tool_calls is not a list")
        calls = []
        for raw in raw_calls:
            name, arguments = raw["function"]["name"], raw["function"].get("arguments")
            if not isinstance(name, str):
                raise TypeError("a tool name is not text")
            call_id = raw.get("id")
            if not (isinstance(call_id, str) and call_id):  # an empty id pairs nothing
                call_id = f"call_py_{uuid.uuid4().hex[:12]}"
            calls.append(ToolCall(id=call_id, name=name, arguments_json=arguments if isinstance(
                arguments, str) else json.dumps(arguments)))
    except (KeyError, IndexError, TypeError, AttributeError):
        log.warning("model response could not be read")
        raise ModelUnavailable("the model's response could not be read") from None
    return ModelStep(tool_calls=calls, text=content if isinstance(content, str) else None)


class OpenAITransport:
    """One HTTPS request to the active service's endpoint with the openai package (both
    services take it; S3A C51). The package's own
    retries are off (the client above does them); its errors become TransportError kinds."""

    def __init__(self, settings):
        self._settings = settings
        self._client = None

    def __call__(self, request):
        import openai

        s = self._settings
        service = model_service(s)
        if not service.api_key:
            raise TransportError("auth")
        if self._client is None:
            self._client = openai.OpenAI(api_key=service.api_key, base_url=service.base_url,
                                         timeout=float(s.moco_model_timeout_seconds),
                                         max_retries=0)
        try:
            response = self._client.chat.completions.create(**request)
        except openai.APITimeoutError:
            raise TransportError("timeout") from None
        except openai.APIConnectionError:
            raise TransportError("network") from None
        except openai.RateLimitError as e:
            raise TransportError("rate_limit", e.status_code) from None
        except (openai.AuthenticationError, openai.PermissionDeniedError) as e:
            raise TransportError("auth", e.status_code) from None
        except openai.APIStatusError as e:
            raise TransportError("server" if e.status_code >= 500 else "client",
                                 e.status_code) from None
        except openai.OpenAIError:
            raise TransportError("client") from None
        return response.model_dump()

    def __repr__(self):
        return "OpenAITransport()"
