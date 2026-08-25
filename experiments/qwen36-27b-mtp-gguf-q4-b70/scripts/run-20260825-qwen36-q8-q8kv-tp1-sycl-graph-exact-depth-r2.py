#!/usr/bin/env python3
"""Sealed q8_0-KV sibling of the passed F16 R4 graph depth packet."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
from pathlib import Path
import sys
from typing import Any, Mapping


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen36-27b-mtp-gguf-q4-b70"
OVERLAY = LANE / "data/2026-08-25-qwen36-q8-q8kv-tp1-sycl-graph-exact-depth-r2-prereg.json"
BASE_MANIFEST = LANE / "data/2026-08-25-qwen36-q8-f16-tp1-sycl-graph-exact-depth-r4-prereg.json"
BASE_RUNNER = LANE / "scripts/run-20260825-qwen36-q8-f16-tp1-sycl-graph-exact-depth-r4.py"
Q8KV_OFF_MANIFEST = LANE / "data/2026-08-25-qwen36-q8-q8kv-tp1-exact-depth-prereg.json"
Q8KV_OFF_RESULT = LANE / "data/2026-08-25-qwen36-q8-q8kv-tp1-exact-depth-result.json"
BASE_MANIFEST_SHA256 = "32ffe76461abcfe2b57606d9d25cb3240f3b6705e0bdcacc6d52465d355b070b"
BASE_RUNNER_SHA256 = "ed3deb0c739dcadab97c26532b8bd4549178932c1926a9a0338d383e985f4602"
Q8KV_OFF_MANIFEST_SHA256 = "24924133fb2a81ca7c368018d9a136067fb38d380904f14cfec4dacf698365e2"
Q8KV_OFF_RESULT_SHA256 = "74b6373258eb2db816f5d5bbe5f69f1478313f818e3e826733b8500d45be2e59"
CAMPAIGN_ID = "qwen36-q8-q8kv-tp1-sycl-graph-exact-depth-20260825-r2"
ACK = f"RUN {CAMPAIGN_ID}"
RUN_ROOT = Path("/mnt/fast-ai/bench-results/qwen36-q8-q8kv-tp1-sycl-graph-exact-depth-20260825-r2")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_f16_r4():
    spec = importlib.util.spec_from_file_location("qwen36_q8_f16_graph_depth_r4_for_q8kv_r2", BASE_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import F16 R4 runner: {BASE_RUNNER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


F16 = _load_f16_r4()
R1 = F16.R1
GateError = F16.GateError
F16_LOAD_MANIFEST = F16.load_manifest


def load_overlay() -> dict[str, Any]:
    value = R1.load_json(OVERLAY)
    base = value.get("base") or {}
    reference = value.get("accepted_graph_off_q8kv_reference") or {}
    delta = value.get("execution_identity_delta") or {}
    preserved = value.get("preserved") or {}
    lifecycle = value.get("lifecycle") or {}
    authority = value.get("authority") or {}
    if not (
        value.get("schema") == "neural.download.qwen36-llama-sycl-graph-q8kv-exact-depth-overlay.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("state") == "preregistered-not-launched"
        and value.get("sealing_status") == "sealed"
        and value.get("supersedes_unsealed_packet") == "qwen36-q8-q8kv-tp1-fa0-graph-exact-depth-20260825-r1"
        and base == {
            "manifest_path": str(BASE_MANIFEST.relative_to(REPO)),
            "manifest_sha256": BASE_MANIFEST_SHA256,
            "runner_path": str(BASE_RUNNER.relative_to(REPO)),
            "runner_sha256": BASE_RUNNER_SHA256,
        }
        and reference.get("manifest_path") == str(Q8KV_OFF_MANIFEST.relative_to(REPO))
        and reference.get("manifest_sha256") == Q8KV_OFF_MANIFEST_SHA256
        and reference.get("result_path") == str(Q8KV_OFF_RESULT.relative_to(REPO))
        and reference.get("result_sha256") == Q8KV_OFF_RESULT_SHA256
        and delta == {
            "only_runtime_change": "replace both F16 KV selectors with q8_0",
            "ctk": {"from": "f16", "to": "q8_0"},
            "ctv": {"from": "f16", "to": "q8_0"},
            "corresponding_identity_label": {"selectors.kv": "q8_0"},
        }
        and preserved == {
            "contexts": R1.DEPTHS,
            "graph_on_cache8": True,
            "source_backend_build_model_and_32_dso_closure": True,
            "environment_and_verbose_argv": True,
            "phase_aware_prefill_and_decode_gates": True,
            "create_only_lifecycle": True,
        }
        and lifecycle == {"output_root": str(RUN_ROOT), "exact_ack": ACK}
        and authority == {
            "raw_cells_require_all_existing_gates": True,
            "quality_gate_required_before_publication": True,
            "site_publication_authorized": False,
            "record_or_submission_authorized": False,
            "quality_claim_authorized": False,
            "graph_estimates_forbidden": True,
            "protected_graph_off_values_must_not_be_replaced": True,
        }
    ):
        raise GateError("q8-KV R2 overlay invariant failed")
    return value


def _replace_kv(template: list[str], flag: str) -> None:
    if template.count(flag) != 1 or template[template.index(flag) + 1] != "f16":
        raise GateError(f"F16 R4 {flag} selector changed")
    template[template.index(flag) + 1] = "q8_0"


def load_manifest() -> dict[str, Any]:
    load_overlay()
    for path, expected, label in (
        (BASE_MANIFEST, BASE_MANIFEST_SHA256, "F16 R4 manifest"),
        (BASE_RUNNER, BASE_RUNNER_SHA256, "F16 R4 runner"),
        (Q8KV_OFF_MANIFEST, Q8KV_OFF_MANIFEST_SHA256, "q8-KV graph-off manifest"),
        (Q8KV_OFF_RESULT, Q8KV_OFF_RESULT_SHA256, "q8-KV graph-off result"),
    ):
        if sha256_file(path) != expected:
            raise GateError(f"sealed {label} changed")
    value = copy.deepcopy(F16_LOAD_MANIFEST())
    value["campaign_id"] = CAMPAIGN_ID
    value["purpose"] = value["purpose"].replace("F16-KV", "q8_0-KV")
    value["selectors"]["kv"] = "q8_0"
    _replace_kv(value["argv_template"], "-ctk")
    _replace_kv(value["argv_template"], "-ctv")
    value["lifecycle"]["output_root"] = str(RUN_ROOT)
    value["lifecycle"]["exact_ack"] = ACK
    value["interpretation"]["fill_only"] = value["interpretation"]["fill_only"].replace("F16-KV", "q8_0-KV")
    return value


def validate_manifest(value: Mapping[str, Any]) -> None:
    expected = load_manifest()
    if dict(value) != expected:
        raise GateError("q8-KV R2 synthesized manifest differs from sealed overlay")
    template = value["argv_template"]
    if not (
        value["selectors"]["kv"] == "q8_0"
        and template[template.index("-ctk") + 1] == "q8_0"
        and template[template.index("-ctv") + 1] == "q8_0"
        and template[-3:] == ["-v", "-o", "json"]
    ):
        raise GateError("q8-KV selectors or verbose argv changed")
    base = F16_LOAD_MANIFEST()
    reconstructed = copy.deepcopy(dict(value))
    reconstructed["campaign_id"] = base["campaign_id"]
    reconstructed["purpose"] = base["purpose"]
    reconstructed["selectors"]["kv"] = "f16"
    reconstructed["argv_template"][reconstructed["argv_template"].index("-ctk") + 1] = "f16"
    reconstructed["argv_template"][reconstructed["argv_template"].index("-ctv") + 1] = "f16"
    reconstructed["lifecycle"]["output_root"] = base["lifecycle"]["output_root"]
    reconstructed["lifecycle"]["exact_ack"] = base["lifecycle"]["exact_ack"]
    reconstructed["interpretation"]["fill_only"] = base["interpretation"]["fill_only"]
    if reconstructed != base:
        raise GateError("q8-KV R2 changes more than KV selectors and corresponding identity/lifecycle labels")


# Rebind the inherited sealed lifecycle; F16's phase-aware parser remains set.
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
