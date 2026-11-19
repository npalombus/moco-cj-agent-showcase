"""The one approved analysis, its checks, and the saved record (design sections 4 to 8 and 11).

Every number comes from counting the rows of the data file at the time of the call, with
pandas. Nothing is stored, cached or typed in. The texts are fixed wording filled in with
the computed numbers; no model writes them.
"""
import calendar
import hashlib
import io
import json
import os
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, ValidationError

from .router import ROUTER, SKILL, route

# ponytail: paths are found from this file, so they hold for the editable install
# (`pip install -e .`) that stage 1 uses; a normal install would need data_path passed.
REPO = Path(__file__).resolve().parents[2]
DEFAULT_DATA = REPO / "data" / "synthetic" / "SYNTHETIC_arrests_v1.csv"
DEFAULT_RUNS = REPO / "runs"

DIRECT_CALL = "DIRECT_CALL"
MODEL_ROUTER = "NVIDIA_MODEL_TOOL_CALL"  # stage 2: the NVIDIA model chose the call
VERSION = "arrest_count_trend@0.1.0"
DATASET_ID = "SYNTHETIC:arrests_v1"
DATA_CLASS = "SYNTHETIC"
METRIC = "arrest_count"
UNIT = "arrest records"
AGE_GROUPS = ("under_18", "18_25", "26_40", "41_plus")
AGE_LABELS = {None: "all ages", "under_18": "people under 18", "18_25": "ages 18 to 25",
              "26_40": "ages 26 to 40", "41_plus": "ages 41 and over"}
CHART_LABEL = "SYNTHETIC DATA - NOT REAL MONTGOMERY COUNTY FIGURES"

STATUS_FOR = {
    "UNRECOGNIZED_QUESTION": "UNSUPPORTED", "REAL_DATA_NOT_AVAILABLE": "UNSUPPORTED",
    "UNSUPPORTED_METRIC": "UNSUPPORTED", "UNSUPPORTED_FIELD": "UNSUPPORTED",
    "OUT_OF_COVERAGE": "UNSUPPORTED", "UNKNOWN_SKILL": "ERROR",
    "INVALID_ARGUMENTS": "ERROR", "DATA_CLASS_MISMATCH": "ERROR", "DATA_UNREADABLE": "ERROR",
}

# What a refusal tells the person (fixed wording; never a number from the data).
REFUSAL_TEXT = {
    "UNRECOGNIZED_QUESTION": "Refused: the fixed rules could not read this as the one "
                             "question they answer, so nothing was counted.",
    "REAL_DATA_NOT_AVAILABLE": "Refused: only SYNTHETIC (made-up) data is loaded, so real, "
                               "actual or official figures are not available.",
    "UNSUPPORTED_METRIC": "Refused: only counts of arrest records can be given, not "
                          "convictions, prosecution, sentencing, jail, incarceration, "
                          "recidivism or any rate.",
    "UNSUPPORTED_FIELD": "Refused: the data has no race, ethnicity, gender, offense, place "
                         "or person details, and its only age groups are under 18, 18 to "
                         "25, 26 to 40, and 41 and over.",
    "UNKNOWN_SKILL": "Error: the requested analysis is not an approved one, so nothing was "
                     "counted.",
    "INVALID_ARGUMENTS": "Error: the analysis was called with arguments that fail its "
                         "checks, so nothing was counted.",
    "DATA_CLASS_MISMATCH": "Error: the data file is not labeled SYNTHETIC on every row, so "
                           "it was not used and nothing was counted.",
    "DATA_UNREADABLE": "Error: the data file is missing or could not be read, so nothing "
                       "was counted.",
}
CAN_ASK = ("You can ask how many SYNTHETIC arrest records there are each month of one year "
           "in the data, for all ages or for one age group: under 18, 18 to 25, 26 to 40, "
           "or 41 and over.")

BASE_LIMITATIONS = [  # design section 11
    "The data is SYNTHETIC. It is made up for testing and says nothing about Montgomery "
    "County.",
    "The count is of arrest records. It is not people, charges, cases, convictions or jail "
    "population.",
    "The numbers describe counts only. They show no cause and support no claim about any "
    "person.",
]
# How the answer was made: true for the rules router and a direct call (stage 1) ...
LIMITATIONS = BASE_LIMITATIONS + [
    "No AI model was used. Python counted the rows of the data file at the time of the call.",
]
# ... and its replacement when a model chose the call (design P1, section 9).
MODEL_LIMITATION = ("An AI model ({}) read the question and chose the analysis. Python "
                    "counted the rows and wrote every word and number of this answer.")
REFUSAL_LIMITATIONS = [
    "Nothing was counted, so this record holds no numbers from the data.",
    "The only data loaded is SYNTHETIC. It is made up for testing and says nothing about "
    "Montgomery County.",
]


