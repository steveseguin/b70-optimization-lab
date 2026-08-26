#!/usr/bin/env python3
"""Create-only Qwen3.8 Q4_K_XL/F16 TP1 HTTP SYCL-graph 8K sentinel."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
MANIFEST = LANE / "data/2026-08-26-qwen38-q4kxl-f16kv-tp1-target-sycl-graph-8k-sentinel-r1-prereg.json"
VALIDATOR = LANE / "scripts/validate-20260826-qwen38-q4kxl-f16kv-tp1-target-sycl-graph-8k-sentinel-r1.py"
BASE_RUNNER = LANE / "scripts/run-20260826-qwen38-q5ks-f16kv-tp1-target-sycl-graph-8k-sentinel-r1.py"
CAMPAIGN_ID = "qwen38-q4kxl-f16kv-tp1-target-sycl-graph-8k-sentinel-20260826-r1"
ACK = f"RUN {CAMPAIGN_ID}"
ARMS = ("control-graph-off-cache0", "candidate-graph-on-cache20")


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BASE = load_module(BASE_RUNNER, "qwen38_q5_graph_sentinel_base_for_q4kxl")
GateError = BASE.GateError
CORE = BASE.CORE
GRAPH = BASE.GRAPH
EXPECTED_CLEANUP = BASE.EXPECTED_CLEANUP
Execution = BASE.Execution
BASE_LOAD_MANIFEST = BASE.load_manifest
BASE_GRAPH_MANIFEST = BASE.graph_manifest


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GateError(f"JSON root must be object: {path}")
    return value


def resolve(raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else REPO / path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_manifest(value: dict[str, Any]) -> None:
    selectors = value.get("selectors") or {}
    execution = value.get("execution_contract") or {}
    lifecycle = value.get("lifecycle") or {}
    frozen = value.get("frozen_interpretation") or {}
    if not (
        value.get("schema") == "neural.download.qwen38-q4kxl-f16kv-target-sycl-graph-8k-sentinel-prereg.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("state") == "preregistered-not-launched"
        and selectors == {
            "revision": "qwen3.8-27b-current-weights",
            "target_quantization": "UD-Q4_K_XL",
            "tp": 1,
            "mtp": 0,
            "active_context_tokens": 8192,
            "target_kv": "f16",
            "graph_mode": "matched-control sentinel",
            "fit": "off",
            "transport": "HTTP /v1/completions",
        }
        and execution.get("arm_order") == list(ARMS)
        and execution.get("fresh_server_lifetime_per_arm") is True
        and execution.get("only_graph_flags_may_differ_between_arms") is True
        and execution.get("control_environment_delta") == {
            "GGML_SYCL_ENABLE_GRAPH": "0", "GGML_SYCL_GRAPH_CACHE_SIZE": "0"
        }
        and execution.get("candidate_environment_delta") == {
            "GGML_SYCL_ENABLE_GRAPH": "1", "GGML_SYCL_GRAPH_CACHE_SIZE": "20"
        }
        and execution.get("cache_capacity_derivation")
        == "18 observed Q5 HTTP warmup/prefill graph requests plus two recurrent decode shapes from qualified same-architecture Qwen3.6 nonzero-depth evidence"
        and execution.get("no_automatic_capacity_escalation") is True
        and execution.get("require_exact_128_token_output_text_token_ids_usage_and_returned_prompt_parity") is True
        and execution.get("require_cached_tokens_zero") is True
        and execution.get("require_positive_graph_requests_hits_and_direct_replay") is True
        and execution.get("require_minimum_cache_hits_and_direct_replays") == 120
        and execution.get("require_requested_equals_hits_plus_misses_and_replayed") is True
        and execution.get("require_zero_graph_compatibility_device_cache_full_update_or_recreate_events") is True
        and execution.get("candidate_quality_battery") is False
        and lifecycle == {
            "output_root": f"/mnt/fast-ai/bench-results/{CAMPAIGN_ID}",
            "exact_ack": ACK,
            "default_is_inert": True,
            "requires_clean_pushed_main": True,
            "create_only": True,
            "requires_idle_gpu0_render_node": "/dev/dri/by-path/pci-0000:23:00.0-render",
            "required_locks": [
                "/run/lock/muse-glimmer-gpu-exclusive.lock",
                "/tmp/b70-benchmark.lock",
                "/tmp/b70-gpu0.lock",
                "/run/user/1000/qwen36-b70-gpu-leases/gpu0.lock",
            ],
            "request_timeout_seconds": 900,
        }
        and frozen.get("speed_floor") is None
        and frozen.get("site_cells_authorized") == 0
        and frozen.get("sentinel_pass_authorizes_full_curve_preregistration") is True
        and frozen.get("full_graph_curve_authorized") is False
        and frozen.get("failure_stops_same_design_full_curve") is True
        and frozen.get("mtp_or_speculative_cells_authorized") == 0
        and frozen.get("tp2_or_tp4_cells_authorized") == 0
        and frozen.get("headline_or_protected_replacement_authorized") is False
        and frozen.get("protected_decode_values")
        == [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144]
    ):
        raise GateError("Q4_K_XL graph sentinel manifest invariant failed")


def load_manifest() -> dict[str, Any]:
    value = load_json(MANIFEST)
    validate_manifest(value)
    return value


def verify_dependencies(value: dict[str, Any]) -> None:
    for name, row in value["dependencies"].items():
        path = resolve(row["path"])
        if not path.is_file() or sha256_file(path) != row["sha256"]:
            raise GateError(f"sealed dependency changed: {name}: {path}")
    terminal = load_json(resolve(value["dependencies"]["qwen38_graph_off_terminal"]["path"]))
    old_8k = load_json(resolve(value["dependencies"]["qwen38_graph_off_8k_receipt"]["path"]))
    prior_negative = load_json(resolve(value["dependencies"]["preserved_qwen38_q5_negative"]["path"]))
    if not (
        terminal.get("status") == "completed-valid-target-only-q4kxl-f16kv-depth-quality"
        and (terminal.get("authority") or {}).get("target_only_q4kxl_f16_serving_curve_cells") == 7
        and (old_8k.get("gate") or {}).get("passed") is True
    ):
        raise GateError("passed Q4_K_XL graph-off parent invariant failed")
    q5_graph = ((prior_negative.get("arms") or {}).get("candidate_graph_on_cache8") or {}).get("graph_summary") or {}
    if not (
        prior_negative.get("status") == "failed-closed"
        and prior_negative.get("classification") == "correct-output-parity-but-no-graph-cache-reuse"
        and q5_graph.get("cache_hit") == 0
        and q5_graph.get("direct_replay") == 0
        and q5_graph.get("cache_full", 0) > 0
        and (prior_negative.get("authority") or {}).get("graph_cells") == 0
    ):
        raise GateError("preserved Q5 HTTP graph warning changed")


def graph_manifest(value: dict[str, Any]) -> dict[str, Any]:
    manifest = copy.deepcopy(BASE_GRAPH_MANIFEST(BASE_LOAD_MANIFEST()))
    argv = manifest["server_argv"]
    for flag, replacement in (
        ("-m", value["model"]["path"]),
        ("--alias", value["server_contract"]["model_alias"]),
        ("--port", str(value["server_contract"]["port"])),
    ):
        argv[argv.index(flag) + 1] = replacement
    manifest["campaign_id"] = CAMPAIGN_ID
    manifest["model"] = copy.deepcopy(value["model"])
    manifest["server_contract"] = copy.deepcopy(value["server_contract"])
    manifest["fixture"] = copy.deepcopy(value["fixture"])
    manifest["clients"] = copy.deepcopy(value["clients"])
    manifest["lifecycle"] = copy.deepcopy(value["lifecycle"])
    return manifest


def static_check(value: dict[str, Any]) -> dict[str, Any]:
    validate_manifest(value)
    verify_dependencies(value)
    BASE.Q5.static_check(BASE.Q5.load_manifest())
    sealed, _, libraries = GRAPH.static_check()
    model = Path(value["model"]["path"])
    if not model.is_file() or model.is_symlink() or model.stat().st_size != value["model"]["size_bytes"]:
        raise GateError("Q4_K_XL model path/size failed; full hash is execute-only")
    runtime = value["graph_runtime"]
    if not (
        sealed["runtime"]["server"]["path"] == runtime["binary"]
        and sealed["runtime"]["server"]["sha256"] == runtime["binary_sha256"]
        and sealed["runtime"]["server_effective_shared_libraries"]
        == {"count": runtime["effective_dso_count"], "canonical_json_sha256": runtime["effective_dso_canonical_sha256"]}
        and [item["sha256"] for item in sealed["source"]["patch_chain_in_order"]] == runtime["patch_chain_sha256"]
    ):
        raise GateError("sealed graph runtime identity changed")
    fixture = load_json(resolve(value["fixture"]["path"]))
    rows = [row for row in fixture.get("cases", []) if row.get("id") == "depth-8192"]
    if len(rows) != 1 or rows[0].get("prompt_token_ids_sha256") != value["fixture"]["prompt_token_ids_sha256"]:
        raise GateError("8K fixture changed")
    argv = Execution(graph_manifest(value)).server_argv()
    if not (
        argv[argv.index("--spec-type") + 1] == "none"
        and "--spec-draft-model" not in argv
        and argv[argv.index("-ctk") + 1] == "f16"
        and argv[argv.index("-ctv") + 1] == "f16"
        and argv[argv.index("-m") + 1] == value["model"]["path"]
        and "-fit" not in argv
    ):
        raise GateError("target-only Q4_K_XL graph argv invariant failed")
    return {
        "schema": "neural.download.qwen38-q4kxl-f16kv-target-sycl-graph-8k-plan.v1",
        "mode": "check",
        "default_is_inert": True,
        "gpu_actions": 0,
        "network_requests": 0,
        "output_writes": 0,
        "campaign_id": CAMPAIGN_ID,
        "exact_ack": ACK,
        "arms": list(ARMS),
        "fresh_server_lifetimes": 2,
        "site_cells_if_valid": 0,
        "full_curve_authorized": False,
        "curve_preregistration_if_valid": True,
        "known_q5_same_runtime_warning_bound": True,
        "server_argv": argv,
        "effective_dso_count": len(libraries),
    }


# Reuse the audited create-only two-arm lifecycle while replacing every packet
# identity entry point with this Q4_K_XL sentinel.
BASE.MANIFEST = MANIFEST
BASE.VALIDATOR = VALIDATOR
BASE.CAMPAIGN_ID = CAMPAIGN_ID
BASE.ACK = ACK
BASE.ARMS = ARMS
BASE.load_manifest = load_manifest
BASE.validate_manifest = validate_manifest
BASE.verify_dependencies = verify_dependencies
BASE.graph_manifest = graph_manifest
BASE.Execution = Execution
BASE.static_check = static_check


def main() -> int:
    return BASE.main()


if __name__ == "__main__":
    raise SystemExit(main())
