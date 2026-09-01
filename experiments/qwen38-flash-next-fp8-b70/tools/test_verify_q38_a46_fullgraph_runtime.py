import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).with_name("verify-q38-a46-fullgraph-runtime.py")
SPEC = importlib.util.spec_from_file_location("q38_a46_runtime", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_consumed_worker_selector_requires_rank_evidence() -> None:
    with pytest.raises(MODULE.BASE.BASE.CORE.VerificationError):
        MODULE.normalize_trace_identity({}, MODULE.WORKER_COMM, "/trace", False)
    assert MODULE.normalize_trace_identity({}, MODULE.WORKER_COMM, "/trace", True) == {
        "TORCH_TRACE": "/trace"
    }


def test_consumed_engine_selector_requires_rank_evidence() -> None:
    with pytest.raises(MODULE.BASE.BASE.CORE.VerificationError):
        MODULE.normalize_trace_identity({}, MODULE.ENGINE_CORE_COMM, "/trace", False)
    assert MODULE.normalize_trace_identity(
        {}, MODULE.ENGINE_CORE_COMM, "/trace", True
    ) == {"TORCH_TRACE": "/trace"}


@pytest.mark.parametrize("command", [MODULE.WORKER_COMM, MODULE.ENGINE_CORE_COMM])
def test_conflicting_consumed_selector_is_rejected(command: str) -> None:
    with pytest.raises(MODULE.BASE.BASE.CORE.VerificationError):
        MODULE.normalize_trace_identity(
            {"TORCH_TRACE": "/wrong"}, command, "/trace", True
        )


def test_unrelated_process_is_not_normalized() -> None:
    assert MODULE.normalize_trace_identity({}, "APIServer", "/trace", True) == {}
    assert (
        MODULE.normalize_trace_identity({}, "VLLM::Worker_TP0_EP0", "/trace", True)
        == {}
    )


def test_exact_selector_is_preserved_without_rank_evidence() -> None:
    environment = {"TORCH_TRACE": "/trace"}
    assert (
        MODULE.normalize_trace_identity(
            environment, MODULE.WORKER_COMM, "/trace", False
        )
        == environment
    )


def test_exact_four_rank_logs_pass(tmp_path: Path) -> None:
    for rank in range(4):
        (tmp_path / f"dedicated_log_torch_trace_rank_{rank}_receipt.log").write_text(
            "record\n", encoding="utf-8"
        )
    logs = MODULE.validate_rank_trace_files(tmp_path)
    assert [path.name for path in logs] == [
        f"dedicated_log_torch_trace_rank_{rank}_receipt.log" for rank in range(4)
    ]


@pytest.mark.parametrize("bad_rank", [None, 4])
def test_missing_or_extra_rank_is_rejected(
    tmp_path: Path, bad_rank: int | None
) -> None:
    ranks = [0, 1, 2, 3]
    if bad_rank is None:
        ranks.remove(3)
    else:
        ranks.append(bad_rank)
    for rank in ranks:
        (tmp_path / f"dedicated_log_torch_trace_rank_{rank}_receipt.log").write_text(
            "record\n", encoding="utf-8"
        )
    with pytest.raises(MODULE.BASE.BASE.CORE.VerificationError):
        MODULE.validate_rank_trace_files(tmp_path)


def test_duplicate_rank_is_rejected(tmp_path: Path) -> None:
    for rank in range(4):
        (tmp_path / f"dedicated_log_torch_trace_rank_{rank}_a.log").write_text(
            "record\n", encoding="utf-8"
        )
    (tmp_path / "dedicated_log_torch_trace_rank_2_b.log").write_text(
        "record\n", encoding="utf-8"
    )
    with pytest.raises(MODULE.BASE.BASE.CORE.VerificationError):
        MODULE.validate_rank_trace_files(tmp_path)


def test_empty_rank_log_is_rejected(tmp_path: Path) -> None:
    for rank in range(4):
        (tmp_path / f"dedicated_log_torch_trace_rank_{rank}_receipt.log").write_text(
            "record\n" if rank != 2 else "", encoding="utf-8"
        )
    with pytest.raises(MODULE.BASE.BASE.CORE.VerificationError):
        MODULE.validate_rank_trace_files(tmp_path)


def test_trace_argument_is_exact() -> None:
    assert MODULE.trace_argument(["--torch-trace", "/trace"]) == Path("/trace")
    with pytest.raises(RuntimeError):
        MODULE.trace_argument([])
    with pytest.raises(RuntimeError):
        MODULE.trace_argument(["--torch-trace", "/a", "--torch-trace", "/b"])


def test_base_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    changed = tmp_path / "changed.py"
    changed.write_text("changed\n", encoding="utf-8")
    with pytest.raises(RuntimeError):
        MODULE.verify_base_hash(changed, MODULE.EXPECTED_BASE_SHA256)
