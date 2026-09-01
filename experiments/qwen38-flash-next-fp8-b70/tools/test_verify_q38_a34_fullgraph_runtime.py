import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).with_name("verify-q38-a34-fullgraph-runtime.py")
SPEC = importlib.util.spec_from_file_location("q38_a34_runtime", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_missing_preload_is_accepted_after_exact_map_gate(monkeypatch) -> None:
    monkeypatch.setattr(MODULE, "ORIGINAL_PROCESS_ENVIRONMENT", lambda _pid: {})
    environment = MODULE.normalized_environment(17)
    assert environment["LD_PRELOAD"] == str(MODULE.BASE.EXPECTED_LIBCCL)


def test_expected_plus_auxiliary_preload_is_accepted(monkeypatch) -> None:
    value = f"{MODULE.BASE.EXPECTED_LIBCCL}:/tmp/libaux.so"
    monkeypatch.setattr(
        MODULE,
        "ORIGINAL_PROCESS_ENVIRONMENT",
        lambda _pid: {"LD_PRELOAD": value},
    )
    environment = MODULE.normalized_environment(18)
    assert environment["LD_PRELOAD"] == str(MODULE.BASE.EXPECTED_LIBCCL)


def test_unexpected_libccl_preload_is_rejected(monkeypatch) -> None:
    monkeypatch.setattr(
        MODULE,
        "ORIGINAL_PROCESS_ENVIRONMENT",
        lambda _pid: {"LD_PRELOAD": "/tmp/libccl.so.1"},
    )
    with pytest.raises(MODULE.BASE.VerificationError):
        MODULE.normalized_environment(19)


def test_base_verifier_hash_mismatch_is_rejected(tmp_path) -> None:
    changed = tmp_path / "changed-verifier.py"
    changed.write_text("changed\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="base verifier hash changed"):
        MODULE.verify_base_hash(changed, MODULE.EXPECTED_BASE_SHA256)
