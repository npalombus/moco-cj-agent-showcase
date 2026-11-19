"""Point 2: the registry (design P1, section 5; P1A, A6 last paragraph; brief P1A-A point 10).

Section 5 says what a Registry gives (the dataset's id, data class, coverage dates, age
groups as code to wording, the metric's unit and meaning, the skill's name and version) but
not under which attribute names. So these tests look for each value anywhere reachable from
the Registry object (p1support.reachable_values) and accept any names. A date may be held
as the text "2024-01-01" or as a date; both are accepted.

The expected values are read from config/registry.json itself and checked against the
truth file and stage 1's constants, never typed in.

P1A (A6): the real file now holds two skills, arrest_count_trend and compare_counts, and
load_registry must load a file with more than one skill and still give the
arrest_count_trend fields it gives now, whatever the skills' order: a text that gives the
counting skill's name, version or description on the file as it is must give the same at the
same place (attribute names and mapping keys, never a list position) on the reversed file.
The 24 P1 tests are kept as they were; the tests at the end are new. Not checked (A6 is silent): which attributes
give the compare_counts skill, and what a file with a broken second skill does.
"""
import json
from collections.abc import Mapping
from datetime import date

import pytest

from p1support import (REGISTRY_JSON, load_registry, mod, reachable_values, registry_copy,
                       registry_json, registry_metric, registry_skill, registry_source)
from support import DATASET_ID, SKILL, VERSION, load_truth


def gives(registry, value):
    """True when the value is reachable as data (an attribute, a property, a mapping or a
    sequence item; not only through a method call). A str Enum member counts as its text."""
    return any(isinstance(v, type(value)) and not isinstance(v, bool) and v == value
               for v in reachable_values(registry))


def gives_date(registry, text):
    return gives(registry, text) or gives(registry, date.fromisoformat(text))


def test_the_real_registry_loads_from_the_default_path_and_from_its_path():
    registry = mod("registry")
    for loaded in (registry.load_registry(), registry.load_registry(REGISTRY_JSON)):
        assert isinstance(loaded, registry.Registry)


def test_the_registry_file_agrees_with_the_truth_file_and_stage_1():
    """A check on the planning chat's file, so the next tests compare against the truth."""
    truth, source = load_truth(), registry_source()
    assert source["id"] == truth["dataset_id"] == DATASET_ID
    assert source["data_class"] == truth["data_class"] == "SYNTHETIC"
    assert source["coverage"] == truth["coverage"]
    assert list(source["age_groups"]) == truth["age_groups"]
    assert (registry_skill()["name"], registry_skill()["version"]) == (SKILL, VERSION)
    assert registry_metric()["unit"] == "arrest records"


def test_registry_gives_the_dataset_id_and_data_class():
    registry = load_registry()
    assert gives(registry, registry_source()["id"])
    assert gives(registry, "SYNTHETIC")


def test_registry_gives_the_coverage_dates():
    registry = load_registry()
    coverage = registry_source()["coverage"]
    assert gives_date(registry, coverage["start"])
    assert gives_date(registry, coverage["end"])


def gives_age_groups(registry):
    """Code to plain wording: as a mapping, or as a sequence of (code, wording) pairs."""
    expected = registry_source()["age_groups"]
    found = False
    for value in reachable_values(registry):
        if isinstance(value, Mapping):
            found = found or dict(value) == expected
        elif isinstance(value, (list, tuple)) and value and all(
                isinstance(pair, (list, tuple)) and len(pair) == 2 for pair in value):
            found = found or dict(value) == expected
    return found


def test_registry_gives_the_four_age_groups_with_their_wording():
    assert gives_age_groups(load_registry()), \
        "no code-to-wording mapping equal to the registry's age groups"


def test_registry_gives_the_metric_unit_and_meaning():
    registry = load_registry()
    assert gives(registry, registry_metric()["unit"])
    assert gives(registry, registry_metric()["meaning"])


def test_registry_gives_the_skill_name_and_version():
    registry = load_registry()
    assert gives(registry, registry_skill()["name"])
    assert gives(registry, registry_skill()["version"])


def _remove(*path):
    def change(data):
        node = data
        for step in path[:-1]:
            node = node[step]
        del node[path[-1]]
    return change


# The parts a Registry must give (section 5), each removed from a copy.
REMOVALS = {
    "approved_sources": _remove("approved_sources"),
    "metric_definitions": _remove("metric_definitions"),
    "skills": _remove("skills"),
    "source_id": _remove("approved_sources", 0, "id"),
    "source_data_class": _remove("approved_sources", 0, "data_class"),
    "source_coverage": _remove("approved_sources", 0, "coverage"),
    "coverage_start": _remove("approved_sources", 0, "coverage", "start"),
    "coverage_end": _remove("approved_sources", 0, "coverage", "end"),
    "source_age_groups": _remove("approved_sources", 0, "age_groups"),
    "metric_unit": _remove("metric_definitions", 0, "unit"),
    "metric_meaning": _remove("metric_definitions", 0, "meaning"),
    "skill_name": _remove("skills", 0, "name"),
    "skill_version": _remove("skills", 0, "version"),
}


