#!/usr/bin/env python3
"""R2 wrapper for the target-Q8/F16 TP1 SYCL-graph exact-depth curve.

The sealed R1 lifecycle is reused. The sole execution identity change is
``-v`` immediately before ``-o json`` so info-level graph evidence is visible.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any, Mapping


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen36-27b-mtp-gguf-q4-b70"
OVERLAY = LANE / "data/2026-08-25-qwen36-q8-f16-tp1-sycl-graph-exact-depth-r2-prereg.json"
BASE_MANIFEST = LANE / "data/2026-08-25-qwen36-q8-f16-tp1-sycl-graph-exact-depth-prereg.json"
BASE_RUNNER = LANE / "scripts/run-20260825-qwen36-q8-f16-tp1-sycl-graph-exact-depth-r1.py"
BASE_MANIFEST_SHA256 = "07ade7f9a89f2845e5d5b4a61c5eb6f63663435ecb882d5f3885a1aaa51b9395"
BASE_RUNNER_SHA256 = "f713abacab63782e5c512dff23c5d888d46f1df948d3ccc95ec6d27e3edaff14"
CAMPAIGN_ID = "qwen36-q8-f16-tp1-sycl-graph-exact-depth-20260825-r2"
ACK = f"RUN {CAMPAIGN_ID}"
RUN_ROOT = Path("/mnt/fast-ai/bench-results/qwen36-q8-f16-tp1-sycl-graph-exact-depth-20260825-r2")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_r1():
    spec = importlib.util.spec_from_file_location("qwen36_q8_f16_sycl_graph_depth_r1_for_r2", BASE_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import R1 runner: {BASE_RUNNER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


R1 = _load_r1()
GateError = R1.GateError
R1_VALIDATE_MANIFEST = R1.validate_manifest


def load_overlay() -> dict[str, Any]:
    value = R1.load_json(OVERLAY)
    base = value.get("base") or {}
    delta = value.get("execution_identity_delta") or {}
    lifecycle = value.get("lifecycle") or {}
    authority = value.get("authority") or {}
    if not (
        value.get("schema") == "neural.download.qwen36-llama-sycl-graph-exact-depth-overlay.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("state") == "preregistered-not-launched"
        and base == {
            "manifest_path": str(BASE_MANIFEST.relative_to(REPO)),
            "manifest_sha256": BASE_MANIFEST_SHA256,
            "runner_path": str(BASE_RUNNER.relative_to(REPO)),
            "runner_sha256": BASE_RUNNER_SHA256,
        }
        and delta.get("insert") == "-v"
        and delta.get("before") == "-o"
        and delta.get("following_value") == "json"
        and lifecycle == {"output_root": str(RUN_ROOT), "exact_ack": ACK}
        and authority == {
            "raw_cells_require_all_existing_gates": True,
            "site_publication_authorized": False,
            "record_or_submission_authorized": False,
            "quality_claim_authorized": False,
            "graph_estimates_forbidden": True,
            "protected_graph_off_values_must_not_be_replaced": True,
        }
    ):
        raise GateError("R2 overlay invariant failed")
    return value


def load_manifest() -> dict[str, Any]:
    load_overlay()
    if sha256_file(BASE_MANIFEST) != BASE_MANIFEST_SHA256:
        raise GateError("sealed R1 base manifest changed")
    if sha256_file(BASE_RUNNER) != BASE_RUNNER_SHA256:
        raise GateError("sealed R1 base runner changed")
    value = R1.load_json(BASE_MANIFEST)
    template = value.get("argv_template")
    if not isinstance(template, list) or template[-2:] != ["-o", "json"] or "-v" in template:
        raise GateError("R1 argv is not the sealed non-verbose base")
    value = copy.deepcopy(value)
    value["campaign_id"] = CAMPAIGN_ID
    value["purpose"] = value["purpose"] + " R2 exposes info-level graph evidence with llama-bench -v."
    value["argv_template"] = [*template[:-2], "-v", "-o", "json"]
    value["lifecycle"]["output_root"] = str(RUN_ROOT)
    value["lifecycle"]["exact_ack"] = ACK
    return value


def validate_manifest(value: Mapping[str, Any]) -> None:
    expected = load_manifest()
    if dict(value) != expected:
        raise GateError("R2 synthesized manifest differs from sealed overlay")
    R1_VALIDATE_MANIFEST(value)
    template = value["argv_template"]
    if template[-3:] != ["-v", "-o", "json"] or template.count("-v") != 1:
        raise GateError("R2 must insert exactly one -v immediately before -o json")
    base = R1.load_json(BASE_MANIFEST)
    reconstructed = copy.deepcopy(dict(value))
    reconstructed["campaign_id"] = base["campaign_id"]
    reconstructed["purpose"] = base["purpose"]
    reconstructed["argv_template"] = [*template[:-3], "-o", "json"]
    reconstructed["lifecycle"]["output_root"] = base["lifecycle"]["output_root"]
    reconstructed["lifecycle"]["exact_ack"] = base["lifecycle"]["exact_ack"]
    if reconstructed != base:
        raise GateError("R2 changes more than campaign lifecycle identity and llama-bench -v")


# Rebind the mature R1 lifecycle to the distinct create-only R2 identity.
R1.MANIFEST = OVERLAY
R1.CAMPAIGN_ID = CAMPAIGN_ID
R1.ACK = ACK
R1.RUN_ROOT = RUN_ROOT
R1.load_manifest = load_manifest
R1.validate_manifest = validate_manifest


def main(argv: list[str] | None = None) -> int:
    return R1.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
