#!/usr/bin/env python3
"""Fresh R3 wrapper with the observed graph-off summary as control authority."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import sys
from typing import Any


HERE = Path(__file__).resolve().parent
R2_SCRIPT = HERE / "run-20260825-qwen36-q8-f16-tp1-graph-parent-sentinel-r2.py"
SPEC = importlib.util.spec_from_file_location("qwen36_graph_parent_sentinel_r2_base", R2_SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import frozen R2 runner: {R2_SCRIPT}")
R2 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = R2
SPEC.loader.exec_module(R2)
BASE = R2.BASE

R3_MANIFEST = BASE.LANE / "data/2026-08-25-qwen36-q8-f16-tp1-graph-parent-sentinel-r3-prereg.json"
R3_CAMPAIGN_ID = "qwen36-q8-f16-tp1-graph-sentinel-20260825-r3"
R3_RUN_ROOT = Path("/mnt/fast-ai/bench-results/qwen36-q8-f16-tp1-graph-sentinel-20260825-r3")
R3_ACK = f"RUN {R3_CAMPAIGN_ID}"


def effective_manifest() -> dict[str, Any]:
    value = copy.deepcopy(R2.effective_manifest())
    delta = R2.ORIGINAL_LOAD_JSON(R3_MANIFEST)
    if not (
        delta.get("campaign_id") == R3_CAMPAIGN_ID
        and delta.get("state") == "preregistered-not-launched"
        and delta.get("lifecycle_delta")
        == {"output_root": str(R3_RUN_ROOT), "exact_ack": R3_ACK}
        and delta.get("candidate_gate_delta") == "none"
        and delta.get("predecessor", {}).get("terminal_sha256")
        == "36d1a596adf882c73b6d1411c57c699229601cd34749d041c178fe25ac67cec1"
        and delta.get("predecessor", {}).get("reuse_any_arm") is False
    ):
        raise BASE.GateError("R3 delta invariant failed")
    control = delta.get("control_gate_delta") or {}
    if not (
        control.get("remove_required_strings")
        == [
            "GGML_SYCL_GRAPH: yes",
            "GGML_SYCL_ENABLE_GRAPH: 0",
            "GGML_SYCL_GRAPH_CACHE_SIZE: 0",
        ]
        and control.get("require_exactly_one_compile_guarded_summary") is True
        and control.get("require_device") == 0
        and control.get("require_all_counters_and_cache_limit_zero") is True
    ):
        raise BASE.GateError("R3 control-gate delta changed")
    value["campaign_id"] = R3_CAMPAIGN_ID
    value["purpose"] = delta["purpose"]
    value["lifecycle"].update(delta["lifecycle_delta"])
    value["r3_delta"] = delta
    return value


def r3_load_json(path: Path) -> dict[str, Any]:
    if path == R3_MANIFEST:
        return effective_manifest()
    return R2.r2_load_json(path)


def validate_control_graph_log(text: str) -> dict[str, int]:
    summary = BASE.parse_graph_summary(text)
    forbidden = (
        "[SYCL-GRAPH] requested", "[SYCL-GRAPH] recording_entered",
        "[SYCL-GRAPH] replayed", "[SYCL-GRAPH] direct_replay",
    )
    leaked = [marker for marker in forbidden if marker in text]
    if leaked:
        raise BASE.GateError(f"graph-off control emitted graph-action markers: {leaked}")
    if summary["device"] != 0:
        raise BASE.GateError(f"graph-off control summary used the wrong device: {summary}")
    if any(summary[name] != 0 for name in (
        "requested", "compatibility_rejected", "device_unsupported", "cache_entries",
        "cache_limit", "cache_hit", "cache_miss", "cache_full", "direct_replay",
        "recorded", "created", "updated", "recreated", "replayed",
    )):
        raise BASE.GateError(f"graph-off control executed graph work: {summary}")
    return summary


BASE.CAMPAIGN_ID = R3_CAMPAIGN_ID
BASE.ACK = R3_ACK
BASE.RUN_ROOT = R3_RUN_ROOT
BASE.MANIFEST = R3_MANIFEST
BASE.PACKET_PATHS = R2.BASE.PACKET_PATHS + (
    "experiments/qwen36-27b-mtp-gguf-q4-b70/data/2026-08-25-qwen36-q8-f16-tp1-graph-parent-sentinel-r2-result.json",
    "experiments/qwen36-27b-mtp-gguf-q4-b70/notes/2026-08-25-qwen36-q8-f16-tp1-graph-parent-sentinel-r2-result.md",
    "experiments/qwen36-27b-mtp-gguf-q4-b70/data/2026-08-25-qwen36-q8-f16-tp1-graph-parent-sentinel-r3-prereg.json",
    "experiments/qwen36-27b-mtp-gguf-q4-b70/notes/2026-08-25-qwen36-q8-f16-tp1-graph-parent-sentinel-r3-preregistration.md",
    "experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-q8-f16-tp1-graph-parent-sentinel-r3.py",
    "experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/test_qwen36_q8_f16_tp1_graph_parent_sentinel_r3.py",
)
BASE.load_json = r3_load_json
BASE.validate_control_graph_log = validate_control_graph_log


if __name__ == "__main__":
    raise SystemExit(BASE.main())
