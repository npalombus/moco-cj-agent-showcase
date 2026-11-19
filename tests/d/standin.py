"""Runs ONE moco_agent command in its own process, with the stand-ins of the tests, against
the copy of the program dsupport.Sandbox made in pytest's temporary folder. Not a test file:
dsupport.Sandbox.run starts it as `python standin.py <config.json>`.

What it puts in place before the command runs (each is the stand-in the tests already use,
imported from tests/p1/p1support.py and tests/s3/s3support.py):
- no network: a socket that tries to connect or look up a name raises ConnectionError;
- the county service: s3support.FakeService, one per source address, behind one transport
  that picks the service by the address asked for (dsupport.Services). It is given to every
  call of sources.fetch that brings no transport of its own, and it replaces sources._get (today's
  real transport) where that exists. A "slow" service waits, at its first request, on an
  event that this runner sets only after the Slack messages have been answered;
- Slack: slack_bolt.App and SocketModeHandler are replaced by stand-ins. The handler's
  start() is the whole Slack session: it waits (bounded) for the requests the config asks
  for, delivers each event to the handlers the program registered, the way Slack's Bolt
  calls them (by parameter name), and returns, so serve ends as it does on Ctrl+C;
- the model: llm.NvidiaModelClient is replaced by p1support.FakeModel, playing the steps of
  the config.

Then it calls moco_agent.__main__.main(argv) and writes what happened to the report file.
The program's own stdout and stderr are left to it. The process ends with os._exit, so a
background thread the program started cannot keep it alive.
"""
import inspect
import json
import os
import socket
import sys
import threading
import traceback
from pathlib import Path

WAIT = 30  # seconds: the longest any wait here lasts; a wait that runs out is reported


def replace_everywhere(module, name, new):
    """Put `new` in place of module.<name>, and in every loaded moco_agent module that holds
    the same object (so `from .x import name` is covered too)."""
    old = getattr(module, name, None)
    setattr(module, name, new)
    if old is None:
        return
    for mod_name, mod in list(sys.modules.items()):
        if (mod_name == "moco_agent" or mod_name.startswith("moco_agent.")) and \
                getattr(mod, name, None) is old:
            setattr(mod, name, new)


