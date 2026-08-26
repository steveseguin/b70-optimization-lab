#!/usr/bin/env python3
"""Q4_K_XL cache20 graph sentinel with a cache20-aware report parser."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
MANIFEST = LANE / "data/2026-08-26-qwen38-q4kxl-f16kv-tp1-target-sycl-graph-cache20-8k-sentinel-r2-prereg.json"
VALIDATOR = LANE / "scripts/validate-20260826-qwen38-q4kxl-f16kv-tp1-target-sycl-graph-cache20-8k-sentinel-r2.py"
R1_RUNNER = LANE / "scripts/run-20260826-qwen38-q4kxl-f16kv-tp1-target-sycl-graph-8k-sentinel-r1.py"
CAMPAIGN_ID = "qwen38-q4kxl-f16kv-tp1-target-sycl-graph-cache20-8k-sentinel-20260826-r2"
ACK = f"RUN {CAMPAIGN_ID}"
ARMS = ("control-graph-off-cache0", "candidate-graph-on-cache20")


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


R1 = _load(R1_RUNNER, "qwen38_q4kxl_graph_cache20_r1_base")
Q5_BASE = R1.BASE
GateError = R1.GateError
GRAPH = R1.GRAPH
Execution = R1.Execution
EXPECTED_CLEANUP = R1.EXPECTED_CLEANUP
R1_VALUE = copy.deepcopy(R1.load_manifest())
R1_GRAPH_TEMPLATE = copy.deepcopy(R1.graph_manifest(R1_VALUE))
R1_STATIC_CHECK = R1.static_check
R1_VERIFY_DEPENDENCIES = R1.verify_dependencies


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GateError(f"JSON root must be object: {path}")
    return value


def _resolve(raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else REPO / path


def load_overlay() -> dict[str, Any]:
    value = _json(MANIFEST)
    delta = value.get("reporting_delta") or {}
    lifecycle = value.get("lifecycle") or {}
    frozen = value.get("frozen_interpretation") or {}
    if not (
        value.get("schema") == "neural.download.qwen38-q4kxl-f16kv-target-sycl-graph-cache20-8k-sentinel-reporting-overlay.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("state") == "preregistered-not-launched"
        and delta == {
            "classification": "report-only parser correction before first launch",
            "configured_candidate_cache_limit": 20,
            "old_inherited_constant": 8,
            "parse_exact_emitted_counters": True,
            "require_one_summary": True,
            "runtime_source_change": False,
            "runtime_binary_change": False,
            "model_change": False,
            "workload_change": False,
            "graph_environment_change": False,
        }
        and lifecycle == {
            "output_root": f"/mnt/fast-ai/bench-results/{CAMPAIGN_ID}",
            "exact_ack": ACK,
            "default_is_inert": True,
            "requires_clean_pushed_main": True,
            "create_only": True,
            "fresh_server_lifetimes": 2,
        }
        and frozen.get("speed_floor") is None
        and frozen.get("site_cells_authorized") == 0
        and frozen.get("full_graph_curve_authorized") is False
        and frozen.get("full_curve_preregistration_authorized_only_on_pass") is True
        and frozen.get("protected_decode_values")
        == [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144]
    ):
        raise GateError("Q4_K_XL cache20 reporting overlay invariant failed")
    for name, row in value["sealed_r1_packet"].items():
        path = _resolve(row["path"])
        if not path.is_file() or R1.sha256_file(path) != row["sha256"]:
            raise GateError(f"sealed R1 packet changed: {name}: {path}")
    return value


def load_manifest() -> dict[str, Any]:
    overlay = load_overlay()
    value = copy.deepcopy(R1_VALUE)
    value["schema"] = "neural.download.qwen38-q4kxl-f16kv-target-sycl-graph-cache20-8k-sentinel-prereg.v2"
    value["campaign_id"] = CAMPAIGN_ID
    value["lifecycle"]["output_root"] = overlay["lifecycle"]["output_root"]
    value["lifecycle"]["exact_ack"] = ACK
    value["reporting_delta"] = copy.deepcopy(overlay["reporting_delta"])
    value["sealed_r1_packet"] = copy.deepcopy(overlay["sealed_r1_packet"])
    value["frozen_interpretation"] = copy.deepcopy(overlay["frozen_interpretation"])
    validate_manifest(value)
    return value


def validate_manifest(value: dict[str, Any]) -> None:
    if not (
        value.get("schema") == "neural.download.qwen38-q4kxl-f16kv-target-sycl-graph-cache20-8k-sentinel-prereg.v2"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("lifecycle", {}).get("output_root") == f"/mnt/fast-ai/bench-results/{CAMPAIGN_ID}"
        and value.get("lifecycle", {}).get("exact_ack") == ACK
        and value.get("execution_contract", {}).get("candidate_environment_delta")
        == {"GGML_SYCL_ENABLE_GRAPH": "1", "GGML_SYCL_GRAPH_CACHE_SIZE": "20"}
        and value.get("reporting_delta") == load_overlay()["reporting_delta"]
        and value.get("sealed_r1_packet") == load_overlay()["sealed_r1_packet"]
    ):
        raise GateError("Q4_K_XL cache20 synthesized manifest invariant failed")
    reconstructed = copy.deepcopy(value)
    reconstructed["schema"] = R1_VALUE["schema"]
    reconstructed["campaign_id"] = R1_VALUE["campaign_id"]
    reconstructed["lifecycle"] = copy.deepcopy(R1_VALUE["lifecycle"])
    reconstructed["frozen_interpretation"] = copy.deepcopy(R1_VALUE["frozen_interpretation"])
    reconstructed.pop("reporting_delta")
    reconstructed.pop("sealed_r1_packet")
    if reconstructed != R1_VALUE:
        raise GateError("R2 changes more than report parsing and lifecycle identity")


def verify_dependencies(value: dict[str, Any]) -> None:
    load_overlay()
    R1_VERIFY_DEPENDENCIES(value)


def graph_manifest(value: dict[str, Any]) -> dict[str, Any]:
    manifest = copy.deepcopy(R1_GRAPH_TEMPLATE)
    manifest["campaign_id"] = CAMPAIGN_ID
    for key in ("model", "server_contract", "fixture", "clients", "lifecycle"):
        manifest[key] = copy.deepcopy(value[key])
    return manifest


def graph_evidence_cache20(text: str) -> dict[str, int]:
    rows = [
        {key: int(item) for key, item in match.groupdict().items()}
        for match in GRAPH.CURVE.R1.SUMMARY_RE.finditer(text)
    ]
    if len(rows) != 1:
        raise GateError(f"expected exactly one SYCL graph summary, observed {len(rows)}")
    row = rows[0]
    result = dict(row)
    result["summary_count"] = 1
    if not (
        row["device"] == 0
        and row["cache_limit"] == 20
        and row["compatibility_rejected"] == 0
        and row["device_unsupported"] == 0
        and row["requested"] > 0
        and row["recorded"] > 0
        and row["created"] > 0
        and row["direct_replay"] > 0
        and row["replayed"] > 0
    ):
        raise GateError("server cache20 graph mechanism evidence failed")
    return result


def static_check(value: dict[str, Any]) -> dict[str, Any]:
    validate_manifest(value)
    plan = R1_STATIC_CHECK(value)
    plan.update(
        {
            "schema": "neural.download.qwen38-q4kxl-f16kv-target-sycl-graph-cache20-8k-plan.v2",
            "campaign_id": CAMPAIGN_ID,
            "exact_ack": ACK,
            "report_parser_cache_limit": 20,
            "runtime_changes": 0,
        }
    )
    return plan


for module in (R1, Q5_BASE):
    module.MANIFEST = MANIFEST
    module.VALIDATOR = VALIDATOR
    module.CAMPAIGN_ID = CAMPAIGN_ID
    module.ACK = ACK
    module.ARMS = ARMS
    module.load_manifest = load_manifest
    module.validate_manifest = validate_manifest
    module.verify_dependencies = verify_dependencies
    module.graph_manifest = graph_manifest
    module.Execution = Execution
    module.static_check = static_check

GRAPH.IMPL.F16.graph_evidence = graph_evidence_cache20


def main() -> int:
    return Q5_BASE.main()


if __name__ == "__main__":
    raise SystemExit(main())
