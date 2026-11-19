"""Record what synthetic mode does today, before stage 3 is built (brief S3A-A step 7).

Not collected by a normal pytest run (its name does not start with test_). Run it once,
on the program as it stood at commit 5233ceb, from the repo root:

    .venv/bin/python -m pytest -q -p no:cacheprovider tests/s3/fixtures/record_synthetic_today.py

It writes tests/s3/fixtures/synthetic_today.json: the three turns of
s3support.synthetic_three_turns (each reply's fields, and every model call's messages and
tools), with MOCO_DATA unset. test_s3_synthetic_untouched.py compares the build with it.
Everything in it is SYNTHETIC: the stage 1 made-up data and a stand-in model.
"""
import json

from s3support import SYNTHETIC_TODAY, synthetic_three_turns


def test_record_synthetic_mode_as_it_is_today(tmp_path):
    turns = synthetic_three_turns(tmp_path)
    data = {"note": "SYNTHETIC. What synthetic mode did before stage 3 (commit 5233ceb), "
                    "recorded by tests/s3/fixtures/record_synthetic_today.py with MOCO_DATA "
                    "unset. Run ids are written <run id N>; turn ids and chart paths are "
                    "left out.",
            "turns": turns}
    SYNTHETIC_TODAY.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                               encoding="utf-8")
    assert len(turns) == 3 and [t["reply"]["status"] for t in turns] == \
        ["ANSWERED", "ANSWERED", "DETAILS"]