def main():
    config = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    report = {"code": None, "error": None, "posts": [], "uploads": [], "apps": 0,
              "socket_handlers": 0, "started": False, "model_clients": 0, "model_calls": 0,
              "requests": [], "network": 0, "answered": [], "seen": {}, "slow": None}

    def no_network(*args, **kwargs):
        report["network"] += 1
        raise ConnectionError("network use is blocked by the Part D stand-in")

    socket.socket.connect = no_network
    socket.socket.connect_ex = no_network
    socket.create_connection = no_network
    socket.getaddrinfo = no_network

    import moco_agent
    report["module_file"] = moco_agent.__file__

    from p1support import FakeModel, Step
    from s3support import FakeService, fixture_rows
    from dsupport import Services

    # ---- the county service ---------------------------------------------------------------
    seen = {}

    class SlowService(FakeService):
        """Its first request waits until `release` is set (or WAIT runs out)."""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.entered, self.release, self.finished = (threading.Event(), threading.Event(),
                                                         threading.Event())

        def _handle(self, method, url, params):
            first = not self.entered.is_set()
            self.entered.set()
            if first:
                self.release.wait(WAIT)
            try:
                return super()._handle(method, url, params)
            finally:
                if first:
                    self.finished.set()

    services, slow = {}, None
    for spec in config.get("services", []):
        rows = fixture_rows(spec["fixture"]) + list(spec.get("extra_rows", []))
        fail = {"all": spec["fail"]} if spec.get("fail") else None
        kind = SlowService if spec.get("slow") else FakeService
        service = kind(rows, address=spec["address"], fail=fail)
        services[spec["address"]] = service
        seen[spec["address"]] = threading.Event()
        if spec.get("slow"):
            slow = service

    def on_request(base):
        report["requests"].append(base)
        if base in seen:
            seen[base].set()

    transport = Services(services, on_request=on_request)
    import moco_agent.sources as sources
    real_fetch = sources.fetch

    def fetch(*args, **kwargs):
        if kwargs.get("transport") is None:
            kwargs["transport"] = transport
        return real_fetch(*args, **kwargs)

    replace_everywhere(sources, "fetch", fetch)
    if hasattr(sources, "_get"):
        replace_everywhere(sources, "_get", transport)

    # ---- the model ----------------------------------------------------------------------------
    steps = [Step(*[tuple(c) for c in s["calls"]], text=s.get("text"))
             for s in config.get("model_steps", [])]

    class StandInModel(FakeModel):
        def __init__(self, settings, *args, **kwargs):
            report["model_clients"] += 1
            super().__init__(*steps, model_id=settings.nvidia_model)

        def step(self, messages, tools):
            report["model_calls"] += 1
            return super().step(messages, tools)

    import moco_agent.llm as llm
    replace_everywhere(llm, "NvidiaModelClient", StandInModel)

    # ---- Slack ----------------------------------------------------------------------------------
    class Client:
        def chat_postMessage(self, **kwargs):
            report["posts"].append({k: kwargs.get(k) for k in ("channel", "thread_ts", "text")})
            return {"ok": True}

        def files_upload_v2(self, **kwargs):
            report["uploads"].append({k: str(kwargs.get(k)) for k in
                                      ("channel", "thread_ts", "file", "title",
                                       "initial_comment")})
            return {"ok": True}

        def auth_test(self, **kwargs):
            return {"ok": True, "team_id": config.get("team_id"), "user_id": "UAGENT001"}

    class App:
        def __init__(self, *args, **kwargs):
            report["apps"] += 1
            self.client = Client()
            self.handlers = {}

        def event(self, name, *args, **kwargs):
            def register(function):
                self.handlers.setdefault(name, []).append(function)
                return function
            return register

        def __getattr__(self, name):
            # Any other registration (app.error, app.middleware, app.message, ...) is taken
            # and ignored, as decorator or as call; no test event goes to it.
            def take(*args, **kwargs):
                if len(args) == 1 and callable(args[0]) and not kwargs:
                    return args[0]
                return lambda function: function
            return take

    def call_handler(function, app, body, event):
        offered = {"body": body, "event": event, "payload": event, "client": app.client,
                   "say": lambda *a, **k: None, "ack": lambda *a, **k: None,
                   "logger": __import__("logging").getLogger("standin"), "context": {}}
        parameters = inspect.signature(function).parameters
        if any(p.kind is p.VAR_KEYWORD for p in parameters.values()):
            return function(**offered)
        return function(**{name: offered[name] for name in parameters if name in offered})

    def session(app):
        report["started"] = True
        for address in config.get("wait_for", []):
            report["seen"][address] = seen[address].wait(WAIT)
        if slow is not None:
            report["slow"] = {"entered_before_message": slow.entered.wait(WAIT)}
        for n, event in enumerate(config.get("events", [])):
            body = {"team_id": config.get("team_id"), "event_id": f"EvD{n:09d}",
                    "type": "event_callback", "event": event}
            worker = threading.Thread(
                target=lambda: [call_handler(f, app, body, event)
                                for f in app.handlers.get(event["type"], [])], daemon=True)
            worker.start()
            worker.join(WAIT)
            report["answered"].append(not worker.is_alive())
        if slow is not None:
            report["slow"]["finished_before_reply"] = slow.finished.is_set()
            slow.release.set()

    class SocketModeHandler:
        def __init__(self, app, *args, **kwargs):
            report["socket_handlers"] += 1
            self.app = app

        def start(self, *args, **kwargs):
            session(self.app)

        def connect(self, *args, **kwargs):
            session(self.app)

        def close(self, *args, **kwargs):
            pass

    import slack_bolt
    import slack_bolt.adapter.socket_mode as socket_mode
    replace_everywhere(slack_bolt, "App", App)
    replace_everywhere(socket_mode, "SocketModeHandler", SocketModeHandler)

    # ---- the command ------------------------------------------------------------------------------
    from moco_agent.__main__ import main as command
    try:
        code = command(config["argv"])
    except SystemExit as stop:
        code = stop.code
    except BaseException:
        report["error"] = traceback.format_exc()
        traceback.print_exc()
        code = None
    report["code"] = 0 if code is None and report["error"] is None else code
    Path(config["report"]).write_text(json.dumps(report, indent=2), encoding="utf-8")
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
