#!/usr/bin/env python3
"""Create-only cache-20 retry of the Qwen3.8 Q5_K_S 8K graph sentinel."""

from __future__ import annotations
import copy, importlib.util, json, sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
MANIFEST = LANE / "data/2026-08-26-qwen38-q5ks-f16kv-tp1-target-sycl-graph-cache20-8k-sentinel-r2-prereg.json"
VALIDATOR = LANE / "scripts/validate-20260826-qwen38-q5ks-f16kv-tp1-target-sycl-graph-cache20-8k-sentinel-r2.py"
BASE_RUNNER = LANE / "scripts/run-20260826-qwen38-q5ks-f16kv-tp1-target-sycl-graph-8k-sentinel-r1.py"
CAMPAIGN_ID = "qwen38-q5ks-f16kv-tp1-target-sycl-graph-cache20-8k-sentinel-20260826-r2"
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

BASE = _load(BASE_RUNNER, "qwen38_q5_graph_cache20_base")
GateError = BASE.GateError
BASE_VALUE = copy.deepcopy(BASE.load_manifest())
BASE_STATIC_CHECK = BASE.static_check
BASE_EXECUTE = BASE.execute
BASE_VERIFY_DEPENDENCIES = BASE.verify_dependencies

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
    failed = value.get("failed_r1_evidence") or {}
    delta = value.get("mechanism_delta") or {}
    lifecycle = value.get("lifecycle") or {}
    acceptance = value.get("acceptance") or {}
    frozen = value.get("frozen_interpretation") or {}
    if not (
        value.get("schema") == "neural.download.qwen38-q5ks-f16kv-target-sycl-graph-cache20-8k-sentinel-overlay.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("state") == "preregistered-not-launched"
        and failed.get("observed") == {"requested":146,"cache_entries":8,"cache_limit":8,"cache_hit":0,"cache_miss":146,"cache_full":138,"direct_replay":0,"recorded":8,"created":8,"replayed":8}
        and failed.get("timing_structure", {}).get("non_decode_graph_requests") == 18
        and failed.get("must_remain_immutable") is True
        and delta.get("candidate_environment") == {"GGML_SYCL_ENABLE_GRAPH":"1","GGML_SYCL_GRAPH_CACHE_SIZE":"20"}
        and delta.get("cache_size") == {"from":8,"to":20}
        and delta.get("source_change") is False and delta.get("binary_change") is False
        and delta.get("maximum_source_supported_cache_size") == 64
        and delta.get("no_automatic_capacity_escalation") is True
        and lifecycle == {"output_root":f"/mnt/fast-ai/bench-results/{CAMPAIGN_ID}","exact_ack":ACK,"default_is_inert":True,"requires_clean_pushed_main":True,"create_only":True,"fresh_server_lifetimes":2}
        and acceptance.get("candidate_cache_limit") == 20
        and acceptance.get("candidate_requested_expected") == 146
        and acceptance.get("candidate_cache_full") == 0
        and acceptance.get("candidate_minimum_cache_hit_and_direct_replay") == 120
        and acceptance.get("speed_floor") is None
        and frozen.get("site_cells_authorized") == 0
        and frozen.get("full_graph_curve_authorized") is False
        and frozen.get("full_curve_preregistration_authorized_only_on_pass") is True
        and frozen.get("protected_decode_values") == [71.45427094575045,30.329809361830037,49.05894025767351,71.9001988117144]
    ):
        raise GateError("cache-20 overlay invariant failed")
    return value

def _verify_refs(overlay: dict[str, Any]) -> None:
    for group in ("sealed_base_packet", "failed_r1_evidence"):
        for name, row in overlay[group].items():
            if not isinstance(row, dict) or "path" not in row:
                continue
            path = _resolve(row["path"])
            if not path.is_file() or BASE.sha256_file(path) != row["sha256"]:
                raise GateError(f"sealed cache-20 dependency changed: {group}.{name}: {path}")
    result = _json(_resolve(overlay["failed_r1_evidence"]["result"]["path"]))
    graph = result.get("arms", {}).get("candidate_graph_on_cache8", {}).get("graph_summary")
    observed = overlay["failed_r1_evidence"]["observed"]
    if (result.get("status") != "failed-closed" or not isinstance(graph, dict)
            or any(graph.get(key) != item for key, item in observed.items())
            or any(graph.get(key) != 0 for key in ("compatibility_rejected", "device_unsupported", "updated", "recreated"))):
        raise GateError("failed cache-8 mechanism evidence changed")