def test_the_changed_copy_helper_keeps_a_loadable_copy(tmp_path):
    """Control: a copy changed in nothing but its (now absolute) data path still loads, so
    the failures below come from the removed part alone."""
    registry = mod("registry")
    assert isinstance(registry.load_registry(registry_copy(tmp_path, lambda data: None)),
                      registry.Registry)


@pytest.mark.parametrize("part", REMOVALS)
def test_a_copy_with_a_part_removed_raises_registry_error(part, tmp_path):
    registry = mod("registry")
    path = registry_copy(tmp_path, REMOVALS[part])
    with pytest.raises(registry.RegistryError):
        registry.load_registry(path)


@pytest.mark.parametrize("data_class", ["VERIFIED_OFFICIAL", "REAL", ""])
def test_a_copy_whose_data_class_is_not_synthetic_raises_registry_error(data_class, tmp_path):
    registry = mod("registry")

    def change(data):
        data["approved_sources"][0]["data_class"] = data_class
    with pytest.raises(registry.RegistryError):
        registry.load_registry(registry_copy(tmp_path, change))


# ---- P1A, A6: a registry with two skills ---------------------------------------------

def _skills_reversed(tmp_path):
    def change(data):
        data["skills"].reverse()
    path = registry_copy(tmp_path, change)
    names = [s["name"] for s in json.loads(path.read_text(encoding="utf-8"))["skills"]]
    assert names[0] == "compare_counts" and names[-1] == SKILL  # control: really reversed
    return path


def test_the_real_file_holds_both_skills_and_loads():
    """A6: the registry gains the skill compare_counts (compare_counts@0.1.0)."""
    skills = registry_json()["skills"]
    assert sorted(s["name"] for s in skills) == sorted([SKILL, "compare_counts"])
    assert registry_skill("compare_counts")["version"] == "compare_counts@0.1.0"
    registry = mod("registry")
    assert isinstance(registry.load_registry(REGISTRY_JSON), registry.Registry)


def _paths(obj, path=(), seen=None):
    """(path, text) for every str reachable through public attributes and mapping keys only,
    never through a list, tuple or set (the skills' order there may follow the file).
    Methods are skipped; containers already visited are skipped (by id, kept alive)."""
    seen = {} if seen is None else seen
    if isinstance(obj, str):
        yield path, obj
        return
    if (isinstance(obj, (bytes, int, float, bool, type(None), date, list, tuple, set,
                         frozenset))
            or id(obj) in seen or len(path) > 6):
        return
    seen[id(obj)] = obj
    if isinstance(obj, Mapping):
        for key, value in obj.items():
            yield from _paths(value, path + (key,), seen)
        return
    for name in dir(obj):
        if name.startswith("_"):
            continue
        try:
            value = getattr(obj, name)
        except Exception:
            continue
        if callable(value) and not isinstance(value, Mapping):
            continue  # a method or a class, not data
        yield from _paths(value, path + (name,), seen)


def test_a_copy_with_the_skills_in_the_other_order_still_gives_arrest_count_trend(tmp_path):
    registry = mod("registry")
    loaded = registry.load_registry(_skills_reversed(tmp_path))
    assert isinstance(loaded, registry.Registry)
    assert gives(loaded, registry_skill()["name"])
    assert gives(loaded, registry_skill()["version"])
    # Same place, same text: a build that still takes the first skill as the counting one
    # gives compare_counts there on the reversed file. A build keyed by skill name passes.
    plain = registry.load_registry(registry_copy(tmp_path, lambda data: None, name="plain.json"))
    wanted = {registry_skill()[k] for k in ("name", "version", "description")}
    a, b = dict(_paths(plain)), dict(_paths(loaded))
    for p, v in a.items():
        if v in wanted:
            assert b.get(p) == v, p


def test_a_copy_with_the_skills_in_the_other_order_still_gives_the_other_fields(tmp_path):
    """The fields the P1 tests above check, on the reversed copy."""
    loaded = load_registry(_skills_reversed(tmp_path))
    source, metric = registry_source(), registry_metric()
    assert gives(loaded, source["id"])
    assert gives(loaded, "SYNTHETIC")
    assert gives_date(loaded, source["coverage"]["start"])
    assert gives_date(loaded, source["coverage"]["end"])
    assert gives_age_groups(loaded), "no code-to-wording mapping equal to the age groups"
    assert gives(loaded, metric["unit"])
    assert gives(loaded, metric["meaning"])
