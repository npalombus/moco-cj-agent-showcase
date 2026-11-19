"""The registry: approved sources, metric definitions and skills (design P1, section 5;
design P1A, A6: more than one skill).

config/registry.json is written by the planning chat and approved by Nino. Everything the
model is told about the data comes from it. A file missing a required part, or naming a
data class other than SYNTHETIC, raises RegistryError.
"""
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .core import REPO

DEFAULT_REGISTRY = REPO / "config" / "registry.json"


class RegistryError(Exception):
    pass


@dataclass(frozen=True)
class Registry:
    dataset_id: str
    data_class: str
    coverage_start: date
    coverage_end: date
    age_groups: dict        # code -> plain wording, in the file's order
    metric_name: str
    metric_unit: str
    metric_meaning: str
    metric_is_not: tuple
    skill_name: str
    skill_version: str
    skill_description: str

    @property
    def coverage_years(self):
        return tuple(range(self.coverage_start.year, self.coverage_end.year + 1))


def load_registry(path=None):
    path = Path(DEFAULT_REGISTRY if path is None else path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        # ponytail: one source and one metric, the first of each. The counting skill is
        # found by its name, so the other skills (compare_counts, A6) may come in any order.
        source = data["approved_sources"][0]
        metric = data["metric_definitions"][0]
        (skill,) = [s for s in data["skills"] if s.get("name") == "arrest_count_trend"]
        registry = Registry(
            dataset_id=_text(source["id"]),
            data_class=_text(source["data_class"]),
            coverage_start=date.fromisoformat(source["coverage"]["start"]),
            coverage_end=date.fromisoformat(source["coverage"]["end"]),
            age_groups={_text(code): _text(wording)
                        for code, wording in source["age_groups"].items()},
            metric_name=_text(metric["name"]),
            metric_unit=_text(metric["unit"]),
            metric_meaning=_text(metric["meaning"]),
            metric_is_not=tuple(_text(item) for item in metric.get("is_not", [])),
            skill_name=_text(skill["name"]),
            skill_version=_text(skill["version"]),
            skill_description=str(skill.get("description", "")),
        )
    except (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError) as e:
        raise RegistryError(f"{path} is missing a required part or cannot be read "
                            f"({type(e).__name__}: {e})") from None
    if registry.data_class != "SYNTHETIC":
        raise RegistryError(f"{path} names the data class {registry.data_class!r}; stage 2 "
                            f"accepts only SYNTHETIC")
    if not registry.age_groups or registry.coverage_start > registry.coverage_end:
        raise RegistryError(f"{path} has no age groups or its coverage ends before it starts")
    return registry


def _text(value):
    if not isinstance(value, str) or not value:
        raise ValueError("expected non-empty text")
    return value