class TrendArgs(BaseModel):
    """Section 4: `year` must be a real int (not text, a float or a boolean); `age_group`
    is one of the four groups or None; nothing else is accepted."""
    model_config = ConfigDict(strict=True, extra="forbid")
    year: int
    age_group: Literal["under_18", "18_25", "26_40", "41_plus"] | None = None


@dataclass
class AnalysisResult:
    status: str
    reason_code: str | None
    run_id: str
    created_at: str
    question: object
    router: str
    skill: str | None
    arguments: object
    data_class: str
    metric_name: str | None
    unit: str | None
    filters: dict
    period: dict
    computed_values: dict
    source_ids: list
    source_urls: list
    snapshot_id: str | None
    calculation_version: str | None
    chart_uri: str | None
    chart_title: str | None
    limitations: list
    user_facing_summary: str
    technical_summary: str
    manifest_path: str | None

    def to_dict(self):
        return asdict(self)


# ---- public interface (design section 5) -------------------------------------------

def answer_question(question, data_path=None, runs_dir=None):
    """Read the question with the fixed rules, then run the one analysis or refuse."""
    decision = route(question)
    if decision.reason_code is None:
        return _execute(decision.skill, decision.arguments, question, data_path, runs_dir,
                        ROUTER)
    raw = _read_bytes(_data_path(data_path))  # only for the record's snapshot_id
    return _refusal(decision.reason_code, decision.why, question=question, router=ROUTER,
                    skill=None, arguments=None, snapshot=_snapshot(raw),
                    data_path=data_path, runs_dir=runs_dir)


def execute_call(skill, arguments, question="", data_path=None, runs_dir=None, *,
                 model_id=None, router=MODEL_ROUTER):
    """The door a model uses. Trusts nothing it is given. `model_id` names the model that
    chose this call (stage 2's agent passes it); without it the record says DIRECT_CALL."""
    if model_id is None:
        return _execute(skill, arguments, question, data_path, runs_dir, DIRECT_CALL)
    return _execute(skill, arguments, question, data_path, runs_dir, router,  # S3A C51
                    model_id=str(model_id))


# ---- the analysis ------------------------------------------------------------------

def _execute(skill, arguments, question, data_path, runs_dir, router, model_id=None):
    path = _data_path(data_path)
    raw = _read_bytes(path)
    snapshot = _snapshot(raw)

    def refuse(code, why, chosen=SKILL, snap=snapshot):
        return _refusal(code, why, question=question, router=router, skill=chosen,
                        arguments=arguments, snapshot=snap, data_path=path,
                        runs_dir=runs_dir)

    if not (isinstance(skill, str) and skill == SKILL):
        return refuse("UNKNOWN_SKILL", f"the skill {_short(skill)} is not approved; the only "
                      f"approved skill is {SKILL}", chosen=None)
    if not isinstance(arguments, dict):
        return refuse("INVALID_ARGUMENTS", f"arguments must be a dictionary, got "
                      f"{type(arguments).__name__}")
    try:
        args = TrendArgs.model_validate(arguments)
    except ValidationError as e:
        problems = "; ".join(f"{'.'.join(map(str, err['loc'])) or 'arguments'}: {err['msg']}"
                             for err in e.errors())
        return refuse("INVALID_ARGUMENTS", f"the arguments fail the checks ({problems})")

    if raw is None:
        return refuse("DATA_UNREADABLE", f"the data file {path} is missing or cannot be read",
                      snap=None)
    try:
        df = pd.read_csv(io.BytesIO(raw), dtype=str, keep_default_na=False)
    except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError) as e:
        return refuse("DATA_UNREADABLE", f"the data file {path} is not readable CSV "
                      f"({type(e).__name__})", snap=None)

    # The data-class guard: every row, every value, before anything is counted.
    class_columns = [c for c in df.columns if re.fullmatch(r"data_class(\.\d+)?", str(c))]
    if "data_class" not in class_columns:
        return refuse("DATA_CLASS_MISMATCH", "the data file has no data_class column")
    bad = int((df[class_columns] != DATA_CLASS).any(axis=1).sum())
    if bad:
        return refuse("DATA_CLASS_MISMATCH", f"{bad} row(s) of the data file are not labeled "
                      f"{DATA_CLASS}")

    missing = [c for c in ("arrest_date", "age_group") if c not in df.columns]
    if missing:
        return refuse("DATA_UNREADABLE", f"the data file lacks the column(s) "
                      f"{', '.join(missing)}", snap=None)
    dates = pd.to_datetime(df["arrest_date"], format="%Y-%m-%d", errors="coerce")
    if dates.isna().any() or not df["age_group"].isin(AGE_GROUPS).all():
        return refuse("DATA_UNREADABLE", "the data file has rows with a date that is not "
                      "YYYY-MM-DD or an age group not in the list", snap=None)

    in_year = dates.dt.year == args.year
    if not in_year.any():
        return refuse("OUT_OF_COVERAGE", f"the data file has no rows for {args.year}")
    if args.age_group is not None:
        in_year &= df["age_group"] == args.age_group
    per_month = (dates[in_year].dt.month.value_counts()
                 .reindex(range(1, 13), fill_value=0).sort_index())
    by_month = {f"{args.year}-{m:02d}": int(n) for m, n in per_month.items()}
    values = {"by_month": by_month, "total": sum(by_month.values())}

    return _answered(args, values, question=question, router=router, snapshot=snapshot,
                     data_path=path, runs_dir=runs_dir, model_id=model_id)


