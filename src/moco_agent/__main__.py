"""Command line (design P0 section 5, design P1 section 12, design P1A A15):

    python -m moco_agent ask "<question>" [--data PATH] [--runs-dir DIR]     stage 1: rules, no model
    python -m moco_agent agent-ask "<question>" [--thread KEY] [--db PATH] [--runs-dir DIR]
    python -m moco_agent requests [--days N] [--db PATH]
    python -m moco_agent serve
    python -m moco_agent whoami
    python -m moco_agent fetch <source id>                                   stage 3: one dated copy
    python -m moco_agent check-engine                                        Part S: R and its packages
    python -m moco_agent fetch-census                                        Part S2: Census copies

A command that needs a secret and finds it missing names the KEY and exits 4, before it
makes anything.
"""
import argparse
import sys
from pathlib import Path

from .core import answer_question

EXIT_CODES = {"ANSWERED": 0, "EXPLAINED": 0, "DETAILS": 0, "UNSUPPORTED": 3, "ERROR": 4,
              "NEEDS_INPUT": 5, "TALKED": 0}  # TALKED: MOCO_TALK on (Part T)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m moco_agent")
    commands = parser.add_subparsers(dest="command", required=True)
    ask = commands.add_parser("ask", help="ask one question about the SYNTHETIC arrest data")
    ask.add_argument("question")
    ask.add_argument("--data", help="data file (default: the SYNTHETIC arrests CSV)")
    ask.add_argument("--runs-dir", help="folder for the saved run (default: runs/)")
    agent_ask = commands.add_parser(
        "agent-ask", help="one agent turn from Terminal, with the real model")
    agent_ask.add_argument("question")
    agent_ask.add_argument("--thread", default="local:terminal:default",
                           help="thread key, so follow-ups can be tried (default: %(default)s)")
    agent_ask.add_argument("--db", help="memory file (default: var/agent.db)")
    agent_ask.add_argument("--runs-dir", help="folder for the saved run (default: runs/)")
    requests = commands.add_parser(
        "requests", help="the questions refused for what the data lacks, newest first")
    requests.add_argument("--days", type=int, default=30, help="how far back (default: 30)")
    requests.add_argument("--db", help="memory file (default: var/agent.db)")
    commands.add_parser("serve", help="run the agent in Slack (Socket Mode); blocks")
    commands.add_parser("whoami", help="ask Slack who the bot token belongs to (ids only)")
    fetch = commands.add_parser(
        "fetch", help="download one county source and save a dated copy (MOCO_STATE_DIR)")
    fetch.add_argument("source", help="the source id, for example MOCO:police_arrests")
    commands.add_parser(
        "refresh", help="download every county source once; a failed one keeps its last copy")
    commands.add_parser("check-engine",
                        help="print the R version and whether each R package loads (Part S)")
    commands.add_parser("fetch-census",
                        help="download the Census tables for rates per resident, a dated copy "
                             "of each published year (CENSUS_API_KEY; Part S2)")
    args = parser.parse_args(argv)

    if args.command == "ask":
        return _ask(args)
    if args.command == "requests":
        return _requests(args)
    from .config import ConfigError
    try:
        return {"agent-ask": _agent_ask, "serve": _serve, "whoami": _whoami,
                "fetch": _fetch, "refresh": _refresh, "fetch-census": _fetch_census,
                "check-engine": _check_engine}[args.command](args)
    except ConfigError as e:  # names the KEY, never a value
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_CODES["ERROR"]


def _ask(args):
    try:
        result = answer_question(args.question, data_path=args.data, runs_dir=args.runs_dir)
    except OSError as e:  # the run folder could not be made or written
        print(f"Error: could not save the run: {e}", file=sys.stderr)
        print("DATA: SYNTHETIC")
        return EXIT_CODES["ERROR"]
    print(result.user_facing_summary)
    print("DATA: SYNTHETIC")
    print(f"STATUS: {result.status}" + (f" ({result.reason_code})" if result.reason_code else ""))
    print(f"RUN ID: {result.run_id}")
    print(f"MANIFEST: {result.manifest_path}")
    print(f"REPORT: {Path(result.manifest_path).parent / 'report.md'}")
    if result.chart_uri:
        print(f"CHART: {result.chart_uri}")
    return EXIT_CODES[result.status]


def _agent_ask(args):
    from .agent import handle_question
    from .config import load_settings, require_for_model
    from .llm import NvidiaModelClient
    from .memory import DEFAULT_DB, Store
    from .registry import load_registry

    settings = load_settings()
    require_for_model(settings)  # before anything is made
    registry = load_registry()
    db = args.db or _state_file(settings, "agent.db", DEFAULT_DB)  # Part D D1
    model = NvidiaModelClient(settings)
    store = Store(db)
    try:
        reply = handle_question(args.question, thread_key=args.thread, user_id="local-terminal",
                                settings=settings, registry=registry, model_client=model,
                                store=store, runs_dir=args.runs_dir)
    finally:
        store.close()
    print(reply.text)
    print(f"MODEL: {model.model_id}")
    print(f"STATUS: {reply.status}" + (f" ({reply.reason_code})" if reply.reason_code else ""))
    print(f"STYLE: {reply.reply_style}" + (f" ({', '.join(reply.draft_failures)})"
                                           if reply.draft_failures else ""))
    if reply.run_ids:
        print(f"RUN IDS: {', '.join(reply.run_ids)}")
    if reply.chart_path:
        print(f"CHART: {reply.chart_path}")
    return EXIT_CODES[reply.status]