def load_manifest() -> dict[str, Any]:
    overlay = load_overlay()
    value = copy.deepcopy(BASE_VALUE)
    value["schema"] = "neural.download.qwen38-q5ks-f16kv-target-sycl-graph-cache20-8k-sentinel-prereg.v1"
    value["campaign_id"] = CAMPAIGN_ID
    value["purpose"] = overlay["purpose"]
    value["execution_contract"]["arm_order"] = list(ARMS)
    value["execution_contract"]["candidate_environment_delta"] = copy.deepcopy(overlay["mechanism_delta"]["candidate_environment"])
    value["lifecycle"].update({key: overlay["lifecycle"][key] for key in ("output_root", "exact_ack")})
    value["failed_r1_evidence"] = copy.deepcopy(overlay["failed_r1_evidence"])
    value["mechanism_delta"] = copy.deepcopy(overlay["mechanism_delta"])
    value["acceptance"] = copy.deepcopy(overlay["acceptance"])
    value["frozen_interpretation"] = copy.deepcopy(overlay["frozen_interpretation"])
    validate_manifest(value)
    return value

def validate_manifest(value: dict[str, Any]) -> None:
    if not (
        value.get("schema") == "neural.download.qwen38-q5ks-f16kv-target-sycl-graph-cache20-8k-sentinel-prereg.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("selectors") == BASE_VALUE["selectors"]
        and value.get("model") == BASE_VALUE["model"]
        and value.get("graph_runtime") == BASE_VALUE["graph_runtime"]
        and value.get("server_contract") == BASE_VALUE["server_contract"]
        and value.get("fixture") == BASE_VALUE["fixture"]
        and value.get("clients") == BASE_VALUE["clients"]
        and value.get("execution_contract", {}).get("arm_order") == list(ARMS)
        and value.get("execution_contract", {}).get("control_environment_delta") == {"GGML_SYCL_ENABLE_GRAPH":"0","GGML_SYCL_GRAPH_CACHE_SIZE":"0"}
        and value.get("execution_contract", {}).get("candidate_environment_delta") == {"GGML_SYCL_ENABLE_GRAPH":"1","GGML_SYCL_GRAPH_CACHE_SIZE":"20"}
        and value.get("lifecycle", {}).get("output_root") == f"/mnt/fast-ai/bench-results/{CAMPAIGN_ID}"
        and value.get("lifecycle", {}).get("exact_ack") == ACK
        and value.get("lifecycle", {}).get("default_is_inert") is True
        and value.get("lifecycle", {}).get("requires_clean_pushed_main") is True
        and value.get("lifecycle", {}).get("create_only") is True
    ):
        raise GateError("cache-20 synthesized manifest invariant failed")
    reconstructed = copy.deepcopy(value)
    reconstructed["schema"] = BASE_VALUE["schema"]
    reconstructed["campaign_id"] = BASE_VALUE["campaign_id"]
    reconstructed["purpose"] = BASE_VALUE["purpose"]
    reconstructed["execution_contract"] = copy.deepcopy(BASE_VALUE["execution_contract"])
    reconstructed["lifecycle"] = copy.deepcopy(BASE_VALUE["lifecycle"])
    reconstructed["frozen_interpretation"] = copy.deepcopy(BASE_VALUE["frozen_interpretation"])
    for key in ("failed_r1_evidence", "mechanism_delta", "acceptance"):
        reconstructed.pop(key)
    if reconstructed != BASE_VALUE:
        raise GateError("cache-20 packet changes more than campaign identity and graph capacity")

def verify_dependencies(value: dict[str, Any]) -> None:
    _verify_refs(load_overlay())
    BASE_VERIFY_DEPENDENCIES(value)

def static_check(value: dict[str, Any]) -> dict[str, Any]:
    validate_manifest(value)
    _verify_refs(load_overlay())
    plan = BASE_STATIC_CHECK(value)
    source = Path(value["graph_runtime"]["source_path"]) / "ggml/src/ggml-sycl/ggml-sycl.cpp"
    text = source.read_text(encoding="utf-8")
    if "std::min(g_ggml_sycl_graph_cache_size, 64)" not in text or "GGML_SYCL_Q8_MEMO_SLOTS * static_cast<size_t>(g_ggml_sycl_graph_cache_size)" not in text:
        raise GateError("sealed source no longer supports capacity-scaled cache 20")
    plan.update({"schema":"neural.download.qwen38-q5ks-f16kv-target-sycl-graph-cache20-8k-plan.v1","campaign_id":CAMPAIGN_ID,"exact_ack":ACK,"arms":list(ARMS),"candidate_cache_limit":20,"minimum_direct_replays":120})
    return plan

BASE.MANIFEST = MANIFEST
BASE.VALIDATOR = VALIDATOR
BASE.CAMPAIGN_ID = CAMPAIGN_ID
BASE.ACK = ACK
BASE.ARMS = ARMS
BASE.load_manifest = load_manifest
BASE.validate_manifest = validate_manifest
BASE.verify_dependencies = verify_dependencies
BASE.static_check = static_check

Execution = BASE.Execution
GRAPH = BASE.GRAPH
EXPECTED_CLEANUP = BASE.EXPECTED_CLEANUP

def execute(value: dict[str, Any]) -> Path:
    return BASE_EXECUTE(value)

def main() -> int:
    return BASE.main()

if __name__ == "__main__":
    raise SystemExit(main())
