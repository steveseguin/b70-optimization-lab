#!/usr/bin/env python3
"""Minimal R3 lifecycle repair for the sealed fa0 graph parent sentinel.

The only data-schema repair is ``runtime.source_provenance``: it is copied
exactly from the already-sealed R2 ``source.provenance`` object. All source,
build, DSO, model, canary, and acceptance identities remain R2's.
"""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import sys
from typing import Any, Mapping


HERE = Path(__file__).resolve().parent
R2_SCRIPT = HERE / "run-20260825-qwen36-q8-f16-tp1-fa0-graph-port-parent-sentinel-r2.py"
SPEC = importlib.util.spec_from_file_location("qwen36_fa0_graph_port_parent_sentinel_r2_for_r3", R2_SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import sealed R2 lifecycle: {R2_SCRIPT}")
R2 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = R2
SPEC.loader.exec_module(R2)
BASE = R2.BASE
ORIGINAL_LOAD_JSON = R2.ORIGINAL_LOAD_JSON
ORIGINAL_CREATE_JSON = R2.ORIGINAL_CREATE_JSON

OVERLAY = BASE.LANE / "data/2026-08-25-qwen36-q8-f16-tp1-fa0-graph-port-parent-sentinel-r3-prereg.json"
NOTE = BASE.LANE / "notes/2026-08-25-qwen36-q8-f16-tp1-fa0-graph-port-parent-sentinel-r3-preregistration.md"
CAMPAIGN_ID = "qwen36-q8-f16-tp1-fa0-graph-port-sentinel-20260825-r3"
RUN_ROOT = Path("/mnt/fast-ai/bench-results/qwen36-q8-f16-tp1-fa0-graph-port-sentinel-20260825-r3")
ACK = f"RUN {CAMPAIGN_ID}"
R2_MANIFEST_REL = "experiments/qwen36-27b-mtp-gguf-q4-b70/data/2026-08-25-qwen36-q8-f16-tp1-fa0-graph-port-parent-sentinel-r2-prereg.json"
R2_MANIFEST = BASE.REPO / R2_MANIFEST_REL
R2_MANIFEST_SHA256 = "175c59eb9a2a2eb95c45f92a0c20c0bd543279d46a4b0e2051ed745db0093a96"
R2_RUNNER_REL = "experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-q8-f16-tp1-fa0-graph-port-parent-sentinel-r2.py"
R2_RUNNER_SHA256 = "4c34b1c5cdf7f1018478836c924d5264ca2914fb624559a07e15a48c4f72aa17"

PACKET_PATHS = R2.PACKET_PATHS + (
    str(OVERLAY.relative_to(BASE.REPO)),
    str(NOTE.relative_to(BASE.REPO)),
    str(Path(__file__).resolve().relative_to(BASE.REPO)),
    "experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/test_qwen36_q8_f16_tp1_fa0_graph_port_parent_sentinel_r3.py",
)


def load_overlay() -> dict[str, Any]:
    return ORIGINAL_LOAD_JSON(OVERLAY)


def validate_overlay(value: Mapping[str, Any]) -> None:
    predecessor = value.get("predecessor") or {}
    delta = value.get("only_manifest_delta") or {}
    preserved = value.get("identity_preservation") or {}
    lifecycle = value.get("lifecycle") or {}
    authority = value.get("authority") or {}
    if not (
        value.get("schema") == "neural.download.qwen36-llama-fa0-graph-port-parent-sentinel-r3-overlay.v1"
        and value.get("state") == "sealed-preregistered-not-launched"
        and value.get("campaign_id") == CAMPAIGN_ID
        and predecessor == {
            "manifest_path": R2_MANIFEST_REL,
            "manifest_sha256": R2_MANIFEST_SHA256,
            "runner_path": R2_RUNNER_REL,
            "runner_sha256": R2_RUNNER_SHA256,
            "failed_run_root": "/mnt/fast-ai/bench-results/qwen36-q8-f16-tp1-fa0-graph-port-sentinel-20260825-r2",
            "failure_stage": "campaign-identity-pre-arm",
            "failure": "KeyError: manifest['runtime']['source_provenance']",
            "arms_launched": 0,
            "evidence_must_remain_immutable": True,
        }
        and delta == {
            "runtime_source_provenance": "exact deep copy of source.provenance",
            "schema": "neural.download.qwen36-llama-fa0-graph-port-parent-sentinel-r3-runtime.v1",
            "terminal_pass_state": "passed-r3-parent-sentinel-only",
            "campaign_id": CAMPAIGN_ID,
            "output_root": str(RUN_ROOT),
            "exact_ack": ACK,
        }
        and preserved.get("source") == "byte-identical sealed R2 object"
        and preserved.get("model") == "byte-identical sealed R2 object"
        and preserved.get("runtime_except_source_provenance") == "byte-identical sealed R2 object"
        and preserved.get("effective_shared_libraries") == "byte-identical sealed R2 34-row closure"
        and preserved.get("canary") == "byte-identical sealed R2 object"
        and preserved.get("generated_tokens_per_arm") == 64
        and preserved.get("same_binary_arms") == ["off-cache0", "on-cache8"]
        and lifecycle == {
            "output_root": str(RUN_ROOT), "exact_ack": ACK, "create_only": True,
            "r1_and_r2_roots_immutable": True,
        }
        and authority == {
            "parent_sentinel_only": True,
            "curve_authorized": False,
            "site_publication_authorized": False,
            "speed_claim_authorized": False,
            "quality_claim_authorized": False,
            "record_or_submission_authorized": False,
            "protected_graph_off_values_may_be_replaced": False,
            "historical_featured_speeds_are_immutable": True,
        }
    ):
        raise BASE.GateError("fa0 graph-port R3 overlay invariant failed")


def synthesize_manifest(r2: Mapping[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    validate_overlay(overlay)
    R2.validate_manifest(r2)
    value = copy.deepcopy(dict(r2))
    value["schema"] = overlay["only_manifest_delta"]["schema"]
    value["campaign_id"] = CAMPAIGN_ID
    value["purpose"] = overlay["purpose"]
    value["runtime"]["source_provenance"] = copy.deepcopy(value["source"]["provenance"])
    value["lifecycle"]["output_root"] = str(RUN_ROOT)
    value["lifecycle"]["exact_ack"] = ACK
    value["lifecycle"]["r2_evidence_must_remain_immutable"] = True
    value["interpretation"]["terminal_pass_state"] = "passed-r3-parent-sentinel-only"
    value["r3_delta"] = copy.deepcopy(dict(overlay))
    return value


def load_manifest() -> dict[str, Any]:
    return synthesize_manifest(R2.load_manifest(), load_overlay())


def validate_manifest(value: Mapping[str, Any]) -> None:
    expected = load_manifest()
    if dict(value) != expected:
        raise BASE.GateError("fa0 graph-port R3 synthesized manifest changed outside the frozen delta")
    runtime = value["runtime"]
    source = value["source"]
    if runtime.get("source_provenance") != source.get("provenance"):
        raise BASE.GateError("R3 runtime/source provenance equality failed")
    if value["canary"].get("generated_tokens_per_arm") != 64:
        raise BASE.GateError("R3 must retain the 64-token parent arms")


def static_check() -> tuple[dict[str, Any], list[dict[str, str]]]:
    overlay = load_overlay()
    validate_overlay(overlay)
    BASE.verify_artifact(R2_MANIFEST, None, R2_MANIFEST_SHA256, "sealed R2 manifest")
    BASE.verify_artifact(R2_SCRIPT, None, R2_RUNNER_SHA256, "sealed R2 runner")
    r2_manifest, libraries = R2.static_check()
    manifest = synthesize_manifest(r2_manifest, overlay)
    validate_manifest(manifest)
    return manifest, libraries


def create_json(path: Path, value: Any) -> None:
    if path.name == "terminal-receipt.json" and isinstance(value, Mapping):
        value = {
            **value,
            "schema": "neural.download.qwen36-llama-fa0-graph-port-parent-sentinel-r3-terminal.v1",
            "parent_sentinel_only": True,
            "curve_authorized": False,
            "site_publication_authorized": False,
            "speed_claim_authorized": False,
            "protected_graph_off_values_may_be_replaced": False,
        }
    ORIGINAL_CREATE_JSON(path, value)


BASE.CAMPAIGN_ID = CAMPAIGN_ID
BASE.ACK = ACK
BASE.RUN_ROOT = RUN_ROOT
BASE.MANIFEST = OVERLAY
BASE.PACKET_PATHS = PACKET_PATHS
BASE.load_json = lambda path: load_manifest() if path == OVERLAY else ORIGINAL_LOAD_JSON(path)
BASE.validate_manifest = validate_manifest
BASE.static_check = static_check
BASE.create_json = create_json


if __name__ == "__main__":
    raise SystemExit(BASE.main())
