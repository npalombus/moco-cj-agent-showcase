"""Point 12: no secrets in the repo. Needs no moco_agent, so it passes now and must keep
passing. A finding is reported by file and position only, never by the text found.

Walks every file under the repo except the top-level .git, .venv, var and runs folders and
cache folders at any depth. A symbolic link (to a file or a folder) is never read or
entered: one that points outside the repo fails the test, since it could reach a secrets
file. The shape also allows "_" after the prefix: a superset of the brief's shape (letters,
digits or dashes), since some keys use it.

Changed by briefs/S3-R14-A-tests.md for C51 (docs/S3A-DESIGN.md, D-071): the shape also
catches a text shaped like an Anthropic key, the prefix "sk-ant-" and at least ten more
characters of the same kind. Its made-up examples are built from pieces, as the others.
"""
import os
import re
from pathlib import Path

from support import REPO

SHAPE = re.compile(rb"(?:nvapi-|xoxb-|xoxp-|xoxa-|xapp-|sk-ant-)[A-Za-z0-9_-]{10,}")
SKIP_AT_TOP = {".git", ".venv", "var", "runs"}
SKIP_ANYWHERE = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}


def repo_files():
    """Every file to scan, and every link to a folder (os.walk does not enter those)."""
    for root, dirs, files in os.walk(REPO):
        top = Path(root) == REPO
        dirs[:] = [d for d in dirs
                   if d not in SKIP_ANYWHERE and not (top and d in SKIP_AT_TOP)]
        for name in dirs:
            if (Path(root) / name).is_symlink():
                yield Path(root) / name
        for name in files:
            yield Path(root) / name


def test_the_walk_sees_the_repo():
    names = {p.relative_to(REPO).as_posix() for p in repo_files()}
    assert {"README.md", "docs/P1-DESIGN.md", "tests/p1/test_p1_no_secrets.py",
            "config/registry.json"} <= names
    assert not any(n.startswith((".git/", ".venv/", "var/", "runs/")) for n in names)


def test_the_shape_matches_what_it_should():
    """The pattern on made-up text built here, so this file itself holds no such text."""
    filler = b"A1b2C3d4E5-f6"
    for prefix in (b"nvapi-", b"xoxb-", b"xoxp-", b"xoxa-", b"xapp-", b"sk-" + b"ant-"):
        assert SHAPE.search(b"x " + prefix + filler + b" y")
        assert SHAPE.search(b"x " + prefix + b"A1_b2C3d4E5" + b" y")
        assert not SHAPE.search(b"x " + prefix + b"short y")
        assert not SHAPE.search(b"starts `" + prefix + b"`)")
    assert not SHAPE.search(b"test-key-not-real-nvidia-q7")
    # C51: an Anthropic key's usual form, a kind word and a dash after the prefix.
    assert SHAPE.search(b"x " + b"sk-" + b"ant-" + b"api00-" + filler + b" y")


def test_no_file_in_the_repo_holds_text_shaped_like_a_key_or_token():
    found = []
    for path in repo_files():
        relative = path.relative_to(REPO).as_posix()
        if path.is_symlink():
            if not path.resolve().is_relative_to(REPO.resolve()):
                found.append(f"{relative}: a link that points outside the repo")
            continue
        data = path.read_bytes()
        for match in SHAPE.finditer(data):
            line = data.count(b"\n", 0, match.start()) + 1
            found.append(f"{relative}, line {line}: starts {match.group()[:5].decode()!r}")
    assert not found, "text shaped like a key or token:\n" + "\n".join(found)
