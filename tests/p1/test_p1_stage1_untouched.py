"""Point 13: stage 1 is untouched (design P1, section 2). The 142 stage 1 tests passing is
shown by the full run. This adds: every stage 1 file directly under tests/ is byte for byte
the one committed in 712d581 ("Stage 1 tests and synthetic data (red)"), and none was added
or removed. The hashes were taken by the stage 2 tests session on 2026-11-10.
"""
import hashlib

from support import REPO

STAGE_1_TESTS = {
    "conftest.py": "eafd11605f4e0d23d433d25e3fca8ed9e770078307f03620a1aefc3ccdc2740d",
    "support.py": "afce59e503083d64fd1a5c58ba4476fe8958f8ea14b2f1a5955de63a58ec6127",
    "test_answered.py": "cb93e7206f443d31fd7c8965aca6bca9afd61ffdf8b5158dd2e39c1dc77f01e9",
    "test_cli.py": "c84bf712e49599fa6a17689635edd2d1d40fc9061f12e2907b9278b4cfaea64c",
    "test_data_class_guard.py": "bcb0926cd702a498db6de3aee5d583dbf3eabe743836ba89f05d59ebb87f5f22",
    "test_data_files.py": "774bfb35e68a8c902a0618570da2590852187eae581f4b46bbac77bf0f10fce4",
    "test_execute_call.py": "5ccb6655f695214ceb44b7455abc01fa9f91e90d3c5c0d37dd89317f9beade5e",
    "test_helpers.py": "264044c33357daffcb028891474f1d15e9147d90a47b250524214dc3c2132244",
    "test_provenance.py": "43b1b737b088225bdd1ece34b35b2cc8fdcd5e2050c14ae1d3493d7ccd7b7c77",
    "test_refusals.py": "f63b83f4d01def84790c0d19baad5bdd2eb76b61a224057fab8fa71923ab80ad",
    "test_router_extra.py": "67c3c369161e0ae4a5b40aa7c42e9bfa61c684e50d6c9fb0bf33d1bf0cf3f328",
}


def test_stage_1_test_files_are_unchanged():
    tests = REPO / "tests"
    assert {p.name for p in tests.glob("*.py")} == set(STAGE_1_TESTS)
    for name, digest in STAGE_1_TESTS.items():
        assert hashlib.sha256((tests / name).read_bytes()).hexdigest() == digest, name