def _requests(args):
    """A15: the turns refused for what the data lacks, newest first, then a count per code.
    No user id."""
    from .config import ConfigError, load_settings
    from .memory import DEFAULT_DB, REQUEST_CODES, Store

    try:  # Part D D1: the memory file follows MOCO_STATE_DIR unless --db is given
        db = args.db or _state_file(load_settings(), "agent.db", DEFAULT_DB)
    except ConfigError as e:
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_CODES["ERROR"]
    store = Store(db)
    try:
        turns = store.refused_turns(args.days)
    finally:
        store.close()
    print(f"Questions refused for what the data lacks, last {args.days} days, newest first:")
    for turn in turns:
        question = " ".join(str(turn["question"]).split())
        print(f"{turn['created_at']:%Y-%m-%d %H:%M} UTC  {turn['reason_code']}  {question}")
    if not turns:
        print("(none)")
    print("Count per code:")
    for code in REQUEST_CODES:
        print(f"{code}: {sum(t['reason_code'] == code for t in turns)}")
    return 0


def _fetch(args):
    """S3A C4: run fetch once; print the copy's date, rows and fingerprint, or the reason it
    failed (the last good copy then stays in use)."""
    from . import sources
    from .config import load_settings
    from .counting import day_text

    settings = load_settings()
    sources.load_sources()
    invalid = sources.why_invalid(args.source)
    if invalid is not None:  # C20: a source file that fails its check is not offered
        name, reasons = invalid
        print(f"Fetch failed: the source file {name} is not valid: {'; '.join(reasons)}.",
              file=sys.stderr)
        return EXIT_CODES["ERROR"]
    try:
        copy = sources.fetch(args.source, state_dir=Path(settings.moco_state_dir))
    except sources.FetchFailed as e:
        print(f"Fetch failed: {e}. The last good copy, if any, stays in use.", file=sys.stderr)
        return EXIT_CODES["ERROR"]
    except OSError as e:  # the copy could not be written
        print(f"Fetch failed: the copy could not be saved ({type(e).__name__}).",
              file=sys.stderr)
        return EXIT_CODES["ERROR"]
    print(f"SOURCE: {copy.source_id}")
    print(f"COPY DATE: {day_text(copy.day)} (fetched {copy.fetched_at})")
    print(f"ROWS: {copy.rows:,}")
    print(f"NEWEST RECORD: {copy.newest[:10]}")
    print(f"FINGERPRINT: sha256:{copy.sha256}")
    print(f"FOLDER: {copy.folder}")
    return 0


def _state_file(settings, name, today):
    """Part D D1: a file of the state folder; the folder is made first when MOCO_STATE_DIR
    is set to something else than the default (a ConfigError if it cannot be)."""
    from .config import ensure_folder, state_file

    path = state_file(settings, name, today)
    if path != Path(today):
        ensure_folder(path.parent, "MOCO_STATE_DIR")
    return path


def _refresh(args):
    """Part D D4: fetch every valid county source once."""
    from . import refresh
    from .config import load_settings

    settings = load_settings()
    good = refresh.refresh_all(Path(settings.moco_state_dir))
    if settings.census_api_key:  # S2 R8: the Census copies too, at most once a day
        from . import census
        fetched = census.refresh_due(Path(settings.moco_state_dir), settings.census_api_key)
        good = good and fetched is not False
    return 0 if good else EXIT_CODES["ERROR"]


def _fetch_census(args):
    """S3S2 R8: a dated copy of the two Census tables for each published year; a year that
    fails its checks keeps its last good copy. Never prints the key."""
    from . import census
    from .config import load_settings, require

    settings = load_settings()
    require(settings, "CENSUS_API_KEY")  # before anything is made
    good = census.fetch_all(Path(settings.moco_state_dir), settings.census_api_key)
    return 0 if good else EXIT_CODES["ERROR"]


def _check_engine(args):
    """S3S S8: the R version (MOCO_RSCRIPT) and whether each package of the analyses loads."""
    from .config import load_settings
    from .stats import check_engine

    settings = load_settings()
    ok, lines = check_engine(settings.moco_rscript)
    print(f"RSCRIPT: {settings.moco_rscript}")
    for line in lines:
        print(line)
    print("ENGINE: ready" if ok else "ENGINE: not ready; statistical answers end with "
                                      "ENGINE_MISSING")
    return 0 if ok else EXIT_CODES["ERROR"]


def _serve(args):
    from .slack_app import serve

    serve()
    return 0


def _whoami(args):
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError

    from .config import load_settings, require

    settings = load_settings()
    require(settings, "SLACK_BOT_TOKEN")
    try:
        me = WebClient(token=settings.slack_bot_token).auth_test()
    except SlackApiError as e:  # Slack's error code only, e.g. invalid_auth
        print(f"Error: Slack refused the bot token ({e.response.get('error')}).",
              file=sys.stderr)
        return EXIT_CODES["ERROR"]
    except Exception as e:
        print(f"Error: could not reach Slack ({type(e).__name__}).", file=sys.stderr)
        return EXIT_CODES["ERROR"]
    print(f"WORKSPACE ID: {me.get('team_id')}")
    print(f"WORKSPACE NAME: {me.get('team')}")
    print(f"AGENT USER ID: {me.get('user_id')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