def _data_path(data_path):
    return data_path if data_path is not None else DEFAULT_DATA


def _read_bytes(path):
    try:
        return Path(path).read_bytes()
    except (OSError, TypeError, ValueError):
        return None


def _snapshot(raw):
    return None if raw is None else "sha256:" + hashlib.sha256(raw).hexdigest()


def _short(value):
    text = repr(value)
    return text if len(text) <= 80 else text[:77] + "..."


def _json_safe(value):
    """The value as JSON would carry it, so manifest.json equals to_dict() exactly."""
    try:
        return json.loads(json.dumps(value, default=repr))
    except (TypeError, ValueError):
        return repr(value)


# ---- building the record -----------------------------------------------------------

def _new_run(runs_dir):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    run_id = f"{now:%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
    root = Path(runs_dir) if runs_dir is not None else DEFAULT_RUNS
    run_dir = (root / run_id).resolve()
    run_dir.mkdir(parents=True)
    return run_id, now.isoformat(), run_dir


def _answered(args, values, *, question, router, snapshot, data_path, runs_dir,
              model_id=None):
    year, group = args.year, args.age_group
    by_month, total = values["by_month"], values["total"]
    label = AGE_LABELS[group]
    run_id, created_at, run_dir = _new_run(runs_dir)

    high, low = max(by_month.values()), min(by_month.values())
    if high == low:
        spread = f"Every month had {high:,}."
    else:
        spread = (f"The highest month was {_months(by_month, high)} with {high:,}; the "
                  f"lowest was {_months(by_month, low)} with {low:,}.")
    user = (f"SYNTHETIC DATA: in {year}, the made-up test data holds {total:,} arrest "
            f"records for {label}, counted month by month. {spread} These numbers are "
            f"invented for testing and say nothing about Montgomery County.")
    age_filter = "all age groups" if group is None else f"age_group == {group!r}"
    technical = (f"Method: pandas count of the rows of {data_path} per calendar month of "
                 f"{year} ({age_filter}); all 12 months listed, a month with no rows counts "
                 f"as 0; total = sum of the 12 months = {total}. Metric: {METRIC} ({UNIT}). "
                 f"Filters: year={year}, age_group={group}. Period: {year}-01-01 to "
                 f"{year}-12-31, by month. Dataset: {DATASET_ID} (data class {DATA_CLASS}; "
                 f"every row checked). Snapshot: {snapshot}. Calculation: {VERSION}. Router: "
                 f"{router}." + (f" Model: {model_id}." if model_id else ""))
    chart_title = f"{CHART_LABEL}\nArrest records per month, {year}, {label}"

    result = AnalysisResult(
        status="ANSWERED", reason_code=None, run_id=run_id, created_at=created_at,
        question=_json_safe(question), router=router, skill=SKILL,
        arguments=args.model_dump(), data_class=DATA_CLASS, metric_name=METRIC, unit=UNIT,
        filters={"year": year, "age_group": group},
        period={"start": f"{year}-01-01", "end": f"{year}-12-31", "granularity": "month"},
        computed_values=values, source_ids=[DATASET_ID], source_urls=[],
        snapshot_id=snapshot, calculation_version=VERSION,
        chart_uri=str(run_dir / "chart.png"), chart_title=chart_title,
        limitations=(list(LIMITATIONS) if model_id is None
                     else BASE_LIMITATIONS + [MODEL_LIMITATION.format(model_id)]),
        user_facing_summary=user, technical_summary=technical,
        manifest_path=str(run_dir / "manifest.json"))
    _draw_chart(result, run_dir / "chart.png")
    _save(result, run_dir)
    return result


