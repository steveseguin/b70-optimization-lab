import importlib.util
import json
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).with_name("verify-q38-a48-fullgraph-runtime.py")
SPEC = importlib.util.spec_from_file_location("q38_a48_runtime", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_exact_algorithm_is_preserved() -> None:
    environment = {"CCL_SYCL_ALLREDUCE_LL": "twoshots"}
    assert MODULE.normalize_algorithm_identity(environment) == environment


def test_consumed_algorithm_is_normalized() -> None:
    assert MODULE.normalize_algorithm_identity({}) == {
        "CCL_SYCL_ALLREDUCE_LL": "twoshots"
    }


@pytest.mark.parametrize("value", ["ring", "ring_markers", "recursive_doubling"])
def test_conflicting_algorithm_is_rejected(value: str) -> None:
    with pytest.raises(MODULE.BASE.BASE.BASE.CORE.VerificationError):
        MODULE.normalize_algorithm_identity({"CCL_SYCL_ALLREDUCE_LL": value})


def test_algorithm_log_receipt_is_required(tmp_path: Path) -> None:
    log = tmp_path / "server.log"
    log.write_text(MODULE.ALGORITHM_LOG_RECEIPT + "\n", encoding="utf-8")
    MODULE.validate_algorithm_log(log)
    log.write_text("no selector receipt\n", encoding="utf-8")
    with pytest.raises(MODULE.BASE.BASE.BASE.CORE.VerificationError):
        MODULE.validate_algorithm_log(log)


def test_collective_error_is_rejected(tmp_path: Path) -> None:
    log = tmp_path / "server.log"
    log.write_text(
        MODULE.ALGORITHM_LOG_RECEIPT + "\n2026 |CCL_ERROR| failure\n",
        encoding="utf-8",
    )
    with pytest.raises(MODULE.BASE.BASE.BASE.CORE.VerificationError):
        MODULE.validate_algorithm_log(log)


def test_output_is_annotated_atomically(tmp_path: Path) -> None:
    output = tmp_path / "result.json"
    output.write_text(json.dumps({"status": "passed", "phase": "after"}))
    MODULE.annotate_output(output)
    result = json.loads(output.read_text())
    assert result["ccl_sycl_allreduce_ll"] == "twoshots"


def test_argument_path_is_exact() -> None:
    assert MODULE.argument_path(["--output", "/result"], "--output") == Path("/result")
    with pytest.raises(RuntimeError):
        MODULE.argument_path([], "--output")
    with pytest.raises(RuntimeError):
        MODULE.argument_path(["--output", "/a", "--output", "/b"], "--output")


def test_base_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    changed = tmp_path / "changed.py"
    changed.write_text("changed\n", encoding="utf-8")
    with pytest.raises(RuntimeError):
        MODULE.verify_base_hash(changed, MODULE.EXPECTED_BASE_SHA256)
