#!/usr/bin/env python3
"""Fresh R5 wrapper freezing local launch identity across postflight."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import sys
from typing import Any, Mapping


HERE = Path(__file__).resolve().parent
R4_SCRIPT = HERE / "run-20260825-qwen36-q8-f16-tp1-graph-parent-sentinel-r4.py"
SPEC = importlib.util.spec_from_file_location("qwen36_graph_parent_sentinel_r4_base", R4_SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import frozen R4 runner: {R4_SCRIPT}")
R4 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = R4
SPEC.loader.exec_module(R4)
BASE = R4.BASE
ORIGINAL_VERIFY = BASE.verify_clean_pushed_main

R5_MANIFEST = BASE.LANE / "data/2026-08-25-qwen36-q8-f16-tp1-graph-parent-sentinel-r5-prereg.json"
R5_CAMPAIGN_ID = "qwen36-q8-f16-tp1-graph-sentinel-20260825-r5"
R5_RUN_ROOT = Path("/mnt/fast-ai/bench-results/qwen36-q8-f16-tp1-graph-sentinel-20260825-r5")
R5_ACK = f"RUN {R5_CAMPAIGN_ID}"


def effective_manifest() -> dict[str, Any]:
    value = copy.deepcopy(R4.effective_manifest())
    delta = R4.R3.R2.ORIGINAL_LOAD_JSON(R5_MANIFEST)
    policy = delta.get("postflight_remote_policy") or {}
    if not (
        delta.get("campaign_id") == R5_CAMPAIGN_ID
        and delta.get("state") == "preregistered-not-launched"
        and delta.get("lifecycle_delta")
        == {"output_root": str(R5_RUN_ROOT), "exact_ack": R5_ACK}
        and delta.get("graph_and_parity_delta") == "none-from-r4"
        and policy.get("live_origin_equality_required_prelaunch") is True
        and policy.get("local_launch_head_and_packet_blobs_frozen_postlaunch") is True
        and policy.get("live_origin_equality_required_postlaunch") is False
        and delta.get("predecessor", {}).get("terminal_sha256")
        == "16d41c9752778227f079ece3838299a81b5510913a806079652a57ac48871e8e"
        and delta.get("predecessor", {}).get("reuse_any_arm") is False
    ):
        raise BASE.GateError("R5 delta invariant failed")
    value["campaign_id"] = R5_CAMPAIGN_ID
    value["purpose"] = delta["purpose"]
    value["lifecycle"].update(delta["lifecycle_delta"])
    value["r5_delta"] = delta
    return value


def r5_load_json(path: Path) -> dict[str, Any]:
    if path == R5_MANIFEST:
        return effective_manifest()
    return R4.r4_load_json(path)


def verify_clean_pushed_main(
    *, expected_head: str | None = None,
    expected_packet_blobs: Mapping[str, str] | None = None,
) -> tuple[str, dict[str, str]]:
    if expected_head is None:
        return ORIGINAL_VERIFY()
    if BASE.git_output("branch", "--show-current") != "main":
        raise BASE.GateError("lab repository must remain on main")
    if BASE.git_output("status", "--porcelain=v1", "--untracked-files=all"):
        raise BASE.GateError("lab repository changed during campaign")
    head = BASE.git_output("rev-parse", "HEAD")
    if head != expected_head:
        raise BASE.GateError(f"local lab HEAD changed during campaign: {head}")
    blobs = BASE.packet_blobs()
    if blobs != dict(expected_packet_blobs or {}):
        raise BASE.GateError("packet blob identity changed during campaign")
    return head, blobs


BASE.CAMPAIGN_ID = R5_CAMPAIGN_ID
BASE.ACK = R5_ACK
BASE.RUN_ROOT = R5_RUN_ROOT
BASE.MANIFEST = R5_MANIFEST
BASE.PACKET_PATHS = R4.BASE.PACKET_PATHS + (
    "experiments/qwen36-27b-mtp-gguf-q4-b70/data/2026-08-25-qwen36-q8-f16-tp1-graph-parent-sentinel-r4-result.json",
    "experiments/qwen36-27b-mtp-gguf-q4-b70/notes/2026-08-25-qwen36-q8-f16-tp1-graph-parent-sentinel-r4-result.md",
    "experiments/qwen36-27b-mtp-gguf-q4-b70/data/2026-08-25-qwen36-q8-f16-tp1-graph-parent-sentinel-r5-prereg.json",
    "experiments/qwen36-27b-mtp-gguf-q4-b70/notes/2026-08-25-qwen36-q8-f16-tp1-graph-parent-sentinel-r5-preregistration.md",
    "experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-q8-f16-tp1-graph-parent-sentinel-r5.py",
    "experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/test_qwen36_q8_f16_tp1_graph_parent_sentinel_r5.py",
)
BASE.load_json = r5_load_json
BASE.verify_clean_pushed_main = verify_clean_pushed_main


if __name__ == "__main__":
    raise SystemExit(BASE.main())
