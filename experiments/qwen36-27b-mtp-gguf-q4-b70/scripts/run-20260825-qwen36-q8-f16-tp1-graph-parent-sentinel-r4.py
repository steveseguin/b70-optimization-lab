#!/usr/bin/env python3
"""Fresh R4 wrapper using only emitted candidate graph evidence."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import re
import sys
from typing import Any


HERE = Path(__file__).resolve().parent
R3_SCRIPT = HERE / "run-20260825-qwen36-q8-f16-tp1-graph-parent-sentinel-r3.py"
SPEC = importlib.util.spec_from_file_location("qwen36_graph_parent_sentinel_r3_base", R3_SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import frozen R3 runner: {R3_SCRIPT}")
R3 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = R3
SPEC.loader.exec_module(R3)
BASE = R3.BASE

R4_MANIFEST = BASE.LANE / "data/2026-08-25-qwen36-q8-f16-tp1-graph-parent-sentinel-r4-prereg.json"
R4_CAMPAIGN_ID = "qwen36-q8-f16-tp1-graph-sentinel-20260825-r4"
R4_RUN_ROOT = Path("/mnt/fast-ai/bench-results/qwen36-q8-f16-tp1-graph-sentinel-20260825-r4")
R4_ACK = f"RUN {R4_CAMPAIGN_ID}"


def effective_manifest() -> dict[str, Any]:
    value = copy.deepcopy(R3.effective_manifest())
    delta = R3.R2.ORIGINAL_LOAD_JSON(R4_MANIFEST)
    candidate = delta.get("candidate_gate_delta") or {}
    if not (
        delta.get("campaign_id") == R4_CAMPAIGN_ID
        and delta.get("state") == "preregistered-not-launched"
        and delta.get("lifecycle_delta")
        == {"output_root": str(R4_RUN_ROOT), "exact_ack": R4_ACK}
        and delta.get("control_gate_delta") == "none-from-r3"
        and candidate.get("remove_required_strings")
        == [
            "GGML_SYCL_GRAPH: yes",
            "GGML_SYCL_ENABLE_GRAPH: 1",
            "GGML_SYCL_GRAPH_CACHE_SIZE: 8",
        ]
        and candidate.get("positive_action_markers_and_summary_unchanged") is True
        and delta.get("predecessor", {}).get("terminal_sha256")
        == "809c9b756526d694a97d37df7e40aa6484d652a14d4513094a8560229cad3c50"
        and delta.get("predecessor", {}).get("reuse_any_arm") is False
    ):
        raise BASE.GateError("R4 delta invariant failed")
    value["campaign_id"] = R4_CAMPAIGN_ID
    value["purpose"] = delta["purpose"]
    value["lifecycle"].update(delta["lifecycle_delta"])
    value["r4_delta"] = delta
    return value


def r4_load_json(path: Path) -> dict[str, Any]:
    if path == R4_MANIFEST:
        return effective_manifest()
    return R3.r3_load_json(path)


def validate_candidate_graph_log(text: str) -> dict[str, int]:
    positive_markers = (
        r"\[SYCL-GRAPH\] requested device=0 count=[1-9][0-9]*\b",
        r"\[SYCL-GRAPH\] recording_entered device=0 count=[1-9][0-9]*\b",
        r"\[SYCL-GRAPH\] replayed device=0 count=[1-9][0-9]*\b",
        r"\[SYCL-GRAPH\] direct_replay device=0 count=[1-9][0-9]*\b",
    )
    absent = [pattern for pattern in positive_markers if re.search(pattern, text) is None]
    if absent:
        raise BASE.GateError(f"candidate positive graph-action evidence absent: {absent}")
    summary = BASE.parse_graph_summary(text)
    if summary["device"] != 0:
        raise BASE.GateError(f"candidate graph summary used the wrong device: {summary}")
    if summary["compatibility_rejected"] != 0:
        raise BASE.GateError(f"candidate graph compatibility rejection: {summary}")
    if summary["device_unsupported"] != 0 or summary["cache_limit"] != 8:
        raise BASE.GateError(f"candidate graph device/cache contract failed: {summary}")
    if any(summary[name] <= 0 for name in (
        "requested", "cache_hit", "direct_replay", "recorded", "created", "replayed",
    )):
        raise BASE.GateError(f"candidate requested graph but did not record/replay/cache-hit: {summary}")
    return summary


BASE.CAMPAIGN_ID = R4_CAMPAIGN_ID
BASE.ACK = R4_ACK
BASE.RUN_ROOT = R4_RUN_ROOT
BASE.MANIFEST = R4_MANIFEST
BASE.PACKET_PATHS = R3.BASE.PACKET_PATHS + (
    "experiments/qwen36-27b-mtp-gguf-q4-b70/data/2026-08-25-qwen36-q8-f16-tp1-graph-parent-sentinel-r3-result.json",
    "experiments/qwen36-27b-mtp-gguf-q4-b70/notes/2026-08-25-qwen36-q8-f16-tp1-graph-parent-sentinel-r3-result.md",
    "experiments/qwen36-27b-mtp-gguf-q4-b70/data/2026-08-25-qwen36-q8-f16-tp1-graph-parent-sentinel-r4-prereg.json",
    "experiments/qwen36-27b-mtp-gguf-q4-b70/notes/2026-08-25-qwen36-q8-f16-tp1-graph-parent-sentinel-r4-preregistration.md",
    "experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-q8-f16-tp1-graph-parent-sentinel-r4.py",
    "experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/test_qwen36_q8_f16_tp1_graph_parent_sentinel_r4.py",
)
BASE.load_json = r4_load_json
BASE.validate_candidate_graph_log = validate_candidate_graph_log


if __name__ == "__main__":
    raise SystemExit(BASE.main())
