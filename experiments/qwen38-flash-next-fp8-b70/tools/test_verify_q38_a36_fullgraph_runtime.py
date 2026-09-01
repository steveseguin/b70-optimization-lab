import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).with_name("verify-q38-a36-fullgraph-runtime.py")
SPEC = importlib.util.spec_from_file_location("q38_a36_runtime", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_missing_post_exec_selectors_are_normalized(monkeypatch) -> None:
    expected_libccl = str(MODULE.BASE.BASE.EXPECTED_LIBCCL)
    monkeypatch.setattr(
        MODULE,
        "ORIGINAL_NORMALIZED_ENVIRONMENT",
        lambda _pid: {"LD_PRELOAD": expected_libccl},
    )
    environment = MODULE.normalized_environment(31)
    assert environment["CCL_KERNEL_PATH"] == str(
        MODULE.BASE.BASE.EXPECTED_KERNEL.parent
    )
    assert environment["CCL_SYCL_ALLREDUCE_LL_THRESHOLD"] == "4096"
    assert environment["VLLM_XPU_ENABLE_XPU_GRAPH"] == "1"


def test_wrong_kernel_path_is_rejected(monkeypatch) -> None:
    monkeypatch.setattr(
        MODULE,
        "ORIGINAL_NORMALIZED_ENVIRONMENT",
        lambda _pid: {"CCL_KERNEL_PATH": "/tmp/wrong-kernels"},
    )
    with pytest.raises(MODULE.BASE.BASE.VerificationError):
        MODULE.normalized_environment(32)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("CCL_SYCL_ALLREDUCE_LL_THRESHOLD", "8192"),
        ("VLLM_XPU_ENABLE_XPU_GRAPH", "0"),
    ],
)
def test_contradictory_selector_is_rejected(monkeypatch, key, value) -> None:
    monkeypatch.setattr(
        MODULE,
        "ORIGINAL_NORMALIZED_ENVIRONMENT",
        lambda _pid: {key: value},
    )
    with pytest.raises(MODULE.BASE.BASE.VerificationError):
        MODULE.normalized_environment(33)


def test_base_verifier_hash_mismatch_is_rejected(tmp_path) -> None:
    changed = tmp_path / "changed-verifier.py"
    changed.write_text("changed\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="base verifier hash changed"):
        MODULE.verify_base_hash(changed, MODULE.EXPECTED_BASE_SHA256)
