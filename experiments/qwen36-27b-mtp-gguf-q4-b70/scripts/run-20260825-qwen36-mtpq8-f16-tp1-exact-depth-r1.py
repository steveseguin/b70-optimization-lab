#!/usr/bin/env python3
"""Run the frozen Qwen3.6 MTP-bearing Q8_0 F16-KV exact-depth curve."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
from typing import Any


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen36-27b-mtp-gguf-q4-b70"
MANIFEST = LANE / "data/2026-08-25-qwen36-mtpq8-f16-tp1-exact-depth-prereg.json"
REFERENCE_MANIFEST = (
    LANE / "data/2026-08-25-qwen36-q4kxl-f16-tp1-exact-depth-prereg.json"
)
REFERENCE_ADAPTER = (
    LANE / "scripts/run-20260825-qwen36-q4kxl-f16-tp1-exact-depth-r1.py"
)
REFERENCE_MANIFEST_SHA256 = (
    "c5ee61e18dde93bba58edb0f03784dbc1972a82811e6b2275366c412a849fd04"
)
REFERENCE_ADAPTER_SHA256 = (
    "f6422e88eee1e6f89e3173b1a0c441d202da1499819b28a14d97268d2fea8ba2"
)
MODEL_VERIFIER = REPO / "scripts/verify-neural-download-model.py"
MODEL_VERIFIER_SHA256 = (
    "f9fbe5968e4bcd3437bb7cdf64ce215968e8958bc935ec8b4c8e76a6d24f84b2"
)
CAMPAIGN_ID = "qwen36-mtpq8-f16-tp1-exact-depth-20260825-r1"
ACK = f"RUN {CAMPAIGN_ID}"
DEPTHS = [0, 2048, 4096, 8192, 16384, 24576, 32768]
CANONICAL_LOCKS = [
    "/run/lock/muse-glimmer-gpu-exclusive.lock",
    "/tmp/b70-benchmark.lock",
    "/tmp/b70-gpu0.lock",
    "/run/user/1000/qwen36-b70-gpu-leases/gpu0.lock",
]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import frozen helper: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


REFERENCE = _load(REFERENCE_ADAPTER, "qwen36_mtpq8_f16_reference")
ENGINE = REFERENCE.BASE
VERIFIER = _load(MODEL_VERIFIER, "qwen36_mtpq8_model_verifier")
ORIGINAL_REFERENCE_LOAD_MANIFEST = REFERENCE.load_manifest
ORIGINAL_ENGINE_PREFLIGHT = ENGINE.preflight
ORIGINAL_WRITE_JSON_EXCLUSIVE = ENGINE.write_json_exclusive
_MODEL_VIEW_RECEIPT: dict[str, Any] | None = None


def load_manifest() -> dict[str, Any]:
    try:
        value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ENGINE.GateError(f"invalid Qwen3.6 MTP-Q8 campaign manifest: {exc}") from exc
    if ENGINE.sha256_file(REFERENCE_MANIFEST) != REFERENCE_MANIFEST_SHA256:
        raise ENGINE.GateError("referenced Qwen3.6 Q4XL manifest changed")
    if ENGINE.sha256_file(REFERENCE_ADAPTER) != REFERENCE_ADAPTER_SHA256:
        raise ENGINE.GateError("referenced repaired lifecycle adapter changed")
    if ENGINE.sha256_file(MODEL_VERIFIER) != MODEL_VERIFIER_SHA256:
        raise ENGINE.GateError("direct/ordinary model verifier changed")
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
        "-ub", "512", "-fa", "on", "-ctk", "f16", "-ctv", "f16",
        "-t", "16", "--poll", "50", "-r", "5", "-o", "json",
    ]
    digest = "9408dcb356cc061a05c139e5647cbde0698ff980c6a69f7fc214e9989f86cfa8"
    if not (
        value.get("schema") == "neural.download.qwen36-llama-exact-depth-prereg.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("state") == "preregistered-not-launched"
        and selectors.get("revision") == "qwen3.6-27b"
        and selectors.get("artifact_id") == "qwen36-27b-unsloth-mtp-q8-0-5cb35eb"
        and selectors.get("quantization") == "Q8_0"
        and selectors.get("tp") == 1
        and selectors.get("mtp") == 0
        and selectors.get("graph_mode") == "off"
        and selectors.get("kv") == "f16"
        and selectors.get("active_context_tokens") == DEPTHS
        and model.get("revision") == "5cb35eb3dcbf52dbce5f87dbc64df6aaffadcace"
        and model.get("size_bytes") == 29047084160
        and model.get("sha256") == digest
        and model.get("direct_sha256") == digest
        and model.get("ordinary_sha256") == digest
        and model.get("embedded_mtp_capability") is True
        and runtime.get("source_head") == ENGINE.SOURCE_HEAD
        and reference.get("manifest_sha256") == REFERENCE_MANIFEST_SHA256
        and reference.get("adapter_sha256") == REFERENCE_ADAPTER_SHA256
        and verification.get("verifier_sha256") == MODEL_VERIFIER_SHA256
        and verification.get("direct_and_ordinary_must_match") is True
        and verification.get("views_coherent_required") is True
        and value.get("argv") == expected_argv
        and value.get("environment", {}).get("GGML_SYCL_ENABLE_GRAPH") == "0"
        and lifecycle.get("exact_ack") == ACK
        and lifecycle.get("output_root")
        == "/mnt/fast-ai/bench-results/qwen36-mtpq8-f16-tp1-exact-depth-20260825-r1"
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
        raise ENGINE.GateError("Qwen3.6 MTP-Q8 F16 campaign invariant failed")
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


def preflight(manifest: dict[str, Any]):
    """Verify the backing-store view first; the inherited preflight reads ordinary next."""
    global _MODEL_VIEW_RECEIPT
    ENGINE.reject_inherited_runtime_environment(dict(os.environ))
    ENGINE.require_clean_pushed_main()
    if ENGINE.git_output("rev-parse", "HEAD", cwd=ENGINE.SOURCE) != ENGINE.SOURCE_HEAD:
        raise ENGINE.GateError("llama.cpp source HEAD changed")
    if ENGINE.git_output(
        "status", "--porcelain=v1", "--untracked-files=all", cwd=ENGINE.SOURCE
    ):
        raise ENGINE.GateError("llama.cpp source tree is not clean")
    model = Path(manifest["model"]["path"])
    if not model.is_file() or model.stat().st_size != manifest["model"]["size_bytes"]:
        raise ENGINE.GateError("model size mismatch")
    try:
        direct_digest, direct_mode = VERIFIER.hash_direct(model)
    except VERIFIER.DirectUnavailable as exc:
        raise ENGINE.GateError(f"direct model verification unavailable: {exc}") from exc
    if direct_digest != manifest["model"]["direct_sha256"]:
        raise ENGINE.GateError("direct model SHA-256 mismatch")
    result = ORIGINAL_ENGINE_PREFLIGHT(manifest)
    _MODEL_VIEW_RECEIPT = {
        "status": "verified",
        "method_order": [direct_mode, "ordinary"],
        "direct_sha256": direct_digest,
        "ordinary_sha256": manifest["model"]["ordinary_sha256"],
        "views_coherent": direct_digest == manifest["model"]["ordinary_sha256"],
        "verifier_sha256": MODEL_VERIFIER_SHA256,
    }
    return result


def metadata(manifest: dict[str, Any], libraries: list[list[str]]) -> dict[str, Any]:
    if _MODEL_VIEW_RECEIPT is None or _MODEL_VIEW_RECEIPT.get("status") != "verified":
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
        "model_view_verification": copy.deepcopy(_MODEL_VIEW_RECEIPT),
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


# Reuse only the corrected executable-identity census and hardened four-lock owner.
if REFERENCE.CANONICAL_LOCKS != CANONICAL_LOCKS:
    raise RuntimeError("referenced Qwen3.6 lock contract changed")
ENGINE.MANIFEST = MANIFEST
ENGINE.CAMPAIGN_ID = CAMPAIGN_ID
ENGINE.ACK = ACK
ENGINE.load_manifest = load_manifest
ENGINE.validate_manifest = validate_manifest
ENGINE.static_check = static_check
ENGINE.preflight = preflight
ENGINE.metadata = metadata
ENGINE.write_json_exclusive = write_json_exclusive
ENGINE.active_model_processes = REFERENCE.active_model_processes
ENGINE.campaign_locks = REFERENCE.campaign_locks


if __name__ == "__main__":
    raise SystemExit(ENGINE.main())
