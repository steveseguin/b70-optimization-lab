#!/usr/bin/env python3
"""Run the frozen Unsloth Qwen3.6 target-only Q8_0 q8_0-KV depth curve."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen36-27b-mtp-gguf-q4-b70"
MANIFEST = LANE / "data/2026-08-25-qwen36-q8-q8kv-tp1-exact-depth-prereg.json"
REFERENCE_MANIFEST = (
    LANE / "data/2026-08-25-qwen36-q8-f16-tp1-exact-depth-prereg.json"
)
REFERENCE_ADAPTER = (
    LANE / "scripts/run-20260825-qwen36-q8-f16-tp1-exact-depth-r1.py"
)
REFERENCE_MANIFEST_SHA256 = (
    "98a9d7df14b2f9679435259651620c22458a5eb80e193c9642532fdca20da244"
)
REFERENCE_ADAPTER_SHA256 = (
    "60947b6e5f6d5579cefbf911c9d0186529cecf5bd36b1c75bf947e38ccc7cb9a"
)
CAMPAIGN_ID = "qwen36-q8-q8kv-tp1-exact-depth-20260825-r1"
ACK = f"RUN {CAMPAIGN_ID}"
DEPTHS = [0, 2048, 4096, 8192, 16384, 24576, 32768]
CANONICAL_LOCKS = [
    "/run/lock/muse-glimmer-gpu-exclusive.lock",
    "/tmp/b70-benchmark.lock",
    "/tmp/b70-gpu0.lock",
    "/run/user/1000/qwen36-b70-gpu-leases/gpu0.lock",
]


def _load_reference():
    spec = importlib.util.spec_from_file_location(
        "qwen36_q8_q8kv_reference", REFERENCE_ADAPTER
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import lifecycle adapter: {REFERENCE_ADAPTER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


REFERENCE = _load_reference()
ENGINE = REFERENCE.ENGINE
ORIGINAL_REFERENCE_LOAD_MANIFEST = REFERENCE.load_manifest
ORIGINAL_WRITE_JSON_EXCLUSIVE = ENGINE.write_json_exclusive


def load_manifest() -> dict[str, Any]:
    try:
        value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ENGINE.GateError(f"invalid target-only Qwen3.6 q8_0 manifest: {exc}") from exc
    if ENGINE.sha256_file(REFERENCE_MANIFEST) != REFERENCE_MANIFEST_SHA256:
        raise ENGINE.GateError("referenced target-only Q8 F16 manifest changed")
    if ENGINE.sha256_file(REFERENCE_ADAPTER) != REFERENCE_ADAPTER_SHA256:
        raise ENGINE.GateError("referenced target-only Q8 F16 adapter changed")
    reference = ORIGINAL_REFERENCE_LOAD_MANIFEST()
    expanded = copy.deepcopy(value)
    expanded["runtime"] = copy.deepcopy(reference["runtime"])
    expanded["environment"] = copy.deepcopy(reference["environment"])
    return expanded


def validate_manifest(value: dict[str, Any]) -> None:
    selectors = value.get("selectors") or {}
    model = value.get("model") or {}
    runtime = value.get("runtime") or {}
    lifecycle = value.get("lifecycle") or {}
    interpretation = value.get("interpretation") or {}
    reference = value.get("runtime_reference") or {}
    verification = value.get("model_view_verification") or {}
    expected_argv = [
        runtime.get("binary", {}).get("path"),
        "-m", model.get("path"), "-dev", "SYCL0", "-ngl", "99",
        "-sm", "layer", "-p", "2048", "-n", "128", "-d",
        "0,2048,4096,8192,16384,24576,32768", "-b", "2048",
        "-ub", "512", "-fa", "on", "-ctk", "q8_0", "-ctv", "q8_0",
        "-t", "16", "--poll", "50", "-r", "5", "-o", "json",
    ]
    digest = "f93f517f38e696d35a1a7df2c0e3155a64f4c4dcd662107a146ae263f7fb14ce"
    if not (
        value.get("schema") == "neural.download.qwen36-llama-exact-depth-prereg.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("state") == "preregistered-not-launched"
        and selectors.get("revision") == "qwen3.6-27b"
        and selectors.get("artifact_id") == "qwen36-27b-unsloth-q8-0-82d411a"
        and selectors.get("quantization") == "Q8_0"
        and selectors.get("tp") == 1
        and selectors.get("mtp") == 0
        and selectors.get("graph_mode") == "off"
        and selectors.get("kv") == "q8_0"
        and selectors.get("active_context_tokens") == DEPTHS
        and model.get("repository") == "unsloth/Qwen3.6-27B-GGUF"
        and model.get("revision") == "82d411acf4a06cfb8d9b073a5211bf410bfc29bf"
        and model.get("artifact_last_change_commit")
        == "9e3417c2ce78c6214c8be9cb7a8b0927b1be2c8b"
        and model.get("path")
        == "/mnt/usb-models/models/qwen36-27b-q8-gguf/Qwen3.6-27B-Q8_0.gguf"
        and model.get("size_bytes") == 28595763424
        and model.get("sha256") == digest
        and model.get("direct_sha256") == digest
        and model.get("ordinary_sha256") == digest
        and model.get("embedded_mtp_capability") is False
        and runtime.get("source_head") == ENGINE.SOURCE_HEAD
        and reference.get("manifest_sha256") == REFERENCE_MANIFEST_SHA256
        and reference.get("adapter_sha256") == REFERENCE_ADAPTER_SHA256
        and verification.get("verifier_sha256") == REFERENCE.REFERENCE.MODEL_VERIFIER_SHA256
        and verification.get("direct_and_ordinary_must_match") is True
        and verification.get("views_coherent_required") is True
        and value.get("argv") == expected_argv
        and value.get("environment", {}).get("GGML_SYCL_ENABLE_GRAPH") == "0"
        and lifecycle.get("exact_ack") == ACK
        and lifecycle.get("output_root")
        == "/mnt/fast-ai/bench-results/qwen36-q8-q8kv-tp1-exact-depth-20260825-r1"
        and lifecycle.get("output_fstype") == "ext4"
        and lifecycle.get("timeout_seconds") == 5400
        and lifecycle.get("requires_clean_pushed_main") is True
        and lifecycle.get("requires_no_server_or_container") is True
        and lifecycle.get("required_locks") == CANONICAL_LOCKS
        and lifecycle.get("artifacts_are_create_only") is True
        and lifecycle.get("terminal_receipt_required") is True
        and interpretation.get("speed_floor") is None
        and interpretation.get("new_quality_gate") is False
        and interpretation.get("cell_gain_on_pass") == 7
        and interpretation.get("site_publication_authorized") is False
        and interpretation.get("record_or_submission_authorized") is False
        and interpretation.get("quality_claim_authorized") is False
        and interpretation.get("historical_featured_speeds_are_immutable") is True
        and interpretation.get("cross_revision_or_quantization_transfer_allowed") is False
    ):
        raise ENGINE.GateError("target-only Qwen3.6 Q8 q8_0 campaign invariant failed")
    libraries = runtime.get("effective_shared_libraries")
    if not isinstance(libraries, list) or len(libraries) != 32:
        raise ENGINE.GateError("exactly 32 effective shared-library rows are required")
    if len({row[0] for row in libraries if len(row) == 4}) != 32:
        raise ENGINE.GateError("shared-library inventory is malformed or duplicated")


def static_check() -> dict[str, Any]:
    manifest = load_manifest()
    validate_manifest(manifest)
    if ENGINE.sha256_file(ENGINE.PARSER) != ENGINE.EXPECTED_PARSER_SHA256:
        raise ENGINE.GateError("exact-depth parser changed")
    if ENGINE.sha256_file(ENGINE.PROTECTED) != ENGINE.EXPECTED_PROTECTED_SHA256:
        raise ENGINE.GateError("protected historical speed manifest changed")
    return manifest


def metadata(manifest: dict[str, Any], libraries: list[list[str]]) -> dict[str, Any]:
    receipt = REFERENCE.REFERENCE._MODEL_VIEW_RECEIPT
    if receipt is None or receipt.get("status") != "verified":
        raise ENGINE.GateError("direct/ordinary model verification receipt is absent")
    return {
        "schema": "llama-bench-exact-depth-metadata-v1",
        "receipt_id": CAMPAIGN_ID,
        "declared_depths": DEPTHS,
        "binary": {
            **manifest["runtime"]["binary"],
            "source_head": ENGINE.SOURCE_HEAD,
            "effective_shared_libraries": libraries,
        },
        "model": manifest["model"],
        "model_view_verification": copy.deepcopy(receipt),
        "argv": manifest["argv"],
        "env": manifest["environment"],
        "cell_selectors": {
            key: item
            for key, item in manifest["selectors"].items()
            if key not in {"active_context_tokens", "graph_mode"}
        },
        "graph": {
            "requested": False,
            "capture": {"count": 0, "source": "GGML_SYCL_ENABLE_GRAPH=0"},
            "replay": {"count": 0, "source": "GGML_SYCL_ENABLE_GRAPH=0"},
        },
    }


def write_json_exclusive(path: Path, value: Any) -> None:
    if path.name == "terminal-receipt.json" and isinstance(value, dict):
        value = copy.deepcopy(value)
        value["schema"] = "neural.download.qwen36-llama-exact-depth-terminal.v1"
        value["site_publication_authorized"] = False
        value["record_or_submission_authorized"] = False
        value["quality_claim_authorized"] = False
    ORIGINAL_WRITE_JSON_EXCLUSIVE(path, value)


if REFERENCE.CANONICAL_LOCKS != CANONICAL_LOCKS:
    raise RuntimeError("referenced target-only Q8 lock contract changed")
ENGINE.MANIFEST = MANIFEST
ENGINE.CAMPAIGN_ID = CAMPAIGN_ID
ENGINE.ACK = ACK
ENGINE.load_manifest = load_manifest
ENGINE.validate_manifest = validate_manifest
ENGINE.static_check = static_check
ENGINE.preflight = REFERENCE.REFERENCE.preflight
ENGINE.metadata = metadata
ENGINE.write_json_exclusive = write_json_exclusive
ENGINE.active_model_processes = REFERENCE.REFERENCE.REFERENCE.active_model_processes
ENGINE.campaign_locks = REFERENCE.REFERENCE.REFERENCE.campaign_locks


if __name__ == "__main__":
    raise SystemExit(ENGINE.main())
