#!/usr/bin/env python3
"""q8_0-KV overlay for the sealed Q4_K_M/F16 graph curve packet."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
from pathlib import Path
import sys
from typing import Any, Mapping


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen36-27b-mtp-gguf-q4-b70"
OVERLAY = LANE / "data/2026-08-25-qwen36-q4km-q8kv-tp1-sycl-graph-exact-depth-r1-prereg.json"
BASE_MANIFEST = LANE / "data/2026-08-25-qwen36-q4km-f16-tp1-sycl-graph-exact-depth-r1-prereg.json"
BASE_RUNNER = LANE / "scripts/run-20260825-qwen36-q4km-f16-tp1-sycl-graph-exact-depth-r1.py"
OFF_MANIFEST = LANE / "data/2026-08-25-qwen36-q4km-q8kv-tp1-exact-depth-r2-prereg.json"
OFF_RESULT = LANE / "data/2026-08-25-qwen36-q4km-q8kv-tp1-exact-depth-result.json"
BASE_MANIFEST_SHA256 = "d2f8de4d70013cfca6100236f35857d024b0573e81d6047a37581c76322d0561"
BASE_RUNNER_SHA256 = "0841a3beabc945c9b9c7443add3fd09fcef1a1dabab85b380cc75ee3c6c6c364"
OFF_MANIFEST_SHA256 = "3b3a2444669bb4461956c9cbcf445e207572746d414581cfe67599fb3e87a4d7"
OFF_RESULT_SHA256 = "073e5c9cdf9025ccc51fa6bd2d07cf3f65f4d01ebf252ab8675c75177e969943"
CAMPAIGN_ID = "qwen36-q4km-q8kv-tp1-sycl-graph-exact-depth-20260825-r1"
ACK = f"RUN {CAMPAIGN_ID}"
RUN_ROOT = Path(f"/mnt/fast-ai/bench-results/{CAMPAIGN_ID}")
ARTIFACT_ID = "qwen36-27b-unsloth-mtp-q4-k-m-5cb35eb"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_base():
    spec = importlib.util.spec_from_file_location("qwen36_q4km_f16_graph_for_q8kv", BASE_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import sealed Q4_K_M/F16 graph runner: {BASE_RUNNER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BASE = _load_base()
R1 = BASE.R1
GateError = BASE.GateError
BASE_LOAD_MANIFEST = BASE.load_manifest


def load_overlay() -> dict[str, Any]:
    value = R1.load_json(OVERLAY)
    base = value.get("base") or {}
    reference = value.get("accepted_graph_off_q4km_q8kv_reference") or {}
    delta = value.get("execution_identity_delta") or {}
    preserved = value.get("preserved") or {}
    lifecycle = value.get("lifecycle") or {}
    authority = value.get("authority") or {}
    if not (
        value.get("schema") == "neural.download.qwen36-llama-sycl-graph-embedded-mtp-q4km-q8kv-overlay.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("state") == "preregistered-not-launched"
        and value.get("sealing_status") == "sealed"
        and base == {
            "manifest_path": str(BASE_MANIFEST.relative_to(REPO)),
            "manifest_sha256": BASE_MANIFEST_SHA256,
            "runner_path": str(BASE_RUNNER.relative_to(REPO)),
            "runner_sha256": BASE_RUNNER_SHA256,
        }
        and reference.get("manifest_path") == str(OFF_MANIFEST.relative_to(REPO))
        and reference.get("manifest_sha256") == OFF_MANIFEST_SHA256
        and reference.get("result_path") == str(OFF_RESULT.relative_to(REPO))
        and reference.get("result_sha256") == OFF_RESULT_SHA256
        and reference.get("measurement_id") == "q36-q4km-tp1-kv-q8-context"
        and delta == {
            "only_runtime_delta": "replace both F16 KV selectors with q8_0",
            "ctk": {"from": "f16", "to": "q8_0"},
            "ctv": {"from": "f16", "to": "q8_0"},
            "corresponding_identity_label": {"selectors.kv": "q8_0"},
        }
        and preserved == {
            "contexts": R1.DEPTHS,
            "artifact_id": ARTIFACT_ID,
            "quantization": "Q4_K_M",
            "tp": 1,
            "mtp": 0,
            "graph_on_cache8": True,
            "source_model_backend_build_and_32_dso_closure": True,
            "three_patch_chain": True,
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
            "speed_floor": None,
        }
    ):
        raise GateError("Q4_K_M q8_0-KV graph overlay invariant failed")
    return value


def _replace_kv(argv: list[str], flag: str) -> None:
    if argv.count(flag) != 1 or argv[argv.index(flag) + 1] != "f16":
        raise GateError(f"sealed Q4_K_M/F16 {flag} selector changed")
    argv[argv.index(flag) + 1] = "q8_0"


def load_manifest() -> dict[str, Any]:
    load_overlay()
    for path, expected, label in (
        (BASE_MANIFEST, BASE_MANIFEST_SHA256, "Q4_K_M/F16 graph manifest"),
        (BASE_RUNNER, BASE_RUNNER_SHA256, "Q4_K_M/F16 graph runner"),
        (OFF_MANIFEST, OFF_MANIFEST_SHA256, "Q4_K_M/q8_0-KV graph-off manifest"),
        (OFF_RESULT, OFF_RESULT_SHA256, "Q4_K_M/q8_0-KV graph-off result"),
    ):
        if sha256_file(path) != expected:
            raise GateError(f"sealed {label} changed")
    value = copy.deepcopy(BASE_LOAD_MANIFEST())
    value["campaign_id"] = CAMPAIGN_ID
    value["purpose"] += " This sibling changes only F16 KV to q8_0 KV."
    value["selectors"]["kv"] = "q8_0"
    _replace_kv(value["argv_template"], "-ctk")
    _replace_kv(value["argv_template"], "-ctv")
    value["lifecycle"]["output_root"] = str(RUN_ROOT)
    value["lifecycle"]["exact_ack"] = ACK
    value["interpretation"]["fill_only"] = "the seven embedded-MTP Q4_K_M artifact TP1/MTP0/SYCL-graph/q8_0-KV cells only"
    return value


def validate_manifest(value: Mapping[str, Any]) -> None:
    expected = load_manifest()
    if dict(value) != expected:
        raise GateError("synthesized Q4_K_M/q8_0-KV manifest differs from sealed overlay")
    base = BASE_LOAD_MANIFEST()
    argv = value["argv_template"]
    if not (
        value["selectors"]["artifact_id"] == ARTIFACT_ID
        and value["selectors"]["quantization"] == "Q4_K_M"
        and value["selectors"]["mtp"] == 0
        and value["selectors"]["kv"] == "q8_0"
        and value["selectors"]["active_context_tokens"] == R1.DEPTHS
        and argv[argv.index("-ctk") + 1] == "q8_0"
        and argv[argv.index("-ctv") + 1] == "q8_0"
        and argv[-3:] == ["-v", "-o", "json"]
        and value["environment"] == base["environment"]
        and value["runtime"] == base["runtime"]
        and value["source"] == base["source"]
        and value["model"] == base["model"]
        and value["graph_evidence"] == base["graph_evidence"]
    ):
        raise GateError("Q4_K_M/q8_0-KV selectors or preserved graph identity changed")
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
        raise GateError("q8_0-KV overlay changes more than KV and create-only lifecycle identity")


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
