from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).with_name("census-q38-bf16-grouped-a5.py")
SPEC = importlib.util.spec_from_file_location("q38_bf16_grouped_a5", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def fake_authority(cell: dict) -> dict:
    return {
        "model": "Qwen/Qwen3.8-Flash-Next-FP8",
        "model_revision": "revision",
        "input_sha256": "input",
        "input_row_sha256": [f"input-row-{row}" for row in range(MODULE.ROWS)],
        "weight_sha256": "logical",
        "sentinel": {"id": cell["sentinel"]},
        "source_tensors": ["tensor"],
        "checkpoint_shards": ["shard"],
    }


def fake_candidate(replica: int, row_hash: str = "supported") -> dict:
    cell = MODULE.canonical_cells()[0]
    authority = fake_authority(cell)
    return {
        "schema": MODULE.A5_CELL_SCHEMA,
        "status": "classified",
        "classification": MODULE.A5_CELL_CLASSIFICATION,
        "identity": {
            "model": authority["model"],
            "model_revision": authority["model_revision"],
            "a1_tool_sha256": MODULE.A1_TOOL_SHA256,
            "a4a_tool_sha256": MODULE.A4A_TOOL_SHA256,
            "a4a_summary_sha256": MODULE.A4A_SUMMARY_SHA256,
            "family": cell["family"],
            "sentinel": authority["sentinel"],
            "cell_index": cell["cell_index"],
            "replica": replica,
            "provider": "xe2-grouped-w16a16",
            "input_seed": MODULE.INPUT_SEED,
            "input_sha256": authority["input_sha256"],
            "input_row_sha256": authority["input_row_sha256"],
            "logical_weight_sha256": authority["weight_sha256"],
            "grouped_weight_sha256": "a" * 64,
            "source_tensors": authority["source_tensors"],
            "checkpoint_shards": authority["checkpoint_shards"],
            "runtime_stage": str(MODULE.RUNTIME_STAGE),
            "runtime_manifest_sha256": MODULE.RUNTIME_MANIFEST_SHA256,
            "runtime_manifest": {"runtime": "hash"},
            "environment": MODULE.A5_ENVIRONMENT,
        },
        "shape": MODULE.expected_shape(cell),
        "protocol": MODULE.A5_PROTOCOL,
        "candidate": {
            "sweep_full_sha256": ["full"] * MODULE.SWEEPS,
            "sweep_active_sha256": ["aggregate"] * MODULE.SWEEPS,
            "sweep_tail_sha256": ["tail"] * MODULE.SWEEPS,
            "unique_full_sha256": ["full"],
            "unique_active_sha256": ["aggregate"],
            "unique_tail_sha256": ["tail"],
            "row_full_sha256_values": [["full-row"] for _ in range(MODULE.ROWS)],
            "row_active_sha256_values": [[row_hash] for _ in range(MODULE.ROWS)],
            "row_tail_sha256_values": [["tail-row"] for _ in range(MODULE.ROWS)],
            "all_tail_numeric_zero": True,
        },
        "latency": {"median": 2560.0},
        "diagnostic_errors": [],
        "credit": MODULE.A5_CREDIT,
    }


def classify(candidates: list[dict], support: list[set[str]]) -> dict:
    cell = MODULE.canonical_cells()[0]
    return MODULE.classify_cell(
        cell,
        candidates,
        support,
        fake_authority(cell),
        {"runtime": "hash"},
    )


def test_exact_four_cell_contract() -> None:
    cells = MODULE.canonical_cells()
    assert len(cells) == 4
    assert [
        (
            cell["family"],
            cell["sentinel"],
            cell["k"],
            cell["logical_n"],
            cell["active_n"],
            cell["grouped_n"],
            cell["calls_per_token"],
        )
        for cell in cells
    ] == [
        ("hc_down_inject", "layer00-attn-r0", 10240, 336, 324, 352, 96),
        ("hc_down_inject", "layer47-mlp-r3", 10240, 336, 324, 352, 96),
        ("final_hc_down", "final-r0", 10240, 320, 320, 320, 1),
        ("final_hc_down", "final-r3", 10240, 320, 320, 320, 1),
    ]


def test_reliability_plan_is_eight_grouped_processes() -> None:
    plan = MODULE.reliability_plan()
    assert len(plan) == 8
    assert {item["provider"] for item in plan} == {"grouped"}
    assert all(
        [item["replica"] for item in plan if item["cell_index"] == index] == [1, 2]
        for index in range(4)
    )


def test_stage2_is_frozen_nggn_after_stage1() -> None:
    plan = MODULE.stage2_timing_plan()
    assert len(plan) == 16
    for cell_index in range(4):
        cell = [item for item in plan if item["cell_index"] == cell_index]
        assert [(item["provider"], item["replica"]) for item in cell] == [
            ("native", 1),
            ("grouped", 1),
            ("grouped", 2),
            ("native", 2),
        ]
        assert [item["position"] for item in cell] == [1, 2, 3, 4]


def test_candidate_path_is_separate_from_w13_and_a4a() -> None:
    path = MODULE.candidate_path(MODULE.canonical_cells()[0], 1)
    assert str(path).startswith(str(MODULE.A5_ROOT))
    assert "w13" not in str(path).lower()
    assert not str(path).startswith(str(MODULE.A4A_ROOT))
    assert MODULE.A5_TIMING_ROOT != MODULE.A5_ROOT


def test_supported_stable_candidates_pass() -> None:
    support = [{"supported"} for _ in range(MODULE.ROWS)]
    result = classify([fake_candidate(1), fake_candidate(2)], support)
    assert result["parity_pass"] is True
    assert result["missing_native_support_rows"] == []


def test_same_row_native_support_is_mandatory() -> None:
    support = [{"supported"} for _ in range(MODULE.ROWS)]
    first = fake_candidate(1)
    second = fake_candidate(2)
    first["candidate"]["row_active_sha256_values"][17] = ["unsupported"]
    second["candidate"]["row_active_sha256_values"][17] = ["unsupported"]
    result = classify([first, second], support)
    assert result["parity_pass"] is False
    assert result["missing_native_support_rows"] == [17]


def test_cross_process_exactness_is_mandatory() -> None:
    support = [{"supported", "alternate"} for _ in range(MODULE.ROWS)]
    first = fake_candidate(1)
    second = fake_candidate(2)
    second["candidate"]["row_active_sha256_values"][23] = ["alternate"]
    result = classify([first, second], support)
    assert result["candidate_active_rows_exact_across_processes"] is False
    assert result["parity_pass"] is False


def test_one_physical_d_hash_across_processes_is_mandatory() -> None:
    support = [{"supported"} for _ in range(MODULE.ROWS)]
    first = fake_candidate(1)
    second = fake_candidate(2)
    second["candidate"]["unique_full_sha256"] = ["other-full"]
    second["candidate"]["sweep_full_sha256"] = ["other-full"] * MODULE.SWEEPS
    result = classify([first, second], support)
    assert result["candidate_physical_d_exact_across_processes"] is False
    assert result["parity_pass"] is False


def test_wrong_record_identity_cannot_pass() -> None:
    support = [{"supported"} for _ in range(MODULE.ROWS)]
    first = fake_candidate(1)
    second = fake_candidate(2)
    second["identity"]["provider"] = "wrong-provider"
    result = classify([first, second], support)
    assert result["candidate_contracts_pass"] is False
    assert result["parity_pass"] is False


def test_duplicate_replica_cannot_pass() -> None:
    support = [{"supported"} for _ in range(MODULE.ROWS)]
    first = fake_candidate(1)
    duplicate = fake_candidate(1)
    result = classify([first, duplicate], support)
    assert result["replica_set_exact"] is False
    assert result["parity_pass"] is False


def test_zero_tail_is_mandatory() -> None:
    support = [{"supported"} for _ in range(MODULE.ROWS)]
    first = fake_candidate(1)
    second = fake_candidate(2)
    second["candidate"]["all_tail_numeric_zero"] = False
    result = classify([first, second], support)
    assert result["tails_exact_numeric_zero"] is False
    assert result["parity_pass"] is False


def test_stage2_requires_complete_parity_and_empty_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(MODULE, "A5_TIMING_ROOT", tmp_path / "timing")
    passing = {
        "schema": "neural.download.qwen38-flash-next.bf16-grouped-a5-summary.v1",
        "status": "parity_passed",
        "all_four_cells_pass": True,
        "stage2_timing_eligible": True,
        "processes": {"planned": 8, "completed": 8},
    }
    MODULE.validate_stage2_prerequisite(passing)
    passing["status"] = "bounded_negative"
    with pytest.raises(RuntimeError, match="does not authorize"):
        MODULE.validate_stage2_prerequisite(passing)


def test_atomic_write_refuses_overwrite(tmp_path: Path) -> None:
    path = tmp_path / "result.json"
    MODULE.atomic_write(path, {"first": True})
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        MODULE.atomic_write(path, {"second": True})


class FakeA1:
    def __init__(self, receipts: list[dict | BaseException]) -> None:
        self.receipts = iter(receipts)

    def validate_admission(self) -> dict:
        value = next(self.receipts)
        if isinstance(value, BaseException):
            raise value
        return value

    def verify_static_identity(self) -> None:
        return None

    def refuse_active_accelerator_owner(self) -> None:
        return None


def prepare_empty_plan(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_a1: FakeA1
) -> Path:
    root = tmp_path / "a5"
    monkeypatch.setattr(MODULE, "A5_ROOT", root)
    monkeypatch.setattr(MODULE, "load_a1", lambda: fake_a1)
    monkeypatch.setattr(MODULE, "verify_a4a_source", lambda: {})
    monkeypatch.setattr(MODULE, "verify_runtime_stage", lambda: {})
    monkeypatch.setattr(MODULE, "reliability_plan", lambda: [])
    monkeypatch.setattr(
        MODULE,
        "summarize",
        lambda root: {
            "schema": "neural.download.qwen38-flash-next.bf16-grouped-a5-summary.v1",
            "status": "parity_passed",
        },
    )
    monkeypatch.setenv(MODULE.AUTHORITY_ENV, "YES")
    return root


def test_final_admission_exception_writes_failure_without_passing_summary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    initial = {"aer_event_count": 0}
    root = prepare_empty_plan(
        monkeypatch,
        tmp_path,
        FakeA1([initial, RuntimeError("final admission failed"), initial]),
    )
    with pytest.raises(RuntimeError, match="preserving failure and final health"):
        MODULE.run_plan()
    failure = json.loads((root / "failure.json").read_text())
    assert failure["failure_location"]["stage"] == "final_health"
    assert failure["primary_error"]["message"] == "final admission failed"
    assert failure["passing_summary_absent"] is True
    assert not (root / "summary.json").exists()


def test_late_aer_writes_failure_without_passing_summary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    initial = {"aer_event_count": 0}
    late = {"aer_event_count": 1}
    root = prepare_empty_plan(
        monkeypatch,
        tmp_path,
        FakeA1([initial, late, late]),
    )
    with pytest.raises(RuntimeError, match="preserving failure and final health"):
        MODULE.run_plan()
    failure = json.loads((root / "failure.json").read_text())
    assert failure["failure_location"]["stage"] == "final_health"
    assert failure["primary_error"]["message"] == "new AER event across A5 plan"
    assert failure["final_health"]["status"] == "error"
    assert failure["passing_summary_absent"] is True
    assert not (root / "summary.json").exists()
