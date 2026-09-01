import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).with_name("verify-q38-a43-fullgraph-runtime.py")
SPEC = importlib.util.spec_from_file_location("q38_a43_runtime", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_engine_core_consumed_selector_is_normalized() -> None:
    assert MODULE.normalize_trace_identity({}, MODULE.ENGINE_CORE_COMM, "/trace") == {
        "TORCH_TRACE": "/trace"
    }


def test_engine_core_different_selector_is_rejected() -> None:
    with pytest.raises(MODULE.BASE.CORE.VerificationError):
        MODULE.normalize_trace_identity(
            {"TORCH_TRACE": "/wrong"}, MODULE.ENGINE_CORE_COMM, "/trace"
        )


def test_untruncated_display_name_is_not_special_cased() -> None:
    assert MODULE.normalize_trace_identity({}, "VLLM::EngineCore", "/trace") == {}


def test_worker_missing_selector_is_not_normalized() -> None:
    assert MODULE.normalize_trace_identity({}, "VLLM::Worker_TP0_EP0", "/trace") == {}


def test_worker_exact_selector_is_preserved() -> None:
    environment = {"TORCH_TRACE": "/trace"}
    assert (
        MODULE.normalize_trace_identity(environment, "VLLM::Worker_TP0_EP0", "/trace")
        == environment
    )


def test_trace_argument_is_exact() -> None:
    assert MODULE.trace_argument(["--torch-trace", "/trace"]) == "/trace"
    with pytest.raises(RuntimeError):
        MODULE.trace_argument([])
    with pytest.raises(RuntimeError):
        MODULE.trace_argument(["--torch-trace", "/a", "--torch-trace", "/b"])


def test_base_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    changed = tmp_path / "changed.py"
    changed.write_text("changed\n", encoding="utf-8")
    with pytest.raises(RuntimeError):
        MODULE.verify_base_hash(changed, MODULE.EXPECTED_BASE_SHA256)