def _refusal(code, why, *, question, router, skill, arguments, snapshot, data_path,
             runs_dir):
    status = STATUS_FOR[code]
    run_id, created_at, run_dir = _new_run(runs_dir)
    if code == "OUT_OF_COVERAGE":
        user = (f"Refused: the SYNTHETIC data has no arrest records for "
                f"{arguments['year']}. {CAN_ASK}")
    else:
        user = f"{REFUSAL_TEXT[code]} {CAN_ASK}"
    technical = (f"{status} {code}: {why}. Router: {router}. Skill: {skill}. Data class: "
                 f"{DATA_CLASS}. Dataset: {DATASET_ID}. Snapshot: "
                 f"{snapshot or 'none (the data file could not be read)'}. Data file: "
                 f"{_data_path(data_path)}.")
    result = AnalysisResult(
        status=status, reason_code=code, run_id=run_id, created_at=created_at,
        question=_json_safe(question), router=router, skill=skill,
        arguments=None if arguments is None else _json_safe(arguments),
        data_class=DATA_CLASS, metric_name=None, unit=None, filters={}, period={},
        computed_values={}, source_ids=[DATASET_ID], source_urls=[], snapshot_id=snapshot,
        calculation_version=None, chart_uri=None, chart_title=None,
        limitations=list(REFUSAL_LIMITATIONS), user_facing_summary=user,
        technical_summary=technical, manifest_path=str(run_dir / "manifest.json"))
    _save(result, run_dir)
    return result


def _months(by_month, value):
    names = [calendar.month_name[int(key[5:])] for key, n in by_month.items() if n == value]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


# ---- saved files (design section 7) ------------------------------------------------

def _save(result, run_dir):
    d = result.to_dict()
    lines = [f"# Run {d['run_id']}", "",
             f"DATA: {DATA_CLASS}. Source: {DATASET_ID}. Made-up test data, not real "
             f"Montgomery County figures.", "",
             f"- Question: {d['question']}",
             f"- Status: {d['status']}" + (f" ({d['reason_code']})" if d["reason_code"] else ""),
             f"- Router: {d['router']}",
             f"- Created (UTC): {d['created_at']}", "",
             "## Summary", "", d["user_facing_summary"], ""]
    if d["status"] == "ANSWERED":
        lines += ["## Monthly counts", "", "| Month | Arrest records |", "| --- | ---: |"]
        lines += [f"| {month} | {n} |" for month, n in d["computed_values"]["by_month"].items()]
        lines += [f"| Total | {d['computed_values']['total']} |", "",
                  "![chart](chart.png)", ""]
    lines += ["## Limitations", ""] + [f"- {s}" for s in d["limitations"]]
    lines += ["", "## Technical summary", "", d["technical_summary"], ""]
    (run_dir / "report.md").write_text("\n".join(lines), encoding="utf-8",
                                       errors="backslashreplace")
    # Written last, so the manifest only exists once everything it points to does.
    (run_dir / "manifest.json").write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8")


def _draw_chart(result, path):
    # Keep matplotlib's font cache inside the project (runs/ is not in git), so nothing
    # is written to the home folder. Must be set before matplotlib is first imported.
    os.environ.setdefault("MPLCONFIGDIR", str(DEFAULT_RUNS / ".matplotlib"))
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    by_month = result.computed_values["by_month"]
    counts = list(by_month.values())
    names = [calendar.month_abbr[m] for m in range(1, 13)]
    ink, muted, grid, bar = "#0b0b0b", "#52514e", "#e4e3df", "#2a78d6"

    fig = Figure(figsize=(10, 5.6), dpi=150, facecolor="#fcfcfb")
    FigureCanvasAgg(fig)  # the Agg backend: draws to a file, never opens a window
    ax = fig.add_subplot()
    ax.set_facecolor("#fcfcfb")
    bars = ax.bar(names, counts, width=0.55, color=bar, zorder=2)
    high, low = max(counts), min(counts)
    for rect, n in zip(bars, counts):  # direct labels on the highest and lowest only
        if n in (high, low):
            ax.annotate(f"{n}", (rect.get_x() + rect.get_width() / 2, n),
                        xytext=(0, 4), textcoords="offset points", ha="center",
                        va="bottom", fontsize=9, color=ink)
    ax.set_ylim(0, max(high * 1.15, 1))
    ax.set_ylabel("Arrest records (count)", color=muted)
    ax.grid(axis="y", color=grid, linewidth=0.8, zorder=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(muted)
    ax.tick_params(colors=muted, length=0)
    label, subtitle = result.chart_title.split("\n")
    fig.suptitle(label, fontsize=13, fontweight="bold", color="#b3261e", y=0.97)
    ax.set_title(subtitle, fontsize=11, color=ink, pad=10)
    fig.text(0.01, 0.015,
             f"Source: {DATASET_ID} (made-up test data)  |  total {result.computed_values['total']}"
             f"  |  {result.snapshot_id[:19]}...  |  {VERSION}  |  run {result.run_id}",
             fontsize=7, color=muted)
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    fig.savefig(path, facecolor=fig.get_facecolor())
